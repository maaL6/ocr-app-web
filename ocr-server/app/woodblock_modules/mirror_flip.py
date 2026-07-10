"""
Mirror Flip Module
==================
Mộc bản khắc ngược để khi in lên giấy thì chữ đọc xuôi.
Vì vậy ảnh chụp mộc bản cần lật ngang (horizontal flip) để đọc được nội dung.

Tham số:
    direction: 'horizontal' (mặc định, lật trái-phải) | 'vertical' | 'both'
"""

import cv2
import numpy as np


def mirror_flip(image: np.ndarray, direction: str = "horizontal") -> np.ndarray:
    """
    Args:
        image: ảnh đầu vào (BGR hoặc grayscale).
        direction:
            - 'horizontal': lật quanh trục dọc (mặc định cho mộc bản).
            - 'vertical'  : lật quanh trục ngang.
            - 'both'      : lật cả hai (tương đương xoay 180°).
    Returns:
        Ảnh đã lật.
    """
    if image is None:
        raise ValueError("image is None")

    flip_codes = {"horizontal": 1, "vertical": 0, "both": -1}
    if direction not in flip_codes:
        raise ValueError(
            f"direction phải là một trong {list(flip_codes)}, nhận được: {direction!r}"
        )

    return cv2.flip(image, flip_codes[direction])
