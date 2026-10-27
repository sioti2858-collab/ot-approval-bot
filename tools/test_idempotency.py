"""
Uji idempotensi tombol (double-tap) dan batas tanggal lampau.

Dijalankan: python tools/test_idempotency.py
"""
import sys
from pathlib import Path

# Console Windows default-nya cp1252, jadi karakter emoji tidak bisa dicetak.
# Paksa UTF-8 supaya output di terminal apa pun aman.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from bot.handlers import (  # noqa: E402
    check_approval_still_valid,
    is_duplicate_action,
    validate_date_range,
)
from config import MAX_PAST_DAYS  # noqa: E402
from models.ot_request import OTRequest, RequestStatus  # noqa: E402
from datetime import datetime, timedelta  # noqa: E402


def make_request(status: RequestStatus, request_type: str = "overtime") -> OTRequest:
    return OTRequest(
        row_id=123,
        user_id=999,
        user_name="Budi Santoso",
        department="EIC & IT",
        request_type=request_type,
        ot_date="2026-10-25",
        od_start_date="2026-10-25",
        od_end_date="2026-10-25",
        start_time="08:00",
        end_time="20:00",
        reason="Uji",
        status=status,
    )


def test_duplicate_action():
    print("=" * 70)
    print("UJI IDEMPOTENSI TOMBOL (double-tap)")
    print("=" * 70)

    assert is_duplicate_action(111, "approve_1_123") is False
    assert is_duplicate_action(111, "approve_1_123") is True, "ketukan kedua harus diabaikan"
    print("  ketukan kedua pada tombol yang sama -> diabaikan OK")

    # Tombol lain / user lain tetap diproses
    assert is_duplicate_action(111, "approve_2_123") is False
    assert is_duplicate_action(222, "approve_1_123") is False
    print("  tombol lain & user lain tetap diproses OK")

    # Setelah jendela waktu lewat, aksi boleh diproses lagi
    import bot.handlers as handlers

    key = (111, "approve_1_123")
    handlers._recent_button_actions[key] = (
        datetime.now(handlers.TZ).timestamp() - handlers.BUTTON_DEBOUNCE_SECONDS - 1
    )
    assert is_duplicate_action(111, "approve_1_123") is False
    print("  setelah jendela waktu habis -> boleh diproses lagi OK")


def test_approval_still_valid():
    print("\n" + "=" * 70)
    print("UJI AKSI BASI (tombol lama diketuk lagi)")
    print("=" * 70)

    ok, msg = check_approval_still_valid(make_request(RequestStatus.SUBMITTED), 1)
    assert ok and not msg
    print("  status submitted, level 1 -> valid OK")

    ok, msg = check_approval_still_valid(make_request(RequestStatus.SUBMITTED), 2)
    assert not ok and "Sudah Diproses" in msg
    print("  status submitted, level 2 -> ditolak OK")

    ok, msg = check_approval_still_valid(
        make_request(RequestStatus.PENDING_APPROVAL_1), 1
    )
    assert not ok, "level 1 yang sudah di-approve tidak boleh di-approve lagi"
    print("  level 1 sudah di-approve -> ditolak OK")

    ok, msg = check_approval_still_valid(make_request(RequestStatus.APPROVED), 3)
    assert not ok
    print("  pengajuan sudah approved -> ditolak OK")

    ok, msg = check_approval_still_valid(make_request(RequestStatus.REJECTED), 1)
    assert not ok
    print("  pengajuan ditolak -> ditolak OK")

    # Overday: hanya 2 level
    ok, msg = check_approval_still_valid(
        make_request(RequestStatus.SUBMITTED, "overday"), 2
    )
    assert not ok
    print("  overday tidak punya level 3 -> level 2 ditolak saat status submitted OK")


def test_date_range():
    print("\n" + "=" * 70)
    print(f"UJI BATAS TANGGAL LAMPAU (max {MAX_PAST_DAYS} hari)")
    print("=" * 70)

    assert MAX_PAST_DAYS == 14, MAX_PAST_DAYS

    today = datetime.now().date()
    ok, msg = validate_date_range(today.strftime("%Y-%m-%d"))
    assert ok, msg

    ok, msg = validate_date_range(
        (today - timedelta(days=MAX_PAST_DAYS)).strftime("%Y-%m-%d")
    )
    assert ok, f"tanggal tepat {MAX_PAST_DAYS} hari lalu harus boleh: {msg}"
    print(f"  {MAX_PAST_DAYS} hari lalu -> boleh OK")

    ok, msg = validate_date_range(
        (today - timedelta(days=MAX_PAST_DAYS + 1)).strftime("%Y-%m-%d")
    )
    assert not ok and "terlalu lampau" in msg
    print(f"  {MAX_PAST_DAYS + 1} hari lalu -> ditolak OK")

    print("\nSEMUA UJI IDEMPOTENSI LULUS")


test_duplicate_action()
test_approval_still_valid()
test_date_range()
