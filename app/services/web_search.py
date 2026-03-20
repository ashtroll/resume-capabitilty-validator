"""
Web Search Service — fallback digital footprint discovery using DuckDuckGo.

Used when the resume lacks profile links or when we need to discover
additional online presence for identity verification.
"""

import logging
from typing import Any

from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)


class WebSearchService:
    """
    Performs targeted web searches to discover a candidate's digital footprint.
    Uses DuckDuckGo (no API key required, free for hackathon use).
    """

    @staticmethod
    async def search_candidate(
        name: str,
        education: list[str] | None = None,
        experience: list[str] | None = None,
        skills: list[str] | None = None,
        max_results: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Search for a candidate's digital footprint using multiple queries.

        Args:
            name: Candidate's full name.
            education: Educational institutions for disambiguation.
            experience: Companies/roles for disambiguation.
            skills: Key skills to refine search.
            max_results: Maximum results per query.

        Returns:
            List of search result dicts with title, url, and snippet.
        """
        queries = WebSearchService._build_search_queries(
            name, education, experience, skills
        )

        all_results: list[dict] = []
        seen_urls: set[str] = set()

        for query in queries:
            try:
                results = WebSearchService._execute_search(query, max_results)
                for result in results:
                    url = result.get("href", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        all_results.append({
                            "query": query,
                            "title": result.get("title", ""),
                            "url": url,
                            "snippet": result.get("body", ""),
                        })
            except Exception as e:
                logger.warning(f"Search failed for query '{query}': {e}")
                continue

        logger.info(f"Web search found {len(all_results)} unique results for '{name}'")
        return all_results

    @staticmethod
    def _build_search_queries(
        name: str,
        education: list[str] | None,
        experience: list[str] | None,
        skills: list[str] | None,
    ) -> list[str]:
        """Build a set of targeted search queries for the candidate."""
        queries = []

        # Basic name searches on developer platforms
        queries.append(f'"{name}" site:github.com')
        queries.append(f'"{name}" site:linkedin.com')
        queries.append(f'"{name}" developer OR engineer OR programmer')

        # Add disambiguation via education
        if education:
            # Use first educational institution
            edu_str = education[0][:100]  # Truncate long entries
            queries.append(f'"{name}" {edu_str}')

        # Add disambiguation via experience
        if experience:
            exp_str = experience[0][:100]
            queries.append(f'"{name}" {exp_str}')

        # Skill-specific searches
        if skills and len(skills) >= 2:
            top_skills = " ".join(skills[:3])
            queries.append(f'"{name}" {top_skills}')

        return queries

    @staticmethod
    def _execute_search(query: str, max_results: int) -> list[dict]:
        """Execute a single DuckDuckGo search query."""
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        return results
