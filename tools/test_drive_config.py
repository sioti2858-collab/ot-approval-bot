"""
Uji konfigurasi Google Drive: oauth vs service_account, dan guard
"upload enabled tapi kredensial belum siap".

Uji ini murni terhadap config.py - tidak memanggil Google API.
"""
import importlib
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Fixture kredensial service account. Dipakai supaya hasil uji tidak
# bergantung pada credentials.json lokal (yang di-gitignore, jadi tidak
# ada di CI).
_TMP_DIR = tempfile.mkdtemp(prefix="uji-sa-")
_FAKE_SA_JSON = os.path.join(_TMP_DIR, "sa-valid.json")
with open(_FAKE_SA_JSON, "w", encoding="utf-8") as _handle:
    json.dump(
        {
            "type": "service_account",
            "project_id": "uji",
            "client_email": "uji@uji.iam.gserviceaccount.com",
            "private_key": "-----BEGIN PRIVATE KEY-----\nuji\n-----END PRIVATE KEY-----\n",
        },
        _handle,
    )

_MISSING_SA_JSON = os.path.join(_TMP_DIR, "tidak-ada.json")

_BROKEN_SA_JSON = os.path.join(_TMP_DIR, "rusak.json")
with open(_BROKEN_SA_JSON, "w", encoding="utf-8") as _handle:
    _handle.write("{bukan json")

FAILED = []


def check(label: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"  OK   {label}")
    else:
        print(f"  GAGAL {label} {detail}")
        FAILED.append(label)


def reload_config(env: dict):
    """Reload config.py dengan environment tertentu."""
    for key, value in env.items():
        os.environ[key] = value
    import config

    return importlib.reload(config)


def clear_drive_env() -> None:
    for key in (
        "DRIVE_UPLOAD_ENABLED",
        "DRIVE_AUTH_MODE",
        "GOOGLE_OAUTH_CLIENT_ID",
        "GOOGLE_OAUTH_CLIENT_SECRET",
        "GOOGLE_OAUTH_REFRESH_TOKEN",
        "GOOGLE_SERVICE_ACCOUNT_JSON",
    ):
        os.environ.pop(key, None)


print("== Upload nonaktif (default) ==")
clear_drive_env()
config = reload_config({})
check("upload mati secara default", config.DRIVE_UPLOAD_ENABLED is False)
check("mode auth default oauth", config.DRIVE_AUTH_MODE == "oauth")
check("oauth belum siap", config.OAUTH_READY is False)
check("upload mati walau flag true tanpa kredensial",
      reload_config({"DRIVE_UPLOAD_ENABLED": "true"}).DRIVE_UPLOAD_ENABLED is False)

print("\n== Kredensial OAuth lengkap ==")
clear_drive_env()
config = reload_config({
    "DRIVE_UPLOAD_ENABLED": "true",
    "DRIVE_AUTH_MODE": "oauth",
    "GOOGLE_OAUTH_CLIENT_ID": "id-uji",
    "GOOGLE_OAUTH_CLIENT_SECRET": "secret-uji",
    "GOOGLE_OAUTH_REFRESH_TOKEN": "refresh-uji",
})
check("oauth siap", config.OAUTH_READY is True)
check("upload aktif", config.DRIVE_UPLOAD_ENABLED is True)
check("auth siap", config.DRIVE_AUTH_READY is True)

print("\n== Kredensial OAuth belum lengkap ==")
clear_drive_env()
config = reload_config({
    "DRIVE_UPLOAD_ENABLED": "true",
    "GOOGLE_OAUTH_CLIENT_ID": "id-uji",
})
check("oauth belum siap", config.OAUTH_READY is False)
check("upload dimatikan otomatis", config.DRIVE_UPLOAD_ENABLED is False)

print("\n== Mode service_account ==")
clear_drive_env()
config = reload_config({
    "DRIVE_UPLOAD_ENABLED": "true",
    "DRIVE_AUTH_MODE": "service_account",
    # Path ke file yang benar-benar ada, supaya tidak bergantung pada
    # credentials.json lokal (yang tidak ada di CI).
    "GOOGLE_SERVICE_ACCOUNT_JSON": str(_FAKE_SA_JSON),
})
check("auth siap dengan SA", config.DRIVE_AUTH_READY is True)
check("upload tetap aktif", config.DRIVE_UPLOAD_ENABLED is True)

clear_drive_env()
config = reload_config({
    "DRIVE_UPLOAD_ENABLED": "true",
    "DRIVE_AUTH_MODE": "service_account",
    "GOOGLE_SERVICE_ACCOUNT_JSON": str(_MISSING_SA_JSON),
})
check("file SA tidak ada -> auth belum siap", config.DRIVE_AUTH_READY is False)
check("upload dimatikan otomatis", config.DRIVE_UPLOAD_ENABLED is False)

clear_drive_env()
config = reload_config({
    "DRIVE_UPLOAD_ENABLED": "true",
    "DRIVE_AUTH_MODE": "service_account",
    "GOOGLE_SERVICE_ACCOUNT_JSON": str(_BROKEN_SA_JSON),
})
check("JSON SA rusak -> auth belum siap", config.DRIVE_AUTH_READY is False)
check("upload dimatikan otomatis", config.DRIVE_UPLOAD_ENABLED is False)

print("\n== DriveService memakai kredensial yang benar ==")
clear_drive_env()
os.environ.update({
    "DRIVE_UPLOAD_ENABLED": "true",
    "DRIVE_AUTH_MODE": "oauth",
    "GOOGLE_OAUTH_CLIENT_ID": "id-uji",
    "GOOGLE_OAUTH_CLIENT_SECRET": "secret-uji",
    "GOOGLE_OAUTH_REFRESH_TOKEN": "refresh-uji",
})
import config as cfg  # noqa: E402

importlib.reload(cfg)
import services.drive as drive_mod  # noqa: E402

importlib.reload(drive_mod)
check("drive.py import dengan mode oauth",
      drive_mod.DRIVE_AUTH_MODE == "oauth")

# Pastikan get_user_credentials menolak kalau ada yang kurang.
clear_drive_env()
os.environ["DRIVE_AUTH_MODE"] = "oauth"
os.environ["GOOGLE_OAUTH_CLIENT_ID"] = "id-uji"
importlib.reload(cfg)
import services.google_creds as creds_mod  # noqa: E402

importlib.reload(creds_mod)
try:
    creds_mod.get_user_credentials(["scope"])
    check("kredensial kurang harus ditolak", False, "tidak ada error")
except ValueError as error:
    check("kredensial kurang harus ditolak", True)
    check("pesan menyebut nama variabel", "GOOGLE_OAUTH_CLIENT_SECRET" in str(error))

clear_drive_env()
importlib.reload(cfg)

print()
if FAILED:
    print(f"ADA {len(FAILED)} UJI GAGAL:")
    for name in FAILED:
        print(f"  - {name}")
    sys.exit(1)

print("SEMUA UJI KONFIGURASI DRIVE LULUS")
