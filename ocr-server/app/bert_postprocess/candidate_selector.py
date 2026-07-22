import math
from typing import Any


def _valid_probability(candidate: Any) -> float | None:
    try:
        probability = float(getattr(candidate, "raw_score", None))
    except (TypeError, ValueError):
        return None
    if (
        getattr(candidate, "score_type", "probability") != "probability"
        or not math.isfinite(probability)
        or probability < 0.0
        or probability > 1.0
    ):
        return None
    return probability


def select_dynamic_candidates(
    candidates: list[Any],
    original_char: str,
    min_top_k: int = 5,
    max_top_k: int = 10,
    cumulative_threshold: float = 0.995,
) -> tuple[list[Any], str]:
    """Keep OCR order/scores while selecting between min_top_k and max_top_k."""

    pool = candidates[:max_top_k]
    probabilities = [_valid_probability(candidate) for candidate in pool]
    if pool and all(value is not None for value in probabilities):
        selected = []
        cumulative = 0.0
        for candidate, probability in zip(pool, probabilities):
            selected.append(candidate)
            cumulative += probability or 0.0
            if len(selected) >= min_top_k and cumulative >= cumulative_threshold:
                reason = "cumulative_probability_reached"
                break
        else:
            reason = (
                "max_top_k_reached"
                if len(pool) >= max_top_k
                else "input_candidates_exhausted"
            )
    else:
        selected = list(pool)
        reason = "invalid_probability_fallback_rank"

    original = next(
        (candidate for candidate in candidates if candidate.char == original_char),
        None,
    )
    if original is not None and not any(
        candidate.char == original_char for candidate in selected
    ):
        if len(selected) >= max_top_k:
            selected[-1] = original
        else:
            selected.append(original)
        reason += "_original_retained"
    return selected, reason
