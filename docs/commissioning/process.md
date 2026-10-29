# Motor commissioning process

## 1. Bench: external computer and Damiao USB2CAN

1. Choose the motor's intended joint from the [motor ID table](motor_ids.md); label the physical motor. Motor 18 (`0x12`) is the left distal arm rotation, while the left elbow is 17 (`0x11`).
2. Connect **exactly one physical motor** to the standalone Damiao adapter with correct power, CAN-H/L, and termination. Disconnect other motors, including unpowered ones. Support the joint: disabling can release supporting torque.
3. For DMTool, use the vendor-supported matching adapter firmware. For our Python script, flash the adapter's **SLCAN firmware** first; see [firmware instructions](../adapters/firmware.md). Close DMTool before opening the adapter with the script.
4. Discover/read the current IDs before writing. From the repository root:

```sh
python tools/damiao/commission_motor.py --motor-id 0x12 --check
```

5. Program the desired ID using auto-detection and the Enter confirmation:

```sh
python tools/damiao/commission_motor.py --motor-id 0x12
```

The target Master ID is derived automatically (`0x12 + 0x10 = 0x22`). If the current ID is known, `--current-id 1 --motor-id 0x12` skips auto-detection and its confirmation. `--port` selects a specific adapter serial port.

6. Require matching write acknowledgements, full ID-register readbacks, a save acknowledgement, and the final connection check. Power-cycle, then rerun `--check` to verify persistence. A failed write/save can leave partly changed IDs; reconnect using the last acknowledged ID rather than blindly retrying the original one.

The script disables the motor, writes Master ID (register 7) and Motor ID (register 8) only when needed, saves all current parameters, and checks firmware consistency. It preserves the physical zero and never sends enable/motion commands. Saving also persists any existing unsaved settings; inspect the motor's configuration first.

## 2. DMTool alternative: keep current and target IDs separate

The software's selected Motor ID and Parameter Settings addressing ID must match the **currently programmed** motor. Setting the software address to the desired target makes it search for a motor at an ID that does not yet exist. That prevents the intended write.

Use the old ID to address manual writes in the CAN tab, then switch to the new ID after the acknowledged change. The vendor's CAN-mode parameter panel does not normally expose ordinary CAN ID editing. Follow [the complete manual CAN sequence](manual_can_id_change.md), or use the commissioning script above.

## 3. Assemble and verify on the RDK X5

After bench IDs are assigned and persistent, connect the correctly labeled branches to the robot board. Verify actual USB-to-branch mapping and can0–can3 at 1 Mbps; interface numbering alone does not establish wiring. The right branch starts with waist motor 13, followed by right-leg motors 7–12.

Run [motor_comms_verifier](../../tools/motor_comms_verifier/README.md) **on the RDK X5** and use a browser on the external computer to view it. The verifier reads Motor/Master IDs and mode, then explicitly enables/disables selected motors. It requires MIT mode 1 and expected Master IDs; it does not assign IDs or change control mode.

Support the robot and limbs and keep the E-stop accessible before starting a live cycle. A green marker means a matching non-fault reply was received, not independent proof that the LED changed or that the joint is physically safe.

## 4. Calibration and motion are separate

Motor encoder/parameter calibration can cause rapid rotation and belongs to the manufacturer's detached-motor procedure. Assembled-joint zero calibration depends on the correct physical fixture/pose and matching runtime offsets. Neither is performed by the simplified bench script or implied by a communication pass. Follow the [RDK commissioning manual](../manuals/roboto_origin_rdk_x5_commissioning_manual_en.pdf) for those later stages.
