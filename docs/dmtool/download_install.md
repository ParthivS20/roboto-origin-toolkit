# DMTool download and installation

DMTool is Damiao's vendor motor/adapter application. Use it on the external computer with the Damiao adapter. It is independent of the RDK X5 verifier.

## Official download

- [Official DMTool packages](https://github.com/dmBots/motor-debugging-tool)
- [Manufacturer installation instructions](https://github.com/dmBots/motor-debugging-tool/blob/master/README.en.md)
- [Release history](https://github.com/dmBots/motor-debugging-tool/blob/master/CHANGELOG.en.md)
- [Manufacturer user manual (Chinese, PDF)](https://github.com/dmBots/motor-debugging-tool/blob/master/DMTool%E4%B8%8A%E4%BD%8D%E6%9C%BA%E8%BD%AF%E4%BB%B6%E8%AF%B4%E6%98%8E%E4%B9%A6.pdf)

As checked 2026-10-13, the public repository README describes version 2.1.6.7. Our locally collected installer is `DMTool-v2.1.8.1-arm64.app.zip`; that newer local filename is not proof that the public repository contains it. Record the version actually running when reporting issues.

## macOS

1. Use `MacOS/arm64` for Apple Silicon or `MacOS/x86_64` for Intel. Download the complete application bundle; a single file from inside `.app` is insufficient. The repository can be downloaded through GitHub's Code → Download ZIP.
2. Extract the download and place the complete `.app` in Applications or a team tools location, then open it. Vendor packages include their runtime frameworks.
3. If macOS blocks the verified vendor app, allow it through System Settings → Privacy & Security as described by the manufacturer.
4. Connect the standalone adapter using a USB data cable. Connect just one motor for ID commissioning. Choose the adapter and correct CAN rate; the robot uses classic CAN at 1 Mbps.
5. Switch to English using [the bottom CN/EN control](usage.md).

Close DMTool before starting the custom SLCAN commissioning script. Only one program should own the USB serial adapter at a time.

## Windows and Linux

Use the matching vendor package, not a Mac bundle. Windows currently lists an x86_64 executable. Linux lists an x86_64 AppImage and a separate arm64 package; follow that package's instructions. The official README documents USB permissions and Linux dependencies. Installing DMTool on the RDK is not required for our verifier.

## Adapter firmware matters

The normal/factory application uses Damiao's vendor protocol. Our bench script requires the [official SLCAN firmware](../adapters/firmware.md). Flashing SLCAN changes how the adapter communicates; use the supported vendor upgrade/recovery flow when switching back. Do not interpret successful device discovery as proof that motor CAN communication works.
