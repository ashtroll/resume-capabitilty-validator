"""
Kaggle Scraper — STUB implementation.

Kaggle's public API offers limited profile data. This stub provides the
interface for future implementation.
"""

import logging
from typing import Any

from app.services.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class KaggleScraper(BaseScraper):
    """Stub scraper for Kaggle profiles."""

    platform_name = "Kaggle"

    async def is_profile_valid(self, username: str) -> bool:
        logger.info(f"Kaggle validation skipped for '{username}' (stub)")
        return True

    async def scrape(self, username: str) -> dict[str, Any]:
        logger.info(f"Kaggle scraping skipped for '{username}' (stub)")
        return {
            "platform": "kaggle",
            "username": username,
            "status": "stub",
            "note": "Kaggle scraping is pending implementation.",
            "profile_url": f"https://kaggle.com/{username}",
        }
