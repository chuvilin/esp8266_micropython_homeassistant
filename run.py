#!/usr/bin/env python3
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""
A local build automation script for compiling, packaging, cleaning, flashing,
and querying custom MicroPython firmware for ESP8266 and ESP32 family chips.
"""
import os
import sys
import time
import subprocess
import urllib.request
import tarfile
import shutil
import argparse
import re
from pathlib import Path

# ==============================================================================
# Configuration
# ==============================================================================
BUILD_ENV_DIR = Path(".build_env")
VENV_DIR = BUILD_ENV_DIR / "venv"
VENV_PIP = VENV_DIR / "bin" / "pip"
VENV_ESPTOOL = VENV_DIR / "bin" / "esptool"
VENV_PYTHON = VENV_DIR / "bin" / "python"
MPY_DIR = BUILD_ENV_DIR / "micropython"
ESP_IDF_DIR = BUILD_ENV_DIR / "esp-idf"

# ESP8266 specific
XTENSA_URL = "https://micropython.org/resources/xtensa-lx106-elf-standalone.tar.gz"
XTENSA_DIR = BUILD_ENV_DIR / "xtensa-lx106-elf"

# ESP32 specific
ESP_IDF_REPO = "https://github.com/espressif/esp-idf.git"
ESP_IDF_TAG = "v5.1.2"  # Stable release for ESP32 builds

# Paths injected into the MicroPython source tree during build
INJECTED_CUSTOM_MODULES = None
INJECTED_MANIFEST = None

# Default flash size matching official MicroPython ESP8266 GENERIC builds
ESP8266_DEFAULT_FLASH_SIZE = "2M"


def get_port_dir(chip):
    return MPY_DIR / "ports" / chip


def get_build_dir(chip, flash_size=ESP8266_DEFAULT_FLASH_SIZE):
    if chip == "esp8266":
        # ESP8266 build directory does not include flash size in its name.
        # Flash size is passed via FLASH_SIZE make variable.
        return get_port_dir(chip) / "build-ESP8266_GENERIC"
    elif chip.startswith("esp32"):
        board = chip.upper().replace("ESP32", "ESP32")
        if chip == "esp32":
            board = "ESP32_GENERIC"
        elif chip == "esp32s2":
            board = "ESP32_GENERIC_S2"
        elif chip == "esp32s3":
            board = "ESP32_GENERIC_S3"
        elif chip == "esp32c3":
            board = "ESP32_GENERIC_C3"
        return get_port_dir("esp32") / f"build-{board}"
    return None


def get_default_firmware(chip, flash_size=ESP8266_DEFAULT_FLASH_SIZE):
    build_dir = get_build_dir(chip, flash_size)
    if build_dir:
        return build_dir / "firmware.bin"
    return None


def run_cmd(cmd, cwd=None, env=None, check=True):
    print(f"\n>>> Executing: {' '.join(str(c) for c in cmd)}")
    result = subprocess.run(cmd, cwd=cwd, env=env, check=check, text=True)
    return result


# ==============================================================================
# Setup
# ==============================================================================
def setup_common():
    BUILD_ENV_DIR.mkdir(exist_ok=True)

    print("Installing system dependencies...")
    run_cmd(["sudo", "apt-get", "update"])
    run_cmd(["sudo", "apt-get", "install", "-y",
             "git", "wget", "make", "python3", "python3-venv",
             "libffi-dev", "pkg-config", "cmake", "ninja-build"])

    if not VENV_DIR.exists():
        print("Creating Python virtual environment...")
        run_cmd(["python3", "-m", "venv", str(VENV_DIR)])
        run_cmd([str(VENV_PIP), "install", "--upgrade", "pip"])

    print("Installing Python packages...")
    run_cmd([str(VENV_PIP), "install", "pyserial", "esptool", "pyelftools", "ar"])

    if not MPY_DIR.exists():
        print("Cloning MicroPython repository...")
        run_cmd(["git", "clone", "--depth", "1",
                 "https://github.com/micropython/micropython.git", str(MPY_DIR)])
        print("Building mpy-cross compiler...")
        run_cmd(["make", "-C", "mpy-cross"], cwd=MPY_DIR)


def setup_esp8266():
    tarball = BUILD_ENV_DIR / "xtensa-lx106-elf-standalone.tar.gz"
    if not XTENSA_DIR.exists():
        print("Downloading Xtensa LX106 toolchain...")
        urllib.request.urlretrieve(XTENSA_URL, tarball)
        print("Extracting toolchain...")
        with tarfile.open(tarball, "r:gz") as tar:
            tar.extractall(path=BUILD_ENV_DIR)
        tarball.unlink()

    esptool_path = XTENSA_DIR / "bin" / "esptool.py"
    if esptool_path.exists():
        esptool_path.unlink()

    esp_port = get_port_dir("esp8266")
    print("Initializing ESP8266 submodules...")
    run_cmd(["make", "submodules"], cwd=esp_port)


def setup_esp32(chip):
    if not ESP_IDF_DIR.exists():
        print(f"Cloning ESP-IDF ({ESP_IDF_TAG})...")
        run_cmd(["git", "clone", "--depth", "1", "--branch", ESP_IDF_TAG,
                 "--recursive", ESP_IDF_REPO, str(ESP_IDF_DIR)])
        print(f"Installing ESP-IDF tools for {chip}...")
        install_cmd = ["./install.sh", chip]
        run_cmd(install_cmd, cwd=ESP_IDF_DIR)

    esp_port = get_port_dir("esp32")
    print("Initializing ESP32 submodules...")
    run_cmd(["make", "submodules"], cwd=esp_port)


def cmd_setup(args):
    print("=== SETTING UP BUILD ENVIRONMENT ===")
    setup_common()

    if args.chip == "esp8266":
        setup_esp8266()
    elif args.chip.startswith("esp32"):
        setup_esp32(args.chip)
    else:
        print(f"❌ Unsupported chip: {args.chip}")
        sys.exit(1)

    print("\n✅ Environment setup completed successfully!")


# ==============================================================================
# Clean
# ==============================================================================
def cmd_clean(args):
    print("=== CLEANING BUILD ARTIFACTS ===")

    if not MPY_DIR.exists():
        print("Nothing to clean.")
        return

    # Clean ESP8266
    esp8266_port = get_port_dir("esp8266")
    if esp8266_port.exists():
        for d in esp8266_port.glob("build-*"):
            print(f"Removing {d}...")
            shutil.rmtree(d, ignore_errors=True)
        inj_mod = esp8266_port / "custom_modules"
        inj_man = esp8266_port / "custom_manifest.py"
        if inj_mod.exists(): shutil.rmtree(inj_mod, ignore_errors=True)
        if inj_man.exists(): inj_man.unlink()

    # Clean ESP32
    esp32_port = get_port_dir("esp32")
    if esp32_port.exists():
        for d in esp32_port.glob("build-*"):
            print(f"Removing {d}...")
            shutil.rmtree(d, ignore_errors=True)
        inj_mod = esp32_port / "custom_modules"
        inj_man = esp32_port / "custom_manifest.py"
        if inj_mod.exists(): shutil.rmtree(inj_mod, ignore_errors=True)
        if inj_man.exists(): inj_man.unlink()

    print("\n✅ Clean completed. Environment preserved.")


# ==============================================================================
# Build
# ==============================================================================
def cmd_build(args):
    print("=== BUILDING FIRMWARE ===")

    chip = args.chip
    flash_size = args.flash_size
    port_dir = get_port_dir(chip)

    if not port_dir.exists():
        print(f"❌ Error: Port directory for {chip} not found. Run 'setup --chip {chip}' first.")
        sys.exit(1)

    if args.clean or (chip == "esp8266" and args.no_espnow):
        cmd_clean(args)

    env = os.environ.copy()

    # Inject custom files
    print("Injecting custom files into MicroPython tree...")
    inj_mod = port_dir / "custom_modules"
    inj_man = port_dir / "custom_manifest.py"
    shutil.copytree("custom_modules", inj_mod, dirs_exist_ok=True)
    shutil.copy("custom_manifest.py", inj_man)

    manifest_text = Path("custom_manifest.py").read_text(encoding="utf-8")
    if "require(" in manifest_text:
        lib_dir = MPY_DIR / "lib" / "micropython-lib"
        if not (lib_dir / "micropython").exists():
            print("Manifest uses require(); initializing micropython-lib...")
            run_cmd(["git", "submodule", "update", "--init", "lib/micropython-lib"], cwd=MPY_DIR)

    if chip == "esp8266":
        toolchain_bin = (Path.cwd() / XTENSA_DIR / "bin").resolve()
        env["PATH"] = f"{toolchain_bin}:{env['PATH']}"

        make_cmd = [
            "make",
            "BOARD=ESP8266_GENERIC",
            f"FLASH_SIZE={flash_size}",
            "FROZEN_MANIFEST=custom_manifest.py",
        ]
        if args.no_espnow:
            make_cmd.append("MICROPY_PY_ESPNOW=0")
        if args.make_var:
            make_cmd.extend(args.make_var)

        run_cmd(make_cmd, cwd=port_dir, env=env)

    elif chip.startswith("esp32"):
        # ESP32 requires ESP-IDF environment
        export_script = ESP_IDF_DIR / "export.sh"
        if not export_script.exists():
            print("❌ ESP-IDF not installed. Run setup first.")
            sys.exit(1)

        board = "ESP32_GENERIC"
        if chip == "esp32s2": board = "ESP32_GENERIC_S2"
        elif chip == "esp32s3": board = "ESP32_GENERIC_S3"
        elif chip == "esp32c3": board = "ESP32_GENERIC_C3"

        make_cmd = f"source {export_script} && make BOARD={board} FROZEN_MANIFEST=custom_manifest.py"
        if args.make_var:
            make_cmd += " " + " ".join(args.make_var)

        run_cmd(["bash", "-c", make_cmd], cwd=port_dir, env=env)

    firmware_path = get_default_firmware(chip, flash_size)
    if not firmware_path.exists():
        print("\n❌ Error: firmware.bin was not generated.")
        sys.exit(1)

    print(f"\n✅ Build completed successfully!")
    print(f"📦 Firmware location: {firmware_path.resolve()}")

    if args.output:
        output_path = Path(args.output).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(firmware_path, output_path)
        print(f"📋 Firmware copied to: {output_path}")


# ==============================================================================
# Flash & Info helpers
# ==============================================================================
def detect_serial_port():
    """Uses the venv python to reliably detect serial ports."""
    script = "import serial.tools.list_ports; print('\n'.join(p.device for p in serial.tools.list_ports.comports()))"
    try:
        result = subprocess.run([str(VENV_PYTHON), "-c", script],
                                capture_output=True, text=True, check=True)
        ports = [p.strip() for p in result.stdout.splitlines() if p.strip()]
        for p in ports:
            if any(token in p for token in ("ttyUSB", "ttyACM", "tty.usbserial", "COM")):
                return p
        return ports[0] if ports else None
    except Exception:
        return None


def wait_for_device(timeout, port=None):
    print(f"Waiting for device (timeout: {timeout}s)...")
    print("💡 TIP: Hold the GPIO0/BOOT button, then press RESET to enter bootloader mode.")
    start_time = time.time()
    while time.time() - start_time < timeout:
        if port:
            if Path(port).exists() or port.startswith("COM"):
                return port
        else:
            detected = detect_serial_port()
            if detected:
                return detected
        time.sleep(1)
        sys.stdout.write(".")
        sys.stdout.flush()
    print()
    return None


def get_esptool_write_command():
    for name in ("write-flash", "write_flash"):
        proc = subprocess.run([str(VENV_ESPTOOL), name, "-h"], capture_output=True, text=True)
        if proc.returncode == 0:
            return name, proc.stdout + proc.stderr
    print("❌ Error: unable to query esptool capabilities.")
    sys.exit(1)


def cmd_flash(args):
    print("=== FLASHING FIRMWARE ===")

    firmware_path = Path(args.firmware).resolve() if args.firmware else get_default_firmware(args.chip, args.flash_size)
    if not firmware_path.exists():
        print(f"❌ Error: Firmware file not found at {firmware_path}")
        sys.exit(1)

    detected_port = wait_for_device(timeout=args.timeout, port=args.port)
    if not detected_port:
        print("❌ Error: Device not detected.")
        sys.exit(1)

    print(f"\n🔌 Device detected on port: {detected_port}")

    base_cmd = [str(VENV_ESPTOOL), "--chip", args.chip, "--port", detected_port,
                "--baud", str(args.baud)]

    # --- Step 1: Full erase ---
    print("\n⏳ Erasing entire flash...")
    run_cmd(base_cmd + ["erase-flash"], check=True)
    print("✅ Flash erased.")

    # --- Step 2: Wait for bootloader re-entry ---
    print("\n⚠️  Device reset after erase. Put it into bootloader mode again:")
    print("    Hold GPIO0/BOOT → Press RESET → Release GPIO0")
    detected_port = wait_for_device(timeout=args.timeout, port=args.port)
    if not detected_port:
        print("❌ Error: Device not detected after erase.")
        sys.exit(1)

    print(f"\n🔌 Device back on port: {detected_port}")

    # --- Step 3: Write firmware ---
    print("\n⏳ Writing firmware...")
    base_cmd[base_cmd.index("--port") + 1] = detected_port

    write_cmd = base_cmd + ["write-flash"]

    # For ESP8266, --flash-size detect patches the bootloader header
    # with correct SPI flash parameters. Without it the board won't boot.
    if args.chip == "esp8266":
        write_cmd.append("--flash-size")
        write_cmd.append("detect")

    write_cmd += ["0x00000", str(firmware_path)]
    run_cmd(write_cmd, check=True)

    print("\n✅ Firmware flashed successfully!")


def cmd_info(args):
    print("=== QUERYING BOARD INFO ===")

    detected_port = wait_for_device(timeout=30, port=args.port)
    if not detected_port:
        print("❌ Error: Device not detected.")
        sys.exit(1)

    print(f"\n🔌 Device detected on port: {detected_port}")

    # --- Chip ID / Chip type / MAC ---
    print("Reading chip information...")
    try:
        res = subprocess.run(
            [str(VENV_ESPTOOL), "--chip", "auto", "--port", detected_port, "chip-id"],
            capture_output=True, text=True, check=True,
        )
        output = res.stdout + res.stderr

        # esptool v3/v4: "Chip is ESP8266EX"
        # esptool v5.x:  "Chip type:          ESP8266EX"
        chip_match = re.search(r"Chip(?:\s+type:|\s+is)\s+(\S+)", output)
        mac_match = re.search(r"MAC:\s+(\S+)", output)
        id_match = re.search(r"Chip ID:\s+(\S+)", output)

        print(f"  Chip:      {chip_match.group(1) if chip_match else 'Unknown'}")
        print(f"  MAC:       {mac_match.group(1) if mac_match else 'Unknown'}")
        if id_match:
            print(f"  Chip ID:   {id_match.group(1)}")
    except subprocess.CalledProcessError:
        print("  Could not read chip ID.")

    # --- Flash size ---
    print("Reading flash information...")
    try:
        res = subprocess.run(
            [str(VENV_ESPTOOL), "--chip", "auto", "--port", detected_port, "flash-id"],
            capture_output=True, text=True, check=True,
        )
        output = res.stdout + res.stderr

        flash_match = re.search(r"Detected flash size:\s+(\S+)", output)
        mfr_match = re.search(r"Manufacturer:\s+(\S+)", output)
        dev_match = re.search(r"Device:\s+(\S+)", output)

        print(f"  Flash Size: {flash_match.group(1) if flash_match else 'Unknown'}")
        if mfr_match and dev_match:
            print(f"  Flash ID:   {mfr_match.group(1)}:{dev_match.group(1)}")
    except subprocess.CalledProcessError:
        print("  Could not read flash ID.")


# ==============================================================================
# CLI
# ==============================================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MicroPython ESP Build & Flash Tool")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Common arguments helper
    def add_common_args(p):
        p.add_argument("--chip", choices=["esp8266", "esp32", "esp32s2", "esp32s3", "esp32c3"],
                       default="esp8266", help="Target chip (default: esp8266)")

    # setup
    p_setup = subparsers.add_parser("setup", help="Prepare build environment")
    add_common_args(p_setup)

    # clean
    p_clean = subparsers.add_parser("clean", help="Remove build artifacts")
    add_common_args(p_clean)

    # build
    p_build = subparsers.add_parser("build", help="Compile firmware")
    add_common_args(p_build)
    p_build.add_argument("--flash-size", choices=["512K", "1M", "2M", "4M", "8M", "16M"],
                         default=ESP8266_DEFAULT_FLASH_SIZE,
                         help=f"Flash size for ESP8266 (default: {ESP8266_DEFAULT_FLASH_SIZE})")
    p_build.add_argument("-c", "--clean", action="store_true", help="Clean before building")
    p_build.add_argument("--no-espnow", action="store_true", help="Disable ESP-NOW (ESP8266)")
    p_build.add_argument("--make-var", action="append", default=[], metavar="KEY=VALUE")
    p_build.add_argument("-o", "--output", help="Copy firmware to this path")

    # flash
    p_flash = subparsers.add_parser("flash", help="Flash firmware")
    add_common_args(p_flash)
    p_flash.add_argument("--flash-size", choices=["512K", "1M", "2M", "4M", "8M", "16M"],
                         default=ESP8266_DEFAULT_FLASH_SIZE)
    p_flash.add_argument("-p", "--port", help="Serial port")
    p_flash.add_argument("-f", "--firmware", help="Path to firmware.bin")
    p_flash.add_argument("-b", "--baud", type=int, default=460800)
    p_flash.add_argument("-t", "--timeout", type=int, default=120)

    # info
    p_info = subparsers.add_parser("info", help="Query board hardware info")
    p_info.add_argument("-p", "--port", help="Serial port")

    args = parser.parse_args()

    if args.command == "setup": cmd_setup(args)
    elif args.command == "clean": cmd_clean(args)
    elif args.command == "build": cmd_build(args)
    elif args.command == "flash": cmd_flash(args)
    elif args.command == "info": cmd_info(args)
