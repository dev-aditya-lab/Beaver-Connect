# Beaver Connect

**BeaverX Pvt. Ltd.** — *"Building the Future of Robotics & AI"*

Beaver Connect is a lightweight Windows desktop companion application for the [BeaverLab Blockly](https://blox.beaverlab.in) robotics platform. It bridges the browser-based visual programming interface with physical Arduino / ESP32 hardware.

```
Website (code.beaverlab.in)
    ↓  HTTP (localhost only)
Beaver Connect  →  http://127.0.0.1:8765
    ↓
Arduino CLI
    ↓
ESP32 / Arduino board
```

---

## Features

| Feature | Status |
|---|---|
| Local FastAPI REST server | ✅ |
| Board detection (USB VID/PID) | ✅ |
| Arduino code compilation | ✅ |
| Firmware flashing | ✅ |
| Rotating log files | ✅ |
| CORS restriction (beaverlab.in only) | ✅ |
| Windows .exe packaging | ✅ |
| Serial Monitor | 🔜 |
| WebSocket progress updates | 🔜 |
| OTA Updates | 🔜 |

---

## Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Python | 3.12+ | [python.org](https://www.python.org) |
| Arduino CLI | Latest | See below |

### Install Arduino CLI

1. Download `arduino-cli_*_Windows_64bit.zip` from the [Arduino CLI releases](https://github.com/arduino/arduino-cli/releases).
2. Extract `arduino-cli.exe` into the `toolchains/` folder:
   ```
   beaver-connect/toolchains/arduino-cli.exe
   ```
3. Install the ESP32 and AVR platforms:
   ```powershell
   .\toolchains\arduino-cli.exe core update-index --arduino-data-dir toolchains\arduino-cli-data
   .\toolchains\arduino-cli.exe core install esp32:esp32 --arduino-data-dir toolchains\arduino-cli-data
   .\toolchains\arduino-cli.exe core install arduino:avr  --arduino-data-dir toolchains\arduino-cli-data
   ```

---

## Local Development

```powershell
# 1. Clone / navigate to the project
cd beaver-connect

# 2. Create a virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -r requirements.txt

# 4. Start the server
python app.py
```

The server starts at **http://127.0.0.1:8765**.

Open **http://127.0.0.1:8765/docs** in a browser to explore the interactive API documentation.

---

## API Reference

### `GET /health`
Liveness probe. Returns `200 OK` when the app is running.
```json
{ "status": "ok", "app": "Beaver Connect", "version": "1.0.0" }
```

### `GET /boards`
Returns connected Arduino-compatible boards.
```json
[{ "port": "COM3", "board": "ESP32", "description": "CP210x USB to UART" }]
```

### `POST /compile`
Compiles Arduino code without flashing.
```json
// Request
{ "board": "esp32", "code": "void setup(){} void loop(){}" }

// Success
{ "success": true, "firmwarePath": "C:\\...\\temp\\build_abc123" }

// Failure
{ "success": false, "error": "compilation error message" }
```

### `POST /flash`
Compiles and uploads firmware in one step.
```json
// Request
{ "board": "esp32", "port": "COM3", "code": "void setup(){} void loop(){}" }

// Success
{ "success": true, "message": "Firmware uploaded successfully to esp32 on COM3." }

// Failure
{ "success": false, "error": "...", "compileLog": "...", "flashLog": "..." }
```

---

## Supported Boards

| API Key | Board | FQBN |
|---|---|---|
| `esp32` | ESP32 | `esp32:esp32:esp32` |
| `esp8266` | ESP8266 | `esp8266:esp8266:generic` |
| `uno` | Arduino Uno | `arduino:avr:uno` |
| `nano` | Arduino Nano | `arduino:avr:nano` |
| `mega` | Arduino Mega | `arduino:avr:mega` |
| `leonardo` | Arduino Leonardo | `arduino:avr:leonardo` |
| `micro` | Arduino Micro | `arduino:avr:micro` |

To add a new board, add one entry to `BOARD_FQBN` in `config.py`.

---

## Project Structure

```
beaver-connect/
├── app.py               ← FastAPI app, CORS, lifecycle hooks, entry point
├── config.py            ← All configuration constants (one place to change them)
├── logger_setup.py      ← Rotating file + console logging
│
├── routes/
│   ├── health.py        ← GET  /health
│   ├── boards.py        ← GET  /boards
│   ├── compile.py       ← POST /compile
│   └── flash.py         ← POST /flash
│
├── services/
│   ├── arduino_service.py   ← Low-level arduino-cli subprocess wrapper
│   ├── board_service.py     ← USB port enumeration + VID/PID fingerprinting
│   ├── compiler_service.py  ← Sketch creation + compile orchestration
│   └── flasher_service.py   ← Compile + upload pipeline
│
├── temp/                ← Temporary sketch and build artefacts (auto-cleaned)
├── logs/                ← Rotating log files (app.log, compile.log, flash.log)
├── toolchains/          ← arduino-cli.exe + platform data
│
├── build_windows.spec   ← PyInstaller spec for Windows .exe
└── requirements.txt
```

---

## Building the Windows Executable

```powershell
# 1. Activate venv and install requirements (see Local Development above)

# 2. Place arduino-cli.exe in toolchains/ (see Prerequisites above)

# 3. Build
pyinstaller build_windows.spec

# Output: dist\BeaverConnect\BeaverConnect.exe
```

The `dist\BeaverConnect\` folder is self-contained — copy it anywhere and run `BeaverConnect.exe`.

---

## Security

- Server binds **only** to `127.0.0.1` — never exposed to the local network.
- CORS allows only `code.beaverlab.in`, `blox.beaverlab.in`, and localhost origins.
- All arduino-cli calls use `subprocess` with explicit argument lists (no shell injection).
- No user credentials are stored or transmitted.

---

## Logs

| File | Contents |
|---|---|
| `logs/app.log` | Server startup, HTTP requests, general events |
| `logs/compile.log` | Compilation subprocess output |
| `logs/flash.log` | Upload subprocess output |

Files rotate at 5 MB; 3 backups are kept.

---

## Adding Future Features

The architecture is designed for easy extension:

- **Serial Monitor** — add `routes/serial.py` + `services/serial_service.py`, stream data via WebSocket.
- **WebSocket progress** — add `fastapi.websockets` to `app.py`; services already log progress strings.
- **Firmware cache** — add a `cache/` lookup in `compiler_service.py` keyed on `hash(board + code)`.
- **Multiple boards** — `board_service.py` already returns a list; flash multiple in parallel with `asyncio.gather`.
- **Auto-updates** — poll a version endpoint from `on_startup()` in `app.py`.

---

*© 2024 BeaverX Pvt. Ltd. All rights reserved.*
