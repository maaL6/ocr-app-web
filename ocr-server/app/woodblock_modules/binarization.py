"""
Binarization Module
===================
Chuyển ảnh xám sang ảnh nhị phân (đen-trắng) để chuẩn bị cho OCR
hoặc các bước downstream khác.

4 phương pháp:
    1. otsu         -- Global threshold (Otsu), nhanh nhưng kém khi ánh
                       sáng không đều
    2. adaptive_mean -- Local threshold dùng trung bình, tốt hơn Otsu
    3. adaptive_gaussian -- Local threshold dùng Gaussian-weighted mean
    4. sauvola      -- Local threshold cho tài liệu lịch sử, BEST cho
                       mộc bản (kết hợp mean và std cục bộ)

Mặc định: sauvola (chuẩn cho tài liệu lịch sử).

Output: ảnh grayscale với chữ = ĐEN (0), nền = TRẮNG (255). Đây là quy
ước chuẩn cho OCR; nếu cần đảo, dùng `invert=True`.
"""

import cv2
import numpy as np


METHODS = ("otsu", "adaptive_mean", "adaptive_gaussian", "sauvola")


def _to_gray(image: np.ndarray) -> np.ndarray:
    """Chuyển BGR sang grayscale nếu cần."""
    if image.ndim == 3:
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return image.copy()


def _sauvola_threshold(gray: np.ndarray, window: int, k: float, r: float) -> np.ndarray:
    """
    Sauvola threshold: T(x,y) = mean(x,y) * (1 + k * (std(x,y)/r - 1))

    Khác Otsu/Adaptive thông thường ở chỗ kết hợp cả std cục bộ -> rất tốt
    cho ảnh có nền không đều, các vùng văn bản đậm/nhạt khác nhau.

    Args:
        gray: ảnh grayscale.
        window: kích thước cửa sổ (lẻ).
        k: hệ số dương (0.2-0.5).
        r: dynamic range của std (mặc định 128).
    """
    gray_f = gray.astype(np.float32)

    # Mean và mean-of-squares cục bộ qua box filter (cực nhanh)
    mean   = cv2.boxFilter(gray_f, ddepth=-1, ksize=(window, window))
    mean_sq = cv2.boxFilter(gray_f ** 2, ddepth=-1, ksize=(window, window))
    var = np.clip(mean_sq - mean ** 2, 0, None)
    std = np.sqrt(var)

    threshold = mean * (1 + k * (std / r - 1))
    binary = (gray_f > threshold).astype(np.uint8) * 255
    return binary


def binarize(
    image: np.ndarray,
    method: str = "sauvola",
    # Tham số chung
    invert: bool = False,
    # otsu: không có tham số
    # adaptive: dùng block_size, c
    block_size: int = 31,
    c: float = 10.0,
    # sauvola: dùng window, k, r
    sauvola_window: int = 25,
    sauvola_k: float = 0.2,
    sauvola_r: float = 128.0,
) -> np.ndarray:
    """
    Nhị phân hoá ảnh.

    Args:
        image: ảnh BGR hoặc grayscale.
        method: 'otsu' | 'adaptive_mean' | 'adaptive_gaussian' | 'sauvola'
        invert: nếu True, đảo đen<->trắng. Mặc định chữ ĐEN, nền TRẮNG.
        block_size: kích thước vùng lân cận cho adaptive (lẻ, 11-51).
        c: hằng số trừ đi từ mean trong adaptive (5-15).
        sauvola_window: kích thước cửa sổ Sauvola (lẻ, 15-35).
        sauvola_k: hệ số Sauvola (0.2-0.5). Cao -> ít text được giữ.
        sauvola_r: dynamic range của std (giữ 128 cho ảnh 8-bit).

    Returns:
        Ảnh nhị phân uint8, chữ = 0, nền = 255 (đảo nếu invert=True).
    """
    if image is None:
        raise ValueError("image is None")
    if method not in METHODS:
        raise ValueError(f"method phải là {METHODS}, nhận: {method!r}")

    gray = _to_gray(image)

    if method == "otsu":
        # Otsu: tự tìm threshold tối ưu
        _, binary = cv2.threshold(
            gray, 0, 255,
            cv2.THRESH_BINARY + cv2.THRESH_OTSU,
        )

    elif method == "adaptive_mean":
        if block_size % 2 == 0:
            block_size += 1
        binary = cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_MEAN_C,
            cv2.THRESH_BINARY,
            block_size, c,
        )

    elif method == "adaptive_gaussian":
        if block_size % 2 == 0:
            block_size += 1
        binary = cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            block_size, c,
        )

    else:  # sauvola
        if sauvola_window % 2 == 0:
            sauvola_window += 1
        binary = _sauvola_threshold(
            gray, sauvola_window, sauvola_k, sauvola_r,
        )

    if invert:
        binary = cv2.bitwise_not(binary)
    return binary
