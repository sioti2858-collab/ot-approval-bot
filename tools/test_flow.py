"""
Uji alur pengajuan lembur dengan objek Telegram tiruan.
Memastikan pesan error selalu menyertakan panduan format yang benar.

Dijalankan: python tools/test_flow.py
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

from bot.handlers import handle_new_request_input  # noqa: E402
from bot.states import ConversationState, get_conversation_context  # noqa: E402


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


UID = 424242


async def send(text):
    up = FakeUpdate(UID, text)
    await handle_new_request_input(up, None)
    return up.message.replies[-1] if up.message.replies else None


async def main():
    ctx = get_conversation_context(UID)
    ctx.reset()
    ctx.state = ConversationState.AWAITING_NAME

    print("=" * 70)
    print("SIMULASI ALUR PENGAJUAN LEMBUR")
    print("=" * 70)

    # 1) nama terlalu pendek -> harus muncul panduan
    r = await send("ab")
    print("\n[1] nama 'ab' (terlalu pendek)")
    print("   ", r.replace("\n", "\n    ")[:300])
    assert "Nama terlalu pendek" in r and "Cara mengisi Nama" in r
    assert ctx.state == ConversationState.AWAITING_NAME, "state harus tetap di step yang sama"

    # 2) nama valid
    r = await send("Budi Santoso")
    print("\n[2] nama 'Budi Santoso' ->", r.splitlines()[0])
    assert ctx.state == ConversationState.AWAITING_DEPARTMENT

    # 3) dept valid
    r = await send("EIC & IT")
    print("[3] dept 'EIC & IT' ->", r.splitlines()[0])
    assert ctx.state == ConversationState.AWAITING_OT_DATE

    # 4) tanggal salah format -> panduan
    r = await send("25 Okt 2026")
    print("\n[4] tanggal '25 Okt 2026' (salah format)")
    print("   ", r.replace("\n", "\n    ")[:400])
    assert "Format tanggal salah" in r and "Cara mengisi Tanggal Lembur" in r
    assert "YYYY-MM-DD" in r
    assert ctx.state == ConversationState.AWAITING_OT_DATE

    # 5) tanggal di luar rentang -> panduan
    r = await send("1999-01-01")
    print("\n[5] tanggal '1999-01-01' (terlalu lampau)")
    print("   ", r.replace("\n", "\n    ")[:250])
    assert "terlalu lampau" in r and "Cara mengisi Tanggal Lembur" in r

    # 6) tanggal valid
    r = await send("2026-10-25")
    print("\n[6] tanggal '2026-10-25' ->", r.splitlines()[0])
    assert ctx.state == ConversationState.AWAITING_START_TIME

    # 7) jam salah -> panduan
    r = await send("lima sore")
    print("\n[7] jam 'lima sore' (salah format)")
    print("   ", r.replace("\n", "\n    ")[:300])
    assert "Format jam salah" in r and "Cara mengisi Jam Mulai" in r
    assert "17:00" in r

    # 8) jam valid
    r = await send("17:00")
    print("\n[8] jam '17:00' ->", r.splitlines()[0])
    assert ctx.state == ConversationState.AWAITING_END_TIME

    # 9) jam selesai salah -> panduan
    r = await send("malam")
    print("\n[9] jam selesai 'malam' (salah format)")
    print("   ", r.replace("\n", "\n    ")[:300])
    assert "Format jam salah" in r and "Cara mengisi Jam Selesai" in r

    # 10) jam selesai valid -> masuk ke alasan
    r = await send("20:00")
    print("\n[10] jam '20:00' ->", r.splitlines()[0])
    assert ctx.state == ConversationState.AWAITING_REASON

    # 11) alasan -> konfirmasi
    r = await send("Penutupan sistem SCADA kiln 2")
    print("[11] alasan ->", r.splitlines()[0])
    assert ctx.state == ConversationState.CONFIRM_REQUEST
    assert "Total: 3 jam 0 menit" in r, r

    print("\n" + "=" * 70)
    print("SEMUA UJI ALUR LULUS")
    print("=" * 70)


asyncio.run(main())
