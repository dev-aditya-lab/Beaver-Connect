"""
services/compiler_service.py — Arduino sketch compilation orchestration.

This service turns raw Arduino C++ source code (sent by the website) into
compiled firmware binaries. It:

  1. Writes the code to a temporary sketch folder.
  2. Delegates to arduino_service for the actual compile subprocess.
  3. Returns the path to the compiled firmware or a structured error.

BeaverX Pvt. Ltd. — "Building the Future of Robotics & AI"
"""

import logging
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path

from config import TEMP_DIR
from services.arduino_service import CLIResult, compile_sketch, resolve_fqbn

logger = logging.getLogger("beaver.compiler_service")


# ─────────────────────────────────────────────────────────────────────────────
# Result types
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CompileResult:
    """
    Outcome of a single compilation request.

    Attributes:
        success:      True when arduino-cli exited with code 0.
        firmware_path: Absolute path to the build output directory.
                       Valid only when success=True.
        error:        Human-readable error message. Set when success=False.
        raw_output:   Full stdout+stderr from arduino-cli for debugging.
    """
    success: bool
    firmware_path: str | None
    error: str | None
    raw_output: str


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _create_sketch(code: str, session_id: str) -> tuple[Path, Path]:
    """
    Write the user's code into a properly structured Arduino sketch folder.

    Arduino CLI requires:
        <sketch_name>/
            <sketch_name>.ino    ← source file must match folder name

    We create a unique folder per compilation request to prevent race
    conditions when multiple compile requests arrive simultaneously.

    Args:
        code:       Raw Arduino C++ source code.
        session_id: Unique identifier for this compilation session.

    Returns:
        (sketch_dir, build_dir) — both as Path objects.
    """
    sketch_name = f"sketch_{session_id}"
    sketch_dir = TEMP_DIR / sketch_name
    build_dir = TEMP_DIR / f"build_{session_id}"

    sketch_dir.mkdir(parents=True, exist_ok=True)

    ino_file = sketch_dir / f"{sketch_name}.ino"
    ino_file.write_text(code, encoding="utf-8")

    logger.debug("Sketch written to %s (%d chars)", ino_file, len(code))
    return sketch_dir, build_dir


def _cleanup_session(sketch_dir: Path, build_dir: Path) -> None:
    """
    Remove temporary sketch and build directories after compilation.

    We deliberately leave the build_dir in place when compilation
    succeeds so the flash service can read the binary without
    having to compile again. Callers are responsible for cleanup
    after the full flash cycle is done.

    This function is only called on compilation failure.
    """
    for directory in (sketch_dir,):
        try:
            shutil.rmtree(directory, ignore_errors=True)
            logger.debug("Cleaned up %s", directory)
        except Exception as exc:
            logger.warning("Could not remove %s: %s", directory, exc)


def _extract_error(result: CLIResult) -> str:
    """
    Pull the most useful error text out of a failed CLIResult.

    arduino-cli prints compilation errors to stderr; we return that
    first and fall back to stdout if stderr is empty.
    """
    if result.stderr:
        return result.stderr
    if result.stdout:
        return result.stdout
    return f"arduino-cli exited with code {result.return_code} and no output."


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

async def compile_code(board: str, code: str) -> CompileResult:
    """
    Compile Arduino source code for the specified board.

    This is the primary entry point called by the /compile route.

    Args:
        board: Short board name sent by the website (e.g. "esp32", "uno").
        code:  Complete Arduino C++ source code to compile.

    Returns:
        CompileResult with success/failure details and the firmware path.
    """
    # ── 1. Resolve FQBN ──────────────────────────────────────────────────────
    fqbn = resolve_fqbn(board)
    if fqbn is None:
        logger.error("Unknown board requested: %s", board)
        return CompileResult(
            success=False,
            firmware_path=None,
            error=f"Unsupported board '{board}'. Check BOARD_FQBN in config.py.",
            raw_output="",
        )

    # ── 2. Write sketch to temp directory ────────────────────────────────────
    session_id = uuid.uuid4().hex[:12]  # short unique ID for this job
    sketch_dir, build_dir = _create_sketch(code, session_id)

    logger.info(
        "Starting compilation | board=%s fqbn=%s session=%s",
        board, fqbn, session_id
    )

    # ── 3. Invoke arduino-cli via arduino_service ─────────────────────────────
    cli_result = await compile_sketch(
        sketch_dir=sketch_dir,
        fqbn=fqbn,
        build_dir=build_dir,
    )

    raw_output = "\n".join(filter(None, [cli_result.stdout, cli_result.stderr]))

    # ── 4. Handle failure ─────────────────────────────────────────────────────
    if not cli_result.success:
        error_msg = _extract_error(cli_result)
        logger.error("Compilation failed for session %s: %s", session_id, error_msg[:200])

        # Clean up the sketch folder on failure; build artefacts don't exist.
        _cleanup_session(sketch_dir, build_dir)

        return CompileResult(
            success=False,
            firmware_path=None,
            error=error_msg,
            raw_output=raw_output,
        )

    # ── 5. Success — return path to build directory ───────────────────────────
    logger.info("Compilation succeeded for session %s. Artefacts: %s", session_id, build_dir)

    return CompileResult(
        success=True,
        firmware_path=str(build_dir),
        error=None,
        raw_output=raw_output,
    )


def cleanup_build(build_dir_path: str) -> None:
    """
    Remove a build directory after it has been flashed to the board.

    Called by flasher_service once the upload is complete so we don't
    accumulate megabytes of firmware files in temp/.
    """
    build_dir = Path(build_dir_path)
    if build_dir.exists():
        shutil.rmtree(build_dir, ignore_errors=True)
        logger.debug("Removed build directory: %s", build_dir)
