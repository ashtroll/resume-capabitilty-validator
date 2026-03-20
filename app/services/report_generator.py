"""
Report Generator — assembles all analysis results into the final
True Capability Report and formats it for display.
"""

import json
import logging
from typing import Optional

from app.models.schemas import TrueCapabilityReport

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generates the final True Capability Report from analysis data."""

    @staticmethod
    def to_json(report: TrueCapabilityReport) -> str:
        """Serialize the report to a JSON string for storage/API response."""
        return report.model_dump_json(indent=2)

    @staticmethod
    def to_template_context(report: TrueCapabilityReport) -> dict:
        """
        Convert the report into a template-friendly context dict
        for rendering in Jinja2 templates.
        """
        data = report.model_dump()

        # Add computed display fields
        data["score_color"] = ReportGenerator._score_to_color(report.overall_score)
        data["score_label"] = ReportGenerator._score_to_label(report.overall_score)
        data["ai_verdict_color"] = ReportGenerator._ai_probability_color(
            report.ai_generated_probability
        )

        # Group verifications by category
        grouped_verifications = {}
        for v in report.claim_verifications:
            category = v.category
            if category not in grouped_verifications:
                grouped_verifications[category] = []
            grouped_verifications[category].append(v.model_dump())

        data["grouped_verifications"] = grouped_verifications

        # Confidence distribution
        confidence_counts = {"verified": 0, "partial": 0, "unverifiable": 0, "contradicted": 0}
        for v in report.claim_verifications:
            confidence_counts[v.confidence.value] = (
                confidence_counts.get(v.confidence.value, 0) + 1
            )
        data["confidence_distribution"] = confidence_counts

        return data

    @staticmethod
    def _score_to_color(score: float) -> str:
        """Map score to a CSS-compatible color for the UI."""
        if score >= 75:
            return "#22c55e"  # Green
        elif score >= 50:
            return "#eab308"  # Yellow
        elif score >= 30:
            return "#f97316"  # Orange
        return "#ef4444"  # Red

    @staticmethod
    def _score_to_label(score: float) -> str:
        """Map score to a human-readable label."""
        if score >= 75:
            return "Strong Match"
        elif score >= 50:
            return "Moderate Match"
        elif score >= 30:
            return "Weak Match"
        return "Insufficient Evidence"

    @staticmethod
    def _ai_probability_color(probability: float) -> str:
        """Color coding for AI-generated probability."""
        if probability >= 0.7:
            return "#ef4444"  # Red — high AI probability
        elif probability >= 0.4:
            return "#f97316"  # Orange — moderate
        return "#22c55e"  # Green — likely human
