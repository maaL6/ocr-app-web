from dataclasses import dataclass, field
import math
from typing import Any

from app.bert_postprocess.candidate_selector import select_dynamic_candidates


@dataclass
class OCRCandidate:
    char: str
    raw_score: float | None
    score_type: str = "probability"
    source: dict[str, Any] = field(default_factory=dict)


@dataclass
class CandidatePosition:
    index: int
    original: str
    candidates: list[OCRCandidate]
    ocr_confidence: float | None = None
    confidence_source: str | None = None
    original_candidate_count: int = 0
    selected_candidate_count: int = 0
    candidate_selection_reason: str = "static_top_k"


class CandidateParser:
    """Parse candidate lists without inventing candidates from BERT.

    The current project JSON stores character records in ``chars``.  OCR
    alternatives, when supplied, are expected under each character record's
    ``candidates`` or ``top_candidates`` field.  A top-level position-aligned
    ``candidate_lists``/``candidates`` list is also accepted for compatibility
    with OCR exporters that do not nest alternatives inside ``chars``.
    """

    _CHAR_KEYS = ("char", "text", "token", "candidate")
    _SCORE_KEYS = ("logit", "confidence", "probability", "prob", "score")

    def __init__(
        self,
        top_k: int = 5,
        use_dynamic_top_k: bool = False,
        min_top_k: int = 5,
        max_top_k: int = 10,
        cumulative_threshold: float = 0.995,
    ) -> None:
        self.top_k = top_k
        self.use_dynamic_top_k = use_dynamic_top_k
        self.min_top_k = min_top_k
        self.max_top_k = max_top_k
        self.cumulative_threshold = cumulative_threshold

    @staticmethod
    def _float_or_none(value: Any) -> float | None:
        try:
            result = None if value is None else float(value)
        except (TypeError, ValueError):
            return None
        return result if result is not None and math.isfinite(result) else None

    def _candidate_from_value(self, value: Any) -> OCRCandidate | None:
        if isinstance(value, str):
            char = value
            raw_score = None
            score_type = "probability"
            source: dict[str, Any] = {"char": value}
        elif isinstance(value, (list, tuple)) and value:
            char = value[0]
            raw_score = self._float_or_none(value[1] if len(value) > 1 else None)
            score_type = "probability"
            source = {"value": list(value)}
        elif isinstance(value, dict):
            char = next(
                (value.get(key) for key in self._CHAR_KEYS if value.get(key) is not None),
                None,
            )
            score_key = next(
                (key for key in self._SCORE_KEYS if value.get(key) is not None),
                None,
            )
            raw_score = self._float_or_none(value.get(score_key)) if score_key else None
            score_type = "logit" if score_key == "logit" else "probability"
            source = dict(value)
        else:
            return None

        if not isinstance(char, str) or len(char) != 1 or not char.strip():
            return None

        return OCRCandidate(
            char=char,
            raw_score=raw_score,
            score_type=score_type,
            source=source,
        )

    @staticmethod
    def _position_candidates(line_data: dict[str, Any], index: int) -> Any:
        chars = line_data.get("chars")
        if isinstance(chars, list) and index < len(chars):
            char_item = chars[index]
            if isinstance(char_item, dict):
                for key in ("candidates", "top_candidates"):
                    if isinstance(char_item.get(key), list):
                        return char_item[key]

        for key in ("candidate_lists", "candidates"):
            lists = line_data.get(key)
            if isinstance(lists, list) and index < len(lists):
                value = lists[index]
                if isinstance(value, dict):
                    value = value.get("candidates", value.get("top_candidates"))
                if isinstance(value, list):
                    return value

        char_candidates = line_data.get("char_candidates")
        if isinstance(char_candidates, list) and index < len(char_candidates):
            value = char_candidates[index]
            if isinstance(value, dict):
                value = value.get("candidates", value.get("top_candidates"))
            if isinstance(value, list):
                return value

        return None

    def _original_confidence(
        self,
        line_data: dict[str, Any],
        index: int,
        original: str,
        candidates: list[OCRCandidate],
    ) -> tuple[float | None, str | None]:
        chars = line_data.get("chars")
        if isinstance(chars, list) and index < len(chars):
            char_item = chars[index]
            if isinstance(char_item, dict):
                value = self._float_or_none(char_item.get("confidence"))
                if value is not None:
                    return value, "chars.confidence"

        original_candidate = next(
            (candidate for candidate in candidates if candidate.char == original),
            None,
        )
        if original_candidate is not None and original_candidate.raw_score is not None:
            return original_candidate.raw_score, "original_candidate"

        confidences = line_data.get("per_char_confidences")
        if isinstance(confidences, list) and index < len(confidences):
            value = self._float_or_none(confidences[index])
            if value is not None:
                return value, "per_char_confidences"
        return None, None

    def parse_line(self, line_data: dict[str, Any]) -> list[CandidatePosition]:
        text = line_data.get("text", "")
        if not isinstance(text, str):
            raise TypeError("line_data['text'] must be a string")

        positions: list[CandidatePosition] = []
        for index, original in enumerate(text):
            raw_values = self._position_candidates(line_data, index)
            if not isinstance(raw_values, list):
                continue

            parsed = [self._candidate_from_value(value) for value in raw_values]
            candidates = [candidate for candidate in parsed if candidate is not None]

            original_score, confidence_source = self._original_confidence(
                line_data,
                index,
                original,
                candidates,
            )
            fallback_original = OCRCandidate(
                char=original,
                raw_score=original_score,
                score_type="probability",
                source={"char": original, "confidence": original_score, "original": True},
            )

            deduplicated: list[OCRCandidate] = []
            seen: set[str] = set()
            for candidate in candidates:
                if candidate.char in seen:
                    continue
                seen.add(candidate.char)
                if candidate.char == original:
                    candidate.source = {**candidate.source, "original": True}
                    if candidate.raw_score is None:
                        candidate.raw_score = original_score
                deduplicated.append(candidate)

            if original not in seen:
                deduplicated.insert(0, fallback_original)

            original_candidate_count = len(deduplicated)
            if self.use_dynamic_top_k:
                limited, selection_reason = select_dynamic_candidates(
                    deduplicated,
                    original,
                    min_top_k=self.min_top_k,
                    max_top_k=self.max_top_k,
                    cumulative_threshold=self.cumulative_threshold,
                )
            else:
                limited = deduplicated[: self.top_k]
                selection_reason = "static_top_k"
            if not any(candidate.char == original for candidate in limited):
                original_candidate = next(
                    candidate
                    for candidate in deduplicated
                    if candidate.char == original
                )
                limited[-1:] = [original_candidate]

            # A list containing only the OCR character is not an ambiguous
            # position, so BERT must not be called for it.
            if len(limited) > 1:
                positions.append(CandidatePosition(
                    index=index,
                    original=original,
                    candidates=limited,
                    ocr_confidence=original_score,
                    confidence_source=confidence_source,
                    original_candidate_count=original_candidate_count,
                    selected_candidate_count=len(limited),
                    candidate_selection_reason=selection_reason,
                ))

        return positions
