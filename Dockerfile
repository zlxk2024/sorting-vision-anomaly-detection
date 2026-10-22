FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 YOLO_CONFIG_DIR=/tmp/sorting-yolo MPLCONFIGDIR=/tmp/sorting-matplotlib YOLO_AUTOINSTALL=false
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt pyproject.toml ./
RUN python -m pip install --no-cache-dir torch==2.8.0 torchvision==0.23.0 --index-url https://download.pytorch.org/whl/cpu && python -m pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p /tmp/sorting-yolo /tmp/sorting-matplotlib && python scripts/verify_project.py
EXPOSE 8080
CMD ["python", "-m", "sorting_vision.api", "--host", "0.0.0.0", "--port", "8080", "--data-dir", "/work/jobs"]
