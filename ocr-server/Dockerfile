# Build context là THƯ MỤC GỐC repo (xem docker-compose.yml), nên các path
# COPY dưới đây tính từ gốc repo.
FROM python:3.11-slim

# Thư viện hệ thống cần cho OpenCV/Paddle
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /code

COPY ocr-server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ocr-server/app/ ./app/

# Vendor module tiền xử lý woodblock vào trong package app (nguồn duy nhất là
# repo woodblock-preprocessing-pipeline, không copy trùng code thủ công).
COPY woodblock-preprocessing-pipeline/src/modules/ ./app/woodblock_modules/

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
