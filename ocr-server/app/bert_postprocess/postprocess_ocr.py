import argparse
from collections import defaultdict
from copy import deepcopy
import json
import time

from app.bert_postprocess.reranker_config import RerankerConfig

def load_ocr_response(input_path: str):
    with open(input_path, "r", encoding="utf-8") as f:
        return json.load(f)


class OCRPostProcessor:
    def __init__(
        self,
        mode: str = "candidate_reranking",
        config: RerankerConfig | None = None,
        corrector=None,
    ):
        self.mode = mode
        if corrector is not None:
            self.corrector = corrector
        elif mode == "candidate_reranking":
            from app.bert_postprocess.bert_corrector import AncientChineseBertCorrector

            config = config or RerankerConfig()
            self.corrector = AncientChineseBertCorrector(
                visual_prior_weight=config.visual_prior_weight,
                min_replacement_score=config.min_replacement_score,
                low_confidence_threshold=config.low_confidence_threshold,
                low_confidence_min_replacement_score=(
                    config.low_confidence_min_replacement_score
                ),
                ctc_support_max_confidence=config.ctc_support_max_confidence,
                ctc_support_min_log_ratio=config.ctc_support_min_log_ratio,
                ctc_support_min_replacement_score=(
                    config.ctc_support_min_replacement_score
                ),
            )
        elif mode == "legacy_free_vocab":
            from app.bert_postprocess.bert_corrector import AncientChineseBertCorrector

            self.corrector = AncientChineseBertCorrector()
        else:
            raise ValueError(
                "mode must be 'candidate_reranking' or 'legacy_free_vocab'"
            )

    def _bbox_top(self, item):
        bbox = item.get("bbox") or []

        if not bbox:
            return 0

        return min(point[1] for point in bbox)

    def _char_confidences(self, item):
        confidences = item.get("per_char_confidences")

        if confidences:
            return confidences

        chars = item.get("chars") or []
        confidences = [
            char.get("confidence")
            for char in chars
            if char.get("confidence") is not None
        ]

        return confidences or None

    def _coerce_response(self, ocr_response):
        if isinstance(ocr_response, dict):
            return ocr_response

        if isinstance(ocr_response, bytes):
            ocr_response = ocr_response.decode("utf-8")

        if isinstance(ocr_response, str):
            return json.loads(ocr_response)

        raise TypeError(
            "ocr_response must be a dict, JSON string, or JSON bytes"
        )

    def process_json(self, json_text: str):
        return self.process(json_text)

    def process_file(self, input_path: str, compact_output: bool = False):
        result = self.process(load_ocr_response(input_path))
        return self.to_ocr_schema(result) if compact_output else result

    @staticmethod
    def to_ocr_schema(processed: dict) -> dict:
        """Return the public OCR JSON schema without reranking candidates.

        The normal ``process`` result deliberately retains audit data for the
        effectiveness report.  This export removes that internal data while
        retaining the same ``results``/``columns``/``full_text`` shape as the
        upstream OCR response.
        """
        output = deepcopy(processed)
        for key in (
            "original_full_text",
            "corrected_full_text",
            "post_correction_telemetry",
        ):
            output.pop(key, None)

        for item in output.get("results", []):
            if not isinstance(item, dict):
                continue
            for key in (
                "char_candidates",
                "char_candidates_available",
                "candidate_dict",
                "candidate_lists",
                "original_text",
                "corrected_text",
                "original_confidence",
                "original_per_char_confidences",
                "final_char_confidences",
                "final_confidence",
                "post_correction",
            ):
                item.pop(key, None)
            for char in item.get("chars", []):
                if not isinstance(char, dict):
                    continue
                char.pop("original_char", None)
                char.pop("original_confidence", None)
                # Keep the empty field used by the OCR schema in the sample,
                # but never expose reranking candidates to the consumer.
                char["candidates"] = []
                char["candidate_source"] = None

        columns = []
        for column in output.get("columns", []):
            if not isinstance(column, dict):
                continue
            columns.append({
                "index": column.get("index"),
                "text": column.get("text", ""),
                "avg_score": column.get("avg_score"),
            })
        output["columns"] = columns
        return output

    def process(self, ocr_response: dict):
        started_at = time.perf_counter()
        data = deepcopy(self._coerce_response(ocr_response))

        results = data.get("results", [])

        for item in results:
            text = item.get("text", "")
            char_confidences = self._char_confidences(item)

            if self.mode == "candidate_reranking":
                correct_line = getattr(self.corrector, "correct_line", None)
                if callable(correct_line):
                    correction = correct_line(item)
                else:
                    # Compatibility for explicitly injected pre-refactor
                    # CandidateReranker test doubles/callers.
                    correction = self.corrector.rerank_line(item)
            else:
                correction = self.corrector.correct_line(
                    text=text,
                    char_confidences=char_confidences,
                )

            item["original_text"] = correction["original_text"]
            item["corrected_text"] = correction["corrected_text"]
            # Confidence of each character in corrected_text. Values are OCR
            # confidences for untouched positions and fused OCR+BERT
            # posteriors for positions that were reranked.
            item["final_char_confidences"] = correction.get(
                "final_char_confidences", []
            )
            item["final_confidence"] = correction.get(
                "final_line_avg_confidence"
            )
            # Keep the JSON schema expected by OCR consumers, but make its
            # primary fields represent the final post-BERT result.
            item["original_confidence"] = item.get("confidence")
            item["original_per_char_confidences"] = item.get(
                "per_char_confidences"
            )
            item["text"] = correction["corrected_text"]
            if item["final_confidence"] is not None:
                item["confidence"] = item["final_confidence"]
            item["per_char_confidences"] = item["final_char_confidences"]

            checked_by_index = {
                checked["index"]: checked
                for checked in correction.get("checked", [])
            }
            output_chars = list(correction["corrected_text"])
            chars = item.get("chars")
            if not isinstance(chars, list):
                chars = []
                item["chars"] = chars
            for index, output_char in enumerate(output_chars):
                if index >= len(chars):
                    chars.append({})
                elif not isinstance(chars[index], dict):
                    chars[index] = {}
                char_item = chars[index]
                char_item["original_char"] = char_item.get("char", text[index])
                char_item["original_confidence"] = char_item.get("confidence")
                char_item["char"] = output_char
                char_item["confidence"] = (
                    item["final_char_confidences"][index]
                    if index < len(item["final_char_confidences"])
                    else None
                )
                checked = checked_by_index.get(index, {})
                char_item["confidence_source"] = checked.get(
                    "final_confidence_source", "ocr_input"
                )
            item["post_correction"] = {
                key: value
                for key, value in correction.items()
                if key not in {"original_text", "corrected_text"}
            }

        # Rebuild columns bằng corrected_text
        columns_map = defaultdict(list)

        for item in results:
            col = item.get("column")
            if col is not None:
                columns_map[col].append(item)

        new_columns = []

        for col_index in sorted(columns_map.keys()):
            items = sorted(columns_map[col_index], key=self._bbox_top)

            original_text = "".join(
                item.get("original_text", item.get("text", ""))
                for item in items
            )

            corrected_text = "".join(
                item.get("corrected_text", item.get("text", ""))
                for item in items
            )

            original_avg_score = sum(
                float(item.get("original_confidence", 0.0)) for item in items
            ) / max(len(items), 1)
            final_confidence_values = [
                item.get("final_confidence")
                for item in items
                if item.get("final_confidence") is not None
            ]

            new_columns.append({
                "index": col_index,
                "text": corrected_text,
                "original_text": original_text,
                "corrected_text": corrected_text,
                "avg_score": (
                    sum(final_confidence_values) / len(final_confidence_values)
                    if final_confidence_values else original_avg_score
                ),
                "original_avg_score": original_avg_score,
                "final_avg_confidence": (
                    sum(final_confidence_values) / len(final_confidence_values)
                    if final_confidence_values else None
                ),
            })

        data["columns"] = new_columns

        data["original_full_text"] = "\n".join(
            col["original_text"] for col in new_columns
        )

        data["corrected_full_text"] = "\n".join(
            col["corrected_text"] for col in new_columns
        )

        # Giữ tương thích nếu frontend đang đọc full_text
        data["full_text"] = data["corrected_full_text"]

        telemetry = {
            "runtime_seconds": time.perf_counter() - started_at,
        }
        bert_scorer = getattr(self.corrector, "bert_scorer", None)
        telemetry_method = getattr(bert_scorer, "telemetry", None)
        if callable(telemetry_method):
            telemetry.update(telemetry_method())
        data["post_correction_telemetry"] = telemetry

        return data


