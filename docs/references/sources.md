# Sources and attribution

## Team-collected material

The English PDFs are team-collected translations and a commissioning guide; see the [manual index](../manuals/README.md). Findings were consolidated from the original Damiao tool README/research notes, motor ID table, and the two dated RDK handoffs. The DMTool Motor ID selection issue is a user-reported team observation.

The simplified bench script is derived from our existing `tools/damiao/commission_motor.py`. The verifier was moved from `tools/rdk_commissioning/` and renamed; its supplied robot model assets retain their [LICENSE](../../tools/motor_comms_verifier/web/public/model/LICENSE). Other upstream/third-party assets retain their original terms; this private repository does not relicense them.

## Official references

| Subject | Source |
|---|---|
| RoboParty documentation / assembly tutorial reference | [RoboParty Docs](https://roboparty.com/roboto_origin/doc) |
| Robot source aggregation | [roboto_origin](https://github.com/Roboparty/roboto_origin) |
| Hardware drawings and versioned manuals | [rpo_hardware](https://github.com/Roboparty/rpo_hardware) |
| Deployment/configuration | [roboparty_deploy](https://github.com/Roboparty/roboparty_deploy) |
| Robot board USB CAN firmware (separate from Damiao adapter) | [roboparty_firmware/roboto_usb2can](https://github.com/Roboparty/roboparty_firmware/tree/main/roboto_usb2can) |
| DMTool packages and installation | [motor-debugging-tool](https://github.com/dmBots/motor-debugging-tool) |
| DMTool manufacturer manual | [PDF](https://github.com/dmBots/motor-debugging-tool/blob/master/DMTool%E4%B8%8A%E4%BD%8D%E6%9C%BA%E8%BD%AF%E4%BB%B6%E8%AF%B4%E6%98%8E%E4%B9%A6.pdf) |
| Damiao adapter module documentation / firmware | [USB2CANFD](https://github.com/dmBots/dm-tools/tree/master/USB2CANFD) |
| Adapter SLCAN usage and bitrate mapping | [FLASHING.md](https://github.com/dmBots/dm-tools/blob/master/USB2CANFD/%E5%9B%BA%E4%BB%B6/socketcan/slcan%E5%9B%BA%E4%BB%B6/FLASHING.md) |
| Damiao official motor protocol examples | [motor-sdk](https://github.com/dmBots/motor-sdk) |
| Historical native adapter SDK | [dm-device-sdk](https://github.com/dmBots/dm-device-sdk) |
| Six-part assembly series | [BV16scUzWE2Z](https://www.bilibili.com/video/BV16scUzWE2Z/) |

Official online links were checked where available during organization on 2026-10-13. Remote contents can change; firmware hashes and video provenance are stored alongside the local assets. The six video episodes were identified from the assembly tutorial link embedded in the official RoboParty documentation and Bilibili's public episode metadata.

Firmware `.enc` files are manufacturer update packages. Manuals, model assets, and videos keep their original attribution and terms; private team storage does not confer permission to publish them publicly. Do not add a blanket license that claims ownership of third-party material.
