"""
Deskew Module
=============
Chỉnh nghiêng còn sót sau Perspective Correction.

Mộc bản có các đường vách ngăn cột (column separators) rất rõ và DÀI.
Dùng HoughLinesP với minLineLength lớn để CHỈ bắt các đường dài này,
loại bỏ nhiễu từ nét chữ Hán Nôm ngắn. Sau đó tính góc trung bình
và xoay ảnh.

API:
    estimate_skew_angle(image, ...) -> float (góc lệch theo độ)
    deskew(image, ...) -> rotated image (hoặc tuple nếu return_angle=True)
"""

import cv2
import numpy as np


def estimate_skew_angle(
    image: np.ndarray,
    angle_range: float = 15.0,
    canny_low: int = 50,
    canny_high: int = 150,
    min_line_length_ratio: float = 0.3,
    hough_threshold: int = 80,
) -> float:
    """
    Ước lượng góc nghiêng (độ) bằng HoughLinesP.

    Args:
        image: ảnh BGR hoặc grayscale.
        angle_range: chỉ xét đường lệch khỏi trục dọc <= angle_range độ.
        canny_low, canny_high: ngưỡng Canny.
        min_line_length_ratio: chiều dài tối thiểu của đường, tính theo
                               tỉ lệ với chiều cao ảnh (0.3 = 30% chiều cao).
                               Mộc bản: vách ngăn cột thường > 70% chiều cao.
        hough_threshold: ngưỡng tích lũy Hough.

    Returns:
        Góc nghiêng (độ). Sign: âm = ảnh đang lệch CCW (cần xoay CW để sửa).
        Trả 0.0 nếu không tìm được đường nào hợp lệ.
    """
    if image.ndim == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()

    h, w = gray.shape[:2]
    min_line_length = int(min_line_length_ratio * h)

    edges = cv2.Canny(gray, canny_low, canny_high)

    # HoughLinesP trả về các đoạn thẳng (x1, y1, x2, y2)
    # maxLineGap: nối các đoạn ngắt nhau nhỏ hơn pixel này
    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 360,
        threshold=hough_threshold,
        minLineLength=min_line_length,
        maxLineGap=20,
    )
    if lines is None or len(lines) == 0:
        return 0.0

    angles = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        dx = x2 - x1
        dy = y2 - y1
        if dy == 0:
            continue  # đường ngang tuyệt đối, không quan tâm
        # Góc của đường so với trục dọc (trục y).
        # arctan2(dx, dy) cho góc theta sao cho:
        #   - theta = 0 khi đường thẳng đứng (dx=0, dy>0)
        #   - theta > 0 khi đường nghiêng phải (dx>0)
        theta = np.degrees(np.arctan2(dx, dy))
        # Wrap về [-90, 90]
        if theta > 90:
            theta -= 180
        elif theta < -90:
            theta += 180
        if abs(theta) < angle_range:
            angles.append(theta)

    if not angles:
        return 0.0

    return float(np.median(angles))


def deskew(
    image: np.ndarray,
    angle_range: float = 15.0,
    canny_low: int = 50,
    canny_high: int = 150,
    min_line_length_ratio: float = 0.3,
    hough_threshold: int = 80,
    min_angle: float = 0.1,
    return_angle: bool = False,
):
    """
    Tự động chỉnh nghiêng ảnh.

    Args:
        image: ảnh đầu vào.
        angle_range: dải tìm kiếm (độ). Sau perspective correction thường < 5°.
        canny_low, canny_high: ngưỡng Canny.
        min_line_length_ratio: chiều dài tối thiểu của đường (tỉ lệ với chiều
                               cao ảnh). Tăng để selective hơn (ít nhiễu).
        hough_threshold: ngưỡng Hough.
        min_angle: bỏ qua xoay nếu góc < min_angle độ.
        return_angle: nếu True, trả về (rotated, angle).

    Returns:
        Mặc định: ảnh đã xoay.
        return_angle: (ảnh đã xoay, góc đã áp dụng).
    """
    angle = estimate_skew_angle(
        image, angle_range, canny_low, canny_high,
        min_line_length_ratio, hough_threshold,
    )

    if abs(angle) < min_angle:
        return (image, angle) if return_angle else image

    h, w = image.shape[:2]
    center = (w // 2, h // 2)
    # estimate_skew_angle: dương = ảnh đang lệch CCW (top-left, bottom-right).
    # Để sửa, cần xoay CW = NEGATIVE trong convention của OpenCV.
    # Vậy ta truyền -angle vào getRotationMatrix2D.
    M = cv2.getRotationMatrix2D(center, -angle, 1.0)

    # Bbox mới sau khi xoay (tránh cắt nội dung)
    cos = abs(M[0, 0])
    sin = abs(M[0, 1])
    new_w = int(h * sin + w * cos)
    new_h = int(h * cos + w * sin)
    M[0, 2] += (new_w / 2) - center[0]
    M[1, 2] += (new_h / 2) - center[1]

    rotated = cv2.warpAffine(
        image, M, (new_w, new_h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )
    return (rotated, angle) if return_angle else rotated
