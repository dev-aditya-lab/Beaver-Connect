"""
services/board_service.py — USB serial port detection and board identification.

Uses pyserial to enumerate available COM ports and matches each port's
USB vendor/product ID against a known fingerprint table to assign a
friendly board name (e.g. "ESP32", "Arduino Uno").

BeaverX Pvt. Ltd. — "Building the Future of Robotics & AI"
"""

import logging
from dataclasses import dataclass

import serial.tools.list_ports
from serial.tools.list_ports_common import ListPortInfo

from config import BOARD_VID_PID

logger = logging.getLogger("beaver.board_service")


# ─────────────────────────────────────────────────────────────────────────────
# Data Model
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class DetectedBoard:
    """
    Represents a single physical board connected to the computer.

    Attributes:
        port:         Serial port name (e.g. "COM3").
        board:        Friendly board name ("ESP32", "Arduino Uno", "Unknown").
        description:  Raw description string from the OS driver.
        vid:          USB Vendor ID as integer, or None if not available.
        pid:          USB Product ID as integer, or None if not available.
        serial_number: USB serial number string, or None.
    """
    port: str
    board: str
    description: str
    vid: int | None = None
    pid: int | None = None
    serial_number: str | None = None


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _identify_board(port_info: ListPortInfo) -> str:
    """
    Map a port's USB VID/PID to a human-readable board name.

    We scan BOARD_VID_PID (defined in config.py) in order.
    The first matching entry wins, so put more specific (VID+PID) entries
    before broader (VID-only) ones in the config list.

    Returns "Unknown Device" when no fingerprint matches.
    """
    vid: int | None = port_info.vid
    pid: int | None = port_info.pid

    if vid is None:
        # Port has no USB VID — likely a pure RS-232 or virtual COM port.
        return "Unknown Device"

    for entry_vid, entry_pid, board_name in BOARD_VID_PID:
        vid_match = entry_vid == vid
        pid_match = (entry_pid is None) or (entry_pid == pid)
        if vid_match and pid_match:
            return board_name

    # VID is present but doesn't match any known board.
    logger.debug(
        "Unrecognised VID=0x%04X PID=0x%04X on %s",
        vid, pid or 0, port_info.device
    )
    return "Unknown Device"


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def list_connected_boards() -> list[DetectedBoard]:
    """
    Enumerate all serial ports and return those that look like hardware boards.

    Ports with no USB VID/PID (e.g. built-in RS-232 adapters on old machines,
    or purely virtual ports without associated hardware) are included but
    labelled "Unknown Device" so the user can still pick them manually.

    Returns:
        A list of DetectedBoard objects, sorted by port name.
    """
    boards: list[DetectedBoard] = []

    raw_ports = serial.tools.list_ports.comports()
    logger.debug("Raw port scan found %d port(s)", len(raw_ports))

    for port_info in sorted(raw_ports, key=lambda p: p.device):
        board_name = _identify_board(port_info)

        board = DetectedBoard(
            port=port_info.device,
            board=board_name,
            description=port_info.description or "",
            vid=port_info.vid,
            pid=port_info.pid,
            serial_number=port_info.serial_number,
        )
        boards.append(board)

        logger.info(
            "Detected port: %s — %s (VID=0x%04X PID=0x%04X)",
            board.port,
            board.board,
            board.vid or 0,
            board.pid or 0,
        )

    if not boards:
        logger.info("No serial ports detected.")

    return boards


def board_to_dict(board: DetectedBoard) -> dict:
    """
    Serialise a DetectedBoard to the JSON shape the API returns.

    We deliberately keep vid/pid out of the public response to avoid
    leaking hardware fingerprints to the website unnecessarily.
    Only port and board name are needed by the frontend.
    """
    return {
        "port": board.port,
        "board": board.board,
        "description": board.description,
    }
