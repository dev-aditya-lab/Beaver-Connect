"""
routes/boards.py — GET /boards

Returns the list of currently connected hardware boards as detected
via USB serial port enumeration.

The website calls this endpoint when the user clicks "Detect Boards"
or when it needs to populate a port selector dropdown.

BeaverX Pvt. Ltd. — "Building the Future of Robotics & AI"
"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.board_service import board_to_dict, list_connected_boards

logger = logging.getLogger("beaver.route.boards")
router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Response schema
# ─────────────────────────────────────────────────────────────────────────────

class BoardInfo(BaseModel):
    """A single detected board entry."""
    port: str          # e.g. "COM3"
    board: str         # e.g. "ESP32"
    description: str   # e.g. "Silicon Labs CP210x USB to UART Bridge"


# ─────────────────────────────────────────────────────────────────────────────
# Route
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/boards",
    response_model=list[BoardInfo],
    summary="Detect connected boards",
    description=(
        "Scans all serial ports and returns boards that appear to be "
        "Arduino-compatible microcontrollers. An empty list means no "
        "boards are currently connected."
    ),
)
async def get_boards() -> list[dict]:
    """
    Enumerate USB serial ports and identify connected hardware boards.

    Returns an empty list (not an error) when no boards are detected —
    the website should handle this gracefully by telling the user to
    connect a board and try again.
    """
    try:
        boards = list_connected_boards()
        result = [board_to_dict(b) for b in boards]
        logger.info("Board scan complete: %d board(s) found", len(result))
        return result

    except Exception as exc:
        # pyserial can raise on some exotic Windows serial drivers.
        logger.exception("Unexpected error during board scan: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Board detection failed: {exc}",
        ) from exc
