"""
Codeforces Scraper — fetches competitive programming profile data via the
official Codeforces API (https://codeforces.com/apiHelp).

Extracts:
  - User info (rating, rank, max rating)
  - Contest participation history
  - Problem solving statistics
  - Recent submissions
"""

import logging
from typing import Any

import httpx

from app.config import settings
from app.services.scrapers.base import BaseScraper, ScrapingError
from app.models.schemas import CodeforcesProfile

logger = logging.getLogger(__name__)

CF_API_BASE = "https://codeforces.com/api"


class CodeforcesScraper(BaseScraper):
    """Scrapes Codeforces profiles via the official public API."""

    platform_name = "Codeforces"

    async def is_profile_valid(self, username: str) -> bool:
        """Check if a Codeforces handle exists."""
        async with httpx.AsyncClient(timeout=settings.REQUEST_TIMEOUT) as client:
            try:
                resp = await client.get(
                    f"{CF_API_BASE}/user.info",
                    params={"handles": username},
                )
                data = resp.json()
                return data.get("status") == "OK"
            except (httpx.RequestError, ValueError):
                return False

    async def scrape(self, username: str) -> dict[str, Any]:
        """
        Scrape a Codeforces user's full competitive programming profile.

        Returns a CodeforcesProfile dict with rating, contests, and submissions.
        """
        async with httpx.AsyncClient(timeout=settings.REQUEST_TIMEOUT) as client:
            try:
                # 1. Fetch user info
                user_info = await self._fetch_user_info(client, username)
                if not user_info:
                    raise ScrapingError("Codeforces", username, "User not found")

                # 2. Fetch contest history
                contests = await self._fetch_contest_history(client, username)

                # 3. Fetch recent submissions → count unique solved problems
                submissions = await self._fetch_submissions(client, username)
                solved_count = self._count_solved_problems(submissions)
                recent_subs = self._summarize_submissions(submissions)

                # 4. Build profile
                profile = CodeforcesProfile(
                    handle=username,
                    rating=user_info.get("rating", 0),
                    max_rating=user_info.get("maxRating", 0),
                    rank=user_info.get("rank"),
                    max_rank=user_info.get("maxRank"),
                    problems_solved=solved_count,
                    contests_participated=len(contests),
                    recent_submissions=recent_subs,
                )

                logger.info(
                    f"Codeforces scrape successful: {username} — "
                    f"Rating {profile.rating}, {solved_count} problems solved, "
                    f"{len(contests)} contests"
                )
                return profile.model_dump()

            except ScrapingError:
                raise
            except Exception as e:
                raise ScrapingError("Codeforces", username, str(e))

    async def _fetch_user_info(self, client: httpx.AsyncClient, handle: str) -> dict | None:
        """Fetch user.info endpoint."""
        resp = await client.get(
            f"{CF_API_BASE}/user.info",
            params={"handles": handle},
        )
        data = resp.json()
        if data.get("status") == "OK" and data.get("result"):
            return data["result"][0]
        return None

    async def _fetch_contest_history(
        self, client: httpx.AsyncClient, handle: str
    ) -> list[dict]:
        """Fetch user.rating (contest participation history)."""
        resp = await client.get(
            f"{CF_API_BASE}/user.rating",
            params={"handle": handle},
        )
        data = resp.json()
        if data.get("status") == "OK":
            return data.get("result", [])
        return []

    async def _fetch_submissions(
        self, client: httpx.AsyncClient, handle: str, count: int = 500
    ) -> list[dict]:
        """Fetch user.status (submissions), up to `count` most recent."""
        resp = await client.get(
            f"{CF_API_BASE}/user.status",
            params={"handle": handle, "from": 1, "count": count},
        )
        data = resp.json()
        if data.get("status") == "OK":
            return data.get("result", [])
        return []

    @staticmethod
    def _count_solved_problems(submissions: list[dict]) -> int:
        """Count unique problems with at least one 'OK' verdict."""
        solved = set()
        for sub in submissions:
            if sub.get("verdict") == "OK":
                problem = sub.get("problem", {})
                problem_id = f"{problem.get('contestId', '')}-{problem.get('index', '')}"
                solved.add(problem_id)
        return len(solved)

    @staticmethod
    def _summarize_submissions(submissions: list[dict], limit: int = 15) -> list[dict]:
        """Summarize recent submissions for the report."""
        summaries = []
        for sub in submissions[:limit]:
            problem = sub.get("problem", {})
            summaries.append({
                "problem_name": problem.get("name", "Unknown"),
                "problem_rating": problem.get("rating"),
                "verdict": sub.get("verdict", ""),
                "language": sub.get("programmingLanguage", ""),
                "time": sub.get("creationTimeSeconds", 0),
                "tags": problem.get("tags", []),
            })
        return summaries
