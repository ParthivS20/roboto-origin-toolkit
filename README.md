# Roboto Origin Toolkit

Team repository for Roboto Origin assembly, motor commissioning, tools, and findings. Historical hardware observations are dated; verify the current robot configuration before use.

## Two CAN workflows

| Tool | Where it runs | Connection | Purpose |
|---|---|---|---|
| [commission_motor.py](tools/damiao/README.md) | External computer | Standalone Damiao USB2CAN / DM-USB2FDCAN adapter with **SLCAN firmware** | Discover one motor, assign Motor/Slave ID and Master ID, verify, and save |
| [motor_comms_verifier](tools/motor_comms_verifier/README.md) | **RDK X5** | Robot board's four Linux SocketCAN buses, can0–can3 | Check motor communications through enable/disable cycles and a browser dashboard |

The verifier's browser can run on your computer; its server and CAN access run on the RDK X5. SLCAN flashing is required for the standalone Damiao adapter used by the bench script. The RDK's robot board uses its own matching SocketCAN firmware.

## Manuals and findings

- [English manuals](docs/manuals/README.md): main installation and RDK X5 commissioning guides.
- [DMTool download and installation](docs/dmtool/download_install.md).
- [DMTool usage](docs/dmtool/usage.md): English language toggle, connection settings, and Motor ID fields.
- [Commissioning process](docs/commissioning/process.md).
- [Motor ID table](docs/commissioning/motor_ids.md): all 23 motors, models, Master IDs, and harness order.
- [Manual CAN ID-change messages](docs/commissioning/manual_can_id_change.md).
- [Adapter firmware](docs/adapters/firmware.md): factory, SLCAN, and gs_usb differences, official links, and flashing.
- [Findings](docs/commissioning/findings.md): verified observations and remaining checks.
- [Robot zeroing, 13 October 2026](docs/commissioning/zeroing_2026-10-13.md): shipped-script completion and fresh feedback evidence.
- [IMU communications, 14 October 2026](docs/commissioning/imu_2026-10-14.md): verified live data and corrected baud rate.
- [CAN scheduling, termination and IMU bring-up](docs/rdk_x5/can_imu_bringup.md).
- [RDK X5 setup notes](docs/rdk_x5/README.md).
- [Custom interrupt policy](docs/rdk_x5/interrupt_policy.md).
- [Six assembly videos](videos/README.md).
- [Sources and attribution](docs/references/sources.md).

**DMTool ID-change trap:** the software's selected Motor ID and Parameter Settings addressing ID must match the motor's **current** ID. Entering the desired new ID makes the software search for a motor at an ID that does not yet exist. Change the actual ID using CAN-tab register messages followed by save, or the bench commissioning script; then update the software address.

## USB2CAN adapter firmware source

Official source: [Damiao USB2CANFD firmware repository](https://github.com/dmBots/dm-tools/tree/master/USB2CANFD/%E5%9B%BA%E4%BB%B6). The repository provides factory, gs_usb, and SLCAN adapter firmware.

Our external-computer commissioning script requires [the official SLCAN firmware](https://github.com/dmBots/dm-tools/tree/master/USB2CANFD/%E5%9B%BA%E4%BB%B6/socketcan/slcan%E5%9B%BA%E4%BB%B6). See [manufacturer flashing instructions](https://github.com/dmBots/dm-tools/blob/master/USB2CANFD/%E5%9B%BA%E4%BB%B6/socketcan/slcan%E5%9B%BA%E4%BB%B6/FLASHING.md) and our [firmware guide](docs/adapters/firmware.md). The collected packages are included in [firmware/damiao_usb2can](firmware/damiao_usb2can/README.md).

## Bench commissioning: external computer

From this repository's root:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r tools/requirements.txt

# Read-only discovery and ID/firmware checks:
python tools/damiao/commission_motor.py --motor-id 0x12 --check

# Discover, confirm, assign IDs, read back, and save:
python tools/damiao/commission_motor.py --motor-id 0x12
```

Connect exactly one powered motor and close DMTool. `0x12` is decimal 18; Master ID is derived as Motor ID + `0x10`, so `0x22` (34). The script uses SLCAN only and preserves the physical zero. Power-cycle and rerun `--check` to verify ID persistence. See the tool README for known-current-ID and serial-port options.

## Communications verifier: RDK X5

Copy `tools/motor_comms_verifier/` or its included runtime archive to the RDK. From the tool directory **on the RDK**, run:

```sh
python3 server.py
```

Open `http://<RDK-address>:8080` in your computer's browser. The app starts idle; select branches and explicitly start a cycle. Support the robot and limbs, stop other motor controllers, and keep the E-stop accessible: the verifier sends enable/disable commands and can produce or release torque.

The RDK backend uses Python's standard library. The prebuilt frontend is included, so Node is needed only when editing/rebuilding the web app. Demo mode (`python3 server.py --demo`) uses simulated CAN.

## Robot calibration: RDK X5

[Robot calibration and slow shoulder test](tools/robot_calibration/README.md) provides separate full-robot zero/save and alternating shoulder-pitch programs. The shoulder test defaults to 15 degrees, with 0.5 seconds per degree in each direction (7.5 seconds out and 7.5 seconds back per side). These are physical commissioning tools; follow their support, pin removal, and persistence checks before motion.

## Layout

```text
docs/       manuals, DMTool, commissioning, adapters, RDK setup, and references
firmware/   official standalone Damiao adapter packages
tools/      Python requirements, bench script, RDK verifier, and tests
videos/     six assembly tutorial episodes
```

## Development checks

```sh
python3 -m unittest discover -s tools/tests -v
python3 -m unittest discover -s tools/motor_comms_verifier -v
```

Tests use simulated transports. Live read-only bench SLCAN discovery/readback was previously verified; ID writes/save and full-robot commissioning require separate live checks.

PDFs and videos use Git LFS. Install Git LFS and run `git lfs install` on a new team computer before cloning/pushing.
