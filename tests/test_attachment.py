"""Tests for Attachment and resolver classes."""

import base64
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from mailcore.attachment import Attachment, AttachmentResolver, IMAPResolver, SimpleResolver

# --- Attachment Tests ---


def test_attachment_initialization() -> None:
    """Constructor stores all parameters correctly."""
    resolver = SimpleResolver()
    att = Attachment(
        uri="imap://INBOX/42/part/2",
        filename="report.pdf",
        size=102400,
        content_type="application/pdf",
        is_inline=False,
        content_id="logo@example.com",
        _resolver=resolver,
        _content=b"cached",
    )

    assert att.uri == "imap://INBOX/42/part/2"
    assert att.filename == "report.pdf"
    assert att.size == 102400
    assert att.content_type == "application/pdf"
    assert att.is_inline is False
    assert att.content_id == "logo@example.com"
    assert att._resolver is resolver
    assert att._content == b"cached"


def test_attachment_metadata_properties() -> None:
    """All properties return correct values without network calls."""
    att = Attachment(
        uri="file:///home/user/file.txt",
        filename="file.txt",
        size=1024,
        content_type="text/plain",
        is_inline=True,
        content_id="cid123",
    )

    # Access all properties (no network calls)
    assert att.uri == "file:///home/user/file.txt"
    assert att.filename == "file.txt"
    assert att.size == 1024
    assert att.content_type == "text/plain"
    assert att.is_inline is True
    assert att.content_id == "cid123"


def test_from_file_creates_file_uri(tmp_path: Path) -> None:
    """from_file() creates file:// URI with absolute path."""
    # Create temporary file
    test_file = tmp_path / "report.pdf"
    test_file.write_bytes(b"PDF content")

    att = Attachment.from_file(test_file)

    assert att.uri == f"file://{test_file.resolve()}"
    assert att.filename == "report.pdf"
    assert att.size == 11
    assert att.content_type == "application/pdf"
    assert isinstance(att._resolver, SimpleResolver)


def test_from_file_raises_if_not_exists() -> None:
    """from_file() raises FileNotFoundError for missing file."""
    with pytest.raises(FileNotFoundError, match="File not found"):
        Attachment.from_file("/nonexistent/file.pdf")


def test_from_file_raises_if_directory(tmp_path: Path) -> None:
    """from_file() raises ValueError for directories."""
    with pytest.raises(ValueError, match="Path is not a file"):
        Attachment.from_file(tmp_path)


def test_from_url_creates_https_uri() -> None:
    """from_url() creates https:// URI."""
    att = Attachment.from_url("https://example.com/chart.png")

    assert att.uri == "https://example.com/chart.png"
    assert att.filename == "chart.png"
    assert isinstance(att._resolver, SimpleResolver)


def test_from_url_extracts_filename() -> None:
    """from_url() extracts filename from URL path."""
    att = Attachment.from_url("https://example.com/path/to/file.pdf")

    assert att.filename == "file.pdf"


def test_from_url_uses_custom_filename() -> None:
    """from_url() uses custom filename if provided."""
    att = Attachment.from_url("https://example.com/file", filename="custom.txt")

    assert att.filename == "custom.txt"


def test_from_url_raises_on_invalid_scheme() -> None:
    """from_url() raises ValueError for invalid URL scheme."""
    with pytest.raises(ValueError, match="Invalid URL scheme"):
        Attachment.from_url("ftp://example.com/file.pdf")


def test_from_bytes_creates_data_uri() -> None:
    """from_bytes() creates data: URI with base64 encoding."""
    content = b"Hello World"
    att = Attachment.from_bytes(content, "hello.txt", "text/plain")

    assert att.uri.startswith("data:text/plain;base64,")
    assert att.filename == "hello.txt"
    assert att.size == 11
    assert att.content_type == "text/plain"


def test_from_bytes_precaches_content() -> None:
    """from_bytes() pre-populates _content field."""
    content = b"Test content"
    att = Attachment.from_bytes(content, "test.txt", "text/plain")

    assert att._content == content


@pytest.mark.asyncio
async def test_read_fetches_content_via_resolver() -> None:
    """read() calls resolver.resolve() on first call."""
    # Create mock resolver
    mock_resolver = AsyncMock(spec=AttachmentResolver)
    mock_resolver.resolve = AsyncMock(return_value=b"fetched content")

    att = Attachment(
        uri="imap://INBOX/42/part/2",
        filename="file.pdf",
        _resolver=mock_resolver,
    )

    content = await att.read()

    assert content == b"fetched content"
    mock_resolver.resolve.assert_awaited_once_with("imap://INBOX/42/part/2")


