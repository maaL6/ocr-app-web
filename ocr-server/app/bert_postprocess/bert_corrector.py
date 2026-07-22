"""Candidate-only SikuBERT reranker for OCR character substitutions."""

import math
from typing import Any

from app.bert_postprocess.bert_candidate_scorer import BertCandidateScorer
from app.bert_postprocess.unihan_variants import are_variants, get_variant_group


def is_cjk_char(ch: str) -> bool:
    if len(ch) != 1:
        return False
    code = ord(ch)
    return (
        0x3400 <= code <= 0x4DBF
        or 0x4E00 <= code <= 0x9FFF
        or 0x20000 <= code <= 0x2EBEF
        or 0x30000 <= code <= 0x3134F
    )


class AncientChineseBertCorrector:
    """Rerank only candidates supplied by the OCR decoder.

    The historical threshold names and result fields remain available for
    report consumers.  BERT never contributes a character that is absent from
    the position-aligned OCR candidate list.
    """

    def __init__(
        self,
        model_name: str = "SIKU-BERT/sikubert",
        char_conf_threshold: float = 0.55,
        review_conf_threshold: float = 0.70,
        min_candidate_prob: float = 0.35,
        min_margin: float = 0.25,
        max_original_prob: float = 5e-5,
        max_corrections_per_line: int = 3,
        high_conf_threshold: float = 0.85,
        high_conf_min_candidate_prob: float = 0.80,
        high_conf_min_margin: float = 0.55,
        min_replacement_score: float = 0.35,
        visual_prior_weight: float = 0.80,
        low_confidence_threshold: float = 0.38,
        low_confidence_min_replacement_score: float = 0.15,
        ctc_support_max_confidence: float = 0.42,
        ctc_support_min_log_ratio: float = -0.20,
        ctc_support_min_replacement_score: float = 0.20,
        enable_adaptive_thresholds: bool = True,
        enable_dynamic_budget: bool = True,
        device: str | None = None,
        bert_scorer: Any | None = None,
    ) -> None:
        if not 0.0 <= visual_prior_weight <= 1.0:
            raise ValueError("visual_prior_weight must be between 0 and 1")
        self.char_conf_threshold = char_conf_threshold
        self.review_conf_threshold = review_conf_threshold
        self.min_candidate_prob = min_candidate_prob
        self.min_margin = min_margin
        self.max_original_prob = max_original_prob
        self.max_corrections_per_line = max_corrections_per_line
        self.high_conf_threshold = high_conf_threshold
        self.high_conf_min_candidate_prob = high_conf_min_candidate_prob
        self.high_conf_min_margin = high_conf_min_margin
        self.min_replacement_score = min_replacement_score
        self.visual_prior_weight = visual_prior_weight
        self.low_confidence_threshold = low_confidence_threshold
        self.low_confidence_min_replacement_score = (
            low_confidence_min_replacement_score
        )
        self.ctc_support_max_confidence = ctc_support_max_confidence
        self.ctc_support_min_log_ratio = ctc_support_min_log_ratio
        self.ctc_support_min_replacement_score = (
            ctc_support_min_replacement_score
        )
        self.enable_adaptive_thresholds = enable_adaptive_thresholds
        self.enable_dynamic_budget = enable_dynamic_budget
        self.bert_scorer = bert_scorer or BertCandidateScorer(
            model_name=model_name,
            device=device,
            scoring_mode="candidate_subset_softmax",
        )

    @staticmethod
    def _float(value: Any) -> float | None:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return None
        return parsed if math.isfinite(parsed) else None

    @staticmethod
    def _raw_candidate_lists(line_data: dict[str, Any], index: int) -> list[Any] | None:
        chars = line_data.get("chars")
        if isinstance(chars, list) and index < len(chars):
            item = chars[index]
            if isinstance(item, dict) and isinstance(item.get("candidates"), list):
                return item["candidates"]
        mirrored = line_data.get("char_candidates")
        if isinstance(mirrored, list) and index < len(mirrored):
            return mirrored[index] if isinstance(mirrored[index], list) else None
        return None

    def _parse_candidates(
        self, line_data: dict[str, Any], index: int, original: str
    ) -> list[dict[str, Any]]:
        values = self._raw_candidate_lists(line_data, index)
        if not isinstance(values, list):
            return []
        parsed: list[dict[str, Any]] = []
        seen: set[str] = set()
        for value in values:
            if not isinstance(value, dict):
                continue
            char = value.get("char")
            confidence = self._float(value.get("confidence"))
            if not isinstance(char, str) or len(char) != 1 or char in seen:
                continue
            if confidence is None or confidence < 0.0:
                continue
            seen.add(char)
            parsed.append({"char": char, "confidence": confidence})
        if original not in seen:
            return []
        return parsed

    @staticmethod
    def _line_average(confidences: list[float | None]) -> float | None:
        values = [value for value in confidences if value is not None]
        return sum(values) / len(values) if values else None

    @staticmethod
    def _normalized_fused_probabilities(candidates: list[dict[str, Any]]) -> None:
        """Add a 0–1 posterior over the OCR candidates at one position."""
        if not candidates:
            return

        max_score = max(item["fused_score"] for item in candidates)
        weights = [math.exp(item["fused_score"] - max_score) for item in candidates]
        total = sum(weights)
        for item, weight in zip(candidates, weights):
            item["fused_probability"] = weight / total if total else 0.0

    def _thresholds(
        self,
        confidence: float | None,
        ctc_log_ratio_margin: float | None = None,
    ) -> dict[str, Any]:
        # Probability thresholds are preserved in output/config for historical
        # report compatibility. They are audit-only in candidate-only mode:
        # full-vocabulary probabilities are not commensurate with the old
        # free-vocabulary gates. ``min_replacement_score`` is now the single
        # fused-margin decision threshold.
        decision_threshold = self.min_replacement_score
        if (
            confidence is not None
            and confidence < self.low_confidence_threshold
        ):
            decision_threshold = self.low_confidence_min_replacement_score
        ctc_support_branch = (
            confidence is not None
            and confidence < self.ctc_support_max_confidence
            and ctc_log_ratio_margin is not None
            and ctc_log_ratio_margin >= self.ctc_support_min_log_ratio
        )
        if ctc_support_branch:
            decision_threshold = min(
                decision_threshold,
                self.ctc_support_min_replacement_score,
            )
        return {
            "min_candidate_prob": self.min_candidate_prob,
            "min_margin": self.min_margin,
            "max_original_prob": self.max_original_prob,
            "min_replacement_score": self.min_replacement_score,
            "low_confidence_threshold": self.low_confidence_threshold,
            "low_confidence_min_replacement_score": (
                self.low_confidence_min_replacement_score
            ),
            "effective_fused_margin_threshold": decision_threshold,
            "ctc_support_max_confidence": self.ctc_support_max_confidence,
            "ctc_support_min_log_ratio": self.ctc_support_min_log_ratio,
            "ctc_support_min_replacement_score": (
                self.ctc_support_min_replacement_score
            ),
            "ctc_support_branch": ctc_support_branch,
            "high_conf_threshold": self.high_conf_threshold,
            "high_conf_min_candidate_prob": self.high_conf_min_candidate_prob,
            "high_conf_min_margin": self.high_conf_min_margin,
            "decision_basis": "fused_margin",
            "probability_thresholds_audit_only": True,
        }

    def _effective_budget(self, text: str, review_count: int) -> int:
        budget = max(0, self.max_corrections_per_line)
        if not self.enable_dynamic_budget or budget <= 1:
            return budget
        if review_count >= max(3, len(text) // 8):
            return budget
        return min(budget, 1)

    def correct_line(
        self,
        text: str | dict[str, Any],
        char_confidences: list[float] | None = None,
        candidate_lists: list[list[dict[str, Any]]] | None = None,
    ) -> dict[str, Any]:
        if isinstance(text, dict):
            line_data = text
            original_text = line_data.get("text", "")
        else:
            original_text = text
            line_data = {"text": original_text}
            if char_confidences is not None:
                line_data["per_char_confidences"] = char_confidences
            if candidate_lists is not None:
                line_data["char_candidates"] = candidate_lists

        result = {
            "original_text": original_text,
            "corrected_text": original_text,
            "applied": False,
            "reason": "",
            "changes": [],
            "checked": [],
            "line_avg_confidence": None,
            "final_char_confidences": [],
            "final_line_avg_confidence": None,
        }
        if not isinstance(original_text, str) or not original_text:
            result["reason"] = "empty_text"
            return result

        position_data = []
        greedy_confidences: list[float | None] = []
        supplied_confidences = line_data.get("per_char_confidences")
        for index, original in enumerate(original_text):
            candidates = self._parse_candidates(line_data, index, original)
            original_item = next(
                (item for item in candidates if item["char"] == original), None
            )
            greedy_confidence = (
                original_item["confidence"] if original_item is not None else None
            )
            if (
                greedy_confidence is None
                and isinstance(supplied_confidences, list)
                and index < len(supplied_confidences)
            ):
                greedy_confidence = self._float(supplied_confidences[index])
            greedy_confidences.append(greedy_confidence)
            position_data.append((index, original, candidates, greedy_confidence))
        result["line_avg_confidence"] = self._line_average(greedy_confidences)
        # Until a position is contextually reranked, its final confidence is
        # exactly the confidence provided by OCR.
        final_confidences = list(greedy_confidences)

        requests = [
            (index, [item["char"] for item in candidates])
            for index, original, candidates, confidence in position_data
            if len(candidates) > 1
            and (confidence is None or confidence < self.review_conf_threshold)
        ]
        bert_by_position: dict[int, dict[str, Any]] = {}
        if requests:
            scored = self.bert_scorer.score_positions(original_text, requests)
            bert_by_position = {
                index: values for (index, _), values in zip(requests, scored)
            }

        applicable = []
        for index, original, candidates, confidence in position_data:
            alternatives = [
                item["confidence"] for item in candidates
                if item["char"] != original
            ]
            source = (
                "single_dominant_candidate"
                if not alternatives or max(alternatives, default=0.0) <= 1e-8
                else "top10_per_timestep"
            )
            if not candidates:
                continue
            variant_group = sorted(get_variant_group(original)) or None
            checked = {
                "index": index,
                "from": original,
                "to": original,
                "char_confidence": confidence,
                "greedy_path_confidence": confidence,
                "candidate_source": source,
                "unihan_variant_group": variant_group,
                "decision_basis": "fused_margin",
                "applied": False,
                "candidates": [],
            }
            if len(candidates) == 1:
                checked["reason"] = "single_dominant_candidate"
                checked["final_char_confidence"] = confidence
                checked["final_confidence_source"] = "ocr_input"
                result["checked"].append(checked)
                continue
            if confidence is not None and confidence >= self.review_conf_threshold:
                checked["reason"] = "char_confidence_high"
                checked["final_char_confidence"] = confidence
                checked["final_confidence_source"] = "ocr_input"
                result["checked"].append(checked)
                continue

            bert_scores = bert_by_position.get(index, {})
            scored_candidates = []
            epsilon = 1e-12
            for candidate in candidates:
                bert = bert_scores.get(candidate["char"])
                bert_log = getattr(bert, "candidate_log_probability", None)
                bert_valid = bool(getattr(bert, "valid", False)) and bert_log is not None
                ctc_log = math.log(max(candidate["confidence"], epsilon))
                fused = (
                    self.visual_prior_weight * ctc_log
                    + (1.0 - self.visual_prior_weight) * bert_log
                    if bert_valid
                    else ctc_log
                )
                scored_candidates.append({
                    **candidate,
                    "ctc_log_confidence": ctc_log,
                    "bert_log_prob": bert_log,
                    "bert_valid": bert_valid,
                    "fused_score": fused,
                    "variant_equivalent_to_original": are_variants(
                        original, candidate["char"]
                    ),
                })
            original_bert = next(
                item for item in scored_candidates if item["char"] == original
            )
            if not original_bert["bert_valid"]:
                # Without a valid BERT score for the original token there is
                # no meaningful contextual margin. Fall back consistently to
                # the original CTC distribution for the whole position.
                for item in scored_candidates:
                    item["fused_score"] = item["ctc_log_confidence"]
            self._normalized_fused_probabilities(scored_candidates)
            scored_candidates.sort(key=lambda item: item["fused_score"], reverse=True)
            original_score = next(item for item in scored_candidates if item["char"] == original)
            winner = scored_candidates[0]
            candidate_prob = (
                math.exp(winner["bert_log_prob"])
                if winner["bert_log_prob"] is not None else 0.0
            )
            original_prob = (
                math.exp(original_score["bert_log_prob"])
                if original_score["bert_log_prob"] is not None else 0.0
            )
            margin = candidate_prob - original_prob
            fused_margin = winner["fused_score"] - original_score["fused_score"]
            ctc_log_ratio_margin = (
                winner["ctc_log_confidence"]
                - original_score["ctc_log_confidence"]
            )
            bert_log_odds_margin = (
                winner["bert_log_prob"] - original_score["bert_log_prob"]
                if winner["bert_log_prob"] is not None
                and original_score["bert_log_prob"] is not None
                else None
            )
            # Backward-compatible audit alias. It is deliberately not a second
            # gate: fused_margin is the sole decision basis.
            replacement_score = fused_margin
            thresholds = self._thresholds(confidence, ctc_log_ratio_margin)
            checks = {
                "candidate_changed": winner["char"] != original,
                "candidate_in_ocr_list": True,
                "fused_margin": (
                    fused_margin
                    >= thresholds["effective_fused_margin_threshold"]
                ),
                "not_variant_equivalent": not winner["variant_equivalent_to_original"],
            }
            checked.update({
                "to": winner["char"],
                "original_prob": original_prob,
                "candidate_prob": candidate_prob,
                "margin": margin,
                "fused_margin": fused_margin,
                "ctc_log_ratio_margin": ctc_log_ratio_margin,
                "bert_log_odds_margin": bert_log_odds_margin,
                "replacement_score": replacement_score,
                "thresholds": thresholds,
                "checks": checks,
                "candidates": scored_candidates,
                "top_candidates": scored_candidates,
                # The output character stays original unless this candidate is
                # later applied; update it after the correction budget is set.
                "final_char_confidence": original_score["fused_probability"],
                "final_confidence_source": "fused_candidate_posterior",
                "reason": "eligible" if all(checks.values()) else "threshold_not_met",
            })
            final_confidences[index] = original_score["fused_probability"]
            result["checked"].append(checked)
            if all(checks.values()):
                applicable.append(checked)

        applicable.sort(
            key=lambda item: (item["replacement_score"], item["fused_margin"]),
            reverse=True,
        )
        chars = list(original_text)
        for item in applicable[: self._effective_budget(original_text, len(applicable))]:
            chars[item["index"]] = item["to"]
            item["applied"] = True
            winner_confidence = next(
                candidate["fused_probability"]
                for candidate in item["candidates"]
                if candidate["char"] == item["to"]
            )
            final_confidences[item["index"]] = winner_confidence
            item["final_char_confidence"] = winner_confidence
            result["changes"].append({
                key: item[key]
                for key in (
                    "index", "from", "to", "char_confidence",
                    "greedy_path_confidence", "original_prob", "candidate_prob",
                    "margin", "fused_margin", "replacement_score", "thresholds",
                    "ctc_log_ratio_margin", "bert_log_odds_margin",
                    "checks", "top_candidates", "candidate_source",
                    "unihan_variant_group", "decision_basis",
                    "final_char_confidence", "final_confidence_source",
                )
            })

        result["corrected_text"] = "".join(chars)
        result["final_char_confidences"] = final_confidences
        result["final_line_avg_confidence"] = self._line_average(final_confidences)
        result["applied"] = bool(result["changes"])
        result["reason"] = (
            "checked_by_bert" if result["checked"] else "no_candidate_list"
        )
        return result
