FROM python:3.11-slim

WORKDIR /app


ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    DISPLAY_GUI=false

# Install system dependencies for OpenCV

RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libgomp1 && rm -rf /var/lib/apt/lists/*

# Copy dependency definitions first for Docker layer caching

COPY ai/requirements.txt /app/ai/requirements.txt

# Install CPU-only PyTorch (avoids CUDA libraries)


# Install CPU-only PyTorch with longer timeouts and retries
RUN pip install \
    --no-cache-dir \
    --default-timeout=300 \
    --retries=10 \
    --index-url https://download.pytorch.org/whl/cu121 \
    torch==2.4.1 torchvision==0.19.1

# Install remaining AI dependencies

RUN pip install \
    --no-cache-dir \
    --default-timeout=300 \
    --retries=10 \
    -r /app/ai/requirements.txt
# Copy AI application and YOLO weights into WORKDIR (/app)

COPY yolov8n.pt /app/yolov8n.pt
COPY ai /app/ai

CMD ["python", "-m", "ai.pipeline"]
