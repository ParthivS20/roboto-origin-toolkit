# Adapter firmware: factory, SLCAN, and gs_usb

## Two hardware paths

**External computer → standalone Damiao USB2CAN / DM-USB2FDCAN → one motor:** our `commission_motor.py` requires the Damiao **SLCAN firmware**. Factory firmware exposes the vendor protocol, which our simplified script does not support. Flash SLCAN before using that custom bench tool.

**RDK X5 → robot board's four CAN channels → robot motors:** `motor_comms_verifier` runs on the RDK's **Linux SocketCAN** interfaces can0–can3. Keep the robot board's matching working gs_usb/SocketCAN firmware. The standalone Damiao `.enc` packages below are not updates for the robot's board. The verifier does not directly open a USB serial SLCAN port.

## Included standalone Damiao packages

These packages are for the vendor's **single-channel USB2CANFD** family, not USB2CANFD_Dual, generic CANable boards, or the RoboParty robot board.

| Included package | Role | Use / recorded status |
|---|---|---|
| `dm_usb2fdcan_slcan_1002.enc` | SLCAN 1.0.0.2: serial CAN command interface | **Required for the external-computer commissioning script.** Live read-only detection/readbacks succeeded after flashing SLCAN. |
| `dm_usb2canfd_gsusb_1003.enc` | gs_usb 1.0.0.3: USB CAN protocol usable through Linux native SocketCAN | Official alternative for compatible standalone Damiao hardware. No flash/communication validation recorded for our standalone adapter. Not required for our SLCAN script. |
| `dm_usb2canfd_app_1006.enc` | Factory/vendor 1.0.0.6 | Factory package available in the vendor repository at collection time. Uses the vendor application/SDK protocol, not the custom script's SLCAN transport. |
| `dm_usb2canfd_app_1005.enc` | Factory/vendor 1.0.0.5 | Historical recovery candidate matching our adapter's originally observed version. Not a dump of this device's full flash or bootloader. |

Packages are in [firmware/damiao_usb2can](../../firmware/damiao_usb2can/README.md); original vendor filenames are preserved. [manifest.json](../../firmware/damiao_usb2can/manifest.json) records direct sources, sizes, and SHA-256 hashes. Hashes were locally calculated, not independently authenticated vendor signatures. `.enc` files update **adapter firmware**, not motor firmware.

## Official documentation and direct downloads

