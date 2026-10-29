# Findings and evidence

Organized 2026-10-13 from the collected tool READMEs, adapter research, manuals, and RDK handoffs. Dates below identify recorded observations, not new hardware tests.

| Finding | Evidence / status |
|---|---|
| DMTool's selected Motor ID is an address/search target, not an ID programming operation | Team report during repository organization: selecting a nonexistent new ID prevents the motor from being found. Keep the selector and Parameter Settings addressing ID at the current motor ID until the write succeeds. |
| CAN-mode ID editing needs the raw CAN path | Manufacturer manual printed page 17: ordinary CAN-mode ID controls are intentionally restricted; use serial ID editing or CAN analyzer register writes followed by save. |
| Standalone adapter originally reported app v1.0.0.5 | Adapter research 2026-10-12; VID:PID 34b7:6877. A v1.0.0.5 package is retained for recovery, not as a full device memory backup. |
| Native macOS SDK discovery/open did not guarantee working communication | Official arm64 SDK 1.1.0 was verified; initialization/control failures and zeroed configuration replies occurred even without a motor. Reopening sometimes recovered initialization; motor reads still timed out. |
| Community python-can-damiao did not establish working communication | Legacy plugin 0.1.0 needed short-message and ID-byte-order workarounds; live read-only motor request still timed out. This transport and native SDK are excluded from the toolkit script. |
| Parameter firmware reads need DLC 4 | Recorded DMTool TX `7FF#1200330E`; RX CAN 022 payload `12 00 33 0E 36 31 31 37`. The four version bytes are ASCII 6.1.1.7. |
| Official Damiao SLCAN mapping differs from generic SLCAN | Manufacturer FLASHING.md: S5 is 1 Mbps classic CAN; S8 is 5 Mbps CAN FD. The bench script explicitly sets S5. |
| SLCAN read-only motor discovery worked live after flashing | Existing tool README records motor 0x12 (18), Master 0x22 (34), FW 6.1.1.7, bootloader 0.0.0.0, and both ID-register readbacks. No live ID changes, zeroing, or saves were performed in that verification. |
| Software assignments must match physical joints | Intended left elbow is ID 17/Master 33; ID 18/Master 34 is left distal rotation. A responding bench ID 18 alone does not identify its installed joint. |
| Two CAN tool paths have different hosts and transports | User clarified: bench commissioning uses external computer + Damiao USB2CAN; motor_comms_verifier runs on RDK X5 + board SocketCAN. |
| RDK software installation/build was recorded complete | Connected-robot handoff dated 2026-10-08: RT kernel, ROS Humble, deployment build, SDK imports, and real ONNX model checked. Hardware was disconnected; full-robot feedback/commissioning was still pending. |
| Feedback alone has limits | Low motor-ID nibble overlaps status on some firmware and does not reliably detect duplicate IDs. A verifier response cannot independently prove LED state, physical disable, or safe motion. |

## Open verification work

- ID write/save and persistence on actual motors using the simplified script.
- Exact standalone adapter hardware revision compatibility before flashing a replacement package. gs_usb is bundled as an official alternative, but no successful gs_usb flash/test was recorded for this standalone adapter.
- Current RDK USB-to-physical-branch mapping, all 23 fresh replies, actual motor variants, E-stop behavior, calibration, and supported motion tests.
- The manuals' unresolved battery/board input-voltage discrepancy noted in the handoff. Resolve against the actual installed hardware before applying motor power.

Do not infer hardware results from unit tests or historical handoffs. See [RDK status](../rdk_x5/README.md) and [sources](../references/sources.md).
