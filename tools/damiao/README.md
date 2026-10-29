# Damiao motor commissioning — external computer

`commission_motor.py` runs on an external computer with the **standalone Damiao USB2CAN / DM-USB2FDCAN adapter flashed with SLCAN firmware**. It sets Motor/Slave ID, derives Master ID as Motor + 0x10, verifies readbacks, and saves parameters. It preserves the existing zero. There is no zeroing, native SDK, or legacy transport option.

## Install and run

From the repository root:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r tools/requirements.txt
python tools/damiao/commission_motor.py --motor-id 0x12 --check
python tools/damiao/commission_motor.py --motor-id 0x12
```

Connect exactly one physical powered motor. Close DMTool and other serial-port programs. Auto-detection scans firmware reads across standard motor IDs for one second, requires exactly one responding Motor/Master pair, then asks for Enter before writing. It cannot detect two physical motors sharing both IDs.

For a known current ID:

```sh
python tools/damiao/commission_motor.py --current-id 1 --motor-id 0x12
python tools/damiao/commission_motor.py --current-id 0x12 --motor-id 0x12 --check
```

Explicit `--current-id` skips auto-detection and its Enter prompt. `--slave-id` is an alias for `--motor-id`; `--auto-detect` remains an explicit alias for the default discovery behavior. `--port /dev/cu.usbmodem...` selects the observed macOS port (Linux: `/dev/ttyACM...`). Without `--port`, exactly one VID:PID `34b7:6877` serial adapter must be detected. Port names can change after reconnection or flashing.

Damiao SLCAN uses **S5 = classic CAN 1 Mbps**; generic SLCAN's S8 would select 5 Mbps/CAN FD on this firmware. The script explicitly sends S5 and uses serial baud 921600.

## Transaction and limits

The script reads firmware, Motor ID, Master ID, and bootloader (informational), disables the motor, checks for a responding destination ID, changes Master/Motor IDs if needed, verifies each write, disables again, saves parameters, and repeats the connection check. The destination probe precedes disabling/writes. No enable or motion setpoint is sent. Disabling can release load-supporting torque; support the motor/joint.

`--check` sends parameter reads only and does not change the motor. Saving persists all current parameters, including existing unsaved settings. If an operation fails, earlier writes may already be active; use the last acknowledged ID rather than blindly retrying the old one. Motor writes are not automatically retried. Power-cycle and use `--check` afterward to verify persistence.

Live read-only SLCAN discovery/readback was recorded on 2026-10-12: motor 0x12, Master 0x22, firmware 6.1.1.7, bootloader 0.0.0.0. Live ID writes/save were not recorded. The simplified script is tested with simulated transports; no hardware was operated during repository organization.

See [process](../../docs/commissioning/process.md), [firmware](../../docs/adapters/firmware.md), and [findings](../../docs/commissioning/findings.md). The RDK X5 verifier is a separate [tool](../motor_comms_verifier/README.md).
