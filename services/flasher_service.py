"""
services/flasher_service.py — Firmware compilation and upload orchestration.

The flash workflow is:
    1. Compile the code (delegates to compiler_service).
    2. If compilation succeeds, upload the firmware (delegates to arduino_service).
    3. Clean up temporary build artefacts after upload.
    4. Return a structured result.

This service is the single entry point for the /flash API route.
It coordinates compiler_service and arduino_service without either
of them knowing about the other.

BeaverX Pvt. Ltd. — "Building the Future of Robotics & AI"
"""

import logging
from dataclasses import dataclass
from pathlib import Path

from services.arduino_service import resolve_fqbn, upload_firmware
from services.compiler_service import CompileResult, cleanup_build, compile_code

logger = logging.getLogger("beaver.flasher_service")


# ─────────────────────────────────────────────────────────────────────────────
# Result types
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class FlashResult:
    """
    Outcome of a complete compile-and-flash operation.

    Attributes:
        success:     True only when BOTH compile and upload succeeded.
        message:     Human-readable success or failure description.
        compile_log: Output captured from the compile step.
        flash_log:   Output captured from the upload step.
    """
    success: bool
    message: str
    compile_log: str
    flash_log: str


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

async def compile_and_flash(
    board: str,
    port: str,
    code: str,
) -> FlashResult:
    """
    Compile Arduino code and upload it to a connected board in one step.

    This is the primary entry point called by the /flash API route.

    Args:
        board: Short board name (e.g. "esp32", "uno").
        port:  Serial port the board is connected to (e.g. "COM3").
        code:  Full Arduino C++ source code.

    Returns:
        FlashResult describing the final outcome.
    """
    # ── Step 1: Resolve FQBN early to surface config errors immediately ───────
    fqbn = resolve_fqbn(board)
    if fqbn is None:
        logger.error("Flash requested for unknown board: %s", board)
        return FlashResult(
            success=False,
            message=f"Unsupported board '{board}'. Update BOARD_FQBN in config.py.",
            compile_log="",
            flash_log="",
        )

    # ── Step 2: Compile ───────────────────────────────────────────────────────
    logger.info("Flash workflow started | board=%s port=%s", board, port)

    compile_result: CompileResult = await compile_code(board=board, code=code)

    if not compile_result.success:
        logger.error("Flash aborted — compilation failed for board %s", board)
        return FlashResult(
            success=False,
            message=f"Compilation failed: {compile_result.error}",
            compile_log=compile_result.raw_output,
            flash_log="",
        )

    logger.info("Compilation OK. Proceeding to upload on port %s", port)

    # ── Step 3: Upload ────────────────────────────────────────────────────────
    build_dir = Path(compile_result.firmware_path)  # type: ignore[arg-type]

    # The sketch directory is derived from the build directory naming convention
    # set in compiler_service: build_<id> → sketch_<id>
    # We pass sketch_dir so arduino-cli upload knows the sketch context.
    sketch_dir = build_dir.parent / f"sketch_{build_dir.name.split('_', 1)[1]}"

    upload_result = await upload_firmware(
        sketch_dir=sketch_dir,
        fqbn=fqbn,
        port=port,
        build_dir=build_dir,
    )

    flash_log = "\n".join(
        filter(None, [upload_result.stdout, upload_result.stderr])
    )

    # ── Step 4: Cleanup — always run, regardless of upload outcome ────────────
    cleanup_build(str(build_dir))

    # Also clean up the sketch directory (compiler_service kept it for us).
    if sketch_dir.exists():
        import shutil
        shutil.rmtree(sketch_dir, ignore_errors=True)
        logger.debug("Cleaned up sketch dir: %s", sketch_dir)

    # ── Step 5: Return result ─────────────────────────────────────────────────
    if upload_result.success:
        logger.info("Firmware uploaded successfully to %s on %s", board, port)
        return FlashResult(
            success=True,
            message=f"Firmware uploaded successfully to {board} on {port}.",
            compile_log=compile_result.raw_output,
            flash_log=flash_log,
        )
    else:
        error_msg = upload_result.stderr or upload_result.stdout or "Unknown upload error."
        logger.error("Upload failed on %s: %s", port, error_msg[:200])
        return FlashResult(
            success=False,
            message=f"Upload failed: {error_msg}",
            compile_log=compile_result.raw_output,
            flash_log=flash_log,
        )
