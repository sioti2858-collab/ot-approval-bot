"""
Configuration for OT Approval Bot

Semua pengaturan dibaca dari environment variables (.env).
Tidak ada nilai default berisi data pribadi/perusahaan - setiap nilai wajib
diisi lewat .env (lihat .env.example) supaya repo ini aman dipakai ulang
oleh orang lain.
"""

import base64
import os

from dotenv import load_dotenv

# Muat .env sekali di sini supaya semua entry point (main.py, monitor.py,
# tools/*.py) membaca konfigurasi yang sama.
load_dotenv()

# Folder tempat file gambar (tanda tangan / logo) yang dikirim lewat
# environment variable ditulis. Folder ini sudah masuk .gitignore.
ASSET_DIR = os.getenv("ASSET_DIR", "local_assets")


def _env_asset(b64_var: str, path_var: str, default_path: str, filename: str) -> str:
    """
    Tentukan path file gambar (tanda tangan / logo).

    Kalau <b64_var> diisi, isinya (PNG dalam base64) ditulis ke file lokal
    lalu path-nya dikembalikan. Ini dipakai saat bot jalan di cloud: file
    PNG tidak boleh ikut di-commit, jadi dikirim lewat environment variable.

    Kalau <b64_var> kosong, path biasa dari <path_var> dipakai.
    """
    encoded = os.getenv(b64_var, "").strip()
    if encoded:
        try:
            os.makedirs(ASSET_DIR, exist_ok=True)
            target = os.path.join(ASSET_DIR, filename)
            if not os.path.exists(target):
                with open(target, "wb") as handle:
                    handle.write(base64.b64decode(encoded))
            return target
        except Exception:
            # Asset gagal ditulis -> pakai path biasa (kalau ada), jangan
            # sampai seluruh bot gagal start.
            pass
    return os.getenv(path_var, default_path)


def _env_int(name: str, default: int = 0) -> int:
    """Baca integer dari env, fallback ke default bila kosong/tidak valid."""
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_id_list(name: str) -> list:
    """Baca daftar ID numerik dari env, dipisah spasi/koma."""
    raw = os.getenv(name, "").replace(",", " ").split()
    return [int(value) for value in raw if value.isdigit()]


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------

# Token bot dari @BotFather. Wajib diisi.
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# ---------------------------------------------------------------------------
# Google Workspace
# ---------------------------------------------------------------------------

# Lokasi file JSON service account (atau isi JSON-nya langsung).
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "credentials.json")

# ID Google Sheet tempat pengajuan disimpan (bagian URL setelah /d/).
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "")

# ID folder Google Drive tujuan upload PDF.
GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")

# ---------------------------------------------------------------------------
# Perusahaan
# ---------------------------------------------------------------------------

# Nama perusahaan, dicetak di header PDF.
COMPANY_NAME = os.getenv("COMPANY_NAME", "PT. Nama Perusahaan")

# Path logo untuk header PDF. Bisa juga diisi lewat LOGO_BASE64 (PNG dalam
# base64) supaya bisa dipakai di cloud tanpa menaruh file PNG di repo.
LOGO_PATH = _env_asset("LOGO_BASE64", "LOGO_PATH", "png/logo.png", "logo.png")

# ---------------------------------------------------------------------------
# Approver & HR
# ---------------------------------------------------------------------------

# Setiap approver punya level sendiri (1 = paling awal).
# name / title / user_id / esign semuanya diambil dari .env.
APPROVERS = {
    "approval_1": {
        "name": os.getenv("APPROVER_1_NAME", "Approver 1"),
        "title": os.getenv("APPROVER_1_TITLE", "Direct Supervisor"),
        "user_id": _env_int("APPROVER_1_USER_ID"),
        "esign": _env_asset(
            "APPROVER_1_ESIGN_BASE64", "APPROVER_1_ESIGN",
            "png/esign_approver_1.png", "esign_approver_1.png",
        ),
    },
    "approval_2": {
        "name": os.getenv("APPROVER_2_NAME", "Approver 2"),
        "title": os.getenv("APPROVER_2_TITLE", "Section Head"),
        "user_id": _env_int("APPROVER_2_USER_ID"),
        "esign": _env_asset(
            "APPROVER_2_ESIGN_BASE64", "APPROVER_2_ESIGN",
            "png/esign_approver_2.png", "esign_approver_2.png",
        ),
    },
    "approval_3": {
        "name": os.getenv("APPROVER_3_NAME", "Approver 3"),
        "title": os.getenv("APPROVER_3_TITLE", "Manager"),
        "user_id": _env_int("APPROVER_3_USER_ID"),
        "esign": _env_asset(
            "APPROVER_3_ESIGN_BASE64", "APPROVER_3_ESIGN",
            "png/esign_approver_3.png", "esign_approver_3.png",
        ),
    },
}

