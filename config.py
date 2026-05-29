"""
config.py — Central configuration for Beaver Connect.

All environment-level knobs live here. Import from this module anywhere you
need a constant so there is exactly ONE place to change values in production.

BeaverX Pvt. Ltd. — "Building the Future of Robotics & AI"
"""

import os
import sys
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# Base Paths
# ─────────────────────────────────────────────────────────────────────────────

# ROOT_DIR is the folder that contains this file (the project root).
ROOT_DIR: Path = Path(__file__).parent.resolve()

# temp/ is where sketch folders and compiled binaries land during build/flash.
TEMP_DIR: Path = ROOT_DIR / "temp"

# logs/ stores rotating log files (app, compile, flash).
LOGS_DIR: Path = ROOT_DIR / "logs"

# toolchains/ is where arduino-cli and board platform files are stored.
TOOLCHAINS_DIR: Path = ROOT_DIR / "toolchains"

# Ensure these directories exist at import time so nothing blows up later.
for _dir in (TEMP_DIR, LOGS_DIR, TOOLCHAINS_DIR):
    _dir.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────────────────────────────────────────
# Server Settings
# ─────────────────────────────────────────────────────────────────────────────

# Bind ONLY to loopback — never expose this server to the LAN/WAN.
SERVER_HOST: str = "127.0.0.1"
SERVER_PORT: int = 8765

# ─────────────────────────────────────────────────────────────────────────────
# Application Metadata
# ─────────────────────────────────────────────────────────────────────────────

APP_NAME: str = "Beaver Connect"
APP_VERSION: str = "1.0.0"
COMPANY: str = "BeaverX Pvt. Ltd."
TAGLINE: str = "Building the Future of Robotics & AI"
WEBSITE: str = "https://code.beaverlab.in"

# ─────────────────────────────────────────────────────────────────────────────
# CORS — Allowed Origins
# ─────────────────────────────────────────────────────────────────────────────
# Only the BeaverLab website and localhost are permitted to call this API.
# Any other origin will be rejected at the middleware level.

ALLOWED_ORIGINS: list[str] = [
    "https://code.beaverlab.in",
    "https://blox.beaverlab.in",
    "http://localhost",
    "http://localhost:3000",   # common React dev port
    "http://localhost:5173",   # Vite dev server
    "http://localhost:8080",
    "http://127.0.0.1",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:8080",
]

# ─────────────────────────────────────────────────────────────────────────────
# Arduino CLI
# ─────────────────────────────────────────────────────────────────────────────

# Path to the arduino-cli executable.
# On Windows, PyInstaller bundles land in sys._MEIPASS when frozen.
# At dev time, fall back to whatever is on PATH.
if getattr(sys, "frozen", False):
    # Running as a PyInstaller bundle — look inside the extracted package.
    _bundle_dir = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    ARDUINO_CLI_PATH: str = str(_bundle_dir / "arduino-cli.exe")
else:
    # Running from source — use the copy inside toolchains/ if present,
    # otherwise trust the system PATH.
    _local_cli = TOOLCHAINS_DIR / "arduino-cli.exe"
    ARDUINO_CLI_PATH = str(_local_cli) if _local_cli.exists() else "arduino-cli"

# Directory where arduino-cli stores its data (platforms, libraries, cache).
# We use a local path so the app is fully self-contained and doesn't pollute
# the user's global Arduino installation.
ARDUINO_DATA_DIR: str = str(TOOLCHAINS_DIR / "arduino-cli-data")

# ─────────────────────────────────────────────────────────────────────────────
# Board FQBN (Fully Qualified Board Name) Map
# ─────────────────────────────────────────────────────────────────────────────
# The FQBN is the identifier arduino-cli needs to target a specific board.
# Keys are the short board names the website sends us in API requests.
# Adding a new board = adding one entry here, nothing else needs to change.

BOARD_FQBN: dict[str, str] = {
    "esp32":        "esp32:esp32:esp32",
    "esp32dev":     "esp32:esp32:esp32",
    "esp8266":      "esp8266:esp8266:generic",
    "uno":          "arduino:avr:uno",
    "arduino_uno":  "arduino:avr:uno",
    "nano":         "arduino:avr:nano",
    "arduino_nano": "arduino:avr:nano",
    "mega":         "arduino:avr:mega",
    "mega2560":     "arduino:avr:mega",
    "micro":        "arduino:avr:micro",
    "leonardo":     "arduino:avr:leonardo",
}

# ─────────────────────────────────────────────────────────────────────────────
# Board USB VID/PID Fingerprints
# ─────────────────────────────────────────────────────────────────────────────
# pyserial exposes the USB vendor/product IDs for each serial port.
# We use these to give friendly board names to detected ports instead of
# showing raw "USB Serial Device" labels.
# Format: (VID, PID | None) → friendly_name
# If PID is None, any product from that vendor matches.

BOARD_VID_PID: list[tuple[int, int | None, str]] = [
    # ── ESP32 (Silicon Labs CP2102/CP2104) ───────────────────────────────
    (0x10C4, 0xEA60, "ESP32"),   # CP2102 — most common ESP32 breakout
    (0x10C4, 0xEA70, "ESP32"),   # CP2104 variant
    # ── ESP32 (WCH CH340/CH341 — common on budget boards) ────────────────
    (0x1A86, 0x7523, "ESP32"),   # CH340
    (0x1A86, 0x5523, "ESP32"),   # CH341
    # ── ESP8266 (same CP2102/CH340 chips) ────────────────────────────────
    (0x10C4, 0xEA60, "ESP8266"), # CP2102 — also used by ESP8266 NodeMCU
    (0x1A86, 0x7523, "ESP8266"), # CH340 — Wemos D1 Mini, NodeMCU
    # ── Arduino Uno (ATmega16U2 USB bridge) ──────────────────────────────
    (0x2341, 0x0043, "Arduino Uno"),
    (0x2341, 0x0001, "Arduino Uno"),
    # ── Arduino Nano (FT232R or CH340 based) ─────────────────────────────
    (0x0403, 0x6001, "Arduino Nano"),  # FTDI FT232R
    (0x1A86, 0x7523, "Arduino Nano"),  # CH340 clone
    # ── Arduino Mega ─────────────────────────────────────────────────────
    (0x2341, 0x0010, "Arduino Mega"),
    (0x2341, 0x0042, "Arduino Mega"),
    # ── Arduino Leonardo / Micro ─────────────────────────────────────────
    (0x2341, 0x8036, "Arduino Leonardo"),
    (0x2341, 0x8037, "Arduino Micro"),
]

# ─────────────────────────────────────────────────────────────────────────────
# Compilation / Flash Timeouts (seconds)
# ─────────────────────────────────────────────────────────────────────────────

COMPILE_TIMEOUT: int = 120   # arduino-cli compile can be slow on first run
FLASH_TIMEOUT: int = 60      # upload is usually fast; give some headroom

# ─────────────────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────────────────

LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FORMAT: str = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
LOG_DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"
LOG_MAX_BYTES: int = 5 * 1024 * 1024   # 5 MB per log file before rotation
LOG_BACKUP_COUNT: int = 3               # keep 3 rotated backups
