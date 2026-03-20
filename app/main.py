"""
True Capability Validator — Main FastAPI Application

Entry point that wires together all routers, middleware, templates,
and startup events.

Run with:
    uvicorn app.main:app --reload --port 8000
"""

import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from app.config import settings
from app.database import init_db
from app.routers import upload, report

# ─── Logging ─────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-7s │ %(name)s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ─── Lifespan (startup / shutdown) ──────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown hooks."""
    logger.info("🚀 Starting True Capability Validator...")
    await init_db()
    settings.upload_path  # Ensure upload dir exists
    logger.info(f"   Upload dir: {settings.upload_path.resolve()}")
    logger.info(f"   Database:   {settings.database_path.resolve()}")
    logger.info("✅ Ready to validate resumes!")
    yield
    logger.info("👋 Shutting down...")


# ─── App Instance ────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "An intelligent platform that validates resume claims by "
        "cross-referencing them against public professional profiles, "
        "coding platforms, and digital footprint analysis."
    ),
    lifespan=lifespan,
)

# ─── Middleware ──────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Static files & Templates ───────────────────────────────────────────────

# Create static directories if they don't exist
static_dir = Path("app/static")
static_dir.mkdir(parents=True, exist_ok=True)
(static_dir / "css").mkdir(exist_ok=True)
(static_dir / "js").mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory="app/templates")

# ─── Routers ─────────────────────────────────────────────────────────────────

app.include_router(upload.router)
app.include_router(report.router)


# ─── Pages ───────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Serve the main upload page."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }
