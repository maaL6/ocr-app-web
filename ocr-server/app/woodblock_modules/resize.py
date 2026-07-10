"""
Resize Module
=============
Thay đổi kích thước ảnh. Tách thành module riêng để dễ tinh chỉnh.

3 chế độ:
    - width:     chỉ định chiều rộng, giữ tỉ lệ
    - height:    chỉ định chiều cao, giữ tỉ lệ
    - scale:     nhân tỉ lệ
    - exact:     kích thước cụ thể (có thể phá tỉ lệ)
    - max_side:  giới hạn cạnh dài nhất (cho ảnh portrait + landscape)

Interpolation:
    - INTER_AREA:    NÊN DÙNG khi THU NHỎ (smooth, ít aliasing)
    - INTER_CUBIC:   NÊN DÙNG khi PHÓNG TO (chất lượng cao hơn LINEAR)
    - INTER_LANCZOS4: chất lượng cao nhất, chậm
    - INTER_LINEAR:  mặc định OpenCV, cân bằng
"""

import cv2
import numpy as np


INTERPOLATIONS = {
    "area":     cv2.INTER_AREA,
    "cubic":    cv2.INTER_CUBIC,
    "linear":   cv2.INTER_LINEAR,
    "lanczos":  cv2.INTER_LANCZOS4,
    "nearest":  cv2.INTER_NEAREST,
}


def _auto_interpolation(src_w: int, src_h: int, dst_w: int, dst_h: int) -> int:
    """Tự chọn interpolation: AREA khi thu nhỏ, CUBIC khi phóng to."""
    if dst_w * dst_h < src_w * src_h:
        return cv2.INTER_AREA
    return cv2.INTER_CUBIC


def resize_by_width(image, target_width: int, interpolation: str = "auto") -> np.ndarray:
    """Resize giữ tỉ lệ, chỉ định chiều rộng."""
    h, w = image.shape[:2]
    if w == target_width:
        return image
    target_height = int(h * target_width / w)
    interp = (_auto_interpolation(w, h, target_width, target_height)
              if interpolation == "auto"
              else INTERPOLATIONS[interpolation])
    return cv2.resize(image, (target_width, target_height), interpolation=interp)


def resize_by_height(image, target_height: int, interpolation: str = "auto") -> np.ndarray:
    """Resize giữ tỉ lệ, chỉ định chiều cao."""
    h, w = image.shape[:2]
    if h == target_height:
        return image
    target_width = int(w * target_height / h)
    interp = (_auto_interpolation(w, h, target_width, target_height)
              if interpolation == "auto"
              else INTERPOLATIONS[interpolation])
    return cv2.resize(image, (target_width, target_height), interpolation=interp)


def resize_by_scale(image, scale: float, interpolation: str = "auto") -> np.ndarray:
    """Resize giữ tỉ lệ theo hệ số nhân (vd: 0.5 = thu nhỏ một nửa, 2 = phóng đôi)."""
    if scale <= 0:
        raise ValueError(f"scale phải > 0, nhận: {scale}")
    if scale == 1.0:
        return image
    h, w = image.shape[:2]
    target_w = int(w * scale)
    target_h = int(h * scale)
    interp = (_auto_interpolation(w, h, target_w, target_h)
              if interpolation == "auto"
              else INTERPOLATIONS[interpolation])
    return cv2.resize(image, (target_w, target_h), interpolation=interp)


def resize_exact(image, width: int, height: int,
                 interpolation: str = "auto") -> np.ndarray:
    """Resize tới kích thước cụ thể (có thể phá tỉ lệ)."""
    h, w = image.shape[:2]
    if w == width and h == height:
        return image
    interp = (_auto_interpolation(w, h, width, height)
              if interpolation == "auto"
              else INTERPOLATIONS[interpolation])
    return cv2.resize(image, (width, height), interpolation=interp)


def resize_max_side(image, max_side: int, interpolation: str = "auto",
                    only_downscale: bool = True) -> np.ndarray:
    """
    Resize giới hạn cạnh dài nhất. Tự phát hiện ảnh portrait/landscape.

    Args:
        max_side: cạnh dài nhất sẽ thành max_side px.
        only_downscale: nếu True và ảnh đã nhỏ hơn max_side, trả nguyên ảnh
                        (không phóng to). Mặc định True.
    """
    h, w = image.shape[:2]
    longest = max(h, w)
    if only_downscale and longest <= max_side:
        return image
    scale = max_side / longest
    return resize_by_scale(image, scale, interpolation)


def resize(image, mode: str = "width", value=None,
           interpolation: str = "auto", **kwargs) -> np.ndarray:
    """
    Wrapper tiện lợi gọi resize bằng mode string.

    Examples:
        resize(img, "width", 1600)
        resize(img, "height", 800)
        resize(img, "scale", 0.5)
        resize(img, "exact", (1024, 768))
        resize(img, "max_side", 1600)
    """
    if mode == "width":
        return resize_by_width(image, value, interpolation)
    if mode == "height":
        return resize_by_height(image, value, interpolation)
    if mode == "scale":
        return resize_by_scale(image, value, interpolation)
    if mode == "exact":
        w, h = value
        return resize_exact(image, w, h, interpolation)
    if mode == "max_side":
        return resize_max_side(image, value, interpolation,
                               kwargs.get("only_downscale", True))
    raise ValueError(f"mode không hợp lệ: {mode!r}")
