"""
Cross-Reference Engine — verifies resume claims against scraped profile data.

Uses a combination of:
  1. Rule-based heuristics (skill matching, timeline checks)
  2. LLM-powered analysis (Google Gemini) for nuanced verification

This is the core intelligence of the True Capability Validator.
"""

import logging
import json
from typing import Optional

import google.generativeai as genai

from app.config import settings
from app.models.schemas import (
    ExtractedEntities,
    ScrapedProfiles,
    ClaimVerification,
    ConfidenceLevel,
    TrueCapabilityReport,
)

logger = logging.getLogger(__name__)


class CrossReferenceEngine:
    """
    Cross-references resume claims against scraped external data
    to produce a validated capability report.
    """

    def __init__(self):
        if settings.GEMINI_API_KEY:
            genai.configure(api_key=settings.GEMINI_API_KEY)
            self.model = genai.GenerativeModel("gemini-2.0-flash")
            self.llm_available = True
            logger.info("Gemini LLM initialized for cross-reference analysis")
        else:
            self.model = None
            self.llm_available = False
            logger.warning("No GEMINI_API_KEY — using heuristic-only analysis")

    async def analyze(
        self,
        job_id: str,
        entities: ExtractedEntities,
        profiles: ScrapedProfiles,
        web_results: list[dict],
    ) -> TrueCapabilityReport:
        """
        Run the full cross-reference analysis pipeline.

        Args:
            job_id: Unique identifier for this analysis job.
            entities: Extracted resume entities.
            profiles: Scraped profile data.
            web_results: Web search findings.

        Returns:
            A complete TrueCapabilityReport.
        """
        claim_verifications: list[ClaimVerification] = []

        # 1. Verify skills against GitHub data
        if profiles.github:
            skill_verifications = self._verify_skills_against_github(
                entities.skills, profiles.github.model_dump()
            )
            claim_verifications.extend(skill_verifications)

        # 2. Verify competitive programming claims against Codeforces
        if profiles.codeforces:
            cp_verifications = self._verify_competitive_programming(
                entities, profiles.codeforces.model_dump()
            )
            claim_verifications.extend(cp_verifications)

        # 3. Check for digital presence signals
        presence_verifications = self._verify_digital_presence(
            entities, profiles, web_results
        )
        claim_verifications.extend(presence_verifications)

        # 4. LLM-powered deep analysis (if available)
        llm_analysis = None
        if self.llm_available:
            llm_analysis = await self._llm_cross_reference(
                entities, profiles, web_results
            )
            if llm_analysis:
                claim_verifications.extend(
                    llm_analysis.get("additional_verifications", [])
                )

        # 5. Compute overall score
        overall_score = self._compute_overall_score(claim_verifications, profiles)

        # 6. Identify red flags and strengths
        red_flags = self._identify_red_flags(entities, profiles, claim_verifications)
        strengths = self._identify_strengths(entities, profiles, claim_verifications)

        # 7. Generate summary
        summary = self._generate_summary(
            entities, profiles, overall_score, red_flags, strengths
        )

        return TrueCapabilityReport(
            job_id=job_id,
            candidate_name=entities.candidate_name,
            overall_score=overall_score,
            summary=summary,
            claim_verifications=claim_verifications,
            scraped_profiles=profiles,
            web_search_findings=web_results,
            red_flags=red_flags,
            strengths=strengths,
        )

    # ── Skill Verification ──────────────────────────────────────────────────

    def _verify_skills_against_github(
        self, resume_skills: list[str], github_data: dict
    ) -> list[ClaimVerification]:
        """Cross-reference claimed skills with GitHub language/repo data."""
        verifications = []
        github_languages = [lang.lower() for lang in github_data.get("top_languages", [])]
        repo_descriptions = " ".join(
            (r.get("description") or "").lower()
            for r in github_data.get("pinned_repos", [])
        )

        for skill in resume_skills:
            skill_lower = skill.lower()

            # Direct language match
            if skill_lower in github_languages:
                verifications.append(ClaimVerification(
                    claim=f"Skill: {skill}",
                    category="skill",
                    confidence=ConfidenceLevel.VERIFIED,
                    evidence=[f"Found in GitHub top languages: {github_languages}"],
                    score=0.9,
                ))
            # Match in repo descriptions
            elif skill_lower in repo_descriptions:
                verifications.append(ClaimVerification(
                    claim=f"Skill: {skill}",
                    category="skill",
                    confidence=ConfidenceLevel.PARTIALLY_VERIFIED,
                    evidence=[f"Mentioned in GitHub repository descriptions"],
                    score=0.6,
                ))
            else:
                verifications.append(ClaimVerification(
                    claim=f"Skill: {skill}",
                    category="skill",
                    confidence=ConfidenceLevel.UNVERIFIABLE,
                    evidence=["No evidence found on GitHub"],
                    score=0.3,
                ))

        return verifications

    # ── Competitive Programming Verification ────────────────────────────────

    def _verify_competitive_programming(
        self, entities: ExtractedEntities, cf_data: dict
    ) -> list[ClaimVerification]:
        """Verify competitive programming claims against Codeforces data."""
        verifications = []
        rating = cf_data.get("rating", 0)
        max_rating = cf_data.get("max_rating", 0)
        problems_solved = cf_data.get("problems_solved", 0)
        contests = cf_data.get("contests_participated", 0)

        # Verify the Codeforces profile itself
        if rating > 0:
            rating_claim = f"Codeforces rating: {rating} (max: {max_rating})"
            verifications.append(ClaimVerification(
                claim=rating_claim,
                category="competitive_programming",
                confidence=ConfidenceLevel.VERIFIED,
                evidence=[
                    f"Current rating: {rating}",
                    f"Max rating: {max_rating}",
                    f"Rank: {cf_data.get('rank', 'N/A')}",
                    f"Problems solved: {problems_solved}",
                    f"Contests participated: {contests}",
                ],
                score=min(rating / 2000, 1.0),  # Normalize: 2000+ = 1.0
            ))

        # Look for CP-related claims in resume text
        resume_text = entities.raw_text.lower()
        if "competitive programming" in resume_text or "codeforces" in resume_text:
            if problems_solved > 100:
                verifications.append(ClaimVerification(
                    claim="Active competitive programmer",
                    category="competitive_programming",
                    confidence=ConfidenceLevel.VERIFIED,
                    evidence=[f"Solved {problems_solved} problems on Codeforces"],
                    score=0.85,
                ))
            elif problems_solved > 0:
                verifications.append(ClaimVerification(
                    claim="Active competitive programmer",
                    category="competitive_programming",
                    confidence=ConfidenceLevel.PARTIALLY_VERIFIED,
                    evidence=[f"Solved {problems_solved} problems (limited activity)"],
                    score=0.5,
                ))

        return verifications

    # ── Digital Presence ────────────────────────────────────────────────────

    def _verify_digital_presence(
        self,
        entities: ExtractedEntities,
        profiles: ScrapedProfiles,
        web_results: list[dict],
    ) -> list[ClaimVerification]:
        """Check the overall digital footprint of the candidate."""
        verifications = []
        presence_signals = 0

        if profiles.github:
            presence_signals += 1
        if profiles.codeforces:
            presence_signals += 1
        if len(entities.profile_links) > 2:
            presence_signals += 1
        if web_results:
            presence_signals += 1

        if presence_signals >= 3:
            verifications.append(ClaimVerification(
                claim="Strong digital presence",
                category="digital_footprint",
                confidence=ConfidenceLevel.VERIFIED,
                evidence=[
                    f"Found {len(entities.profile_links)} profile links",
                    f"Web search returned {len(web_results)} results",
                ],
                score=0.9,
            ))
        elif presence_signals >= 1:
            verifications.append(ClaimVerification(
                claim="Moderate digital presence",
                category="digital_footprint",
                confidence=ConfidenceLevel.PARTIALLY_VERIFIED,
                evidence=[f"Found {presence_signals} online signals"],
                score=0.5,
            ))
        else:
            verifications.append(ClaimVerification(
                claim="Minimal digital presence",
                category="digital_footprint",
                confidence=ConfidenceLevel.UNVERIFIABLE,
                evidence=["Very limited online presence found"],
                score=0.2,
            ))

        return verifications

    # ── LLM Cross-Reference ─────────────────────────────────────────────────

    async def _llm_cross_reference(
        self,
        entities: ExtractedEntities,
        profiles: ScrapedProfiles,
        web_results: list[dict],
    ) -> Optional[dict]:
        """Use Gemini to perform nuanced cross-reference analysis."""
        if not self.llm_available:
            return None

        prompt = f"""You are an expert resume fraud detector. Analyze the following resume data
against the scraped external profile data. Identify any inconsistencies, red flags,
or verified claims.

RESUME DATA:
- Name: {entities.candidate_name}
- Skills: {', '.join(entities.skills)}
- Education: {'; '.join(entities.education)}
- Experience: {'; '.join(entities.experience)}

GITHUB DATA:
{json.dumps(profiles.github.model_dump() if profiles.github else {}, indent=2, default=str)}

CODEFORCES DATA:
{json.dumps(profiles.codeforces.model_dump() if profiles.codeforces else {}, indent=2, default=str)}

WEB SEARCH RESULTS:
{json.dumps(web_results[:5], indent=2, default=str)}

Respond in this exact JSON format:
{{
    "analysis_summary": "Brief analysis of the candidate's resume validity",
    "inconsistencies": ["list of any inconsistencies between resume and external data"],
    "verified_claims": ["list of claims that are well-supported by external data"],
    "additional_verifications": [],
    "credibility_score": 0.0-1.0
}}

Respond ONLY with valid JSON, no other text."""

        try:
            response = self.model.generate_content(prompt)
            response_text = response.text.strip()

            # Strip markdown code fences if present
            if response_text.startswith("```"):
                response_text = response_text.split("\n", 1)[1]
                response_text = response_text.rsplit("```", 1)[0]

            result = json.loads(response_text)
            logger.info("LLM cross-reference analysis completed")
            return result
        except Exception as e:
            logger.warning(f"LLM cross-reference failed: {e}")
            return None

    # ── Scoring ─────────────────────────────────────────────────────────────

    def _compute_overall_score(
        self,
        verifications: list[ClaimVerification],
        profiles: ScrapedProfiles,
    ) -> float:
        """Compute the overall True Capability Score (0-100)."""
        if not verifications:
            return 25.0  # Base score when no verification is possible

        # Weighted average of claim scores
        total_score = sum(v.score for v in verifications)
        avg_score = total_score / len(verifications)

        # Bonus for strong profiles
        bonus = 0.0
        if profiles.github and profiles.github.public_repos > 10:
            bonus += 5.0
        if profiles.github and profiles.github.total_stars > 5:
            bonus += 5.0
        if profiles.codeforces and profiles.codeforces.rating > 1200:
            bonus += 5.0
        if profiles.codeforces and profiles.codeforces.problems_solved > 200:
            bonus += 5.0

        return min(round(avg_score * 80 + bonus + 10, 1), 100.0)

    # ── Red Flags & Strengths ───────────────────────────────────────────────

    def _identify_red_flags(
        self,
        entities: ExtractedEntities,
        profiles: ScrapedProfiles,
        verifications: list[ClaimVerification],
    ) -> list[str]:
        """Identify potential red flags in the resume."""
        flags = []

        # Many skills, few verifiable
        unverifiable = [
            v for v in verifications
            if v.confidence == ConfidenceLevel.UNVERIFIABLE and v.category == "skill"
        ]
        if len(unverifiable) > len(entities.skills) * 0.6:
            flags.append(
                f"{len(unverifiable)}/{len(entities.skills)} claimed skills "
                "could not be verified against external profiles"
            )

        # GitHub account very new but claims years of experience
        if profiles.github and profiles.github.public_repos < 3:
            flags.append("GitHub profile has very few public repositories")

        # No profile links in resume
        if not entities.profile_links:
            flags.append("Resume contains no links to professional profiles")

        # Contradicted claims
        contradictions = [
            v for v in verifications
            if v.confidence == ConfidenceLevel.CONTRADICTED
        ]
        for c in contradictions:
            flags.append(f"Contradicted claim: {c.claim}")

        return flags

    def _identify_strengths(
        self,
        entities: ExtractedEntities,
        profiles: ScrapedProfiles,
        verifications: list[ClaimVerification],
    ) -> list[str]:
        """Identify verified strengths of the candidate."""
        strengths = []

        verified = [
            v for v in verifications
            if v.confidence == ConfidenceLevel.VERIFIED
        ]

        if len(verified) > 3:
            strengths.append(f"{len(verified)} claims verified against external data")

        if profiles.github:
            gh = profiles.github
            if gh.total_stars > 10:
                strengths.append(f"GitHub repos have {gh.total_stars} total stars")
            if gh.followers > 20:
                strengths.append(f"{gh.followers} GitHub followers")
            if len(gh.top_languages) >= 3:
                strengths.append(
                    f"Proficient in {len(gh.top_languages)} languages on GitHub"
                )

        if profiles.codeforces:
            cf = profiles.codeforces
            if cf.rating >= 1400:
                strengths.append(f"Codeforces rating: {cf.rating} ({cf.rank})")
            if cf.problems_solved > 200:
                strengths.append(f"Solved {cf.problems_solved} problems on Codeforces")

        return strengths

    def _generate_summary(
        self,
        entities: ExtractedEntities,
        profiles: ScrapedProfiles,
        score: float,
        red_flags: list[str],
        strengths: list[str],
    ) -> str:
        """Generate a human-readable summary paragraph."""
        name = entities.candidate_name or "The candidate"

        if score >= 75:
            verdict = "shows strong alignment between resume claims and verifiable online activity"
        elif score >= 50:
            verdict = "has moderate external verification for resume claims"
        elif score >= 30:
            verdict = "has limited verifiable evidence supporting resume claims"
        else:
            verdict = "lacks sufficient external evidence to validate resume claims"

        parts = [f"{name} {verdict} (score: {score}/100)."]

        if strengths:
            parts.append(f"Key strengths: {'; '.join(strengths[:3])}.")
        if red_flags:
            parts.append(f"Concerns: {'; '.join(red_flags[:3])}.")

        return " ".join(parts)
