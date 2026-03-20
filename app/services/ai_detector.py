"""
AI-Generated Text Detector — flags sections of resume that may be LLM-written.

Uses a simple perplexity-based heuristic for the hackathon:
  - LLM-generated text tends to have very low perplexity (too "smooth")
  - Human-written text has higher and more variable perplexity

For a hackathon MVP, this uses simple statistical features. A production
system would use a fine-tuned classifier or tools like GPTZero/Binoculars.
"""

import re
import math
import logging
from collections import Counter

logger = logging.getLogger(__name__)


class AITextDetector:
    """
    Detects potentially AI-generated text in resumes using
    statistical text analysis heuristics.
    """

    # Common "buzzword-heavy" phrases that LLMs tend to generate
    AI_INDICATOR_PHRASES = [
        "leveraged", "spearheaded", "orchestrated", "synergized",
        "cutting-edge", "state-of-the-art", "innovative solutions",
        "passionate about", "driven individual", "proven track record",
        "results-oriented", "self-motivated", "dynamic environment",
        "cross-functional", "stakeholder management",
        "actionable insights", "paradigm shift", "holistic approach",
        "seamlessly integrated", "robust and scalable",
        "end-to-end", "deep expertise", "thought leader",
    ]

    @staticmethod
    def analyze(text: str) -> dict:
        """
        Analyze text for AI-generated content signals.

        Args:
            text: The resume text to analyze.

        Returns:
            Dict with ai_probability (0.0-1.0), signals, and details.
        """
        signals: list[str] = []
        scores: list[float] = []

        # 1. Buzzword density check
        buzzword_score = AITextDetector._check_buzzword_density(text)
        scores.append(buzzword_score)
        if buzzword_score > 0.5:
            signals.append(
                f"High density of AI-typical buzzwords ({buzzword_score:.2f})"
            )

        # 2. Sentence uniformity check (LLMs write very uniform sentences)
        uniformity_score = AITextDetector._check_sentence_uniformity(text)
        scores.append(uniformity_score)
        if uniformity_score > 0.6:
            signals.append(
                f"Unusually uniform sentence structure ({uniformity_score:.2f})"
            )

        # 3. Vocabulary richness (LLMs tend to use diverse vocabulary)
        vocab_score = AITextDetector._check_vocabulary_richness(text)
        scores.append(vocab_score)
        if vocab_score > 0.5:
            signals.append(
                f"Vocabulary pattern consistent with AI generation ({vocab_score:.2f})"
            )

        # 4. Repetitive patterns
        repetition_score = AITextDetector._check_repetitive_patterns(text)
        scores.append(repetition_score)
        if repetition_score > 0.5:
            signals.append(
                f"Repetitive structural patterns detected ({repetition_score:.2f})"
            )

        # Weighted average
        weights = [0.35, 0.25, 0.20, 0.20]
        ai_probability = sum(s * w for s, w in zip(scores, weights))
        ai_probability = max(0.0, min(1.0, ai_probability))

        return {
            "ai_probability": round(ai_probability, 3),
            "signals": signals,
            "details": {
                "buzzword_score": round(buzzword_score, 3),
                "uniformity_score": round(uniformity_score, 3),
                "vocabulary_score": round(vocab_score, 3),
                "repetition_score": round(repetition_score, 3),
            },
            "verdict": AITextDetector._get_verdict(ai_probability),
        }

    @staticmethod
    def _check_buzzword_density(text: str) -> float:
        """Score based on density of AI-typical buzzwords/phrases."""
        text_lower = text.lower()
        word_count = len(text_lower.split())
        if word_count == 0:
            return 0.0

        matches = sum(
            1 for phrase in AITextDetector.AI_INDICATOR_PHRASES
            if phrase in text_lower
        )

        # Normalize: 5+ matches in a typical resume (300-500 words) is suspicious
        density = matches / max(word_count / 100, 1)
        return min(density / 3.0, 1.0)

    @staticmethod
    def _check_sentence_uniformity(text: str) -> float:
        """
        LLM text tends to have very uniform sentence lengths.
        Human writing has more variation.
        """
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 10]

        if len(sentences) < 3:
            return 0.0

        lengths = [len(s.split()) for s in sentences]
        mean_len = sum(lengths) / len(lengths)
        variance = sum((l - mean_len) ** 2 for l in lengths) / len(lengths)
        std_dev = math.sqrt(variance)

        # Low std dev relative to mean → suspicious uniformity
        coefficient_of_variation = std_dev / mean_len if mean_len > 0 else 0

        # CV below 0.3 is suspiciously uniform
        if coefficient_of_variation < 0.2:
            return 0.8
        elif coefficient_of_variation < 0.3:
            return 0.5
        elif coefficient_of_variation < 0.4:
            return 0.3
        return 0.1

    @staticmethod
    def _check_vocabulary_richness(text: str) -> float:
        """
        Measure Type-Token Ratio (TTR).
        LLMs tend to use a wider vocabulary than typical human resume writers.
        """
        words = re.findall(r'\b[a-zA-Z]+\b', text.lower())
        if len(words) < 20:
            return 0.0

        unique_words = set(words)
        ttr = len(unique_words) / len(words)

        # In resumes, TTR > 0.7 with common words can indicate AI generation
        if ttr > 0.75:
            return 0.7
        elif ttr > 0.65:
            return 0.4
        return 0.1

    @staticmethod
    def _check_repetitive_patterns(text: str) -> float:
        """Check for repetitive structural patterns (e.g., bullet point starts)."""
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        if len(lines) < 5:
            return 0.0

        # Check first words of lines
        first_words = [l.split()[0].lower() if l.split() else "" for l in lines]
        word_counts = Counter(first_words)

        # If any single word starts > 30% of lines, that's a pattern
        most_common_count = word_counts.most_common(1)[0][1] if word_counts else 0
        repetition_ratio = most_common_count / len(lines)

        if repetition_ratio > 0.4:
            return 0.8
        elif repetition_ratio > 0.3:
            return 0.5
        return 0.1

    @staticmethod
    def _get_verdict(probability: float) -> str:
        """Human-readable verdict based on AI probability."""
        if probability >= 0.7:
            return "High likelihood of AI-generated content"
        elif probability >= 0.4:
            return "Moderate indicators of AI-generated content"
        elif probability >= 0.2:
            return "Low indicators of AI-generated content"
        return "Appears to be human-written"
