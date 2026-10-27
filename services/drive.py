"""
Google Drive Service
Handles file uploads to Google Drive
"""

import json
import io
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from typing import Optional

from config import GOOGLE_SERVICE_ACCOUNT_JSON, GOOGLE_DRIVE_FOLDER_ID, DRIVE_SHARE_MODE


class DriveService:
    """Service for Google Drive operations"""

    SCOPES = ["https://www.googleapis.com/auth/drive.file"]

    def __init__(self):
        self._service = None

    def _get_service(self):
        """Initialize Google Drive service"""
        if self._service is None:
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
            self._service = build("drive", "v3", credentials=creds)
        return self._service

    def upload_pdf(
        self,
        pdf_content: bytes,
        file_name: str,
        folder_id: Optional[str] = None
    ) -> str:
        """
        Upload a PDF file to Google Drive

        Sharing follows DRIVE_SHARE_MODE (see config.py):

          "link"       -> role "reader" for "anyone with the link": the document
                          can be viewed and downloaded, but NOT edited, and it is
                          not discoverable through Drive search.
          "restricted" -> no permission is added; access stays limited to the
                          members of the destination folder.

        Args:
            pdf_content: The PDF file content as bytes
            file_name: Name for the file in Drive
            folder_id: Optional folder ID (uses default if not provided)

        Returns:
            The webViewLink of the uploaded file
        """
        service = self._get_service()

        # Prepare file metadata
        file_metadata = {
            "name": file_name,
            "mimeType": "application/pdf",
        }

        # Add parent folder if specified
        target_folder = folder_id or GOOGLE_DRIVE_FOLDER_ID
        if target_folder:
            file_metadata["parents"] = [target_folder]

        # Create media upload object
        media = MediaIoBaseUpload(
            io.BytesIO(pdf_content),
            mimetype="application/pdf",
            resumable=True,
        )

        # Upload the file
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id, webViewLink",
        ).execute()

        # NOTE: the PDF holds personal data (name, department, overtime hours,
        # reason), so it is shared as READ ONLY - "anyone with the link" may
        # view and download it, but nobody can edit it. "allowFileDiscovery":
        # False keeps the file out of Drive search results, so the link is the
        # only way in.
        if DRIVE_SHARE_MODE == "link":
            service.permissions().create(
                fileId=file.get("id"),
                body={
                    "type": "anyone",
                    "role": "reader",
                    "allowFileDiscovery": False,
                },
            ).execute()

        return file.get("webViewLink")

    def get_file_link(self, file_id: str) -> str:
        """Get the web view link for a file"""
        service = self._get_service()
        file = service.files().get(
            fileId=file_id,
            fields="webViewLink",
        ).execute()
        return file.get("webViewLink")

    def create_folder(self, folder_name: str, parent_id: Optional[str] = None) -> str:
        """Create a new folder in Google Drive"""
        service = self._get_service()

        folder_metadata = {
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder",
        }

        if parent_id:
            folder_metadata["parents"] = [parent_id]

        folder = service.files().create(
            body=folder_metadata,
            fields="id",
        ).execute()

        return folder.get("id")


# Singleton instance
_drive_service = None


def get_drive_service() -> DriveService:
    """Get the singleton drive service instance"""
    global _drive_service
    if _drive_service is None:
        _drive_service = DriveService()
    return _drive_service