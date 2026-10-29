# Damiao single-channel USB2CAN adapter firmware

Original manufacturer `.enc` update packages for the standalone adapter used with an external computer. These are not motor firmware and are not for the RoboParty robot board.

Read [firmware selection and flashing](../../docs/adapters/firmware.md) before use. `dm_usb2fdcan_slcan_1002.enc` is required by our SLCAN-only commissioning script. `gsusb_1003` is the Linux USB SocketCAN alternative; `app_1006` and historical `app_1005` use the vendor/factory protocol.

[manifest.json](manifest.json) contains direct official download URLs and SHA-256 hashes. To verify on macOS, run `shasum -a 256 -c SHA256SUMS` from this directory; Linux can use `sha256sum -c SHA256SUMS`.

Original vendor terms apply. Local hashes verify file identity, not independent manufacturer authenticity. Keep the exact hardware revision and recovery workflow in mind before flashing.
