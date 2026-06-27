# Woodblock Image Preprocessing Pipeline

Dự án này dùng để tiền xử lý ảnh mộc bản trước khi đọc nội dung hoặc đưa vào OCR.

Pipeline chính gồm 7 bước:

```text
corners → warp → deskew → clahe → denoise → flipped → inverted
```

Trong đó:

| Bước | Output | Ý nghĩa |
|---|---|---|
| 1 | `01_corners.jpg` | Ảnh debug hiển thị 4 góc được phát hiện |
| 2 | `02_warped.jpg` | Ảnh đã chỉnh phối cảnh |
| 3 | `03_deskewed.jpg` | Ảnh đã chỉnh nghiêng |
| 4 | `04_clahe.jpg` | Ảnh đã tăng tương phản cục bộ bằng CLAHE |
| 5 | `05_denoised.jpg` | Ảnh đã khử nhiễu |
| 6 | `06_flipped.jpg` | Ảnh đã lật ngang, phù hợp với ảnh mộc bản bị khắc ngược |
| 7 | `07_inverted.jpg` | Ảnh đã đảo màu |

---

## 1. Cấu trúc thư mục

```text
woodblock-preprocessing-pipeline/
├── README.md
├── requirements.txt
├── .gitignore
├── src/
│   ├── pipeline_7_steps.py
│   └── modules/
│       ├── __init__.py
│       ├── perspective_correction.py
│       ├── deskew.py
│       ├── clahe.py
│       ├── noise_reduction.py
│       ├── mirror_flip.py
│       ├── resize.py
│       ├── binarization.py
│       └── morphology.py
└── data/
    ├── input/
    │   └── .gitkeep
    └── output/
        └── .gitkeep
```

Ghi chú:

- `src/pipeline_7_steps.py`: file chạy chính.
- `src/modules/`: chứa các module xử lý ảnh.
- `data/input/`: đặt ảnh đầu vào tại đây.
- `data/output/`: kết quả sau khi chạy sẽ được lưu tại đây.

---

## 2. Cài đặt môi trường

### Bước 1: Clone repository

```bash
git clone https://github.com/nguyenduylamdeptrai/woodblock-preprocessing-pipeline.git
cd woodblock-preprocessing-pipeline

```

### Bước 2: Tạo môi trường ảo Python

Trên Windows PowerShell:

```bash
python -m venv .venv
.venv\Scripts\activate
```

Trên macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Bước 3: Cài thư viện

```bash
pip install -r requirements.txt
```

Thư viện chính được dùng:

- `opencv-python`
- `numpy`

---

## 3. Chuẩn bị dữ liệu

Đặt ảnh cần xử lý vào thư mục:

```text
data/input/
```

Ví dụ:

```text
data/input/
├── 53_mk50.jpg
├── 54_mk51.jpg
└── 55_mk52.png
```

Các định dạng ảnh được hỗ trợ:

```text
.jpg, .jpeg, .png, .bmp, .tif, .tiff, .webp
```

---

## 4. Chạy pipeline

Chạy lệnh sau từ thư mục gốc của project:

```bash
python src/pipeline_7_steps.py
```

Pipeline mặc định:

```text
corners → warp → deskew → clahe → denoise → flipped → inverted
```

Sau khi chạy, kết quả sẽ nằm trong:

```text
data/output/
```

Ví dụ nếu input là:

```text
data/input/53_mk50.jpg
```

thì output sẽ là:

```text
data/output/53_mk50/
├── 01_corners.jpg
├── 02_warped.jpg
├── 03_deskewed.jpg
├── 04_clahe.jpg
├── 05_denoised.jpg
├── 06_flipped.jpg
└── 07_inverted.jpg
```

Ngoài ra, file log sẽ được tạo tại:

```text
data/output/run_log.csv
```

---

## 5. Các cách chạy thường dùng

### Chạy mặc định

```bash
python src/pipeline_7_steps.py
```

### Xóa output cũ rồi chạy lại

```bash
python src/pipeline_7_steps.py --clean
```

### Chạy với folder input/output khác

```bash
python src/pipeline_7_steps.py --input data/input --output data/output
```

### Không resize ảnh đầu vào

```bash
python src/pipeline_7_steps.py --resize 0
```

### Đọc ảnh trong cả các folder con

```bash
python src/pipeline_7_steps.py --recursive
```

### Đổi phương pháp khử nhiễu

Mặc định dùng `bilateral`.

```bash
python src/pipeline_7_steps.py --noise-method bilateral
```

Các lựa chọn:

```text
gaussian, median, bilateral, nlm
```

Gợi ý:

- `bilateral`: phù hợp nhất cho mộc bản vì giữ cạnh tốt.
- `median`: tốt nếu ảnh có nhiễu chấm kiểu salt-pepper.
- `gaussian`: nhanh nhưng có thể làm mờ nét chữ.
- `nlm`: chất lượng cao nhưng chậm.

