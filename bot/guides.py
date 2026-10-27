"""
Panduan Perintah (Guides)
Teks cara memakai bot untuk setiap langkah, dipakai ulang saat user
salah ketik atau salah memformat input.

Tujuan: setiap error valider harus menjawab 3 pertanyaan sekaligus:
  1. Apa yang salah
  2. Format yang benar (dengan contoh)
  3. Cara mengulang / membatalkan
"""

from bot.states import ConversationState
from config import MAX_FUTURE_DAYS, MAX_PAST_DAYS


# ---------------------------------------------------------------------------
# Panduan per langkah
# ---------------------------------------------------------------------------

# Batas rentang tanggal, diambil dari config supaya selalu sama dengan
# validasi di bot/handlers.py (validate_date_range).
DATE_RANGE_NOTE = (
    f"💡 Tanggal maksimal {MAX_FUTURE_DAYS} hari ke depan dan "
    f"tidak boleh lebih dari {MAX_PAST_DAYS} hari lalu."
)

GUIDE_NAME = (
    "📝 *Cara mengisi Nama*\n\n"
    "Ketik nama lengkap Anda, minimal 3 huruf.\n"
    "Contoh: `Budi Santoso`"
)

GUIDE_DEPARTMENT = (
    "🏢 *Cara mengisi Dept/Section*\n\n"
    "Ketik nama dept atau section Anda (tidak boleh kosong).\n"
    "Contoh: `EIC & IT` atau `Maintenance`"
)

GUIDE_OT_DATE = (
    "📅 *Cara mengisi Tanggal Lembur*\n\n"
    "Gunakan salah satu format berikut:\n"
    "• `YYYY-MM-DD`  → contoh: `2026-10-25`\n"
    "• `DD/MM/YYYY`  → contoh: `25/10/2026`\n"
    "• `DD-MM-YYYY`  → contoh: `25-10-2026`\n\n"
    + DATE_RANGE_NOTE
)

GUIDE_OD_START_DATE = (
    "📅 *Cara mengisi Tanggal Overday*\n\n"
    "Gunakan salah satu format berikut:\n"
    "• `YYYY-MM-DD`  → contoh: `2026-10-25`\n"
    "• `DD/MM/YYYY`  → contoh: `25/10/2026`\n"
    "• `DD-MM-YYYY`  → contoh: `25-10-2026`\n\n"
    "💡 Cukup satu tanggal, tidak perlu tanggal selesai.\n"
    + DATE_RANGE_NOTE
)

GUIDE_START_TIME = (
    "⏰ *Cara mengisi Jam Mulai*\n\n"
    "Format 24 jam, dua digit jam dan menit, dipisah tanda titik dua.\n"
    "Contoh: `17:00` atau `08:30`\n\n"
    "💡 Jam kecil lebih dulu, lalu ketik `:` - atau cukup ketik `1700`."
)

GUIDE_END_TIME = (
    "⏰ *Cara mengisi Jam Selesai*\n\n"
    "Format 24 jam, dua digit jam dan menit, dipisah tanda titik dua.\n"
    "Contoh: `20:00` atau `06:30`\n\n"
    "💡 Kalau melewati tengah malam, tulis jam selesai lebih kecil, "
    "misal mulai `22:00` selesai `06:00`."
)

GUIDE_REASON = (
    "📝 *Cara mengisi Alasan*\n\n"
    "Tuliskan alasan lembur/overday, чем yang jelas dan singkat.\n"
    "Contoh: `Penutupan sistem SCADA kiln 2`\n\n"
    "💡 Alasan ini akan terbaca oleh approver dan akan tercetak di dokumen."
)

GUIDE_OD_REASON = (
    "📝 *Cara mengisi Alasan Overday*\n\n"
    "Tuliskan alasan overday, чем yang jelas dan singkat.\n"
    "Contoh: `Perawatan overhaol kiln 2`\n\n"
    "💡 Alasan ini akan terbaca oleh approver dan akan tercetak di dokumen."
)

