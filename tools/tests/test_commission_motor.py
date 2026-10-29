import contextlib
import io
import queue
from types import SimpleNamespace
import struct
import unittest
from unittest.mock import patch

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "damiao"))
import commission_motor as cm


class FakeAdapter:
    instances = []
    bootloader_error = False
    bootloader_changes = False
    firmware_changes = False

    def __init__(self, *_args):
        self.id, self.master = 1, 0
        self.messages, self.saved = [], False
        self.instances.append(self)

    def close(self):
        pass

    def exchange(self, ident, data, match, timeout=2):
        self.messages.append((ident, data))
        registers = {7: self.master, 8: self.id, 0x15: 0x41480000, 0x0E: 0x37313136, 0x25: 0}
        if ident == 0x7FF:
            motor, cmd, reg = struct.unpack('<HBB', data[:4])
            if motor != self.id:
                raise TimeoutError('No motor at this address')
            if cmd == 0x33:
                if reg == 0x25 and self.bootloader_error:
                    raise TimeoutError("Bootloader register unsupported")
                if reg == 0x25 and self.bootloader_changes and self.saved:
                    registers[reg] = 0x31313131
                if reg == 0x0E and self.firmware_changes and self.saved:
                    registers[reg] = 0x38313136
                response = cm.parameter(self.id, cmd, reg, registers[reg])
            elif cmd == 0x55:
                value = int.from_bytes(data[4:], 'little')
                if reg == 7:
                    self.master = value
                elif reg == 8:
                    self.id = value
                response = cm.parameter(self.id, cmd, reg, value)
            elif cmd == 0xAA:
                self.saved = True
                response = data
            elif cmd == 0xCC:
                response = self.feedback()
            else:
                raise AssertionError('Unexpected command')
        else:
            assert ident == self.id and data[-1] == 0xFD
            response = self.feedback()
        assert match(self.master, response), 'Reply matcher rejected correct motor reply'
        return self.master, response

    def feedback(self):
        position = 32767
        return bytes([self.id & 0xFF]) + position.to_bytes(2, 'big') + bytes(5)


