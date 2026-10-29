# Custom interrupt policy

The robot's existing RPO `interrupt` policy is the walking and balance policy used with the custom controller changes. The 19 October 2026 upgrade preserved the controller axis mapping, D-pad-left manual-arm toggle, LB/RB arm selection, both shoulder axes and their ranges and speed, and malformed joystick-message guard. The RPO interrupt configuration and ONNX model were byte-identical to the previously installed revision; the controller changes do not constitute a newly trained policy.

The recorded deployment revision was `e4a1f064aa75b628f66eed9b10e891954bc9e0dc`, with inference `798f254a1754daff0a964a0e2db58e1c5a5450f7` and motors `45eac3ff3dc860e3bd688c1e62a3c5368166849a`. That build retained the robot's then-current IMU baud of 115200 and waist offset 0; the IMU was subsequently changed to 921600 as described in the [bring-up notes](can_imu_bringup.md). Use the actual calibrated configuration, not a historical copy.

The upgrade included a local can0 CPU6 affinity patch. Its idle CPU masks were verified without motor enable; earlier powered comparisons used a different diagnostic build. Do not infer that the upgraded build passed a powered test from those comparisons. See the [CAN scheduling history](can_imu_bringup.md).

The custom deployment source and executable are not included in this toolkit. Preserve the working RDK installation and backups, and verify the current software and controller mapping before operating the robot. Support the robot and keep the E-stop accessible for physical tests.
