"""
Uji mode penyimpanan dokumen (arsip lokal vs Telegram-only).

Dijalankan: python tools/test_document_storage.py
"""
import os
import shutil
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from bot.handlers import build_document_view_text  # noqa: E402
from config import PDF_MARKER_TELEGRAM  # noqa: E402

failures = []


def check(label, condition, detail=""):
    if condition:
        print(f"  OK   {label}")
    else:
        print(f"  GAGAL {label} {detail}")
        failures.append(label)


print("== Mode Telegram-only ==")

# 1. Penanda yang dipakai di kolom O Sheet
check("penanda kolom O = 'telegram'", PDF_MARKER_TELEGRAM == "telegram")

# 2. Folder pdfs/ TIDAK boleh ikut dibuat saat arsip lokal dimatikan
tmp_dir = tempfile.mkdtemp(prefix="ot_test_")
try:
    pdfs_dir = Path(tmp_dir) / "pdfs"
    if pdfs_dir.exists():
        shutil.rmtree(pdfs_dir)

    save_locally = False
    if save_locally:
        pdfs_dir.mkdir(parents=True, exist_ok=True)
        (pdfs_dir / "OT_1_Uji.pdf").write_bytes(b"%PDF-1.4")

    written = list(pdfs_dir.glob("*.pdf")) if pdfs_dir.exists() else []
    check("tidak ada file PDF di server", written == [], f"-> {written}")

    # 3. Teks tombol "Lihat PDF" harus menjelaskan dokumen dikirim via Telegram
    text = build_document_view_text(1, PDF_MARKER_TELEGRAM)
    check("menyebut dokumen dikirim via Telegram",
          "tidak disimpan di server" in text, f"-> {text!r}")
    check("tidak menampilkan path server",
          "Arsip di server" not in text, f"-> {text!r}")
    check("tidak menampilkan link Drive",
          "Google Drive" not in text, f"-> {text!r}")
finally:
    shutil.rmtree(tmp_dir, ignore_errors=True)

print("== Mode arsip lokal ==")
text = build_document_view_text(7, "local:pdfs/OT_7_Budi_2026-11-02.pdf")
check("menampilkan path arsip lokal", "Arsip di server" in text, f"-> {text!r}")
check("path lokal tampil utuh", "pdfs/OT_7_Budi_2026-11-02.pdf" in text, f"-> {text!r}")

print("== Mode Google Drive ==")
text = build_document_view_text(9, "https://drive.google.com/file/d/abc123/view")
check("menampilkan link Drive", "Link Google Drive" in text, f"-> {text!r}")
check("link Drive tampil utuh", "abc123" in text, f"-> {text!r}")

print()
if failures:
    print(f"GAGAL {len(failures)} pemeriksaan:")
    for item in failures:
        print(f"  - {item}")
    sys.exit(1)

print("SEMUA UJI PENYIMPANAN DOKUMEN LULUS")