def _parse_args():
    parser = argparse.ArgumentParser(
        description="Rerank OCR-provided character candidates with SikuBERT."
    )
    parser.add_argument("input_path", nargs="?", help="Legacy positional input path")
    parser.add_argument("output_path", nargs="?", help="Legacy positional output path")
    parser.add_argument("--input", dest="input_option", help="OCR JSON input path")
    parser.add_argument("--output", dest="output_option", help="Output JSON path")
    parser.add_argument(
        "--mode",
        choices=("candidate_reranking", "legacy_free_vocab"),
        default="candidate_reranking",
    )
    parser.add_argument(
        "--ocr-normalization",
        choices=("rank", "temperature", "log_ratio"),
        default="log_ratio",
    )
    parser.add_argument("--temperature", type=float, default=3.0)
    parser.add_argument("--ocr-score-temperature", type=float, default=3.0)
    parser.add_argument("--ocr-score-epsilon", type=float, default=1e-8)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--static-top-k", action="store_true")
    parser.add_argument("--min-top-k", type=int, default=5)
    parser.add_argument("--max-top-k", type=int, default=10)
    parser.add_argument(
        "--candidate-cumulative-probability",
        type=float,
        default=0.995,
    )
    parser.add_argument(
        "--bert-scoring-mode",
        choices=("full_vocab_log_odds", "candidate_subset_softmax"),
        default="full_vocab_log_odds",
    )
    parser.add_argument("--bert-log-odds-clip", type=float, default=10.0)
    parser.add_argument("--beam-width", type=int, default=5)
    parser.add_argument("--visual-prior-weight", type=float, default=0.80)
    parser.add_argument("--min-replacement-score", type=float, default=0.35)
    parser.add_argument("--low-confidence-threshold", type=float, default=0.38)
    parser.add_argument(
        "--low-confidence-min-replacement-score", type=float, default=0.15
    )
    parser.add_argument("--ctc-support-max-confidence", type=float, default=0.42)
    parser.add_argument("--ctc-support-min-log-ratio", type=float, default=-0.20)
    parser.add_argument(
        "--ctc-support-min-replacement-score", type=float, default=0.20
    )
    parser.add_argument("--replacement-margin", type=float, default=0.33)
    parser.add_argument("--max-changes-per-line", type=int, default=5)
    parser.add_argument(
        "--confidence-protection-threshold",
        type=float,
        default=0.80,
        help="Never replace OCR characters with confidence above this value.",
    )
    parser.add_argument(
        "--allow-variant-changes",
        action="store_true",
        help="Allow replacements that only change simplified/traditional variants.",
    )
    parser.add_argument(
        "--disable-unihan",
        action="store_true",
        help="Disable the packaged UniHan similarity feature for ablation.",
    )
    args = parser.parse_args()

    args.input_file = args.input_option or args.input_path
    args.output_file = args.output_option or args.output_path
    if not args.input_file:
        parser.error("an input path is required (use --input or a positional path)")
    return args


