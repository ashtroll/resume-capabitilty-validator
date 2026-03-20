"""
GitHub Scraper — fetches public profile data via the GitHub REST API.

Extracts:
  - Profile metadata (bio, followers, account age)
  - Repository statistics (top repos, languages, stars)
  - Contribution activity (recent commits, PRs)
  - Pinned repositories

Uses authenticated requests (via GITHUB_TOKEN) for higher rate limits.
"""

import logging
from typing import Any
from datetime import datetime, timezone

import httpx

from app.config import settings
from app.services.scrapers.base import BaseScraper, ScrapingError
from app.models.schemas import GitHubProfile

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"


class GitHubScraper(BaseScraper):
    """Scrapes public GitHub profile data via the REST API."""

    platform_name = "GitHub"

    # Valid GitHub token prefixes
    _VALID_TOKEN_PREFIXES = ("ghp_", "github_pat_", "ghs_", "gho_", "ghr_")

    def __init__(self):
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "TrueCapabilityValidator/1.0",
        }
        token = settings.GITHUB_TOKEN or ""
        # Validate it's a real token, not a placeholder like 'ghp_your_token_here'
        is_real_token = (
            token
            and any(token.startswith(prefix) for prefix in self._VALID_TOKEN_PREFIXES)
            and len(token) > 20
            and "your" not in token.lower()
            and "placeholder" not in token.lower()
        )
        if is_real_token:
            self.headers["Authorization"] = f"Bearer {token}"
            logger.info("GitHub scraper initialized with authentication (5000 req/hr)")
        else:
            logger.warning("GitHub scraper running WITHOUT auth (60 req/hr rate limit). Set GITHUB_TOKEN in .env for full access.")

    async def is_profile_valid(self, username: str) -> bool:
        """Check if a GitHub user exists."""
        async with httpx.AsyncClient(timeout=settings.REQUEST_TIMEOUT) as client:
            try:
                resp = await client.get(
                    f"{GITHUB_API_BASE}/users/{username}",
                    headers=self.headers,
                )
                return resp.status_code == 200
            except httpx.RequestError:
                return False

    async def scrape(self, username: str) -> dict[str, Any]:
        """
        Scrape a GitHub user's public profile data.

        Returns a GitHubProfile dict with repos, languages, stars, and activity.
        """
        async with httpx.AsyncClient(timeout=settings.REQUEST_TIMEOUT) as client:
            try:
                # 1. Fetch user profile
                user_data = await self._fetch_user(client, username)
                if not user_data:
                    raise ScrapingError("GitHub", username, "User not found")

                # 2. Fetch repositories
                repos = await self._fetch_repos(client, username)

                # 3. Analyze repo data
                top_languages = self._analyze_languages(repos)
                total_stars = sum(r.get("stargazers_count", 0) for r in repos)
                pinned_repos = self._get_notable_repos(repos)

                # 4. Fetch recent activity (events)
                recent_activity = await self._fetch_recent_activity(client, username)

                # 5. Build profile
                profile = GitHubProfile(
                    username=username,
                    name=user_data.get("name"),
                    bio=user_data.get("bio"),
                    public_repos=user_data.get("public_repos", 0),
                    followers=user_data.get("followers", 0),
                    following=user_data.get("following", 0),
                    total_stars=total_stars,
                    top_languages=top_languages,
                    pinned_repos=pinned_repos,
                    account_created=user_data.get("created_at"),
                    recent_activity=recent_activity,
                )

                logger.info(
                    f"GitHub scrape successful: {username} — "
                    f"{profile.public_repos} repos, {total_stars} stars, "
                    f"{len(top_languages)} languages"
                )
                return profile.model_dump()

            except ScrapingError:
                raise
            except Exception as e:
                raise ScrapingError("GitHub", username, str(e))

    async def _fetch_user(self, client: httpx.AsyncClient, username: str) -> dict | None:
        """Fetch the /users/{username} endpoint."""
        resp = await client.get(
            f"{GITHUB_API_BASE}/users/{username}",
            headers=self.headers,
        )
        if resp.status_code == 200:
            return resp.json()
        rate_remaining = resp.headers.get("X-RateLimit-Remaining", "?")
        logger.warning(
            f"GitHub user fetch failed: HTTP {resp.status_code} for '{username}' "
            f"(rate limit remaining: {rate_remaining}). "
            f"{'Check GITHUB_TOKEN in .env' if resp.status_code in (401, 403) else ''}"
        )
        return None

    async def _fetch_repos(
        self, client: httpx.AsyncClient, username: str, max_pages: int = 3
    ) -> list[dict]:
        """Fetch user's public repositories (paginated, up to max_pages)."""
        all_repos = []
        for page in range(1, max_pages + 1):
            resp = await client.get(
                f"{GITHUB_API_BASE}/users/{username}/repos",
                headers=self.headers,
                params={
                    "sort": "updated",
                    "direction": "desc",
                    "per_page": 30,
                    "page": page,
                },
            )
            if resp.status_code != 200:
                break
            repos = resp.json()
            if not repos:
                break
            all_repos.extend(repos)
        return all_repos

    async def _fetch_recent_activity(
        self, client: httpx.AsyncClient, username: str
    ) -> list[dict]:
        """Fetch recent public events (last 30)."""
        resp = await client.get(
            f"{GITHUB_API_BASE}/users/{username}/events/public",
            headers=self.headers,
            params={"per_page": 30},
        )
        if resp.status_code != 200:
            return []

        events = resp.json()
        # Summarize events into a digestible format
        activity = []
        for event in events[:20]:  # Limit to 20 for readability
            activity.append({
                "type": event.get("type", ""),
                "repo": event.get("repo", {}).get("name", ""),
                "created_at": event.get("created_at", ""),
            })
        return activity

    @staticmethod
    def _analyze_languages(repos: list[dict]) -> list[str]:
        """Extract and rank programming languages across all repos."""
        lang_count: dict[str, int] = {}
        for repo in repos:
            lang = repo.get("language")
            if lang:
                lang_count[lang] = lang_count.get(lang, 0) + 1

        # Sort by frequency, return top 10
        sorted_langs = sorted(lang_count.items(), key=lambda x: x[1], reverse=True)
        return [lang for lang, _ in sorted_langs[:10]]

    @staticmethod
    def _get_notable_repos(repos: list[dict], top_n: int = 6) -> list[dict]:
        """Get the most notable repos (by stars + recent activity)."""
        # Score repos: stars * 2 + forks + (recent update bonus)
        scored_repos = []
        now = datetime.now(timezone.utc)
        for repo in repos:
            if repo.get("fork"):  # Skip forks by default
                continue
            stars = repo.get("stargazers_count", 0)
            forks = repo.get("forks_count", 0)
            updated = repo.get("updated_at", "")

            # Recency bonus: repos updated in last 90 days get a boost
            recency_bonus = 0
            if updated:
                try:
                    updated_dt = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                    days_ago = (now - updated_dt).days
                    if days_ago < 90:
                        recency_bonus = 5
                    elif days_ago < 365:
                        recency_bonus = 2
                except (ValueError, TypeError):
                    pass

            score = (stars * 2) + forks + recency_bonus
            scored_repos.append({
                "name": repo.get("name", ""),
                "description": repo.get("description", ""),
                "language": repo.get("language", ""),
                "stars": stars,
                "forks": forks,
                "url": repo.get("html_url", ""),
                "updated_at": updated,
                "score": score,
            })

        scored_repos.sort(key=lambda x: x["score"], reverse=True)
        return scored_repos[:top_n]
