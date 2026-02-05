# Vigil Edge Video Security — production backend (Flask + YOLO + OpenCV)
# Supports CPU and NVIDIA GPU (set YOLO_DEVICE=0 when using nvidia runtime).
FROM python:3.11-slim

WORKDIR /app

# OpenCV and common deps (minimal for headless)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application
COPY app.py config.json ./
COPY templates/ templates/
COPY proactive/ proactive/
COPY vigil_upgrade/ vigil_upgrade/
COPY config/cameras.example.yaml /app/config/

# Optional: pre-download YOLO weights (comment out to download at first run)
# RUN python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"

EXPOSE 5000

ENV PORT=5000
ENV DATA_DIR=/app/data
ENV RECORDINGS_DIR=/app/recordings
ENV NOTABLE_SCREENSHOTS_DIR=/app/snapshots
ENV CONFIG_DIR=/app/config
RUN mkdir -p /app/data /app/recordings /app/config /app/snapshots
CMD ["python", "app.py"]
