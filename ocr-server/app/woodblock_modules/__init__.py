"""Woodblock preprocessing modules."""

from .mirror_flip import mirror_flip
from .perspective_correction import (
    auto_perspective_correction,
    manual_perspective_correction,
    draw_corners,
)
from .deskew import deskew, estimate_skew_angle
from .clahe import apply_clahe
from .noise_reduction import reduce_noise
from .binarization import binarize
from .morphology import apply_morphology
from .resize import (
    resize,
    resize_by_width,
    resize_by_height,
    resize_by_scale,
    resize_exact,
    resize_max_side,
)

__all__ = [
    # Sprint 1
    "mirror_flip",
    "auto_perspective_correction",
    "manual_perspective_correction",
    "draw_corners",
    "deskew",
    "estimate_skew_angle",
    "apply_clahe",
    "reduce_noise",
    # Sprint 2
    "binarize",
    "apply_morphology",
    "resize",
    "resize_by_width",
    "resize_by_height",
    "resize_by_scale",
    "resize_exact",
    "resize_max_side",
]