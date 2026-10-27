"""
Uji alur pengajuan OVERDAY (satu tanggal saja) dan aturan self-approval.

Dijalankan: python tools/test_overday_flow.py
"""
import asyncio
import sys
from pathlib import Path

# Console Windows default-nya cp1252, jadi karakter emoji tidak bisa dicetak.
# Paksa UTF-8 supaya output di terminal apa pun aman.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from bot.handlers import handle_overday_input  # noqa: E402
from bot.states import ConversationState, get_conversation_context  # noqa: E402
from models.ot_request import OTRequest, RequestStatus  # noqa: E402
from config import ALLOW_APPROVER_SELF_APPROVAL, APPROVERS  # noqa: E402


class FakeMessage:
    def __init__(self, text):
        self.text = text
        self.replies = []

    async def reply_text(self, text, parse_mode=None, reply_markup=None):
        self.replies.append(text)


class FakeUser:
    def __init__(self, uid):
        self.id = uid


class FakeUpdate:
    def __init__(self, uid, text):
        self.message = FakeMessage(text)
        self.message.from_user = FakeUser(uid)
        self.effective_user = FakeUser(uid)
        self.effective_message = self.message


UID = 515151


async def send(text):
    up = FakeUpdate(UID, text)
    await handle_overday_input(up, None)
    return up.message.replies[-1] if up.message.replies else None


async def main():
    ctx = get_conversation_context(UID)
    ctx.reset()
    ctx.state = ConversationState.AWAITING_OD_NAME

    print("=" * 70)
    print("SIMULASI ALUR PENGAJUAN OVERDAY (satu tanggal)")
    print("=" * 70)

    r = await send("Budi Santoso")
    assert ctx.state == ConversationState.AWAITING_OD_DEPARTMENT

    r = await send("EIC & IT")
    print("[1] dept ->", r.splitlines()[0])
    assert ctx.state == ConversationState.AWAITING_OD_START_DATE
    assert "Tanggal Overday" in r
    assert "tidak perlu tanggal selesai" in r

    # Tanggal salah format -> tetap di step yang sama
    r = await send("25 Okt 2026")
    assert "Format tanggal salah" in r and "Cara mengisi Tanggal Overday" in r
    assert ctx.state == ConversationState.AWAITING_OD_START_DATE

    r = await send("2026-10-25")
    print("[2] tanggal '2026-10-25' ->", r.splitlines()[0])
    # Tidak ada lagi pertanyaan "tanggal selesai"
    assert ctx.state == ConversationState.AWAITING_OD_START_TIME, ctx.state
    assert "Tanggal Selesai" not in r
    assert ctx.get_data("start_date") == "2026-10-25"
    assert ctx.get_data("end_date") == "2026-10-25"

    r = await send("08:00")
    assert ctx.state == ConversationState.AWAITING_OD_END_TIME

    r = await send("20:00")
    assert ctx.state == ConversationState.AWAITING_OD_REASON

    r = await send("Perawatan overhaol kiln 2")
    print("[3] alasan ->", r.splitlines()[0])
    assert ctx.state == ConversationState.CONFIRM_OVERDAY
    assert "2026-10-25" in r
    assert "2026-10-25 - 2026-10-25" not in r
    assert "Total: 12 jam 0 menit" in r, r

    # 4) baris sheet: kolom N = tanggal yang sama
    request = OTRequest(
        row_id=99,
        user_id=UID,
        user_name="Budi Santoso",
        department="EIC & IT",
        request_type="overday",
        od_start_date="2026-10-25",
        od_end_date=ctx.get_data("end_date"),
        start_time="08:00",
        end_time="20:00",
        reason="Perawatan overhaol kiln 2",
        status=RequestStatus.SUBMITTED,
    )
    row = request.to_sheet_row()
    print("[4] sheet row: tanggal OT=%s, total jam=%s, kolom N=%s"
          % (row[6], row[9], row[13]))
    assert row[13] == "2026-10-25", row[13]
    assert row[9] == "12 jam 0 menit", row[9]

    # 5) aturan self-approval: approver boleh menyetujui pengajuannya sendiri
    print("[5] ALLOW_APPROVER_SELF_APPROVAL =", ALLOW_APPROVER_SELF_APPROVAL)
    assert ALLOW_APPROVER_SELF_APPROVAL is True
    approver_id = APPROVERS["approval_1"]["user_id"]
    print("    approver level 1 =", approver_id)
    assert isinstance(approver_id, int)

    print("\n" + "=" * 70)
    print("SEMUA UJI OVERDAY + SELF-APPROVAL LULUS")
    print("=" * 70)


asyncio.run(main())
