import math

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from paddleocr import PaddleOCR
import numpy as np
import cv2
import base64

from app.routers.auth import router as auth_router
from app.preprocess import preprocess_for_ocr, STAGES, NOISE_METHODS, FLIP_DIRECTIONS
from app.layout import assign_columns
from app.paddleocr_char_confidence_patch import apply_paddleocr_char_confidence_patch

app = FastAPI(title="OCR Server - PP-OCRv6 (woodblock)")
app.include_router(auth_router)

apply_paddleocr_char_confidence_patch()

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
    # Bật word/char boxes; per-character confidence được lấy từ decoder patch
    # trong app/paddleocr_char_confidence_patch.py nếu PaddleOCR giữ được conf_list.
    return_word_box=True,
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


def _as_plain_list(value):
    if hasattr(value, "tolist"):
        return value.tolist()
    if isinstance(value, tuple):
        return [_as_plain_list(item) for item in value]
    if isinstance(value, list):
        return [_as_plain_list(item) for item in value]
    return value


def normalize_char_confidences(text, confidence, char_confidences=None):
    # Fallback tạm thời: nếu PaddleOCR không expose được conf_list thật từ
    # decoder thì lặp line confidence cho từng ký tự để giữ contract API.
    if char_confidences is None:
        return [float(confidence)] * len(text)

    values = [float(item) for item in char_confidences]
    if len(values) > len(text):
        values = values[:len(text)]
    if len(values) < len(text):
        values.extend([float(confidence)] * (len(text) - len(values)))
    return values


def _extract_char_confidences_from_score(score):
    char_confidences = getattr(score, "char_confidences", None)
    if char_confidences is None:
        return None
    return [float(item) for item in char_confidences]


def normalize_char_candidates(text, char_candidates=None):
    empty_candidates = [[] for _ in text]
    if char_candidates is None:
        return empty_candidates

    values = []
    for candidates in char_candidates:
        normalized_candidates = []
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            if "char" not in candidate or "confidence" not in candidate:
                continue
            normalized_candidates.append({
                "char": str(candidate["char"]),
                "confidence": float(candidate["confidence"]),
            })
        values.append(normalized_candidates)

    if len(values) > len(text):
        values = values[:len(text)]
    if len(values) < len(text):
        values.extend(empty_candidates[len(values):])
    return values


def _extract_char_candidates_from_score(score):
    char_candidates = getattr(score, "char_candidates", None)
    if char_candidates is None:
        return None
    return normalize_char_candidates("x" * len(char_candidates), char_candidates)


