from difflib import SequenceMatcher
from functools import lru_cache
import gzip
import json
from pathlib import Path
from typing import Any


DEFAULT_UNIHAN_DATA_PATH = (
    Path(__file__).resolve().parent / "data" / "unihan_ocr_features.json.gz"
)
UNIHAN_SCHEMA_VERSION = 1
UNIHAN_UNICODE_VERSION = "17.0.0"
UNIHAN_SOURCE_SHA256 = (
    "f7a48b2b545acfaa77b2d607ae28747404ce02baefee16396c5d2d7a8ef34b5e"
)


class FeatureScorer:
    """Optional non-BERT features used by the OCR candidate reranker."""

    _loaded_indexes: dict[
        Path,
        tuple[dict[str, dict[str, str]], dict[str, Any]],
    ] = {}

    def __init__(
        self,
        use_unihan: bool = True,
        unihan_data_path: str | Path | None = None,
    ) -> None:
        self.use_unihan = use_unihan
        self.unihan_data_path = Path(
            unihan_data_path or DEFAULT_UNIHAN_DATA_PATH
        ).resolve()
        self._unihan_index: dict[str, dict[str, str]] = {}
        self.unihan_metadata: dict[str, Any] = {}
        if use_unihan:
            self._load_unihan_index()

    def _load_unihan_index(self) -> None:
        cached = self._loaded_indexes.get(self.unihan_data_path)
        if cached is not None:
            self._unihan_index, self.unihan_metadata = cached
            return

        try:
            with gzip.open(self.unihan_data_path, "rt", encoding="utf-8") as file:
                payload = json.load(file)
            records = payload.get("records")
            if not isinstance(records, dict):
                raise ValueError("missing records object")
            expected_metadata = {
                "schema_version": UNIHAN_SCHEMA_VERSION,
                "unicode_version": UNIHAN_UNICODE_VERSION,
                "source_sha256": UNIHAN_SOURCE_SHA256,
            }
            for key, expected in expected_metadata.items():
                if payload.get(key) != expected:
                    raise ValueError(
                        f"unexpected {key}: {payload.get(key)!r}; "
                        f"expected {expected!r}"
                    )
            self.unihan_metadata = {
                key: payload.get(key)
                for key in ("schema_version", "unicode_version", "source_sha256")
            }
            self._unihan_index = records
            self._loaded_indexes[self.unihan_data_path] = (
                records,
                self.unihan_metadata,
            )
        except Exception as exc:
            raise RuntimeError(
                f"Cannot load the packaged UniHan index at "
                f"{self.unihan_data_path}: {exc}"
            ) from exc

    @staticmethod
    def _radicals(value: str) -> set[str]:
        return {
            item.split(".", 1)[0].rstrip("'")
            for item in value.split()
            if item
        }

    @staticmethod
    def _integers(value: str) -> set[int]:
        result = set()
        for item in value.split():
            try:
                result.add(int(item))
            except ValueError:
                continue
        return result

    @staticmethod
    def _four_corner_codes(value: str) -> list[str]:
        return [item.replace(".", "") for item in value.split() if item]

    @staticmethod
    def _sequence_similarity(left: str, right: str) -> float:
        return SequenceMatcher(None, left, right).ratio()

    @lru_cache(maxsize=65536)
    def _unihan_pair(
        self,
        original_char: str,
        candidate: str,
    ) -> tuple[float, bool, tuple[tuple[str, float], ...]]:
        if not self.use_unihan:
            return 0.0, False, ()
        if original_char == candidate:
            return 1.0, True, (("exact", 1.0),)

        original = self._unihan_index.get(f"{ord(original_char):X}", {})
        proposed = self._unihan_index.get(f"{ord(candidate):X}", {})
        weighted_components: list[tuple[str, float, float]] = []

        original_rs = original.get("kRSUnicode")
        candidate_rs = proposed.get("kRSUnicode")
        if original_rs and candidate_rs:
            radical_match = float(bool(
                self._radicals(original_rs) & self._radicals(candidate_rs)
            ))
            weighted_components.append(("radical", radical_match, 0.30))

        original_strokes = self._integers(original.get("kTotalStrokes", ""))
        candidate_strokes = self._integers(proposed.get("kTotalStrokes", ""))
        if original_strokes and candidate_strokes:
            difference = min(
                abs(left - right)
                for left in original_strokes
                for right in candidate_strokes
            )
            stroke_score = max(0.0, 1.0 - difference / 5.0)
            weighted_components.append(("total_strokes", stroke_score, 0.25))

        original_four = self._four_corner_codes(
            original.get("kFourCornerCode", "")
        )
        candidate_four = self._four_corner_codes(
            proposed.get("kFourCornerCode", "")
        )
        if original_four and candidate_four:
            four_corner_score = max(
                sum(a == b for a, b in zip(left, right))
                / max(len(left), len(right))
                for left in original_four
                for right in candidate_four
            )
            weighted_components.append(
                ("four_corner", four_corner_score, 0.30)
            )

        original_cangjie = original.get("kCangjie", "").split()
        candidate_cangjie = proposed.get("kCangjie", "").split()
        if original_cangjie and candidate_cangjie:
            cangjie_score = max(
                self._sequence_similarity(left, right)
                for left in original_cangjie
                for right in candidate_cangjie
            )
            weighted_components.append(("cangjie", cangjie_score, 0.15))

        original_phonetic = set(original.get("kPhonetic", "").split())
        candidate_phonetic = set(proposed.get("kPhonetic", "").split())
        phonetic_match = bool(original_phonetic & candidate_phonetic)

        if not weighted_components and not phonetic_match:
            # Absence of data is not evidence that two rare characters differ.
            return 1.0, False, ()

        if weighted_components:
            total_weight = sum(weight for _, _, weight in weighted_components)
            score = sum(
                value * weight for _, value, weight in weighted_components
            ) / total_weight
        else:
            score = 0.0

        components = [(name, value) for name, value, _ in weighted_components]
        if phonetic_match:
            score = max(score, 0.85)
            components.append(("phonetic", 1.0))
        return max(0.0, min(1.0, score)), True, tuple(components)

    def get_unihan_details(
        self,
        original_char: str,
        candidate: str,
    ) -> dict[str, Any]:
        score, available, components = self._unihan_pair(
            original_char,
            candidate,
        )
        return {
            "score": score,
            "available": available,
            "components": dict(components),
        }

    def get_glyph_score(self, original_char: str, candidate: str) -> float:
        del original_char, candidate
        return 0.0

    def get_ngram_score(self, text: str, position: int, candidate: str) -> float:
        del text, position, candidate
        return 0.0

    def get_unihan_score(self, original_char: str, candidate: str) -> float:
        return self._unihan_pair(original_char, candidate)[0]

    def get_confusion_score(self, original_char: str, candidate: str) -> float:
        del original_char, candidate
        return 0.0
