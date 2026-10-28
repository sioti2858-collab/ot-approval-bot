"""
Telegram Bot Handlers
Main handlers for the OT approval bot
FIXED: Validation, error handling, duplicate check, time validation
"""

from telegram import Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes
from datetime import datetime, timedelta
import pytz
import logging

from config import (
    ALLOW_APPROVER_SELF_APPROVAL,
    ALLOW_SELF_APPROVAL,
    APPROVERS,
    BUTTON_DEBOUNCE_SECONDS,
    DRIVE_UPLOAD_ENABLED,
    HR_USER_ID,
    MAX_FUTURE_DAYS,
    MAX_PAST_DAYS,
    PDF_MARKER_TELEGRAM,
    SAVE_PDF_LOCALLY,
)
from bot.keyboards import (
    get_main_menu_keyboard,
    get_approval_keyboard,
    get_confirmation_keyboard,
    get_cancel_only_keyboard,
    get_back_to_menu_keyboard,
    get_approval_list_keyboard,
    get_request_detail_keyboard,
    get_user_request_list_keyboard,
    get_request_action_keyboard,
)
from bot.states import (
    ConversationState,
    get_conversation_context,
    clear_conversation_context,
)
from models.ot_request import OTRequest, RequestStatus, ApprovalStatus, ApprovalInfo
from services.sheets import get_sheets_service
from services.drive import get_drive_service
from services.pdf import get_pdf_service
from bot.guides import (
    GUIDE_COMMANDS,
    GUIDE_IDLE_TEXT,
    GUIDE_MENU,
    guide_for_state,
)
from bot.guides import (
    GUIDE_COMMANDS,
    GUIDE_IDLE_TEXT,
    GUIDE_MENU,
    guide_for_state,
)
from services.delivery import (
    describe_recipients as delivery_describe_recipients,
    document_recipients as delivery_document_recipients,
    send_document as delivery_send_document,
)

# Timezone for Indonesia
TZ = pytz.timezone("Asia/Jakarta")

# Logger for this module
logger = logging.getLogger("OTBot")


# =============================================================================
# Helper Functions
# =============================================================================

def is_approver(user_id: int, level: int) -> bool:
    """Check if user is an approver at the specified level"""
    key = f"approval_{level}"
    return user_id == APPROVERS.get(key, {}).get("user_id")


def get_approver_name(level: int) -> str:
    """Get approver name for a level"""
    return APPROVERS.get(f"approval_{level}", {}).get("name", f"Approver {level}")


# =============================================================================
# Idempotensi tombol
# =============================================================================
# Satu tombol yang diketuk berkali-kali hanya boleh diproses sekali.
# Bot Telegram mengirim callback baru setiap kali tombol ditekan, jadi tanpa
# guard ini notifikasi ke approver berikutnya, baris di sheet, dan PDF bisa
# terkirim berkali-kali.

# key: (user_id, callback_data) -> waktu (epoch detik) aksi terakhir
_recent_button_actions: dict = {}


def is_duplicate_action(user_id: int, data: str) -> bool:
    """
    True kalau aksi tombol yang sama baru saja diproses (dalam
    BUTTON_DEBOUNCE_SECONDS detik terakhir), jadi abaikan yang berikutnya.
    """
    now = datetime.now(TZ).timestamp()
    key = (user_id, data)
    last = _recent_button_actions.get(key)

    if last is not None and (now - last) < BUTTON_DEBOUNCE_SECONDS:
        logger.info(
            f"CB | U:{user_id} | aksi '{data}' diabaikan (double-tap)"
        )
        return True

    _recent_button_actions[key] = now

    # Buang entri lama supaya tidak menumpuk di memori.
    if len(_recent_button_actions) > 500:
        cutoff = now - BUTTON_DEBOUNCE_SECONDS
        for old_key, old_time in list(_recent_button_actions.items()):
            if old_time < cutoff:
                del _recent_button_actions[old_key]

    return False


def check_approval_still_valid(request: OTRequest, level: int) -> tuple:
    """
    Cek apakah aksi approve/reject di level ini masih berlaku.

    Mengembalikan (is_valid, pesan_error). Menolak aksi basi dari tombol lama
    (mis. sudah approve lalu diketuk lagi, atau ditolak lalu diketuk Setuju).
    """
    expected_level = request.get_current_approval_level()

    if expected_level is None:
        return False, (
            "❌ *Sudah Diproses*\n\n"
            f"Pengajuan #{request.row_id} sudah selesai diproses "
            f"(status: {request.status.value})."
        )

    if expected_level != level:
        return False, (
            "❌ *Sudah Diproses*\n\n"
            f"Pengajuan #{request.row_id} sudah diproses di level {expected_level}. "
            f"Level {level} sudah lewat."
        )

    return True, ""


async def reply_with_guide(update, error_text: str, guide: str):
    """Balas pesan error sekaligus cara memakai bot yang benar."""
    await update.message.reply_text(
        f"{error_text}\n\n{guide}",
        parse_mode="Markdown",
        reply_markup=get_cancel_only_keyboard(),
    )


async def safe_edit(query, text: str, parse_mode=None, reply_markup=None):
    """
    Edit pesan tanpa melempar error saat isinya tidak berubah.

    Tombol yang ditekan ulang (mis. user mengetuk "Kembali" dua kali) akan
    menghasilkan error "Message is not modified" dari Telegram. Di sini error
    itu ditelan supaya bot tidak mencatat traceback yang tidak perlu.
    """
    try:
        await query.edit_message_text(
            text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
        )
    except TelegramError as error:
        logger.debug(f"Edit pesan dilewati: {error}")


def calculate_total_hours(start_time: str, end_time: str) -> str:
    """Calculate total hours from start_time and end_time"""
    try:
        start = datetime.strptime(start_time, "%H:%M")
        end = datetime.strptime(end_time, "%H:%M")
        diff = end - start
        # Handle overnight shifts (end time is next day)
        if diff.total_seconds() < 0:
            diff = diff + timedelta(days=1)
        hours = diff.seconds // 3600
        minutes = (diff.seconds % 3600) // 60
        return f"{hours} jam {minutes} menit"
    except:
        return "-"