@pytest.mark.asyncio
async def test_read_caches_content_after_first_fetch() -> None:
    """Second read() returns cached _content without refetch."""
    # Create mock resolver
    mock_resolver = AsyncMock(spec=AttachmentResolver)
    mock_resolver.resolve = AsyncMock(return_value=b"fetched content")

    att = Attachment(
        uri="imap://INBOX/42/part/2",
        filename="file.pdf",
        _resolver=mock_resolver,
    )

    # First call fetches
    content1 = await att.read()
    assert content1 == b"fetched content"
    assert mock_resolver.resolve.await_count == 1

    # Second call returns cached (no refetch)
    content2 = await att.read()
    assert content2 == b"fetched content"
    assert mock_resolver.resolve.await_count == 1  # Still 1 (not called again)


@pytest.mark.asyncio
async def test_read_raises_if_no_resolver() -> None:
    """read() raises ValueError if no resolver available."""
    att = Attachment(
        uri="imap://INBOX/42/part/2",
        filename="file.pdf",
        _resolver=None,  # No resolver
    )

    with pytest.raises(ValueError, match="No resolver available"):
        await att.read()


@pytest.mark.asyncio
async def test_data_uri_content_precached() -> None:
    """Attachment created with data: URI has _content pre-populated."""
    content = b"Pre-cached content"
    att = Attachment.from_bytes(content, "file.txt", "text/plain")

    # read() returns pre-cached content without calling resolver
    fetched = await att.read()
    assert fetched == content


@pytest.mark.asyncio
async def test_save_downloads_and_writes_to_disk(tmp_path: Path) -> None:
    """save() fetches content and writes to Path."""
    # Create mock resolver
    mock_resolver = AsyncMock(spec=AttachmentResolver)
    mock_resolver.resolve = AsyncMock(return_value=b"file content")

    att = Attachment(
        uri="imap://INBOX/42/part/2",
        filename="report.pdf",
        _resolver=mock_resolver,
    )

    # Save to specific file
    save_path = tmp_path / "output.pdf"
    result = await att.save(save_path)

    assert result == save_path
    assert save_path.exists()
    assert save_path.read_bytes() == b"file content"


@pytest.mark.asyncio
async def test_save_to_current_directory(tmp_path: Path, monkeypatch: Any) -> None:
    """save(path=None) uses current dir + filename."""
    # Change to tmp_path
    monkeypatch.chdir(tmp_path)

    att = Attachment.from_bytes(b"content", "file.txt", "text/plain")

    result = await att.save()

    assert result == tmp_path / "file.txt"
    assert result.exists()


@pytest.mark.asyncio
async def test_save_to_directory(tmp_path: Path) -> None:
    """save() appends filename if path is directory."""
    att = Attachment.from_bytes(b"content", "report.pdf", "application/pdf")

    result = await att.save(tmp_path)

    assert result == tmp_path / "report.pdf"
    assert result.exists()


@pytest.mark.asyncio
async def test_save_raises_if_exists_no_overwrite(tmp_path: Path) -> None:
    """save() raises FileExistsError if file exists and overwrite=False."""
    # Create existing file
    existing = tmp_path / "existing.txt"
    existing.write_bytes(b"old content")

    att = Attachment.from_bytes(b"new content", "file.txt", "text/plain")

    with pytest.raises(FileExistsError, match="File already exists"):
        await att.save(existing, overwrite=False)


@pytest.mark.asyncio
async def test_save_overwrites_if_flag_set(tmp_path: Path) -> None:
    """save() overwrites existing file if overwrite=True."""
    # Create existing file
    existing = tmp_path / "existing.txt"
    existing.write_bytes(b"old content")

    att = Attachment.from_bytes(b"new content", "file.txt", "text/plain")

    result = await att.save(existing, overwrite=True)

    assert result.read_bytes() == b"new content"


def test_attachment_repr() -> None:
    """__repr__ returns developer-friendly representation."""
    att = Attachment(
        uri="imap://INBOX/42/part/2",
        filename="report.pdf",
        size=102400,
        content_type="application/pdf",
        is_inline=False,
    )

    repr_str = repr(att)

    assert "Attachment(" in repr_str
    assert "filename='report.pdf'" in repr_str
    assert "size=102400" in repr_str
    assert "content_type='application/pdf'" in repr_str
    assert "is_inline=False" in repr_str


