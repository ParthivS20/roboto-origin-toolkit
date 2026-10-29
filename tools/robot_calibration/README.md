# RDK robot zeroing and slow shoulder test

Runs on the RDK alongside `../motor_comms_verifier`. Shoulder control uses the shipped `motors_py` SDK; independent identity and fresh feedback checks use standard-library SocketCAN. Stop the verifier **server** and inference first; these tools share its exclusive lock. Support the torso and limbs, have the E-stop ready, and confirm physical ID/bus mapping.

## Zero with the shipped X5 script

At the supported pinned/fixture reference pose, run the supplied per-motor calibration tool:

```sh
cd ~/roboparty_deploy
source /opt/ros/humble/setup.bash
source install/setup.bash
python3 scripts/set_zero.py
```

The shipped script enables one motor at a time in damping mode. Enter sets its zero; Space skips. It disables after each motor. Confirm the correct physical reference before Enter. It does not enforce every low-level result, so independently check fresh positions:

```sh
cd ~/robot_calibration
python3 verify_zeros.py
```

Power-cycle the **motor supply** with the robot supported at the same reference and repeat the read-only check before motion. Persistence across a power cycle has not yet been verified. Waist fixture versus limit-block reference must be recorded for the later runtime offset; these tools do not change robot.yaml.

Interface names changed on the observed RDK boot. Calibration helpers require can0–can3 to map respectively to USB devices 1-1.1.1:1.0 through 1-1.1.4:1.0 and refuse otherwise. The internal SPI CAN controller belongs at can4. This mapping was corrected for the current session; recheck after an RDK reboot.

## Alternating shoulder pitch

**Remove and account for every pin/fixture before running.** Arms must start near their verified hanging zero/rest pose, and any supporting joint loads must be supported mechanically. This program controls only motor 14/can2 and motor 19/can3; it doesn't hold the torso, elbow or other joints.

```sh
source /opt/ros/humble/setup.bash
source ~/roboparty_deploy/install/setup.bash
python3 shoulder_pitch.py --degrees 15 --seconds 15 --cycles 1
```

Type MOVE at its prompt after verifying support, cleared pins and E-stop. One side at a time: left up/down, then right up/down. Timing defaults to 0.5 seconds per requested degree in each direction: 3 degrees takes 1.5 seconds out and 1.5 seconds back; 15 degrees takes 15 seconds total per side; 45 degrees takes 22.5 seconds each way, 45 seconds total per side. A one-second disabled pause follows each side. One cycle is one left and one right movement; `--cycles` is configurable. Use `--degrees 1` for the first physical direction test; positive degrees here selects a forward shoulder raise (negative logical pitch, with right-side motor sign corrected from the supplied robot.yaml).

Enable, MIT command encoding/transmission and disable use the shipped SDK (`motor_model=0`, Master offset 16, zero offset 0), matching the factory shoulder configuration. Independent SocketCAN management reads retain full identity checks and fresh reply deadlines rather than trusting cached SDK getters.

Trajectory is cosine-eased, relative to measured starting positions. kp defaults to 40 and kd to 2, matching factory robot.yaml. Higher gains are experimental: kp ceiling 500 preserves an existing local edit and kd is capped at the SDK maximum 5. Feedforward torque remains zero. Planned peak speed is capped at 0.12 rad/s. `--velocity-stop` defaults to 0.15 rad/s and permits up to 0.7 rad/s, explicitly requested by the owner; it is a measured-feedback stop, not a commanded speed or hard speed limit. `--side left` and exactly one cycle are required for higher gains, a raised speed stop, or travel above 30 degrees. Maximum requested travel is 45 degrees. Total seconds must be at least degrees; omitting `--seconds` selects 0.5 seconds per degree in each direction.

The higher-gain checks stop above 10 Nm reported torque in either direction, including immediately after SDK initialization. This is a sampled software stop, not a hard torque/current limit; torque can exceed it before feedback and cleanup. The owner explicitly authorized live attempts with the E-stop manned. A left-only 45-degree cycle completed with kp=240/kd=5, 45 seconds total and `--velocity-stop 0.7`. Feedback reached approximately -43.95 degrees relative travel for the -45-degree target and returned within 0.04 degrees of the starting position. Fresh feedback then confirmed motor 14 disabled at 30/27 C. Earlier attempts tripped the 0.15-rad/s speed stop, and the owner reported jerky movement; completion does not establish smoothness or general stability. No gravity compensation or torque support of other joints is provided.

During the completed run, the RDK's `shoulder_pitch.py` was edited to remove input validation and the configurable speed-stop option. Those edits were preserved. The tested source from this repository is separately installed on that RDK as `~/robot_calibration/shoulder_pitch_verified.py`; its 17 mocked tests pass when loaded as the shoulder_pitch module. Use that verified copy to reproduce the completed configuration:

```sh
python3 shoulder_pitch_verified.py --side left --degrees 45 --seconds 45 --cycles 1 --kp 240 --kd 5 --velocity-stop 0.7
```

Stops on reply timeout, motor fault, excessive velocity/travel/following error or temperature, and repeats SDK disable calls for selected shoulders on exit/Ctrl+C. Following error is limited to half the requested angle, bounded between 0.5 and 8 degrees. Each endpoint must track within one quarter of the angle, bounded between 0.3 and 3 degrees. A stationary 1-degree test cannot pass. Target and actual relative angles are logged every half second. Hard power/process/CAN failure can prevent software cleanup; verify LEDs and use physical E-stop as needed.

