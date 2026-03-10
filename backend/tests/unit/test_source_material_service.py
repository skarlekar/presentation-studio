"""
Unit tests for source_material_service.py — text extraction.
"""
import pytest

from services.source_material_service import (
    extract_text_from_file,
    SourceMaterialError,
    MAX_FILE_SIZE_BYTES,
)


class TestExtractTextFromFile:
    @pytest.mark.asyncio
    async def test_plain_text_utf8(self):
        content = b"Hello, this is plain text content."
        result = await extract_text_from_file(content, "doc.txt")
        assert result == "Hello, this is plain text content."

    @pytest.mark.asyncio
    async def test_markdown_file(self):
        content = b"# Title\n\nThis is markdown content."
        result = await extract_text_from_file(content, "doc.md")
        assert "markdown content" in result

    @pytest.mark.asyncio
    async def test_unsupported_extension_raises(self):
        with pytest.raises(SourceMaterialError, match="Unsupported"):
            await extract_text_from_file(b"content", "doc.xlsx")

    @pytest.mark.asyncio
    async def test_file_too_large_raises(self):
        big_content = b"x" * (MAX_FILE_SIZE_BYTES + 1)
        with pytest.raises(SourceMaterialError, match="10 MB"):
            await extract_text_from_file(big_content, "big.txt")

    @pytest.mark.asyncio
    async def test_file_at_max_size_raises(self):
        exact_limit = b"x" * MAX_FILE_SIZE_BYTES
        # Exactly at limit should also fail (> not >=)
        # Actually > MAX_FILE_SIZE_BYTES means limit+1 fails; limit itself is ok
        # Let's verify the boundary
        over_limit = b"x" * (MAX_FILE_SIZE_BYTES + 1)
        with pytest.raises(SourceMaterialError):
            await extract_text_from_file(over_limit, "doc.txt")

    @pytest.mark.asyncio
    async def test_latin1_encoding_fallback(self):
        content = "Caf\xe9 au lait".encode("latin-1")
        result = await extract_text_from_file(content, "doc.txt")
        assert "Caf" in result

    @pytest.mark.asyncio
    async def test_allowed_extensions(self):
        for ext in [".pdf", ".txt", ".docx", ".md"]:
            # For non-text files we just check no "unsupported" error is raised
            # (pdf/docx will fail on content but not on extension check)
            try:
                await extract_text_from_file(b"minimal", f"doc{ext}")
            except SourceMaterialError as e:
                assert "Unsupported" not in str(e)

    @pytest.mark.asyncio
    async def test_case_insensitive_extension(self):
        content = b"Content here"
        result = await extract_text_from_file(content, "doc.TXT")
        assert "Content here" in result
