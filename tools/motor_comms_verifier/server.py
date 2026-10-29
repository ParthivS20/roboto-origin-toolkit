#!/usr/bin/env python3
"""RDK LED commissioning server. Starts idle; live CAN only after explicit Start."""
import argparse
from collections import deque
import copy
import fcntl
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import signal
import threading
import time
from urllib.parse import urlsplit

from canbus import Cancelled, DemoCAN, SocketCAN, NEUTRAL_MIT, command, read_register
from topology import BRANCHES, MOTORS

ROOT = Path(__file__).resolve().parent


class Runner:
    def __init__(self, demo=False, missing=None, slot=2.0, timeout=0.5, factory=None):
        self.demo, self.slot, self.timeout = demo, slot, timeout
        missing = tuple(range(2, 24, 2)) if missing is None else tuple(missing)
        self.factory = factory or (lambda bus: DemoCAN(bus, missing) if demo else SocketCAN(bus))
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.thread = None
        self.heartbeat = 0
        self.state = dict(running=False, mode='Demo' if demo else 'Live', phase='Idle',
                          active={bus: None for bus in BRANCHES}, cycle=0, slot=slot, timeout=timeout, error=None,
                          branches={bus: dict(cycle=0, phase='Idle', selected=False) for bus in BRANCHES},
                          motors={str(m['id']): dict(m, color='idle', result=None, phase='Not checked',
                                   latency_ms=None, raw=None) for m in MOTORS})
        self.logs = deque(maxlen=60)

    def snapshot(self):
        with self.lock:
            return dict(copy.deepcopy(self.state), events=list(self.logs))

    def log(self, text):
        with self.lock:
            self.logs.appendleft(dict(time=time.strftime('%H:%M:%S'), text=text))

    def update_motor(self, motor, **changes):
        with self.lock:
            if changes.get('color') in ('ok', 'error'):
                changes['result'] = changes['color']
            self.state['motors'][str(motor['id'])].update(changes)

    def alive(self):
        with self.lock:
            self.heartbeat = time.monotonic()

    def cancelled(self):
        if time.monotonic() - self.heartbeat > 3:
            with self.lock:
                self.state['error'] = 'Browser heartbeat lost; disabling motors.'
            self.stop_event.set()
        return self.stop_event.is_set()

    def start(self, branches):
        if not branches or len(set(branches)) != len(branches) or any(b not in BRANCHES for b in branches):
            raise ValueError('Select valid CAN branches')
        with self.lock:
            if self.thread and self.thread.is_alive():
                raise ValueError('A cycle is already running')
            if not self.demo and self.controller_running():
                raise ValueError('Stop inference_node before commissioning')
            self.stop_event.clear()
            self.heartbeat = time.monotonic()
            self.state.update(running=True, error=None, cycle=0, phase='Connecting')
            for bus, branch in self.state['branches'].items():
                branch.update(cycle=0, phase='Connecting' if bus in branches else 'Not selected', selected=bus in branches)
                self.state['active'][bus] = None
            selected = [m for m in MOTORS if m['bus'] in branches]
            self.thread = threading.Thread(target=self.run, args=(selected,), daemon=True)
            self.thread.start()

    @staticmethod
    def controller_running():
        for path in Path('/proc').glob('[0-9]*/comm'):
            try:
                if path.read_text().strip() == 'inference_node':
                    return True
            except (OSError, UnicodeError):
                continue  # Process may have exited while scanning.
        return False

    def stop(self):
        self.stop_event.set()
        thread = self.thread
        if thread:
            thread.join(timeout=5)
        if thread and thread.is_alive():
            raise RuntimeError('Disable cleanup still running; inspect motor LEDs / use E-stop.')

    def wait_until(self, deadline):
        while time.monotonic() < deadline:
            if self.cancelled():
                raise Cancelled()
            self.stop_event.wait(min(0.025, max(0, deadline-time.monotonic())))

    def run(self, selected):
        buses, workers = {}, []
        try:
            for name in dict.fromkeys(m['bus'] for m in selected):
                with self.lock:
                    self.state['branches'][name]['selected'] = True
                buses[name] = self.factory(name)
            for motor in selected:
                buses[motor['bus']].send(motor['id'], b'\xff'*7 + b'\xfd')
            self.log('Disabled baseline sent. Branches cycling simultaneously, one motor per branch.')
            with self.lock:
                self.state['phase'] = 'Cycling'
            for name, bus in buses.items():
                motors = [m for m in selected if m['bus'] == name]
                worker = threading.Thread(target=self.run_branch, args=(name, bus, motors), daemon=True)
                workers.append(worker)
                worker.start()
            for worker in workers:
                worker.join()
        except Exception as exc:
            with self.lock:
                self.state['error'] = str(exc)
            self.log('Stopped: '+str(exc))
        finally:
            self.stop_event.set()
            for worker in workers:
                if worker.ident is not None:
                    worker.join()
            # All branch workers have stopped before cleanup touches their sockets.
            failures = []
            for motor in selected:
                bus = buses.get(motor['bus'])
                if bus:
                    try:
                        for _ in range(3):
                            bus.send(motor['id'], b'\xff'*7 + b'\xfd')
                    except Exception as exc:
                        failures.append('ID %s: %s' % (motor['id'], exc))
            for bus in buses.values():
                bus.close()
            with self.lock:
                self.state.update(running=False, active={name: None for name in BRANCHES}, phase='Stopped')
                if failures:
                    self.state['error'] = 'Disable send failed: '+ '; '.join(failures)
                for branch in self.state['branches'].values():
                    if branch['selected']:
                        branch['phase'] = 'Stopped'
                for motor in self.state['motors'].values():
                    if motor['color'] == 'waiting':
                        motor.update(color=motor['result'] or 'idle', phase='Stopped · disable sent, unconfirmed')
            self.log('Cleanup: disable frames sent; physically verify red LEDs. No cleanup ACK claim.')

    def run_branch(self, name, bus, selected):
        active = None
        try:
            while not self.cancelled():
                with self.lock:
                    self.state['branches'][name]['cycle'] += 1
                    self.state['cycle'] = min(branch['cycle'] for branch in self.state['branches'].values() if branch['selected'])
                for motor in selected:
                    if self.cancelled():
                        raise Cancelled()
                    deadline = time.monotonic() + self.slot
                    with self.lock:
                        self.state['active'][name] = motor['id']
                        self.state['branches'][name]['phase'] = 'Checking'
                    self.update_motor(motor, color='waiting', phase='Checking IDs / MIT mode', raw=None,
                                      latency_ms=None)
                    try:
                        # Full ID readbacks avoid relying solely on the truncated feedback ID.
                        for register, expected in ((8, motor['id']), (7, motor['master']), (10, 1)):
                            actual, _ = read_register(bus, motor, register, self.timeout, self.cancelled)
                            if actual != expected:
                                raise RuntimeError('Register 0x%02X: expected %s, got %s' % (register, expected, actual))
                    except (TimeoutError, RuntimeError) as exc:
                        self.update_motor(motor, color='error', phase=str(exc))
                        self.log('%s · ID %s skipped: %s' % (motor['bus'], motor['id'], exc))
                        self.wait_until(deadline)
                        continue
                    enable_failed = False
                    active = motor  # Cleanup must disable even if enable reply is missing.
                    try:
                        command(bus, motor, 0xFD, self.timeout, self.cancelled)
                        bus.send(motor['id'], NEUTRAL_MIT)
                        self.update_motor(motor, color='waiting', phase='Enable sent · awaiting reply')
                        with self.lock:
                            self.state['branches'][name]['phase'] = 'Enabling'
                        reply = command(bus, motor, 0xFC, self.timeout, self.cancelled)
                        self.update_motor(motor, color='ok', phase='Enable reply received', **reply)
                        self.log('%s · ID %s enable reply · %.1f ms' % (motor['bus'], motor['id'], reply['latency_ms']))
                        # Hold for roughly one second, leaving time for disable within the slot.
                        self.wait_until(min(deadline-self.timeout, time.monotonic()+1.0))
                    except TimeoutError as exc:
                        enable_failed = True
                        self.update_motor(motor, color='error', phase='Enable timeout')
                        self.log('ID %s: %s; attempting disable.' % (motor['id'], exc))
                    # Failure to get a disable reply halts cycling; never enable the next motor.
                    self.update_motor(motor, color='waiting', phase='Disable sent · awaiting reply')
                    with self.lock:
                        self.state['branches'][name]['phase'] = 'Disabling'
                    reply = command(bus, motor, 0xFD, self.timeout, self.cancelled)
                    self.update_motor(motor, color='error' if enable_failed else 'ok',
                                      phase='Enable timed out · disable reply received' if enable_failed
                                      else 'Disable reply received', **reply)
                    active = None
                    self.wait_until(deadline)
        except Cancelled:
            self.log(name+': stopped; disable cleanup requested.')
        except Exception as exc:
            with self.lock:
                self.state['error'] = name+': '+str(exc)
            if active:
                self.update_motor(active, color='error', phase='Stopped: '+str(exc))
            self.log(name+': stopped: '+str(exc))
            # A disable failure or motor fault cancels every branch.
            self.stop_event.set()
        finally:
            # Disable the possibly active joint immediately, without waiting on other branches.
            if active:
                try:
                    for _ in range(3):
                        bus.send(active['id'], b'\xff'*7+b'\xfd')
                except Exception as exc:
                    with self.lock:
                        self.state['error'] = name+': disable cleanup failed: '+str(exc)
                    self.stop_event.set()


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def json(self, value, status=200):
        data = json.dumps(value).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == '/api/state':
            self.json(dict(self.server.runner.snapshot(), token=self.server.token))
        else:
            super().do_GET()

    def do_POST(self):
        # No CORS. Cross-origin requests cannot control real motors.
        origin = self.headers.get('Origin')
        host = self.headers.get('Host')
        if (origin and urlsplit(origin).netloc != host) or self.headers.get('Sec-Fetch-Site') == 'cross-site':
            return self.json({'error': 'Cross-origin control denied'}, 403)
        if self.headers.get('X-Control-Token') != self.server.token:
            return self.json({'error': 'Invalid control token'}, 403)
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 <= length <= 4096:
                raise ValueError('Invalid body size')
            body = json.loads(self.rfile.read(length) or b'{}')
            if self.path == '/api/start':
                self.server.runner.start(body.get('branches', []))
            elif self.path == '/api/stop':
                self.server.runner.stop()
            elif self.path == '/api/heartbeat':
                self.server.runner.alive()
            else:
                return self.json({'error': 'Not found'}, 404)
            self.json({'ok': True})
        except (ValueError, RuntimeError) as exc:
            self.json({'error': str(exc)}, 400)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--demo', action='store_true', help='Simulate CAN; no hardware access')
    parser.add_argument('--demo-missing', type=int, nargs='*', default=None,
                        help='Override demo failures; default: every even motor ID fails')
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--slot', type=float, default=2.0)
    parser.add_argument('--timeout', type=float, default=0.5)
    args = parser.parse_args()
    if not (1.5 <= args.slot <= 10 and 0.1 <= args.timeout <= 1 and args.timeout < args.slot/2):
        parser.error('Use slot 1.5–10 s and timeout 0.1–1 s, shorter than half the slot')
    if not (ROOT/'web/dist/index.html').exists():
        parser.error('Build the frontend first: cd web && npm ci && npm run build')
    lockfile = open('/tmp/roboto-led-commissioning.lock', 'w')
    try:
        fcntl.flock(lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        parser.error('Another commissioning server is already running')
    runner = Runner(args.demo, args.demo_missing, args.slot, args.timeout)
    server = ThreadingHTTPServer((args.host, args.port), partial(Handler, directory=str(ROOT/'web/dist')))
    server.runner, server.token = runner, secrets.token_urlsafe(24)
    def shutdown(_signum, _frame):
        runner.stop_event.set()
        threading.Thread(target=server.shutdown, daemon=True).start()
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    print('Roboto commissioning · %s · http://%s:%s · starts idle' %
          ('DEMO' if args.demo else 'LIVE CAN', args.host, args.port), flush=True)
    try:
        server.serve_forever()
    finally:
        runner.stop()
        server.server_close()
        lockfile.close()


if __name__ == '__main__':
    main()
