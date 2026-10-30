"""
Helper: salin nilai GitHub secret/variable ke clipboard, satu per satu.

Tujuan: Anda tidak perlu menampilkan atau menyalin nilai sensitif secara
manual. Skrip ini membaca .env / credentials.json / local_assets, lalu
menyalin satu nilai ke clipboard dan menunggu Anda menekan Enter untuk
lanjut ke nilai berikutnya.

Nilai TIDAK PERNAH dicetak ke layar dan TIDAK PERNAH disimpan di luar
clipboard - clipboard otomatis ditimpa oleh nilai berikutnya.

Prasyarat:
  pip install pynacl requests

Pemakaian:
  python tools/copy_github_values.py            # daftar saja (nilai tidak ditampilkan)
  python tools/copy_github_values.py --copy     # mulai menyalin ke clipboard
"""
import argparse
import base64
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Urutan pengisian: secret dulu, lalu variable.
SECRETS = [
    ("TELEGRAM_BOT_TOKEN", "Secret", "Token bot dari @BotFather (atau baris TELEGRAM_BOT_TOKEN di .env)"),
    ("GOOGLE_SERVICE_ACCOUNT_JSON", "Secret", "Isi penuh credentials.json dalam satu baris"),
]

VARIABLES = [
    ("GOOGLE_SHEET_ID", "Variable", "Dari .env"),
    ("GOOGLE_DRIVE_FOLDER_ID", "Variable", "Dari .env (boleh kosong - Drive dimatikan)"),
    ("COMPANY_NAME", "Variable", "Dari .env"),
    ("APPROVER_1_USER_ID", "Variable", "Dari .env"),
    ("APPROVER_1_NAME", "Variable", "Dari .env"),
    ("APPROVER_1_TITLE", "Variable", "Dari .env"),
    ("APPROVER_1_ESIGN_BASE64", "Variable", "Dari local_assets/optimized/esign_*.b64"),
    ("APPROVER_2_USER_ID", "Variable", "Dari .env"),
    ("APPROVER_2_NAME", "Variable", "Dari .env"),
    ("APPROVER_2_TITLE", "Variable", "Dari .env"),
    ("APPROVER_2_ESIGN_BASE64", "Variable", "Dari local_assets/optimized/esign_*.b64"),
    ("APPROVER_3_USER_ID", "Variable", "Dari .env"),
    ("APPROVER_3_NAME", "Variable", "Dari .env"),
    ("APPROVER_3_TITLE", "Variable", "Dari .env"),
    ("APPROVER_3_ESIGN_BASE64", "Variable", "Dari local_assets/optimized/esign_*.b64"),
    ("HR_USER_ID", "Variable", "Dari .env"),
    ("LOGO_BASE64", "Variable", "Dari local_assets/optimized/logo.b64"),
]

SECRETS_URL = "https://github.com/sioti2858-collab/ot-approval-bot/settings/secrets/actions"
VARIABLES_URL = "https://github.com/sioti2858-collab/ot-approval-bot/settings/variables/actions"


def parse_env(path):
    values = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        values[key.strip()] = val.strip().strip('"').strip("'")
    return values


def copy_to_clipboard(text):
    """Salin ke clipboard Windows lewat PowerShell (tanpa menampilkan isi)."""
    if not text:
        return False
    import subprocess

    script = (
        "$t = [Console]::In.ReadToEnd();"
        "Set-Clipboard -Value $t;"
    )
    try:
        subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", script],
            input=text,
            text=True,
            capture_output=True,
            timeout=30,
        )
        return True
    except Exception:
        return False


def collect(env):
    """Kembalikan daftar (nama, jenis, sumber, nilai)."""
    items = []

    for name, kind, hint in SECRETS:
        value = ""
        if name == "TELEGRAM_BOT_TOKEN":
            value = env.get("TELEGRAM_BOT_TOKEN", "")
        else:
            cred = PROJECT_ROOT / "credentials.json"
            if cred.exists():
                raw = cred.read_text(encoding="utf-8").strip()
                try:
                    json.loads(raw)
                    value = raw
                except json.JSONDecodeError:
                    value = ""
        items.append((name, kind, hint, value))

    opt = PROJECT_ROOT / "local_assets" / "optimized"
    esign_map = {
        "APPROVER_1_ESIGN_BASE64": "esign_basuki.b64",
        "APPROVER_2_ESIGN_BASE64": "esign_dede.b64",
        "APPROVER_3_ESIGN_BASE64": "esign_teuku.b64",
    }

    for name, kind, hint in VARIABLES:
        value = ""
        if name in esign_map:
            p = opt / esign_map[name]
            if p.exists():
                value = p.read_text(encoding="utf-8").strip()
        elif name == "LOGO_BASE64":
            p = opt / "logo.b64"
            if p.exists():
                value = p.read_text(encoding="utf-8").strip()
        else:
            value = env.get(name, "")
        items.append((name, kind, hint, value))

    return items


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--copy", action="store_true", help="Mulai menyalin ke clipboard")
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    env = parse_env(PROJECT_ROOT / ".env")
    items = collect(env)

    print("Daftar nilai yang perlu dipasang di GitHub:")
    print(f"  {SECRETS_URL}")
    print(f"  {VARIABLES_URL}")
    print()
    print(f"{'nama':<28}{'jenis':<10}{'status':<14}panjang")
    print("-" * 62)
    for name, kind, hint, value in items:
        status = "ADA" if value else "KOSONG"
        print(f"{name:<28}{kind:<10}{status:<14}{len(value)}")

    kosong = [n for n, _, _, v in items if not v]
    if kosong:
        print()
        print("! Nilai kosong: " + ", ".join(kosong))
        print("  Isi manual di .env atau local_assets/optimized/ lalu ulangi.")

    if not args.copy:
        print()
        print("Jalankan ulang dengan --copy untuk menyalin satu per satu ke clipboard.")
        return 0

    print()
    print("=" * 62)
    print("MODE SALIN. Untuk tiap nilai:")
    print("  1. salin dari clipboard (Ctrl+V) ke kolom GitHub")
    print("  2. tekan Enter di jendela ini untuk lanjut")
    print("=" * 62)

    for name, kind, hint, value in items:
        if not value:
            print(f"\n>>> {name}: TIDAK ADA NILAI - isi manual, lalu tekan Enter")
            try:
                input()
            except EOFError:
                return 0
            continue

        ok = copy_to_clipboard(value)
        if not ok:
            print(f"\n! Gagal menyalin {name}")
            return 1
        print(f"\n>>> {name} ({kind}, {len(value)} karakter) - sudah di clipboard")
        print(f"    sumber: {hint}")
        try:
            input()
        except EOFError:
            return 0

    print("\nSelesai. Semua nilai sudah pernah disalin ke clipboard.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