Diagnostics report a fresh feedback frame after SDK initialization, the status nibble during motion, and the estimated MIT torque `kp*(target-position)+kd*(desired_velocity-velocity)` before motor limits and packet quantization. Following-error messages use angles relative to the measured rest pose, matching progress logs, and include the raw reply. Nominal status 0 is disabled and 1 enabled; some observed firmware overlaps IDs above 15 with that nibble, so right shoulder ID 19 needs physical LED confirmation. At kp=40, a 0.5-degree error contributes only about 0.35 Nm of position torque. A small-angle failure does not alone distinguish friction/load from an enable or command problem. These diagnostics do not increase gains or relax stopping limits.

Automated tests:

```sh
python3 -m unittest discover -s . -v
```

The owner has run 1- and 3-degree tests at kp=40; they stopped on following error. Automated tests use mocks and send no hardware commands. After explicit authorization with the owner manning the E-stop, the agent separately ran one live left-shoulder 3-degree cycle at kp=120/kd=3 over 20 seconds; it completed and disabled. The owner confirmed physical left shoulder pitch movement. Further live results are recorded in the dated commissioning record. The shipped zero script and independent reads completed on 2026-10-13; all 23 positions were approximately -0.000191 rad. See the dated commissioning record for evidence and remaining persistence checks.

## Alternating arms using the owner's working version

`arms_back_and_forth.py` is based on the owner's pasted working script and preserves its controller behavior, including the 2 rad/s measured-speed stop and 10 Nm reported-torque stop at higher gains. It defaults to both arms, alternating left out/back then right out/back, 45 degrees, 45 seconds of motion per arm, kp=240/kd=5 and one cycle. Omitted --seconds now receives the angle-based default, and the speed-stop message matches the actual 2 rad/s check. --cycles repeats the left/right sequence. Twenty-one mocked checks pass locally; its four dedicated alternation tests also pass on the RDK.

A live left/right cycle reached approximately -44.00 degrees on motor 14 and +43.98 degrees on motor 19, and returned within 0.04/0.02 degrees of their measured starts. The owner confirmed physical forward right-arm movement, then asked to end the test and requested a four-second-per-arm command. Stop was sent and disable commands were repeated for both motors. Four-second motion (two seconds out, two seconds back) has not been live-tested; it retains a one-second disabled pause after each arm. Run on the RDK:

```sh
cd ~/robot_calibration
python3 arms_back_and_forth.py --side both --degrees 45 --seconds 4 --cycles 1 --kp 240 --kd 5
```

## Experimental waist centering — not hardware validated

`center_waist.py` uses the shipped SDK on waist motor 13/can1, model 1, Master offset 16 and raw encoder offset 0. It seeks an initial low stop, then four full traversals, requires repeatable low/high stop positions and a known expected span, moves to their midpoint and calls the shipped SDK zero operation. Fresh status and post-zero reads are independent SocketCAN requests. It does not change robot.yaml.

Required inputs are a mechanically validated contact torque (`--max-torque`, Nm) and known full stop span (`--expected-span`, radians). Neither is established for this robot; do not guess them from the motor's rated torque or the existing 2.093-rad waist offset. The latest user-requested settings are 0.4 rad/s target and a 1.5 rad/s measured-speed cutoff, retaining a 6 Nm absolute reported-torque cutoff. The revised controller uses SDK MIT position/velocity commands with supplied waist gains 150/5, scaled to bound estimated PD effort. Torque commands are bounded, with reply, thermal, travel and time checks. A sustained stall with matching torque after established travel is only a possible contact, not proof of a mechanical stop. Repeated contact consistency and span checks reduce false acceptance but cannot distinguish every obstruction or snag.

Keep the robot suspended/supporting loads, clear the waist pin/fixture and all cable restrictions, stop other controllers and keep E-stop accessible. The program prompts CENTER before any motor traffic. Hardware attempts and the later completed centering and zero are recorded in the dated IMU/commissioning notes. This remains an experimental procedure, not a generally validated calibration routine. Motor zeroing at mechanical center changes the meaning of the encoder reference; the runtime waist offset must then be reviewed (a true centered encoder zero needs 0 instead of the hard-stop 2.093 offset), and persistence verified after a supported motor-supply power cycle.


Latest waist threshold behavior: `--max-torque 6` is a soft contact stop: release torque immediately, validate the known endpoint and torque direction, wait for settling, then let the sequence reverse. A 6 Nm event elsewhere aborts as an obstruction. `--hard-torque 9` aborts the complete program for absolute reported torque **above** 9 Nm. Centering treats a 6 Nm event as unexpected and aborts. Target speed remains 0.4 rad/s and the speed cutoff 1.5 rad/s. These checks use reported feedback; sampling latency and motor dynamics can produce overshoot. The initial threshold revision was mock-tested before the subsequent hardware completion described below.

Hardware completion on 14 October 2026 is documented in [the dated record](../../docs/commissioning/imu_2026-10-14.md): four traversals completed, centering required bounded integral assistance, SDK zero succeeded and fresh disabled feedback was near zero. The RDK runtime waist offset was then changed to 0. Earlier absolute stop positions and interrupted resume records belong to the **old encoder reference** and must not be reused after this zero. Measure new stops before another calibration. Persistence after motor-supply power cycle remains unverified.