# --- IMAPResolver Tests ---


@pytest.mark.asyncio
async def test_imap_resolver_parses_uri_and_fetches() -> None:
    """IMAPResolver parses imap:// URI and calls fetch_attachment_content()."""
    # Create mock IMAP connection
    mock_imap = MagicMock()
    mock_imap.fetch_attachment_content = AsyncMock(return_value=b"attachment content")

    resolver = IMAPResolver(mock_imap)
    content = await resolver.resolve("imap://INBOX/42/part/2")

    assert content == b"attachment content"
    mock_imap.fetch_attachment_content.assert_awaited_once_with("INBOX", 42, "2")


@pytest.mark.asyncio
async def test_imap_resolver_handles_nested_parts() -> None:
    """IMAPResolver handles nested part indices like '1.1'."""
    mock_imap = MagicMock()
    mock_imap.fetch_attachment_content = AsyncMock(return_value=b"nested content")

    resolver = IMAPResolver(mock_imap)
    content = await resolver.resolve("imap://INBOX/100/part/1.1")

    assert content == b"nested content"
    mock_imap.fetch_attachment_content.assert_awaited_once_with("INBOX", 100, "1.1")


@pytest.mark.asyncio
async def test_imap_resolver_raises_on_invalid_uri() -> None:
    """IMAPResolver raises ValueError for invalid URI format."""
    mock_imap = MagicMock()
    resolver = IMAPResolver(mock_imap)

    # Invalid scheme
    with pytest.raises(ValueError, match="Invalid IMAP URI scheme"):
        await resolver.resolve("https://example.com/file")

    # Missing 'part' component
    with pytest.raises(ValueError, match="Invalid IMAP URI format"):
        await resolver.resolve("imap://INBOX/42/2")

    # Invalid UID
    with pytest.raises(ValueError, match="Invalid UID"):
        await resolver.resolve("imap://INBOX/notanumber/part/2")


# --- SimpleResolver Tests ---


@pytest.mark.asyncio
async def test_simple_resolver_handles_file_uri(tmp_path: Path) -> None:
    """SimpleResolver reads file:// URIs from filesystem."""
    # Create test file
    test_file = tmp_path / "test.txt"
    test_file.write_bytes(b"file content")

    resolver = SimpleResolver()
    content = await resolver.resolve(f"file://{test_file}")

    assert content == b"file content"


@pytest.mark.asyncio
async def test_simple_resolver_raises_if_file_not_found() -> None:
    """SimpleResolver raises FileNotFoundError for missing file."""
    resolver = SimpleResolver()

    with pytest.raises(FileNotFoundError, match="File not found"):
        await resolver.resolve("file:///nonexistent/file.txt")


@pytest.mark.asyncio
async def test_simple_resolver_handles_data_uri() -> None:
    """SimpleResolver base64 decodes data: URIs."""
    # Create data URI
    content = b"Hello World"
    encoded = base64.b64encode(content).decode("ascii")
    uri = f"data:text/plain;base64,{encoded}"

    resolver = SimpleResolver()
    decoded = await resolver.resolve(uri)

    assert decoded == content


@pytest.mark.asyncio
async def test_simple_resolver_raises_on_invalid_data_uri() -> None:
    """SimpleResolver raises ValueError for invalid data URI format."""
    resolver = SimpleResolver()

    # Missing comma
    with pytest.raises(ValueError, match="Invalid data URI format"):
        await resolver.resolve("data:text/plain;base64")

    # Missing base64 encoding
    with pytest.raises(ValueError, match="Unsupported data URI encoding"):
        await resolver.resolve("data:text/plain,content")


@pytest.mark.asyncio
async def test_simple_resolver_http_not_implemented() -> None:
    """SimpleResolver raises NotImplementedError for https:// URIs."""
    resolver = SimpleResolver()

    with pytest.raises(NotImplementedError, match="HTTP fetch not implemented"):
        await resolver.resolve("https://example.com/file.pdf")

    with pytest.raises(NotImplementedError, match="HTTP fetch not implemented"):
        await resolver.resolve("http://example.com/file.pdf")


@pytest.mark.asyncio
async def test_simple_resolver_raises_on_unsupported_scheme() -> None:
    """SimpleResolver raises ValueError for unknown URI schemes."""
    resolver = SimpleResolver()

    with pytest.raises(ValueError, match="Unsupported URI scheme"):
        await resolver.resolve("ftp://example.com/file.pdf")
