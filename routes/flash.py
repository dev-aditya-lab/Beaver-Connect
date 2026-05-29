"""
routes/flash.py — POST /flash

Accepts Arduino source code, compiles it, and uploads the resulting
firmware to the specified board on the specified serial port — all
in a single HTTP request.

This is the primary endpoint the website uses when the user clicks
"Upload to Board" in the Blockly interface.

BeaverX Pvt. Ltd. — "Building the Future of Robotics & AI"
"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.flasher_service import compile_and_flash

logger = logging.getLogger("beaver.route.flash")
router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Request / Response schemas
# ─────────────────────────────────────────────────────────────────────────────

class FlashRequest(BaseModel):
    """POST body expected by /flash."""

    board: str = Field(
        ...,
        examples=["esp32", "uno"],
        description="Short board name (must match a key in config.BOARD_FQBN).",
    )
    port: str = Field(
        ...,
        examples=["COM3", "COM5"],
        description=(
            "Serial port the target board is connected to. "
            "Use GET /boards to discover available ports."
        ),
    )
    code: str = Field(
        ...,
        min_length=1,
        description="Complete Arduino C++ source code to compile and flash.",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Route
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/flash",
    summary="Compile and flash firmware",
    description=(
        "Compiles the provided Arduino source code for the target board "
        "and then uploads the resulting firmware over the specified serial port. "
        "Returns success/failure with logs from both the compile and upload steps."
    ),
)
async def flash_firmware(request: FlashRequest) -> dict:
    """
    End-to-end compile + upload workflow triggered by the website.

    Steps:
      1. Resolve board FQBN.
      2. Compile the sketch (arduino-cli compile).
      3. Upload firmware to the board (arduino-cli upload).
      4. Clean up temporary build files.
      5. Return structured result.

    Because flashing blocks the serial port, only one flash request
    should be in-flight at a time. The website is responsible for
    preventing concurrent flash calls (e.g. by disabling the Upload
    button while a flash is in progress).
    """
    logger.info(
        "Flash request | board=%s port=%s code_length=%d",
        request.board, request.port, len(request.code)
    )

    # Basic port sanity check — Windows ports must start with "COM".
    # This prevents obviously wrong input without being overly strict.
    if not request.port.upper().startswith("COM") and not request.port.startswith("/dev/"):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid port '{request.port}'. "
                "Expected a COM port (e.g. 'COM3') on Windows."
            ),
        )

    try:
        result = await compile_and_flash(
            board=request.board,
            port=request.port,
            code=request.code,
        )
    except Exception as exc:
        logger.exception("Unhandled error in compile_and_flash: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Internal flash error: {exc}",
        ) from exc

    if result.success:
        logger.info("Flash succeeded | board=%s port=%s", request.board, request.port)
        return {
            "success": True,
            "message": result.message,
        }
    else:
        logger.warning("Flash failed | message=%s", result.message[:200])
        return {
            "success": False,
            "error": result.message,
            # Include logs so the developer can debug without digging through log files.
            "compileLog": result.compile_log,
            "flashLog": result.flash_log,
        }
