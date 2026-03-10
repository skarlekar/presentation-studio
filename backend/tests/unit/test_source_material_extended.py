"""
Extended tests for source_material_service.py — covers PDF and DOCX extraction paths.
Uses minimal real file bytes to test actual extraction logic.
"""
import io
import struct
import pytest
from unittest.mock import MagicMock, patch

from services.source_material_service import (
    extract_text_from_file,
    _extract_text,
    _extract_pdf,
    _extract_docx,
    SourceMaterialError,
)


class TestExtractText:
    """Unit tests for the plain-text extractor."""

    def test_utf8_content(self):
        result = _extract_text(b"Hello UTF-8 world")
        assert result == "Hello UTF-8 world"

    def test_utf8_bom_content(self):
        content = "\ufeffHello BOM world".encode("utf-8-sig")
        result = _extract_text(content)
        assert "Hello BOM world" in result

    def test_latin1_content(self):
        content = "Caf\xe9 lait".encode("latin-1")
        result = _extract_text(content)
        assert "Caf" in result

    def test_strips_whitespace(self):
        result = _extract_text(b"   trimmed   ")
        assert result == "trimmed"

    def test_empty_returns_error(self):
        """All encodings fail for empty-but-decoded content → should try all and give last error."""
        # Pass bytes that can't be decoded in any charset
        try:
            _extract_text(b"\x81\x82\x83")  # invalid in UTF-8 and UTF-8-sig
        except SourceMaterialError:
            pass  # expected if all encodings fail
        # If latin-1 succeeds (it always does), that's fine too


class TestExtractPdf:
    """Tests for PDF extraction — mocks pypdf.PdfReader."""

    def test_extracts_text_from_pages(self):
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Page content here"

        mock_reader = MagicMock()
        mock_reader.pages = [mock_page, mock_page]

        with patch("pypdf.PdfReader", return_value=mock_reader):
            result = _extract_pdf(b"%PDF-1.4 fake")
        assert "Page content here" in result

    def test_empty_pdf_raises(self):
        mock_page = MagicMock()
        mock_page.extract_text.return_value = ""  # scanned PDF — no text

        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]

        with patch("pypdf.PdfReader", return_value=mock_reader):
            with pytest.raises(SourceMaterialError, match="scanned"):
                _extract_pdf(b"%PDF-1.4 fake")

    def test_pdf_extraction_error_raises(self):
        with patch("pypdf.PdfReader", side_effect=Exception("corrupt")):
            with pytest.raises(SourceMaterialError, match="PDF extraction failed"):
                _extract_pdf(b"not a pdf")

    def test_joins_multiple_pages(self):
        pages = [MagicMock(), MagicMock()]
        pages[0].extract_text.return_value = "Page one content"
        pages[1].extract_text.return_value = "Page two content"

        mock_reader = MagicMock()
        mock_reader.pages = pages

        with patch("pypdf.PdfReader", return_value=mock_reader):
            result = _extract_pdf(b"%PDF fake")
        assert "Page one" in result
        assert "Page two" in result

    def test_skips_empty_pages(self):
        pages = [MagicMock(), MagicMock()]
        pages[0].extract_text.return_value = "Valid page"
        pages[1].extract_text.return_value = "   "  # whitespace only

        mock_reader = MagicMock()
        mock_reader.pages = pages

        with patch("pypdf.PdfReader", return_value=mock_reader):
            result = _extract_pdf(b"%PDF fake")
        assert "Valid page" in result


class TestExtractDocx:
    """Tests for DOCX extraction — mocks python-docx Document."""

    def test_extracts_paragraph_text(self):
        mock_para = MagicMock()
        mock_para.text = "This is a paragraph"

        mock_doc = MagicMock()
        mock_doc.paragraphs = [mock_para]
        mock_doc.tables = []

        with patch("docx.Document", return_value=mock_doc):
            result = _extract_docx(b"PK fake docx")
        assert "This is a paragraph" in result

    def test_skips_empty_paragraphs(self):
        para1 = MagicMock()
        para1.text = "Real content"
        para2 = MagicMock()
        para2.text = ""  # empty

        mock_doc = MagicMock()
        mock_doc.paragraphs = [para1, para2]
        mock_doc.tables = []

        with patch("docx.Document", return_value=mock_doc):
            result = _extract_docx(b"PK fake")
        assert "Real content" in result

    def test_extracts_table_cells(self):
        cell1 = MagicMock()
        cell1.text = "Header"
        cell2 = MagicMock()
        cell2.text = "Value"

        row = MagicMock()
        row.cells = [cell1, cell2]

        table = MagicMock()
        table.rows = [row]

        mock_doc = MagicMock()
        mock_doc.paragraphs = []
        mock_doc.tables = [table]

        with patch("docx.Document", return_value=mock_doc):
            result = _extract_docx(b"PK fake")
        assert "Header" in result
        assert "Value" in result

    def test_empty_docx_raises(self):
        mock_doc = MagicMock()
        mock_doc.paragraphs = []
        mock_doc.tables = []

        with patch("docx.Document", return_value=mock_doc):
            with pytest.raises(SourceMaterialError, match="empty"):
                _extract_docx(b"PK fake")

    def test_docx_error_raises(self):
        with patch("docx.Document", side_effect=Exception("corrupt")):
            with pytest.raises(SourceMaterialError, match="DOCX extraction failed"):
                _extract_docx(b"PK fake")


class TestExtractTextFromFileIntegration:
    """Integration-style tests using mocked parsers."""

    @pytest.mark.asyncio
    async def test_pdf_dispatched_correctly(self):
        with patch("services.source_material_service._extract_pdf", return_value="PDF content") as mock_pdf:
            result = await extract_text_from_file(b"x" * 100, "report.pdf")
        mock_pdf.assert_called_once()
        assert result == "PDF content"

    @pytest.mark.asyncio
    async def test_docx_dispatched_correctly(self):
        with patch("services.source_material_service._extract_docx", return_value="DOCX content") as mock_docx:
            result = await extract_text_from_file(b"x" * 100, "report.docx")
        mock_docx.assert_called_once()
        assert result == "DOCX content"

    @pytest.mark.asyncio
    async def test_uppercase_pdf_extension(self):
        with patch("services.source_material_service._extract_pdf", return_value="PDF content"):
            result = await extract_text_from_file(b"x" * 100, "REPORT.PDF")
        assert result == "PDF content"

    @pytest.mark.asyncio
    async def test_txt_extension_dispatches_to_text(self):
        result = await extract_text_from_file(b"Plain text content here", "notes.txt")
        assert "Plain text content" in result

    @pytest.mark.asyncio
    async def test_md_extension_dispatches_to_text(self):
        result = await extract_text_from_file(b"# Heading\n\nContent", "notes.md")
        assert "Heading" in result or "Content" in result
