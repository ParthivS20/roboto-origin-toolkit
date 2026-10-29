# motor_comms_verifier — RDK X5

Runs its Python server on the **RDK X5**, with the dashboard viewed from a browser on your external computer. This is separate from the Damiao USB2CAN bench ID-setting script.

A dark Vite/Three.js dashboard and a standard-library Python SocketCAN backend for the RDK X5. The supplied Roboto Origin URDF and STL geometry are included. Python requires no pip packages, ROS environment, DMTool, or Damiao native library. The prebuilt web/dist folder means **Node is not required on the RDK**.

## Run on the RDK

Copy the included runtime archive to the board (from the Mac, substitute its actual address):

```sh
scp motor_comms_verifier.tar.gz sunrise@192.168.127.10:~/
```

On the RDK:

```sh
mkdir -p ~/motor_comms_verifier
tar -xzf ~/motor_comms_verifier.tar.gz -C ~/motor_comms_verifier
cd ~/motor_comms_verifier
python3 server.py
```

Open http://192.168.127.10:8080 in the Mac's browser (or http://10.42.0.1:8080 on the board hotspot). The server starts **idle**. Select the connected branches, then click **Start cycle**. Live mode requires Linux SocketCAN buses can0–can3, the actual branch mapping below, 1 Mbps, and configured motor IDs/Master IDs. Use the RDK's four-channel board USB-to-CAN link; a standalone Damiao USB adapter that does not enumerate SocketCAN cannot be used directly by this tool.

Support the robot and loose limbs, make the physical E-stop accessible, and stop every other motor-control program first. Enabling can produce torque or release supporting torque when disabled. The server refuses to start if it detects inference_node; this does not detect every possible controller. Do not enable inference, DMTool, another commissioning program, or zeroing software while this tool owns the bus.

To inspect interfaces:

```sh
ip -br link
lsusb -t
ip -details -statistics link show can0
```

If interfaces already have the correct verified names but need configuration, run the following **only for connected branches** while other controllers are stopped:

```sh
sudo ip link set can0 down
sudo ip link set can0 up type can bitrate 1000000
sudo ip link set can0 txqueuelen 1000
```

Repeat for other verified branches. The server does not rename interfaces, alter bitrate, or flash adapter firmware. Normal SocketCAN access usually does not require root once interfaces are configured. Do not install generic CAN drivers if the board already enumerates correctly.

## What a cycle does

Selected branches run **simultaneously and independently**, with **one enabled motor per branch** (up to four total). Each advances every two seconds in its own physical harness order. Left leg repeats roughly every 12 seconds, waist/right leg every 14 seconds, and each arm every 10 seconds. The cycle counter shows the slowest selected branch; each fixed-size detail card also shows its own cycle. The 3D view highlights all active joints together.

Physical harness order (supplied manual B7/B8 and deployment configuration):

| Bus | Order | Branch |
|---|---|---|
| can0 | 1 → 2 → 3 → 4 → 5 → 6 | Left hip yaw / roll / pitch, knee, upper / lower ankle |
| can1 | **13 → 7 → 8 → 9 → 10 → 11 → 12** | Waist first, then right hip yaw / roll / pitch, knee, upper / lower ankle |
| can2 | 14 → 15 → 16 → 17 → 18 | Left shoulder pitch / roll / yaw, elbow, distal rotation |
| can3 | 19 → 20 → 21 → 22 → 23 | Right shoulder pitch / roll / yaw, elbow, distal rotation |

For each two-second slot:

1. Mark the joint yellow. Read motor ID (register 8), Master ID (7), and mode (10). Replies must match the full motor ID in the parameter payload and Master CAN ID (motor+16). Require MIT mode = 1; never silently change it.
2. If a precheck times out or mismatches, mark red, skip enabling, then advance. Each individual response deadline defaults to 0.5 seconds. No FW/bootloader reads are needed here.
3. Confirm a disable-command reply, send a neutral MIT frame with kp=kd=0 and nominal zero velocity/feedforward torque, then send enable FC. The packed symmetric zero fields have normal protocol quantization; this is not a position-hold test.
4. Yellow while waiting; green after a matching, non-fault feedback frame. Hold for roughly one second, then send disable FD and await its reply. Yellow/green applies to both transitions. Keep enable timeouts red even if the subsequent disable replies.
5. Advance at the end of the slot. If checks take longer than the slot, advance only after they finish; never overlap enabled motors within the same branch to preserve timing. A lost disable reply or motor fault cancels all branch workers and triggers disable cleanup on every selected branch.

