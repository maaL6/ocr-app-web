from dataclasses import dataclass
import math
from typing import Any

import torch
from transformers import AutoModelForMaskedLM, AutoTokenizer


@dataclass
class BertCandidateScore:
    # ``score`` is retained for API compatibility and contains the normalized
    # full-vocabulary log-odds used by the new reranker.
    score: float
    log_probability: float | None
    valid: bool
    reason: str | None = None
    candidate_log_probability: float | None = None
    original_log_probability: float | None = None
    log_odds: float | None = None
    normalized_score: float | None = None
    subset_probability: float | None = None


class BertCandidateScorer:
    """Score OCR candidates against the full masked-LM vocabulary."""

    def __init__(
        self,
        model_name: str = "SIKU-BERT/sikubert",
        device: str | None = None,
        tokenizer: Any | None = None,
        model: Any | None = None,
        scoring_mode: str = "full_vocab_log_odds",
        log_odds_clip: float = 10.0,
    ) -> None:
        if scoring_mode not in {"full_vocab_log_odds", "candidate_subset_softmax"}:
            raise ValueError("unsupported BERT scoring mode")
        self.model_identifier = model_name
        self.scoring_mode = scoring_mode
        self.log_odds_clip = log_odds_clip
        if device is None:
            if torch.cuda.is_available():
                device = "cuda"
            elif torch.backends.mps.is_available():
                device = "mps"
            else:
                device = "cpu"
        self.device = device

        try:
            self.tokenizer = tokenizer or AutoTokenizer.from_pretrained(model_name)
            self.model = model or AutoModelForMaskedLM.from_pretrained(model_name)
        except Exception as exc:
            raise RuntimeError(
                f"Failed to load MaskedLM model '{model_name}'. Check the model "
                "name, dependencies, and Hugging Face cache/network access."
            ) from exc

        self.model.to(self.device)
        self.model.eval()
        self._cache: dict[
            tuple[str, str, str, int, tuple[str, ...]],
            dict[str, BertCandidateScore],
        ] = {}
        self.forward_count = 0
        self.cache_hits = 0
        self.cache_misses = 0

    def _token_id(self, candidate: str) -> tuple[int | None, str | None]:
        tokens = self.tokenizer.tokenize(candidate)
        if len(tokens) != 1:
            return None, "candidate_tokenized_to_multiple_tokens"
        token = tokens[0]
        special_tokens = set(getattr(self.tokenizer, "all_special_tokens", []))
        if token in special_tokens:
            return None, "candidate_is_special_token"
        token_id = self.tokenizer.convert_tokens_to_ids(token)
        if token_id is None or token_id == self.tokenizer.unk_token_id:
            return None, "candidate_is_unk"
        return int(token_id), None

    def _normalized_log_odds(self, value: float) -> float:
        if not math.isfinite(value):
            return 0.0
        return max(-1.0, min(1.0, value / self.log_odds_clip))

    def score_candidates(
        self,
        text: str,
        position: int,
        candidates: list[str],
    ) -> dict[str, BertCandidateScore]:
        return self.score_positions(text, [(position, candidates)])[0]

    def score_positions(
        self,
        text: str,
        requests: list[tuple[int, list[str]]],
    ) -> list[dict[str, BertCandidateScore]]:
        """Batch all masked positions in a line in one model forward pass."""
        results: list[dict[str, BertCandidateScore] | None] = [
            None for _ in requests
        ]
        pending: list[dict[str, Any]] = []

        for request_index, (position, candidates) in enumerate(requests):
            key = (
                self.model_identifier,
                self.scoring_mode,
                text,
                position,
                tuple(candidates),
            )
            if key in self._cache:
                self.cache_hits += 1
                results[request_index] = self._cache[key]
                continue
            self.cache_misses += 1
            if position < 0 or position >= len(text):
                raise IndexError("candidate position is outside the OCR text")

            original_id, original_reason = self._token_id(text[position])
            invalid = {}
            if original_id is None:
                invalid = {
                    candidate: BertCandidateScore(
                        0.0,
                        None,
                        False,
                        "invalid_original_bert_token",
                    )
                    for candidate in candidates
                }
                self._cache[key] = invalid
                results[request_index] = invalid
                continue

            token_ids: dict[str, int] = {}
            for candidate in candidates:
                token_id, reason = self._token_id(candidate)
                if token_id is None:
                    invalid[candidate] = BertCandidateScore(
                        0.0,
                        None,
                        False,
                        reason,
                    )
                else:
                    token_ids[candidate] = token_id

            if not token_ids:
                self._cache[key] = invalid
                results[request_index] = invalid
                continue

            pending.append({
                "request_index": request_index,
                "key": key,
                "position": position,
                "candidates": candidates,
                "token_ids": token_ids,
                "invalid": invalid,
                "original_id": original_id,
                "masked_text": (
                    text[:position]
                    + self.tokenizer.mask_token
                    + text[position + 1:]
                ),
            })

        if pending:
            inputs = self.tokenizer(
                [item["masked_text"] for item in pending],
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=512,
            )
            inputs = {name: value.to(self.device) for name, value in inputs.items()}
            self.model.eval()
            with torch.inference_mode():
                batch_logits = self.model(**inputs).logits
            self.forward_count += 1

            for batch_index, item in enumerate(pending):
                mask_positions = (
                    inputs["input_ids"][batch_index] == self.tokenizer.mask_token_id
                ).nonzero(as_tuple=False)
                if len(mask_positions) != 1:
                    reason = (
                        "mask_position_not_found"
                        if len(mask_positions) == 0
                        else "multiple_masks"
                    )
                    result = {
                        candidate: BertCandidateScore(0.0, None, False, reason)
                        for candidate in item["candidates"]
                    }
                else:
                    mask_index = int(mask_positions[0, 0].item())
                    logits = batch_logits[batch_index, mask_index].float()
                    full_log_probs = torch.log_softmax(logits, dim=-1)
                    original_log_prob = float(
                        full_log_probs[item["original_id"]].item()
                    )
                    valid_ids = item["token_ids"]
                    subset_logits = torch.stack([
                        logits[token_id] for token_id in valid_ids.values()
                    ])
                    subset_probs = torch.softmax(subset_logits, dim=0)
                    result = dict(item["invalid"])
                    for (candidate, token_id), subset_probability in zip(
                        valid_ids.items(), subset_probs
                    ):
                        candidate_log_prob = float(full_log_probs[token_id].item())
                        log_odds = candidate_log_prob - original_log_prob
                        normalized = self._normalized_log_odds(log_odds)
                        if self.scoring_mode == "candidate_subset_softmax":
                            normalized = float(subset_probability.item())
                        result[candidate] = BertCandidateScore(
                            score=normalized,
                            log_probability=candidate_log_prob,
                            valid=True,
                            candidate_log_probability=candidate_log_prob,
                            original_log_probability=original_log_prob,
                            log_odds=log_odds,
                            normalized_score=normalized,
                            subset_probability=float(subset_probability.item()),
                        )

                self._cache[item["key"]] = result
                results[item["request_index"]] = result

        return [result or {} for result in results]

    def telemetry(self) -> dict[str, int]:
        return {
            "bert_forward_count": self.forward_count,
            "bert_cache_hits": self.cache_hits,
            "bert_cache_misses": self.cache_misses,
        }
