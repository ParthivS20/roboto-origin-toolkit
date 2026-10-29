# CAN and IMU bring-up notes

These notes describe this robot's observed setup through 27 October 2026. Recheck the active configuration and wiring before use.

## CAN scheduling history

On 19 October, can0 motor feedback was present in independent CAN captures while the SDK reported motors offline. The can0 receive thread appeared runnable but did not process feedback for about 168 ms. CPU0 also carried interrupt traffic; scheduling starvation was the leading explanation, not a proven identification of the competing task.

Moving only can0 receive and transmit threads from CPU0 to CPU6 produced five successful fresh processes and eight starts in the subsequent comparison, although the trials were not all identical. A local SDK patch then made can0→CPU6 persistent; can1, can2 and can3 remained on CPUs 1, 2 and 3. The patched build's affinity was checked without motor enable; it was not itself validated by a powered test at that time.

The later motor SDK defaults **all** CAN receive and transmit threads to CPU6, configurable with `ROBOT_CAN_CPU`. On 27 October the separately staged release reported eight CAN threads on CPU6 during an idle launch. This is a different allocation from the local patch, and powered all-bus testing and feedback-latency checks remain outstanding.

## CAN termination

The team reports that the power board has 120 Ω termination, while the limbs do not. Each physical CAN bus needs termination at its two ends: check the actual topology and add a 120 Ω resistor across CAN-H and CAN-L at the far end of each unterminated limb bus as appropriate. Do not add resistors blindly where another endpoint is already terminated. With power off and isolated from other paths, approximately 60 Ω across CAN-H and CAN-L is consistent with two 120 Ω terminators in parallel; verify each branch and record measurements. Installation and measurements are still to be verified.

## IMU baud

The supplied HIPNUC IMU was observed at 115200 baud while the Roboto Origin configuration expected 921600. On 14 October the robot configuration was temporarily changed to 115200 to obtain valid data. On 27 October the sensor was changed to 921600 using `SERIALCONFIG 921600` and `SAVECONFIG`, and the robot configuration was updated to match. Live data was verified at 921600; persistence after an IMU power cycle remains unverified. See the [IMU record](../commissioning/imu_2026-10-14.md) for model, evidence and limitations.

## Adapter firmware

The external Damiao adapter needs SLCAN for the bench script; factory firmware uses the vendor protocol. The robot board is different hardware. Follow the [firmware guide](../adapters/firmware.md) for package selection, flashing and recovery; do not flash the standalone adapter packages onto the robot board.
