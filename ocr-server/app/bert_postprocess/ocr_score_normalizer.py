import math
from typing import Any

from app.bert_postprocess.candidate_parser import OCRCandidate


def finite_probability(candidate: OCRCandidate | None) -> float | None:
    if candidate is None or candidate.score_type != "probability":
        return None
    try:
        value = float(candidate.raw_score)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value) or value < 0.0 or value > 1.0:
        return None
    return value


def score_ocr_candidates(
    candidates: list[OCRCandidate],
    original_char: str,
    method: str = "log_ratio",
    temperature: float = 3.0,
    epsilon: float = 1e-8,
) -> dict[str, dict[str, Any]]:
    if not candidates:
        return {}
    if temperature <= 0 or epsilon <= 0:
        raise ValueError("temperature and epsilon must be positive")

    if method == "rank":
        return {
            candidate.char: {
                "score": max(0.0, 1.0 - rank * 0.3),
                "log_ratio": None,
                "available": True,
                "score_type": "rank",
                "original_probability": None,
            }
            for rank, candidate in enumerate(candidates)
        }

    if method == "temperature":
        transformed = []
        for rank, candidate in enumerate(candidates):
            probability = finite_probability(candidate)
            value = (
                math.log(max(probability, epsilon))
                if probability is not None
                else -float(rank)
            )
            transformed.append(value / temperature)
        maximum = max(transformed)
        exponents = [math.exp(value - maximum) for value in transformed]
        denominator = sum(exponents) or 1.0
        return {
            candidate.char: {
                "score": exponent / denominator,
                "log_ratio": None,
                "available": finite_probability(candidate) is not None,
                "score_type": "temperature",
                "original_probability": None,
            }
            for candidate, exponent in zip(candidates, exponents)
        }

    if method != "log_ratio":
        raise ValueError("unknown OCR normalization method")

    original = next(
        (candidate for candidate in candidates if candidate.char == original_char),
        None,
    )
    original_probability = finite_probability(original)
    result = {}
    for candidate in candidates:
        probability = finite_probability(candidate)
        available = probability is not None and original_probability is not None
        if available:
            log_ratio = math.log(probability + epsilon) - math.log(
                original_probability + epsilon
            )
            normalized = math.tanh(log_ratio / temperature)
        else:
            log_ratio = None
            normalized = 0.0
        result[candidate.char] = {
            "score": normalized if math.isfinite(normalized) else 0.0,
            "log_ratio": (
                log_ratio if log_ratio is None or math.isfinite(log_ratio) else None
            ),
            "available": available,
            "score_type": "log_ratio",
            "original_probability": original_probability,
        }
    return result


def normalize_ocr_scores(
    candidates: list[OCRCandidate],
    method: str = "rank",
    temperature: float = 3.0,
) -> dict[str, float]:
    """Backward-compatible score-only wrapper."""
    original = candidates[0].char if candidates else ""
    details = score_ocr_candidates(
        candidates,
        original,
        method=method,
        temperature=temperature,
    )
    return {char: item["score"] for char, item in details.items()}
