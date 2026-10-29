# Team repository instructions

This repository contains team findings, third-party reference material, and two different CAN workflows. Read README.md and the relevant tool README before changing code or procedures.

## Tools and hardware

- `tools/damiao/commission_motor.py` runs on an external computer using the standalone Damiao USB2CAN adapter with SLCAN firmware. Keep it SLCAN-only. Do not reintroduce native SDKs, python-can-damiao, zeroing, enabling, or motion features.
- `tools/motor_comms_verifier/` runs its Python backend on the RDK X5 using Linux SocketCAN can0–can3. Its frontend may be viewed remotely. Keep its Python backend standard-library-only and preserve the explicit Start/Stop flow, heartbeat cleanup, fault cancellation, and one enabled motor per branch.
- Do not confuse the standalone Damiao adapter's firmware with the robot board's firmware. A hardware action requires an explicit user request covering that action; organizing files or running tests does not authorize connecting to or writing real hardware.
- The commissioning script writes IDs and saves parameters; the verifier can enable/disable motors. Use mocked transports or demo mode for development. Never test changes on real motors as a side effect of a software test.

## Documentation

- Put findings in the existing docs subfolders and link new pages from README.md. Keep the DMTool current-ID/target-ID distinction and Master = Motor + 0x10 rule explicit.
- Separate recorded observations, manufacturer instructions, and untested suggestions. Include dates, raw evidence, model/firmware versions, and limitations where known. Dated setup notes describe a historical state; recheck before treating them as current.
- Preserve third-party filenames, licenses, and source links. Firmware packages are adapter application update files, not motor firmware or full device backups. Recalculate SHA256SUMS and update provenance when replacing binary assets.
- Keep distinct English translation editions labeled. Do not silently merge or overwrite manuals.
- Preserve video episode order, source URLs, checksums, and metadata. Do not commit credentials, browser cookies, transient download URLs, dependencies, caches, or local virtual environments.

## Verification

Run the relevant existing unittest suite after code changes. For bench changes: `python3 -m unittest discover -s tools/tests -v`. For verifier changes: `python3 -m unittest discover -s tools/motor_comms_verifier -v`.

When modifying the frontend, run `npm ci` and `npm run build` inside its web directory, and include the matching web/dist output because the RDK should not require Node. Rebuild the runtime archive when included runtime files change. Verify relative documentation links and firmware/media checksums before reporting the repository complete.
