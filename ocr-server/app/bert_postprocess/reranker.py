from copy import deepcopy
import math
from typing import Any

from app.bert_postprocess.beam_search_decoder import BeamSearchDecoder
from app.bert_postprocess.bert_candidate_scorer import BertCandidateScore, BertCandidateScorer
from app.bert_postprocess.candidate_parser import CandidateParser, CandidatePosition
from app.bert_postprocess.feature_scorer import FeatureScorer
from app.bert_postprocess.ocr_score_normalizer import score_ocr_candidates
from app.bert_postprocess.reranker_config import RerankerConfig


class CandidateReranker:
    def __init__(
        self,
        config: RerankerConfig | None = None,
        bert_scorer: BertCandidateScorer | Any | None = None,
        feature_scorer: FeatureScorer | None = None,
        variant_converter: Any | None = None,
    ) -> None:
        self.config = config or RerankerConfig()
        self.parser = CandidateParser(
            self.config.top_k,
            use_dynamic_top_k=self.config.use_dynamic_top_k,
            min_top_k=self.config.min_top_k,
            max_top_k=self.config.max_top_k,
            cumulative_threshold=self.config.candidate_cumulative_probability,
        )
        self.bert_scorer = bert_scorer
        self.feature_scorer = feature_scorer or FeatureScorer(
            use_unihan=self.config.use_unihan
        )
        self.variant_converter = variant_converter
        if self.config.preserve_ocr_variants and self.variant_converter is None:
            try:
                import opencc

                self.variant_converter = opencc.OpenCC("t2s.json")
            except Exception as exc:
                raise RuntimeError(
                    "preserve_ocr_variants requires OpenCC. Install the "
                    "dependencies from requirements.txt."
                ) from exc
        self.decoder = BeamSearchDecoder(
            beam_width=self.config.beam_width,
            max_changes_per_line=self.config.max_changes_per_line,
        )

    def _ensure_bert_scorer(self) -> BertCandidateScorer:
        if self.bert_scorer is None:
            self.bert_scorer = BertCandidateScorer(
                scoring_mode=self.config.bert_scoring_mode,
                log_odds_clip=self.config.bert_log_odds_clip,
            )
        return self.bert_scorer

    def _are_variant_equivalent(self, original: str, candidate: str) -> bool:
        if (
            not self.config.preserve_ocr_variants
            or self.config.variant_policy != "preserve"
            or self.variant_converter is None
            or original == candidate
        ):
            return False
        try:
            return self.variant_converter.convert(original) == self.variant_converter.convert(candidate)
        except Exception:
            return True

    @staticmethod
    def _coerce_bert_score(value: Any) -> BertCandidateScore:
        if isinstance(value, BertCandidateScore):
            return value
        if isinstance(value, (int, float)) and math.isfinite(float(value)):
            return BertCandidateScore(float(value), None, True, normalized_score=float(value))
        if isinstance(value, dict):
            score = value.get("normalized_score", value.get("score", 0.0))
            try:
                score = float(score)
            except (TypeError, ValueError):
                return BertCandidateScore(0.0, None, False, "invalid_scorer_output")
            if not math.isfinite(score):
                return BertCandidateScore(0.0, None, False, "nonfinite_scorer_output")
            return BertCandidateScore(
                score=score,
                log_probability=value.get("candidate_log_probability", value.get("log_probability")),
                valid=bool(value.get("valid", True)),
                reason=value.get("reason"),
                candidate_log_probability=value.get("candidate_log_probability"),
                original_log_probability=value.get("original_log_probability"),
                log_odds=value.get("log_odds"),
                normalized_score=score,
                subset_probability=value.get("subset_probability"),
            )
        return BertCandidateScore(0.0, None, False, "invalid_scorer_output")

    @staticmethod
    def _line_average_confidence(line_data: dict[str, Any]) -> float | None:
        values = line_data.get("per_char_confidences")
        if not isinstance(values, list):
            chars = line_data.get("chars")
            if isinstance(chars, list):
                values = [
                    item.get("confidence")
                    for item in chars
                    if isinstance(item, dict)
                ]
        if not isinstance(values, list):
            return None
        scores = []
        for value in values:
            try:
                parsed = float(value)
                if math.isfinite(parsed):
                    scores.append(parsed)
            except (TypeError, ValueError):
                continue
        return sum(scores) / len(scores) if scores else None

    def _score_position(
        self,
        text: str,
        position: CandidatePosition,
        prefetched_bert_scores: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ocr_details = score_ocr_candidates(
            position.candidates,
            position.original,
            method=self.config.ocr_normalization,
            temperature=self.config.ocr_score_temperature,
            epsilon=self.config.ocr_score_epsilon,
        )
        chars = [candidate.char for candidate in position.candidates]
        scorer_error = None
        if prefetched_bert_scores is not None:
            raw_bert_scores = prefetched_bert_scores
        else:
            try:
                raw_bert_scores = self._ensure_bert_scorer().score_candidates(
                    text, position.index, chars
                )
            except Exception as exc:
                raw_bert_scores = {}
                scorer_error = f"bert_scoring_error: {exc}"

        scored = []
        for candidate in position.candidates:
            bert = self._coerce_bert_score(raw_bert_scores.get(candidate.char))
            if scorer_error:
                bert = BertCandidateScore(0.0, None, False, scorer_error)
            ocr = ocr_details[candidate.char]
            if self.config.use_unihan:
                details_method = getattr(self.feature_scorer, "get_unihan_details", None)
                if callable(details_method):
                    unihan_details = details_method(position.original, candidate.char)
                else:
                    unihan_details = {
                        "score": self.feature_scorer.get_unihan_score(
                            position.original, candidate.char
                        ),
                        "available": None,
                        "components": {},
                    }
                unihan_similarity = float(unihan_details.get("score", 1.0))
                unihan_available = unihan_details.get("available")
            else:
                unihan_similarity = 1.0
                unihan_available = False
                unihan_details = {"components": {}}
            unihan_delta = (
                0.0
                if candidate.char == position.original or unihan_available is False
                else max(-0.5, min(0.5, unihan_similarity - 0.5))
            )
            variant_equivalent = self._are_variant_equivalent(
                position.original, candidate.char
            )
            active = {
                "ocr": self.config.ocr_weight if ocr["available"] else 0.0,
                "bert": self.config.bert_weight if bert.valid else 0.0,
                "unihan": self.config.unihan_weight if unihan_available is not False else 0.0,
            }
            active_total = sum(active.values()) or 1.0
            effective_weights = {key: value / active_total for key, value in active.items()}
            delta = (
                effective_weights["ocr"] * ocr["score"]
                + effective_weights["bert"] * bert.score
                + effective_weights["unihan"] * unihan_delta
            )
            if candidate.char == position.original:
                delta = 0.0
            if not math.isfinite(delta):
                delta = 0.0
            scored.append({
                "char": candidate.char,
                "ocr_raw_score": candidate.raw_score,
                "original_ocr_raw_score": ocr["original_probability"],
                "ocr_log_ratio": ocr["log_ratio"],
                "ocr_normalized_score": ocr["score"],
                "ocr_score_type": ocr["score_type"],
                "bert_score": bert.score,
                "bert_candidate_log_probability": bert.candidate_log_probability,
                "bert_original_log_probability": bert.original_log_probability,
                "bert_log_probability": bert.log_probability,
                "bert_log_odds": bert.log_odds,
                "bert_normalized_score": bert.normalized_score,
                "bert_subset_probability": bert.subset_probability,
                "bert_valid": bert.valid,
                "bert_reason": bert.reason,
                "unihan_score": unihan_similarity,
                "unihan_similarity": unihan_similarity,
                "unihan_delta": unihan_delta,
                "unihan_available": unihan_available,
                "unihan_components": unihan_details.get("components", {}),
                "glyph_score": None,
                "glyph_available": False,
                "ngram_score": None,
                "confusion_score": None,
                "configured_weights": {
                    "ocr": self.config.ocr_weight,
                    "bert": self.config.bert_weight,
                    "unihan": self.config.unihan_weight,
                },
                "effective_weights": effective_weights,
                "final_score": delta,
                "candidate_delta_score": delta,
                "variant_equivalent": variant_equivalent,
            })

        for candidate in scored:
            candidate["margin"] = candidate["candidate_delta_score"]
            if candidate["char"] == position.original:
                candidate["eligible"] = True
                candidate["rejection_reason"] = None
            elif candidate["variant_equivalent"]:
                candidate["eligible"] = False
                candidate["rejection_reason"] = "variant_equivalent"
            elif not candidate["bert_valid"]:
                candidate["eligible"] = False
                candidate["rejection_reason"] = candidate["bert_reason"] or "bert_invalid"
            elif candidate["candidate_delta_score"] < self.config.replacement_margin:
                candidate["eligible"] = False
                candidate["rejection_reason"] = "replacement_margin_not_met"
            else:
                candidate["eligible"] = True
                candidate["rejection_reason"] = None

        return {
            "index": position.index,
            "original": position.original,
            "ocr_confidence": position.ocr_confidence,
            "confidence_source": position.confidence_source,
            "protection_threshold": self.config.confidence_protection_threshold,
            "use_unihan": self.config.use_unihan,
            "original_candidate_count": position.original_candidate_count,
            "selected_candidate_count": position.selected_candidate_count,
            "candidate_selection_reason": position.candidate_selection_reason,
            "candidates": scored,
        }

    def _protected_position(self, position: CandidatePosition) -> dict[str, Any] | None:
        confidence = position.ocr_confidence
        if confidence is None:
            reason = "missing_ocr_confidence"
        elif confidence > self.config.confidence_protection_threshold:
            reason = "high_ocr_confidence"
        else:
            return None
        return {
            "index": position.index,
            "original": position.original,
            "reason": reason,
            "ocr_confidence": confidence,
            "confidence_source": position.confidence_source,
            "protection_threshold": self.config.confidence_protection_threshold,
        }

    def rerank_line(self, line_data: dict[str, Any]) -> dict[str, Any]:
        original_text = line_data.get("text", "")
        result: dict[str, Any] = {
            "original_text": original_text,
            "corrected_text": original_text,
            "applied": False,
            "reason": "no_candidate_list",
            "changes": [],
            "candidate_positions": [],
            "checked": [],
            "skipped_positions": [],
            "variant_candidates_blocked": 0,
            "confidence_protection_threshold": self.config.confidence_protection_threshold,
            "preserve_ocr_variants": self.config.preserve_ocr_variants,
            "use_unihan": self.config.use_unihan,
            "line_avg_confidence": self._line_average_confidence(line_data),
            "beam": {
                "beam_width": self.config.beam_width,
                "max_observed_size": 0,
                "accumulated_score": 0.0,
                "per_position_scores": [],
            },
        }
        if not isinstance(original_text, str) or not original_text:
            result["reason"] = "empty_text"
            return result
        positions = self.parser.parse_line(line_data)
        if not positions:
            return result
        eligible_positions = []
        for position in positions:
            protected = self._protected_position(position)
            if protected is None:
                eligible_positions.append(position)
            else:
                result["skipped_positions"].append(protected)
        if result["line_avg_confidence"] is None:
            values = [p.ocr_confidence for p in positions if p.ocr_confidence is not None]
            if values:
                result["line_avg_confidence"] = sum(values) / len(values)
        if not eligible_positions:
            result["reason"] = "protected_by_ocr_confidence"
            return result

        prefetched = None
        try:
            scorer = self._ensure_bert_scorer()
            prefetched = scorer.score_positions(original_text, [
                (p.index, [candidate.char for candidate in p.candidates])
                for p in eligible_positions
            ])
        except Exception:
            prefetched = None
        scored_positions = [
            self._score_position(original_text, position, prefetched[index] if prefetched is not None else None)
            for index, position in enumerate(eligible_positions)
        ]
        result["candidate_positions"] = scored_positions
        result["checked"] = scored_positions
        result["variant_candidates_blocked"] = sum(
            candidate["rejection_reason"] == "variant_equivalent"
            for position in scored_positions
            for candidate in position["candidates"]
        )
        best = self.decoder.decode(original_text, scored_positions)
        result["corrected_text"] = best.candidate_text
        result["changes"] = best.changes
        result["applied"] = bool(best.changes)
        result["reason"] = "candidate_reranking" if best.changes else "replacement_margin_not_met"
        result["beam"] = {
            "beam_width": self.config.beam_width,
            "max_observed_size": self.decoder.max_observed_beam_size,
            "accumulated_score": best.accumulated_score,
            "per_position_scores": best.per_position_scores,
        }
        return result

    def telemetry(self) -> dict[str, Any]:
        scorer = self.bert_scorer
        return scorer.telemetry() if scorer is not None and hasattr(scorer, "telemetry") else {}

    def rerank_document(self, data: dict[str, Any]) -> dict[str, Any]:
        output = deepcopy(data)
        for item in output.get("results", []):
            correction = self.rerank_line(item)
            item["original_text"] = correction["original_text"]
            item["corrected_text"] = correction["corrected_text"]
            item["post_correction"] = correction
        return output
