"""Evaluate whether a discovered string is suitable for translation.

The original text is never modified. Control-code stripping is only used to
score a candidate, so the parser can still write the exact source text back.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


CONTROL_CODE_PATTERN = re.compile(r"\\[A-Za-z]+\[[^\]]*\]|\\[{}$.|!><^]")
TAG_PATTERN = re.compile(r"<[^>\n]+>")
PATH_PREFIX_PATTERN = re.compile(r"^(?:[a-zA-Z]:[\\/]|\.{0,2}/|www/|img/|audio/|data/|js/)", re.I)
FILE_EXTENSION_PATTERN = re.compile(r"\.(?:png|jpe?g|webp|ogg|mp3|wav|m4a|json|js|dll|exe|rpy|rvdata2)$", re.I)
URL_PATTERN = re.compile(r"^(?:https?://|www\.)", re.I)
IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]*(?:\.[A-Za-z_$][A-Za-z0-9_$]*)*$")
CODE_ONLY_PATTERN = re.compile(r"^[\d\s.,+\-*/%()[\]{}<>:=]+$")
CJK_PATTERN = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uff00-\uffef]")
NATURAL_PUNCTUATION_PATTERN = re.compile(r"[。！？…「」『』!?]")


@dataclass(frozen=True)
class CandidateEvaluation:
    decision: str  # accept, review, reject
    score: int
    analysis_text: str
    reason: Optional[str] = None


def strip_control_codes_for_analysis(text: str) -> str:
    """Remove game control codes and tags from an analysis-only copy of text."""
    return TAG_PATTERN.sub("", CONTROL_CODE_PATTERN.sub("", text)).strip()


def _hard_reject(text: str) -> Optional[str]:
    if not text:
        return "empty"
    if len(text) == 1 and not text.isalnum():
        return "punctuation"
    if CODE_ONLY_PATTERN.fullmatch(text):
        return "code-only"
    if text.lower() in {"true", "false", "null", "undefined", "nan"}:
        return "literal"
    if PATH_PREFIX_PATTERN.match(text) or FILE_EXTENSION_PATTERN.search(text):
        return "resource-path"
    if URL_PATTERN.match(text):
        return "url"
    return None


def evaluate_candidate(
    raw_text: str,
    *,
    source_type: str,
    field: Optional[str] = None,
) -> CandidateEvaluation:
    """Score structured, script, and generic candidates consistently."""
    analysis_text = strip_control_codes_for_analysis(raw_text)
    reason = _hard_reject(analysis_text)
    if reason:
        return CandidateEvaluation("reject", 0, analysis_text, reason)

    score = 0
    if source_type == "event":
        score += 50
    elif source_type == "database":
        score += 45
    elif source_type == "runtime":
        score += 40
    elif source_type == "script":
        score += 10

    if field in {"name", "nickname", "description", "profile", "displayName", "gameTitle", "message"}:
        score += 20
    if CJK_PATTERN.search(analysis_text):
        score += 25
    if NATURAL_PUNCTUATION_PATTERN.search(analysis_text):
        score += 10
    if len(analysis_text) >= 4:
        score += 5
    if len(analysis_text) >= 12:
        score += 5

    # A name such as "Hero" is valid in structured game data, but an
    # identifier in a generic/script scan is usually not player-facing text.
    if source_type in {"generic", "script"} and IDENTIFIER_PATTERN.fullmatch(analysis_text):
        score -= 50
    if source_type == "script" and any(token in analysis_text for token in ("$game", "Scene_", "Window_", "AudioManager")):
        score -= 45

    if score >= 50:
        return CandidateEvaluation("accept", score, analysis_text)
    if score >= 25:
        return CandidateEvaluation("review", score, analysis_text)
    return CandidateEvaluation("reject", score, analysis_text, "low-score")
