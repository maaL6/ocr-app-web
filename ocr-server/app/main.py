import math

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from paddleocr import PaddleOCR
import numpy as np
import cv2
import base64

from app.preprocess import preprocess_for_ocr, STAGES, NOISE_METHODS, FLIP_DIRECTIONS
from app.layout import assign_columns

app = FastAPI(title="OCR Server - PP-OCRv6 (woodblock)")

# Cho phép web frontend (chạy ở cổng khác) gọi API từ trình duyệt.
# Khi deploy thật nên thay "*" bằng domain cụ thể.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ngưỡng tham khảo từ ocr-testing/v6_current (tinh chỉnh cho mộc bản chữ Hán dọc):
# - limit_side_len lớn (2560, type=max) để KHÔNG thu nhỏ ảnh to -> giữ chữ nhỏ
#   (mặc định PaddleOCR chỉ 960, làm mất nét trên ảnh mộc bản full-page).
# - box_thresh/unclip_ratio/thresh giữ như bản v6_current đã chạy ổn.
V6_DET_REC_KWARGS = dict(
    text_det_limit_side_len=2560,
    text_det_limit_type="max",
    text_det_thresh=0.3,
    text_det_box_thresh=0.6,
    text_det_unclip_ratio=1.5,
    text_rec_score_thresh=0.0,
)

# Load model 1 LẦN lúc khởi động, không load mỗi request.
# lang="ch": model PP-OCRv6_medium hợp nhất (phồn thể + giản thể + pinyin/Anh/Nhật).
# Muốn model chuyên phồn thể (PP-OCRv3 cũ) thì đổi thành "chinese_cht".
_base_kwargs = dict(
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False,
    lang="ch",
)
try:
    ocr = PaddleOCR(**_base_kwargs, **V6_DET_REC_KWARGS)
except Exception as e:  # nếu phiên bản PaddleOCR không nhận param ngưỡng -> chạy bản tối thiểu
    print(f"[WARN] PaddleOCR không nhận ngưỡng tuỳ chỉnh ({e}); dùng cấu hình mặc định.")
    ocr = PaddleOCR(**_base_kwargs)

# Lọc box có score thấp hơn ngưỡng này sau khi nhận dạng (giống drop_score của v6_current).
DEFAULT_DROP_SCORE = 0.30


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/options")
def options():
    """Liệt kê các lựa chọn hợp lệ để web dựng UI điều khiển."""
    return {"stages": STAGES, "noise_methods": NOISE_METHODS, "flip_directions": FLIP_DIRECTIONS}


def _bgr_to_data_url(bgr) -> str:
    ok, buf = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, 90])
    if not ok:
        return ""
    return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode("ascii")


@app.post("/preprocess")
async def run_preprocess(
    file: UploadFile = File(...),
    stage: str = Form("flipped"),
    resize_width: int = Form(1600),
    canny_low: int = Form(30),
    canny_high: int = Form(120),
    deskew_range: float = Form(15.0),
    clahe_clip: float = Form(3.0),
    clahe_tile: int = Form(8),
    noise_method: str = Form("bilateral"),
    flip: str = Form("horizontal"),
):
    """Chỉ chạy tiền xử lý, trả ảnh kết quả để quan sát (KHÔNG OCR)."""
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(400, "File phải là ảnh")

    contents = await file.read()
    bgr = cv2.imdecode(np.frombuffer(contents, np.uint8), cv2.IMREAD_COLOR)
    if bgr is None:
        raise HTTPException(400, "Không đọc được ảnh")

    try:
        bgr, meta = preprocess_for_ocr(
            bgr, stage=stage, resize_width=resize_width,
            canny_low=canny_low, canny_high=canny_high, deskew_range=deskew_range,
            clahe_clip=clahe_clip, clahe_tile=clahe_tile,
            noise_method=noise_method, flip=flip,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    return {"image": _bgr_to_data_url(bgr), "preprocess": {"applied": True, **meta}}


@app.post("/ocr")
async def run_ocr(
    file: UploadFile = File(...),
    preprocess: bool = Form(True),
    stage: str = Form("flipped"),
    resize_width: int = Form(1600),
    canny_low: int = Form(30),
    canny_high: int = Form(120),
    deskew_range: float = Form(15.0),
    clahe_clip: float = Form(3.0),
    clahe_tile: int = Form(8),
    noise_method: str = Form("bilateral"),
    flip: str = Form("horizontal"),
    drop_score: float = Form(DEFAULT_DROP_SCORE),
):
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(400, "File phải là ảnh")

    contents = await file.read()
    bgr = cv2.imdecode(np.frombuffer(contents, np.uint8), cv2.IMREAD_COLOR)
    if bgr is None:
        raise HTTPException(400, "Không đọc được ảnh")

    pre_meta = None
    if preprocess:
        try:
            bgr, pre_meta = preprocess_for_ocr(
                bgr,
                stage=stage,
                resize_width=resize_width,
                canny_low=canny_low,
                canny_high=canny_high,
                deskew_range=deskew_range,
                clahe_clip=clahe_clip,
                clahe_tile=clahe_tile,
                noise_method=noise_method,
                flip=flip,
            )
        except ValueError as e:
            raise HTTPException(400, str(e))

    # PaddleOCR nhận RGB (giữ nguyên hành vi cũ). bgr ở đây là ảnh thực sự sẽ OCR.
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    result = ocr.predict(rgb)

    # Parse record kèm tâm/box-size để gom cột.
    records = []
    for res in result:
        rec_texts = res.get("rec_texts", [])
        rec_scores = res.get("rec_scores", [])
        polys = res.get("rec_polys", res.get("dt_polys", []))
        for i, t in enumerate(rec_texts):
            t = str(t)
            score = float(rec_scores[i]) if i < len(rec_scores) else 0.0
            if not t or score < drop_score:
                continue
            if i >= len(polys):
                continue
            bbox = np.asarray(polys[i], dtype=float).reshape(-1, 2).tolist()
            xs = [p[0] for p in bbox]
            ys = [p[1] for p in bbox]
            width = max(math.dist(bbox[0], bbox[1]), math.dist(bbox[2], bbox[3]), 1.0)
            records.append({
                "text": t,
                "confidence": score,
                "bbox": bbox,
                "cx": sum(xs) / len(xs),
                "cy": sum(ys) / len(ys),
                "w": width,
            })

    # Gom cột PHẢI -> TRÁI, trong cột TRÊN -> DƯỚI (quy ước mộc bản).
    columns = assign_columns(records)

    # results theo đúng thứ tự đọc (cột phải->trái, mỗi cột trên->dưới).
    ordered = [rec for col in columns for rec in col]
    results_out = [
        {"text": r["text"], "confidence": r["confidence"], "bbox": r["bbox"], "column": r["column"]}
        for r in ordered
    ]
    columns_out = [
        {
            "index": idx,
            "text": "".join(r["text"] for r in col),
            "avg_score": (sum(r["confidence"] for r in col) / len(col)) if col else 0.0,
        }
        for idx, col in enumerate(columns, start=1)
    ]
    full_text = "\n".join(c["text"] for c in columns_out)

    return {
        "results": results_out,
        "columns": columns_out,
        "full_text": full_text,
        # Ảnh thực sự được OCR (đã tiền xử lý nếu bật). Toạ độ bbox khớp ảnh này,
        # nên web vẽ overlay trực tiếp lên nó.
        "ocr_image": _bgr_to_data_url(bgr),
        "preprocess": {"applied": preprocess, **(pre_meta or {})},
    }
