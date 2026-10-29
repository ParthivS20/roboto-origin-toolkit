# Roboto Origin motor IDs

Physical branch order, from the top/root to the bottom/end of each limb. Left and right refer to the robot’s own sides.

**Motor / Slave ID** is the command CAN ID. **Master ID** is the feedback CAN ID. The deployment uses Master = Slave + 16 decimal (0x10).

These are the intended assignments from the supplied commissioning manual and deployment configuration; verify physical motor labels before programming.

## Left leg — can0

| Order | Motor / joint | Motor model | Slave ID (decimal) | Slave ID (hex) | Master ID (decimal) | Master ID (hex) |
|---|---|---|---|---|---|---|
| 1 | Left hip yaw | DM-J10010L-2EC | 1 | 0x01 | 17 | 0x11 |
| 2 | Left hip roll | DM-J10010L-2EC | 2 | 0x02 | 18 | 0x12 |
| 3 | Left hip pitch | DM-J10010L-2EC | 3 | 0x03 | 19 | 0x13 |
| 4 | Left knee | DM-J10010L-2EC | 4 | 0x04 | 20 | 0x14 |
| 5 | Left ankle upper | DM-J4340P-2EC | 5 | 0x05 | 21 | 0x15 |
| 6 | Left ankle lower | DM-J4340P-2EC | 6 | 0x06 | 22 | 0x16 |

## Waist · right leg — can1

| Order | Motor / joint | Motor model | Slave ID (decimal) | Slave ID (hex) | Master ID (decimal) | Master ID (hex) |
|---|---|---|---|---|---|---|
| 1 | Waist yaw | DM-J10010L-2EC | 13 | 0x0D | 29 | 0x1D |
| 2 | Right hip yaw | DM-J10010L-2EC | 7 | 0x07 | 23 | 0x17 |
| 3 | Right hip roll | DM-J10010L-2EC | 8 | 0x08 | 24 | 0x18 |
| 4 | Right hip pitch | DM-J10010L-2EC | 9 | 0x09 | 25 | 0x19 |
| 5 | Right knee | DM-J10010L-2EC | 10 | 0x0A | 26 | 0x1A |
| 6 | Right ankle upper | DM-J4340P-2EC | 11 | 0x0B | 27 | 0x1B |
| 7 | Right ankle lower | DM-J4340P-2EC | 12 | 0x0C | 28 | 0x1C |

## Left arm — can2

| Order | Motor / joint | Motor model | Slave ID (decimal) | Slave ID (hex) | Master ID (decimal) | Master ID (hex) |
|---|---|---|---|---|---|---|
| 1 | Left shoulder pitch | DM-J4340P-2EC | 14 | 0x0E | 30 | 0x1E |
| 2 | Left shoulder roll | DM-J4340P-2EC | 15 | 0x0F | 31 | 0x1F |
| 3 | Left shoulder yaw | DM-J4340P-2EC | 16 | 0x10 | 32 | 0x20 |
| 4 | Left elbow | DM-J4340P-2EC | 17 | 0x11 | 33 | 0x21 |
| 5 | Left distal arm rotation | DM-J4340P-2EC | 18 | 0x12 | 34 | 0x22 |

## Right arm — can3

| Order | Motor / joint | Motor model | Slave ID (decimal) | Slave ID (hex) | Master ID (decimal) | Master ID (hex) |
|---|---|---|---|---|---|---|
| 1 | Right shoulder pitch | DM-J4340P-2EC | 19 | 0x13 | 35 | 0x23 |
| 2 | Right shoulder roll | DM-J4340P-2EC | 20 | 0x14 | 36 | 0x24 |
| 3 | Right shoulder yaw | DM-J4340P-2EC | 21 | 0x15 | 37 | 0x25 |
| 4 | Right elbow | DM-J4340P-2EC | 22 | 0x16 | 38 | 0x26 |
| 5 | Right distal arm rotation | DM-J4340P-2EC | 23 | 0x17 | 39 | 0x27 |

## Notes

- The right-leg branch starts at **waist motor 13**, then continues through motors **7–12**.
- Upper/lower ankle entries identify the two actuators in the coupled ankle linkage, rather than independent pitch/roll joints.
- There are **23 motors**: 9 DM-J10010L-2EC and 14 DM-J4340P-2EC.
- In the commissioning script, plain `12` means decimal 12; `0x12` means decimal 18.

Sources: supplied [RDK X5 commissioning manual](../manuals/roboto_origin_rdk_x5_commissioning_manual_en.pdf), sections B7/B8/D4; `roboto_origin/modules/roboparty_deploy/src/inference/robots/rpo/robot.yaml`.
