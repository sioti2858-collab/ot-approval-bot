"""
OT Request Model
Represents an overtime request submission
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, List
from enum import Enum


class ApprovalStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class RequestStatus(Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    PENDING_APPROVAL_1 = "pending_approval_1"
    PENDING_APPROVAL_2 = "pending_approval_2"
    PENDING_APPROVAL_3 = "pending_approval_3"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass
class ApprovalInfo:
    """Information about an approval action"""
    approver_name: str
    status: ApprovalStatus
    timestamp: Optional[datetime] = None
    comment: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "approver_name": self.approver_name,
            "status": self.status.value,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "comment": self.comment,
        }


@dataclass
class OTRequest:
    """Overtime request data model"""
    row_id: int  # Row number in Google Sheet
    user_id: int  # Telegram user ID
    user_name: str  # User's name
    department: str  # Department

    # Request type: "overtime" or "overday"
    request_type: str = "overtime"

    # OT Details
    ot_date: str = ""  # Date of overtime (YYYY-MM-DD)
    start_time: str = ""  # Start time (HH:MM)
    end_time: str = ""  # End time (HH:MM)
    reason: str = ""  # Reason for overtime

    # Overday Details
    od_start_date: str = ""  # Tanggal overday (YYYY-MM-DD)
    od_end_date: str = ""  # Sama dengan od_start_date (isi kolom N di sheet)

    # Metadata
    submitted_at: datetime = field(default_factory=datetime.now)
    status: RequestStatus = RequestStatus.DRAFT

    # Approval tracking
    approval_1: Optional[ApprovalInfo] = None
    approval_2: Optional[ApprovalInfo] = None
    approval_3: Optional[ApprovalInfo] = None

    # PDF tracking
    pdf_url: Optional[str] = None

    def get_current_approval_level(self) -> Optional[int]:
        """Returns the current approval level that needs action"""
        if self.request_type == "overday":
            # Overday only has 2 approval levels
            if self.status == RequestStatus.SUBMITTED:
                return 1
            elif self.status == RequestStatus.PENDING_APPROVAL_1:
                return 2
            return None
        else:
            # Overtime has 3 approval levels
            if self.status == RequestStatus.SUBMITTED:
                return 1
            elif self.status == RequestStatus.PENDING_APPROVAL_1:
                return 2
            elif self.status == RequestStatus.PENDING_APPROVAL_2:
                return 3
            return None

    def get_next_status(self, approval_level: int) -> RequestStatus:
        """Returns the next status after approval"""
        if self.request_type == "overday":
            # Overday only has 2 levels
            status_map = {
                1: RequestStatus.PENDING_APPROVAL_1,
                2: RequestStatus.APPROVED,
            }
        else:
            # Overtime has 3 levels
            status_map = {
                1: RequestStatus.PENDING_APPROVAL_1,
                2: RequestStatus.PENDING_APPROVAL_2,
                3: RequestStatus.APPROVED,
            }
        return status_map.get(approval_level, self.status)

    def to_sheet_row(self) -> List:
        """Convert to row data for Google Sheet"""
        approval_history = self._build_approval_history()
        total_hours = self._calculate_total_hours()
        return [
            self.row_id,
            self.submitted_at.strftime("%Y-%m-%d %H:%M"),
            str(self.user_id),
            self.request_type,
            self.user_name,
            self.department,
            self.ot_date or self.od_start_date,
            self.start_time,
            self.end_time,
            total_hours,
            self.reason,
            self.status.value,
            approval_history,
            self.od_end_date or "",
            self.pdf_url or "",
        ]

    def _calculate_total_hours(self) -> str:
        """Calculate total hours from start_time and end_time"""
        try:
            start = datetime.strptime(self.start_time, "%H:%M")
            end = datetime.strptime(self.end_time, "%H:%M")
            diff = end - start
            # Handle overnight shifts (end time is next day)
            if diff.total_seconds() < 0:
                from datetime import timedelta
                diff = diff + timedelta(days=1)
            total_minutes = int(diff.total_seconds() // 60)

            # Overday spans multiple days: daily duration x number of days
            num_days = 1
            if self.request_type == "overday" and self.od_start_date and self.od_end_date:
                start_date = datetime.strptime(self.od_start_date, "%Y-%m-%d").date()
                end_date = datetime.strptime(self.od_end_date, "%Y-%m-%d").date()
                num_days = max((end_date - start_date).days + 1, 1)

            total_minutes *= num_days
            hours, minutes = divmod(total_minutes, 60)
            if num_days > 1:
                return f"{hours} jam {minutes} menit ({num_days} hari)"
            return f"{hours} jam {minutes} menit"
        except:
            return "-"

    def _build_approval_history(self) -> str:
        """Build approval history string"""
        history = []
        for i, approval in enumerate([self.approval_1, self.approval_2, self.approval_3], 1):
            if approval and approval.timestamp:
                status_symbol = "✓" if approval.status == ApprovalStatus.APPROVED else "✗"
                history.append(
                    f"Approval {i} ({approval.approver_name}): {status_symbol} "
                    f"on {approval.timestamp.strftime('%Y-%m-%d %H:%M')}"
                )
        return "\n".join(history) if history else ""

    @classmethod
    def from_sheet_row(cls, row_id: int, row_data: List) -> "OTRequest":
        """Create OTRequest from Google Sheet row data"""
        # Column order: No, Tanggal Submit, User ID, Type, Nama, Dept, Tanggal OT,
        # Jam Mulai, Jam Selesai, Total Jam, Alasan, Status, Approval History,
        # Tanggal Selesai Overday, PDF URL
        request_type = row_data[3] if len(row_data) > 3 and row_data[3] in ["overtime", "overday"] else "overtime"

        request = cls(
            row_id=row_id,
            user_id=int(row_data[2]),
            user_name=row_data[4],
            department=row_data[5],
            request_type=request_type,
            ot_date=row_data[6] if request_type == "overtime" else "",
            od_start_date=row_data[6] if request_type == "overday" else "",
            od_end_date=row_data[13] if len(row_data) > 13 and row_data[13] else "",
            start_time=row_data[7],
            end_time=row_data[8],
            reason=row_data[10] if len(row_data) > 10 else "",
            status=RequestStatus(row_data[11]) if len(row_data) > 11 and row_data[11] in [s.value for s in RequestStatus] else RequestStatus.SUBMITTED,
            pdf_url=row_data[14] if len(row_data) > 14 and row_data[14] else None,
        )
        # Overday end date defaults to start date when the sheet has no value yet
        if request.request_type == "overday" and not request.od_end_date:
            request.od_end_date = request.od_start_date
        # Parse approval history
        if len(row_data) > 12 and row_data[12]:
            request._parse_approval_history(row_data[12])
        return request

    def _parse_approval_history(self, history: str):
        """Parse approval history string back to ApprovalInfo objects"""
        if not history:
            return

        import re
        from dateutil import parser as date_parser

        # Pattern: "Approval N (Name): ✓/✗ on YYYY-MM-DD HH:MM"
        # Example: "Approval 1 (Manager): ✓ on 2024-06-15 14:30"
        pattern = r"Approval (\d) \(([^)]+)\): (✓|✗) on (.+)"

        matches = re.findall(pattern, history)
        for match in matches:
            level = int(match[0])
            name = match[1]
            status_symbol = match[2]
            timestamp_str = match[3].strip()

            # Parse timestamp
            try:
                timestamp = date_parser.parse(timestamp_str)
            except:
                timestamp = None

            # Determine status
            status = ApprovalStatus.APPROVED if status_symbol == "✓" else ApprovalStatus.REJECTED

            # Create ApprovalInfo
            approval = ApprovalInfo(
                approver_name=name,
                status=status,
                timestamp=timestamp,
            )

            # Set to appropriate level
            if level == 1:
                self.approval_1 = approval
            elif level == 2:
                self.approval_2 = approval
            elif level == 3:
                self.approval_3 = approval

    def to_pdf_data(self) -> Dict:
        """Get data for PDF generation"""
        return {
            "user_name": self.user_name,
            "department": self.department,
            "ot_date": self.ot_date,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "reason": self.reason,
            "submitted_at": self.submitted_at.strftime("%Y-%m-%d %H:%M"),
            "approval_1": self.approval_1,
            "approval_2": self.approval_2,
            "approval_3": self.approval_3,
        }