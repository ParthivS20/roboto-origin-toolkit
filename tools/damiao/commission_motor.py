#!/usr/bin/env python3
"""Set Damiao motor/Master IDs and save parameters using a SLCAN USB2CAN adapter.

Run on an external computer with exactly one motor connected. Close DMTool first.
Requires Damiao SLCAN firmware. Never enables motion or changes the motor zero.
"""
import argparse
import threading
import queue
import struct
import sys
import time


def parameter(motor, command, register, value=0):
    return struct.pack("<HBBI", motor, command, register, value)


class SlcanAdapter:
    """python-can SLCAN with Damiao's nonstandard S5 = 1 Mbps mapping."""
    def __init__(self, port):
        try:
            import can
            from serial.tools import list_ports
        except ImportError as exc:
            raise RuntimeError("Install dependencies: python -m pip install -r tools/requirements.txt") from exc
        if port is None:
            ports = [p.device for p in list_ports.comports() if p.vid == 0x34B7 and p.pid == 0x6877]
            if len(ports) != 1:
                raise RuntimeError(f"Expected one Damiao serial adapter; found {ports}. Supply --port.")
            port = ports[0]
            if sys.platform == 'darwin':
                port = port.replace('/dev/tty.', '/dev/cu.')
        print(f"Opening python-can SLCAN on {port} · UART 921600 · CAN S5 / 1 Mbps", flush=True)
        self.can = can
        self.bus = None
        try:
            # Do not pass bitrate=1M: generic SLCAN would select S8 (5M on Damiao).
            self.bus = can.Bus(interface='slcan', channel=port, tty_baudrate=921600,
                               bitrate=None, sleep_after_open=0.2)
            self.bus.close()
            self.bus.serialPortOrig.write(b'S5\r')
            self.bus.serialPortOrig.flush()
            self.bus.open()
        except Exception as exc:
            if self.bus:
                self.bus.shutdown()
            raise RuntimeError(f"Cannot open SLCAN: {exc}") from exc
        self.frames = queue.Queue()
        self.stopping = threading.Event()
        self.receive_error = None
        self.reader = threading.Thread(target=self.receive, daemon=True)
        self.reader.start()
    def send(self, can_id, payload, log=True):
        if self.receive_error:
            raise RuntimeError(f"SLCAN receive failed: {self.receive_error}")
        if log:
            print(f"TX {can_id:#05x}: {payload.hex(' ').upper()}", flush=True)
        try:
            self.bus.send(self.can.Message(arbitration_id=can_id, is_extended_id=False,
                                          data=payload), timeout=1)
        except Exception as exc:
            raise RuntimeError(f"SLCAN transmit failed: {exc}") from exc
    def receive(self):
        try:
            while not self.stopping.is_set():
                msg = self.bus.recv(timeout=0.05)
                if msg is None or msg.is_extended_id or msg.is_remote_frame or msg.is_error_frame:
                    continue
                ident = msg.arbitration_id
                if ident <= 0x7FF:
                    self.frames.put((ident, bytes(msg.data[:msg.dlc])))
        except Exception as exc:
            self.receive_error = str(exc)

    def close(self):
        self.stopping.set()
        self.reader.join(timeout=1)
        self.bus.shutdown()

    def auto_detect(self, duration=1.0):
        """Probe all permitted standard motor IDs, collecting firmware replies."""
        while True:
            try:
                self.frames.get_nowait()
            except queue.Empty:
                break
        print("Auto-detect: probing motor IDs 0x000–0x7FE for firmware replies (1 second).")
        deadline = time.monotonic() + duration
        found, queried = {}, set()

        def collect():
            while True:
                try:
                    ident, data = self.frames.get_nowait()
                except queue.Empty:
                    return
                if len(data) != 8 or data[2:4] != bytes([0x33, 0x0E]):
                    continue
                motor_id = int.from_bytes(data[:2], "little")
                if motor_id in queried and 0 <= ident <= 0x7FF:
                    found[(motor_id, ident)] = int.from_bytes(data[4:], "little")

        for motor_id in range(0x7FF):
            if time.monotonic() >= deadline:
                raise RuntimeError("Auto-detect could not probe all IDs within 1 second; no settings written")
            queried.add(motor_id)
            self.send(0x7FF, parameter(motor_id, 0x33, 0x0E)[:4], log=False)
            collect()
        while time.monotonic() < deadline:
            collect()
            time.sleep(min(0.001, max(0, deadline-time.monotonic())))
        collect()
        if not found:
            raise RuntimeError("Auto-detect: no motor firmware reply received; check power, wiring and CAN bitrate")
        if len(found) != 1:
            ids = ", ".join(f"motor={mid:#x}, Master={master:#x}" for mid, master in sorted(found))
            raise RuntimeError(f"Only 1 motor can be connected. Found {len(found)} responding motor/Master pairs: {ids}")
        (motor_id, master), firmware = next(iter(found.items()))
        print(f"Found motor at ID {motor_id:#x} ({motor_id}), Master {master:#x}; FW={version(firmware)}")
        return motor_id, master

    def exchange(self, can_id, payload, match, timeout=2):
        while True:
            try:
                self.frames.get_nowait()
            except queue.Empty:
                break
        self.send(can_id, payload)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                ident, response = self.frames.get(timeout=max(0.001, deadline-time.monotonic()))
            except queue.Empty:
                break
            if match(ident, response):
                print(f"RX {ident:#05x}: {response.hex(' ').upper()}")
                return ident, response
        raise TimeoutError(f"No matching reply to {payload.hex(' ')}. Stop; inspect wiring/current ID.")

