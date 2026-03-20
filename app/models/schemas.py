"""
Pydantic schemas for API request/response validation and internal data structures.
These models define the shape of data flowing through the entire pipeline.
"""

from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


# ─── Enums ───────────────────────────────────────────────────────────────────

class JobStatus(str, Enum):
    PENDING = "pending"
    PARSING = "parsing"
    EXTRACTING = "extracting"
    SCRAPING = "scraping"
    SEARCHING = "searching"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"


class ConfidenceLevel(str, Enum):
    VERIFIED = "verified"           # ✅ Strong external evidence
    PARTIALLY_VERIFIED = "partial"  # ⚠️  Some supporting evidence
    UNVERIFIABLE = "unverifiable"   # ❌ No data found
    CONTRADICTED = "contradicted"   # 🚫 Evidence contradicts claim


class Platform(str, Enum):
    GITHUB = "github"
    LINKEDIN = "linkedin"
    CODEFORCES = "codeforces"
    KAGGLE = "kaggle"
    LEETCODE = "leetcode"
    PORTFOLIO = "portfolio"
    OTHER = "other"


# ─── Extracted Entities ──────────────────────────────────────────────────────

class ProfileLink(BaseModel):
    """A single extracted profile URL/handle from a resume."""
    platform: Platform
    url: str
    username: Optional[str] = None


class ExtractedEntities(BaseModel):
    """All entities extracted from a parsed resume."""
    candidate_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    profile_links: list[ProfileLink] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)
    experience: list[str] = Field(default_factory=list)
    raw_text: str = ""


# ─── Scraped Profile Data ───────────────────────────────────────────────────

class GitHubProfile(BaseModel):
    """Scraped data from a GitHub profile."""
    username: str
    name: Optional[str] = None
    bio: Optional[str] = None
    public_repos: int = 0
    followers: int = 0
    following: int = 0
    total_stars: int = 0
    total_commits_last_year: int = 0
    top_languages: list[str] = Field(default_factory=list)
    pinned_repos: list[dict] = Field(default_factory=list)
    account_created: Optional[str] = None
    recent_activity: list[dict] = Field(default_factory=list)


class CodeforcesProfile(BaseModel):
    """Scraped data from a Codeforces profile."""
    handle: str
    rating: int = 0
    max_rating: int = 0
    rank: Optional[str] = None
    max_rank: Optional[str] = None
    problems_solved: int = 0
    contests_participated: int = 0
    recent_submissions: list[dict] = Field(default_factory=list)


class ScrapedProfiles(BaseModel):
    """Aggregated scraped data from all platforms."""
    github: Optional[GitHubProfile] = None
    codeforces: Optional[CodeforcesProfile] = None
    # Extensible — add Kaggle, LinkedIn etc.
    raw_data: dict = Field(default_factory=dict)


# ─── Claim Verification ─────────────────────────────────────────────────────

class ClaimVerification(BaseModel):
    """Verification result for a single resume claim."""
    claim: str
    category: str  # e.g., "skill", "project", "experience", "education"
    confidence: ConfidenceLevel
    evidence: list[str] = Field(default_factory=list)
    score: float = Field(ge=0.0, le=1.0, default=0.5)


# ─── Final Report ────────────────────────────────────────────────────────────

class TrueCapabilityReport(BaseModel):
    """The final output — a comprehensive validation report."""
    job_id: str
    candidate_name: Optional[str] = None
    overall_score: float = Field(ge=0.0, le=100.0, default=0.0)
    ai_generated_probability: float = Field(ge=0.0, le=1.0, default=0.0)
    summary: str = ""
    claim_verifications: list[ClaimVerification] = Field(default_factory=list)
    scraped_profiles: Optional[ScrapedProfiles] = None
    web_search_findings: list[dict] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)


# ─── API Response Models ────────────────────────────────────────────────────

class UploadResponse(BaseModel):
    """Response returned after a resume is uploaded."""
    job_id: str
    status: JobStatus
    message: str


class JobStatusResponse(BaseModel):
    """Response for checking the status of an analysis job."""
    job_id: str
    status: JobStatus
    progress: Optional[str] = None
    error: Optional[str] = None
