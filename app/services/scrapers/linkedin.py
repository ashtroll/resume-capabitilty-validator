"""
LinkedIn Scraper — STUB implementation.

LinkedIn aggressively blocks automated scraping and its Terms of Service
prohibit it. This stub provides the interface for future implementation
via LinkedIn's official API or manual data input.
"""

import logging
from typing import Any

from app.services.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class LinkedInScraper(BaseScraper):
    """
    Stub scraper for LinkedIn profiles.

    NOTE: Full implementation requires LinkedIn API access (OAuth 2.0)
    or risks being blocked/banned. For the hackathon, we accept LinkedIn
    URLs but don't scrape them — instead, we note their existence as a
    positive signal in the report.
    """

    platform_name = "LinkedIn"

    async def is_profile_valid(self, username: str) -> bool:
        """LinkedIn profiles can't be easily validated without API access."""
        logger.info(f"LinkedIn validation skipped for '{username}' (stub)")
        return True  # Assume valid if URL was found in resume

    async def scrape(self, username: str) -> dict[str, Any]:
        """Return a stub indicating LinkedIn data was not scraped."""
        logger.info(f"LinkedIn scraping skipped for '{username}' (stub)")
        return {
            "platform": "linkedin",
            "username": username,
            "status": "stub",
            "note": (
                "LinkedIn scraping is not implemented due to ToS restrictions. "
                "The presence of a LinkedIn profile URL is noted as a positive signal."
            ),
            "profile_url": f"https://linkedin.com/in/{username}",
        }