### Không lật ảnh

```bash
python src/pipeline_7_steps.py --flip none
```

### Lật ngang, mặc định cho mộc bản

```bash
python src/pipeline_7_steps.py --flip horizontal
```

---

## 6. Giải thích pipeline

### 1. Detect corners

File module:

```text
src/modules/perspective_correction.py
```

Chức năng:

- Tự động phát hiện 4 góc của mộc bản.
- Lưu ảnh debug `01_corners.jpg` để kiểm tra góc phát hiện có đúng không.

### 2. Warp

File module:

```text
src/modules/perspective_correction.py
```

Chức năng:

- Dùng 4 góc đã phát hiện để chỉnh phối cảnh.
- Output là `02_warped.jpg`.

### 3. Deskew

File module:

```text
src/modules/deskew.py
```

Chức năng:

- Chỉnh nghiêng còn sót sau bước warp.
- Output là `03_deskewed.jpg`.

### 4. CLAHE

File module:

```text
src/modules/clahe.py
```

Chức năng:

- Tăng tương phản cục bộ.
- Hữu ích khi ảnh bị bóng đổ, ánh sáng không đều hoặc nền loang.
- Output là `04_clahe.jpg`.

### 5. Denoise

File module:

```text
src/modules/noise_reduction.py
```

Chức năng:

- Khử nhiễu ảnh.
- Mặc định dùng `bilateral` để giữ nét chữ tốt hơn.
- Output là `05_denoised.jpg`.

### 6. Flipped

File module:

```text
src/modules/mirror_flip.py
```

Chức năng:

- Lật ngang ảnh mộc bản.
- Vì mộc bản thường khắc ngược để khi in ra giấy chữ đọc xuôi.
- Output là `06_flipped.jpg`.

### 7. Inverted

Trong file:

```text
src/pipeline_7_steps.py
```

Chức năng:

- Đảo màu ảnh bằng OpenCV:

```python
cv2.bitwise_not(image)
```

- Output là `07_inverted.jpg`.

---

## 7. Lỗi thường gặp

### Lỗi: `ModuleNotFoundError: No module named 'cv2'`

Nguyên nhân: chưa cài OpenCV.

Cách sửa:

```bash
pip install -r requirements.txt
```

hoặc:

```bash
pip install opencv-python numpy
```

### Lỗi: không tìm thấy ảnh input

Thông báo có dạng:

```text
[ERROR] No images found in: data/input
```

Cách sửa:

- Kiểm tra ảnh đã được đặt trong `data/input/` chưa.
- Kiểm tra định dạng ảnh có thuộc nhóm được hỗ trợ không.

### Bước detect corners thất bại

Nếu không phát hiện được 4 góc, chương trình vẫn chạy tiếp bằng ảnh gốc.

Khi đó trong log có thể thấy:

```text
Perspective failed; used original image.
```

Cách xử lý:

- Chụp ảnh rõ viền mộc bản hơn.
- Đảm bảo mộc bản chiếm phần lớn ảnh.
- Tránh nền quá phức tạp.
- Thử chỉnh tham số:

```bash
python src/pipeline_7_steps.py --canny-low 20 --canny-high 100
```

---

## 8. Gợi ý quy trình kiểm tra output

Sau khi chạy, nên kiểm tra theo thứ tự:

1. `01_corners.jpg`: 4 góc có đúng không?
2. `02_warped.jpg`: ảnh đã được kéo phẳng chưa?
3. `03_deskewed.jpg`: ảnh còn nghiêng không?
4. `04_clahe.jpg`: chữ và nền có rõ hơn không?
5. `05_denoised.jpg`: nhiễu có giảm không?
6. `06_flipped.jpg`: chữ đã đúng chiều chưa?
7. `07_inverted.jpg`: màu đã đảo đúng mục tiêu chưa?

Nếu chỉ cần ảnh cuối cùng, dùng:

```text
07_inverted.jpg
```

Nếu cần ảnh trước khi đảo màu, dùng:

```text
06_flipped.jpg
```

---

## 9. Push lên GitHub

Sau khi tạo repo trên GitHub, chạy các lệnh sau trong thư mục project:

```bash
git init
git add .
git commit -m "Initial woodblock preprocessing pipeline"
git branch -M main
git remote add origin <LINK_REPOSITORY_CUA_BAN>
git push -u origin main
```

Ví dụ:

```bash
git remote add origin https://github.com/username/woodblock-preprocessing-pipeline.git
git push -u origin main
```

---

## 10. Ghi chú về dữ liệu ảnh

Mặc định `.gitignore` đang bỏ qua output sinh ra trong:

```text
data/output/
```

Vì output thường nhiều và dung lượng lớn.

Nếu không muốn upload ảnh input lên GitHub, mở file `.gitignore` và bỏ comment các dòng sau:

```gitignore
data/input/*
!data/input/.gitkeep
```
