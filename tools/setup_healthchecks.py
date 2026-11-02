"""
Buat check Healthchecks.io + isi secret GitHub HC_PING_UUID.

Pakai:
    python tools/setup_healthchecks.py --api-token <TOKEN_HC>

Alur:
    1. Ambil API access key dari https://healthchecks.io/api/
    2. Skrip ini membuat check "OT Bot - GitHub Actions watchdog" dengan
       jadwal cron */5 dan grace period 30 menit.
    3. UUID check dibaca dari respons, lalu disimpan sebagai repository
       secret "HC_PING_UUID" (dienkripsi oleh GitHub).
    4. Di akhir, skrip mengirim satu heartbeat uji ke ping URL, sehingga
       Anda bisa langsung melihat check-nya hidup di dashboard Healthchecks.

Nilai token hanya dipakai di memori dan tidak pernah dicetak.
"""
import argparse
import base64
import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GITHUB_REPO = "sioti2858-collab/ot-approval-bot"
HC_API = "https://healthchecks.io/api/v3"
CHECK_NAME = "OT Bot - GitHub Actions watchdog"
CRON = "*/5 * * * *"
GRACE_SECONDS = 1800  # 30 menit


def _github_pat() -> str:
    """Ambil PAT dari credential manager GitHub (dipakai untuk push)."""
    result = subprocess.run(
        ["git", "credential", "fill"],
        input="protocol=https\nhost=github.com\n\n",
        capture_output=True,
        text=True,
    )
    for line in result.stdout.splitlines():
        if line.startswith("password="):
            return line.split("=", 1)[1].strip()
    return ""


def _github_api(path: str, method: str = "GET", body: dict | None = None, token: str = ""):
    url = f"https://api.github.com/repos/{GITHUB_REPO}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req) as resp:
        raw = resp.read()
        return resp.status if resp.status == 204 else json.loads(raw or b"{}")


def create_check(api_token: str) -> dict:
    body = {
        "name": CHECK_NAME,
        "schedule": CRON,
        "grace": GRACE_SECONDS,
        "tz": "UTC",
        "channels": "",
    }
    req = urllib.request.Request(
        f"{HC_API}/checks/",
        data=json.dumps(body).encode(),
        method="POST",
        headers={
            "X-Api-Key": api_token,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def list_checks(api_token: str) -> list:
    req = urllib.request.Request(
        f"{HC_API}/checks/",
        headers={"X-Api-Key": api_token, "Accept": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read()).get("checks", [])


def set_secret(github_token: str, secret_name: str, secret_value: str) -> None:
    key = _github_api("/actions/secrets/public-key", token=github_token)
    try:
        from nacl import encoding, public

        pubkey = public.PublicKey(key["key"].encode(), encoding.Base64Encoder())
        encrypted = base64.b64encode(public.SealedBox(pubkey).encrypt(secret_value.encode())).decode()
    except ImportError:
        raise SystemExit("pynacl belum terpasang. Jalankan: pip install pynacl")
    _github_api(
        f"/actions/secrets/{secret_name}",
        method="PUT",
        body={"encrypted_value": encrypted, "key_id": key["key_id"]},
        token=github_token,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-token", required=True, help="API access key Healthchecks.io")
    parser.add_argument("--secret-name", default="HC_PING_UUID")
    parser.add_argument("--dry-run", action="store_true", help="Hanya cek, jangan buat/ubah apa pun")
    args = parser.parse_args()

    print("Mencari check yang sudah ada...")
    try:
        existing = list_checks(args.api_token)
    except urllib.error.HTTPError as error:
        print(f"Gagal menghubungi Healthchecks.io: HTTP {error.code}", file=sys.stderr)
        print("Periksa API access key Anda di https://healthchecks.io/api/", file=sys.stderr)
        return 1

    match = [c for c in existing if c.get("name") == CHECK_NAME]
    if match:
        check = match[0]
        print(f"Check sudah ada: {check.get('name')} (uuid {check.get('uuid')})")
    else:
        if args.dry_run:
            print("Check belum ada. Jalankan tanpa --dry-run untuk membuatnya.")
            return 0
        check = create_check(args.api_token)
        print(f"Check dibuat: {check.get('name')} (uuid {check.get('uuid')})")

    uuid = check.get("uuid")
    ping_url = check.get("ping_url") or f"https://hc-ping.com/{uuid}"
    print(f"Ping URL: {ping_url}")

    if args.dry_run:
        print("Mode dry-run: secret tidak diubah.")
        return 0

    github_token = _github_pat()
    if not github_token:
        print("PAT GitHub tidak ditemukan di credential manager.", file=sys.stderr)
        return 1
    set_secret(github_token, args.secret_name, uuid)
    print(f"Secret GitHub '{args.secret_name}' tersimpan.")

    # Heartbeat uji supaya dashboard langsung menunjukkan check hidup.
    try:
        with urllib.request.urlopen(ping_url, timeout=15) as resp:
            print(f"Heartbeat uji: HTTP {resp.status}")
    except urllib.error.HTTPError as error:
        print(f"Heartbeat uji: HTTP {error.code}", file=sys.stderr)

    print("\nSelesai. Now:")
    print(f"  1. Buka {ping_url.replace(uuid, '<uuid>')} -> dashboard Healthchecks.io")
    print("  2. Pastikan bot.yml (workflow) sudah berjalan normal")
    return 0


if __name__ == "__main__":
    sys.exit(main())
