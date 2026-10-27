"""
Document Delivery Service
Mengirim dokumen PDF hasil approval ke penerima yang telah diverifikasi.

Modul ini disambungkan ke bot/handlers.py pada blok "Kirim dokumennya sebagai
file terlampir". Pengiriman hanya terjadi untuk pengajuan yang sudah
berstatus APPROVED, dan hanya ke penerima yang lolos validate_recipients().

Aturan pengiriman (dijaga ketat, bukan opsional):
  - Hanya tiga jenis penerima yang boleh:
      1. HR_USER_ID - menerima salinan dokumen (dokumentasi resmi)
      2. pemilik pengajuan (request.user_id) - menerima dokumen miliknya
      3. approver di EXTRA_DOCUMENT_RECIPIENT_USER_IDS (opsional)
  - Tidak ada pengiriman ke nomor Telegram lain, termasuk ke approver
    yang tidak terkait request.
  - Pengiriman hanya terjadi setelah pengajuan berstatus APPROVED.

Kenapa modul terpisah: aturan ini adalah batas privasi data, jadi ia
ditempatkan di satu tempat dan tidak bisa bocor lewat call site lain.
"""

import logging
from typing import Iterable, List, Optional

from config import APPROVERS, EXTRA_DOCUMENT_RECIPIENT_USER_IDS, HR_USER_ID

logger = logging.getLogger("OTBot")


class DeliveryError(Exception):
    """Pengiriman ditolak karena penerima tidak diizinkan."""


def allowed_recipients(owner_user_id: int) -> List[int]:
    """Daftar penerima yang sah untuk sebuah pengajuan."""
    recipients = [HR_USER_ID, owner_user_id]
    # Penerima tambahan yang ditetapkan di config (mis. approver level 1)
    recipients.extend(EXTRA_DOCUMENT_RECIPIENT_USER_IDS)
    return recipients


def document_recipients(owner_user_id: int) -> List[int]:
    """
    Tentukan siapa yang menerima berkas dokumen untuk sebuah pengajuan.

    Mode standar: HR + pemilik pengajuan.
    Mode dengan EXTRA_DOCUMENT_RECIPIENT_USER_IDS: approver yang terdaftar
    + pemilik pengajuan (HR tidak diberi salinan berkas).
    """
    if EXTRA_DOCUMENT_RECIPIENT_USER_IDS:
        recipients = list(EXTRA_DOCUMENT_RECIPIENT_USER_IDS)
        recipients.append(owner_user_id)
        return recipients
    return [HR_USER_ID, owner_user_id]


def approver_name(user_id: int) -> Optional[str]:
    """Nama approver untuk sebuah Telegram user id, atau None."""
    for info in APPROVERS.values():
        if info.get("user_id") == user_id:
            return info.get("name")
    return None


def describe_recipients(owner_user_id: int) -> str:
    """Nama-nama penerima dokumen, untuk ditampilkan di pesan notifikasi."""
    names = []
    for uid in document_recipients(owner_user_id):
        name = approver_name(uid)
        names.append(name if name else "Pemohon")
    return ", ".join(names)


def validate_recipients(recipients: Iterable[int], owner_user_id: int) -> List[int]:
    """
    Pastikan semua penerima berasal dari daftar yang sah.

    Mengembalikan daftar penerima unik yang sudah tervalidasi.
    Melempar DeliveryError bila ada penerima di luar daftar.
    """
    permitted = allowed_recipients(owner_user_id)

    validated = []
    for chat_id in recipients:
        if chat_id not in permitted:
            logger.error(
                f"Pengiriman dokumen DITOLAK: chat {chat_id} bukan penerima "
                f"yang sah untuk pengajuan milik user {owner_user_id}"
            )
            raise DeliveryError(f"chat {chat_id} tidak diizinkan")

        if chat_id not in validated:
            validated.append(chat_id)

    return validated


async def send_document(bot, pdf_content: bytes, file_name: str,
                        recipients: Iterable[int], owner_user_id: int,
                        caption: str = "") -> List[int]:
    """
    Kirim PDF sebagai file terlampir ke penerima yang sudah divalidasi.

    Args:
        bot: Instansi telegram.Bot
        pdf_content: Isi file PDF (bytes)
        file_name: Nama file yang ditampilkan ke penerima
        recipients: Iterable chat id tujuan
        owner_user_id: Telegram user id pemilik pengajuan
        caption: Keterangan singkat pada file

    Returns:
        Daftar chat id yang benar-benar berhasil dikirim.
    """
    targets = validate_recipients(recipients, owner_user_id)

    sent = []
    for chat_id in targets:
        try:
            await bot.send_document(
                chat_id=chat_id,
                document=pdf_content,
                filename=file_name,
                caption=caption,
            )
            sent.append(chat_id)
            logger.info(f"Dokumen dikirim ke chat {chat_id}")
        except Exception as e:
            logger.error(f"Gagal mengirim dokumen ke chat {chat_id}: {e}")

    return sent