Dark gray = never checked since server startup. Dots always keep the same size; only their color changes. Each motor retains its last pass/fail result across cycles and browser reloads; waiting is a temporary yellow overlay on the active joint. Stopping a check restores its saved result instead of clearing it. Restarting the backend resets all dots to dark gray. Yellow = awaiting reply. Green = the last command received a matching non-fault reply, **not necessarily currently enabled**. Red = timeout/mismatch/fault. The detail panel says whether the reply followed enable or disable and shows raw bytes, latency, temperatures. Click a marker or motor number to inspect it; selection does not send commands.

Motor feedback does not echo a command sequence number. The backend drains old queued packets before each transaction, matches the bus/Master ID and payload low ID nibble, and requires full ID register prechecks. Periodic unsolicited feedback cannot always be distinguished from a direct command acknowledgement. On some firmware, IDs above 15 overlap the feedback status nibble (the owner's disabled ID 18 returned 0x12). Therefore the tool does **not claim that feedback alone proves the LED changed or that a motor is physically disabled**. Observe actual red/green LEDs. Duplicate motor IDs on one bus cannot reliably be detected with this protocol.

## Stop and connection loss

- **Stop & disable** sets cancellation immediately and repeats disable frames for all selected motors.
- Browser heartbeat every 0.7 s; more than 3 s without a heartbeat stops the cycle. Closing/suspending the browser or losing its network triggers this. Keep the page foreground during the check.
- Ctrl+C / SIGTERM also cancels and performs disable cleanup.
- Cleanup sends three disable frames per selected motor. These are best-effort sends and are explicitly **not acknowledged cleanup**. If CAN/power is lost, the software cannot guarantee disable. Verify LEDs/use the physical E-stop as needed.
- A hard process kill, host power failure, or kernel failure cannot execute cleanup. Do not use this tool as an E-stop or load-bearing controller.
- No hardware zero command, ID write, parameter save, automatic mode change, or firmware flash is sent.

The HTTP service listens on the RDK's network interfaces. Keep it on the trusted robot LAN/hotspot, not Internet-forwarded. The random control token and same-origin checks protect against cross-site browser requests; they are not user authentication against another device on that LAN. Only one operator browser should control it. One server instance is enforced with a local process lock.

## Demo and timing

On the Mac or RDK, with no motor connection:

```sh
python3 server.py --demo  # Odd IDs pass; even IDs fail
# Override the default: make only motor 5 fail the precheck to see a red joint:
python3 server.py --demo --demo-missing 5
# All motors pass:
python3 server.py --demo --demo-missing
```

Optional timing:

```sh
python3 server.py --slot 2 --timeout 0.5 --port 8080
```

The tool does not start a cycle merely because the server launches. Start is always a page action. Model pose is static, not live joint telemetry. The ankle highlight marks the corresponding URDF linkage joint; the two ankle actuators are coupled and these markers are not an exact independent actuator-axis depiction.

## Build or modify the frontend

The source uses only Vite and Three.js, with system fonts, no React/UI framework, no CDN or external font calls. Building Vite 7 requires Node 20.19+ or 22.12+; building on the Mac and copying web/dist avoids installing Node on the RDK.

```sh
cd web
npm ci
npm run build
```

For frontend development, run the Python demo server on 8080 and `npm run dev` in web; Vite proxies /api to it. Production runs a single Python server serving both API and built static files.

Tests:

```sh
python3 -m unittest discover -s . -v
```

## Sources and verification

- Topology: owner commissioning manual B7/B8/D4 and supplied roboparty_deploy/src/inference/robots/rpo/robot.yaml. The topology is explicit in topology.py and editable there if the measured harness differs.
- Model copied from supplied roboto_origin/modules/rpo_description/urdf/rpo.urdf and meshes. Its upstream GPL license is retained at web/public/model/LICENSE (and web/dist/model/LICENSE after building). Model source: https://github.com/Roboparty/rpo_description . Retain the source/license when distributing.
- Damiao commands: https://github.com/dmBots/motor-sdk and supplied roboparty_motors DM driver (FC enable, FD disable, parameter reads).
- Vite build prerequisites: https://vite.dev/guide/ .

Automated tests cover physical branch order, one-enabled-motor-per-branch invariant, concurrent four-branch enabling, cross-branch cancellation, missing-motor skips, wrong mode, reply filtering, lost disable replies, cancellation, heartbeat loss, and input validation. Browser demo verifies the actual supplied 3D model, colors and controls. No live motor enable/disable testing was performed while creating the program.

## Rebuild the RDK runtime archive

After rebuilding the frontend, run this from the tool directory:

```sh
COPYFILE_DISABLE=1 tar -czf motor_comms_verifier.tar.gz server.py canbus.py topology.py README.md web/dist
```

The archive includes only runtime files and the prebuilt frontend, so the RDK requires neither Node nor pip packages.