def _parse_chars_with_scores(text: str, rec_chars, rec_words=None, rec_word_boxes=None):
    if not text:
        return []

    boxes_by_char = {}
    if (
        isinstance(rec_words, (list, tuple))
        and isinstance(rec_word_boxes, (list, tuple))
        and len(rec_words) == len(rec_word_boxes)
    ):
        cursor = 0
        for word, box in zip(rec_words, rec_word_boxes):
            word = str(word)
            if len(word) == 1 and cursor < len(text) and text[cursor] == word:
                boxes_by_char[cursor] = _as_plain_list(box)
                cursor += 1
            else:
                cursor += len(word)

    if isinstance(rec_chars, (list, tuple)) and len(rec_chars) == len(text):
        chars = []
        for idx, item in enumerate(rec_chars):
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                chars.append({
                    "char": str(item[0]),
                    "confidence": float(item[1]),
                    "confidence_source": "rec_chars",
                    "candidates": [],
                    "candidate_source": None,
                    "bbox": boxes_by_char.get(idx),
                })
            elif isinstance(item, dict):
                has_confidence = "confidence" in item and item["confidence"] is not None
                chars.append({
                    "char": str(item.get("char", text[idx])),
                    "confidence": float(item["confidence"]) if has_confidence else None,
                    "confidence_source": "rec_chars" if has_confidence else None,
                    "candidates": [],
                    "candidate_source": None,
                    "bbox": boxes_by_char.get(idx),
                })
            else:
                chars.append({
                    "char": text[idx],
                    "confidence": None,
                    "confidence_source": None,
                    "candidates": [],
                    "candidate_source": None,
                    "bbox": boxes_by_char.get(idx),
                })
        return chars

    return [
        {
            "char": ch,
            "confidence": None,
            "confidence_source": None,
            "candidates": [],
            "candidate_source": None,
            "bbox": boxes_by_char.get(idx),
        }
        for idx, ch in enumerate(text)
    ]


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
    return_char_confidence: bool = Form(False),
    return_char_candidates: bool = Form(False),
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
    return_char_metadata = return_char_confidence or return_char_candidates
    result = ocr.predict(rgb, return_word_box=return_char_metadata)

    # Parse record kèm tâm/box-size để gom cột.
    records = []
    for res in result:
        rec_texts = res.get("rec_texts", [])
        rec_scores = res.get("rec_scores", [])
        polys = res.get("rec_polys", res.get("dt_polys", []))
        rec_chars_all = res.get("rec_chars", [])
        rec_words_all = res.get("text_word", [])
        rec_word_boxes_all = res.get("text_word_region", res.get("text_word_boxes", []))
        for i, t in enumerate(rec_texts):
            t = str(t)
            raw_score = rec_scores[i] if i < len(rec_scores) else 0.0
            score = float(raw_score)
            if not t or score < drop_score:
                continue
            if i >= len(polys):
                continue

            rec_chars_for_text = None
            if isinstance(rec_chars_all, (list, tuple)):
                if len(rec_chars_all) == len(rec_texts):
                    rec_chars_for_text = rec_chars_all[i]
                else:
                    rec_chars_for_text = rec_chars_all

            rec_words_for_text = rec_words_all[i] if i < len(rec_words_all) else None
            rec_word_boxes_for_text = (
                rec_word_boxes_all[i] if i < len(rec_word_boxes_all) else None
            )

            chars = _parse_chars_with_scores(
                t,
                rec_chars_for_text,
                rec_words=rec_words_for_text,
                rec_word_boxes=rec_word_boxes_for_text,
            )
            decoder_char_confidences = _extract_char_confidences_from_score(raw_score)
            per_char_confidences = normalize_char_confidences(
                t,
                score,
                decoder_char_confidences,
            )
            decoder_char_candidates = _extract_char_candidates_from_score(raw_score)
            char_candidates = normalize_char_candidates(t, decoder_char_candidates)
            char_confidence_available = decoder_char_confidences is not None
            char_candidates_available = decoder_char_candidates is not None
            if return_char_confidence and char_confidence_available:
                for idx, char in enumerate(chars):
                    char["confidence"] = per_char_confidences[idx]
                    char["confidence_source"] = "decoder_conf_list"
            if return_char_candidates and char_candidates_available:
                for idx, char in enumerate(chars):
                    char["candidates"] = char_candidates[idx]
                    char["candidate_source"] = "decoder_topk"
            char_box_available = any(char["bbox"] is not None for char in chars)
            bbox = np.asarray(polys[i], dtype=float).reshape(-1, 2).tolist()
            xs = [p[0] for p in bbox]
            ys = [p[1] for p in bbox]
            width = max(math.dist(bbox[0], bbox[1]), math.dist(bbox[2], bbox[3]), 1.0)
            
            record = {
                "text": t,
                "confidence": score,
                "bbox": bbox,
                "cx": sum(xs) / len(xs),
                "cy": sum(ys) / len(ys),
                "w": width,
            }
            if return_char_confidence:
                record.update({
                    "per_char_confidences": per_char_confidences,
                    "chars": chars,
                    "char_confidence_available": char_confidence_available,
                    "char_box_available": char_box_available,
                })
            if return_char_candidates:
                record.update({
                    "char_candidates": char_candidates,
                    "char_candidates_available": char_candidates_available,
                })
                record.setdefault("chars", chars)
                record.setdefault("char_box_available", char_box_available)
            records.append(record)

    # Gom cột PHẢI -> TRÁI, trong cột TRÊN -> DƯỚI (quy ước mộc bản).
    columns = assign_columns(records)

    # results theo đúng thứ tự đọc (cột phải->trái, mỗi cột trên->dưới).
    ordered = [rec for col in columns for rec in col]
    results_out = []
    for r in ordered:
        item = {
            "text": r["text"],
            "confidence": r["confidence"],
            "bbox": r["bbox"],
            "column": r["column"],
        }
        if return_char_confidence:
            item.update({
                "per_char_confidences": r.get("per_char_confidences", []),
                "chars": r.get("chars", []),
                "char_confidence_available": r.get("char_confidence_available", False),
                "char_box_available": r.get("char_box_available", False),
            })
        if return_char_candidates:
            item.update({
                "char_candidates": r.get("char_candidates", []),
                "char_candidates_available": r.get("char_candidates_available", False),
            })
            item.setdefault("chars", r.get("chars", []))
            item.setdefault("char_box_available", r.get("char_box_available", False))
        results_out.append(item)
        
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
