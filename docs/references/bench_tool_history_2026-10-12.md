# Historical bench tool development notes

Archived from the original tool README. SDK/plugin/zero options described below were removed from the toolkit script on 2026-10-13. Use [the current tool README](../../tools/damiao/README.md) for runnable instructions. This document preserves the recorded experiments and evidence only.

# Damiao motor commissioning

`commission_motor.py` changes the motor command ID (slave ID), its feedback CAN
ID (Master ID). With `--zero`, it also sets the **current physical pose** as zero.
By default the existing zero is preserved. It saves current
parameters to motor flash. It does not flash firmware, enable torque, move the
motor to a physical origin, or perform encoder calibration.

Connect exactly one motor to the USB2FDCAN adapter and close DMTool before running.
When using `--zero`, position the motor at the desired zero pose first. Keep motor power on throughout
the operation. Do not use this on a robot joint that needs torque to hold its pose:
the script disables the motor. It uses classic CAN at 1 Mbps, channel 0 by default.

## Run on this Apple Silicon Mac

The default transport is now Python CAN **SLCAN**, for the flashed Damiao SLCAN
firmware. Activate `.venv` and install `python -m pip install -r requirements.txt`.
It selects Damiao **S5 = 1 Mbps**, rather than generic SLCAN S8.
The optional `--transport sdk` uses the included native SDK in `dlls/` without pip dependencies.

```sh
cd '/Users/parthiv/Documents/classes/ASE 381P Human Centered Robotics/tools/damiao'

# Read current IDs, firmware and bootloader versions without writing motor settings:
python3 commission_motor.py --current-id 0x12 --slave-id 0x12 --check

# Set IDs, verify, and save; preserve the existing zero:
python3 commission_motor.py --current-id 0x12 --slave-id 0x12

# A fresh factory motor at ID 1; also zero its current pose:
python3 commission_motor.py --current-id 1 --slave-id 0x12 --zero
```

`0x12` means hexadecimal 12 (decimal 18). Plain `12` means decimal 12.
Master ID is the feedback-message CAN ID, not a USB adapter address.
The current Master ID is read automatically; supply the current motor ID explicitly.

Before writing, the script reads firmware (register `0x0E`), bootloader (`0x25`),
motor ID and Master ID. These read requests check that the motor responds: the
payload motor ID must match `--current-id`, while the CAN response ID must match
the motor's current Master ID. Version numbers do not uniquely identify a motor.

It verifies each changed ID by register readback and checks the save acknowledgement.
After saving it repeats the connection check using the new motor and Master IDs
and verifies that the firmware version is unchanged. Bootloader reads are informational:
a successful read prints the value; a failed read prints ERROR and commissioning
continues. Bootloader values do not determine whether commissioning passes. Versions
are printed with raw bytes; unrecognized encodings are labeled explicitly.
With `--zero`, it also verifies the zeroed position using PMAX-scaled feedback. Power-cycle afterward and use `--check`
to verify ID persistence. Zero persistence needs a feedback-position check after
power cycling as well; the script cannot physically power-cycle the motor.
Saving writes **all current parameters**, including pre-existing unsaved values.

If a step fails, the script stops without claiming completion. Earlier ID changes
may already be active even if saving failed. Inspect its TX/RX log and reconnect
using the last acknowledged ID. Do not blindly rerun with the original ID.
One physical motor is a prerequisite: software cannot reliably detect two motors
sharing the same ID. The destination-ID probe catches another responding ID but
does not establish that the bus has only one motor.

For another platform, pass `--library /path/to/official/libdm_device.so` (or DLL).
That platform has not been verified here.

## Sources and validation

