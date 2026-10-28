# ==========================================================
#  OT Approval Bot - image container untuk Railway / Docker
#
#  Build : docker build -t ot-approval-bot .
#  Run   : docker run --env-file .env -v "$(pwd)/pdfs:/app/pdfs" ot-approval-bot
#
#  Catatan: bot ini memakai LONG POLLING Telegram, jadi container
#  TIDAK butuh port HTTP yang di-expose. Cukup satu replica.
# ==========================================================

FROM python:3.11-slim

# Tidak perlu compiler: semua dependency di requirements.txt punya wheel
# siap pakai untuk amd64/arm64.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TZ=Asia/Jakarta

WORKDIR /app

# Layer dependency dulu supaya cache Docker tetap efektif saat cuma
# kode yang berubah.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Folder yang perlu writable: arsip PDF dan log harian.
RUN mkdir -p pdfs logs local_assets \
    && useradd --create-home --uid 1000 bot \
    && chown -R bot:bot /app

USER bot

# Railway/Docker: proses utama. Kalau proses ini berhenti, platform
# yang meng-restart (lihat railway.json).
CMD ["python", "main.py"]
