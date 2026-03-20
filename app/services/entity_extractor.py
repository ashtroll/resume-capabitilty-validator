"""
Entity Extractor Service — mines structured data from raw resume text.

Extracts:
  - Profile URLs (GitHub, LinkedIn, Codeforces, Kaggle, LeetCode, portfolios)
  - Social handles (@username patterns)
  - Candidate name, email, phone
  - Skills, education, experience sections
"""

import re
import logging
from typing import Optional

from app.models.schemas import ExtractedEntities, ProfileLink, Platform

logger = logging.getLogger(__name__)


# ─── URL & Handle Regex Patterns ────────────────────────────────────────────

PLATFORM_PATTERNS: dict[Platform, list[re.Pattern]] = {
    Platform.GITHUB: [
        # Match github.com/username — username is ONLY the first path segment
        # We deliberately stop at the next '/' so repo paths are not captured
        re.compile(r'(?:https?://)?(?:www\.)?github\.com/([A-Za-z0-9][A-Za-z0-9_.-]{0,38})(?:/[^\s]*)?', re.I),
    ],
    Platform.LINKEDIN: [
        re.compile(r'(?:https?://)?(?:www\.)?linkedin\.com/in/([A-Za-z0-9_.-]+)/?', re.I),
    ],
    Platform.CODEFORCES: [
        re.compile(r'(?:https?://)?(?:www\.)?codeforces\.com/profile/([A-Za-z0-9_.-]+)/?', re.I),
    ],
    Platform.KAGGLE: [
        re.compile(r'(?:https?://)?(?:www\.)?kaggle\.com/([A-Za-z0-9_.-]+)/?', re.I),
    ],
    Platform.LEETCODE: [
        re.compile(r'(?:https?://)?(?:www\.)?leetcode\.com/(?:u/)?([A-Za-z0-9_.-]+)/?', re.I),
    ],
}

# GitHub usernames that are well-known orgs/bots — skip these as profile candidates
GITHUB_ORG_BLOCKLIST = {
    "marketplace", "features", "pricing", "about", "topics", "explore",
    "trending", "collections", "events", "sponsors", "readme", "apps",
    "login", "join", "orgs", "teams",
}

# Generic URL pattern to catch portfolio sites and other links
GENERIC_URL_PATTERN = re.compile(
    r'https?://[^\s<>"{}|\\^`\[\]]+',
    re.I
)

# Email and phone patterns
EMAIL_PATTERN = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
PHONE_PATTERN = re.compile(r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}')

# Common skills (expandable list — covers the most common tech skills)
COMMON_SKILLS = {
    # Languages
    "python", "java", "javascript", "typescript", "c++", "c#", "go", "rust",
    "ruby", "php", "swift", "kotlin", "scala", "r", "matlab", "sql", "html",
    "css", "bash", "shell", "perl", "lua", "dart", "elixir", "haskell",
    # Frameworks & Libraries
    "react", "angular", "vue", "django", "flask", "fastapi", "spring",
    "express", "node.js", "next.js", "tensorflow", "pytorch", "keras",
    "scikit-learn", "pandas", "numpy", "opencv", "flutter", "rails",
    # Cloud & DevOps
    "aws", "azure", "gcp", "docker", "kubernetes", "jenkins", "terraform",
    "ansible", "ci/cd", "linux", "nginx", "apache",
    # Databases
    "mysql", "postgresql", "mongodb", "redis", "elasticsearch", "cassandra",
    "dynamodb", "sqlite", "firebase", "neo4j",
    # ML / AI
    "machine learning", "deep learning", "nlp", "computer vision",
    "reinforcement learning", "transformers", "llm", "generative ai",
    "neural networks", "data science", "data analysis",
    # Other
    "git", "rest api", "graphql", "microservices", "agile", "scrum",
    "golang", "xgboost", "shiny",
}


