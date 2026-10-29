# DMTool usage

## Switch the interface to English

The manufacturer manual places the **CN/EN toggle in the bottom status bar**. Click or slide it to select EN. It is not a motor setting and does not require a motor parameter write. The same status bar shows adapter state, bitrate, and send/receive counters.

Source: [official DMTool manual](https://github.com/dmBots/motor-debugging-tool/blob/master/DMTool%E4%B8%8A%E4%BD%8D%E6%9C%BA%E8%BD%AF%E4%BB%B6%E8%AF%B4%E6%98%8E%E4%B9%A6.pdf), printed page 7.

## Connect and read before changing anything

1. Connect the correct standalone Damiao adapter, power one motor, and use classic CAN at 1 Mbps.
2. Select the motor's **existing Motor ID** in the software. The software uses that ID to address/search for a motor; changing this field does not itself reprogram the motor.
3. In Parameter Settings, select CAN mode and read parameters using the same existing motor ID. Keep the software's selected Motor ID and the parameter page's addressing ID consistent with the motor that actually exists on the bus.
4. Record CAN_ID / Slave ID, Master ID, control mode, motor firmware, and adapter firmware. Motor firmware and adapter firmware are separate.
5. After any successful write, read the values back and verify again after a power cycle.

The vendor manual treats CAN_ID and Master ID as hexadecimal fields. The Python tool accepts decimal or `0x`-prefixed hexadecimal: plain `12` is decimal 12; `0x12` is decimal 18. Our robot's Master ID is Motor ID + 16 decimal (`+0x10`).

## Why entering the new ID can lose the motor

Team finding: changing the software's Motor ID to the desired new ID makes DMTool search/address **that new ID**. The motor still answers at its old ID, so DMTool cannot find it and cannot complete the intended ID write. Keeping only the target value in the software is not sufficient.

Keep the software address set to the existing ID. To actually change the motor ID, use the CAN tab's raw register messages or our external-computer commissioning script. See the [commissioning process](../commissioning/process.md) and [manual CAN sequence](../commissioning/manual_can_id_change.md).

The vendor manual also explicitly says that CAN-mode parameter controls do not provide ordinary CAN ID editing by default to avoid accidental changes. It recommends a serial connection for ID editing, or manually sending CAN register writes **followed by a save command** through the CAN analyzer (printed page 17). Our script automates this raw-CAN method.

## Useful controls

- **F2 — Device configuration:** adapter/CAN configuration. Match the motor bus rate.
- **F9 — FDCAN module firmware upgrade:** updates the USB adapter with the matching `.enc` package. This is separate from motor firmware upgrade controls.
- **CAN analyzer/tab:** standard CAN ID, DLC, and hexadecimal payload; supports manual register reads/writes.
- **Parameter Settings:** readback and motor parameters. Do not alter encoder calibration, pole pairs, gear ratio, or physical zero as part of ID assignment.

Our commissioning script only writes IDs and saves existing parameters. Neither its `--check` mode nor a successful ID readback proves encoder calibration is complete. See [findings](../commissioning/findings.md) for what was verified live.