class Motor:
    def __init__(self, bus, current):
        self.bus, self.id, self.master = bus, current, None

    def read(self, register, motor=None, timeout=2):
        motor = self.id if motor is None else motor
        packet = parameter(motor, 0x33, register)[:4]
        ident, data = self.bus.exchange(0x7FF, packet,
            lambda ident, data: len(data) == 8 and data[:4] == packet[:4]
            and (motor != self.id or self.master is None or ident == self.master), timeout)
        return ident, struct.unpack("<I", data[4:])[0]

    def check_connection(self, label):
        # Version reads are non-mutating probes. The payload carries the motor ID;
        # the CAN frame ID carries its configured feedback/Master ID.
        response_id, firmware = self.read(0x0E)
        if self.master is None:
            self.master = response_id
        try:
            _, bootloader = self.read(0x25)
            bootloader_display = version(bootloader)
        except (OSError, RuntimeError, TimeoutError) as exc:
            bootloader_display = f"ERROR: {exc}"
        _, actual = self.read(8)
        _, master = self.read(7)
        if actual != self.id or master != self.master:
            raise RuntimeError("Connection check: motor or feedback ID mismatch")
        print(f"{label}: motor={actual:#x}, response/master={master:#x}; "
              f"FW={version(firmware)}, bootloader={bootloader_display}")
        return firmware

    def write(self, register, value):
        new_id = value if register == 8 else self.id
        new_master = value if register == 7 else self.master
        expected = parameter(new_id, 0x55, register, value)
        self.bus.exchange(0x7FF, parameter(self.id, 0x55, register, value),
            lambda ident, data: ident == new_master and data == expected)
        self.id, self.master = new_id, new_master
        _, actual = self.read(register)
        if actual != value:
            raise RuntimeError(f"Register {register:#x} readback mismatch")

    def command(self, command):
        return self.bus.exchange(self.id, b"\xff" * 7 + bytes([command]),
            lambda ident, data: ident == self.master and len(data) == 8
            and (data[0] & 15) == (self.id & 15))[1]

    def save(self):
        packet = struct.pack("<HBB", self.id, 0xAA, 1)
        self.bus.exchange(0x7FF, packet,
            lambda ident, data: ident == self.master and data[:4] == packet)
        time.sleep(0.1)


