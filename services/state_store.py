"""
Conversation State Store

Menyimpan state percakapan (form pengajuan yang sedang diisi) ke tab
Google Sheets, supaya tidak hilang saat proses bot restart.

Kapan ini perlu:
  - Bot jalan sebagai GitHub Actions (runner restart tiap ~6 jam)
  - Bot jalan di container cloud (restart saat redeploy)

Semua operasi di sini bersifat "best effort": kalau Sheets tidak bisa
daccessed, bot tetap jalan dengan state in-memory seperti biasa. State
hanya boleh jadi pelengkap, bukan syarat.

Format tab (satu baris per user):
    A = user_id
    B = state (nama enum ConversationState)
    C = updated_at (ISO 8601)
    D = data (JSON)
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import gspread
from google.oauth2.service_account import Credentials

from config import (
    GOOGLE_SERVICE_ACCOUNT_JSON,
    GOOGLE_SHEET_ID,
    STATE_TAB_NAME,
    STATE_TTL_HOURS,
)

logger = logging.getLogger("OTBot")

# Kolom di tab state
COL_USER_ID = 0
COL_STATE = 1
COL_UPDATED = 2
COL_DATA = 3

HEADER_ROW = ["user_id", "state", "updated_at", "data"]


class StateStore:
    """Simpan & muat state percakapan lewat Google Sheets."""

    SCOPES = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    def __init__(self, tab_name: str = STATE_TAB_NAME):
        self._tab_name = tab_name
        self._client = None
        self._sheet = None
        # Cache baris: user_id -> nomor baris (1-indexed di sheet)
        self._index = {}

    # ------------------------------------------------------------------
    # Koneksi
    # ------------------------------------------------------------------

    def _get_sheet(self):
        """Buka spreadsheet + tab state, buat tabnya kalau belum ada."""
        if self._sheet is not None:
            return self._sheet

        if GOOGLE_SERVICE_ACCOUNT_JSON.endswith(".json"):
            creds = Credentials.from_service_account_file(
                GOOGLE_SERVICE_ACCOUNT_JSON, scopes=self.SCOPES
            )
        else:
            creds = Credentials.from_service_account_info(
                json.loads(GOOGLE_SERVICE_ACCOUNT_JSON), scopes=self.SCOPES
            )

        self._client = gspread.authorize(creds)
        spreadsheet = self._client.open_by_key(GOOGLE_SHEET_ID)

        try:
            sheet = spreadsheet.worksheet(self._tab_name)
        except Exception:
            # Tab belum ada -> buat.
            logger.info(f"Creating state tab '{self._tab_name}'")
            sheet = spreadsheet.add_worksheet(
                title=self._tab_name, rows=1000, cols=len(HEADER_ROW)
            )
            sheet.update([HEADER_ROW], "A1:D1")

        self._sheet = sheet
        self._index = {}
        return sheet

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def _find_row(self, user_id: int) -> Optional[int]:
        """Nomor baris (1-indexed) milik user_id, atau None."""
        sheet = self._get_sheet()
        try:
            cell = sheet.find(f"{user_id}", in_column=COL_USER_ID + 1)
            return cell.row
        except Exception:
            return None

    def _next_row(self) -> int:
        """Baris kosong berikutnya di bawah data yang ada."""
        sheet = self._get_sheet()
        try:
            count = sheet.row_count
        except Exception:
            count = 1000
        # baris 1 = header
        return max(count, 2)

    # ------------------------------------------------------------------
    # API publik
    # ------------------------------------------------------------------

    def load(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Ambil state user dari tab.

        Return dict {"state": str, "data": dict} atau None kalau tidak ada
        / kedaluwarsa / gagal dibaca.
        """
        try:
            row = self._find_row(user_id)
            if not row:
                return None

            sheet = self._get_sheet()
            values = sheet.row_values(row)

            state = values[COL_STATE] if len(values) > COL_STATE else ""
            updated_raw = values[COL_UPDATED] if len(values) > COL_UPDATED else ""
            data_raw = values[COL_DATA] if len(values) > COL_DATA else ""

            if not state:
                return None

            # Cek masa berlaku
            if updated_raw and STATE_TTL_HOURS > 0:
                try:
                    updated = datetime.fromisoformat(updated_raw)
                    if updated.tzinfo is None:
                        updated = updated.replace(tzinfo=timezone.utc)
                    if datetime.now(timezone.utc) - updated > timedelta(hours=STATE_TTL_HOURS):
                        logger.info(
                            f"State user {user_id} kedaluwarsa "
                            f"(>{STATE_TTL_HOURS} jam), dibuang"
                        )
                        self.delete(user_id)
                        return None
                except ValueError:
                    pass  # format tanggal aneh -> tetap pakai datanya

            data = {}
            if data_raw:
                try:
                    data = json.loads(data_raw)
                except json.JSONDecodeError:
                    logger.warning(f"Data state user {user_id} tidak bisa dibaca, diabaikan")
                    data = {}

            return {"state": state, "data": data}

        except Exception as error:
            logger.warning(f"Gagal memuat state user {user_id}: {error}")
            return None

    def save(self, user_id: int, state: str, data: Dict[str, Any]):
        """Simpan state user ke tab (update kalau sudah ada)."""
        try:
            sheet = self._get_sheet()
            payload = json.dumps(data, ensure_ascii=False)
            updated = datetime.now(timezone.utc).isoformat()

            row = self._find_row(user_id)
            if row:
                sheet.update(
                    [[str(user_id), state, updated, payload]],
                    f"A{row}:D{row}",
                )
            else:
                sheet.append_row([str(user_id), state, updated, payload])
                self._index.pop(user_id, None)

            logger.info(f"State user {user_id} disimpan: {state}")

        except Exception as error:
            logger.warning(f"Gagal menyimpan state user {user_id}: {error}")

    def delete(self, user_id: int):
        """Hapus state user (misal setelah pengajuan selesai)."""
        try:
            row = self._find_row(user_id)
            if not row:
                return
            sheet = self._get_sheet()
            sheet.update_cells([[""]], f"A{row}:D{row}")
            logger.info(f"State user {user_id} dihapus")
        except Exception as error:
            logger.warning(f"Gagal menghapus state user {user_id}: {error}")
