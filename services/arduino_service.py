"""
services/arduino_service.py — Low-level Arduino CLI wrapper.

This module is the ONLY place that knows how to run arduino-cli.
Every other service that needs compilation or upload goes through
the functions defined here, so changing the underlying tool (or
adding mock support for tests) only requires editing this one file.

BeaverX Pvt. Ltd. — "Building the Future of Robotics & AI"
"""

import asyncio
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

from config import (
    ARDUINO_CLI_PATH,
    ARDUINO_DATA_DIR,
    BOARD_FQBN,
    COMPILE_TIMEOUT,
    FLASH_TIMEOUT,
)

logger = logging.getLogger("beaver.arduino_service")


# ─────────────────────────────────────────────────────────────────────────────
# Result Dataclass
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CLIResult:
    """Holds the outcome of a single arduino-cli invocation."""
    success: bool
    stdout: str
    stderr: str
    return_code: int


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _base_args() -> list[str]:
    """
    Return the common CLI flags shared by every arduino-cli call.
    --config-file is omitted on purpose; we use --arduino-data-dir instead
    so we don't need to manage a separate config file on first install.
    """
    return [
        ARDUINO_CLI_PATH,
        "--no-color",                          # machine-readable output
        "--arduino-data-dir", ARDUINO_DATA_DIR, # isolated data directory
    ]


async def _run_cli(
    args: list[str],
    timeout: int,
    cwd: Path | None = None,
) -> CLIResult:
    """
    Execute arduino-cli asynchronously and capture stdout/stderr.

    We use asyncio.create_subprocess_exec (not shell=True) to avoid
    shell injection risks when user-supplied strings like port names
    pass through later.

    Args:
        args:    Full argument list, starting with the executable path.
        timeout: Maximum seconds to wait before aborting.
        cwd:     Working directory for the subprocess (None = inherit).

    Returns:
        CLIResult with all captured output.
    """
    logger.debug("Running CLI: %s", " ".join(args))

    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(cwd) if cwd else None,
        )

        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(), timeout=timeout
        )

        stdout = stdout_bytes.decode("utf-8", errors="replace").strip()
        stderr = stderr_bytes.decode("utf-8", errors="replace").strip()
        rc = proc.returncode or 0

        if rc != 0:
            logger.warning("CLI exited %d. stderr: %s", rc, stderr)
        else:
            logger.debug("CLI succeeded. stdout: %s", stdout[:300])

        return CLIResult(success=(rc == 0), stdout=stdout, stderr=stderr, return_code=rc)

    except asyncio.TimeoutError:
        logger.error("CLI timed out after %ds: %s", timeout, " ".join(args))
        # Kill the hanging process if possible.
        try:
            proc.kill()
        except Exception:
            pass
        return CLIResult(
            success=False,
            stdout="",
            stderr=f"Process timed out after {timeout} seconds.",
            return_code=-1,
        )

    except FileNotFoundError:
        # arduino-cli binary not found at the configured path.
        logger.error("arduino-cli not found at: %s", ARDUINO_CLI_PATH)
        return CLIResult(
            success=False,
            stdout="",
            stderr=(
                f"arduino-cli not found at '{ARDUINO_CLI_PATH}'. "
                "Please install Arduino CLI and ensure it is in your PATH, "
                "or place arduino-cli.exe inside the toolchains/ directory."
            ),
            return_code=-2,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def resolve_fqbn(board: str) -> str | None:
    """
    Convert a short board name (e.g. "esp32") to its FQBN.

    Returns None if the board is not in the config map, which lets the
    caller decide how to report the error rather than crashing here.
    """
    return BOARD_FQBN.get(board.lower().strip())


async def check_cli_available() -> bool:
    """
    Quick sanity check: can we actually call arduino-cli?

    Used at startup so the app can log a clear warning if the tool
    is missing rather than failing silently on the first compile request.
    """
    result = await _run_cli(
        [ARDUINO_CLI_PATH, "version", "--no-color"],
        timeout=10,
    )
    if result.success:
        logger.info("arduino-cli detected: %s", result.stdout.splitlines()[0])
    else:
        logger.warning("arduino-cli not available: %s", result.stderr)
    return result.success


async def compile_sketch(
    sketch_dir: Path,
    fqbn: str,
    build_dir: Path,
) -> CLIResult:
    """
    Compile an Arduino sketch using arduino-cli.

    Args:
        sketch_dir: Path to the folder containing the .ino file.
        fqbn:       Fully Qualified Board Name (e.g. "esp32:esp32:esp32").
        build_dir:  Where to write compiled .elf / .bin / .hex output.

    Returns:
        CLIResult — check .success and .stderr for details.
    """
    build_dir.mkdir(parents=True, exist_ok=True)

    args = _base_args() + [
        "compile",
        "--fqbn", fqbn,
        "--build-path", str(build_dir),
        "--warnings", "default",
        str(sketch_dir),
    ]

    logger.info("Compiling sketch at %s for %s", sketch_dir, fqbn)
    result = await _run_cli(args, timeout=COMPILE_TIMEOUT, cwd=sketch_dir)

    if result.success:
        logger.info("Compilation succeeded. Build artefacts in %s", build_dir)
    else:
        logger.error("Compilation failed:\n%s", result.stderr)

    return result


async def upload_firmware(
    sketch_dir: Path,
    fqbn: str,
    port: str,
    build_dir: Path,
) -> CLIResult:
    """
    Upload compiled firmware to a board over a serial port.

    arduino-cli upload can use already-compiled build artefacts so we
    don't have to recompile here — the caller is expected to run
    compile_sketch first and pass the same build_dir.

    Args:
        sketch_dir: Path to the sketch folder (needed by arduino-cli upload).
        fqbn:       Board FQBN.
        port:       Serial port (e.g. "COM3" on Windows).
        build_dir:  Directory containing the compiled firmware files.

    Returns:
        CLIResult — check .success and .stderr for details.
    """
    args = _base_args() + [
        "upload",
        "--fqbn", fqbn,
        "--port", port,
        "--input-dir", str(build_dir),
        str(sketch_dir),
    ]

    logger.info("Uploading to %s on port %s", fqbn, port)
    result = await _run_cli(args, timeout=FLASH_TIMEOUT, cwd=sketch_dir)

    if result.success:
        logger.info("Upload succeeded on port %s", port)
    else:
        logger.error("Upload failed on port %s:\n%s", port, result.stderr)

    return result


async def install_platform(platform: str) -> CLIResult:
    """
    Install a missing platform via arduino-cli core install.

    Example: install_platform("esp32:esp32")

    This is a best-effort helper — callers should check the result
    but a failure here should not crash the application.
    """
    args = _base_args() + ["core", "install", platform]
    logger.info("Installing platform: %s", platform)
    return await _run_cli(args, timeout=300)  # platform downloads can be slow


async def update_index() -> CLIResult:
    """
    Refresh the arduino-cli package index.

    Should be called once on startup (non-blocking, fire-and-forget is OK).
    Keeps the platform list fresh so new board support packages are visible.
    """
    args = _base_args() + ["core", "update-index"]
    logger.info("Updating arduino-cli package index")
    return await _run_cli(args, timeout=60)
