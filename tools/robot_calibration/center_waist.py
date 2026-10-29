#!/usr/bin/env python3
"""Torque-limited experimental waist end-stop search; requires known span and safe torque."""
import argparse
import json
import math
from pathlib import Path
import time
from common import MOTORS, SocketCAN, acquire_lock, verify_interfaces, preflight, sample

MOTOR = next(m for m in MOTORS if m['id'] == 13)
SPEED_CUTOFF = 1.5


def bounded_torque(target_velocity, actual_velocity, speed, limit):
    return max(-limit, min(limit, limit/speed*(target_velocity-actual_velocity)))


def checked_read(bus, scales, origin, max_travel, torque_cutoff=9.0, speed_cutoff=SPEED_CUTOFF):
    reading = sample(bus, MOTOR, scales, timeout=.15)
    if not all(math.isfinite(reading[k]) for k in ('position','velocity','torque')):
        raise RuntimeError('Invalid feedback')
    if abs(reading['torque']) > torque_cutoff:
        raise RuntimeError(f'Reported torque reached {torque_cutoff:g} Nm hard fault: {reading}')
    if abs(reading['velocity']) >= speed_cutoff:
        raise RuntimeError(f'{speed_cutoff:g} rad/s velocity failsafe triggered: {reading}')
    if abs(reading['position']-origin) > max_travel:
        raise RuntimeError('Maximum search travel exceeded')
    if max(reading['mos_c'],reading['rotor_c']) >= 60:
        raise RuntimeError('Motor temperature reached 60 C')
    return reading


def servo_command(driver, target, velocity, reading, torque_limit, feedforward=0.0):
    # Supplied waist gains: kp=150, kd=5. Scale both to bound estimated PD effort.
    kp,kd=150.0,5.0
    effort=kp*(target-reading['position'])+kd*(velocity-reading['velocity'])+feedforward
    scale=min(1.0,torque_limit/max(abs(effort),1e-9))
    driver.motor_mit_cmd(target,velocity,kp*scale,kd*scale,feedforward*scale)
    return effort*scale


def accept_contact(reading, direction, expected, moved, threshold):
    if abs(reading['torque']) < threshold:
        return False
    if not moved or direction*reading['torque'] < threshold or abs(reading['position']-expected)>.02:
        raise RuntimeError('6 Nm soft stop away from expected contact or with wrong torque direction')
    return True


def release_contact(driver,bus,scales,reading,args):
    driver.motor_mit_cmd(0,0,0,0,0)
    for _ in range(10):
        settled=checked_read(bus,scales,reading['position'],.03,args.hard_torque,args.speed_stop)
        if abs(settled['torque'])<args.max_torque and abs(settled['velocity'])<.02:
            return reading['position']
        time.sleep(.05)
    raise RuntimeError('Waist did not settle after contact release')


def seek(driver, bus, scales, direction, args):
    initial = sample(bus,MOTOR,scales)
    initial = checked_read(bus,scales,initial['position'],.03,args.hard_torque,args.speed_stop)
    start = previous = time.monotonic()
    moved = False
    stall_since = None
    torque_limit=args.max_torque
    target=initial['position']
    expected = args.low_stop if direction<0 else args.high_stop
    last_log = -1.
    if abs(initial['position']-expected)<.02 and abs(initial['velocity'])<.02:
        driver.motor_mit_cmd(0,0,0,0,0)
        print('Starting at known end stop; no push needed',flush=True)
        return initial['position']
    while time.monotonic()-start < args.timeout:
        r = checked_read(bus,scales,initial['position'],args.expected_span+.05,args.hard_torque,args.speed_stop)
        if not args.low_stop-.02 <= r['position'] <= args.high_stop+.02:
            raise RuntimeError('Outside manually measured stop envelope')
        now=time.monotonic();dt=min(.1,now-previous);previous=now
        moved |= direction*(r['position']-initial['position']) >= .03
        if abs(r['torque']) >= args.max_torque:
            # Release immediately at the soft threshold, before deciding whether to continue.
            driver.motor_mit_cmd(0,0,0,0,0)
            if accept_contact(r,direction,expected,moved,args.max_torque):
                print(f"Soft contact: {r['position']:+.5f} rad, torque={r['torque']:+.3f} Nm; reverse next",flush=True)
                return release_contact(driver,bus,scales,r,args)
        # A stationary, loaded, known endpoint may sit below a commanded 6 Nm
        # due to quantization/control error. Release early rather than hold pressure.
        stalled = (moved and abs(r['position']-expected)<.02
                   and abs(r['velocity'])<.02 and direction*r['torque']>=.9*args.max_torque)
        if stalled:
            if stall_since is None:stall_since=now
            if now-stall_since>=.15:
                print(f"Confirmed stationary endpoint below torque ceiling: {r['position']:+.5f} rad, {r['torque']:+.3f} Nm",flush=True)
                return release_contact(driver,bus,scales,r,args)
        else:stall_since=None
        # Half-second ramp, slowing within 0.05 rad of the manual endpoint.
        speed=args.speed*min(1.0,(now-start)/.5,max(.1,abs(expected-r['position'])/.05))
        velocity=direction*speed
        target+=velocity*dt
        target=max(r['position']-.04,min(r['position']+.04,target))
        torque=servo_command(driver,target,velocity,r,torque_limit)
        if now-start-last_log>=1:
            print(f"q={r['position']:+.4f} v={r['velocity']:+.3f} torque={r['torque']:+.2f} request={torque:+.2f}",flush=True)
            last_log=now-start
        time.sleep(.02)
    raise RuntimeError('Search timed out; do not raise torque blindly')


