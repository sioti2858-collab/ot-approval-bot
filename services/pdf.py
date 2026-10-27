"""
PDF Generation Service
Creates OT Form PDF documents with approval signatures
"""

import io
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm, mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from typing import Optional, List
from datetime import datetime

from config import COMPANY_NAME, APPROVERS, LOGO_PATH
from models.ot_request import OTRequest, ApprovalInfo, ApprovalStatus


def _logo_text() -> str:
    """Inisial singkat dari COMPANY_NAME, dipakai kalau file logo tidak ada."""
    initials = "".join(
        word[0] for word in COMPANY_NAME.split() if word and word[0].isalpha()
    )
    return initials[:3].upper() or "LOGO"


class PDFService:
    """Service for generating OT Form PDF documents"""

    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_styles()

    def _setup_styles(self):
        """Setup custom styles for the PDF"""
        self.styles.add(
            ParagraphStyle(
                name="Title_Custom",
                parent=self.styles["Heading1"],
                fontSize=12,
                alignment=1,  # Center
                spaceAfter=2,
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="SubTitle",
                parent=self.styles["Normal"],
                fontSize=10,
                alignment=1,
                spaceAfter=2,
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="SectionHeader",
                parent=self.styles["Heading2"],
                fontSize=10,
                spaceAfter=3,
                spaceBefore=5,
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="Normal_Small",
                parent=self.styles["Normal"],
                fontSize=9,
                spaceAfter=2,
            )
        )

    def generate_ot_form(self, request: OTRequest) -> bytes:
        """
        Generate an OT Form PDF - Single page, portrait layout with logo at top left

        Args:
            request: OTRequest object with all data

        Returns:
            PDF content as bytes
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=1.5*cm,
            leftMargin=1.5*cm,
            topMargin=1*cm,
            bottomMargin=1*cm,
        )

        # Build PDF content
        elements = []

        # Header with Logo (left) and Company Info (right) - TOP LEFT POSITION
        logo_path = LOGO_PATH
        try:
            if os.path.exists(logo_path):
                logo_img = Image(logo_path, width=2.5*cm, height=2.5*cm)
            else:
                logo_img = Paragraph(f"<b>{_logo_text()}</b>", ParagraphStyle(name="LogoText", fontSize=18, fontName="Helvetica-Bold", textColor=colors.HexColor("#003366")))
        except:
            logo_img = Paragraph(f"<b>{_logo_text()}</b>", ParagraphStyle(name="LogoText", fontSize=18, fontName="Helvetica-Bold", textColor=colors.HexColor("#003366")))

        # Header row: Logo | Company Name & Form Title
        header_table = Table(
            [[logo_img, Paragraph(f"<b>{COMPANY_NAME}</b><br/><font size=10>FORM OVERTIME</font>", ParagraphStyle(name="HeaderRight", fontSize=14, fontName="Helvetica-Bold", alignment=0, leading=18))]],
            colWidths=[3*cm, 15.5*cm],
        )
        header_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (0, 0), "LEFT"),
            ("ALIGN", (1, 0), (1, 0), "LEFT"),
            ("LINEBELOW", (0, 0), (-1, 0), 1, colors.HexColor("#003366")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
        ]))
        elements.append(header_table)
        elements.append(Spacer(1, 8*mm))

        # Document Number
        doc_number = f"OT-{request.row_id:04d}-{datetime.now().strftime('%Y%m%d')}"
        elements.append(Paragraph(f"<b>No: {doc_number}</b>", self.styles["Normal_Small"]))
        elements.append(Spacer(1, 6*mm))

        # Data Karyawan Section
        elements.append(Paragraph("DATA KARYAWAN", self.styles["SectionHeader"]))
        employee_data = [
            ["Nama", ":", request.user_name],
            ["Dept/Section", ":", request.department],
            ["Tanggal Pengajuan", ":", request.submitted_at.strftime("%d-%m-%Y %H:%M")],
        ]
        emp_table = Table(employee_data, colWidths=[4*cm, 1*cm, 13*cm])
        emp_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        elements.append(emp_table)
        elements.append(Spacer(1, 5*mm))

        # Detail Lembur Section
        elements.append(Paragraph("DETAIL LEMBUR", self.styles["SectionHeader"]))
        total_hours = request._calculate_total_hours()
        ot_data = [
            ["Tanggal Lembur", ":", request.ot_date],
            ["Jam", ":", f"{request.start_time} - {request.end_time}"],
            ["Total Jam", ":", total_hours],
            ["Alasan", ":", request.reason],
        ]
        ot_table = Table(ot_data, colWidths=[4*cm, 1*cm, 13*cm])
        ot_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        elements.append(ot_table)
        elements.append(Spacer(1, 6*mm))

        # Persetujuan Section
        elements.append(Paragraph("PERSETUJUAN", self.styles["SectionHeader"]))
        elements.append(self._create_approval_section(request))
        elements.append(Spacer(1, 8*mm))

        # Tanda Tangan Section
        elements.append(self._create_signature_section(request))

        # Footer
        elements.append(Spacer(1, 5*mm))
        elements.append(Paragraph(
            f"Dokumen ini dibuat secara elektronik pada {datetime.now().strftime('%d-%m-%Y %H:%M')}",
            ParagraphStyle(name="Footer", fontSize=7, alignment=1, textColor=colors.grey)
        ))

        # Build PDF
        doc.build(elements)
        buffer.seek(0)
        return buffer.read()

    def _create_table(self, data: List[List[str]], col_widths: List[float]) -> Table:
        """Create a simple table with data"""
        table = Table(data, colWidths=col_widths)
        table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TEXTCOLOR", (0, 0), (0, -1), colors.black),
            ("ALIGN", (0, 0), (0, -1), "LEFT"),
            ("ALIGN", (1, 0), (1, -1), "LEFT"),
            ("ALIGN", (2, 0), (2, -1), "LEFT"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        return table

    def _create_approval_section(self, request: OTRequest) -> Table:
        """Create approval status table - WITHOUT E-Sign column"""
        approval_data = [
            ["Level", "Nama", "Jabatan", "Status", "Tanggal"]
        ]

        # Real approver info from config
        approver_info = {
            1: {
                "name": APPROVERS.get("approval_1", {}).get("name", "Approver 1"),
                "title": APPROVERS.get("approval_1", {}).get("title", "Engineer EIC & IT"),
            },
            2: {
                "name": APPROVERS.get("approval_2", {}).get("name", "Approver 2"),
                "title": APPROVERS.get("approval_2", {}).get("title", "Section Head EIC & IT"),
            },
            3: {
                "name": APPROVERS.get("approval_3", {}).get("name", "Approver 3"),
                "title": APPROVERS.get("approval_3", {}).get("title", "Manager Maintenance"),
            },
        }

        request_approvals = {
            1: request.approval_1,
            2: request.approval_2,
            3: request.approval_3,
        }

        for level in [1, 2, 3]:
            info = approver_info[level]
            approval = request_approvals[level]

            if approval and approval.status == ApprovalStatus.APPROVED:
                status_text = "DISETUJUI"
                date_text = approval.timestamp.strftime("%d-%m-%Y %H:%M") if approval.timestamp else "-"
            else:
                status_text = "MENUNGGU"
                date_text = "-"

            approval_data.append([
                str(level),
                info["name"],
                info["title"],
                status_text,
                date_text,
            ])

        table = Table(
            approval_data,
            colWidths=[1.2*cm, 4.5*cm, 3.5*cm, 2.2*cm, 3.5*cm],
            rowHeights=[0.5*cm] + [0.55*cm] * 3,
        )
        table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#003366")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
            ("FONTNAME", (0, 1), (2, -1), "Helvetica-Bold"),
        ]))
        return table

    def _esign_image(self, request: OTRequest, level: int):
        """
        Return the e-signature image of an approver, but only when that
        approver has actually approved the request. Approvers who have not
        approved yet get an empty slot, so the document never shows the
        signature of someone who did not sign it.
        """
        approval = getattr(request, f"approval_{level}", None)
        if not approval or approval.status != ApprovalStatus.APPROVED:
            return ""

        esign = APPROVERS.get(f"approval_{level}", {}).get("esign", "")
        if not esign or not os.path.exists(esign):
            return ""

        try:
            return Image(esign, width=1.5*cm, height=0.7*cm)
        except:
            return ""

    def _create_signature_section(self, request: OTRequest) -> Table:
        """Create signature section - compact version"""
        # Get approver names from config
        diajukan_oleh = APPROVERS.get("approval_1", {}).get("name", "Approver 1")
        diketaui_oleh = APPROVERS.get("approval_2", {}).get("name", "Approver 2")
        disetujui_oleh = APPROVERS.get("approval_3", {}).get("name", "Approver 3")

        sig_data = [
            ["Diajukan oleh:", "Diketahui oleh:", "Disetujui oleh:"],
        ]

        # E-sign images - only for approvers who have actually approved
        img1 = self._esign_image(request, 1)
        img2 = self._esign_image(request, 2)
        img3 = self._esign_image(request, 3)

        sig_data.append([img1, img2, img3])
        sig_data.append([diajukan_oleh, diketaui_oleh, disetujui_oleh])
        sig_data.append([
            APPROVERS.get("approval_1", {}).get("title", "Engineer EIC & IT"),
            APPROVERS.get("approval_2", {}).get("title", "Section Head EIC & IT"),
            APPROVERS.get("approval_3", {}).get("title", "Manager Maintenance"),
        ])

        table = Table(
            sig_data,
            colWidths=[6.3*cm, 6.3*cm, 6.3*cm],
            rowHeights=[0.4*cm, 0.9*cm, 0.4*cm, 0.3*cm],
        )
        table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        return table

    def generate_overday_form(self, request: OTRequest) -> bytes:
        """
        Generate an Overday Form PDF - Single page, portrait layout with logo at top left

        Args:
            request: OTRequest object with all data

        Returns:
            PDF content as bytes
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=1.5*cm,
            leftMargin=1.5*cm,
            topMargin=1*cm,
            bottomMargin=1*cm,
        )

        # Build PDF content
        elements = []

        # Header with Logo (left) and Company Info (right) - TOP LEFT POSITION
        logo_path = LOGO_PATH
        try:
            if os.path.exists(logo_path):
                logo_img = Image(logo_path, width=2.5*cm, height=2.5*cm)
            else:
                logo_img = Paragraph(f"<b>{_logo_text()}</b>", ParagraphStyle(name="LogoText", fontSize=18, fontName="Helvetica-Bold", textColor=colors.HexColor("#003366")))
        except:
            logo_img = Paragraph(f"<b>{_logo_text()}</b>", ParagraphStyle(name="LogoText", fontSize=18, fontName="Helvetica-Bold", textColor=colors.HexColor("#003366")))

        # Header row: Logo | Company Name & Form Title
        header_table = Table(
            [[logo_img, Paragraph(f"<b>{COMPANY_NAME}</b><br/><font size=10>FORM OVERDAY</font>", ParagraphStyle(name="HeaderRight", fontSize=14, fontName="Helvetica-Bold", alignment=0, leading=18))]],
            colWidths=[3*cm, 15.5*cm],
        )
        header_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (0, 0), "LEFT"),
            ("ALIGN", (1, 0), (1, 0), "LEFT"),
            ("LINEBELOW", (0, 0), (-1, 0), 1, colors.HexColor("#003366")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
        ]))
        elements.append(header_table)
        elements.append(Spacer(1, 8*mm))

        # Document Number
        doc_number = f"OD-{request.row_id:04d}-{datetime.now().strftime('%Y%m%d')}"
        elements.append(Paragraph(f"<b>No: {doc_number}</b>", self.styles["Normal_Small"]))
        elements.append(Spacer(1, 6*mm))

        # Data Karyawan Section
        elements.append(Paragraph("DATA KARYAWAN", self.styles["SectionHeader"]))
        employee_data = [
            ["Nama", ":", request.user_name],
            ["Dept/Section", ":", request.department],
            ["Tanggal Pengajuan", ":", request.submitted_at.strftime("%d-%m-%Y %H:%M")],
        ]
        emp_table = Table(employee_data, colWidths=[4*cm, 1*cm, 13*cm])
        emp_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        elements.append(emp_table)
        elements.append(Spacer(1, 5*mm))

        # Detail Overday Section
        elements.append(Paragraph("DETAIL OVERDAY", self.styles["SectionHeader"]))
        total_hours = request._calculate_total_hours()

        # Format date range
        if request.od_end_date and request.od_end_date != request.od_start_date:
            date_range = f"{request.od_start_date} - {request.od_end_date}"
        else:
            date_range = request.od_start_date

        od_data = [
            ["Tanggal Overday", ":", date_range],
            ["Jam", ":", f"{request.start_time} - {request.end_time}"],
            ["Total Jam", ":", total_hours],
            ["Alasan", ":", request.reason],
        ]
        od_table = Table(od_data, colWidths=[4*cm, 1*cm, 13*cm])
        od_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        elements.append(od_table)
        elements.append(Spacer(1, 6*mm))

        # Persetujuan Section - Overday only has 2 levels
        elements.append(Paragraph("PERSETUJUAN", self.styles["SectionHeader"]))
        elements.append(self._create_overday_approval_section(request))
        elements.append(Spacer(1, 8*mm))

        # Tanda Tangan Section - Overday only has 2 approvers
        elements.append(self._create_overday_signature_section(request))

        # Footer
        elements.append(Spacer(1, 5*mm))
        elements.append(Paragraph(
            f"Dokumen ini dibuat secara elektronik pada {datetime.now().strftime('%d-%m-%Y %H:%M')}",
            ParagraphStyle(name="Footer", fontSize=7, alignment=1, textColor=colors.grey)
        ))

        # Build PDF
        doc.build(elements)
        buffer.seek(0)
        return buffer.read()

    def _create_overday_approval_section(self, request: OTRequest) -> Table:
        """Create approval status table for Overday - only 2 levels"""
        approval_data = [
            ["Level", "Nama", "Jabatan", "Status", "Tanggal"]
        ]

        # Overday approver info (level 1 dan level 2)
        approver_info = {
            1: {
                "name": APPROVERS.get("approval_1", {}).get("name", "Approver 1"),
                "title": APPROVERS.get("approval_1", {}).get("title", "Engineer EIC & IT"),
            },
            2: {
                "name": APPROVERS.get("approval_2", {}).get("name", "Approver 2"),
                "title": APPROVERS.get("approval_2", {}).get("title", "Section Head EIC & IT"),
            },
        }

        request_approvals = {
            1: request.approval_1,
            2: request.approval_2,
        }

        for level in [1, 2]:
            info = approver_info[level]
            approval = request_approvals[level]

            if approval and approval.status == ApprovalStatus.APPROVED:
                status_text = "DISETUJUI"
                date_text = approval.timestamp.strftime("%d-%m-%Y %H:%M") if approval.timestamp else "-"
            else:
                status_text = "MENUNGGU"
                date_text = "-"

            approval_data.append([
                str(level),
                info["name"],
                info["title"],
                status_text,
                date_text,
            ])

        table = Table(
            approval_data,
            colWidths=[1.2*cm, 4.5*cm, 3.5*cm, 2.2*cm, 3.5*cm],
            rowHeights=[0.5*cm] + [0.55*cm] * 2,
        )
        table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#003366")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
            ("FONTNAME", (0, 1), (2, -1), "Helvetica-Bold"),
        ]))
        return table

    def _create_overday_signature_section(self, request: OTRequest) -> Table:
        """Create signature section for Overday - only 2 approvers"""
        diajukan_oleh = APPROVERS.get("approval_1", {}).get("name", "Approver 1")
        disetujui_oleh = APPROVERS.get("approval_2", {}).get("name", "Approver 2")

        sig_data = [
            ["Diajukan oleh:", "Diketahui oleh:"],
        ]

        # E-sign images - only for approvers who have actually approved
        img1 = self._esign_image(request, 1)
        img2 = self._esign_image(request, 2)

        sig_data.append([img1, img2])
        sig_data.append([diajukan_oleh, disetujui_oleh])
        sig_data.append([
            APPROVERS.get("approval_1", {}).get("title", "Engineer EIC & IT"),
            APPROVERS.get("approval_2", {}).get("title", "Section Head EIC & IT"),
        ])

        table = Table(
            sig_data,
            colWidths=[9.5*cm, 9.5*cm],
            rowHeights=[0.4*cm, 0.9*cm, 0.4*cm, 0.3*cm],
        )
        table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        return table



# Singleton instance
_pdf_service = None


def get_pdf_service() -> PDFService:
    """Get the singleton PDF service instance"""
    global _pdf_service
    if _pdf_service is None:
        _pdf_service = PDFService()
    return _pdf_service
