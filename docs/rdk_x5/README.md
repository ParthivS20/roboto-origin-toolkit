# RDK X5 setup and status

The RDK X5 owns the robot's four CAN buses through its board connection. [motor_comms_verifier](../../tools/motor_comms_verifier/README.md) runs here; a browser on the external computer views the dashboard. The standalone Damiao USB adapter is for separate bench ID commissioning.

## Recorded installation state (2026-10-08)

The recorded setup notes describe Ubuntu 22.04.5 aarch64, ROS 2 Humble, kernel `6.1.83-rt28` with PREEMPT_RT, RT priority 98/unlimited memlock, a successful four-package deployment build, SDK imports, and a real ONNX policy with input `[1,780]` / output `[1,23]`. The checkout was deployment `a8a0f15`, inference `ac448b1`, motors `118e569`, IMU `7a6e6d2`, camera `7434a8d`, create_ap `637a769`.

At that time the RDK was off the robot with Ethernet attached; USB topology/udev rules, fresh motor feedback, IMU/gamepad verification, physical calibration, and motion remained to be checked. Re-audit current state rather than reinstalling or assuming this historical state is current.

## Recorded access

- Direct Ethernet: RDK `192.168.127.10`, external computer `192.168.127.1`; login `sunrise`.
- Robot hotspot: SSID `roboto_origin`, RDK `10.42.0.1`.
- The board had no Internet over the direct cable and no RTC; its clock required correction before HTTPS downloads/logging. Check the current network and clock.

These are recorded addresses, not guaranteed current values. Inspect `ip -br address` on the board if unreachable.

## Next steps

1. Recheck OS/kernel, current network addresses, deployment configuration, and actual USB interfaces.
2. Map the four CAN interfaces to the physical branches and configure 1 Mbps.
3. Confirm bench-assigned IDs and Master IDs against the [motor table](../commissioning/motor_ids.md).
4. Use [motor_comms_verifier](../../tools/motor_comms_verifier/README.md) on the RDK with the robot supported and E-stop accessible.
5. Follow the [RDK commissioning manual](../manuals/roboto_origin_rdk_x5_commissioning_manual_en.pdf) for the separate calibration and motion stages.

Organizing this repository did not connect to or modify the RDK, power motors, or verify a walking robot.