# Panduan umum -------------------------------------------------------------

GUIDE_MENU = (
    "🏠 *Menu Utama*\n\n"
    "Pilih salah satu:\n"
    "• 📝 *Ajukan Lembur* - pengajuan lembur satu hari\n"
    "• 📅 *Ajukan Overday* - pengajuan lembur dengan satu tanggal overday\n"
    "• 📋 *Status Pengajuan Saya* - lihat pengajuan Anda\n"
    "• 📊 *Daftar Pengajuan* - daftar approval (khusus approver)"
)

GUIDE_COMMANDS = (
    "🤖 *Perintah yang tersedia*\n\n"
    "• `/start` - membuka menu utama\n"
    "• `/help` - panduan lengkap\n\n"
    "💡 Semua pengajuan diisi lewat tombol di menu, bukan lewat perintah."
)

GUIDE_IDLE_TEXT = (
    "ℹ️ Saya belum sedang dalam pengajuan yang berjalan.\n\n"
    "Pilih salah satu tombol di bawah, atau ketik `/start` untuk kembali ke menu."
)

GUIDE_CONFIRM = (
    "ℹ️ Data Anda sudah lengkap, tinggal dikonfirmasi.\n\n"
    "Tap tombol **\"✅ Ya, Konfirmasi\"** untuk mengirim pengajuan, "
    "atau **\"❌ Batal\"** untuk membatalkan.\n\n"
    "💡 Pengajuan dikirim lewat tombol, bukan lewat ketikan teks."
)


# ---------------------------------------------------------------------------
# Pemetaan state -> panduan
# ---------------------------------------------------------------------------

_STATE_GUIDES = {
    ConversationState.AWAITING_NAME: GUIDE_NAME,
    ConversationState.AWAITING_DEPARTMENT: GUIDE_DEPARTMENT,
    ConversationState.AWAITING_OT_DATE: GUIDE_OT_DATE,
    ConversationState.AWAITING_START_TIME: GUIDE_START_TIME,
    ConversationState.AWAITING_END_TIME: GUIDE_END_TIME,
    ConversationState.AWAITING_REASON: GUIDE_REASON,
    ConversationState.AWAITING_OD_NAME: GUIDE_NAME,
    ConversationState.AWAITING_OD_DEPARTMENT: GUIDE_DEPARTMENT,
    ConversationState.AWAITING_OD_START_DATE: GUIDE_OD_START_DATE,
    ConversationState.AWAITING_OD_START_TIME: GUIDE_START_TIME,
    ConversationState.AWAITING_OD_END_TIME: GUIDE_END_TIME,
    ConversationState.AWAITING_OD_REASON: GUIDE_OD_REASON,
}


def guide_for_state(state) -> str:
    """Panduan yang sesuai untuk state percakapan tertentu."""
    return _STATE_GUIDES.get(state, GUIDE_MENU)


def guide_for_type(request_type: str, step: str) -> str:
    """
    Panduan berdasarkan jenis pengajuan dan nama langkah.

    Dipakai saat pesan konfirmasi ditampilkan, supaya user tahu persis
    format apa yang diminta pada langkah tersebut.
    """
    if request_type == "overday":
        return {
            "name": GUIDE_NAME,
            "department": GUIDE_DEPARTMENT,
            "start_date": GUIDE_OD_START_DATE,
            "start_time": GUIDE_START_TIME,
            "end_time": GUIDE_END_TIME,
            "reason": GUIDE_OD_REASON,
        }.get(step, GUIDE_MENU)

    return {
        "name": GUIDE_NAME,
        "department": GUIDE_DEPARTMENT,
        "date": GUIDE_OT_DATE,
        "start_time": GUIDE_START_TIME,
        "end_time": GUIDE_END_TIME,
        "reason": GUIDE_REASON,
    }.get(step, GUIDE_MENU)