def main():
    args = _parse_args()
    config = RerankerConfig(
        top_k=args.top_k,
        use_dynamic_top_k=not args.static_top_k,
        min_top_k=args.min_top_k,
        max_top_k=args.max_top_k,
        candidate_cumulative_probability=args.candidate_cumulative_probability,
        beam_width=args.beam_width,
        visual_prior_weight=args.visual_prior_weight,
        min_replacement_score=args.min_replacement_score,
        low_confidence_threshold=args.low_confidence_threshold,
        low_confidence_min_replacement_score=(
            args.low_confidence_min_replacement_score
        ),
        ctc_support_max_confidence=args.ctc_support_max_confidence,
        ctc_support_min_log_ratio=args.ctc_support_min_log_ratio,
        ctc_support_min_replacement_score=(
            args.ctc_support_min_replacement_score
        ),
        ocr_normalization=args.ocr_normalization,
        temperature=args.temperature,
        ocr_score_temperature=args.ocr_score_temperature,
        ocr_score_epsilon=args.ocr_score_epsilon,
        bert_scoring_mode=args.bert_scoring_mode,
        bert_log_odds_clip=args.bert_log_odds_clip,
        replacement_margin=args.replacement_margin,
        max_changes_per_line=args.max_changes_per_line,
        confidence_protection_threshold=args.confidence_protection_threshold,
        preserve_ocr_variants=not args.allow_variant_changes,
        use_unihan=not args.disable_unihan,
    )
    result = OCRPostProcessor(mode=args.mode, config=config).process_file(
        args.input_file,
        compact_output=True,
    )
    output = json.dumps(result, ensure_ascii=False, indent=2)

    if args.output_file:
        with open(args.output_file, "w", encoding="utf-8") as f:
            f.write(output)
            f.write("\n")
    else:
        print(output)


if __name__ == "__main__":
    main()
