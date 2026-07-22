from dataclasses import dataclass, field
from typing import Any


@dataclass
class BeamState:
    candidate_text: str
    accumulated_score: float = 0.0
    changes: list[dict[str, Any]] = field(default_factory=list)
    per_position_scores: list[dict[str, Any]] = field(default_factory=list)


class BeamSearchDecoder:
    def __init__(self, beam_width: int = 5, max_changes_per_line: int = 5) -> None:
        self.beam_width = beam_width
        self.max_changes_per_line = max_changes_per_line
        self.max_observed_beam_size = 0

    def decode(
        self,
        original_text: str,
        candidate_positions: list[dict[str, Any]],
    ) -> BeamState:
        beams = [BeamState(candidate_text=original_text)]
        self.max_observed_beam_size = 1

        for position in candidate_positions:
            index = position["index"]
            original = position["original"]
            candidates = position["candidates"]
            expanded: list[BeamState] = []

            for beam in beams:
                for candidate in candidates:
                    changed = candidate["char"] != original
                    if changed and len(beam.changes) >= self.max_changes_per_line:
                        continue
                    if changed and not candidate.get("eligible", False):
                        continue

                    chars = list(beam.candidate_text)
                    chars[index] = candidate["char"]
                    score_record = {
                        "index": index,
                        "selected": candidate["char"],
                        "final_score": candidate["final_score"],
                    }
                    changes = list(beam.changes)
                    if changed:
                        original_record = next(
                            item for item in candidates
                            if item["char"] == original
                        )
                        changes.append({
                            "index": index,
                            "original": original,
                            "selected": candidate["char"],
                            # Backward-compatible aliases used by the old
                            # post-correction report consumers.
                            "from": original,
                            "to": candidate["char"],
                            "char_confidence": original_record["ocr_raw_score"],
                            "original_prob": (
                                original_record.get("bert_original_probability")
                                if original_record.get("bert_original_probability")
                                is not None
                                else original_record["bert_score"]
                            ),
                            "candidate_prob": (
                                candidate.get("bert_candidate_probability")
                                if candidate.get("bert_candidate_probability")
                                is not None
                                else candidate["bert_score"]
                            ),
                            "replacement_score": candidate["final_score"],
                            "candidate_rank": next(
                                rank for rank, item in enumerate(candidates, 1)
                                if item["char"] == candidate["char"]
                            ),
                            "margin": candidate["margin"],
                            "checks": {
                                "candidate_changed": True,
                                "bert_valid": candidate["bert_valid"],
                                "replacement_margin": candidate["eligible"],
                            },
                            "candidates": candidates,
                            "top_candidates": candidates,
                        })

                    expanded.append(BeamState(
                        candidate_text="".join(chars),
                        accumulated_score=(
                            beam.accumulated_score + candidate["final_score"]
                        ),
                        changes=changes,
                        per_position_scores=[*beam.per_position_scores, score_record],
                    ))

            expanded.sort(key=lambda state: state.accumulated_score, reverse=True)
            beams = expanded[: self.beam_width]
            self.max_observed_beam_size = max(
                self.max_observed_beam_size,
                len(beams),
            )

        return beams[0] if beams else BeamState(candidate_text=original_text)
