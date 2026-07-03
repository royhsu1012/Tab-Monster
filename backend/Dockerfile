FROM python:3.11-slim

# ffmpeg 是 yt-dlp / ffmpeg-python 的必要系統依賴，librosa 需要 libsndfile
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV UPLOAD_DIR=/tmp/tabmonster/uploads
RUN mkdir -p /tmp/tabmonster/uploads

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
