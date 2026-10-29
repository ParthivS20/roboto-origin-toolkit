"""Shared standard-library SocketCAN helpers for physical robot commissioning."""
import fcntl
import math
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'motor_comms_verifier'))
from canbus import SocketCAN, command, read_register
from topology import MOTORS


def acquire_lock():
    handle = open('/tmp/roboto-led-commissioning.lock', 'a')
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        raise RuntimeError('Stop the commissioning UI server before using this script')
    if any(read_comm(p) == 'inference_node' for p in Path('/proc').glob('[0-9]*/comm')):
        handle.close()
        raise RuntimeError('Stop inference_node first')
    return handle


def verify_interfaces():
    # Linux enumeration changed after reboot; never trust names alone.
    for index in range(4):
        device = Path(f'/sys/class/net/can{index}/device').resolve().name
        expected = f'1-1.1.{index+1}:1.0'
        if device != expected:
            raise RuntimeError(f'can{index} maps to {device}, expected USB {expected}; '
                               'correct interface mapping before commissioning')


def read_comm(path):
    try:
        return path.read_text().strip()
    except OSError:
        return ''


def read_float(bus, motor, register):
    bits, _ = read_register(bus, motor, register, .5, lambda: False)
    value = struct.unpack('<f', struct.pack('<I', bits))[0]
    if not math.isfinite(value) or value <= 0:
        raise RuntimeError(f"ID {motor['id']}: invalid scale register {register:#x}: {value}")
    return value


def preflight(bus, motor):
    for register, expected in ((8, motor['id']), (7, motor['master']), (10, 1)):
        actual, _ = read_register(bus, motor, register, .5, lambda: False)
        if actual != expected:
            raise RuntimeError(f"ID {motor['id']}: register {register:#x} expected {expected}, got {actual}")
    return tuple(read_float(bus, motor, reg) for reg in (0x15, 0x16, 0x17))


def sample(bus, motor, scales, timeout=.3):
    request = struct.pack('<HBBI', motor['id'], 0xCC, 0, 0)
    data, _ = bus.exchange(0x7FF, request,
        lambda ident, data: ident == motor['master'] and data[0] & 15 == motor['id'] & 15,
        timeout, lambda: False)
    if data[0] >> 4 >= 8:
        raise RuntimeError(f"ID {motor['id']}: fault {data[0] >> 4:#x}")
    pmax, vmax, tmax = scales
    q = int.from_bytes(data[1:3], 'big') * 2*pmax/65535-pmax
    v = ((data[3]<<4) | (data[4]>>4)) * 2*vmax/4095-vmax
    torque = (((data[4]&15)<<8) | data[5]) * 2*tmax/4095-tmax
    return dict(position=q, velocity=v, torque=torque, mos_c=data[6], rotor_c=data[7],
                status=data[0] >> 4, raw=data.hex(' '))


def disable(bus, motor):
    return command(bus, motor, 0xFD, .5, lambda: False)


def cleanup(buses, motors):
    for motor in motors:
        bus = buses.get(motor['bus'])
        if bus:
            for _ in range(3):
                try:
                    bus.send(motor['id'], b'\xff'*7+b'\xfd')
                except OSError:
                    break
    for bus in buses.values():
        bus.close()


def pack_mit(position, scales, kp=10.0, kd=1.0):
    pmax, vmax, tmax = scales
    if not -pmax <= position <= pmax or not 0 <= kp <= 20 or not 0 <= kd <= 2:
        raise ValueError('MIT command outside test limits')
    def encode(value, low, high, bits):
        return int((value-low)/(high-low)*((1<<bits)-1))
    p = encode(position, -pmax, pmax, 16)
    v = encode(0, -vmax, vmax, 12)
    k = encode(kp, 0, 500, 12)
    d = encode(kd, 0, 5, 12)
    t = encode(0, -tmax, tmax, 12)
    return bytes([p>>8, p&255, v>>4, ((v&15)<<4)|(k>>8), k&255,
                  d>>4, ((d&15)<<4)|(t>>8), t&255])
