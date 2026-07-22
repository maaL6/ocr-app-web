from dataclasses import dataclass, fields


@dataclass
class RerankerConfig:
    """Configuration for OCR-candidate reranking."""

    top_k: int = 5
    use_dynamic_top_k: bool = True
    min_top_k: int = 5
    max_top_k: int = 10
    candidate_cumulative_probability: float = 0.995
    beam_width: int = 5
    # Candidate-only fusion lambda: CTC log-probability weight.
    visual_prior_weight: float = 0.80
    min_replacement_score: float = 0.35
    low_confidence_threshold: float = 0.38
    low_confidence_min_replacement_score: float = 0.15
    ctc_support_max_confidence: float = 0.42
    ctc_support_min_log_ratio: float = -0.20
    ctc_support_min_replacement_score: float = 0.20

    ocr_weight: float = 0.20
    bert_weight: float = 0.75
    glyph_weight: float = 0.0
    ngram_weight: float = 0.0
    unihan_weight: float = 0.05
    confusion_weight: float = 0.0

    ocr_normalization: str = "log_ratio"
    temperature: float = 3.0
    ocr_score_temperature: float = 3.0
    ocr_score_epsilon: float = 1e-8
    bert_scoring_mode: str = "full_vocab_log_odds"
    bert_log_odds_clip: float = 10.0
    # Tuned jointly with the packaged UniHan similarity feature.
    replacement_margin: float = 0.33
    max_changes_per_line: int = 5
    confidence_protection_threshold: float = 0.80
    preserve_ocr_variants: bool = True
    variant_policy: str = "preserve"
    use_unihan: bool = True
    unihan_mode: str = "small_support"

    def __post_init__(self) -> None:
        if self.top_k < 1:
            raise ValueError("top_k must be at least 1")
        if self.min_top_k < 1 or self.max_top_k < self.min_top_k:
            raise ValueError("dynamic top-k requires 1 <= min_top_k <= max_top_k")
        if not 0.0 < self.candidate_cumulative_probability <= 1.0:
            raise ValueError("candidate_cumulative_probability must be in (0, 1]")
        if self.beam_width < 1:
            raise ValueError("beam_width must be at least 1")
        if not 0.0 <= self.visual_prior_weight <= 1.0:
            raise ValueError("visual_prior_weight must be between 0 and 1")
        if self.max_changes_per_line < 0:
            raise ValueError("max_changes_per_line cannot be negative")
        if self.temperature <= 0:
            raise ValueError("temperature must be greater than 0")
        if self.ocr_score_temperature <= 0 or self.ocr_score_epsilon <= 0:
            raise ValueError("OCR score temperature and epsilon must be positive")
        if self.bert_log_odds_clip <= 0:
            raise ValueError("bert_log_odds_clip must be positive")
        if not 0.0 <= self.confidence_protection_threshold <= 1.0:
            raise ValueError(
                "confidence_protection_threshold must be between 0 and 1"
            )
        if self.ocr_normalization not in {"rank", "temperature", "log_ratio"}:
            raise ValueError(
                "ocr_normalization must be 'rank', 'temperature', or 'log_ratio'"
            )
        if self.bert_scoring_mode not in {
            "full_vocab_log_odds",
            "candidate_subset_softmax",
        }:
            raise ValueError("unsupported BERT scoring mode")
        if self.unihan_mode != "small_support":
            raise ValueError("unihan_mode must be 'small_support'")
        if self.variant_policy not in {"preserve", "allow"}:
            raise ValueError("variant_policy must be 'preserve' or 'allow'")

        weight_names = [
            field.name for field in fields(self)
            if field.name.endswith("_weight")
            and field.name != "visual_prior_weight"
        ]
        weights = [float(getattr(self, name)) for name in weight_names]
        if any(weight < 0 for weight in weights):
            raise ValueError("reranking weights cannot be negative")

        total = sum(weights)
        if total <= 0:
            raise ValueError("at least one reranking weight must be positive")

        # A custom configuration may use unnormalised weights. Keep their
        # relative importance while making final scores comparable.
        if abs(total - 1.0) > 1e-9:
            for name in weight_names:
                setattr(self, name, float(getattr(self, name)) / total)
