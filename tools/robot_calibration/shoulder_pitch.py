"""Roboto motors_py SDK shoulder pitch: left up/down, then right up/down; no zero writes."""
import argparse
import math
import time
from common import (MOTORS, SocketCAN, acquire_lock, verify_interfaces, preflight, sample,
                    )

# Supplied src/inference/robots/rpo/robot.yaml, motor indices 13 and 18.
SHOULDER_SIGNS = {14: 1, 19: -1}
SHOULDER_KP = 40.0
SHOULDER_KD = 2.0
TEST_KP_MAX = 500
TEST_KD_MAX = 5.0
TEST_TORQUE_STOP = 10.0


def trajectory_velocity(elapsed, duration, degrees):
    progress = min(1.0, max(0.0, elapsed/duration))
    if progress in (0.0, 1.0):
        return 0.0
    return math.radians(degrees)*math.pi*math.sin(math.pi*progress)/(2*duration)


def offset(elapsed, duration, degrees):
    # Cosine easing has zero velocity at the start/end of each leg.
    progress = min(1.0, max(0.0, elapsed/duration))
    return math.radians(degrees) * (1-math.cos(math.pi*progress))/2


def check_motion(reading, rest, target, degrees, torque_limit=None, velocity_limit=.15):
    travel = abs(math.degrees(reading['position']-rest))
    error = abs(math.degrees(reading['position']-target))
    if torque_limit is not None and abs(reading['torque']) > torque_limit:
        return f"reported torque {reading['torque']:+.2f} Nm exceeds {torque_limit:.2f} Nm stop threshold"
    if travel > degrees+3:
        return f'travel {travel:.2f}° exceeds {degrees+3:.2f}°'
    if abs(reading['velocity']) > velocity_limit:
        return f"velocity {reading['velocity']:.3f} rad/s exceeds {velocity_limit:.2f} rad/s"
    error_limit = min(8.0, max(.5, degrees/2))
    if error > error_limit:
        return (f'following error {error:.2f}° exceeds {error_limit:.2f}°; '
                f"relative target={math.degrees(target-rest):+.2f}°, "
                f"relative actual={math.degrees(reading['position']-rest):+.2f}°, "
                f"reported torque={reading['torque']:+.2f} Nm; "
                f"status={reading.get('status', 'unknown')}, raw={reading.get('raw', 'unavailable')}. "
                'Verify motor enable/LED and other controllers; friction or load may exceed commanded torque. '
                'Do not increase gains against a restrained joint.')
    if max(reading['mos_c'], reading['rotor_c']) >= 60:
        return 'motor temperature reached 60°C'
    return None


