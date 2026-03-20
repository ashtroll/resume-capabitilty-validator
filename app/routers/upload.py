"""
Upload Router — handles resume file upload and triggers the analysis pipeline.
"""

import uuid
import json
import asyncio
import logging
from pathlib import Path

import aiosqlite
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks

from app.config import settings
from app.database import DATABASE_PATH
from app.models.schemas import (
    UploadResponse, JobStatus, JobStatusResponse,
    ExtractedEntities, ScrapedProfiles, Platform,
)
from app.services.pdf_parser import PDFParser
from app.services.entity_extractor import EntityExtractor
from app.services.scrapers.github import GitHubScraper
from app.services.scrapers.codeforces import CodeforcesScraper
from app.services.scrapers.linkedin import LinkedInScraper
from app.services.scrapers.kaggle import KaggleScraper
from app.services.web_search import WebSearchService
from app.services.cross_reference import CrossReferenceEngine
from app.services.ai_detector import AITextDetector
from app.services.report_generator import ReportGenerator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["upload"])


@router.post("/upload", response_model=UploadResponse)
async def upload_resume(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    """
    Upload a resume PDF for analysis.

    Returns immediately with a job_id. Processing happens in the background.
    Use /api/status/{job_id} to check progress and /api/report/{job_id} for results.
    """
    # Validate file type
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    # Validate file size
    contents = await file.read()
    max_size = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(contents) > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size is {settings.MAX_UPLOAD_SIZE_MB}MB"
        )

    # Save file
    job_id = str(uuid.uuid4())
    upload_path = settings.upload_path / f"{job_id}.pdf"
    upload_path.write_bytes(contents)

    # Create DB record
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "INSERT INTO analysis_jobs (id, status, filename) VALUES (?, ?, ?)",
            (job_id, JobStatus.PENDING.value, file.filename),
        )
        await db.commit()

    # Kick off background analysis
    background_tasks.add_task(run_analysis_pipeline, job_id, str(upload_path))

    logger.info(f"Job created: {job_id} for file: {file.filename}")

    return UploadResponse(
        job_id=job_id,
        status=JobStatus.PENDING,
        message=f"Resume '{file.filename}' uploaded successfully. Analysis started.",
    )


@router.get("/status/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """Check the current status of an analysis job."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, status, error_message FROM analysis_jobs WHERE id = ?",
            (job_id,),
        )
        row = await cursor.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobStatusResponse(
        job_id=row["id"],
        status=JobStatus(row["status"]),
        error=row["error_message"],
    )


# ─── Background Pipeline ────────────────────────────────────────────────────

