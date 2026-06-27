# ocr-app-web

Ứng dụng OCR mộc bản Hán–Nôm, gồm server xử lý ảnh + nhận dạng và các client web / mobile.

## Cấu trúc

| Thư mục | Mô tả | Công nghệ |
|---|---|---|
| `ocr-server/` | API OCR: tiền xử lý ảnh + nhận dạng (PP-OCRv6) + phân cột | FastAPI, PaddleOCR, OpenCV |
| `web/` | Giao diện web upload ảnh và xem kết quả | React + Vite |
| `mobile/` | App di động | Expo / React Native |
| `woodblock-preprocessing-pipeline/` | Pipeline tiền xử lý ảnh mộc bản (xem README riêng trong thư mục) | Python |

## Yêu cầu môi trường

- **Python** 3.11 (cho `ocr-server`)
- **Node.js** 18+ và npm (cho `web` và `mobile`)
- **Docker** (tùy chọn, nếu muốn chạy server bằng container)
- Điện thoại có app **Expo Go** hoặc máy ảo Android/iOS (cho `mobile`)

> Thứ tự khởi động: chạy **OCR server trước**, rồi mới chạy web/mobile vì chúng gọi tới server.

---

## 1. OCR server (`ocr-server/`)

API nhận ảnh, tiền xử lý và trả về kết quả nhận dạng.

### Cách A — Chạy bằng Python (khuyến nghị khi dev)

```bash
cd ocr-server

# Tạo môi trường ảo
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\activate
# macOS/Linux:
# source .venv/bin/activate

# Cài thư viện (lần đầu sẽ hơi lâu vì có paddlepaddle/paddleocr)
pip install -r requirements.txt

# Chạy server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

> Lần chạy đầu PaddleOCR sẽ **tải model về** nên cần mạng và mất vài phút.

### Cách B — Chạy bằng Docker

```bash
cd ocr-server
docker compose up --build
```

Model được cache trong volume `paddle_models` nên các lần build sau không phải tải lại.

### Kiểm tra server đã chạy

Server chạy ở `http://localhost:8000`. Các endpoint chính:

| Method | Đường dẫn | Chức năng |
|---|---|---|
| GET | `/health` | Kiểm tra server sống |
| GET | `/options` | Danh sách tùy chọn tiền xử lý (stage, khử nhiễu, hướng lật...) |
| POST | `/preprocess` | Chỉ tiền xử lý ảnh, trả ảnh kết quả |
| POST | `/ocr` | Tiền xử lý + nhận dạng chữ |

Mở tài liệu API tương tác (Swagger) tại: `http://localhost:8000/docs`

Kiểm tra nhanh bằng curl:
```bash
curl http://localhost:8000/health
```

---

## 2. Web (`web/`)

Giao diện upload ảnh và xem kết quả OCR.

```bash
cd web

# Cài dependency
npm install

# Cấu hình URL server (xem mục Cấu hình bên dưới)
cp .env.example .env

# Chạy dev server
npm run dev
```

Mở trình duyệt tại địa chỉ Vite in ra (mặc định `http://localhost:5173`).

Build bản production:
```bash
npm run build      # tạo thư mục dist/
npm run preview    # xem thử bản build
```

---

## 3. Mobile (`mobile/`)

App Expo / React Native.

```bash
cd mobile

# Cài dependency
npm install

# Khởi động Expo
npm start
# hoặc chạy thẳng trên thiết bị:
npm run android
npm run ios
npm run web
```

Sau khi `npm start`, quét QR code bằng app **Expo Go** trên điện thoại, hoặc nhấn `a`/`i` để mở máy ảo Android/iOS.

> **Lưu ý:** điện thoại và máy chạy server phải cùng mạng LAN. Trong app, mở phần cài đặt địa chỉ server và nhập IP máy tính thay vì `localhost`, ví dụ `http://192.168.1.10:8000` (xem IP bằng `ipconfig` trên Windows hoặc `ifconfig`/`ip a` trên macOS/Linux). App lưu địa chỉ này trong AsyncStorage.

---

## Cấu hình

### Web
Web đọc URL server từ biến `VITE_API_BASE` trong file `web/.env`:
```env
VITE_API_BASE=http://localhost:8000
```
Đổi giá trị này nếu server chạy ở host/cổng khác, rồi **restart `npm run dev`**.

### Mobile
Địa chỉ server được nhập trực tiếp trong app và lưu vào AsyncStorage (không dùng file `.env`).

---

## 4. Pipeline tiền xử lý mộc bản (`woodblock-preprocessing-pipeline/`)

Pipeline Python 7 bước (corners → warp → deskew → clahe → denoise → flipped → inverted) để xử lý ảnh trước OCR.
Hướng dẫn chi tiết nằm trong [`woodblock-preprocessing-pipeline/README.md`](woodblock-preprocessing-pipeline/README.md).

Chạy nhanh:
```bash
cd woodblock-preprocessing-pipeline
python -m venv .venv && .venv\Scripts\activate   # Windows
pip install -r requirements.txt
# đặt ảnh vào data/input/ rồi:
python src/pipeline_7_steps.py
```

---

## Sự cố thường gặp

- **Web/mobile báo lỗi kết nối:** kiểm tra OCR server đã chạy chưa (`curl http://localhost:8000/health`) và `VITE_API_BASE` / địa chỉ trong app có đúng không.
- **Mobile không gọi được server:** dùng IP LAN của máy tính thay cho `localhost`, và đảm bảo cùng mạng Wi-Fi; tắt firewall chặn cổng 8000 nếu cần.
- **Lần đầu chạy server rất lâu:** PaddleOCR đang tải model, là bình thường; cần kết nối mạng.
