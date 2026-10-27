"""
Telegram Bot Keyboard Definitions
Inline keyboards for the bot
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Main menu keyboard"""
    keyboard = [
        [InlineKeyboardButton("📝 Ajukan Lembur", callback_data="menu_new_request")],
        [InlineKeyboardButton("📅 Ajukan Overday", callback_data="menu_new_overday")],
        [InlineKeyboardButton("📋 Status Pengajuan Saya", callback_data="menu_my_requests")],
        [InlineKeyboardButton("📊 Daftar Pengajuan", callback_data="menu_all_requests")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_approval_keyboard(row_id: int, approval_level: int) -> InlineKeyboardMarkup:
    """Approval action keyboard for approvers"""
    keyboard = [
        [
            InlineKeyboardButton("✅ Setuju", callback_data=f"approve_{approval_level}_{row_id}"),
            InlineKeyboardButton("❌ Tolak", callback_data=f"reject_{approval_level}_{row_id}"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_confirmation_keyboard(action: str) -> InlineKeyboardMarkup:
    """Confirmation keyboard for user actions"""
    keyboard = [
        [InlineKeyboardButton("✅ Ya, Konfirmasi", callback_data=f"confirm_{action}")],
        [InlineKeyboardButton("❌ Batal", callback_data=f"cancel_{action}")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_cancel_only_keyboard() -> InlineKeyboardMarkup:
    """Cancel only keyboard for initial steps"""
    keyboard = [
        [InlineKeyboardButton("❌ Batal", callback_data="cancel_cancel_request")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_back_to_menu_keyboard() -> InlineKeyboardMarkup:
    """Back to menu keyboard"""
    keyboard = [
        [InlineKeyboardButton("🔙 Kembali ke Menu", callback_data="back_to_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_approval_list_keyboard(requests: list, approval_level: int) -> InlineKeyboardMarkup:
    """List of pending approvals for approver"""
    keyboard = []
    for req in requests[:10]:  # Limit to 10 items
        # Use appropriate date field based on request type
        display_date = req.od_start_date if req.request_type == "overday" else req.ot_date
        keyboard.append([
            InlineKeyboardButton(
                f"#{req.row_id} - {req.user_name} ({display_date})",
                callback_data=f"view_approval_{approval_level}_{req.row_id}"
            )
        ])
    keyboard.append([InlineKeyboardButton("🔙 Kembali ke Menu", callback_data="back_to_menu")])
    return InlineKeyboardMarkup(keyboard)


def get_request_detail_keyboard(
    row_id: int,
    approval_level: int,
    current_status: str
) -> InlineKeyboardMarkup:
    """Request detail keyboard for approver"""
    keyboard = []

    # Only show approval buttons if it's pending for this level
    if current_status in ["submitted", "pending_approval_1", "pending_approval_2"]:
        keyboard.append([
            InlineKeyboardButton("✅ Setuju", callback_data=f"approve_{approval_level}_{row_id}"),
            InlineKeyboardButton("❌ Tolak", callback_data=f"reject_{approval_level}_{row_id}"),
        ])

    keyboard.append([InlineKeyboardButton("🔙 Kembali", callback_data=f"back_to_approval_list_{approval_level}")])
    return InlineKeyboardMarkup(keyboard)


def get_user_request_list_keyboard(requests: list) -> InlineKeyboardMarkup:
    """List of user's requests"""
    keyboard = []
    for req in requests[:10]:
        status_emoji = {
            "draft": "📝",
            "submitted": "📤",
            "pending_approval_1": "⏳",
            "pending_approval_2": "⏳",
            "pending_approval_3": "⏳",
            "approved": "✅",
            "rejected": "❌",
        }
        emoji = status_emoji.get(req.status.value, "❓")
        # Use appropriate date field based on request type
        display_date = req.od_start_date if req.request_type == "overday" else req.ot_date
        keyboard.append([
            InlineKeyboardButton(
                f"{emoji} #{req.row_id} - {display_date} ({req.status.value.replace('_', ' ').title()})",
                callback_data=f"view_request_{req.row_id}"
            )
        ])
    keyboard.append([InlineKeyboardButton("🔙 Kembali ke Menu", callback_data="back_to_menu")])
    return InlineKeyboardMarkup(keyboard)


def get_request_action_keyboard(
    row_id: int,
    has_pdf: bool = False,
    approval_level: int = None,
) -> InlineKeyboardMarkup:
    """
    Action keyboard for viewing a specific request.

    approval_level diisi kalau pemilik pengajuan ini sekaligus berwenang
    menyetujui di level tersebut (approver yang mengajukan pengajuannya
    sendiri). Tombol Setuju/Tolak baru muncul di level itu.
    """
    keyboard = []
    if approval_level is not None:
        keyboard.append([
            InlineKeyboardButton("✅ Setuju", callback_data=f"approve_{approval_level}_{row_id}"),
            InlineKeyboardButton("❌ Tolak", callback_data=f"reject_{approval_level}_{row_id}"),
        ])
    if has_pdf:
        keyboard.append([
            InlineKeyboardButton("📄 Lihat Dokumen", callback_data=f"view_pdf_{row_id}")
        ])
    keyboard.append([InlineKeyboardButton("🔙 Kembali", callback_data="back_to_my_requests")])
    return InlineKeyboardMarkup(keyboard)