def move(driver, bus, motor, scales, rest, direction, degrees, duration, kp, kd, velocity_limit=.15):
    driver.motor_mit_cmd(rest, 0.0, kp, kd, 0.0)
    driver.init_motor()
    reading = sample(bus, motor, scales, timeout=.15)
    torque_limit = TEST_TORQUE_STOP if kp > SHOULDER_KP or kd > SHOULDER_KD else None
    reason = check_motion(reading, rest, rest, degrees, torque_limit, velocity_limit)
    if reason:
        raise RuntimeError(f"ID {motor['id']}: {reason}")
    print(f"ID {motor['id']}: after SDK enable: status={reading['status']}, raw={reading['raw']}; "
          'nominal status 0=disabled, 1=enabled; IDs above 15 can overlap the status nibble. '
          'Verify the motor LED.', flush=True)
    for upwards in (True, False):
        start = time.monotonic()
        last_log = -1.0
        while True:
            elapsed = time.monotonic()-start
            amount = offset(elapsed, duration, degrees)
            velocity = trajectory_velocity(elapsed, duration, degrees)
            if not upwards:
                amount = math.radians(degrees)-amount
                velocity = -velocity
            target = rest+direction*amount
            driver.motor_mit_cmd(target, direction*velocity, kp, kd, 0.0)
            reading = sample(bus, motor, scales, timeout=.15)
            estimated_torque = kp*(target-reading['position']) + kd*(direction*velocity-reading['velocity'])
            if elapsed-last_log >= .5 or elapsed >= duration:
                print(f"ID {motor['id']}: target={math.degrees(target-rest):+.2f}° "
                      f"actual={math.degrees(reading['position']-rest):+.2f}° "
                      f"velocity={reading['velocity']:+.3f} rad/s torque={reading['torque']:+.2f} Nm "
                      f"estimated MIT torque={estimated_torque:+.2f} Nm status={reading['status']}",
                      flush=True)
                last_log = elapsed
            reason = check_motion(reading, rest, target, degrees, torque_limit, velocity_limit)
            if reason:
                raise RuntimeError(f"ID {motor['id']}: {reason}")
            if elapsed >= duration:
                endpoint_limit = min(3.0, max(.3, degrees/4))
                endpoint_error = abs(math.degrees(reading['position']-target))
                if endpoint_error > endpoint_limit:
                    raise RuntimeError(f"ID {motor['id']}: endpoint error {endpoint_error:.2f}° "
                                       f"exceeds {endpoint_limit:.2f}°; "
                                       f"relative target={math.degrees(target-rest):+.2f}°, "
                                       f"relative actual={math.degrees(reading['position']-rest):+.2f}°, "
                                       f"reported torque={reading['torque']:+.2f} Nm")
                break
            time.sleep(.02)
    if abs(reading['position']-rest) > math.radians(3):
        raise RuntimeError('Shoulder did not return near its measured resting position')
    driver.deinit_motor()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--degrees', type=float, default=15)
    parser.add_argument('--seconds', type=float,
                        help='Total up/down duration per side; default degrees (0.5 seconds per degree each way)')
    parser.add_argument('--cycles', type=int, default=1)
    parser.add_argument('--side', choices=('both', 'left', 'right'), default='both')
    parser.add_argument('--velocity-stop', type=float, default=.15,
                        help='Measured speed stop in rad/s; default 0.15, max 0.70 for left-only one-cycle checks')
    parser.add_argument('--kp', type=float, default=SHOULDER_KP,
                        help=f'Default 40; ceiling {TEST_KP_MAX}; above 40 requires left side, <=45 degrees, one cycle')
    parser.add_argument('--kd', type=float, default=SHOULDER_KD,
                        help='Default 2; experimental values up to 5 require left side, <=45 degrees, one cycle')
    args = parser.parse_args()
    if args.seconds is None:
        args.seconds = args.degrees
    if not (0 < args.degrees <= 45 and args.seconds >= args.degrees and 1 <= args.cycles <= 100
            and 0 < args.kp <= TEST_KP_MAX and 0 < args.kd <= TEST_KD_MAX
            and 0 < args.velocity_stop <= .70
            and all(math.isfinite(v) for v in (args.degrees,args.seconds,args.kp,args.kd,args.velocity_stop))):
        parser.error(f'Use degrees 0..45, seconds >=degrees, cycles 1..100, kp <={TEST_KP_MAX}, kd <={TEST_KD_MAX}, velocity-stop <=0.70')
    experimental = args.kp > SHOULDER_KP or args.kd > SHOULDER_KD or args.velocity_stop > .15
    if (experimental or args.degrees > 30) and (args.side != 'left' or args.cycles != 1):
        parser.error('Higher gains or angles above 30 degrees require --side left and --cycles 1')
    if math.radians(args.degrees)*math.pi/args.seconds > .12:
        parser.error('Requested trajectory exceeds 0.12 rad/s; increase --seconds')
    try:
        import motors_py
    except ImportError as exc:
        raise RuntimeError('Source /opt/ros/humble/setup.bash and ~/roboparty_deploy/install/setup.bash first') from exc
    motor_ids = {'both': (14, 19), 'left': (14,), 'right': (19,)}[args.side]
    motors = [next(m for m in MOTORS if m['id'] == mid) for mid in motor_ids]
    if experimental:
        print(f'Experimental left shoulder check: kp={args.kp}, kd={args.kd}; factory values 40/2; '
              f'stop above {TEST_TORQUE_STOP} Nm reported torque. '
              f'Measured speed stop {args.velocity_stop:.2f} rad/s. '
              'This software stop is not a hardware torque limit.', flush=True)
    print('Support robot/arms; remove ALL pins and fixtures. E-stop ready. Stop other controllers.')
    if input('Type MOVE to confirm pins removed and begin: ').strip() != 'MOVE':
        print('Cancelled; no CAN commands sent.')
        return
    lock = acquire_lock()
    buses, drivers = {}, {}
    try:
        verify_interfaces()
        scales, resting = {}, {}
        for motor in motors:
            buses[motor['bus']] = SocketCAN(motor['bus'])
            bus = buses[motor['bus']]
            scales[motor['id']] = preflight(bus, motor)
            print(f"ID {motor['id']}: PMAX/VMAX/TMAX={scales[motor['id']]}, kp={args.kp}, kd={args.kd}", flush=True)
            reading = sample(bus, motor, scales[motor['id']])
            if abs(reading['velocity']) > .05 or max(reading['mos_c'],reading['rotor_c']) >= 60:
                raise RuntimeError('Shoulder moving or too warm at startup')
            rest = reading['position']
            # Arms must be at the verified hanging rest pose, near the saved zero.
            if abs(rest) > math.radians(5):
                raise RuntimeError('Shoulder is not near its verified zero/rest pose')
            resting[motor['id']] = rest
        # Only construct SDK drivers once both independent read-only preflights pass.
        for motor in motors:
            driver = motors_py.MotorDriver.create_motor(
                motor_id=motor['id'], interface_type='can', interface=motor['bus'],
                motor_type='DM', motor_model=0, master_id_offset=16, motor_zero_offset=0.0)
            drivers[motor['id']] = driver
            driver.deinit_motor()
            driver.set_motor_control_mode(motors_py.MotorControlMode.MIT)
        for cycle in range(args.cycles):
            for motor in motors:
                # URDF forward lift uses negative logical pitch; robot.yaml right sign=-1.
                direction = -SHOULDER_SIGNS[motor['id']]
                print(f"Cycle {cycle+1}: {motor['name']} {args.degrees}° up and back", flush=True)
                move(drivers[motor['id']], buses[motor['bus']], motor, scales[motor['id']], resting[motor['id']],
                     direction, args.degrees, args.seconds/2, args.kp, args.kd, velocity_limit=args.velocity_stop)
                time.sleep(1)
        print('Complete; selected shoulders disabled.')
    finally:
        # All enable, motion and disable commands use the shipped SDK.
        try:
            for mid, driver in drivers.items():
                for _ in range(3):
                    try:
                        driver.deinit_motor()
                    except Exception as exc:
                        print(f'ID {mid}: SDK disable failed: {exc}', flush=True)
        finally:
            for bus in buses.values():
                bus.close()
            lock.close()


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, TimeoutError, OSError, KeyboardInterrupt) as exc:
        print(f'Stopped: {exc or "interrupted"}. Cleanup attempted disable commands; verify motor LEDs.')
        raise SystemExit(1)
