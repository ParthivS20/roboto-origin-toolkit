import threading
import time
import unittest
from unittest.mock import patch

from canbus import Cancelled, command, read_register
from server import Runner
from topology import BRANCHES, MOTORS


class FakeCAN:
    def __init__(self, interface, missing=(), disable_timeout=False, wrong_mode=False):
        self.interface = interface
        self.missing, self.disable_timeout, self.wrong_mode = missing, disable_timeout, wrong_mode
        self.enabled = set()
        self.enables = []
        self.sends = []

    def send(self, ident, data):
        self.sends.append((ident, data))
        if data == b'\xff'*7+b'\xfd':
            self.enabled.discard(ident)

    def exchange(self, ident, data, matcher, timeout, cancelled):
        if cancelled():
            raise Cancelled()
        mid = int.from_bytes(data[:2], 'little') if ident == 0x7FF else ident
        if mid in self.missing:
            raise TimeoutError('Missing motor')
        if ident == 0x7FF:
            value = {7:mid+16, 8:mid, 10:2 if self.wrong_mode else 1}[data[3]]
            response = data[:4]+value.to_bytes(4,'little')
        else:
            if data[-1] == 0xFC:
                self.enables.append(mid)
                self.enabled.add(mid)
            else:
                if self.disable_timeout and self.enables:
                    raise TimeoutError('Disable reply lost')
                self.enabled.discard(mid)
            response = bytes([(mid & 15) | (16 if mid in self.enabled else 0)])+bytes.fromhex('7F FF 7F F8 00 1E 1C')
        if not matcher(mid+16, response):
            raise AssertionError('Correct reply rejected')
        return response, 3.0

    def close(self):
        pass


