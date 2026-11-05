"""
Siapkan OAuth Google Drive untuk bot OT Approval + isi secret GitHub.

Kenapa perlu OAuth, bukan service account?
    Service account tidak punya storage quota (about().get() membalas
    storageQuota.limit = "0"), jadi upload PDF ke My Drive ditolak dengan
    403 "Service Accounts do not have storage quota". Dengan OAuth milik
    user, file dibuat atas nama user, jadi kuotanya mengikuti kuota akun
    user - tanpa perlu Google Workspace atau Shared Drive.

PERSIAPAN (sekali saja, di Google Cloud Console):
    1. Buka project yang sama dengan yang dipakai bot (ot-approval-bot)
    2. APIs & Services > OAuth consent screen
         - tipe: External
         - App name / user support email / developer email: isi email Anda
         - tambahkan email Anda sebagai Test user
    3. APIs & Services > Credentials > Create Credentials > OAuth client ID
         - Application type: Desktop app  (WAJIB Desktop app)
         - Name: bebas, mis. "ot-approval-bot-local"
    4. Unduh file JSON-nya (client_secret_*.json)

Pakai:
    python tools/setup_drive_oauth.py path/ke/client_secret_*.json

Alur:
    1. Browser terbuka; Anda login sebagai akun pemilik folder Drive tujuan
       (pemilik GOOGLE_DRIVE_FOLDER_ID) dan menyetujui izin.
    2. Ketiga nilai (client id, client secret, refresh token) disimpan
       sebagai GitHub secret:
           GOOGLE_OAUTH_CLIENT_ID
           GOOGLE_OAUTH_CLIENT_SECRET
           GOOGLE_OAUTH_REFRESH_TOKEN
       dan repository variable:
           DRIVE_UPLOAD_ENABLED = true
    3. Folder tujuan diperiksa: boleh upload oleh akun ini atau tidak.

Nilai kredensial hanya dipakai di memori, tidak pernah dicetak ke terminal
maupun ditulis ke file.
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

# Scope yang dipakai bot. Sama dengan services/drive.py.
SCOPES = ["https://www.googleapis.com/auth/drive"]

SECRET_CLIENT_ID = "GOOGLE_OAUTH_CLIENT_ID"
SECRET_CLIENT_SECRET = "GOOGLE_OAUTH_CLIENT_SECRET"
SECRET_REFRESH_TOKEN = "GOOGLE_OAUTH_REFRESH_TOKEN"
VAR_UPLOAD_ENABLED = "DRIVE_UPLOAD_ENABLED"
VAR_SHARE_MODE = "DRIVE_SHARE_MODE"


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


def set_secret(github_token: str, secret_name: str, secret_value: str) -> None:
    """Simpan repository secret (dienkripsi oleh GitHub)."""
    key = _github_api("/actions/secrets/public-key", token=github_token)
    try:
        from nacl import encoding, public

        pubkey = public.PublicKey(key["key"].encode(), encoding.Base64Encoder())
        encrypted = base64.b64encode(
            public.SealedBox(pubkey).encrypt(secret_value.encode())
        ).decode()
    except ImportError:
        raise SystemExit("pynacl belum terpasang. Jalankan: pip install pynacl")
    _github_api(
        f"/actions/secrets/{secret_name}",
        method="PUT",
        body={"encrypted_value": encrypted, "key_id": key["key_id"]},
        token=github_token,
    )


def set_variable(github_token: str, name: str, value: str) -> None:
    """Buat atau perbarui repository variable."""
    try:
        _github_api(
            f"/actions/variables/{name}",
            method="PATCH",
            body={"name": name, "value": value},
            token=github_token,
        )
        return
    except urllib.error.HTTPError as error:
        if error.code != 404:
            raise
    _github_api(
        "/actions/variables",
        method="POST",
        body={"name": name, "value": value},
        token=github_token,
    )


def load_client_info(path) -> dict:
    """Baca client_secret_*.json yang diunduh dari Google Cloud Console."""
    path = Path(path)
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    # File dari Console: {"installed": {...}} untuk tipe Desktop app.
    for key in ("installed", "web"):
        if key in data:
            return data[key]
    raise SystemExit(
        "Format file tidak dikenali. Pastikan file client_secret_*.json "
        "dari OAuth client bertipe 'Desktop app'."
    )


def check_upload_access(refresh_token: str, client_id: str, client_secret: str,
                        folder_id: str) -> tuple[bool, str]:
    """
    Cek apakah akun OAuth boleh upload ke folder tujuan.

    Mengembalikan (boleh, pesan).
    """
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseUpload
    import io

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=list(SCOPES),
    )
    drive = build("drive", "v3", credentials=creds)

    if not folder_id:
        return False, "GOOGLE_DRIVE_FOLDER_ID kosong - diisi dulu di .env."

    # Cek folder bisa diakses & nama pemiliknya.
    try:
        folder = (
            drive.files()
            .get(fileId=folder_id, fields="id, name, driveId, owners", supportsAllDrives=True)
            .execute()
        )
    except Exception as error:  # noqa: BLE001 - pesan untuk operator
        return False, f"Folder tujuan tidak bisa diakses: {error}"

    owners = [o.get("emailAddress", "?") for o in folder.get("owners", [])]
    where = "Shared Drive" if folder.get("driveId") else "My Drive"

    # Uji tulis sungguhan: file kecil, lalu langsung dihapus.
    probe_name = ".__setup_probe.txt"
    try:
        probe = (
            drive.files()
            .create(
                body={"name": probe_name, "mimeType": "text/plain", "parents": [folder_id]},
                media_body=MediaIoBaseUpload(io.BytesIO(b"probe"), mimetype="text/plain"),
                fields="id",
                supportsAllDrives=True,
            )
            .execute()
        )
    except Exception as error:  # noqa: BLE001
        return False, f"Tidak boleh upload ke folder '{folder.get('name')}': {error}"

    try:
        drive.files().delete(fileId=probe["id"], supportsAllDrives=True).execute()
    except Exception:  # noqa: BLE001 - probe yang tertinggal tidak fatal
        pass

    return True, (
        f"Upload ke '{folder.get('name')}' ({where}) berhasil. "
        f"Pemilik: {', '.join(owners)}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Setup OAuth Drive + secret GitHub")
    parser.add_argument(
        "client_secret_json",
        help="Path ke client_secret_*.json hasil download dari Google Cloud Console",
    )
    parser.add_argument(
        "--folder-id",
        default="",
        help="ID folder Drive tujuan (default: ambil dari GOOGLE_DRIVE_FOLDER_ID di .env)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Hanya cek akses folder; jangan sentuh secret/variable GitHub",
    )
    args = parser.parse_args()

    path = Path(args.client_secret_json)
    if not path.exists():
        print(f"File tidak ditemukan: {path}", file=sys.stderr)
        return 1

    client_info = load_client_info(path)
    client_id = client_info.get("client_id", "")
    client_secret = client_info.get("client_secret", "")
    if not client_id or not client_secret:
        print("client_id / client_secret tidak terbaca dari file.", file=sys.stderr)
        return 1

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("Paket google-auth-oauthlib belum terpasang.", file=sys.stderr)
        print("Jalankan: pip install google-auth-oauthlib", file=sys.stderr)
        return 1

    folder_id = args.folder_id
    if not folder_id:
        # Ambil dari .env tanpa membocorkan nilai lain.
        env_file = PROJECT_ROOT / ".env"
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("GOOGLE_DRIVE_FOLDER_ID="):
                    folder_id = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break

    print("Membuka browser untuk login & persetujuan...")
    print("Login sebagai akun PEMILIK folder Drive tujuan, lalu setujui izin.")
    print()

    flow = InstalledAppFlow.from_client_config(
        client_info, scopes=SCOPES, redirect_uri="http://localhost"
    )
    creds = flow.run_local_server(port=0, prompt="consent")

    if not creds.refresh_token:
        print(
            "\nTidak ada refresh token. Biasanya terjadi kalau izin sudah pernah "
            "diberikan sebelumnya.\nCoba hapus aplikasi ini dari "
            "https://myaccount.google.com/permissions lalu jalankan lagi.",
            file=sys.stderr,
        )
        return 1

    print("Consent berhasil. Memeriksa hak upload ke folder tujuan...")
    ok, message = check_upload_access(
        creds.refresh_token, client_id, client_secret, folder_id
    )
    print(f"  {message}")
    if not ok:
        print(
            "\nUpload ke folder tujuan BELUM bisa. Secret tetap boleh disimpan, "
            "tapi upload akan gagal sampai aksesnya beres.",
            file=sys.stderr,
        )

    if args.dry_run:
        print("\nMode dry-run: secret dan variable GitHub tidak diubah.")
        return 0 if ok else 1

    github_token = _github_pat()
    if not github_token:
        print("PAT GitHub tidak ditemukan di credential manager.", file=sys.stderr)
        return 1

    for name, value in (
        (SECRET_CLIENT_ID, client_id),
        (SECRET_CLIENT_SECRET, client_secret),
        (SECRET_REFRESH_TOKEN, creds.refresh_token),
    ):
        set_secret(github_token, name, value)
        print(f"Secret GitHub '{name}' tersimpan.")

    set_variable(github_token, VAR_UPLOAD_ENABLED, "true")
    print(f"Repository variable '{VAR_UPLOAD_ENABLED}' = true")
    set_variable(github_token, VAR_SHARE_MODE, "restricted")
    print(f"Repository variable '{VAR_SHARE_MODE}' = restricted")

    print("\nSelesai. Bot di cloud akan mengarsipkan PDF ke Drive pada approval berikutnya.")
    print("Secret tidak pernah dicetak, dan tidak ada file kredensial yang ditulis.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