# User ID Telegram HR (penerima notifikasi & dokumen).
HR_USER_ID = _env_int("HR_USER_ID")

# ---------------------------------------------------------------------------
# Validasi pengajuan
# ---------------------------------------------------------------------------

MAX_FUTURE_DAYS = 30  # Maksimal hari ke depan untuk pengajuan OT
MAX_PAST_DAYS = 14    # Pengajuan OT lampiran masih diterima sampai 14 hari ke belakang

# Jeda minimal (detik) sebelum aksi tombol yang sama boleh diproses lagi.
# Mencegah notifikasi/PDF terkirim berkali-kali saat tombol diketuk berulang.
BUTTON_DEBOUNCE_SECONDS = _env_int("BUTTON_DEBOUNCE_SECONDS", 5)

# Jumlah level approval yang dibutuhkan per jenis pengajuan:
#   overtime -> 3 level (Supervisor -> Section Head -> Manager)
#   overday  -> 2 level (Supervisor -> Section Head)
APPROVAL_LEVELS = {
    "overtime": 3,
    "overday": 2,
}

# ---------------------------------------------------------------------------
# Google Drive
# ---------------------------------------------------------------------------

# Mode berbagi file di Google Drive:
#   "link"       -> siapa pun yang punya link bisa Melihat & mengunduh (read only,
#                   tidak bisa mengedit). File tidak bisa ditemukan lewat pencarian.
#   "restricted" -> hanya anggota folder tujuan yang bisa membuka file.
DRIVE_SHARE_MODE = os.getenv("DRIVE_SHARE_MODE", "link").strip().lower()

# Upload PDF ke Google Drive.
#
# CATATAN: service account TIDAK punya storage quota di My Drive, jadi upload ke
# folder biasa akan gagal dengan 403 storageQuotaExceeded. Folder biasa juga
# bukan Shared Drive. Selama upload dinonaktifkan, dokumen dikirim langsung ke
# chat Telegram sebagai file terlampir dan tetap diarsipkan di folder pdfs/.
#
# Aktifkan (nilai true) setelah:
#   1. Shared Drive dibuat,
#   2. service account ditambahkan sebagai member (role: Content Manager),
#   3. folder tujuan dibuat di dalam shared drive tersebut,
#   4. GOOGLE_DRIVE_FOLDER_ID di-point ke folder itu.
DRIVE_UPLOAD_ENABLED = os.getenv("DRIVE_UPLOAD_ENABLED", "false").strip().lower() in (
    "1", "true", "yes", "on",
)

# ---------------------------------------------------------------------------
# Distribusi dokumen
# ---------------------------------------------------------------------------

# Penerima tambahan berkas PDF (selain HR + pemohon).
# Kosongkan (nilai kosong di .env) untuk memakai mode standar: HR + pemohon.
EXTRA_DOCUMENT_RECIPIENT_USER_IDS = _env_id_list("EXTRA_DOCUMENT_RECIPIENT_USER_IDS")

# ---------------------------------------------------------------------------
# Self-approval
# ---------------------------------------------------------------------------

# Apakah approver boleh menyetujui pengajuan yang dia ajukan sendiri?
# Default: BOLEH untuk approver yang terdaftar (level 1/2/3).
#
# Alasan: approver yang juga pemohon akan terjebak kalau pengajuannya sendiri
# tidak bisa ia setujui - tidak ada approver lain di level yang sama. Self-approval
# dicatat atas namanya sendiri di approval history, jadi jejaknya tetap terlihat.
# Set false di .env kalau memang ingin menutup self-approval untuk approver.
ALLOW_APPROVER_SELF_APPROVAL = os.getenv(
    "ALLOW_APPROVER_SELF_APPROVAL", "true"
).strip().lower() in ("1", "true", "yes", "on")

# Self-approval untuk semua orang (hanya untuk pengujian/emergency).
# Default: TIDAK BOLEH.
ALLOW_SELF_APPROVAL = os.getenv("ALLOW_SELF_APPROVAL", "false").strip().lower() in (
    "1", "true", "yes", "on",
)
