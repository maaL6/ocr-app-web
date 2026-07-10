"""
Morphological Operations Module
================================
Các phép biến đổi hình thái học, dùng để làm sạch ảnh nhị phân
sau Binarization.

5 phép cơ bản:
    erosion  -- "Bào mòn" vùng trắng. Làm chữ MỎNG đi, loại bỏ chấm nhỏ.
    dilation -- "Phồng ra" vùng trắng. Làm chữ DÀY hơn, lấp lỗ nhỏ.
    opening  -- Erosion -> Dilation. Loại nhiễu chấm trên nền trắng.
    closing  -- Dilation -> Erosion. Lấp lỗ trong chữ (nét đứt).
    gradient -- Dilation - Erosion. Lấy đường viền (cạnh).

Lưu ý: phép morphology hoạt động trên "foreground = trắng (255)".
Nếu ảnh bạn là chữ trắng/nền đen thì áp như mô tả trên.
Nếu ảnh chữ đen/nền trắng (như output từ binarize() mặc định) thì
ngược lại: opening lấp lỗ trong chữ, closing loại nhiễu chấm.
Truyền `invert_before=True` để tự xử lý cho đúng ngữ cảnh "làm sạch CHỮ".
"""

import cv2
import numpy as np


OPERATIONS = ("erosion", "dilation", "opening", "closing", "gradient")
KERNEL_SHAPES = ("rect", "ellipse", "cross")


_OP_MAP = {
    "opening":  cv2.MORPH_OPEN,
    "closing":  cv2.MORPH_CLOSE,
    "gradient": cv2.MORPH_GRADIENT,
}

_SHAPE_MAP = {
    "rect":    cv2.MORPH_RECT,
    "ellipse": cv2.MORPH_ELLIPSE,
    "cross":   cv2.MORPH_CROSS,
}


def apply_morphology(
    image: np.ndarray,
    operation: str = "closing",
    kernel_size: int = 3,
    kernel_shape: str = "rect",
    iterations: int = 1,
    invert_before: bool = False,
) -> np.ndarray:
    """
    Áp dụng phép morphology lên ảnh nhị phân.

    Args:
        image: ảnh nhị phân (grayscale uint8 với 2 giá trị 0/255).
        operation: 'erosion' | 'dilation' | 'opening' | 'closing' | 'gradient'
        kernel_size: kích thước kernel (lẻ, 3/5/7). Lớn -> tác động mạnh.
        kernel_shape: 'rect' | 'ellipse' | 'cross'.
        iterations: số lần áp dụng (1-3).
        invert_before: đảo ảnh trước khi áp morphology. Dùng khi ảnh
                       của bạn là chữ ĐEN trên nền TRẮNG nhưng muốn các
                       phép morphology hoạt động đúng ngữ cảnh "trên chữ".

    Returns:
        Ảnh đã xử lý (cùng định dạng input, đảo lại nếu invert_before=True).
    """
    if image is None:
        raise ValueError("image is None")
    if operation not in OPERATIONS:
        raise ValueError(f"operation phải là {OPERATIONS}, nhận: {operation!r}")
    if kernel_shape not in KERNEL_SHAPES:
        raise ValueError(f"kernel_shape phải là {KERNEL_SHAPES}, nhận: {kernel_shape!r}")

    if kernel_size % 2 == 0:
        kernel_size += 1

    kernel = cv2.getStructuringElement(
        _SHAPE_MAP[kernel_shape], (kernel_size, kernel_size),
    )

    work = cv2.bitwise_not(image) if invert_before else image

    if operation == "erosion":
        result = cv2.erode(work, kernel, iterations=iterations)
    elif operation == "dilation":
        result = cv2.dilate(work, kernel, iterations=iterations)
    else:
        result = cv2.morphologyEx(work, _OP_MAP[operation], kernel,
                                  iterations=iterations)

    if invert_before:
        result = cv2.bitwise_not(result)
    return result
