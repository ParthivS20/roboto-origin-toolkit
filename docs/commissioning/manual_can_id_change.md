# Change motor IDs manually from the DMTool CAN tab

Use the external computer and matching Damiao adapter/DMTool setup, with **one physical motor**, disabled and supported. These examples change current Motor ID **1** to **0x12 (18)** and Master ID to **0x22 (34)**. Substitute the intended joint ID from [the table](motor_ids.md); these values are not universal defaults.

Use **standard 11-bit classic CAN**, 1 Mbps. All parameter requests go to CAN ID **0x7FF**. The first two payload bytes address the current Motor ID in little-endian order. Parameter values occupy four little-endian bytes. The reply CAN ID is the motor's current Master ID.

| Step | TX CAN ID | DLC | TX payload (hex) | Expected result |
|---|---|---|---|---|
| Read current firmware | 7FF | 4 | `01 00 33 0E` | Firmware reply from the current Master ID |
| Read current Master ID | 7FF | 4 | `01 00 33 07` | Full value of register 7 |
| Read current Motor ID | 7FF | 4 | `01 00 33 08` | Value 1 in register 8 |
| Disable current motor | 001 | 8 | `FF FF FF FF FF FF FF FD` | Matching disabled-motor feedback |
| Set Master ID to 0x22 | 7FF | 8 | `01 00 55 07 22 00 00 00` | Write acknowledgement now at CAN 022 |
| Read Master back | 7FF | 4 | `01 00 33 07` | CAN 022, payload `01 00 33 07 22 00 00 00` |
| Set Motor ID to 0x12 | 7FF | 8 | `01 00 55 08 12 00 00 00` | CAN 022, acknowledgement carries new Motor ID 0x12 |
| Read new Motor ID | 7FF | 4 | `12 00 33 08` | CAN 022, payload `12 00 33 08 12 00 00 00` |
| Read new Master ID | 7FF | 4 | `12 00 33 07` | CAN 022, payload `12 00 33 07 22 00 00 00` |
| Disable using new ID | 012 | 8 | `FF FF FF FF FF FF FF FD` | Matching feedback at CAN 022 |
| Save current parameters | 7FF | 4 | `12 00 AA 01` | Matching save acknowledgement at CAN 022 |

Stop on a timeout or mismatch. Do not send the next write without confirming the previous reply. The table follows the script's protocol expectations and simulated transactions; live ID writes/save with this script have not been recorded. Inspect the actual firmware's replies if they differ.

After changing the motor, update DMTool's software addressing ID to `0x12`, then reread parameters. Power-cycle and repeat the final two reads to verify flash persistence. Merely entering `0x12` in DMTool's selector does not perform the write. Saving persists **all current parameters**, including unrelated unsaved values.

## Known read-only example from our bench motor

Motor `0x12`, Master `0x22`: transmit CAN `7FF`, DLC 4, payload `12 00 33 0E`. Recorded response: CAN `022`, payload `12 00 33 0E 36 31 31 37`, where ASCII `36 31 31 37` represents firmware **6.1.1.7**. Parameter reads use **four bytes**, not an eight-byte padded request.

## Sources

- [Official DMTool manual](https://github.com/dmBots/motor-debugging-tool/blob/master/DMTool%E4%B8%8A%E4%BD%8D%E6%9C%BA%E8%BD%AF%E4%BB%B6%E8%AF%B4%E6%98%8E%E4%B9%A6.pdf), CAN parameter operations, printed page 17 and register tables.
- [Official Damiao motor SDK](https://github.com/dmBots/motor-sdk), parameter read/write/save and disable commands.
- [Our simplified script](../../tools/damiao/commission_motor.py) and simulated transaction tests.
