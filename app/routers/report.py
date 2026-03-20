"""
Report Router — serves the analysis report as JSON and HTML.
"""

import json
import logging

import aiosqlite
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.database import DATABASE_PATH
from app.models.schemas import TrueCapabilityReport
from app.services.report_generator import ReportGenerator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["report"])

templates = Jinja2Templates(directory="app/templates")


@router.get("/report/{job_id}")
async def get_report_json(job_id: str):
    """Get the raw analysis report as JSON."""
    report_data = await _fetch_report(job_id)
    return json.loads(report_data)


@router.get("/report/{job_id}/view", response_class=HTMLResponse)
async def view_report(request: Request, job_id: str):
    """Render the analysis report as a styled HTML page."""
    report_data = await _fetch_report(job_id)
    report = TrueCapabilityReport(**json.loads(report_data))
    context = ReportGenerator.to_template_context(report)
    context["request"] = request
    return templates.TemplateResponse("report.html", context)


async def _fetch_report(job_id: str) -> str:
    """Fetch the report JSON from the database."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT status, report_json, error_message FROM analysis_jobs WHERE id = ?",
            (job_id,),
        )
        row = await cursor.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Job not found")

    if row["status"] == "failed":
        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed: {row['error_message']}"
        )

    if row["status"] != "completed":
        raise HTTPException(
            status_code=202,
            detail=f"Analysis still in progress. Status: {row['status']}"
        )

    if not row["report_json"]:
        raise HTTPException(status_code=500, detail="Report data is missing")

    return row["report_json"]