class EntityExtractor:
    """Extracts structured entities from raw resume text."""

    @staticmethod
    def extract(text: str) -> ExtractedEntities:
        """
        Extract all entities from resume text.

        Args:
            text: Raw text extracted from a PDF resume.

        Returns:
            ExtractedEntities with all discovered data points.
        """
        return ExtractedEntities(
            candidate_name=EntityExtractor._extract_name(text),
            email=EntityExtractor._extract_email(text),
            phone=EntityExtractor._extract_phone(text),
            profile_links=EntityExtractor._extract_profile_links(text),
            skills=EntityExtractor._extract_skills(text),
            education=EntityExtractor._extract_sections(text, "education"),
            experience=EntityExtractor._extract_sections(text, "experience"),
            raw_text=text,
        )

    @staticmethod
    def _extract_profile_links(text: str) -> list[ProfileLink]:
        """
        Extract profile URLs for known platforms + generic URLs.

        For GitHub specifically: multiple links may be present (user profile +
        individual repo links). We pick the root profile URL (shortest path)
        per platform to avoid scraping repo URLs as usernames.
        """
        # Collect all candidates per platform
        candidates: dict[Platform, list[tuple[str, str]]] = {p: [] for p in Platform}
        seen_urls: set[str] = set()

        for platform, patterns in PLATFORM_PATTERNS.items():
            for pattern in patterns:
                for match in pattern.finditer(text):
                    full_url = match.group(0).rstrip(".,;:)")
                    username = match.group(1) if match.lastindex else None

                    # Normalize URL to always have https://
                    if not full_url.startswith("http"):
                        full_url = f"https://{full_url}"

                    # For GitHub: skip org blocklist entries
                    if platform == Platform.GITHUB and username:
                        if username.lower() in GITHUB_ORG_BLOCKLIST:
                            continue

                    if username and full_url not in seen_urls:
                        seen_urls.add(full_url)
                        candidates[platform].append((username, full_url))

        links: list[ProfileLink] = []
        added_platforms: set[Platform] = set()

        for platform, entries in candidates.items():
            if not entries:
                continue

            if platform == Platform.GITHUB:
                # For GitHub: prefer the entry whose URL has fewest path segments
                # github.com/user (2 segments) beats github.com/user/repo (3 segments)
                entries_sorted = sorted(
                    entries,
                    key=lambda x: len(x[1].split("/"))
                )
                best_username, best_url = entries_sorted[0]
                # Reconstruct the clean root profile URL
                clean_url = f"https://github.com/{best_username}"
                links.append(ProfileLink(
                    platform=platform,
                    url=clean_url,
                    username=best_username,
                ))
                logger.info(f"GitHub profile identified: {best_username} (from {len(entries)} candidates)")
            else:
                # For other platforms: take first found, deduplicate by platform
                if platform not in added_platforms:
                    username, url = entries[0]
                    links.append(ProfileLink(
                        platform=platform,
                        url=url,
                        username=username,
                    ))
                    added_platforms.add(platform)

        # Extract generic portfolio URLs (not already captured above)
        known_domains = {"github.com", "linkedin.com", "codeforces.com",
                         "kaggle.com", "leetcode.com"}
        for match in GENERIC_URL_PATTERN.finditer(text):
            url = match.group(0).rstrip(".,;:)")
            if url in seen_urls:
                continue
            if not any(domain in url.lower() for domain in known_domains):
                seen_urls.add(url)
                links.append(ProfileLink(platform=Platform.PORTFOLIO, url=url))

        return links


    @staticmethod
    def _extract_email(text: str) -> Optional[str]:
        """Extract the first email address from text."""
        match = EMAIL_PATTERN.search(text)
        return match.group(0) if match else None

    @staticmethod
    def _extract_phone(text: str) -> Optional[str]:
        """Extract the first phone number from text."""
        match = PHONE_PATTERN.search(text)
        return match.group(0).strip() if match else None

    @staticmethod
    def _extract_name(text: str) -> Optional[str]:
        """
        Extract the candidate's name from the resume.

        Heuristic: The name is typically the first significant line of text
        in a resume (before email/phone/address lines).
        """
        lines = text.strip().split("\n")
        for line in lines[:5]:  # Check first 5 lines
            line = line.strip()
            if not line or len(line) < 2:
                continue
            # Skip lines that look like emails, phones, or URLs
            if EMAIL_PATTERN.search(line) or PHONE_PATTERN.search(line):
                continue
            if "http" in line.lower() or "@" in line:
                continue
            # Skip lines that are too long (likely descriptions, not names)
            if len(line) > 50:
                continue
            # A name line typically has 2-4 words, each capitalized
            words = line.split()
            if 1 <= len(words) <= 5:
                # Check if most words start with uppercase
                capitalized = sum(1 for w in words if w[0].isupper())
                if capitalized >= len(words) * 0.5:
                    return line
        return None

    @staticmethod
    def _extract_skills(text: str) -> list[str]:
        """
        Extract technical skills mentioned in the resume.
        Uses a keyword matching approach against a known skills dictionary.
        """
        text_lower = text.lower()
        found_skills = []

        for skill in COMMON_SKILLS:
            # Use word boundary matching to avoid partial matches
            # e.g., "c" shouldn't match "cache"
            pattern = r'\b' + re.escape(skill) + r'\b'
            if re.search(pattern, text_lower):
                found_skills.append(skill)

        return sorted(found_skills)

    @staticmethod
    def _extract_sections(text: str, section_type: str) -> list[str]:
        """
        Extract content from specific resume sections (education, experience).

        This uses a simple header-detection heuristic: finds lines that
        look like section headers, then captures content until the next header.
        """
        section_headers = {
            "education": [
                r"education", r"academic", r"qualification", r"degree",
                r"university", r"college",
            ],
            "experience": [
                r"experience", r"employment", r"work\s*history",
                r"professional\s*experience", r"internship",
            ],
        }

        headers = section_headers.get(section_type, [])
        if not headers:
            return []

        lines = text.split("\n")
        entries: list[str] = []
        capturing = False
        current_entry: list[str] = []

        # Common section headers that STOP capture
        all_stop_headers = [
            r"education", r"experience", r"skills", r"projects",
            r"certifications", r"publications", r"achievements",
            r"awards", r"interests", r"references", r"summary",
            r"objective", r"languages", r"hobbies", r"volunteer",
        ]

        for line in lines:
            stripped = line.strip()
            if not stripped:
                if capturing and current_entry:
                    current_entry.append("")  # Preserve paragraph breaks
                continue

            # Check if this line is a section header for our target section
            is_target_header = any(
                re.search(rf'^\s*{h}\s*$', stripped, re.I) or
                re.search(rf'^\s*{h}\s*:', stripped, re.I)
                for h in headers
            )

            if is_target_header and not capturing:
                capturing = True
                continue

            if capturing:
                # Check if we've hit a new section header (stop capturing)
                is_stop_header = any(
                    re.search(rf'^\s*{h}\s*$', stripped, re.I) or
                    re.search(rf'^\s*{h}\s*:', stripped, re.I)
                    for h in all_stop_headers
                    if h not in [re.escape(hh) for hh in headers]
                )
                if is_stop_header:
                    if current_entry:
                        entries.append("\n".join(current_entry).strip())
                    break
                current_entry.append(stripped)

        # Capture remaining if section was the last one
        if capturing and current_entry:
            entries.append("\n".join(current_entry).strip())

        return entries