def calculate_total_hours_for_request(request: OTRequest) -> str:
    """
    Calculate total hours of a request.

    For overday, the daily duration is multiplied by the number of days in
    the date range, so a 3-day overday of 08:00-20:00 counts as 36 hours.
    """
    daily = calculate_total_hours(request.start_time, request.end_time)
    if daily == "-" or request.request_type != "overday":
        return daily

    try:
        start_date = datetime.strptime(request.od_start_date, "%Y-%m-%d").date()
        end_date = datetime.strptime(request.od_end_date, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return daily

    num_days = (end_date - start_date).days + 1
    if num_days <= 1:
        return daily

    try:
        start = datetime.strptime(request.start_time, "%H:%M")
        end = datetime.strptime(request.end_time, "%H:%M")
        diff = end - start
        if diff.total_seconds() < 0:
            diff = diff + timedelta(days=1)
        total_minutes = int(diff.total_seconds() // 60) * num_days
        hours, minutes = divmod(total_minutes, 60)
        return f"{hours} jam {minutes} menit ({num_days} hari)"
    except:
        return daily


def validate_date_range(date_str: str) -> tuple:
    """
    Validate if date is within acceptable range.
    Returns (is_valid, error_message)
    """
    try:
        parsed_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        today = datetime.now(TZ).date()

        # Check if date is in the past beyond allowed range
        min_date = today - timedelta(days=MAX_PAST_DAYS)
        if parsed_date < min_date:
            return False, f"Tanggal terlalu lampau. Maksimal {MAX_PAST_DAYS} hari ke belakang."

        # Check if date is too far in the future
        max_date = today + timedelta(days=MAX_FUTURE_DAYS)
        if parsed_date > max_date:
            return False, f"Tanggal terlalu jauh. Maksimal {MAX_FUTURE_DAYS} hari ke depan."

        return True, ""
    except:
        return False, "Format tanggal tidak valid."


# =============================================================================
# Helper Functions
# =============================================================================

def format_request_summary(request: OTRequest) -> str:
    """Format a request into a summary message"""
    status_emoji = {
        "draft": "📝",
        "submitted": "📤",
        "pending_approval_1": "⏳",
        "pending_approval_2": "⏳",
        "pending_approval_3": "⏳",
        "approved": "✅",
        "rejected": "❌",
    }
    emoji = status_emoji.get(request.status.value, "❓")
    total_hours = calculate_total_hours_for_request(request)

    return f"""
📋 Pengajuan Lembur #{request.row_id}

👤 Karyawan: {request.user_name}
🏢 Dept: {request.department}
📅 Tanggal: {request.ot_date}
⏰ Jam: {request.start_time} - {request.end_time}
⏱️ Total: {total_hours}
📝 Alasan: {request.reason}

📊 Status: {emoji} {request.status.value.replace('_', ' ').title()}
"""


def format_overday_summary(request: OTRequest) -> str:
    """Format an overday request into a summary message"""
    status_emoji = {
        "draft": "📝",
        "submitted": "📤",
        "pending_approval_1": "⏳",
        "pending_approval_2": "⏳",
        "approved": "✅",
        "rejected": "❌",
    }
    emoji = status_emoji.get(request.status.value, "❓")
    total_hours = calculate_total_hours_for_request(request)

    # Format date range for overday (tanggal selesai = tanggal overday)
    if request.od_end_date and request.od_end_date != request.od_start_date:
        date_range = f"{request.od_start_date} - {request.od_end_date}"
    else:
        date_range = request.od_start_date

    return f"""
📋 Pengajuan Overday #{request.row_id}

👤 Karyawan: {request.user_name}
🏢 Dept: {request.department}
📅 Tanggal Overday: {date_range}
⏰ Jam: {request.start_time} - {request.end_time}
⏱️ Total: {total_hours}
📝 Alasan: {request.reason}

📊 Status: {emoji} {request.status.value.replace('_', ' ').title()}
"""


def format_approval_detail(request: OTRequest, level: int) -> str:
    """Format approval details for approver"""
    approval_info = {
        1: request.approval_1,
        2: request.approval_2,
        3: request.approval_3,
    }
    approval = approval_info.get(level)

    msg = format_request_summary(request)
    msg += f"\n🔐 Approval Level: {level} ({get_approver_name(level)})"

    if approval:
        status_text = "✅ Disetujui" if approval.status == ApprovalStatus.APPROVED else "❌ Ditolak"
        msg += f"\n✓ Status: {status_text}"
        if approval.timestamp:
            msg += f"\n📅 Waktu: {approval.timestamp.strftime('%d-%m-%Y %H:%M')}"
        if approval.comment:
            msg += f"\n💬 Komentar: {approval.comment}"
    else:
        msg += "\n⏳ Status: Menunggu persetujuan"

    return msg


# =============================================================================
# Main Command Handlers
# =============================================================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user

    welcome_message = f"""
*Perkenalkan saya bot Sitampan OTi*

Halo {user.first_name}! 👋 

Bot ini digunakan untuk:
• Mengajukan lembur
• Mengajukan overday
• Proses persetujuan
• Generate dokumen otomatis

Silakan pilih menu di bawah:
"""

    await update.effective_message.reply_text(
        welcome_message,
        parse_mode="Markdown",
        reply_markup=get_main_menu_keyboard(),
    )


async def handle_unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Balas perintah yang tidak dikenal dengan daftar perintah yang benar."""
    user = update.effective_user
    command = (update.message.text or "").split("@")[0]

    logger.info(f"CMD | U:{user.id} | unknown: {command}")

    await update.effective_message.reply_text(
        f"🤔 Perintah `{command}` tidak dikenal.\n\n"
        f"{GUIDE_COMMANDS}",
        parse_mode="Markdown",
        reply_markup=get_main_menu_keyboard(),
    )


async def handle_idle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bantu user yang mengirim teks acak di luar alur pengajuan."""
    user = update.effective_user
    logger.info(f"MSG | U:{user.id} | idle text, showing guide")

    await update.effective_message.reply_text(
        f"{GUIDE_IDLE_TEXT}\n\n{GUIDE_MENU}",
        parse_mode="Markdown",
        reply_markup=get_main_menu_keyboard(),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    help_text = """
 *Panduan Penggunaan*

*Pengajuan Lembur:*
1. Pilih "Ajukan Lembur" dari menu
2. Isi data: Dept/Section, tanggal, jam, alasan
3. Konfirmasi pengajuan
4. Tunggu persetujuan

*Pengajuan Overday:*
1. Pilih "Ajukan Overday" dari menu
2. Isi data: Dept/Section, tanggal overday, jam, alasan
3. Konfirmasi pengajuan
4. Tunggu persetujuan 2 level

*Status Approval:*
• Overtime: 3 level (Direct Supervisor → Section Head → Manager)
• Overday: 2 level (Section Head → Manager)

*Notifikasi:*
Anda akan menerima notifikasi di setiap tahap persetujuan.

Ketik /start untuk kembali ke menu utama.
"""
    await update.effective_message.reply_text(
        help_text,
        parse_mode="Markdown",
        reply_markup=get_back_to_menu_keyboard(),
    )


# =============================================================================
# Callback Query Handlers
# =============================================================================

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main callback query handler"""
    query = update.callback_query

    user_id = query.from_user.id
    data = query.data

    # Idempotensi: tombol yang diketuk berkali-kali hanya diproses sekali.
    if is_duplicate_action(user_id, data):
        await query.answer(
            text="⏳ Aksi sudah diproses, tunggu sebentar.",
            show_alert=True,
        )
        return

    await query.answer()

    # Parse callback data
    if data == "menu_new_request":
        await handle_new_request_start(query, user_id)
    elif data == "menu_new_overday":
        await handle_new_overday_start(query, user_id)
    elif data == "menu_my_requests":
        await handle_my_requests(query, user_id)
    elif data == "menu_all_requests":
        await handle_all_requests(query, user_id)
    elif data == "back_to_menu":
        await handle_back_to_menu(query, user_id)
    elif data.startswith("approve_"):
        await handle_approval(query, user_id, data, approved=True)
    elif data.startswith("reject_"):
        await handle_rejection(query, user_id, data)
    elif data.startswith("view_approval_"):
        await handle_view_approval(query, user_id, data)
    elif data.startswith("view_request_"):
        await handle_view_request(query, user_id, data)
    elif data.startswith("view_pdf_"):
        await handle_view_pdf(query, user_id, data)
    elif data.startswith("confirm_"):
        await handle_confirmation(query, user_id, data)
    elif data.startswith("cancel_"):
        await handle_cancel(query, user_id, data)
    elif data.startswith("back_to_approval_list_"):
        await handle_back_to_approval_list(query, user_id, data)
    elif data == "back_to_my_requests":
        await handle_my_requests(query, user_id)


# =============================================================================
# New Request Flow
# =============================================================================

async def handle_new_request_start(query, user_id):
    """Start new OT request flow"""
    ctx = get_conversation_context(user_id)
    ctx.reset()
    ctx.state = ConversationState.AWAITING_NAME
    ctx.set_data("request_type", "overtime")  # Set type automatically

    try:
        await query.edit_message_text(
            "🏢 *Pengajuan Lembur Baru*\n\n"
            "Masukkan nama lengkap Anda:",
            parse_mode="Markdown",
            reply_markup=get_cancel_only_keyboard(),
        )
    except Exception:
        # Message not modified or other error - ignore silently
        pass


async def handle_new_request_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle input during new request flow"""
    user_id = update.message.from_user.id
    ctx = get_conversation_context(user_id)
    text = update.message.text.strip()

    # NEW: Handle name input
    if ctx.state == ConversationState.AWAITING_NAME:
        if len(text) < 3:
            await update.message.reply_text(
                "❌ Nama terlalu pendek. Masukkan nama lengkap Anda."
            )
            await reply_with_guide(
                update, "❌ Nama terlalu pendek. Masukkan nama lengkap Anda.",
                guide_for_state(ctx.state),
            )
            return
        if not text or not text.strip():
            await update.message.reply_text(
                "❌ Nama tidak boleh kosong. Masukkan nama lengkap Anda."
            )
            await reply_with_guide(
                update, "❌ Nama tidak boleh kosong. Masukkan nama lengkap Anda.",
                guide_for_state(ctx.state),
            )
            return
        ctx.set_data("name", text)
        ctx.state = ConversationState.AWAITING_DEPARTMENT
        await update.message.reply_text(
            "🏢 *Dept/Section*\n\n"
            "Masukkan nama Dept/Section Anda:",
            parse_mode="Markdown",
        )

    elif ctx.state == ConversationState.AWAITING_DEPARTMENT:
        if not text or not text.strip():
            await update.message.reply_text(
                "❌ Dept/Section tidak boleh kosong. Masukkan nama Dept/Section Anda."
            )
            await reply_with_guide(
                update, "❌ Dept/Section tidak boleh kosong. Masukkan nama Dept/Section Anda.",
                guide_for_state(ctx.state),
            )
            return
        ctx.set_data("department", text)
        ctx.state = ConversationState.AWAITING_OT_DATE
        await update.message.reply_text(
            "📅 *Tanggal Lembur*\n\n"
            "Masukkan tanggal lembur (format: YYYY-MM-DD, contoh: 2024-06-15):",
            parse_mode="Markdown",
        )

    elif ctx.state == ConversationState.AWAITING_OT_DATE:
        # Validate date format - accept multiple formats
        try:
            # Try YYYY-MM-DD first
            parsed_date = datetime.strptime(text, "%Y-%m-%d")
            date_str = text
        except ValueError:
            try:
                # Try DD/MM/YYYY
                parsed_date = datetime.strptime(text, "%d/%m/%Y")
                date_str = parsed_date.strftime("%Y-%m-%d")
            except ValueError:
                try:
                    # Try DD-MM-YYYY
                    parsed_date = datetime.strptime(text, "%d-%m-%Y")
                    date_str = parsed_date.strftime("%Y-%m-%d")
                except ValueError:
                    await update.message.reply_text(
                        "❌ Format tanggal salah."
                    )
                    await reply_with_guide(
                        update, "❌ Format tanggal salah.",
                        guide_for_state(ctx.state),
                    )
                    return

        # NEW: Validate date range
        is_valid, error_msg = validate_date_range(date_str)
        if not is_valid:
            await reply_with_guide(
                update, f"❌ {error_msg}", guide_for_state(ctx.state),
            )
            return

        ctx.set_data("ot_date", date_str)
        ctx.state = ConversationState.AWAITING_START_TIME
        await update.message.reply_text(
            "⏰ *Jam Mulai*\n\n"
            "Masukkan jam mulai lembur (format: HH:MM, contoh: 17:00):",
            parse_mode="Markdown",
        )

    elif ctx.state == ConversationState.AWAITING_START_TIME:
        # Validate time format
        try:
            datetime.strptime(text, "%H:%M")
            ctx.set_data("start_time", text)
            ctx.state = ConversationState.AWAITING_END_TIME
            await update.message.reply_text(
                "⏰ *Jam Selesai*\n\n"
                "Masukkan jam selesai lembur (format: HH:MM, contoh: 20:00):",
                parse_mode="Markdown",
            )
        except ValueError:
            await update.message.reply_text(
                "❌ Format jam salah."
            )
            await reply_with_guide(
                update, "❌ Format jam salah.",
                guide_for_state(ctx.state),
            )

    elif ctx.state == ConversationState.AWAITING_END_TIME:
        # Validate time format
        try:
            datetime.strptime(text, "%H:%M")
            start_time = ctx.get_data("start_time")

            # NEW: Validate end time is after start time
            start_dt = datetime.strptime(start_time, "%H:%M")
            end_dt = datetime.strptime(text, "%H:%M")
            diff = end_dt - start_dt

            # Allow overnight shifts (negative diff means end time is next day)
            if diff.total_seconds() <= 0:
                diff_hours = (diff.total_seconds() + 86400) / 3600
            else:
                diff_hours = diff.total_seconds() / 3600

            # Warn if less than 1 hour
            if diff_hours < 1:
                await update.message.reply_text(
                    "⚠️ *Peringatan*: Total jam lembur kurang dari 1 jam.\n"
                    "Apakah Anda yakin ingin melanjutkan?",
                    parse_mode="Markdown",
                    reply_markup=get_confirmation_keyboard(f"endtime_1_{text}"),
                )
                return

            # Warn if more than 8 hours
            if diff_hours > 8:
                await update.message.reply_text(
                    f"⚠️ *Peringatan*: Total jam lembur adalah {int(diff_hours)} jam.\n"
                    "Apakah Anda yakin ingin melanjutkan?",
                    parse_mode="Markdown",
                    reply_markup=get_confirmation_keyboard(f"endtime_1_{text}"),
                )
                return

            ctx.set_data("end_time", text)
            ctx.state = ConversationState.AWAITING_REASON
            await update.message.reply_text(
                "📝 *Alasan Lembur*\n\n"
                "Jelaskan alasan mengapa Anda perlu lembur:",
                parse_mode="Markdown",
            )
        except ValueError:
            await update.message.reply_text(
                "❌ Format jam salah."
            )
            await reply_with_guide(
                update, "❌ Format jam salah.",
                guide_for_state(ctx.state),
            )

    elif ctx.state == ConversationState.AWAITING_REASON:
        ctx.set_data("reason", text)
        ctx.state = ConversationState.CONFIRM_REQUEST

        # Calculate total hours for display
        total_hours = calculate_total_hours(
            ctx.get_data("start_time"),
            ctx.get_data("end_time")
        )

        # Show confirmation with total hours
        confirmation_text = f"""
✅ *Konfirmasi Pengajuan Lembur*

🏢 Dept/Section: {ctx.get_data('department')}
📅 Tanggal: {ctx.get_data('ot_date')}
⏰ Jam: {ctx.get_data('start_time')} - {ctx.get_data('end_time')}
⏱️ Total: {total_hours}
📝 Alasan: {text}

Apakah data sudah benar?
"""
        await update.message.reply_text(
            confirmation_text,
            parse_mode="Markdown",
            reply_markup=get_confirmation_keyboard("submit_request"),
        )


# =============================================================================
# Overday Request Flow
# =============================================================================

async def handle_new_overday_start(query, user_id):
    """Start new Overday request flow"""
    ctx = get_conversation_context(user_id)
    ctx.reset()
    ctx.state = ConversationState.AWAITING_OD_NAME
    ctx.set_data("request_type", "overday")  # Set type automatically

    try:
        await query.edit_message_text(
            "📅 *Pengajuan Overday Baru*\n\n"
            "Masukkan nama lengkap Anda:",
            parse_mode="Markdown",
            reply_markup=get_cancel_only_keyboard(),
        )
    except Exception:
        # Message not modified or other error - ignore silently
        pass


async def handle_overday_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle input during overday request flow"""
    user_id = update.message.from_user.id
    ctx = get_conversation_context(user_id)
    text = update.message.text.strip()

    if ctx.state == ConversationState.AWAITING_OD_NAME:
        if len(text) < 3:
            await update.message.reply_text(
                "❌ Nama terlalu pendek. Masukkan nama lengkap Anda."
            )
            await reply_with_guide(
                update, "❌ Nama terlalu pendek. Masukkan nama lengkap Anda.",
                guide_for_state(ctx.state),
            )
            return
        if not text or not text.strip():
            await update.message.reply_text(
                "❌ Nama tidak boleh kosong. Masukkan nama lengkap Anda."
            )
            await reply_with_guide(
                update, "❌ Nama tidak boleh kosong. Masukkan nama lengkap Anda.",
                guide_for_state(ctx.state),
            )
            return
        ctx.set_data("name", text)
        ctx.state = ConversationState.AWAITING_OD_DEPARTMENT
        await update.message.reply_text(
            "🏢 *Dept/Section*\n\n"
            "Masukkan nama Dept/Section Anda:",
            parse_mode="Markdown",
        )

    elif ctx.state == ConversationState.AWAITING_OD_DEPARTMENT:
        if not text or not text.strip():
            await update.message.reply_text(
                "❌ Dept/Section tidak boleh kosong. Masukkan nama Dept/Section Anda."
            )
            await reply_with_guide(
                update, "❌ Dept/Section tidak boleh kosong. Masukkan nama Dept/Section Anda.",
                guide_for_state(ctx.state),
            )
            return
        ctx.set_data("department", text)
        ctx.state = ConversationState.AWAITING_OD_START_DATE
        await update.message.reply_text(
            "📅 *Tanggal Overday*\n\n"
            "Masukkan tanggal overday (format: YYYY-MM-DD, contoh: 2024-06-15):\n"
            "💡 Cukup satu tanggal, tidak perlu tanggal selesai.",
            parse_mode="Markdown",
        )

    elif ctx.state == ConversationState.AWAITING_OD_START_DATE:
        try:
            # Try YYYY-MM-DD first
            parsed_date = datetime.strptime(text, "%Y-%m-%d")
            date_str = text
        except ValueError:
            try:
                # Try DD/MM/YYYY
                parsed_date = datetime.strptime(text, "%d/%m/%Y")
                date_str = parsed_date.strftime("%Y-%m-%d")
            except ValueError:
                try:
                    # Try DD-MM-YYYY
                    parsed_date = datetime.strptime(text, "%d-%m-%Y")
                    date_str = parsed_date.strftime("%Y-%m-%d")
                except ValueError:
                    await update.message.reply_text(
                        "❌ Format tanggal salah."
                    )
                    await reply_with_guide(
                        update, "❌ Format tanggal salah.",
                        guide_for_state(ctx.state),
                    )
                    return

        # NEW: Validate date range
        is_valid, error_msg = validate_date_range(date_str)
        if not is_valid:
            await reply_with_guide(
                update, f"❌ {error_msg}", guide_for_state(ctx.state),
            )
            return

        ctx.set_data("start_date", date_str)
        # Overday hanya butuh satu tanggal: tanggal selesai disamakan dengan
        # tanggal overday (kolom N di sheet diisi tanggal yang sama).
        ctx.set_data("end_date", date_str)
        ctx.state = ConversationState.AWAITING_OD_START_TIME
        await update.message.reply_text(
            "⏰ *Jam Mulai*\n\n"
            "Masukkan jam mulai overday (format: HH:MM, contoh: 08:00):",
            parse_mode="Markdown",
        )

    elif ctx.state == ConversationState.AWAITING_OD_START_TIME:
        try:
            datetime.strptime(text, "%H:%M")
            ctx.set_data("start_time", text)
            ctx.state = ConversationState.AWAITING_OD_END_TIME
            await update.message.reply_text(
                "⏰ *Jam Selesai*\n\n"
                "Masukkan jam selesai overday (format: HH:MM, contoh: 20:00):",
                parse_mode="Markdown",
            )
        except ValueError:
            await update.message.reply_text(
                "❌ Format jam salah."
            )
            await reply_with_guide(
                update, "❌ Format jam salah.",
                guide_for_state(ctx.state),
            )

    elif ctx.state == ConversationState.AWAITING_OD_END_TIME:
        try:
            datetime.strptime(text, "%H:%M")
            ctx.set_data("end_time", text)
            ctx.state = ConversationState.AWAITING_OD_REASON
            await update.message.reply_text(
                "📝 *Alasan Overday*\n\n"
                "Jelaskan alasan mengapa Anda perlu overday:",
                parse_mode="Markdown",
            )
        except ValueError:
            await update.message.reply_text(
                "❌ Format jam salah."
            )
            await reply_with_guide(
                update, "❌ Format jam salah.",
                guide_for_state(ctx.state),
            )

    elif ctx.state == ConversationState.AWAITING_OD_REASON:
        ctx.set_data("reason", text)
        ctx.state = ConversationState.CONFIRM_OVERDAY

        # Calculate total hours for display
        total_hours = calculate_total_hours(
            ctx.get_data("start_time"),
            ctx.get_data("end_time")
        )

        # Format date range
        start_date = ctx.get_data("start_date")
        end_date = ctx.get_data("end_date")
        if start_date == end_date:
            date_range = start_date
        else:
            date_range = f"{start_date} - {end_date}"

        confirmation_text = f"""
✅ *Konfirmasi Pengajuan Overday*

🏢 Dept/Section: {ctx.get_data('department')}
📅 Tanggal Overday: {date_range}
⏰ Jam: {ctx.get_data('start_time')} - {ctx.get_data('end_time')}
⏱️ Total: {total_hours}
📝 Alasan: {text}

Apakah data sudah benar?
"""
        await update.message.reply_text(
            confirmation_text,
            parse_mode="Markdown",
            reply_markup=get_confirmation_keyboard("submit_overday"),
        )


# =============================================================================
# Submit Request Handler
# =============================================================================

async def handle_confirmation(query, user_id, data):
    """Handle confirmation actions"""
    action = data.replace("confirm_", "")

    if action.startswith("endtime_1_"):
        # Konfirmasi durasi ekstrem (<1 jam atau >8 jam).
        # Format: confirm_endtime_1_{HH:MM}
        ctx = get_conversation_context(user_id)
        end_time = action.split("_", 2)[2] if action.count("_") >= 2 else ""

        try:
            datetime.strptime(end_time, "%H:%M")
        except ValueError:
            await query.edit_message_text(
                "❌ *Format Jam Salah*\n\n"
                "Gunakan format HH:MM (contoh: 20:00).\n"
                "Silakan ulangi jam selesai lembur.",
                parse_mode="Markdown",
                reply_markup=get_back_to_menu_keyboard(),
            )
            clear_conversation_context(user_id)
            return

        ctx.set_data("end_time", end_time)
        ctx.state = ConversationState.AWAITING_REASON

        await query.edit_message_text(
            "📝 *Alasan Lembur*\n\n"
            "Jelaskan alasan mengapa Anda perlu lembur:",
            parse_mode="Markdown",
        )
        return

    if action == "submit_request":
        ctx = get_conversation_context(user_id)
        user = query.from_user

        # FIX: Validate all required data exists (prevent cancelled requests from being sent)
        required_fields = ["name", "department", "ot_date", "start_time", "end_time", "reason"]
        missing_fields = [f for f in required_fields if not ctx.get_data(f)]

        if missing_fields:
            # Data is missing (likely cancelled) - don't submit
            await query.edit_message_text(
                "❌ *Pengajuan Tidak Valid*\n\n"
                "Data pengajuan tidak lengkap. Silakan mulai lagi.",
                parse_mode="Markdown",
                reply_markup=get_main_menu_keyboard(),
            )
            clear_conversation_context(user_id)
            return

        # Create OT request - use MANUAL NAME (not from Telegram)
        request = OTRequest(
            row_id=0,  # Will be set by sheets service
            user_id=user_id,
            user_name=ctx.get_data("name"),  # Manual input name
            department=ctx.get_data("department"),
            request_type=ctx.get_data("request_type", "overtime"),
            ot_date=ctx.get_data("ot_date"),
            start_time=ctx.get_data("start_time"),
            end_time=ctx.get_data("end_time"),
            reason=ctx.get_data("reason"),
            submitted_at=datetime.now(TZ),
            status=RequestStatus.SUBMITTED,
        )

        # Save to Google Sheets
        sheets = get_sheets_service()
        row_id = sheets.add_request(request)
        request.row_id = row_id

        # Clear conversation
        clear_conversation_context(user_id)

        # Confirm to user
        await query.edit_message_text(
            f"✅ *Pengajuan Lembur #{row_id} Berhasil!*\n\n"
            f"Pengajuan Anda telah diterima dan sedang menunggu persetujuan.\n\n"
            f"📋 No. Pengajuan: *#{row_id}*\n"
            f"📅 Tanggal: {request.ot_date}\n"
            f"⏰ Jam: {request.start_time} - {request.end_time}\n\n"
            f"Anda akan menerima notifikasi setelah ada aksi dari approver.",
            parse_mode="Markdown",
            reply_markup=get_back_to_menu_keyboard(),
        )

        # Notify approver 1
        approver_1_id = APPROVERS.get("approval_1", {}).get("user_id")
        if approver_1_id:
            from telegram import Bot
            bot = Bot(token=query._bot.token)
            summary = format_request_summary(request)
            await bot.send_message(
                chat_id=approver_1_id,
                text=f"🔔 *Pengajuan Lembur Baru*\n\n{summary}\n\nSilakan review dan approve:",
                parse_mode="Markdown",
                reply_markup=get_approval_keyboard(row_id, 1),
            )

    elif action == "cancel_request":
        clear_conversation_context(user_id)
        await query.edit_message_text(
            "❌ *Pengajuan Dibatalkan*\n\n"
            "Pengajuan lembur Anda telah dibatalkan.\n"
            "Silakan mulai lagi dengan memilih menu.",
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard(),
        )

    elif action == "submit_overday":
        ctx = get_conversation_context(user_id)
        user = query.from_user

        # Validate all required data exists
        required_fields = ["name", "department", "start_date", "start_time", "end_time", "reason"]
        missing_fields = [f for f in required_fields if not ctx.get_data(f)]

        if missing_fields:
            await query.edit_message_text(
                "❌ *Pengajuan Tidak Valid*\n\n"
                "Data pengajuan tidak lengkap. Silakan mulai lagi.",
                parse_mode="Markdown",
                reply_markup=get_main_menu_keyboard(),
            )
            clear_conversation_context(user_id)
            return

        # Create Overday request
        request = OTRequest(
            row_id=0,
            user_id=user_id,
            user_name=ctx.get_data("name"),
            department=ctx.get_data("department"),
            request_type="overday",
            od_start_date=ctx.get_data("start_date"),
            od_end_date=ctx.get_data("end_date"),
            start_time=ctx.get_data("start_time"),
            end_time=ctx.get_data("end_time"),
            reason=ctx.get_data("reason"),
            submitted_at=datetime.now(TZ),
            status=RequestStatus.SUBMITTED,
        )

        # Save to Google Sheets
        sheets = get_sheets_service()
        row_id = sheets.add_request(request)
        request.row_id = row_id

        # Clear conversation
        clear_conversation_context(user_id)

        # Confirm to user
        await query.edit_message_text(
            f"✅ *Pengajuan Overday #{row_id} Berhasil!*\n\n"
            f"Pengajuan Anda telah diterima dan sedang menunggu persetujuan.\n\n"
            f"📋 No. Pengajuan: *#{row_id}*\n"
            f"📅 Tanggal: {request.od_start_date}\n"
            f"⏰ Jam: {request.start_time} - {request.end_time}\n\n"
            f"Anda akan menerima notifikasi setelah ada aksi dari approver.",
            parse_mode="Markdown",
            reply_markup=get_back_to_menu_keyboard(),
        )

        # Notify approver 1 - Overday starts at level 1
        approver_1_id = APPROVERS.get("approval_1", {}).get("user_id")
        if approver_1_id:
            from telegram import Bot
            bot = Bot(token=query._bot.token)
            summary = format_overday_summary(request)
            await bot.send_message(
                chat_id=approver_1_id,
                text=f"🔔 *Pengajuan Overday Baru*\n\n{summary}\n\nSilakan review dan approve:",
                parse_mode="Markdown",
                reply_markup=get_approval_keyboard(row_id, 1),
            )


async def handle_cancel(query, user_id, data):
    """Handle cancel actions"""
    logger.info(f"CB | U:{user_id} | Cancel action: {data}")

    # Clear any ongoing conversation
    clear_conversation_context(user_id)

    await query.edit_message_text(
        "❌ *Pengajuan Dibatalkan*\n\n"
        "Silakan mulai lagi dengan memilih menu di bawah.",
        parse_mode="Markdown",
        reply_markup=get_main_menu_keyboard(),
    )


# =============================================================================
# Approval Handlers
# =============================================================================

async def handle_view_approval(query, user_id, data):
    """View details of a request pending approval"""
    # Parse: view_approval_{level}_{row_id}
    parts = data.split("_")
    level = int(parts[2])
    row_id = int(parts[3])

    # Check if user is authorized
    if not is_approver(user_id, level):
        await query.edit_message_text(
            "❌ *Akses Ditolak*\n\n"
            "Anda bukan approver untuk level ini.",
            parse_mode="Markdown",
        )
        return

    # Get request from sheets
    sheets = get_sheets_service()
    request = sheets.get_request_by_row(row_id)

    if not request:
        await query.edit_message_text(
            "❌ *Data Tidak Ditemukan*\n\n"
            "Pengajuan tidak ditemukan.",
            parse_mode="Markdown",
        )
        return

    # Show request details with approval options
    await safe_edit(
        query,
        format_approval_detail(request, level),
        parse_mode="Markdown",
        reply_markup=get_request_detail_keyboard(row_id, level, request.status.value),
    )


async def handle_approval(query, user_id, data, approved: bool):
    """Handle approval action"""
    # Parse: approve_{level}_{row_id}
    parts = data.split("_")
    level = int(parts[1])
    row_id = int(parts[2])

    # Check if user is authorized
    if not is_approver(user_id, level):
        await query.edit_message_text(
            "❌ *Akses Ditolak*\n\n"
            "Anda bukan approver untuk level ini.",
            parse_mode="Markdown",
        )
        return

    # Get request from sheets
    sheets = get_sheets_service()
    request = sheets.get_request_by_row(row_id)

    if not request:
        await query.edit_message_text(
            "❌ *Data Tidak Ditemukan*\n\n"
            "Pengajuan tidak ditemukan.",
            parse_mode="Markdown",
        )
        return

    # Aksi basi ditolak: pengajuan yang sudah lewat level ini (mis. tombol lama
    # yang masih diketuk lagi) tidak boleh diproses dua kali.
    is_valid, invalid_message = check_approval_still_valid(request, level)
    if not is_valid:
        await query.edit_message_text(
            invalid_message,
            parse_mode="Markdown",
            reply_markup=get_back_to_menu_keyboard(),
        )
        return

    # Approver tidak boleh menyetujui pengajuan yang dia ajukan sendiri,
    # KECUALI Approver yang terdaftar (level 1/2/3): supaya approver yang juga
    # pemohon tidak terjebak - tidak ada orang lain di level yang sama.
    # Self-approval dicatat atas namanya sendiri di approval history.
    if (
        request.user_id == user_id
        and not ALLOW_SELF_APPROVAL
        and not ALLOW_APPROVER_SELF_APPROVAL
    ):
        logger.warning(
            f"Self-approval ditolak: U:{user_id} mencoba menyetujui "
            f"pengajuannya sendiri (#{row_id})"
        )
        await query.edit_message_text(
            "❌ *Self-Approval Ditolak*\n\n"
            "Anda tidak bisa menyetujui pengajuan yang Anda ajukan sendiri.\n\n"
            "Pengajuan ini harus disetujui approver lain.",
            parse_mode="Markdown",
            reply_markup=get_back_to_menu_keyboard(),
        )
        return

    # Approver yang menyetujui pengajuannya sendiri dicatat atas namanya sendiri
    # (bukan nama approver level lain), supaya jejaknya jelas di dokumen.
    approver_display_name = get_approver_name(level)

    # Create approval info
    approval = ApprovalInfo(
        approver_name=approver_display_name,
        status=ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED,
        timestamp=datetime.now(TZ),
        comment="",  # Could be extended to ask for comment
    )

    # Update approval info
    if level == 1:
        request.approval_1 = approval
    elif level == 2:
        request.approval_2 = approval
    elif level == 3:
        request.approval_3 = approval

    # Update sheets
    sheets.update_approval(
        row_id,
        level,
        approval.approver_name,
        approval.status,
        approval.timestamp,
    )

    # Determine new status
    if approved:
        # Check if this is an overday request (2 levels only)
        is_overday = request.request_type == "overday"
        max_level = 2 if is_overday else 3

        if level < max_level:
            new_status = {
1: RequestStatus.PENDING_APPROVAL_1,
                2: RequestStatus.PENDING_APPROVAL_2,
            }[level]

            # Update both database AND memory
            sheets.update_status(row_id, new_status)
            request.status = new_status

            # DEBUG: Print status update
            logger.info(f"Level {level} approved. Status updated to: {new_status.value}")
            logger.debug(f"Row ID: {row_id}, Next approver level: {level + 1}")

            # Notify next approver
            next_approver_id = APPROVERS.get(f"approval_{level + 1}", {}).get("user_id")
            logger.debug(f"Next approver ID: {next_approver_id}")

            if next_approver_id:
                try:
                    from telegram import Bot
                    bot = Bot(token=query._bot.token)
                    summary = format_overday_summary(request) if is_overday else format_request_summary(request)
                    approval_type = "Overday" if is_overday else "Lembur"
                    await bot.send_message(
                        chat_id=next_approver_id,
                        text=f"🔔 *Approval Lanjut {approval_type}: Level {level + 1}*\n\n{summary}\n\nSilakan review dan approve:",
                        parse_mode="Markdown",
                        reply_markup=get_approval_keyboard(row_id, level + 1),
                    )
                    logger.info(f"Notification sent to approver level {level + 1}")
                except Exception as e:
                    logger.error(f"Failed to send notification to approver: {e}")
                    status_text = f"✅ *Approved* (Level {level})\n\nPengajuan #{row_id} telah disetujui. Tapi notifikasi gagal dikirim: {str(e)}"
                    await query.edit_message_text(status_text, parse_mode="Markdown", reply_markup=get_back_to_menu_keyboard())
                    return
            else:
                logger.warning(f"No next approver found for level {level + 1}")

            status_text = f"✅ *Approved* (Level {level})\n\nPengajuan #{row_id} telah disetujui pada level {level}. Menunggu approval level {level + 1}."
        else:
            # All approvals complete - generate PDF
            new_status = RequestStatus.APPROVED
            sheets.update_status(row_id, new_status)
            request.status = new_status

            # Re-fetch request to get all approval info (from parsed history)
            request = sheets.get_request_by_row(row_id)
            request.status = new_status

            # Initialize variables
            pdf_content = None
            pdf_url = "PDF not available"

            # Generate PDF based on request type
            try:
                pdf_service = get_pdf_service()
                if request.request_type == "overday":
                    pdf_content = pdf_service.generate_overday_form(request)
                    logger.info(f"Overday PDF generated successfully for request #{row_id}")
                else:
                    pdf_content = pdf_service.generate_ot_form(request)
                    logger.info(f"Overtime PDF generated successfully for request #{row_id}")

                # Arsip lokal. Kalau SAVE_PDF_LOCALLY=false (mode cloud),
                # PDF tidak menyentuh disk sama sekali - dikirim ke Telegram
                # saja, karena folder container hilang tiap redeploy.
                import os
                if request.request_type == "overday":
                    local_file_name = f"pdfs/OD_{row_id}_{request.user_name}_{request.od_start_date}.pdf"
                    drive_file_name = f"OD_{row_id}_{request.user_name}_{request.od_start_date}.pdf"
                else:
                    local_file_name = f"pdfs/OT_{row_id}_{request.user_name}_{request.ot_date}.pdf"
                    drive_file_name = f"OT_{row_id}_{request.user_name}_{request.ot_date}.pdf"

                if SAVE_PDF_LOCALLY:
                    os.makedirs("pdfs", exist_ok=True)
                    with open(local_file_name, "wb") as f:
                        f.write(pdf_content)
                    logger.info(f"PDF saved locally: {local_file_name}")
                else:
                    logger.info(
                        "Local archive disabled - PDF hanya dikirim via Telegram"
                    )

                # Upload ke Google Drive hanya kalau DRIVE_UPLOAD_ENABLED=true.
                # Secara default nonaktif: service account tidak punya storage
                # quota di My Drive, jadi upload ke folder biasa ditolak 403.
                # Aktifkan setelah Shared Drive tersedia.
                if DRIVE_UPLOAD_ENABLED:
                    try:
                        drive_service = get_drive_service()
                        pdf_url = drive_service.upload_pdf(pdf_content, drive_file_name)
                        logger.info(f"PDF uploaded to Drive: {pdf_url}")
                    except Exception as upload_error:
                        logger.error(f"Upload to Drive failed: {upload_error}")
                        pdf_url = None
                else:
                    logger.info("Drive upload disabled - PDF hanya diarsipkan lokal")
                    pdf_url = None

                if pdf_url:
                    request.pdf_url = pdf_url
                    document_note = f"📎 {pdf_url}"
                elif SAVE_PDF_LOCALLY:
                    request.pdf_url = f"local:{local_file_name}"
                    document_note = (
                        "📎 Dokumen dikirim sebagai file terlampir ke: "
                        f"{delivery_describe_recipients(request.user_id)}"
                    )
                else:
                    # Mode Telegram-only: tidak ada arsip lokal dan tidak ada
                    # link Drive, jadi kolom O hanya berisi penanda.
                    request.pdf_url = PDF_MARKER_TELEGRAM
                    document_note = (
                        "📎 Dokumen dikirim sebagai file terlampir ke: "
                        f"{delivery_describe_recipients(request.user_id)}"
                    )

                # Penerima dokumen ditentukan di services/delivery.py
                doc_recipients = delivery_document_recipients(request.user_id)

                try:
                    sheets.update_pdf_url(row_id, request.pdf_url)
                except Exception as sheet_error:
                    logger.error(f"Failed to store document reference in sheet: {sheet_error}")

                # Notify HR and user
                from telegram import Bot
                bot = Bot(token=query._bot.token)

                # Determine request type labels
                is_overday = request.request_type == "overday"
                doc_type = "Overday" if is_overday else "OT"
                date_display = request.od_start_date if is_overday else request.ot_date

                # Notify HR
                await bot.send_message(
                    chat_id=HR_USER_ID,
                    text=f"📋 *{doc_type} Approved - #{row_id}*\n\n"
                         f"Pegawai: {request.user_name}\n"
                         f"Dept/Section: {request.department}\n"
                         f"Tanggal: {date_display}\n"
                         f"Jam: {request.start_time} - {request.end_time}\n"
                         f"Alasan: {request.reason}\n\n"
                         f"📄 Dokumen {doc_type} #{row_id} telah disetujui.\n\n"
                         f"{document_note}",
                    parse_mode="Markdown",
                )

                # Notify user
                request_label = "Overday" if is_overday else "Lembur"
                await bot.send_message(
                    chat_id=request.user_id,
                    text=f"✅ *Pengajuan {request_label} #{row_id} Approved*\n\n"
                         f"Selamat! Pengajuan {request_label.lower()} Anda telah disetujui di semua level.\n\n"
                         f"📄 Dokumen {doc_type}:\n{document_note}",
                    parse_mode="Markdown",
                )

                # Kirim dokumennya sebagai file terlampir ke penerima yang sah.
                # Penerima divalidasi di services/delivery.py: hanya HR, pemilik
                # pengajuan, dan approver yang terdaftar di config.
                await delivery_send_document(
                    bot=bot,
                    pdf_content=pdf_content,
                    file_name=os.path.basename(local_file_name),
                    recipients=doc_recipients,
                    owner_user_id=request.user_id,
                    caption=f"📄 {doc_type} #{row_id} - {request.user_name} - {date_display}",
                )

                status_text = f"✅ *Fully Approved!*\n\nPengajuan #{row_id} telah disetujui di semua level.\n\n📄 Dokumen {doc_type} sudah dibuat."

            except Exception as e:
                # Log full error for debugging
                import traceback
                logger.error(f"PDF generation failed for request #{row_id}: {e}")
                logger.error(traceback.format_exc())

                # Still notify approval success even if PDF fails
                from telegram import Bot
                bot = Bot(token=query._bot.token)

                is_overday = request.request_type == "overday"
                doc_type = "Overday" if is_overday else "OT"
                date_display = request.od_start_date if is_overday else request.ot_date

                await bot.send_message(
                    chat_id=HR_USER_ID,
                    text=f"📋 *{doc_type} Approved - #{row_id}*\n\n"
                         f"Pegawai: {request.user_name}\n"
                         f"Dept/Section: {request.department}\n"
                         f"Tanggal: {date_display}\n"
                         f"Jam: {request.start_time} - {request.end_time}\n"
                         f"Alasan: {request.reason}\n\n"
                         f"⚠️ PDF generation error, please create manually.",
                    parse_mode="Markdown",
                )

                request_label = "Overday" if is_overday else "Lembur"
                await bot.send_message(
                    chat_id=request.user_id,
                    text=f"✅ *Pengajuan {request_label} #{row_id} Approved*\n\n"
                         f"Selamat! Pengajuan {request_label.lower()} Anda telah disetujui di semua level.\n\n"
                         f"⚠️ Dokumen {doc_type} sedang diproses, "
                         f"mohon hubungi HR untuk DOE.",
                    parse_mode="Markdown",
                )

                status_text = f"✅ *Fully Approved!*\n\nPengajuan #{row_id} telah disetujui di semua level.\n\n⚠️ Generate PDF gagal, dokumen dibuat manual oleh HR."
    else:
        # Rejected
        new_status = RequestStatus.REJECTED
        sheets.update_status(row_id, new_status)
        request.status = new_status

        request_label = "Overday" if request.request_type == "overday" else "Lembur"
        status_text = f"❌ *Rejected* (Level {level})\n\nPengajuan #{row_id} ditolak pada level {level}."

        # Notify user
        from telegram import Bot
        bot = Bot(token=query._bot.token)
        await bot.send_message(
            chat_id=request.user_id,
            text=f"❌ *Pengajuan {request_label} #{row_id} Ditolak*\n\n"
                 f"Maaf, pengajuan {request_label.lower()} Anda ditolak pada level {level}.",
            parse_mode="Markdown",
        )

    try:
        await query.edit_message_text(
            status_text,
            parse_mode="Markdown",
            reply_markup=get_back_to_menu_keyboard(),
        )
    except TelegramError:
        # Message not modified (tombol ditekan ulang) - ignore silently
        pass


async def handle_rejection(query, user_id, data):
    """Handle rejection - same as approval with rejected status"""
    await handle_approval(query, user_id, data, approved=False)


# =============================================================================
# View Request Handlers
# =============================================================================

async def handle_my_requests(query, user_id):
    """Show user's own requests"""
    sheets = get_sheets_service()
    requests = sheets.get_user_requests(user_id)

    if not requests:
        await safe_edit(
            query,
            "📋 *Pengajuan Saya*\n\n"
            "Anda belum memiliki pengajuan lembur.",
            parse_mode="Markdown",
            reply_markup=get_back_to_menu_keyboard(),
        )
        return

    await safe_edit(
        query,
        "📋 *Pengajuan Saya*\n\n"
        f"Total: {len(requests)} pengajuan\n\n"
        "Pilih pengajuan untuk melihat detail:",
        parse_mode="Markdown",
        reply_markup=get_user_request_list_keyboard(requests),
    )


async def handle_view_request(query, user_id, data):
    """View a specific request detail"""
    row_id = int(data.split("_")[-1])

    sheets = get_sheets_service()
    request = sheets.get_request_by_row(row_id)

    if not request:
        await query.edit_message_text(
            "❌ *Data Tidak Ditemukan*",
            parse_mode="Markdown",
        )
        return

    # Check ownership
    if request.user_id != user_id:
        await query.edit_message_text(
            "❌ *Akses Ditolak*\n\n"
            "Anda tidak memiliki akses ke pengajuan ini.",
            parse_mode="Markdown",
        )
        return

    # Use appropriate format for request type
    if request.request_type == "overday":
        msg = format_overday_summary(request)
    else:
        msg = format_request_summary(request)

    # Add approval info if any (name & title taken from config, not hardcoded)
    for level in (1, 2, 3):
        approval = getattr(request, f"approval_{level}")
        if approval:
            status = "✅" if approval.status == ApprovalStatus.APPROVED else "❌"
            approver = APPROVERS.get(f"approval_{level}", {})
            name = approver.get("name", approval.approver_name)
            title = approver.get("title", "")
            msg += f"\n\n✅ Approval {level} ({title} - {name}): {status}"
        else:
            break

    # Kalau pemilik pengajuan ini juga approver di level yang sedang menunggu,
    # tampilkan tombol Setuju/Tolak supaya ia bisa menyetujui pengajuannya sendiri.
    pending_level = request.get_current_approval_level()
    owner_level = None
    if pending_level and is_approver(user_id, pending_level):
        owner_level = pending_level
        msg += (
            f"\n\n🔐 Anda berwenang menyetujui level {pending_level} "
            f"untuk pengajuan ini (approve pengajuan sendiri)."
        )

    try:
        await query.edit_message_text(
            msg,
            parse_mode="Markdown",
            reply_markup=get_request_action_keyboard(
                row_id, bool(request.pdf_url), owner_level
            ),
        )
    except TelegramError:
        # Message not modified (tombol ditekan ulang) - ignore silently
        pass


def build_document_view_text(row_id: int, pdf_url: str) -> str:
    """
    Susun teks untuk tombol "Lihat PDF".

    Dipisah jadi fungsi sendiri supaya bisa diuji tanpa koneksi
    Telegram maupun Google Sheets.
    """
    if pdf_url and not pdf_url.startswith("local:") and pdf_url != PDF_MARKER_TELEGRAM:
        body = f"Link Google Drive:\n{pdf_url}"
    else:
        body = (
            "Dokumen ini dikirim sebagai file terlampir di chat ini "
            "saat pengajuan disetujui.\n\n"
        )
        if pdf_url and pdf_url.startswith("local:"):
            body += f"📁 Arsip di server: {pdf_url[len('local:'):]}"
        else:
            body += (
                "📨 Dokumen dikirim langsung ke chat Telegram "
                "dan tidak disimpan di server.\n"
                "Kalau Anda tidak menemukan lampirannya, "
                "cari pesan pengajuan ini di chat."
            )
    return f"📄 *Dokumen #{row_id}*\n\n" + body


async def handle_view_pdf(query, user_id, data):
    """View PDF link for a request"""
    row_id = int(data.split("_")[-1])

    sheets = get_sheets_service()
    request = sheets.get_request_by_row(row_id)

    if not request or not request.pdf_url:
        await safe_edit(
            query,
            "❌ *PDF Tidak Tersedia*\n\n"
            "PDF belum dibuat atau pengajuan belum selesai di-approve.",
            parse_mode="Markdown",
            reply_markup=get_back_to_menu_keyboard(),
        )
        return

    # Only the request owner and HR may open the document
    is_hr = user_id == HR_USER_ID
    if request.user_id != user_id and not is_hr:
        await safe_edit(
            query,
            "❌ *Akses Ditolak*\n\n"
            "Anda tidak memiliki akses ke dokumen ini.",
            parse_mode="Markdown",
            reply_markup=get_back_to_menu_keyboard(),
        )
        return

    await safe_edit(
        query,
        build_document_view_text(row_id, request.pdf_url),
        parse_mode="Markdown",
        reply_markup=get_back_to_menu_keyboard(),
    )


# =============================================================================
# All Requests (for approvers)
# =============================================================================

async def handle_all_requests(query, user_id):
    """Show all pending requests for approvers"""
    # Check if user is any approver
    approver_level = None
    for level in [1, 2, 3]:
        if is_approver(user_id, level):
            approver_level = level
            break

    if not approver_level:
        await safe_edit(
            query,
            "❌ *Akses Ditolak*\n\n"
            "Anda bukan approver.",
            parse_mode="Markdown",
        )
        return

    sheets = get_sheets_service()
    requests = sheets.get_pending_requests_for_approver(approver_level)

    if not requests:
        await safe_edit(
            query,
            f"📋 *Daftar Approval Level {approver_level}*\n\n"
            "Tidak ada pengajuan yang menunggu approval Anda.",
            parse_mode="Markdown",
            reply_markup=get_back_to_menu_keyboard(),
        )
        return

    await safe_edit(
        query,
        f"📋 *Daftar Approval Level {approver_level}*\n\n"
        f"Total: {len(requests)} pengajuan\n\n"
        "Pilih pengajuan untuk review:",
        parse_mode="Markdown",
        reply_markup=get_approval_list_keyboard(requests, approver_level),
    )


async def handle_back_to_approval_list(query, user_id, data):
    """Go back to approval list"""
    level = int(data.split("_")[-1])
    await handle_all_requests(query, user_id)


# =============================================================================
# Navigation
# =============================================================================

async def handle_back_to_menu(query, user_id):
    """Return to main menu"""
    await safe_edit(
        query,
        "🏠 *Menu Utama*\n\n"
        "Silakan pilih menu:",
        parse_mode="Markdown",
        reply_markup=get_main_menu_keyboard(),
    )