def version(value):
    raw = struct.pack("<I", value)
    # This motor reports ASCII version digits (e.g. 36 31 31 37 = 6.1.1.7).
    if all(48 <= byte <= 57 for byte in raw):
        decoded = ".".join(chr(byte) for byte in raw)
    elif value == 0:
        decoded = "0.0.0.0"
    else:
        decoded = "unknown encoding"
    return f"{decoded} [raw {raw.hex(' ').upper()}]"


def can_id(value):
    try:
        number = int(value, 16) if value.lower().startswith("0x") else int(value, 10)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Use decimal or 0x-prefixed hexadecimal") from exc
    if not 0 <= number < 0x7FF:
        raise argparse.ArgumentTypeError("ID must be 0..0x7FE; 0x7FF is reserved here")
    return number


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    detection = parser.add_mutually_exclusive_group()
    detection.add_argument("--current-id", type=can_id)
    detection.add_argument("--auto-detect", action="store_true", help="Probe firmware for 1 second; require one motor and Enter before writing")
    parser.add_argument("--motor-id", "--slave-id", dest="slave_id", type=can_id, required=True,
                        help="Target motor CAN ID (0x-prefixed hex); Master is motor + 0x10")
    parser.add_argument("--port", help="Serial port; automatically detects one Damiao adapter if omitted")
    parser.add_argument("--check", action="store_true", help="Read IDs and versions only; no motor changes")
    args = parser.parse_args()
    args.master_id = args.slave_id + 0x10
    if args.slave_id == 0 or args.master_id >= 0x7FF:
        parser.error("Motor ID must be nonzero and motor + 0x10 must be below reserved ID 0x7FF")
    if args.current_id is None:
        args.auto_detect = True
    print(f"Target motor={args.slave_id:#x}; derived Master={args.master_id:#x}", flush=True)
    bus = None
    motor_commands_started = False
    try:
        bus = SlcanAdapter(args.port)
        current_id = args.current_id
        discovered_master = None
        if args.auto_detect:
            current_id, discovered_master = bus.auto_detect()
            if not args.check:
                input("Press Enter to continue with the requested ID changes (Ctrl+C to cancel): ")
        motor = Motor(bus, current_id)
        motor.master = discovered_master
        before_firmware = motor.check_connection("Before")
        if args.check:
            return 0
        # Check destination before changing anything. Exactly one motor must be wired.
        if args.slave_id != motor.id:
            try:
                motor.read(8, motor=args.slave_id, timeout=0.3)
            except TimeoutError:
                pass
            else:
                raise RuntimeError("New motor ID already responds; disconnect other motors")
        motor_commands_started = True
        motor.command(0xFD)  # Disable; never send enable or a motion setpoint.
        if args.master_id != motor.master:
            motor.write(7, args.master_id)
        if args.slave_id != motor.id:
            motor.write(8, args.slave_id)
        motor.command(0xFD)
        motor.save()
        after_firmware = motor.check_connection("After")
        if after_firmware != before_firmware:
            raise RuntimeError("Firmware version changed unexpectedly")
        print(f"Saved: motor={motor.id:#x}, master={motor.master:#x}; zero position unchanged, motor disabled.")
        print("Power-cycle and run with --check to verify persistence.")
        return 0
    except (OSError, RuntimeError, TimeoutError) as exc:
        detail = ("Changes may be partially applied; do not retry using the old ID blindly."
                  if motor_commands_started else "No motor settings were written.")
        print(f"ERROR: {exc}\n{detail}", file=sys.stderr)
        return 1
    except (KeyboardInterrupt, EOFError):
        print("Cancelled; no further commands sent.", file=sys.stderr)
        return 1
    finally:
        if bus:
            bus.close()


if __name__ == "__main__":
    sys.exit(main())
