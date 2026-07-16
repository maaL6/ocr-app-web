# Hướng dẫn Triển khai và Deploy lại hệ thống OCR Mộc Bản

Tài liệu này hướng dẫn chi tiết cách triển khai (deploy) và cập nhật lại cả hai thành phần **OCR Server (Backend)** và **OCR Web Frontend** lên máy chủ (VPS/Server).

---

## 1. Kiến trúc hệ thống khi Deploy

Hệ thống bao gồm các thành phần:
1. **Database**: PostgreSQL 16 lưu trữ thông tin người dùng và lịch sử quét tài liệu.
2. **Backend**: FastAPI xử lý OCR (PaddleOCR), tiền xử lý ảnh (OpenCV) và các API quản lý tài liệu, auth. Chạy ở cổng `8000`.
3. **Frontend**: Ứng dụng React + Vite được build ra các tệp tĩnh (HTML, JS, CSS) và phục vụ thông qua một Web Server (Nginx) ở cổng `80` (HTTP) hoặc `443` (HTTPS).

---

## 2. Triển khai lại Backend & Database (ocr-server)

Khuyên dùng phương thức chạy bằng **Docker Compose** vì nó tự động đóng gói môi trường Python và model PaddleOCR cùng cơ sở dữ liệu PostgreSQL.

### Bước 2.1: Truy cập thư mục backend trên máy chủ
```bash
cd ocr-server
```

### Bước 2.2: Build và Khởi động Container
Khi có sự thay đổi về mã nguồn backend (ví dụ thêm thư viện mới trong `requirements.txt` hoặc cập nhật code trong `app/`):
```bash
# Build lại image và chạy các container ở chế độ chạy ngầm (-d)
docker compose up -d --build
```
*Lưu ý: Lần chạy đầu tiên sẽ mất khoảng 3-5 phút để tải các thư viện của PaddleOCR và tải model nhận dạng về vùng nhớ đệm (`paddle_models` volume).*

### Bước 2.3: Chạy database migrations (Alembic)
Nếu có sự thay đổi về cấu trúc bảng cơ sở dữ liệu (ví dụ: cập nhật thêm cột `google_id`, `fullname` của người dùng, hoặc cập nhật bảng tài liệu):
```bash
# Thực hiện nâng cấp cơ sở dữ liệu lên phiên bản mới nhất
docker compose exec ocr alembic upgrade head
```

### Bước 2.4: Kiểm tra trạng thái và logs
```bash
# Xem các container đang chạy
docker compose ps

# Xem logs thời gian thực của backend để debug lỗi kết nối hoặc xử lý ảnh
docker compose logs -f ocr
```

---

## 3. Triển khai lại Web Frontend (web)

Frontend chạy dưới dạng các tệp tĩnh sau khi build, do đó bạn cần build nó thành thư mục `dist/` và copy lên server Web.

### Bước 3.1: Truy cập thư mục frontend và cấu hình API
Tạo tệp `.env.production` (nếu chưa có) nằm ở thư mục `web/` để chỉ định địa chỉ API Backend mà client sẽ gọi tới:
```env
# Địa chỉ IP của máy chủ VPS hoặc tên miền trỏ tới Backend
VITE_API_BASE=http://<IP_HOẶC_DOMAIN_SERVER>:8000
```
*(Nếu bạn cấu hình Nginx làm Proxy ngược như phần 4, bạn có thể thiết lập là `VITE_API_BASE=http://<IP_HOẶC_DOMAIN_SERVER>/api` hoặc `/api` nếu chạy chung domain).*

### Bước 3.2: Cài đặt thư viện và build dự án
Chạy lệnh sau trên máy chủ (hoặc máy local rồi copy thư mục `dist/` lên máy chủ):
```bash
cd web
npm install
npm run build
```
Lệnh này sẽ sinh ra thư mục `web/dist/`.

---

## 4. Cấu hình Nginx phục vụ Frontend và Proxy Backend (Mẫu tối ưu)

Dưới đây là tệp cấu hình Nginx mẫu để chạy thực tế trên máy chủ sản xuất (production). Nó sẽ phục vụ trực tiếp các file tĩnh của React và chuyển tiếp các yêu cầu API đến container backend (port 8000) một cách an toàn, tránh lỗi CORS:

Lưu cấu hình này tại `/etc/nginx/sites-available/ocr-app` (trên Linux Ubuntu/Debian):

```nginx
server {
    listen 80;
    server_name ocr.mocban.example.com; # Thay thế bằng tên miền hoặc IP máy chủ của bạn

    # Thư mục chứa mã nguồn frontend đã build
    root /var/www/ocr-app/web/dist;
    index index.html;

    # Cấu hình phục vụ ứng dụng Single Page (React Router)
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Proxy các request API đến Backend FastAPI
    location /auth/ {
        proxy_pass http://127.0.0.1:8000/auth/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /documents/ {
        proxy_pass http://127.0.0.1:8000/documents/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Tăng giới hạn upload file (ảnh mộc bản có độ phân giải cao thường rất nặng)
        client_max_body_size 50M;
    }

    location /preprocess {
        proxy_pass http://127.0.0.1:8000/preprocess;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        client_max_body_size 50M;
    }

    location /ocr {
        proxy_pass http://127.0.0.1:8000/ocr;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        client_max_body_size 50M;
        
        # Tăng thời gian chờ (timeout) cho các tác vụ OCR nặng
        proxy_read_timeout 300s;
        proxy_connect_timeout 300s;
    }

    location /health {
        proxy_pass http://127.0.0.1:8000/health;
        proxy_set_header Host $host;
    }

    location /options {
        proxy_pass http://127.0.0.1:8000/options;
        proxy_set_header Host $host;
    }

    # Bật nén Gzip để tải trang web nhanh hơn
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml;
    gzip_min_length 1000;
}
```

Kích hoạt cấu hình và reload Nginx:
```bash
ln -s /etc/nginx/sites-available/ocr-app /etc/nginx/sites-enabled/
nginx -t # Kiểm tra cú pháp xem có lỗi gì không
systemctl restart nginx
```

---

## 5. Các sự cố thường gặp (Troubleshooting)

1. **Lỗi CORS (Cross-Origin Resource Sharing)**:
   - Hiện tượng: Trình duyệt báo lỗi màu đỏ, không gọi được API dù server backend vẫn sống.
   - Khắc phục: Sử dụng cấu hình Nginx proxy ở trên để chạy frontend và backend cùng chung một cổng/domain. Hoặc kiểm tra xem `allow_origins=["*"]` trong `ocr-server/app/main.py` đã được bật chưa.

2. **Lỗi quyền ghi ảnh tải lên (Permission Denied)**:
   - Hiện tượng: Khi chạy OCR hoặc tiền xử lý, hệ thống báo lỗi không ghi được ảnh vào thư mục `data/uploads`.
   - Khắc phục: Phân quyền lại thư mục lưu trữ ảnh trên VPS:
     ```bash
     chmod -R 777 ocr-server/data/uploads
     ```

3. **Database bị ngắt kết nối đột ngột hoặc không thể Migrate**:
   - Hiện tượng: Container backend thoát (exit) liên tục và báo lỗi `connection refused` khi kết nối Postgres.
   - Khắc phục: Đảm bảo database đã chạy ổn định trước khi chạy migration. Kiểm tra log của Postgres: `docker compose logs postgres`.
