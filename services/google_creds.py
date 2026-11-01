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

from config import GOOGLE_SERVICE_ACCOUNT_JSON

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
    raw = GOOGLE_SERVICE_ACCOUNT_JSON or ""
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


def validate_credentials() -> None:
    """Cek kredensial bisa dibaca. Melempar ValueError dengan pesan jelas.

    Dipakai main.py saat start supaya masalah kredensial ketahuan dari awal,
    bukan baru saat user menekan tombol.
    """
    load_service_account_info()
