# Per-Character Confidence Changes

## Mục tiêu

API `POST /ocr` trả thêm field mới cho từng dòng OCR:

```json
"per_char_confidences": [0.99, 0.87, 0.93]
```

và top-k ký tự ứng viên mà model đã cân nhắc ở từng vị trí:

```json
"char_candidates": [
  [
    {"char": "圖", "confidence": 0.99},
    {"char": "圆", "confidence": 0.01}
  ]
]
```

Các field này có độ dài luôn bằng `len(text)` khi cờ tương ứng được bật:

- `return_char_confidence=true`: trả `per_char_confidences`.
- `return_char_candidates=true`: trả `char_candidates`.

Mặc định hai cờ đều tắt để giữ response cũ gọn và tương thích.

## File đã sửa / thêm

- `app/main.py`
  - Import và gọi `apply_paddleocr_char_confidence_patch()` trước khi khởi tạo `PaddleOCR`.
  - Bật `return_word_box=True` trong config OCR.
  - Giữ form field cũ `return_char_confidence`, default là `false`.
  - Thêm form field mới `return_char_candidates`, default là `false`.
  - Thêm helper `normalize_char_confidences(...)`.
  - Thêm helper `normalize_char_candidates(...)`.
  - Thêm field `per_char_confidences` vào mỗi item trong `results` khi bật `return_char_confidence`.
  - Thêm field `char_candidates` vào mỗi item trong `results` và thêm
    `candidates` trong từng phần tử `chars` khi bật `return_char_candidates`.
  - Giữ nguyên các field cũ: `text`, `confidence`, `bbox`, `column`, `columns`, `full_text`, `ocr_image`, `preprocess`.
  - Nếu lấy được score từng ký tự thật từ decoder thì dùng score đó.
  - Nếu không lấy được thì fallback `[confidence] * len(text)` và có comment rõ trong code.

- `app/paddleocr_char_confidence_patch.py`
  - Monkey patch `BaseRecLabelDecode.decode()` của PaddleOCR/PaddleX.
  - Monkey patch thêm `CTCLabelDecode.__call__()` để lấy top-k ứng viên từ
    full probability matrix trước khi PaddleOCR rút gọn bằng `argmax`.
  - PaddleOCR vốn đã tính `conf_list = text_prob[batch_idx][selection]` trong decoder, nhưng mặc định chỉ trả trung bình `np.mean(conf_list)` làm line score.
  - Patch này giữ `rec_score` là float-compatible, đồng thời gắn thêm attribute `char_confidences` và `char_candidates`.
  - Backend đọc các attribute này để xuất `per_char_confidences` và `char_candidates`.

- `app/preprocess.py`
  - Thêm fallback import `woodblock-preprocessing-pipeline/src/modules` khi chạy
    local bằng `uvicorn` mà chưa có `app/woodblock_modules` được vendor bởi Dockerfile.

- `scripts/test_per_char_confidences.py`
  - Script gọi API `/ocr` với một ảnh bất kỳ.
  - Gửi cả `return_char_confidence=true` và `return_char_candidates=true`.
  - In `text`, `confidence`, `per_char_confidences`, `char_candidates`.
  - Assert `len(text) == len(per_char_confidences) == len(char_candidates)`.

## Response mới

Ví dụ mỗi dòng trong `results`:

```json
{
  "text": "圖家見官物多損敝",
  "confidence": 0.9810970425605774,
  "per_char_confidences": [0.99, 0.98, 0.72, 0.95, 0.94, 0.99, 0.97, 0.96],
  "char_candidates": [
    [{"char": "圖", "confidence": 0.99}, {"char": "圓", "confidence": 0.01}],
    [{"char": "家", "confidence": 0.98}, {"char": "冢", "confidence": 0.02}]
  ],
  "char_candidates_available": true,
  "bbox": [[1035, 177], [1082, 177], [1082, 853], [1035, 853]],
  "column": 5
}
```

Nếu chỉ bật một cờ thì response chỉ có nhóm field tương ứng. Ví dụ không bật
`return_char_candidates` thì sẽ không có `char_candidates`.

## Có phải score thật không?

Có, khi patch lấy được `char_confidences`, các giá trị đến từ `conf_list` thật
trong decoder của PaddleOCR/PaddleX.

Không phải số random hoặc tự bịa. Chỉ fallback bằng line confidence khi không
lấy được `conf_list`.

`char_candidates` cũng lấy từ output xác suất thật của model, trước bước CTC
loại blank/ký tự trùng. Mặc định mỗi ký tự giữ top 10 ứng viên, không bao gồm
CTC blank.

## Cách test

Chạy server:

```bash
docker compose up --build
```

Gọi test script:

```bash
python3 scripts/test_per_char_confidences.py /duong/dan/anh.jpg
```

Kiểm tra nhanh cú pháp:

```bash
python3 -m py_compile app/main.py app/paddleocr_char_confidence_patch.py scripts/test_per_char_confidences.py
```

## Lưu ý merge từ `ocr-server-new`

- Đã lấy phần source cần thiết từ `ocr-server-new`.
- Không merge `.venv/`, `__pycache__/`, `.DS_Store` vì đây là môi trường/cache local.
- `confidence` vẫn là score dòng/box OCR như trước.
- `per_char_confidences` là score từng ký tự sau decode CTC.
- `char_candidates` là danh sách top-k ký tự ứng viên theo từng ký tự OCR đã
  được giữ lại sau CTC.
- Confidence không phải accuracy tuyệt đối; nên dùng để highlight ký tự nghi ngờ, ví dụ `< 0.75`.
- Repo server hiện tại chưa thấy tầng BERT post-correction, nên chưa có phần BERT để sửa.