- [Single-channel adapter documentation and module manual](https://github.com/dmBots/dm-tools/tree/master/USB2CANFD)
- [Firmware directory](https://github.com/dmBots/dm-tools/tree/master/USB2CANFD/%E5%9B%BA%E4%BB%B6)
- [Official SLCAN flashing/use instructions](https://github.com/dmBots/dm-tools/blob/master/USB2CANFD/%E5%9B%BA%E4%BB%B6/socketcan/slcan%E5%9B%BA%E4%BB%B6/FLASHING.md)
- [Vendor SDK compatibility changes](https://github.com/dmBots/dm-tools/blob/master/USB2CANFD/SDK/UPDATE.md)
- [USB2CANFD-series upgrade utility](https://github.com/dmBots/dm-tools/tree/master/USB2CANFD%E9%80%9A%E7%94%A8%E5%8D%87%E7%BA%A7%E5%B7%A5%E5%85%B7)

Direct manufacturer package downloads:

- [dm_usb2canfd_app_1005.enc](https://raw.githubusercontent.com/dmBots/dm-tools/master/USB2CANFD/%E5%9B%BA%E4%BB%B6/%E5%87%BA%E5%8E%82%E5%9B%BA%E4%BB%B6/%E5%8E%86%E5%8F%B2%E5%9B%BA%E4%BB%B6/dm_usb2canfd_app_1005.enc)
- [dm_usb2canfd_app_1006.enc](https://raw.githubusercontent.com/dmBots/dm-tools/master/USB2CANFD/%E5%9B%BA%E4%BB%B6/%E5%87%BA%E5%8E%82%E5%9B%BA%E4%BB%B6/dm_usb2canfd_app_1006.enc)
- [dm_usb2canfd_gsusb_1003.enc](https://raw.githubusercontent.com/dmBots/dm-tools/master/USB2CANFD/%E5%9B%BA%E4%BB%B6/socketcan/gsusb%E5%85%8D%E9%A9%B1%E5%9B%BA%E4%BB%B6/dm_usb2canfd_gsusb_1003.enc)
- [dm_usb2fdcan_slcan_1002.enc](https://raw.githubusercontent.com/dmBots/dm-tools/master/USB2CANFD/%E5%9B%BA%E4%BB%B6/socketcan/slcan%E5%9B%BA%E4%BB%B6/dm_usb2fdcan_slcan_1002.enc)

## Flash the standalone adapter to SLCAN

1. Identify the exact adapter model/revision and choose the matching **single-channel** package. Disconnect the motor during adapter flashing and keep the factory recovery packages available.
2. Open the compatible manufacturer application, connect/open the adapter, and use **F9 — FDCAN module firmware upgrade**. Select `dm_usb2fdcan_slcan_1002.enc`. Do not use the motor firmware-upgrade controls.
3. Start the adapter update and wait for a confirmed success and restart. Reconnect the adapter if required by the vendor flow, then check its new serial enumeration. A missing/changed port name after flashing does not establish firmware failure by itself.
4. Close DMTool before opening the adapter with the Python script. Install [tools/requirements.txt](../../tools/requirements.txt), then use read-only `--check` first.
5. To restore the vendor protocol, use the manufacturer-supported upgrade utility and select the matching factory package, normally `dm_usb2canfd_app_1006.enc`. The manufacturer says factory and SLCAN firmware can be switched by reflashing. The precise recovery procedure from SLCAN and macOS compatibility of the separate universal upgrader have not been verified here; consult the module manual and utility before proceeding. Confirm vendor-tool communication after the update.

No adapter was flashed during repository organization. The recorded earlier SLCAN success was read-only motor verification; ID writes/save still need their own live validation.

## Damiao-specific SLCAN bitrate mapping

| Command | CAN bitrate | Format |
|---|---|---|
| S0 | 100 kbps | classic CAN |
| S1 | 125 kbps | classic CAN |
| S2 | 200 kbps | classic CAN |
| S3 | 250 kbps | classic CAN |
| S4 | 500 kbps | classic CAN |
| **S5** | **1 Mbps** | **classic CAN; our motors** |
| S6 | 2 Mbps | CAN FD |
| S7 | 4 Mbps | CAN FD |
| S8 | 5 Mbps | CAN FD |

This differs from conventional SLCAN indexing. Our bench script uses serial baud 921600 and explicitly sends **S5**; letting generic python-can choose S8 for 1 Mbps would configure the wrong Damiao bitrate.

## Optional Linux serial-to-SocketCAN bridge

The vendor documents `slcand` as a way to expose a SLCAN serial adapter to Linux tools. For a correctly identified port at **1 Mbps**, the example is:

```sh
sudo slcand -o -c -s5 /dev/ttyACM0 slcan0
sudo ip link set slcan0 up
candump slcan0
# In a second terminal, read firmware for motor 0x12:
cansend slcan0 7FF#1200330E
```

This optional bridge was not tested on our adapter/RDK and is not the robot's established four-bus connection. Do not have the Python bench script and slcand own the same serial port concurrently. Do not substitute it for the verifier's verified can0–can3 branch mapping.

## Robot board firmware

The RoboParty board has its own [roboto_usb2can firmware](https://github.com/Roboparty/roboparty_firmware/tree/main/roboto_usb2can), based on STM32G431 and gs_usb/candleLight, with native Linux SocketCAN support. The RDK handoff expects four USB interfaces with VID:PID `1d50:606f`; determine actual USB-to-branch mapping before assigning persistent interface names. These are different hardware/firmware assets from Damiao's standalone adapter packages.

See [historical adapter investigation](research_2026-10-12.md) for failed SDK/plugin experiments and original evidence, and [current findings](../commissioning/findings.md) for the later successful SLCAN result.