def midpoint(stops, expected_span, tolerance=.02):
    if len(stops) != 5:
        raise RuntimeError('Need initial contact plus four complete traversals')
    low, high = stops[::2], stops[1::2]
    if max(low)-min(low) > .02 or max(high)-min(high) > .02:
        raise RuntimeError('Repeated stops disagree by more than 0.02 rad')
    left,right = sum(low)/len(low),sum(high)/len(high)
    if abs((right-left)-expected_span) > tolerance:
        raise RuntimeError(f'Stop span {right-left:.4f} does not match expected {expected_span:.4f} rad')
    return (left+right)/2


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--max-torque',type=float,required=True,help='Mechanically validated safe contact torque, Nm')
    p.add_argument('--hard-torque',type=float,default=9.0,help='Abort whole program above this reported torque, at most 9 Nm')
    p.add_argument('--expected-span',type=float,required=True,help='Known full mechanical stop span, rad')
    p.add_argument('--low-stop',type=float,default=-.538452735)
    p.add_argument('--high-stop',type=float,default=.508697642)
    p.add_argument('--speed',type=float,default=.4,help='Search speed rad/s; maximum 0.4')
    p.add_argument('--speed-stop',type=float,default=1.5,help='Measured velocity cutoff, at most 1.5 rad/s')
    p.add_argument('--timeout',type=float,default=180,help='Maximum seconds per search/centering leg')
    p.add_argument('--resume-record',type=Path,help='Use five verified contacts from an interrupted unzeroed run; skip new sweeps')
    p.add_argument('--record',type=Path,default=Path('waist_center_record.json'))
    a=p.parse_args()
    if (not all(math.isfinite(v) for v in (a.max_torque,a.hard_torque,a.expected_span,a.speed,a.speed_stop,a.timeout))
            or not 0<a.max_torque<=6 or not a.max_torque<a.hard_torque<=9 or not .1<a.expected_span<=5
            or not 0<a.speed<=.4 or not a.speed<a.speed_stop<=1.5 or not 10<=a.timeout<=600):
        p.error('Require reported torque soft stop 0..6 Nm, hard torque above soft and <=9 Nm, span 0.1..5 rad, speed 0..0.4 rad/s, speed-stop above speed and <=1.5, timeout 10..600 s')
    if not (math.isfinite(a.low_stop) and math.isfinite(a.high_stop) and abs(a.high_stop-a.low_stop-a.expected_span)<.02):
        p.error('Manual stop envelope must match expected span')
    print('Experimental stall-based contact detection: obstruction can resemble an end stop.')
    print('Support robot, clear waist pin/fixture and cables, start away from both stops; E-stop ready.')
    if input('Type CENTER to confirm safe contact torque, span and clear waist: ').strip()!='CENTER':return
    import motors_py
    lock=acquire_lock();bus=None;driver=None
    record=dict(stops=[],zeroed=False,max_torque=a.max_torque,hard_torque=a.hard_torque,expected_span=a.expected_span,speed=a.speed,speed_stop=a.speed_stop)
    try:
        verify_interfaces();bus=SocketCAN(MOTOR['bus']);scales=preflight(bus,MOTOR)
        initial=sample(bus,MOTOR,scales)
        if abs(initial['velocity'])>.02:raise RuntimeError('Waist moving at startup')
        if a.max_torque>scales[2]:raise RuntimeError('Requested torque exceeds motor range')
        torque_step = 2*scales[2]/4095
        if a.max_torque < 10*torque_step:
            raise RuntimeError('Torque limit is too close to feedback quantization for reliable contact detection')
        if a.resume_record:
            saved=json.loads(a.resume_record.read_text())
            if saved.get('zeroed'):raise RuntimeError('Resume record already zeroed; old encoder coordinates are invalid')
            record['stops']=saved['stops']
            midpoint(record['stops'],a.expected_span)
            record['resumed_from']=str(a.resume_record)
        driver=motors_py.MotorDriver.create_motor(motor_id=13,interface_type='can',interface='can1',
            motor_type='DM',motor_model=1,master_id_offset=16,motor_zero_offset=0.0)
        driver.deinit_motor();driver.set_motor_control_mode(motors_py.MotorControlMode.MIT)
        driver.motor_mit_cmd(0,0,0,0,0);driver.init_motor()
        # Initial low stop, then four full stop-to-stop traversals.
        if not a.resume_record:
            for index,direction in enumerate((-1,1,-1,1,-1)):
                print(f'Search {index+1}/5; direction {direction:+d}',flush=True)
                record['stops'].append(seek(driver,bus,scales,direction,a))
                a.record.write_text(json.dumps(record,indent=2))
        center=midpoint(record['stops'],a.expected_span);record['center_before_zero']=center
        print(f'Consistent stops; moving to midpoint {center:+.5f} rad',flush=True)
        start=previous=time.monotonic();settled=None
        target=sample(bus,MOTOR,scales)['position']
        integral=0.0
        last_log=-1.0
        while time.monotonic()-start<a.timeout:
            r=checked_read(bus,scales,center,a.expected_span/2+.02,a.hard_torque,a.speed_stop)
            if abs(r['torque'])>=a.max_torque:
                driver.motor_mit_cmd(0,0,0,0,0)
                raise RuntimeError('Unexpected soft torque stop during centering')
            error=center-r['position']
            now=time.monotonic();dt=min(.1,now-previous);previous=now
            velocity=max(-a.speed,min(a.speed,(center-target)*2))
            velocity*=min(1.0,(now-start)/.5)
            target+=velocity*dt
            target=max(r['position']-.04,min(r['position']+.04,target))
            if abs(error)<.05:
                integral=max(-2.0,min(2.0,integral+10*error*dt))
            servo_command(driver,target,velocity,r,a.max_torque,integral)
            if now-start-last_log>=1:
                print(f'Centering q={r["position"]:+.5f} error={error:+.5f} v={r["velocity"]:+.3f} tau={r["torque"]:+.2f}',flush=True)
                last_log=now-start
            if abs(error)<.002 and abs(r['velocity'])<.02:
                if settled is None:settled=time.monotonic()
                if time.monotonic()-settled>=.5:break
            else:settled=None
            time.sleep(.02)
        else:raise RuntimeError('Could not settle at center')
        driver.motor_mit_cmd(0,0,0,0,0)
        # Use shipped SDK encoder-zero operation, like scripts/set_zero.py.
        if not driver.set_motor_zero():raise RuntimeError('SDK zero operation reported failure')
        driver.deinit_motor();r=sample(bus,MOTOR,scales)
        if abs(r['position'])>.01:raise RuntimeError('Fresh post-zero verification failed')
        record['zeroed']=True;record['after']=r
        print('Center zero verified; waist disabled. Verify after motor-supply power cycle.')
        print('A mechanical-center encoder zero needs waist runtime motor_zero_offset=0, not 2.093; config not changed.')
    except BaseException as exc:
        record['error']=str(exc);raise
    finally:
        try:
            if driver:
                for _ in range(3):
                    try:driver.deinit_motor()
                    except Exception as exc:print(f'Disable failed: {exc}')
        finally:
            if bus:bus.close()
            lock.close();a.record.write_text(json.dumps(record,indent=2))


if __name__=='__main__':
    try:main()
    except (RuntimeError,OSError,TimeoutError,KeyboardInterrupt) as exc:
        print(f'Stopped: {exc or "interrupted"}. Verify motor disabled.');raise SystemExit(1)
