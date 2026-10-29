"""Classic Linux SocketCAN; no ROS, DMTool, pip packages, or ID writes."""
import select
import socket
import struct
import time

FRAME = struct.Struct('=IB3x8s')
NEUTRAL_MIT = bytes.fromhex('7F FF 7F F0 00 00 07 FF')  # kp=kd=0, nominal v/t=0


class Cancelled(Exception):
    pass


class SocketCAN:
    def __init__(self, interface):
        if not hasattr(socket, 'AF_CAN'):
            raise RuntimeError('Live mode requires Linux SocketCAN (run on the RDK).')
        self.sock = socket.socket(socket.AF_CAN, socket.SOCK_RAW, socket.CAN_RAW)
        try:
            self.sock.bind((interface,))
            self.sock.setblocking(False)
        except BaseException:
            self.sock.close()
            raise

    def send(self, ident, data):
        self.sock.send(FRAME.pack(ident, len(data), data.ljust(8, b'\0')))

    def drain(self):
        while select.select([self.sock], [], [], 0)[0]:
            self.sock.recv(16)

    def exchange(self, ident, data, matcher, timeout, cancelled):
        self.drain()
        if cancelled():
            raise Cancelled()
        start = time.monotonic()
        self.send(ident, data)
        while time.monotonic() - start < timeout:
            if cancelled():
                raise Cancelled()
            if not select.select([self.sock], [], [], min(0.025, timeout))[0]:
                continue
            packet = self.sock.recv(16)
            if len(packet) != 16:
                continue
            response_id, length, payload = FRAME.unpack(packet)
            # Reject extended, RTR, error frames and malformed DLCs.
            if response_id & 0xE0000000 or length != 8:
                continue
            if matcher(response_id, payload):
                return payload, (time.monotonic()-start)*1000
        raise TimeoutError('No matching reply within %.2f s' % timeout)

    def close(self):
        self.sock.close()


def read_register(bus, motor, register, timeout, cancelled):
    request = struct.pack('<HBBI', motor['id'], 0x33, register, 0)
    data, latency = bus.exchange(0x7FF, request,
        lambda ident, data: ident == motor['master'] and data[:4] == request[:4],
        timeout, cancelled)
    return int.from_bytes(data[4:], 'little'), latency


def command(bus, motor, code, timeout, cancelled):
    data, latency = bus.exchange(motor['id'], b'\xff'*7 + bytes([code]),
        lambda ident, data: ident == motor['master']
        and data[0] & 15 == motor['id'] & 15, timeout, cancelled)
    status = data[0] >> 4
    if status >= 8:
        raise RuntimeError('Motor fault 0x%X (raw %s)' % (status, data.hex(' ')))
    return dict(latency_ms=round(latency, 1), raw=data.hex(' ').upper(), status=status,
                mos_c=data[6], rotor_c=data[7])


class DemoCAN:
    """Deterministic simulator. A missing motor is never enabled by the runner."""
    def __init__(self, interface, missing=()):
        self.interface, self.missing = interface, missing
        self.enabled = set()

    def send(self, ident, data):
        if data == b'\xff'*7 + b'\xfd':
            self.enabled.discard(ident)

    def exchange(self, ident, data, matcher, timeout, cancelled):
        motor = int.from_bytes(data[:2], 'little') if ident == 0x7FF else ident
        end = time.monotonic() + (timeout if motor in self.missing else 0.09)
        while time.monotonic() < end:
            if cancelled():
                raise Cancelled()
            time.sleep(0.01)
        if motor in self.missing:
            raise TimeoutError('Simulated missing reply')
        if ident == 0x7FF:
            values = {7: motor+16, 8: motor, 10: 1}
            response = data[:4] + struct.pack('<I', values[data[3]])
        else:
            if data[-1] == 0xFC:
                self.enabled.add(motor)
            else:
                self.enabled.discard(motor)
            response = bytes([(motor & 15) | (16 if motor in self.enabled else 0)]) + bytes.fromhex('7F FF 7F F8 00 1E 1C')
        if not matcher(motor+16, response):
            raise RuntimeError('Simulator reply rejected')
        return response, 90.0

    def close(self):
        pass
