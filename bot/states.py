"""
Conversation States for OT Request Flow
"""

from enum import Enum


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
# In production, use Redis or database for persistence
_conversation_contexts = {}


def get_conversation_context(user_id: int) -> ConversationContext:
    """Get or create a conversation context for a user"""
    if user_id not in _conversation_contexts:
        _conversation_contexts[user_id] = ConversationContext(user_id)
    return _conversation_contexts[user_id]


def clear_conversation_context(user_id: int):
    """Clear a user's conversation context"""
    if user_id in _conversation_contexts:
        del _conversation_contexts[user_id]