class Tests(unittest.TestCase):
    def runner(self, **kwargs):
        buses = {}
        def factory(name):
            buses[name] = FakeCAN(name, **kwargs)
            return buses[name]
        runner = Runner(demo=True, factory=factory)
        runner.alive()
        # Advance each slot without the wall-clock delay; don't alter CAN decisions.
        runner.wait_until = lambda deadline: None
        return runner, buses

    def test_topology(self):
        self.assertEqual(len(MOTORS), 23)
        self.assertEqual(BRANCHES['can1'][1], [13,7,8,9,10,11,12])
        self.assertEqual(len({m['id'] for m in MOTORS}),23)
        self.assertTrue(all(m['master']==m['id']+16 for m in MOTORS))

    def test_physical_order_and_one_enabled_at_a_time(self):
        runner,buses=self.runner()
        motors=[m for m in MOTORS if m['bus']=='can1']
        original=FakeCAN.exchange
        def exchange(bus,*args):
            result=original(bus,*args)
            self.assertLessEqual(sum(len(b.enabled) for b in buses.values()),1)
            if len(bus.enables)==7 and not bus.enabled:
                runner.stop_event.set()
            return result
        with patch.object(FakeCAN,'exchange',exchange):
            runner.run(motors)
        self.assertEqual(buses['can1'].enables,[13,7,8,9,10,11,12])
        self.assertFalse(buses['can1'].enabled)

    def test_missing_motor_skipped_without_enable(self):
        runner,buses=self.runner(missing=(1,))
        motors=[m for m in MOTORS if m['id'] in (1,2)]
        original=FakeCAN.exchange
        def exchange(bus,*args):
            result=original(bus,*args)
            if bus.enables and not bus.enabled:
                runner.stop_event.set()
            return result
        with patch.object(FakeCAN,'exchange',exchange):
            runner.run(motors)
        self.assertEqual(buses['can0'].enables,[2])
        self.assertEqual(runner.snapshot()['motors']['1']['color'],'error')

    def test_disable_timeout_halts_and_cleans_up(self):
        runner,buses=self.runner(disable_timeout=True)
        runner.run([m for m in MOTORS if m['id'] in (1,2)])
        self.assertEqual(buses['can0'].enables,[1])
        self.assertIn('Disable reply lost',runner.snapshot()['error'])
        self.assertFalse(buses['can0'].enabled)

    def test_wrong_mode_never_enables(self):
        runner,buses=self.runner(wrong_mode=True)
        runner.wait_until=lambda deadline: runner.stop_event.set()
        runner.run([MOTORS[0]])
        self.assertFalse(buses['can0'].enables)
        self.assertIn('expected 1, got 2',runner.snapshot()['motors']['1']['phase'])

    def test_browser_heartbeat_stops_and_disables(self):
        runner,buses=self.runner()
        original=FakeCAN.exchange
        def exchange(bus,*args):
            result=original(bus,*args)
            if bus.enabled:
                runner.heartbeat=time.monotonic()-4
            return result
        with patch.object(FakeCAN,'exchange',exchange):
            runner.run([MOTORS[0]])
        self.assertFalse(buses['can0'].enabled)
        self.assertIn('heartbeat lost',runner.snapshot()['error'])

    def test_stop_during_enable_wait_still_disables(self):
        runner,buses=self.runner()
        original=FakeCAN.exchange
        def exchange(bus,ident,data,*args):
            if ident!=0x7FF and data[-1]==0xFC:
                bus.enabled.add(ident)
                runner.stop_event.set()
                raise Cancelled()
            return original(bus,ident,data,*args)
        with patch.object(FakeCAN,'exchange',exchange):
            runner.run([MOTORS[0]])
        self.assertFalse(buses['can0'].enabled)

    def test_matcher_rejects_wrong_response(self):
        class Invalid:
            def exchange(bus, ident, data, match, *_args):
                if ident==0x7FF:
                    self.assertFalse(match(18,data[:4]+bytes(4)))
                    self.assertFalse(match(17,bytes.fromhex('02 00 33 08')+bytes(4)))
                    self.assertFalse(match(17,bytes.fromhex('01 00 33 07')+bytes(4)))
                else:
                    self.assertFalse(match(18,bytes(8)))
                    self.assertFalse(match(17,bytes([2])+bytes(7)))
                raise TimeoutError()
        with self.assertRaises(TimeoutError):
            read_register(Invalid(),MOTORS[0],8,.5,lambda:False)
        with self.assertRaises(TimeoutError):
            command(Invalid(),MOTORS[0],0xFC,.5,lambda:False)

    def test_four_branches_enable_simultaneously_and_cleanup_all(self):
        runner,buses=self.runner()
        enabled_barrier=threading.Barrier(4,timeout=2)
        observations=[]
        original=FakeCAN.exchange
        def exchange(bus,ident,data,*args):
            result=original(bus,ident,data,*args)
            if ident!=0x7FF and data[-1]==0xFC:
                enabled_barrier.wait()
                observations.append(sum(len(b.enabled) for b in buses.values()))
                # Second rendezvous prevents an early disable during observation.
                enabled_barrier.wait()
                runner.stop_event.set()
            return result
        with patch.object(FakeCAN,'exchange',exchange):
            runner.run(MOTORS)
        self.assertEqual(observations,[4,4,4,4])
        self.assertEqual({name:bus.enables for name,bus in buses.items()},
                         {'can0':[1],'can1':[13],'can2':[14],'can3':[19]})
        self.assertTrue(all(not bus.enabled for bus in buses.values()))
        self.assertTrue(all(v is None for v in runner.snapshot()['active'].values()))

    def test_disable_failure_cancels_other_branches(self):
        runner,buses=self.runner(disable_timeout=True)
        runner.run(MOTORS)
        self.assertTrue(runner.stop_event.is_set())
        self.assertTrue(all(not bus.enabled for bus in buses.values()))
        self.assertTrue(all(len(bus.enables)<=1 for bus in buses.values()))
        self.assertIn('Disable reply lost',runner.snapshot()['error'])

    def test_results_start_unknown_and_persist_through_waiting(self):
        runner,_=self.runner()
        motor=MOTORS[0]
        self.assertTrue(all(m['result'] is None for m in runner.snapshot()['motors'].values()))
        for result in ('ok','error'):
            runner.update_motor(motor,color=result)
            runner.update_motor(motor,color='waiting',phase='Checking')
            state=runner.snapshot()['motors']['1']
            self.assertEqual(state['result'],result)
            self.assertEqual(state['color'],'waiting')

    def test_demo_defaults_to_alternating_failed_ids(self):
        runner=Runner(demo=True)
        bus=runner.factory('can0')
        self.assertEqual(bus.missing,tuple(range(2,24,2)))
        self.assertNotIn(1,bus.missing)
        self.assertIn(2,bus.missing)
        self.assertEqual(Runner(demo=True,missing=[]).factory('can0').missing,())

    def test_start_validation(self):
        runner,_=self.runner()
        for branches in ([],['can9'],['can0','can0']):
            with self.assertRaises(ValueError):runner.start(branches)


if __name__=='__main__':
    unittest.main()
