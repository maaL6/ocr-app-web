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
COPY ocr-server/alembic.ini ./alembic.ini
COPY ocr-server/migrations/ ./migrations/

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
