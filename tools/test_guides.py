"""
Uji fitur panduan perintah (bot/guides.py) tanpa koneksi Telegram.

Dijalankan: python tools/test_guides.py
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

from bot.guides import (  # noqa: E402
    GUIDE_COMMANDS,
    GUIDE_IDLE_TEXT,
    GUIDE_MENU,
    guide_for_state,
    guide_for_type,
)
from bot.states import ConversationState  # noqa: E402
from bot.handlers import handle_unknown_command, handle_idle_text  # noqa: E402


class FakeMessage:
    def __init__(self, text):
        self.text = text
        self.replies = []

    async def reply_text(self, text, parse_mode=None, reply_markup=None):
        self.replies.append(text)


class FakeUser:
    def __init__(self, uid=111):
        self.id = uid
        self.first_name = "Tester"


class FakeUpdate:
    def __init__(self, text):
        self.message = FakeMessage(text)
        self.effective_message = self.message
        self.effective_user = FakeUser()


def show(title, text, limit=400):
    print(f"\n{'='*70}\n{title}\n{'-'*70}")
    print(text[:limit])


async def main():
    # 1) panduan per state
    print("=" * 70)
    print("PANDUAN PER STATE")
    print("=" * 70)
    for state in [
        ConversationState.AWAITING_NAME,
        ConversationState.AWAITING_OT_DATE,
        ConversationState.AWAITING_START_TIME,
        ConversationState.AWAITING_END_TIME,
        ConversationState.AWAITING_REASON,
        ConversationState.AWAITING_OD_START_DATE,
        ConversationState.AWAITING_OD_REASON,
    ]:
        g = guide_for_state(state)
        assert g and len(g) > 20, state
        print(f"  {state.value:28s} -> {len(g):4d} chars, contoh: {g.splitlines()[0]}")

    # 2) panduan per jenis pengajuan
    print("\n" + "=" * 70)
    print("PANDUAN PER JENIS")
    print("=" * 70)
    ot = guide_for_type("overtime", "date")
    od = guide_for_type("overday", "start_date")
    print("  overtime/date      :", ot.splitlines()[0])
    print("  overday/start_date :", od.splitlines()[0])
    assert "Tanggal Overday" in od
    assert "sama" not in od.lower()

    # 3) perintah tidak dikenal
    up = FakeUpdate("/starr")
    await handle_unknown_command(up, None)
    reply = up.effective_message.replies[0]
    show("PERINTAH TIDAK DIKENAL (/starr)", reply)
    assert "/starr" in reply and "/start" in reply

    # 4) teks idle
    up2 = FakeUpdate("halo")
    await handle_idle_text(up2, None)
    reply2 = up2.effective_message.replies[0]
    show("TEKS IDLE (di luar pengajuan)", reply2)
    assert "Menu Utama" in reply2

    # 5) semua panduan memuat contoh format
    print("\n" + "=" * 70)
    print("CEK: setiap panduan memuat contoh format")
    print("=" * 70)
    for state in ConversationState:
        g = guide_for_state(state)
        if not state.value.startswith("awaiting_"):
            continue
        assert "contoh" in g.lower(), state
    print("  semua panduan punya contoh format OK")

    print("\nSEMUA UJI GUIDES LULUS")


asyncio.run(main())
