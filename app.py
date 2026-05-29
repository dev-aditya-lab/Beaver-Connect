"""
app.py — Entry point and FastAPI application factory for Beaver Connect.

This file does three things:
  1. Wires the FastAPI app together (middleware, routers, event hooks).
  2. Starts the Uvicorn server when run directly (`python app.py`).
  3. Can be imported as a module by PyInstaller's entry-point shim or
     by test code without launching a server.

Architecture overview:
    Website (code.beaverlab.in)
        ↓  HTTP  (CORS-restricted to known origins)
    localhost:8765  ← this file owns that address
        ↓
    routes/  ←  thin HTTP layer, input validation, error mapping
        ↓
    services/ ← business logic, no HTTP knowledge
        ↓
    arduino-cli  ←  the actual build/upload tool

BeaverX Pvt. Ltd. — "Building the Future of Robotics & AI"
"""

import asyncio
import logging

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Logging must be configured BEFORE any other beaver.* module is imported
# because those modules create module-level loggers on import.
from logger_setup import configure_logging
configure_logging()

from config import (
    ALLOWED_ORIGINS,
    APP_NAME,
    APP_VERSION,
    COMPANY,
    SERVER_HOST,
    SERVER_PORT,
    TAGLINE,
)
from routes import boards, compile, flash, health
from services.arduino_service import check_cli_available, update_index

logger = logging.getLogger("beaver.app")


# ─────────────────────────────────────────────────────────────────────────────
# FastAPI Application
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title=APP_NAME,
    description=(
        f"{COMPANY} — {TAGLINE}\n\n"
        "Local companion API for the BeaverLab Blockly robotics platform. "
        "Handles board detection, code compilation, and firmware flashing "
        "via the bundled Arduino CLI."
    ),
    version=APP_VERSION,
    docs_url="/docs",       # Swagger UI available at http://127.0.0.1:8765/docs
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)


# ─────────────────────────────────────────────────────────────────────────────
# CORS Middleware
# ─────────────────────────────────────────────────────────────────────────────
# Only the BeaverLab website origins are allowed to call this API.
# All other origins are blocked at this layer — the routers never see the
# request.  Binding to 127.0.0.1 (loopback only) is a second line of defence.

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,          # needed if the website sends session cookies
    allow_methods=["GET", "POST"],   # only the verbs our routes actually use
    allow_headers=["Content-Type", "Authorization"],
)


# ─────────────────────────────────────────────────────────────────────────────
# Global Exception Handler
# ─────────────────────────────────────────────────────────────────────────────
# Catches anything that escapes route-level try/except blocks and returns
# a structured JSON error instead of a plain-text 500 page.

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "An internal server error occurred. Check logs/app.log for details.",
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# Startup / Shutdown Lifecycle Hooks
# ─────────────────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def on_startup() -> None:
    """
    Run once when the server starts.

    We check that arduino-cli is accessible and kick off a background
    package-index update. Neither operation blocks server startup — if
    arduino-cli is missing we log a warning but still serve /health and
    /boards so the website can display a meaningful status message.
    """
    logger.info("=" * 60)
    logger.info("%s v%s starting up", APP_NAME, APP_VERSION)
    logger.info("%s — %s", COMPANY, TAGLINE)
    logger.info("Listening on http://%s:%d", SERVER_HOST, SERVER_PORT)
    logger.info("=" * 60)

    # Non-blocking check — we don't await the index update.
    cli_ok = await check_cli_available()
    if not cli_ok:
        logger.warning(
            "arduino-cli is NOT available. Compilation and flashing will fail "
            "until arduino-cli is installed. See README.md for setup instructions."
        )
    else:
        # Fire-and-forget index update so it doesn't delay server startup.
        # asyncio.ensure_future schedules it on the running event loop.
        asyncio.ensure_future(update_index())


@app.on_event("shutdown")
async def on_shutdown() -> None:
    """Run once when the server is stopping (Ctrl-C or OS signal)."""
    logger.info("%s shutting down.", APP_NAME)


# ─────────────────────────────────────────────────────────────────────────────
# Route Registration
# ─────────────────────────────────────────────────────────────────────────────
# Each router is defined in its own file under routes/.
# Adding a new feature = creating a new route file and one line here.

app.include_router(health.router, tags=["System"])
app.include_router(boards.router, tags=["Hardware"])
app.include_router(compile.router, tags=["Build"])
app.include_router(flash.router,   tags=["Build"])


# ─────────────────────────────────────────────────────────────────────────────
# Root Route (informational)
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
async def root() -> dict:
    """
    Landing page for humans who accidentally open the API in a browser.
    Not used by the website — the website calls /health instead.
    """
    return {
        "app": APP_NAME,
        "version": APP_VERSION,
        "company": COMPANY,
        "docs": f"http://{SERVER_HOST}:{SERVER_PORT}/docs",
        "health": f"http://{SERVER_HOST}:{SERVER_PORT}/health",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Run via: python app.py
    # The server binds to loopback only — never 0.0.0.0.
    uvicorn.run(
        "app:app",
        host=SERVER_HOST,
        port=SERVER_PORT,
        reload=False,          # reload=True breaks PyInstaller bundles
        log_level="warning",   # uvicorn's own logs; our handlers cover the rest
        access_log=True,
    )
