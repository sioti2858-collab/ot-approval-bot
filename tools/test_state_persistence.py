"""
Uji persistensi state percakapan (tanpa koneksi Google Sheets).

Dipakai backend tiruan (fake store) untuk memastikan:
  - state bisa dipulihkan setelah proses restart
  - state tersimpan setiap kali user memberi input
  - state bisa dihapus setelah pengajuan selesai

Dijalankan: python tools/test_state_persistence.py
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import bot.states as states  # noqa: E402
from bot.states import ConversationState  # noqa: E402

failures = []


def check(label, condition, detail=""):
    if condition:
        print(f"  OK   {label}")
    else:
        print(f"  GAGAL {label} {detail}")
        failures.append(label)


class FakeStore:
    """PBACKEND tiruan:QVarying yang meniru services/state_store.py."""

    def __init__(self):
        self.rows = {}
        self.saved = []
        self.deleted = []

    def load(self, user_id):
        return self.rows.get(user_id)

    def save(self, user_id, state, data):
        self.rows[user_id] = {"state": state, "data": dict(data)}
        self.saved.append((user_id, state))

    def delete(self, user_id):
        self.rows.pop(user_id, None)
        self.deleted.append(user_id)


print("== State tanpa persistensi ==")
states.set_state_store(None)
states._conversation_contexts.clear()

ctx = states.get_conversation_context(111)
ctx.state = ConversationState.AWAITING_NAME
ctx.set_data("name", "Budi")
check("context dibuat di memory", ctx.state == ConversationState.AWAITING_NAME)
check("data tersimpan di memory", ctx.get_data("name") == "Budi")

print("== State dengan persistensi ==")
store = FakeStore()
states.set_state_store(store)
states._conversation_contexts.clear()

# Proses "restart": context di memory dibuang, harus dipulihkan dari store.
ctx = states.get_conversation_context(222)
ctx.state = ConversationState.AWAITING_DEPARTMENT
ctx.set_data("name", "Sari")
ctx.set_data("department", "EIC")
states.persist_conversation_context(222)
check("state tersimpan ke backend", 222 in store.rows)
check("state yang disimpan benar",
      store.rows.get(222, {}).get("state") == "awaiting_department")

# Simulasi restart: kosongkan cache memory, lalu ambil context lagi.
states._conversation_contexts.clear()
restored = states.get_conversation_context(222)
check("state dipulihkan setelah restart",
      restored.state == ConversationState.AWAITING_DEPARTMENT,
      f"-> {restored.state}")
check("data dipulihkan setelah restart",
      restored.get_data("name") == "Sari" and restored.get_data("department") == "EIC",
      f"-> {restored.data}")
check("context dipulihkan adalah instance yang sama di cache",
      states.get_conversation_context(222) is restored)

print("== State tidak ada di backend ==")
states._conversation_contexts.clear()
fresh = states.get_conversation_context(333)
check("user baru mulai dari IDLE", fresh.state == ConversationState.IDLE)
check("user baru tidak punya data", fresh.data == {})

print("== Hapus state ==")
states.clear_conversation_context(222)
check("state dihapus dari backend", 222 in store.deleted)
check("state dihapus dari memory", 222 not in states._conversation_contexts)

print("== Backend yang error tidak boleh bikin bot crash ==")


class BrokenStore:
    def load(self, user_id):
        raise RuntimeError("Sheets tidak bisa diakses")

    def save(self, user_id, state, data):
        raise RuntimeError("Sheets tidak bisa diakses")

    def delete(self, user_id):
        raise RuntimeError("Sheets tidak bisa diakses")


states.set_state_store(BrokenStore())
states._conversation_contexts.clear()
try:
    ctx = states.get_conversation_context(444)
    ctx.state = ConversationState.AWAITING_NAME
    states.persist_conversation_context(444)
    states.clear_conversation_context(444)
    check("bot tetap jalan saat backend error", True)
except Exception as error:
    check("bot tetap jalan saat backend error", False, f"-> {error}")

states.set_state_store(None)
states._conversation_contexts.clear()

print()
if failures:
    print(f"GAGAL {len(failures)} pemeriksaan:")
    for item in failures:
        print(f"  - {item}")
    sys.exit(1)

print("SEMUA UJI PERSISTENSI STATE LULUS")
