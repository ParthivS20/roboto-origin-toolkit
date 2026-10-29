import math
import types
import unittest
from unittest.mock import Mock, patch
import arms_back_and_forth as arms


class AlternatingArmsTests(unittest.TestCase):
    def run_main(self, arguments=(), motion_error=None):
        left, right = Mock(), Mock()
        sdk = types.SimpleNamespace(MotorDriver=Mock(), MotorControlMode=types.SimpleNamespace(MIT=1))
        sdk.MotorDriver.create_motor.side_effect = [left, right]
        with patch.dict('sys.modules', {'motors_py': sdk}), \
                patch('sys.argv', ['arms_back_and_forth.py', *arguments]), \
                patch('builtins.input', return_value='MOVE'), patch('builtins.print'), \
                patch.object(arms, 'acquire_lock'), patch.object(arms, 'verify_interfaces'), \
                patch.object(arms, 'SocketCAN'), \
                patch.object(arms, 'preflight', return_value=(12.5,20,28)), \
                patch.object(arms, 'sample', return_value=dict(position=0,velocity=0,mos_c=30,rotor_c=27)), \
                patch.object(arms, 'move', side_effect=motion_error) as motion, \
                patch.object(arms.time, 'sleep'):
            if motion_error is None:
                arms.main()
            else:
                with self.assertRaisesRegex(RuntimeError, 'following error'):
                    arms.main()
        return left, right, sdk, motion

    def test_left_then_right_repeat_with_mirrored_direction(self):
        left, right, sdk, motion = self.run_main(('--cycles', '2'))
        calls = motion.call_args_list
        self.assertEqual([c.args[2]['id'] for c in calls], [14,19,14,19])
        self.assertEqual([c.args[5] for c in calls], [-1,1,-1,1])
        for call in calls:
            self.assertEqual(call.args[6:], (45,22.5,240,5))
        self.assertEqual([c.kwargs['interface'] for c in sdk.MotorDriver.create_motor.call_args_list], ['can2','can3'])

    def test_failure_on_right_attempts_cleanup_for_both(self):
        left, right, sdk, motion = self.run_main(motion_error=[None,RuntimeError('following error')])
        self.assertEqual([c.args[2]['id'] for c in motion.call_args_list], [14,19])
        self.assertEqual(left.deinit_motor.call_count,4)
        self.assertEqual(right.deinit_motor.call_count,4)

    def test_right_outward_target_is_positive_and_returns_to_rest(self):
        driver, bus = Mock(), Mock()
        readings = [dict(position=0,velocity=0,torque=0,mos_c=30,rotor_c=27,status=1,raw='rest'),
                    dict(position=math.radians(45),velocity=0,torque=0,mos_c=30,rotor_c=27,status=1,raw='out'),
                    dict(position=0,velocity=0,torque=0,mos_c=30,rotor_c=27,status=1,raw='back')]
        motor=next(m for m in arms.MOTORS if m['id']==19)
        with patch.object(arms,'sample',side_effect=readings), \
                patch.object(arms.time,'monotonic',side_effect=[0,22.5,22.5,45]), patch('builtins.print'):
            arms.move(driver,bus,motor,(12.5,20,28),0,1,45,22.5,240,5)
        self.assertAlmostEqual(driver.motor_mit_cmd.call_args_list[1].args[0],math.radians(45))
        self.assertEqual(driver.motor_mit_cmd.call_args_list[-1].args,(0.0,0.0,240,5,0.0))
        driver.deinit_motor.assert_called_once()

    def test_working_speed_stop_message_matches_two_radians_per_second(self):
        reading=dict(position=0,velocity=2.01,torque=0,mos_c=30,rotor_c=27)
        self.assertIn('exceeds 2.00 rad/s',arms.check_motion(reading,0,0,45,10))


if __name__=='__main__':
    unittest.main()
