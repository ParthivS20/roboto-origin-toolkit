#!/usr/bin/env python3
"""Read-only manual waist calibration logger. No enable, motion, zero or save commands."""
import argparse
import csv
import json
import math
from pathlib import Path
import signal
import time
from common import MOTORS, SocketCAN, acquire_lock, verify_interfaces, preflight, sample


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--seconds',type=float,default=600)
    p.add_argument('--output',type=Path,default=Path('waist_manual.csv'))
    a=p.parse_args()
    if not math.isfinite(a.seconds) or not 1<=a.seconds<=3600:p.error('seconds must be 1..3600')
    running=True
    def stop(*_):
        nonlocal running
        running=False
    signal.signal(signal.SIGTERM,stop)
    signal.signal(signal.SIGINT,stop)
    lock=acquire_lock();bus=None
    summary=dict(samples=0,read_only=True,torque_is_reported_motor_feedback=True)
    try:
        verify_interfaces();motor=next(m for m in MOTORS if m['id']==13)
        bus=SocketCAN(motor['bus']);scales=preflight(bus,motor)
        summary['scales']=scales
        summary['torque_step_nm']=2*scales[2]/4095
        fields=['elapsed_s','position_rad','position_deg','velocity_rad_s','reported_torque_nm','mos_c','rotor_c','status','raw']
        start=time.monotonic();last_log=-1.;low=math.inf;high=-math.inf;peak_torque=0.;peak_velocity=0.
        with a.output.open('x',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();f.flush()
            print(f'READY: disabled waist ID 13 / 0x0D, {motor["bus"]}; {a.output}; {a.seconds:g} seconds',flush=True)
            while running and time.monotonic()-start<a.seconds:
                tick=time.monotonic();r=sample(bus,motor,scales,timeout=.2)
                # ID 13 does not overlap the four-bit status field.
                if r['status']!=0:raise RuntimeError('Waist is enabled or faulted; stopping passive capture')
                elapsed=time.monotonic()-start
                writer.writerow(dict(elapsed_s=elapsed,position_rad=r['position'],position_deg=math.degrees(r['position']),
                    velocity_rad_s=r['velocity'],reported_torque_nm=r['torque'],mos_c=r['mos_c'],rotor_c=r['rotor_c'],status=r['status'],raw=r['raw']))
                f.flush();low=min(low,r['position']);high=max(high,r['position']);summary['samples']+=1
                peak_torque=max(peak_torque,abs(r['torque']));peak_velocity=max(peak_velocity,abs(r['velocity']))
                summary.update(min_rad=low,max_rad=high,span_rad=high-low,
                    midpoint_rad=(high+low)/2,peak_reported_torque_nm=peak_torque,peak_velocity_rad_s=peak_velocity)
                if elapsed-last_log>=1:
                    print(f'{elapsed:.1f}s q={r["position"]:+.5f} rad torque={r["torque"]:+.3f} Nm range=[{low:+.5f},{high:+.5f}]',flush=True);last_log=elapsed
                time.sleep(max(0,.05-(time.monotonic()-tick)))
    except BaseException as exc:
        summary['error']=str(exc);raise
    finally:
        if bus:bus.close()
        lock.close();a.output.with_suffix('.summary.json').write_text(json.dumps(summary,indent=2))
        print('Capture finished. No motor settings changed. '+json.dumps(summary),flush=True)


if __name__=='__main__':main()
