import math
import itertools
import types
import unittest
from unittest.mock import patch
from unittest.mock import Mock
from common import MOTORS, pack_mit, preflight, sample
from shoulder_pitch import offset, check_motion, move, trajectory_velocity
import shoulder_pitch
from center_waist import midpoint, bounded_torque, servo_command, checked_read, accept_contact, seek


class Tests(unittest.TestCase):
    def test_waist_hard_torque_fault_above_nine(self):
        r=dict(position=0,velocity=0,torque=9.1,mos_c=25,rotor_c=25)
        with patch('center_waist.sample',return_value=r):
            with self.assertRaisesRegex(RuntimeError,'9 Nm hard fault'):
                checked_read(None,(12.5,25,200),0,1,9)
        r['torque']=9
        with patch('center_waist.sample',return_value=r):
            self.assertEqual(checked_read(None,(12.5,25,200),0,1,9),r)

    def test_waist_six_nm_contact_and_obstruction(self):
        r=dict(position=-.54,torque=-6.007)
        self.assertTrue(accept_contact(r,-1,-.538,True,6))
        r['position']=0
        with self.assertRaisesRegex(RuntimeError,'away from expected'):
            accept_contact(r,-1,-.538,True,6)

    def test_waist_soft_stop_releases_and_returns_for_next_leg(self):
        driver=Mock()
        initial=dict(position=0,velocity=0,torque=0,mos_c=25,rotor_c=25)
        contact=dict(initial,position=-.54,torque=-6.007)
        released=dict(contact,torque=0)
        args=types.SimpleNamespace(max_torque=6,hard_torque=9,expected_span=1.047,
            low_stop=-.538,high_stop=.509,speed=.4,speed_stop=1.5,timeout=10)
        with patch('center_waist.sample',return_value=initial), \
                patch('center_waist.checked_read',side_effect=[initial,contact,released]):
            self.assertEqual(seek(driver,None,(12.5,25,200),-1,args),-.54)
        self.assertTrue(all(c.args==(0,0,0,0,0) for c in driver.motor_mit_cmd.call_args_list))

    def test_waist_releases_known_stall_below_six(self):
        driver=Mock()
        initial=dict(position=0,velocity=0,torque=0,mos_c=25,rotor_c=25)
        stalled=dict(initial,position=-.54,torque=-5.8)
        released=dict(stalled,torque=0)
        args=types.SimpleNamespace(max_torque=6,hard_torque=9,expected_span=1.047,
            low_stop=-.538,high_stop=.509,speed=.4,speed_stop=1.5,timeout=10)
        with patch('center_waist.sample',return_value=initial), \
                patch('center_waist.checked_read',side_effect=[initial,stalled,stalled,released]), \
                patch('center_waist.time.monotonic',side_effect=itertools.count(0,.1)), \
                patch('center_waist.time.sleep'):
            self.assertEqual(seek(driver,None,(12.5,25,200),-1,args),-.54)
        self.assertEqual(driver.motor_mit_cmd.call_args.args,(0,0,0,0,0))

    def test_waist_servo_scales_pd_effort_to_limit(self):
        driver=Mock()
        reading=dict(position=0,velocity=0)
        effort=servo_command(driver,.04,.4,reading,5.8)
        self.assertAlmostEqual(effort,5.8)
        q,v,kp,kd,tau=driver.motor_mit_cmd.call_args.args
        self.assertAlmostEqual(kp*q+kd*v+tau,5.8)
        self.assertLessEqual(kp,150)
        self.assertLessEqual(kd,5)

    def test_waist_centering_feedforward_stays_inside_effort_limit(self):
        driver=Mock()
        r=dict(position=0,velocity=0)
        effort=servo_command(driver,.04,.4,r,6,2)
        q,v,kp,kd,tau=driver.motor_mit_cmd.call_args.args
        self.assertAlmostEqual(effort,6)
        self.assertAlmostEqual(kp*q+kd*v+tau,6)

    def test_waist_new_speed_cutoff(self):
        r=dict(position=0,velocity=1.5,torque=0,mos_c=25,rotor_c=25)
        with patch('center_waist.sample',return_value=r):
            with self.assertRaisesRegex(RuntimeError,'1.5 rad/s'):
                checked_read(None,(12.5,25,200),0,1,6,1.5)

    def test_waist_midpoint_requires_repeatable_known_span(self):
        self.assertAlmostEqual(midpoint([-1,1,-1.005,1.005,-1],2),0.0004166666666667)
        for stops,span in (([-1,1,-.8,1,-1],2),([-1,.2,-1,.2,-1],2),([-1,1],2)):
            with self.assertRaises(RuntimeError):midpoint(stops,span)

    def test_waist_torque_is_bounded_even_during_overspeed(self):
        for target in (-.03,0,.03):
            for actual in (-.6,0,.6):
                self.assertLessEqual(abs(bounded_torque(target,actual,.03,1)),1)

    def test_explicit_speed_stop_remains_bounded(self):
        for velocity in (-.151,.151,-.69,.69):
            reading=dict(position=0,velocity=velocity,torque=0,mos_c=30,rotor_c=27)
            self.assertIn('velocity',check_motion(reading,0,0,45))
            self.assertIsNone(check_motion(reading,0,0,45,10,.70))
        for velocity in (-.701,.701):
            reading=dict(position=0,velocity=velocity,torque=0,mos_c=30,rotor_c=27)
            self.assertIn('exceeds 0.70',check_motion(reading,0,0,45,10,.70))

    def test_partial_motion_fails_endpoint_without_return_trajectory(self):
        driver, bus = Mock(), Mock()
        readings = [dict(position=0,velocity=0,torque=0,mos_c=30,rotor_c=27,status=1,raw='enabled'),
                    dict(position=-math.radians(1.64),velocity=-.005,torque=-1.42,
                         mos_c=30,rotor_c=27,status=1,raw='partial')]
        with patch('shoulder_pitch.sample',side_effect=readings), \
                patch('shoulder_pitch.time.monotonic',side_effect=[0,5]), patch('builtins.print'):
            with self.assertRaisesRegex(RuntimeError,'endpoint error 1.36° exceeds 0.75°') as error:
                move(driver,bus,MOTORS[13],(12.5,20,28),0,-1,3,5,60,2)
        self.assertIn('relative actual=-1.64°',str(error.exception))
        self.assertIn('reported torque=-1.42 Nm',str(error.exception))
        self.assertEqual(driver.motor_mit_cmd.call_count,2)
        self.assertAlmostEqual(driver.motor_mit_cmd.call_args.args[0],-math.radians(3))

    def test_experimental_torque_stop_both_directions(self):
        self.assertEqual(shoulder_pitch.TEST_TORQUE_STOP,10.0)
        for torque in (-10.01, 10.01):
            reading = dict(position=0,velocity=0,torque=torque,mos_c=25,rotor_c=25)
            self.assertIn('stop threshold',check_motion(reading,0,0,3,shoulder_pitch.TEST_TORQUE_STOP))
            self.assertIsNone(check_motion(reading,0,0,3))
        for torque in (-10.0,-2.01,2.01,10.0):
            reading = dict(position=0,velocity=0,torque=torque,mos_c=25,rotor_c=25)
            self.assertIsNone(check_motion(reading,0,0,3,shoulder_pitch.TEST_TORQUE_STOP))

    def test_experimental_kp_rejects_large_or_bilateral_checks_before_hardware(self):
        cases = [('--kp',str(shoulder_pitch.TEST_KP_MAX+1),'--side','left','--degrees','3','--seconds','20'),
                 ('--side','left','--degrees','45','--velocity-stop','.701'),
                 ('--side','both','--degrees','3','--velocity-stop','.70'),
                 ('--kp','120','--side','left','--degrees','3','--seconds','2'),
                 ('--kp','60','--kd','3','--side','left','--degrees','3','--seconds','0'),
                 ('--kd',str(shoulder_pitch.TEST_KD_MAX+.01),'--side','left','--degrees','3','--seconds','20'),
                 ('--kp','120','--kd','3','--side','left','--degrees','3','--seconds','nan'),
                 ('--kp','60','--degrees','3'),
                 ('--kp','60','--side','right','--degrees','3'),
                 ('--kp','60','--side','left','--degrees','46'),
                 ('--side','both','--degrees','45'),
                 ('--kp','60','--side','left','--degrees','3','--cycles','2')]
        for args in cases:
            with self.subTest(args=args), patch('sys.argv',['shoulder_pitch.py',*args]), \
                    patch('sys.stderr'), patch.object(shoulder_pitch,'acquire_lock') as lock:
                with self.assertRaises(SystemExit) as error:
                    shoulder_pitch.main()
                self.assertEqual(error.exception.code,2)
                lock.assert_not_called()

    def test_experimental_kp_only_constructs_left_driver_and_cleanup_runs(self):
        left = Mock()
        sdk = types.SimpleNamespace(MotorDriver=Mock(), MotorControlMode=types.SimpleNamespace(MIT=1))
        sdk.MotorDriver.create_motor.return_value = left
        with patch.dict('sys.modules', {'motors_py':sdk}), \
                patch('sys.argv',['shoulder_pitch.py','--side','left','--degrees','45','--kp','240','--kd','5','--velocity-stop','.70']), \
                patch('builtins.input',return_value='MOVE'), patch('builtins.print'), \
                patch.object(shoulder_pitch,'acquire_lock'), patch.object(shoulder_pitch,'verify_interfaces'), \
                patch.object(shoulder_pitch,'SocketCAN'), \
                patch.object(shoulder_pitch,'preflight',return_value=(12.5,20,28)), \
                patch.object(shoulder_pitch,'sample',return_value=dict(position=0,velocity=0,mos_c=25,rotor_c=25)), \
                patch.object(shoulder_pitch,'move',side_effect=RuntimeError('torque stop')) as motion:
            with self.assertRaisesRegex(RuntimeError,'torque stop'):
                shoulder_pitch.main()
        sdk.MotorDriver.create_motor.assert_called_once()
        self.assertEqual(sdk.MotorDriver.create_motor.call_args.kwargs['motor_id'],14)
        self.assertEqual(motion.call_args.args[-2:],(240,5))
        self.assertEqual(motion.call_args.kwargs['velocity_limit'],.70)
        self.assertEqual(motion.call_args.args[-3],22.5)
        self.assertEqual(motion.call_args.args[-4],45)
        self.assertEqual(left.deinit_motor.call_count,4)

    def test_feedback_retains_disabled_status_and_raw_bytes(self):
        bus = Mock()
        payload = bytes.fromhex('0e 7f ff 7f f7 ff 19 19')
        bus.exchange.return_value = (payload, 1)
        reading = sample(bus, MOTORS[13], (12.5,20,28))
        self.assertEqual(reading['status'], 0)
        self.assertEqual(reading['raw'], payload.hex(' '))
        self.assertAlmostEqual(reading['position'], -12.5/65535)

    def test_feedback_fault_still_rejected(self):
        bus = Mock()
        bus.exchange.return_value = (bytes.fromhex('9e 7f ff 7f f7 ff 19 19'), 1)
        with self.assertRaisesRegex(RuntimeError, 'fault 0x9'):
            sample(bus, MOTORS[13], (12.5,20,28))

    def test_following_error_uses_relative_angles_and_retains_evidence(self):
        rest = math.radians(2.04)
        reading = dict(position=rest,velocity=0,torque=-.38,mos_c=25,rotor_c=25,
                       status=1,raw='1e 80 5d 7f f7 e4 19 19')
        reason = check_motion(reading,rest,rest-math.radians(.51),1)
        self.assertIn('relative target=-0.51°',reason)
        self.assertIn('relative actual=+0.00°',reason)
        self.assertIn('status=1, raw=',reason)

    def test_one_degree_test_rejects_no_movement(self):
        reading = dict(position=0,velocity=0,torque=0,mos_c=25,rotor_c=25)
        self.assertIn('following error',check_motion(reading,0,math.radians(1),1))

    def test_slow_velocity_feedforward(self):
        self.assertEqual(trajectory_velocity(0,5,15),0)
        self.assertEqual(trajectory_velocity(5,5,15),0)
        self.assertAlmostEqual(trajectory_velocity(2.5,5,15),math.radians(15)*math.pi/10)
        self.assertLess(trajectory_velocity(2.5,5,15),.12)

    def test_half_second_per_degree_trajectory_peak_speed(self):
        for degrees in (1,3,15,30,45):
            leg_duration = degrees/2
            self.assertAlmostEqual(trajectory_velocity(leg_duration/2,leg_duration,degrees),math.pi**2/180)
            self.assertLess(trajectory_velocity(leg_duration/2,leg_duration,degrees),.12)

    def test_motion_failure_disables_both_sdk_drivers(self):
        left, right = Mock(), Mock()
        sdk = types.SimpleNamespace(MotorDriver=Mock(), MotorControlMode=types.SimpleNamespace(MIT=1))
        sdk.MotorDriver.create_motor.side_effect = [left,right]
        with patch.dict('sys.modules', {'motors_py':sdk}), \
                patch('sys.argv', ['shoulder_pitch.py']), patch('builtins.input',return_value='MOVE'), \
                patch.object(shoulder_pitch,'acquire_lock'), patch.object(shoulder_pitch,'verify_interfaces'), \
                patch.object(shoulder_pitch,'SocketCAN'), \
                patch.object(shoulder_pitch,'preflight',return_value=(12.5,20,28)), \
                patch.object(shoulder_pitch,'sample',return_value=dict(position=0,velocity=0,mos_c=25,rotor_c=25)), \
                patch.object(shoulder_pitch,'move',side_effect=RuntimeError('following error')), \
                patch('builtins.print'):
            with self.assertRaisesRegex(RuntimeError,'following error'):
                shoulder_pitch.main()
        self.assertEqual(left.deinit_motor.call_count,4)
        self.assertEqual(right.deinit_motor.call_count,4)
        self.assertEqual(sdk.MotorDriver.create_motor.call_args_list[0].kwargs['motor_id'],14)
        self.assertEqual(sdk.MotorDriver.create_motor.call_args_list[1].kwargs['motor_id'],19)

    def test_sdk_controls_enable_motion_and_disable(self):
        driver, bus = Mock(), Mock()
        readings = [dict(position=0, velocity=0, torque=0, mos_c=25, rotor_c=25,status=1,raw='enabled'),
                    dict(position=-math.radians(1), velocity=0, torque=0, mos_c=25, rotor_c=25,status=1,raw='raised'),
                    dict(position=0, velocity=0, torque=0, mos_c=25, rotor_c=25,status=1,raw='returned')]
        with patch('shoulder_pitch.sample', side_effect=readings), \
                patch('shoulder_pitch.time.monotonic', side_effect=[0,5,5,10]):
            move(driver, bus, MOTORS[13], (12.5,20,28), 0, -1, 1, 5, 10, 1)
        driver.init_motor.assert_called_once()
        driver.deinit_motor.assert_called_once()
        self.assertEqual(driver.motor_mit_cmd.call_count, 3)
        self.assertAlmostEqual(driver.motor_mit_cmd.call_args_list[1].args[0], -math.radians(1))
        self.assertEqual(driver.motor_mit_cmd.call_args_list[-1].args, (0.0,0.0,10,1,0.0))
        bus.send.assert_not_called()

    def test_stationary_shoulder_reports_following_error(self):
        reading = dict(position=-.002479591, velocity=-.004884,
                       torque=-1.429, mos_c=27, rotor_c=23)
        reason = check_motion(reading, 0, math.radians(-9), 15)
        self.assertIn('following error', reason)
        self.assertIn('actual=-0.14°', reason)
        self.assertIsNone(check_motion(reading, 0, math.radians(-1), 15))

    def test_wrong_motor_identity_rejected(self):
        with patch('common.read_register', return_value=(99, 1)):
            with self.assertRaises(RuntimeError):
                preflight(None, MOTORS[0])

    def test_eased_trajectory_bounds(self):
        values=[offset(t/100*5,5,15) for t in range(101)]
        self.assertEqual(values[0],0)
        self.assertAlmostEqual(values[-1],math.radians(15))
        self.assertTrue(all(a<=b for a,b in zip(values,values[1:])))
        self.assertLess(max((b-a)/.05 for a,b in zip(values,values[1:])),.15)
        self.assertAlmostEqual(offset(2.5,5,15),math.radians(7.5))

    def test_mit_encoding_and_limits(self):
        packet=pack_mit(0,(12.5,20,28))
        self.assertEqual(len(packet),8)
        self.assertEqual(int.from_bytes(packet[:2],'big'),32767)
        self.assertNotEqual(packet,b'\xff'*8)
        for q,kp in ((13,10),(0,100)):
            with self.assertRaises(ValueError):pack_mit(q,(12.5,20,28),kp)


if __name__=='__main__':unittest.main()