async def run_analysis_pipeline(job_id: str, file_path: str):
    """
    The main analysis pipeline — runs as a background task.

    Pipeline stages:
      1. Parse PDF → raw text
      2. Extract entities (URLs, skills, name, etc.)
      3. Scrape external profiles
      4. Web search fallback
      5. Cross-reference & score
      6. AI text detection
      7. Generate final report
    """
    try:
        # ── Stage 1: Parse PDF ──────────────────────────────────────────
        await _update_job_status(job_id, JobStatus.PARSING)
        text = PDFParser.parse(file_path)

        await _update_job_field(job_id, "extracted_text", text)

        # ── Stage 2: Extract entities ───────────────────────────────────
        await _update_job_status(job_id, JobStatus.EXTRACTING)
        entities = EntityExtractor.extract(text)

        await _update_job_field(
            job_id, "extracted_entities", entities.model_dump_json()
        )

        # ── Stage 3: Scrape profiles ────────────────────────────────────
        await _update_job_status(job_id, JobStatus.SCRAPING)
        profiles = await _scrape_all_profiles(entities)

        await _update_job_field(
            job_id, "scraped_profiles", profiles.model_dump_json()
        )

        # ── Stage 4: Web search fallback ────────────────────────────────
        await _update_job_status(job_id, JobStatus.SEARCHING)
        web_results = []
        if entities.candidate_name:
            web_results = await WebSearchService.search_candidate(
                name=entities.candidate_name,
                education=entities.education,
                experience=entities.experience,
                skills=entities.skills[:5],
            )

        await _update_job_field(
            job_id, "web_search_results", json.dumps(web_results)
        )

        # ── Stage 5: Cross-reference & score ────────────────────────────
        await _update_job_status(job_id, JobStatus.ANALYZING)
        engine = CrossReferenceEngine()
        report = await engine.analyze(job_id, entities, profiles, web_results)

        # ── Stage 6: AI text detection ──────────────────────────────────
        ai_result = AITextDetector.analyze(text)
        report.ai_generated_probability = ai_result["ai_probability"]

        # ── Stage 7: Store report ───────────────────────────────────────
        report_json = ReportGenerator.to_json(report)
        await _update_job_field(job_id, "report_json", report_json)
        await _update_job_field(
            job_id, "overall_score", str(report.overall_score)
        )
        await _update_job_status(job_id, JobStatus.COMPLETED)

        logger.info(
            f"Pipeline completed for job {job_id}: "
            f"score={report.overall_score}, "
            f"ai_prob={report.ai_generated_probability}"
        )

    except Exception as e:
        logger.error(f"Pipeline failed for job {job_id}: {e}", exc_info=True)
        await _update_job_status(job_id, JobStatus.FAILED, error=str(e))


async def _scrape_all_profiles(entities: ExtractedEntities) -> ScrapedProfiles:
    """Scrape all discovered profile links concurrently."""
    from app.models.schemas import GitHubProfile, CodeforcesProfile

    profiles = ScrapedProfiles()
    raw_data = {}

    # Map platform → scraper
    scraper_map = {
        Platform.GITHUB: GitHubScraper(),
        Platform.CODEFORCES: CodeforcesScraper(),
        Platform.LINKEDIN: LinkedInScraper(),
        Platform.KAGGLE: KaggleScraper(),
    }

    # Run scrapers concurrently
    tasks = []
    for link in entities.profile_links:
        scraper = scraper_map.get(link.platform)
        if scraper and link.username:
            tasks.append(_scrape_single(scraper, link.username, link.platform))

    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                logger.warning(f"Scraper error: {result}")
                continue
            if not result:
                continue

            platform = result.get("_platform")
            data = {k: v for k, v in result.items() if k != "_platform"}

            if platform == Platform.GITHUB:
                profiles.github = GitHubProfile(**data)
            elif platform == Platform.CODEFORCES:
                profiles.codeforces = CodeforcesProfile(**data)
            else:
                raw_data[platform] = data

    profiles.raw_data = raw_data
    return profiles


async def _scrape_single(scraper, username: str, platform: Platform) -> dict:
    """Scrape a single profile and tag it with the platform."""
    data = await scraper.scrape(username)
    data["_platform"] = platform
    return data


async def _update_job_status(
    job_id: str, status: JobStatus, error: str | None = None
):
    """Update the status field of a job in the database."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        if error:
            await db.execute(
                "UPDATE analysis_jobs SET status = ?, error_message = ? WHERE id = ?",
                (status.value, error, job_id),
            )
        else:
            await db.execute(
                "UPDATE analysis_jobs SET status = ? WHERE id = ?",
                (status.value, job_id),
            )
        await db.commit()


async def _update_job_field(job_id: str, field: str, value: str):
    """Update a specific field of a job in the database."""
    # Safety: only allow known field names
    allowed_fields = {
        "extracted_text", "extracted_entities", "scraped_profiles",
        "web_search_results", "report_json", "overall_score",
    }
    if field not in allowed_fields:
        raise ValueError(f"Invalid field: {field}")

    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            f"UPDATE analysis_jobs SET {field} = ? WHERE id = ?",
            (value, job_id),
        )
        await db.commit()
