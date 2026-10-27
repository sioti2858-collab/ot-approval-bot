"""
Google Sheets Service
Handles all Google Sheets operations for OT requests
"""

import json
import logging

import gspread
from google.oauth2.service_account import Credentials
from typing import Optional, List, Dict
from datetime import datetime

from config import GOOGLE_SERVICE_ACCOUNT_JSON, GOOGLE_SHEET_ID
from models.ot_request import OTRequest, RequestStatus, ApprovalStatus

logger = logging.getLogger("OTBot")


def _col_letter(idx: int) -> str:
    """Convert a 1-based column index to its spreadsheet letter (1 -> A, 14 -> N)."""
    letters = ""
    while idx > 0:
        idx, remainder = divmod(idx - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


class SheetsService:
    """Service for Google Sheets operations"""

    SCOPES = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    # Header row of the OT Request sheet, in column order.
    # Columns 1-13 are the original layout; 14-15 were added later.
    # Keep the first 13 labels identical to what the live sheet already has,
    # so check_headers() only reports the columns that really need adding.
    HEADERS = [
        "No", "Tanggal Submit", "User ID", "Type", "Nama", "Dept",
        "Tanggal OT", "Jam Mulai", "Jam Selesai", "Total Jam", "Alasan",
        "Status", "Approval History",
        "Tanggal Selesai Overday", "PDF URL",
    ]

    def __init__(self):
        self._client = None
        self._sheet = None
        self._header_checked = False

    def _get_client(self):
        """Initialize Google Sheets client"""
        if self._client is None:
            # Parse service account JSON
            if GOOGLE_SERVICE_ACCOUNT_JSON.endswith(".json"):
                # File path
                creds = Credentials.from_service_account_file(
                    GOOGLE_SERVICE_ACCOUNT_JSON, scopes=self.SCOPES
                )
            else:
                # JSON content
                creds = Credentials.from_service_account_info(
                    json.loads(GOOGLE_SERVICE_ACCOUNT_JSON), scopes=self.SCOPES
                )
            self._client = gspread.authorize(creds)
        return self._client

    def _get_sheet(self):
        """Get the OT requests sheet"""
        if self._sheet is None:
            client = self._get_client()
            spreadsheet = client.open_by_key(GOOGLE_SHEET_ID)
            self._sheet = spreadsheet.sheet1
        return self._sheet

    def check_headers(self):
        """
        Check that the header row contains the columns the app writes to.

        Columns 14-15 ("Tanggal Selesai Overday", "PDF URL") were added after
        the sheet was created. The bot never modifies the shared sheet header
        on its own - it only logs what is missing so an administrator can add
        the labels manually.
        """
        if self._header_checked:
            return

        sheet = self._get_sheet()
        self._header_checked = True

        try:
            current = sheet.row_values(1)
        except Exception:
            return

        missing = [
            (idx, header)
            for idx, header in enumerate(self.HEADERS, start=1)
            if idx > len(current) or current[idx - 1].strip() != header
        ]

        if not missing:
            return

        logger.warning(
            "Header sheet belum lengkap. Tambahkan manual di baris 1: %s",
            "; ".join(f"{_col_letter(idx)}: {header}" for idx, header in missing),
        )

    def get_next_row_id(self) -> int:
        """Get the next available row ID"""
        sheet = self._get_sheet()
        # Find the last used row
        all_values = sheet.get_all_values()
        # All values includes header, so if len=1, next row is 2
        return len(all_values) + 1

    def add_request(self, request: OTRequest) -> int:
        """Add a new OT request to the sheet"""
        sheet = self._get_sheet()
        self.check_headers()
        row_id = self.get_next_row_id()
        request.row_id = row_id

        row_data = request.to_sheet_row()
        sheet.append_row(row_data)
        return row_id

    def update_request(self, row_id: int, request: OTRequest):
        """Update an existing request in the sheet"""
        sheet = self._get_sheet()
        row_data = request.to_sheet_row()

        # Update the specific row (row_id + 1 because of 1-indexed and header)
        row_index = row_id
        for col_idx, value in enumerate(row_data, start=1):
            sheet.update_cell(row_index, col_idx, value)

    def update_status(self, row_id: int, status: RequestStatus, approval_history: str = ""):
        """Update only the status and approval history columns"""
        sheet = self._get_sheet()
        sheet.update_cell(row_id, 12, status.value)
        if approval_history:
            sheet.update_cell(row_id, 13, approval_history)

    def update_pdf_url(self, row_id: int, pdf_url: str):
        """Store the Google Drive link of the generated PDF (column O)."""
        sheet = self._get_sheet()
        sheet.update_cell(row_id, 15, pdf_url)
        logger.info(f"PDF URL stored for row #{row_id}: {pdf_url}")

    def update_approval(
        self,
        row_id: int,
        approval_level: int,
        approver_name: str,
        status: ApprovalStatus,
        timestamp: datetime,
        comment: str = ""
    ):
        """Update approval info for a specific level"""
        sheet = self._get_sheet()

        # Build approval entry - MATCHING FORMAT for parsing
        # Format: "Approval N (Name): ✓/✗ on YYYY-MM-DD HH:MM"
        status_symbol = "✓" if status == ApprovalStatus.APPROVED else "✗"
        approval_entry = f"Approval {approval_level} ({approver_name}): {status_symbol} on {timestamp.strftime('%Y-%m-%d %H:%M')}"
        if comment:
            approval_entry += f" - {comment}"

        # Get current approval history (Column M = index 13)
        current_history = sheet.cell(row_id, 13).value or ""

        # Append new approval
        if current_history:
            new_history = current_history + "\n" + approval_entry
        else:
            new_history = approval_entry

        sheet.update_cell(row_id, 13, new_history)

    def get_request_by_row(self, row_id: int) -> Optional[OTRequest]:
        """Get a request by its row ID"""
        sheet = self._get_sheet()
        try:
            row_data = sheet.row_values(row_id)
            if row_data and len(row_data) >= 10:
                return OTRequest.from_sheet_row(row_id, row_data)
        except Exception:
            return None
        return None

    def get_pending_requests_for_approver(self, approval_level: int) -> List[OTRequest]:
        """Get all requests pending approval for a specific level"""
        sheet = self._get_sheet()
        all_rows = sheet.get_all_values()

        requests = []
        expected_status = {
            1: RequestStatus.SUBMITTED.value,
            2: RequestStatus.PENDING_APPROVAL_1.value,
            3: RequestStatus.PENDING_APPROVAL_2.value,
        }

        # Iterate through all rows (skip header at index 0)
        for idx, row in enumerate(all_rows):
            # Skip header row (idx=0)
            if idx == 0:
                continue
            # row_id is the actual sheet row number (1-indexed)
            row_id = idx + 1
            if len(row) >= 12 and row[11] == expected_status.get(approval_level):
                # Check request type
                request_type = row[3] if len(row) > 3 else "overtime"
                # For overday:
                # - Level 1 sees SUBMITTED requests
                # - Level 2 sees PENDING_APPROVAL_1 requests
                if request_type == "overday":
                    # Overday: level 1 dan level 2
                    if approval_level in [1, 2]:
                        requests.append(OTRequest.from_sheet_row(row_id, row))
                else:
                    # Regular overtime
                    requests.append(OTRequest.from_sheet_row(row_id, row))

        return requests

    def get_user_requests(self, user_id: int) -> List[OTRequest]:
        """Get all requests for a specific user"""
        sheet = self._get_sheet()
        all_rows = sheet.get_all_values()

        requests = []
        for idx, row in enumerate(all_rows):
            if idx == 0:  # Skip header
                continue
            row_id = idx + 1
            if len(row) >= 10 and int(row[2]) == user_id:
                requests.append(OTRequest.from_sheet_row(row_id, row))

        return requests

    def get_all_requests(self) -> List[OTRequest]:
        """Get all OT requests"""
        sheet = self._get_sheet()
        all_rows = sheet.get_all_values()

        requests = []
        for idx, row in enumerate(all_rows):
            if idx == 0:  # Skip header
                continue
            row_id = idx + 1
            if len(row) >= 10:
                requests.append(OTRequest.from_sheet_row(row_id, row))

        return requests


# Singleton instance
_sheets_service = None


def get_sheets_service() -> SheetsService:
    """Get the singleton sheets service instance"""
    global _sheets_service
    if _sheets_service is None:
        _sheets_service = SheetsService()
    return _sheets_service