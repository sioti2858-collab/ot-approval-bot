"""
Setup Sheet Columns
Tambahkan header kolom baru di Google Sheet "OT Request Database".

Kolom baru:
  N = Tanggal Selesai Overday
  O = PDF URL

Skrip ini hanya menulis ke sel N1 dan O1 (baris header). Data di bawahnya
tidak disentuh. Aman diulang berkali-kali: sel yang sudah benar dilewati.

Usage:
  python tools/setup_sheet_columns.py
  python tools/setup_sheet_columns.py --check   # hanya cek, tidak menulis
"""

import sys
from pathlib import Path

# Console Windows default-nya cp1252, jadi karakter emoji tidak bisa dicetak.
# Paksa UTF-8 supaya output di terminal apa pun aman.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# pastikan import modul project bisa jalan dari folder tools/
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

from services.sheets import SheetsService, _col_letter  # noqa: E402


NEW_COLUMNS = [
    (14, "Tanggal Selesai Overday"),
    (15, "PDF URL"),
]


def main(check_only: bool = False):
    service = SheetsService()
    sheet = service._get_sheet()

    print(f"Spreadsheet: {service._sheet.title}")
    print(f"Jumlah kolom saat ini: {sheet.row_values(1).__len__()}")
    print()

    header = sheet.row_values(1)

    for col_idx, label in NEW_COLUMNS:
        letter = _col_letter(col_idx)
        current = header[col_idx - 1].strip() if len(header) >= col_idx else ""

        if current == label:
            print(f"  {letter}1 sudah benar: {label!r} - dilewati")
            continue

        if current:
            print(f"  {letter}1 berisi {current!r} (bukan {label!r}) - TIDAK ditulis")
            continue

        if check_only:
            print(f"  {letter}1 kosong - perlu diisi {label!r}")
            continue

        sheet.update_cell(1, col_idx, label)
        print(f"  {letter}1 ditulis: {label!r}")

    print()

    # Verifikasi ulang
    header = sheet.row_values(1)
    ok = True
    for col_idx, label in NEW_COLUMNS:
        letter = _col_letter(col_idx)
        value = header[col_idx - 1].strip() if len(header) >= col_idx else ""
        status = "OK" if value == label else "GAGAL"
        if value != label:
            ok = False
        print(f"  {letter}1 = {value!r} [{status}]")

    print()
    if ok:
        print("Selesai. Semua kolom baru siap dipakai.")
    else:
        print("Ada kolom yang belum sesuai. Coba jalankan ulang.")
        return 1
    return 0


if __name__ == "__main__":
    check_only = "--check" in sys.argv
    if check_only:
        print("Mode --check: tidak menulis apa pun.\n")
    sys.exit(main(check_only))
