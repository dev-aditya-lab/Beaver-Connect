"""
routes/compile.py — POST /compile

Accepts Arduino source code from the website, compiles it for the
specified board using Arduino CLI, and returns the result.

Use this endpoint when you want to verify code compiles correctly
without flashing it (e.g. dry-run before uploading, or when you need
to cache the binary for a later OTA push).

BeaverX Pvt. Ltd. — "Building the Future of Robotics & AI"
"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.compiler_service import compile_code

logger = logging.getLogger("beaver.route.compile")
router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Request / Response schemas
# ─────────────────────────────────────────────────────────────────────────────

class CompileRequest(BaseModel):
    """POST body expected by /compile."""

    board: str = Field(
        ...,
        examples=["esp32", "uno"],
        description=(
            "Short board name. Must match a key in BOARD_FQBN (config.py). "
            "Examples: 'esp32', 'uno', 'nano', 'mega', 'esp8266'."
        ),
    )
    code: str = Field(
        ...,
        min_length=1,
        description="Complete Arduino C++ source code to compile.",
    )


class CompileSuccessResponse(BaseModel):
    """Returned when compilation succeeds."""
    success: bool = True
    firmwarePath: str   # Path to the build directory on disk


class CompileErrorResponse(BaseModel):
    """Returned when compilation fails."""
    success: bool = False
    error: str          # Human-readable error from arduino-cli


# ─────────────────────────────────────────────────────────────────────────────
# Route
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/compile",
    summary="Compile Arduino code",
    description=(
        "Compiles the provided Arduino source code for the given board. "
        "Returns the path to the compiled firmware on success, or a "
        "detailed error message on failure."
    ),
)
async def compile_sketch(request: CompileRequest) -> dict:
    """
    Compile Arduino C++ code for the requested target board.

    The board name must match one of the keys in BOARD_FQBN (config.py).
    Compilation runs locally using the bundled Arduino CLI — no internet
    connection is required after the first platform install.
    """
    logger.info(
        "Compile request | board=%s | code_length=%d chars",
        request.board, len(request.code)
    )

    try:
        result = await compile_code(board=request.board, code=request.code)
    except Exception as exc:
        # Catch unexpected errors (e.g. disk full, permission denied on temp/).
        logger.exception("Unhandled error in compile_code: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Internal compilation error: {exc}",
        ) from exc

    if result.success:
        logger.info("Compile succeeded | firmwarePath=%s", result.firmware_path)
        return {
            "success": True,
            "firmwarePath": result.firmware_path,
        }
    else:
        logger.warning("Compile failed | error=%s", result.error[:200] if result.error else "")
        return {
            "success": False,
            "error": result.error,
        }
