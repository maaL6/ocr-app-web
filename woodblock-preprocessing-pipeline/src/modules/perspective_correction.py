"""
Perspective Correction Module (v2 — multi-strategy)
====================================================
Auto mode dùng 3 strategy xếp tầng (fail-over):
    1. Canny edges + approxPolyDP (cho ảnh sạch, cạnh rõ)
    2. Otsu threshold + approxPolyDP (cho ảnh tương phản đen-trắng cao)
    3. Otsu threshold + minAreaRect (fallback, luôn cho 4 góc)

Tất cả kết quả phải qua validate (diện tích đủ lớn, aspect ratio hợp lý)
trước khi được chấp nhận.

API ngược tương thích: auto_perspective_correction(...) -> (warped, corners)
"""

import cv2
import numpy as np


# ============================================================
#  Helpers
# ============================================================

def _order_points(pts: np.ndarray) -> np.ndarray:
    pts = pts.reshape(4, 2).astype(np.float32)
    ordered = np.zeros((4, 2), dtype=np.float32)
    s = pts.sum(axis=1)
    ordered[0] = pts[np.argmin(s)]      # tl
    ordered[2] = pts[np.argmax(s)]      # br
    d = np.diff(pts, axis=1).ravel()
    ordered[1] = pts[np.argmin(d)]      # tr
    ordered[3] = pts[np.argmax(d)]      # bl
    return ordered


def _four_point_warp(image: np.ndarray, corners: np.ndarray) -> np.ndarray:
    tl, tr, br, bl = corners
    max_width  = int(max(np.linalg.norm(tr - tl), np.linalg.norm(br - bl)))
    max_height = int(max(np.linalg.norm(bl - tl), np.linalg.norm(br - tr)))
    dst = np.array(
        [[0, 0], [max_width - 1, 0],
         [max_width - 1, max_height - 1], [0, max_height - 1]],
        dtype=np.float32,
    )
    M = cv2.getPerspectiveTransform(corners, dst)
    return cv2.warpPerspective(image, M, (max_width, max_height))


def _validate_corners(corners: np.ndarray, img_shape, min_area_ratio: float) -> bool:
    """Kiểm tra 4 góc hợp lý không: diện tích đủ, aspect ratio mộc bản,
    không có góc trùng nhau."""
    if corners is None or len(corners) != 4:
        return False
    h, w = img_shape[:2]
    img_area = h * w

    area = cv2.contourArea(corners.astype(np.float32))
    if area < min_area_ratio * img_area:
        return False

    rect = cv2.minAreaRect(corners.astype(np.float32))
    (_, _), (rw, rh), _ = rect
    if rw < 30 or rh < 30:
        return False
    aspect = max(rw, rh) / max(min(rw, rh), 1)
    if aspect < 1.2 or aspect > 5.0:
        return False

    for i in range(4):
        for j in range(i + 1, 4):
            if np.linalg.norm(corners[i] - corners[j]) < 20:
                return False
    return True


def _largest_contour(mask: np.ndarray, min_area: float):
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    biggest = max(contours, key=cv2.contourArea)
    if cv2.contourArea(biggest) < min_area:
        return None
    return biggest


# ============================================================
#  Strategy 1: Canny + approxPolyDP
# ============================================================

def _strategy_canny(image, canny_low, canny_high, blur_ksize, min_area_ratio):
    h, w = image.shape[:2]
    min_area = min_area_ratio * h * w

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image.copy()
    blurred = cv2.GaussianBlur(gray, (blur_ksize, blur_ksize), 0)
    edges = cv2.Canny(blurred, canny_low, canny_high)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)

    for cnt in contours[:10]:
        if cv2.contourArea(cnt) < min_area:
            break
        peri = cv2.arcLength(cnt, True)
        for eps in (0.02, 0.03, 0.015, 0.04, 0.01):
            approx = cv2.approxPolyDP(cnt, eps * peri, True)
            if len(approx) == 4:
                corners = _order_points(approx)
                if _validate_corners(corners, image.shape, min_area_ratio):
                    return corners
    return None