- [Official Damiao Device SDK](https://github.com/dmBots/dm-device-sdk), C API 1.1.0.
  Bundled binary: `C&C++/lib/v1.1.0/macos/arm64/libdm_device.dylib`.
- [ID registers and save protocol](https://damiao.enactic.ai/en/products/hardware/dm-j4340p-2ec-v1.0/).
- [Official motor SDK: disable and set-zero commands](https://github.com/dmBots/motor-sdk/blob/main/Python%E4%BE%8B%E7%A8%8B/u2can/DM_CAN.py).

The Mac backend loads successfully. Run `python3 -m unittest discover -s . -v`
for simulated transactions and failure checks. Live motor commissioning has not
been performed with this script.

## Auto-detect the current ID

```sh
python3 commission_motor.py --auto-detect --slave-id 0x12
```

This sends firmware-register read requests for all possible motor IDs 0x000–0x7FE
and collects replies for one second. It requires exactly one responding
motor/Master pair, prints its ID and firmware, then waits for Enter before any
motor setting changes. Ctrl+C or end-of-input cancels. Existing firmware/ID
checks and readbacks still run after confirmation. Add `--zero` only when you
want to zero the current physical pose. Use `--check` for read-only detection
and checks without the write confirmation prompt.

`--auto-detect` and `--current-id` are mutually exclusive. No replies, multiple
responders, a send failure, or an incomplete scan stops the operation. The
one-second scan cannot prove that two physical motors with identical motor and
Master IDs are absent, or detect a silent/unpowered motor. Connect exactly one
physical motor even when using detection. Scan timing has been simulated;
live adapter performance has not been verified.

## USB startup recovery (verified 2026-10-12)

The supplied Damiao macOS SDK can discover/open this DM_USB2FDCAN adapter while
its USB control commands fail. This was reproduced in both Python and a minimal
native C++ SDK program with the motor disconnected. Failed sessions sometimes
report successful configuration reads containing only zeros. The SDK binary
matches the official arm64 1.1.0 download; successful sessions identify adapter
firmware app v1.0.0.5 and classic CAN channel 0 at 1 Mbps.

The script now retries **adapter initialization only**, reopening USB up to five
attempts and rejecting empty/invalid configuration replies. Three consecutive
live adapter-only runs succeeded after one reopen each. This is a recovery for
the vendor transport failure, not a change to the vendor binary. Motor writes
are never automatically retried. Native `libusb_transfer_cancelled or error`
lines also appear during normal SDK shutdown when its background transfers are
cancelled; they alone do not indicate a motor failure.

The owner's DMTool capture confirms motor ID 0x12 (18), Master 0x22 (34),
CAN bitrate register 0x23 = 4 (1 Mbps), and FW 6.1.1.7. Successful parameter
requests in that capture use DLC 4, e.g. CAN 0x7FF: `12 00 33 0E`.
The script now matches that four-byte read format; writes still carry eight
bytes. A live SDK read using the corrected format still timed out, so native
USB motor communication remains unresolved; the captured DMTool reply is not
evidence that the script's transport is working.

## python-can-damiao transport (optional legacy path)

```sh
source .venv/bin/activate
python -m pip install -r requirements.txt
python commission_motor.py --current-id 0x12 --slave-id 0x12 --check
```

For this optional path add `--transport python-can-damiao`; it is not used with
the flashed SLCAN firmware. One matching USB serial adapter is detected automatically. Override with
`--port /dev/cu.usbmodem31104` if necessary; the port name may change. It uses
921600 serial baud and 1 Mbps CAN. Close DMTool before opening the port.
The existing ID writes/save, --zero, and --auto-detect use the selected transport.
The default backend does not load libdm_device.dylib or use its USB reopen loop.

For plugin 0.1.0, the wrapper preserves short CAN requests in bytes D0–D3 while
keeping DLC 4 (the plugin otherwise prepends padding), and corrects the byte
order of standard receive IDs when the plugin produces an out-of-range ID.
No motion/enable command was sent while testing. The live read-only firmware
request still timed out; using this backend is not a claim of working hardware
communication. Native SDK mode remains available explicitly with --transport sdk.

## Working SLCAN commissioning (verified live)

```sh
source .venv/bin/activate
python commission_motor.py --auto-detect --slave-id 0x12
```

The script scans firmware requests for one second, prints the detected motor ID,
and requires Enter before changing IDs/saving. Add --zero only to zero the current
pose. `--check` omits the confirmation because it sends reads only:

```sh
python commission_motor.py --auto-detect --slave-id 0x12 --check
```

Live read-only auto-detection succeeded after the adapter was flashed with SLCAN:
found motor 0x12 (18), Master 0x22 (34), firmware 6.1.1.7, bootloader 0.0.0.0.
Both full ID-register readbacks succeeded. The serial port was automatically
selected as /dev/cu.usbmodem11104; override with --port if necessary. No native
Damiao dylib or python-can-damiao binary protocol is used by the default path.
No ID writes, zeroing or saves were performed during this live verification.

## Provide only the target motor ID

```sh
python commission_motor.py --motor-id 0x12
```

Auto-detection is now the default when --current-id is omitted. The Master ID is
always derived as target motor ID + 0x10, so --master-id is no longer accepted.
--slave-id remains an alias for --motor-id. Use 0x-prefixed hexadecimal to avoid
ambiguity; plain numbers retain decimal interpretation. For target 0x12, Master
is 0x22. Enter confirmation, optional --zero and read-only --check still apply.
