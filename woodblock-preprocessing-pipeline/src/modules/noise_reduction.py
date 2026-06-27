"""
Noise Reduction Module
======================
Khử nhiễu ảnh. Cung cấp 4 phương pháp cho người dùng chọn theo nhu cầu.

So sánh tốc độ và chất lượng (cho ảnh ~1000x600):
    gaussian:   ~5ms  -- nhanh, làm mờ cả cạnh
    median:     ~10ms -- tốt cho nhiễu salt-pepper, giữ cạnh khá
    bilateral:  ~50ms -- giữ cạnh tốt, NÊN DÙNG cho mộc bản
    nlm:        ~500ms -- chất lượng cao nhất, chậm
                          (Non-Local Means)

Mặc định: bilateral. Là cân bằng tốt nhất giữa tốc độ + giữ nét chữ Hán Nôm.
"""

import cv2
import numpy as np


METHODS = ("gaussian", "median", "bilateral", "nlm")


def reduce_noise(
    image: np.ndarray,
    method: str = "bilateral",
    # gaussian / median: dùng ksize (lẻ)
    ksize: int = 5,
    # bilateral params
    bilateral_d: int = 9,
    bilateral_sigma_color: float = 75.0,
    bilateral_sigma_space: float = 75.0,
    # NLM params
    nlm_h: float = 10.0,
    nlm_template_size: int = 7,
    nlm_search_size: int = 21,
) -> np.ndarray:
    """
    Khử nhiễu ảnh bằng phương pháp đã chọn.

    Args:
        image: ảnh BGR hoặc grayscale.
        method: 'gaussian' | 'median' | 'bilateral' | 'nlm'
        ksize: kernel size cho gaussian/median (lẻ, 3/5/7).
        bilateral_d: đường kính vùng lân cận (5/9/15).
        bilateral_sigma_color: sigma màu. Tăng -> kết hợp nhiều màu khác nhau.
        bilateral_sigma_space: sigma không gian. Tăng -> ảnh hưởng pixel xa hơn.
        nlm_h: strength khử nhiễu cho NLM (5-15, cao = mờ hơn).
        nlm_template_size: kích thước template patch (lẻ).
        nlm_search_size: kích thước cửa sổ tìm kiếm (lẻ, lớn hơn template).

    Returns:
        Ảnh đã khử nhiễu, cùng shape và số kênh với input.
    """
    if image is None:
        raise ValueError("image is None")
    if method not in METHODS:
        raise ValueError(f"method phải là {METHODS}, nhận: {method!r}")

    if method == "gaussian":
        if ksize % 2 == 0:
            ksize += 1  # tự đảm bảo lẻ
        return cv2.GaussianBlur(image, (ksize, ksize), 0)

    if method == "median":
        if ksize % 2 == 0:
            ksize += 1
        return cv2.medianBlur(image, ksize)

    if method == "bilateral":
        return cv2.bilateralFilter(
            image, bilateral_d,
            bilateral_sigma_color, bilateral_sigma_space,
        )

    # method == 'nlm'
    if image.ndim == 2:
        return cv2.fastNlMeansDenoising(
            image, None, nlm_h,
            nlm_template_size, nlm_search_size,
        )
    return cv2.fastNlMeansDenoisingColored(
        image, None, nlm_h, nlm_h,
        nlm_template_size, nlm_search_size,
    )
