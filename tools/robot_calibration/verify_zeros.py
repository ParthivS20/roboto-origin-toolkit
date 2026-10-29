#!/usr/bin/env python3
"""Read all 23 motor identities and positions; no enable, zero or save commands."""
import argparse
import json
from pathlib import Path
from common import MOTORS, SocketCAN, acquire_lock, verify_interfaces, preflight, sample


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record', type=Path, default=Path('zero_verification.json'))
    args = parser.parse_args()
    lock = acquire_lock()
    buses, readings = {}, {}
    try:
        verify_interfaces()
        for motor in MOTORS:
            bus = buses.setdefault(motor['bus'], None)
            if bus is None:
                bus = buses[motor['bus']] = SocketCAN(motor['bus'])
            reading = sample(bus, motor, preflight(bus, motor))
            readings[str(motor['id'])] = reading
            args.record.write_text(json.dumps(readings, indent=2))
            print(f"ID {motor['id']:02d} {motor['name']}: {reading['position']:+.6f} rad", flush=True)
            if abs(reading['position']) > .01 or abs(reading['velocity']) > .05:
                raise RuntimeError(f"ID {motor['id']}: not stationary near zero")
        print('All 23 fresh positions verified near zero. No motor settings written.')
    finally:
        for bus in buses.values():
            if bus is not None:
                bus.close()
        lock.close()


if __name__ == '__main__':
    main()
