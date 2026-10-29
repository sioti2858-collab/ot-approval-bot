"""
Conversation States for OT Request Flow
"""

import logging
from enum import Enum

logger = logging.getLogger("OTBot")


class ConversationState(Enum):
    """States for the OT request conversation"""
    # Main menu states
    IDLE = "idle"

    # New request flow states
    AWAITING_NAME = "awaiting_name"
    AWAITING_DEPARTMENT = "awaiting_department"
    AWAITING_OT_DATE = "awaiting_ot_date"
    AWAITING_START_TIME = "awaiting_start_time"
    AWAITING_END_TIME = "awaiting_end_time"
    AWAITING_REASON = "awaiting_reason"
    CONFIRM_REQUEST = "confirm_request"

    # Overday request flow states
    AWAITING_OD_NAME = "awaiting_od_name"
    AWAITING_OD_DEPARTMENT = "awaiting_od_department"
    AWAITING_OD_START_DATE = "awaiting_od_start_date"
    AWAITING_OD_START_TIME = "awaiting_od_start_time"
    AWAITING_OD_END_TIME = "awaiting_od_end_time"
    AWAITING_OD_REASON = "awaiting_od_reason"
    CONFIRM_OVERDAY = "confirm_overday"

    # Admin states
    VIEW_APPROVAL = "view_approval"
    ENTER_REJECTION_REASON = "enter_rejection_reason"


class ConversationContext:
    """Context for ongoing conversation"""

    def __init__(self, user_id: int):
        self.user_id = user_id
        self.state = ConversationState.IDLE
        self.data = {}

    def reset(self):
        """Reset the conversation context"""
        self.state = ConversationState.IDLE
        self.data = {}

    def set_data(self, key: str, value):
        """Set data in the context"""
        self.data[key] = value

    def get_data(self, key: str, default=None):
        """Get data from the context"""
        return self.data.get(key, default)


# In-memory storage for conversation contexts
# Cache cepat. Kalau persistensi aktif (STATE_PERSISTENCE_ENABLED),
# state juga ditulis ke tab Google Sheets supaya tidak hilang saat
# proses bot restart.
_conversation_contexts = {}

# Backend persistensi (opsional). Di-set dari main.py saat start.
_state_store = None


def set_state_store(store):
    """Aktifkan persistensi state (backend mis. services.state_store)."""
    global _state_store
    _state_store = store


def get_state_store():
    """Backend persistensi aktif, atau None kalau tidak diaktifkan."""
    return _state_store


def _hydrate(user_id: int, context: ConversationContext) -> ConversationContext:
    """Isi context dari backend persistensi kalau ada."""
    if _state_store is None:
        return context

    try:
        saved = _state_store.load(user_id)
    except Exception as error:
        logger.warning(f"Gagal memuat state user {user_id}: {error}")
        return context

    if not saved:
        return context

    try:
        context.state = ConversationState(saved["state"])
        context.data = saved.get("data") or {}
        logger.info(
            f"State user {user_id} dipulihkan dari persistensi: {saved['state']}"
        )
    except Exception as error:
        logger.warning(f"State user {user_id} tidak bisa dipulihkan: {error}")

    return context


def get_conversation_context(user_id: int) -> ConversationContext:
    """Get or create a conversation context for a user"""
    if user_id not in _conversation_contexts:
        context = ConversationContext(user_id)
        _conversation_contexts[user_id] = _hydrate(user_id, context)
    return _conversation_contexts[user_id]


def persist_conversation_context(user_id: int):
    """
    Simpan state user ke backend persistensi.

    Dipanggil setelah setiap input user, supaya state terakhir selalu
    tersimpan - penting kalau proses bot bisa restart kapan saja.
    """
    context = _conversation_contexts.get(user_id)
    if context is None or _state_store is None:
        return
    try:
        _state_store.save(user_id, context.state.value, context.data)
    except Exception as error:
        logger.warning(f"Gagal persist state user {user_id}: {error}")


def clear_conversation_context(user_id: int):
    """Clear a user's conversation context"""
    if user_id in _conversation_contexts:
        del _conversation_contexts[user_id]
    if _state_store is not None:
        try:
            _state_store.delete(user_id)
        except Exception as error:
            logger.warning(f"Gagal hapus state user {user_id}: {error}")