# ============================================================
#  Strategy 2: Otsu + approxPolyDP
# ============================================================

def _strategy_otsu_poly(image, min_area_ratio):
    h, w = image.shape[:2]
    min_area = min_area_ratio * h * w

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image.copy()
    blurred = cv2.GaussianBlur(gray, (7, 7), 0)
    # INV vì mộc bản tối < nền sáng -> đảo để mộc bản = trắng (foreground)
    _, mask = cv2.threshold(blurred, 0, 255,
                            cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    kernel = np.ones((15, 15), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)

    cnt = _largest_contour(mask, min_area)
    if cnt is None:
        return None

    peri = cv2.arcLength(cnt, True)
    for eps in (0.02, 0.03, 0.015, 0.04, 0.01):
        approx = cv2.approxPolyDP(cnt, eps * peri, True)
        if len(approx) == 4:
            corners = _order_points(approx)
            if _validate_corners(corners, image.shape, min_area_ratio):
                return corners
    return None


# ============================================================
#  Strategy 3: Otsu + minAreaRect (fallback)
# ============================================================

def _strategy_otsu_minrect(image, min_area_ratio):
    h, w = image.shape[:2]
    min_area = min_area_ratio * h * w

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image.copy()
    blurred = cv2.GaussianBlur(gray, (7, 7), 0)
    _, mask = cv2.threshold(blurred, 0, 255,
                            cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    kernel = np.ones((15, 15), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)

    cnt = _largest_contour(mask, min_area)
    if cnt is None:
        return None

    rect = cv2.minAreaRect(cnt)
    box = cv2.boxPoints(rect)
    corners = _order_points(box)
    return corners if _validate_corners(corners, image.shape, min_area_ratio) else None


# ============================================================
#  Public API
# ============================================================

def auto_perspective_correction(
    image: np.ndarray,
    canny_low: int = 30,
    canny_high: int = 120,
    blur_ksize: int = 5,
    min_area_ratio: float = 0.1,
    return_strategy: bool = False,
):
    """
    Tự động phát hiện 4 góc của mộc bản. Thử 3 strategy theo thứ tự,
    dùng cái đầu tiên thành công.

    Returns:
        Mặc định:         (warped, corners) hoặc (None, None)
        return_strategy:  (warped, corners, strategy_name)
            strategy_name: 'canny' | 'otsu_poly' | 'otsu_minrect' | None
    """
    if image is None:
        raise ValueError("image is None")

    strategies = [
        ("canny",        lambda: _strategy_canny(image, canny_low, canny_high,
                                                 blur_ksize, min_area_ratio)),
        ("otsu_poly",    lambda: _strategy_otsu_poly(image, min_area_ratio)),
        ("otsu_minrect", lambda: _strategy_otsu_minrect(image, min_area_ratio)),
    ]

    for name, fn in strategies:
        corners = fn()
        if corners is not None:
            warped = _four_point_warp(image, corners)
            if return_strategy:
                return warped, corners, name
            return warped, corners

    if return_strategy:
        return None, None, None
    return None, None


def manual_perspective_correction(image: np.ndarray, corners: np.ndarray):
    corners = np.asarray(corners, dtype=np.float32)
    if corners.shape != (4, 2):
        raise ValueError(f"corners phải có shape (4, 2), nhận: {corners.shape}")
    ordered = _order_points(corners)
    return _four_point_warp(image, ordered), ordered


def draw_corners(image: np.ndarray, corners: np.ndarray) -> np.ndarray:
    out = image.copy()
    pts = corners.astype(int).reshape(-1, 1, 2)
    cv2.polylines(out, [pts], isClosed=True, color=(0, 255, 0), thickness=4)
    for i, (x, y) in enumerate(corners.astype(int)):
        cv2.circle(out, (x, y), 12, (0, 0, 255), -1)
        cv2.putText(out, str(i), (x + 15, y + 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3)
    return out