"""
Pembacaan kredensial service account Google, di satu tempat.

Kenapa modul ini ada:

  Nilai `GOOGLE_SERVICE_ACCOUNT_JSON` bisa berupa:
    - path file JSON (mis. "credentials/service_account.json"), atau
    - isi JSON-nya langsung (dipakai di Railway/container).

  Dua masalah yang pernah kejadian dan membuat bot gagal diam-diam:
    1. Secret kosong -> file cuma berisi newline -> JSONDecodeError
       yang muncul belakangan, saat user menekan tombol, bukan saat start.
    2. BOM / spasi di awal atau akhir -> JSON tidak terbaca.

  Modul ini menormalkan keduanya dan.error-nya jelas, jadi bisa
  ditampilkan ke user atau ke log dengan jelas.

Semua service (sheets, drive, state_store) memakai helper ini supaya
perilakunya konsisten.
"""
import json
import os

from google.oauth2 import service_account

import config

# Pesan error yang enak dibacauser
ERR_EMPTY = (
    "GOOGLE_SERVICE_ACCOUNT_JSON kosong. Isi secret ini di "
    "Settings > Secrets and variables > Actions (isi penuh isi file "
    "credentials.json dalam satu baris)."
)
ERR_INVALID = (
    "Isi GOOGLE_SERVICE_ACCOUNT_JSON bukan JSON yang valid. "
    "Salin ulang isi penuh file credentials.json (tanpa karakter lain)."
)


def _read_raw() -> str:
    """Ambil isi mentah dari env var: path file atau JSON langsung."""
    # Dibaca dari config saat dipanggil, bukan saat modul diimpor, supaya
    # nilai terbaru selalu terpakai.
    raw = config.GOOGLE_SERVICE_ACCOUNT_JSON or ""
    stripped = raw.strip()

    # Path file?
    if stripped.endswith(".json"):
        path = stripped
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"File kredensial tidak ditemukan: {path}. "
                "Pastikan langkah 'Siapkan kredensial Google' di workflow sudah jalan."
            )
        # utf-8-sig: buang BOM kalau ada
        with open(path, "r", encoding="utf-8-sig") as handle:
            return handle.read()

    # JSON langsung
    return raw


def load_service_account_info() -> dict:
    """Parse JSON service account, dengan pesan error yang jelas."""
    raw = _read_raw()

    # Buang BOM + whitespace di tepi
    cleaned = raw.lstrip("\ufeff").strip()

    if not cleaned:
        raise ValueError(ERR_EMPTY)

    try:
        info = json.loads(cleaned)
    except json.JSONDecodeError as error:
        raise ValueError(f"{ERR_INVALID} (detail: {error})") from error

    if not isinstance(info, dict) or "client_email" not in info:
        raise ValueError(
            "Isi GOOGLE_SERVICE_ACCOUNT_JSON bukan service account JSON yang valid "
            "(field 'client_email' tidak ada)."
        )

    return info


def get_credentials(scopes):
    """Kredensial service account untuk scope yang diminta."""
    info = load_service_account_info()
    return service_account.Credentials.from_service_account_info(info, scopes=scopes)


def service_account_usable() -> bool:
    """
    True kalau kredensial service account benar-benar bisa dipakai.

    Hanya memeriksa string env var tidak cukup: nilainya bisa menunjuk file
    yang tidak ada, atau JSON yang rusak. Dipakai config.py untuk deciding
    apakah upload Drive boleh dinyalakan.
    """
    try:
        load_service_account_info()
    except (ValueError, FileNotFoundError, OSError):
        return False
    return True


def get_user_credentials(scopes):
    """
    Kredensial OAuth milik user (bukan service account).

    Dipakai untuk Google Drive. Service account tidak punya storage quota
    (storageQuota.limit = 0), jadi upload PDF selalu ditolak 403 "Service
    Accounts do not have storage quota". Dengan OAuth, file dibuat atas nama
    user sehingga kuotanya mengikuti kuota akun user.

    Yang disimpan hanya refresh token; access token diambil ulang otomatis
    oleh google-auth saat kedaluwarsa. Jadi script setup cukup dijalankan
    sekali.
    """
    from google.oauth2.credentials import Credentials as UserCredentials

    missing = []
    if not config.GOOGLE_OAUTH_CLIENT_ID:
        missing.append("GOOGLE_OAUTH_CLIENT_ID")
    if not config.GOOGLE_OAUTH_CLIENT_SECRET:
        missing.append("GOOGLE_OAUTH_CLIENT_SECRET")
    if not config.GOOGLE_OAUTH_REFRESH_TOKEN:
        missing.append("GOOGLE_OAUTH_REFRESH_TOKEN")

    if missing:
        raise ValueError(
            "Kredensial OAuth Google Drive belum lengkap: "
            + ", ".join(missing)
            + ". Jalankan tools/setup_drive_oauth.py untuk mendapatkannya."
        )

    return UserCredentials(
        token=None,
        refresh_token=config.GOOGLE_OAUTH_REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=config.GOOGLE_OAUTH_CLIENT_ID,
        client_secret=config.GOOGLE_OAUTH_CLIENT_SECRET,
        scopes=list(scopes),
    )


def validate_credentials() -> None:
    """Cek kredensial bisa dibaca. Melempar ValueError dengan pesan jelas.

    Dipakai main.py saat start supaya masalah kredensial ketahuan dari awal,
    bukan baru saat user menekan tombol.
    """
    load_service_account_info()
