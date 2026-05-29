"""
logger_setup.py — Centralised logging configuration for Beaver Connect.

Call configure_logging() once at startup (in app.py) before any other
module creates a logger. After that, every module can simply do:

    import logging
    logger = logging.getLogger("beaver.module_name")

and it will automatically inherit the correct handlers and formatter.

Log files rotate automatically when they exceed LOG_MAX_BYTES so they
don't grow unbounded on long-running installations.

BeaverX Pvt. Ltd. — "Building the Future of Robotics & AI"
"""

import logging
import logging.handlers
import sys
from pathlib import Path

from config import (
    LOG_BACKUP_COUNT,
    LOG_DATE_FORMAT,
    LOG_FORMAT,
    LOG_LEVEL,
    LOG_MAX_BYTES,
    LOGS_DIR,
)


def _make_rotating_handler(filename: str, level: int) -> logging.handlers.RotatingFileHandler:
    """
    Create a rotating file handler that writes to logs/<filename>.

    Rotation happens when the file exceeds LOG_MAX_BYTES (default 5 MB).
    Up to LOG_BACKUP_COUNT old files are kept before the oldest is deleted.
    """
    log_path: Path = LOGS_DIR / filename
    handler = logging.handlers.RotatingFileHandler(
        filename=log_path,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setLevel(level)
    return handler


def configure_logging() -> None:
    """
    Set up the root logger and module-specific file handlers.

    Log routing:
        beaver.*       → logs/app.log  (all app-level events)
        beaver.compiler_service → also logs/compile.log
        beaver.flasher_service  → also logs/flash.log
        uvicorn.*      → logs/app.log  (HTTP access + startup events)

    The console handler always goes to stderr (visible in a terminal or
    the system tray app's log window). File handlers persist history.
    """
    numeric_level = getattr(logging, LOG_LEVEL, logging.INFO)
    formatter = logging.Formatter(fmt=LOG_FORMAT, datefmt=LOG_DATE_FORMAT)

    # ── Root logger ───────────────────────────────────────────────────────────
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)  # handlers control granularity, not root

    # ── Console handler (stderr) ──────────────────────────────────────────────
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)

    # ── Main app log (all beaver.* + uvicorn.*) ───────────────────────────────
    app_handler = _make_rotating_handler("app.log", numeric_level)
    app_handler.setFormatter(formatter)

    logging.getLogger("beaver").addHandler(app_handler)
    logging.getLogger("uvicorn").addHandler(app_handler)
    logging.getLogger("uvicorn.error").addHandler(app_handler)
    logging.getLogger("uvicorn.access").addHandler(app_handler)
    logging.getLogger("fastapi").addHandler(app_handler)

    # Prevent uvicorn from spamming the root logger (it adds its own handlers).
    logging.getLogger("uvicorn").propagate = False
    logging.getLogger("uvicorn.error").propagate = False
    logging.getLogger("uvicorn.access").propagate = False

    # ── Compile log (compilation-specific events) ─────────────────────────────
    compile_handler = _make_rotating_handler("compile.log", logging.DEBUG)
    compile_handler.setFormatter(formatter)
    logging.getLogger("beaver.compiler_service").addHandler(compile_handler)
    logging.getLogger("beaver.arduino_service").addHandler(compile_handler)

    # ── Flash log (upload-specific events) ───────────────────────────────────
    flash_handler = _make_rotating_handler("flash.log", logging.DEBUG)
    flash_handler.setFormatter(formatter)
    logging.getLogger("beaver.flasher_service").addHandler(flash_handler)

    logging.getLogger("beaver").info(
        "Logging configured | level=%s | log_dir=%s", LOG_LEVEL, LOGS_DIR
    )
