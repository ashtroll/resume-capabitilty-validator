"""
Base Scraper Interface — defines the contract for all platform scrapers.
Each platform scraper (GitHub, Codeforces, etc.) must implement this interface.
"""

from abc import ABC, abstractmethod
from typing import Any
import logging

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """Abstract base class for all platform scrapers."""

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Human-readable name of the platform (e.g., 'GitHub')."""
        ...

    @abstractmethod
    async def scrape(self, username: str) -> dict[str, Any]:
        """
        Scrape public data for the given username/handle.

        Args:
            username: The user's handle on this platform.

        Returns:
            Dictionary of scraped profile data.

        Raises:
            ScrapingError: If scraping fails after retries.
        """
        ...

    @abstractmethod
    async def is_profile_valid(self, username: str) -> bool:
        """
        Quick check whether a profile exists on this platform.

        Args:
            username: The user's handle.

        Returns:
            True if the profile exists and is accessible.
        """
        ...


class ScrapingError(Exception):
    """Raised when a scraping operation fails."""
    def __init__(self, platform: str, username: str, message: str):
        self.platform = platform
        self.username = username
        super().__init__(f"[{platform}] Failed to scrape '{username}': {message}")
