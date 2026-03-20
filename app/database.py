"""
Database module — async SQLite setup using aiosqlite.
Manages the analysis_jobs table that tracks each resume validation run.
"""

import aiosqlite
from pathlib import Path
from app.config import settings

DATABASE_PATH = str(settings.database_path)


async def get_db() -> aiosqlite.Connection:
    """Get a database connection. Used as a FastAPI dependency."""
    db = await aiosqlite.connect(DATABASE_PATH)
    db.row_factory = aiosqlite.Row
    try:
        yield db
    finally:
        await db.close()


async def init_db():
    """Create tables if they don't exist. Called on app startup."""
    Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS analysis_jobs (
                id TEXT PRIMARY KEY,
                status TEXT NOT NULL DEFAULT 'pending',
                filename TEXT NOT NULL,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,

                -- Extracted data (stored as JSON strings)
                extracted_text TEXT,
                extracted_entities TEXT,

                -- Scraped profile data
                scraped_profiles TEXT,

                -- Web search results
                web_search_results TEXT,

                -- Final report
                report_json TEXT,
                overall_score REAL,

                -- Error tracking
                error_message TEXT
            )
        """)
        await db.commit()