class CommissionTests(unittest.TestCase):
    def run_script(self, *extra):
        args = ['commission_motor.py', '--current-id', '1',
                '--slave-id', '0x12', *extra]
        with patch.object(cm, 'SlcanAdapter', FakeAdapter), patch('sys.argv', args), \
                patch.object(cm.time, 'sleep'), contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            return cm.main(), FakeAdapter.instances[-1]



    def test_id_write_readback_and_save_transaction(self):
        result, bus = self.run_script()
        self.assertEqual(result, 0)
        self.assertEqual((bus.id, bus.master, bus.saved), (0x12, 0x22, True))
        self.assertIn((0x7FF, bytes.fromhex('01 00 55 07 22 00 00 00')), bus.messages)
        self.assertIn((0x7FF, bytes.fromhex('01 00 55 08 12 00 00 00')), bus.messages)
        self.assertIn((0x7FF, bytes.fromhex('12 00 AA 01')), bus.messages)
        self.assertFalse(any(ident != 0x7FF and data[-1] in (0xFC, 0xFE)
                             for ident, data in bus.messages))

    def test_check_only_reads(self):
        result, bus = self.run_script('--check')
        self.assertEqual(result, 0)
        self.assertTrue(all(ident == 0x7FF and data[2] == 0x33
                            for ident, data in bus.messages))

    def test_default_preserves_zero_and_checks_versions_before_and_after(self):
        result, bus = self.run_script()
        self.assertEqual(result, 0)
        self.assertFalse(any(ident != 0x7FF and data[-1] == 0xFE
                             for ident, data in bus.messages))
        for motor in (1, 0x12):
            for register in (0x0E, 0x25):
                self.assertIn((0x7FF, cm.parameter(motor, 0x33, register)[:4]), bus.messages)
        self.assertEqual(bus.messages[0], (0x7FF, cm.parameter(1, 0x33, 0x0E)[:4]))

    def test_wrong_payload_motor_and_wrong_response_id_are_rejected(self):
        class WrongReply:
            def exchange(self, ident, packet, match, timeout=2):
                self_outer.assertFalse(match(0x22, cm.parameter(2, 0x33, 0x0E, 0)))
                self_outer.assertFalse(match(0x23, cm.parameter(1, 0x33, 0x0E, 0)))
                raise TimeoutError('No matching response')
        self_outer = self
        motor = cm.Motor(WrongReply(), 1)
        motor.master = 0x22
        with self.assertRaises(TimeoutError):
            motor.read(0x0E)

    def test_bootloader_error_printed_and_commissioning_continues(self):
        captured = io.StringIO()
        # Capture connection-check output separately from the helper's redirection.
        original_check = cm.Motor.check_connection
        def check(motor, label):
            with contextlib.redirect_stdout(captured):
                return original_check(motor, label)
        with patch.object(FakeAdapter, 'bootloader_error', True), \
                patch.object(cm.Motor, 'check_connection', check):
            result, bus = self.run_script()
        self.assertEqual(result, 0)
        self.assertTrue(bus.saved)
        self.assertEqual(captured.getvalue().count('bootloader=ERROR:'), 2)

    def test_changed_bootloader_does_not_fail(self):
        with patch.object(FakeAdapter, 'bootloader_changes', True):
            result, bus = self.run_script()
        self.assertEqual(result, 0)
        self.assertTrue(bus.saved)

    def test_changed_firmware_fails_post_check(self):
        with patch.object(FakeAdapter, 'firmware_changes', True):
            result, bus = self.run_script()
        self.assertEqual(result, 1)
        self.assertTrue(bus.saved)

    def test_firmware_read_failure_prevents_writes(self):
        original = FakeAdapter.exchange
        def exchange(bus, ident, data, match, timeout=2):
            if ident == 0x7FF and data[2:4] == bytes([0x33, 0x0E]):
                raise TimeoutError('Firmware unavailable')
            return original(bus, ident, data, match, timeout)
        with patch.object(FakeAdapter, 'exchange', exchange):
            result, bus = self.run_script()
        self.assertEqual(result, 1)
        self.assertFalse(bus.saved)
        self.assertEqual((bus.id, bus.master), (1, 0))

    def detection_adapter(self, replies):
        bus = cm.SlcanAdapter.__new__(cm.SlcanAdapter)
        bus.frames = queue.Queue()
        sent = []
        def send(ident, data, log=True):
            sent.append((ident, data))
            mid = int.from_bytes(data[:2], 'little')
            if mid in replies:
                master = replies[mid]
                bus.frames.put((master, cm.parameter(mid, 0x33, 0x0E, 0x37313136)))
                bus.frames.put((master, cm.parameter(mid, 0x33, 0x0E, 0x37313136)))
                bus.frames.put((master, cm.parameter(mid, 0x33, 8, mid)))
        bus.send = send
        return bus, sent

    def test_auto_detect_single_deduplicates_and_probes_all_ids(self):
        bus, sent = self.detection_adapter({0x12: 0x22})
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(bus.auto_detect(duration=0.03), (0x12, 0x22))
        self.assertEqual(len(sent), 0x7FF)
        self.assertTrue(all(ident == 0x7FF and data[2:4] == bytes([0x33, 0x0E])
                            for ident, data in sent))

    def test_auto_detect_multiple_or_none_fails(self):
        for replies, message in (({}, 'no motor'), ({1: 0, 18: 34}, 'Only 1 motor')):
            bus, _ = self.detection_adapter(replies)
            with contextlib.redirect_stdout(io.StringIO()), self.assertRaisesRegex(RuntimeError, message):
                bus.auto_detect(duration=0.03)

    def test_auto_detect_confirm_and_cancel(self):
        args = ['commission_motor.py', '--auto-detect', '--slave-id', '0x12']
        for confirmed in (True, False):
            with patch.object(cm, 'SlcanAdapter', FakeAdapter), \
                    patch.object(FakeAdapter, 'auto_detect', return_value=(1, 0), create=True), \
                    patch('sys.argv', args), patch('builtins.input', side_effect=None if confirmed else EOFError(), return_value='') as prompt, \
                    patch.object(cm.time, 'sleep'), contextlib.redirect_stdout(io.StringIO()), \
                    contextlib.redirect_stderr(io.StringIO()):
                result = cm.main()
            bus = FakeAdapter.instances[-1]
            prompt.assert_called_once()
            self.assertEqual(result, 0 if confirmed else 1)
            self.assertEqual(bus.saved, confirmed)
            if not confirmed:
                self.assertEqual(bus.messages, [])



    def test_slcan_sends_actual_length_without_plugin_padding(self):
        adapter=cm.SlcanAdapter.__new__(cm.SlcanAdapter)
        adapter.receive_error=None
        adapter.can=SimpleNamespace(Message=lambda **kwargs: SimpleNamespace(**kwargs))
        messages=[]
        adapter.bus=SimpleNamespace(send=lambda message, timeout: messages.append(message))
        with contextlib.redirect_stdout(io.StringIO()):
            adapter.send(0x7FF,bytes.fromhex('12 00 33 0E'))
        self.assertEqual(messages[0].data,bytes.fromhex('12 00 33 0E'))
        self.assertEqual(messages[0].arbitration_id,0x7FF)

    def test_version_decode(self):
        self.assertIn('6.1.1.7', cm.version(0x37313136))
        self.assertIn('0.0.0.0', cm.version(0))

    def test_id_input(self):
        self.assertEqual(cm.can_id('0x12'), 18)
        self.assertEqual(cm.can_id('12'), 12)
        with self.assertRaises(cm.argparse.ArgumentTypeError):
            cm.can_id('0x7FF')


if __name__ == '__main__':
    unittest.main()
