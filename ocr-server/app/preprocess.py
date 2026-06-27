"""
Tiền xử lý ảnh mộc bản (in-memory) cho OCR.

Tái dùng trực tiếp các module của woodblock-preprocessing-pipeline (được vendor
vào app/woodblock_modules trong Docker — xem Dockerfile). KHÔNG ghi file ra đĩa
như CLI gốc; mọi thứ chạy trên numpy array trong RAM.

Pipeline gốc: warped -> deskewed -> clahe -> denoised -> flipped -> inverted
Có thể dừng ở bất kỳ `stage` nào để so sánh chất lượng OCR.

Ảnh vào/ra đều là BGR (chuẩn OpenCV).
"""

import cv2

from app.woodblock_modules import (
    auto_perspective_correction,
    deskew,
    apply_clahe,
    reduce_noise,
    mirror_flip,
    resize_by_width,
)

# Thứ tự các stage; OCR có thể nhận đầu ra ở bất kỳ stage nào.
STAGES = ["warped", "deskewed", "clahe", "denoised", "flipped", "inverted"]
NOISE_METHODS = ["gaussian", "median", "bilateral", "nlm"]
FLIP_DIRECTIONS = ["horizontal", "vertical", "both", "none"]


def preprocess_for_ocr(
    bgr,
    *,
    stage: str = "flipped",
    resize_width: int = 1600,
    canny_low: int = 30,
    canny_high: int = 120,
    deskew_range: float = 15.0,
    clahe_clip: float = 3.0,
    clahe_tile: int = 8,
    noise_method: str = "bilateral",
    flip: str = "horizontal",
):
    """
    Chạy pipeline tiền xử lý tới `stage` rồi trả về (ảnh_bgr, meta).

    meta gồm: strategy phát hiện góc, có auto-detect được không, góc nghiêng,
    kích thước vào/ra — để hiển thị/đánh giá trên web.
    """
    if stage not in STAGES:
        raise ValueError(f"stage phải thuộc {STAGES}, nhận: {stage!r}")

    meta = {
        "stage": stage,
        "strategy": None,
        "auto_detected": False,
        "skew_angle": 0.0,
        "input_shape": f"{bgr.shape[1]}x{bgr.shape[0]}",
        "output_shape": None,
    }

    img = bgr
    if resize_width > 0 and img.shape[1] > resize_width:
        img = resize_by_width(img, resize_width)

    # 1+2. Phát hiện 4 góc + nắn phối cảnh. Thất bại thì dùng ảnh hiện tại.
    warped, _corners, strategy = auto_perspective_correction(
        img, canny_low=canny_low, canny_high=canny_high, return_strategy=True
    )
    if warped is not None:
        meta["auto_detected"] = True
        meta["strategy"] = strategy
        img = warped

    if stage != "warped":
        # 3. Deskew
        img, angle = deskew(img, angle_range=deskew_range, return_angle=True)
        meta["skew_angle"] = round(float(angle), 3)

    if stage in ("clahe", "denoised", "flipped", "inverted"):
        # 4. CLAHE
        img = apply_clahe(img, clip_limit=clahe_clip, tile_grid_size=clahe_tile)

    if stage in ("denoised", "flipped", "inverted"):
        # 5. Khử nhiễu
        img = reduce_noise(img, method=noise_method)

    if stage in ("flipped", "inverted"):
        # 6. Lật (mộc bản khắc ngược -> lật ngang để chữ đọc xuôi)
        if flip != "none":
            img = mirror_flip(img, direction=flip)

    if stage == "inverted":
        # 7. Đảo màu
        img = cv2.bitwise_not(img)

    meta["output_shape"] = f"{img.shape[1]}x{img.shape[0]}"
    return img, meta
