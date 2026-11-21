# Custom MicroPython Firmware Builder

A comprehensive template repository for building, packaging, cleaning, and flashing custom MicroPython firmware tailored for **ESP8266** and **ESP32** family modules.

## Features
- 🏗️ **Multi-chip support**: ESP8266 (1MB-16MB) and ESP32 family (ESP32, S2, S3, C3).
- 📦 **Frozen modules**: Custom Python code pre-compiled into optimized firmware bytecode (`opt=2`).
- ⚡ **Flash size configuration**: Easily specify flash size (1M, 2M, 4M, etc.) for ESP8266 builds.
- 🔍 **Board info tool**: Built-in command to query connected board details (Chip ID, MAC, Flash size).
- 🧹 **Clean builds**: Dedicated `clean` command that removes artifacts while preserving the heavy toolchain environment.
- 🔌 **Automated flashing**: Auto-detection of serial ports, bootloader mode waiting, single-session erase+write.
- 🐳 **Isolated environment**: All toolchains and dependencies live in a hidden `.build_env/` directory.
- 🚀 **Fast local builds**: Shallow clones and targeted submodules.

## Repository Structure
```text
.
├── .github/workflows/build.yml  # GitHub Actions workflow for cloud builds
├── custom_modules/              # Directory for your frozen Python modules
│   └── my_module.py             
├── custom_manifest.py           # MicroPython manifest defining what to freeze
├── run.py                       # Local build, clean, flash & info automation script
├── README.md                    # This file
└── .build_env/                  # (generated) Toolchain, venv, MicroPython/ESP-IDF clones
```

## Quick Start

### 1. Prepare the Environment
Run the setup command once. Specify the target chip (defaults to `esp8266`).
```bash
# For ESP8266 (downloads Xtensa LX106 toolchain)
python3 run.py setup --chip esp8266

# For ESP32 (downloads and installs ESP-IDF)
python3 run.py setup --chip esp32
```
> **Note:** The first run takes 5–15 minutes depending on your internet speed and chosen chip.

### 2. Build the Firmware
```bash
# Default build (ESP8266, 1MB flash)
python3 run.py build

# Specify flash size for ESP8266 (e.g., 4MB)
python3 run.py build --flash-size 4M

# Build for ESP32
python3 run.py build --chip esp32

# Disable ESP-NOW to save space (ESP8266 only)
python3 run.py build --no-espnow
```

### 3. Get Board Information
Connect your board and query its hardware details:
```bash
python3 run.py info
```
*Output example:*
```text
🔌 Device detected on port: /dev/ttyUSB0
Chip: ESP8266EX
MAC: aa:bb:cc:dd:ee:ff
Flash Size: 4MB
```

### 4. Flash the Firmware
```bash
python3 run.py flash
```
The script will wait for you to put the device into bootloader mode (Hold GPIO0 -> Press Reset -> Release GPIO0).

### 5. Clean Build Artifacts
```bash
python3 run.py clean
```

## Command Reference

| Command | Description |
|---------|-------------|
| `setup [--chip CHIP]` | Prepare the build environment for the specified chip. |
| `build [--chip CHIP] [--flash-size SIZE]` | Compile the firmware. |
| `clean` | Remove build artifacts (preserves toolchains). |
| `flash [--chip CHIP] [-p PORT]` | Flash firmware to a connected device. |
| `info [-p PORT]` | Query hardware information from a connected device. |

## Optimizing for 1MB Flash (ESP8266)
If you encounter `region 'irom0_0_seg' overflowed`, try:
1. Build with `--no-espnow` (saves ~10 KB).
2. Disable Berkeley DB: `--make-var MICROPY_PY_BTREE=0`.
3. Keep `custom_manifest.py` minimal.

## License
This project is licensed under the **Mozilla Public License 2.0 (MPL-2.0)**.
MicroPython itself is licensed under the MIT License.
