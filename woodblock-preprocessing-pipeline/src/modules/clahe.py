"""
CLAHE Module (Contrast Limited Adaptive Histogram Equalization)
================================================================
Cân bằng độ sáng cục bộ. Phù hợp với mộc bản khi ảnh chụp có vệt sáng/tối
không đều (vd: ánh đèn flash, bóng đổ).

CLAHE chia ảnh thành các ô (tile), cân bằng histogram trong từng ô,
rồi nội suy giữa các ô. clipLimit giới hạn việc khuếch đại tránh
amplify nhiễu quá mức.

Với ảnh màu, áp CLAHE lên kênh L của LAB (giữ nguyên màu, chỉ điều
chỉnh độ sáng).
"""

import cv2
import numpy as np


def apply_clahe(
    image: np.ndarray,
    clip_limit: float = 3.0,
    tile_grid_size: int = 8,
) -> np.ndarray:
    """
    Áp dụng CLAHE lên ảnh.

    Args:
        image: ảnh BGR hoặc grayscale.
        clip_limit: ngưỡng giới hạn (1.0-4.0).
            - Thấp (1.0-2.0): cân bằng nhẹ, tự nhiên.
            - Cao (3.0-4.0): tương phản mạnh, có thể amplify nhiễu.
            - Mặc định 3.0 phù hợp mộc bản.
        tile_grid_size: kích thước lưới chia ô (mặc định 8 = 8x8 ô).
            Lớn hơn = ô nhỏ hơn = điều chỉnh cục bộ hơn.

    Returns:
        Ảnh đã cân bằng, cùng số kênh với input.
    """
    if image is None:
        raise ValueError("image is None")
    if clip_limit <= 0:
        raise ValueError(f"clip_limit phải > 0, nhận: {clip_limit}")
    if tile_grid_size < 2:
        raise ValueError(f"tile_grid_size phải >= 2, nhận: {tile_grid_size}")

    clahe = cv2.createCLAHE(
        clipLimit=clip_limit,
        tileGridSize=(tile_grid_size, tile_grid_size),
    )

    if image.ndim == 2:
        # Grayscale: áp trực tiếp
        return clahe.apply(image)

    # Ảnh màu: chuyển sang LAB, áp CLAHE lên kênh L (luminance)
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    l_enhanced = clahe.apply(l)
    lab_enhanced = cv2.merge([l_enhanced, a, b])
    return cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2BGR)
