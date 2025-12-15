"""Tests for MessageBody class.

Story 3.9: Refactored to use centralized mock fixtures from conftest.py.
Eliminated 1 duplicate fixture (mock_imap).
"""

from unittest.mock import AsyncMock

import pytest

from mailcore.body import MessageBody


@pytest.fixture
def message_body(mock_imap):
    """Create MessageBody instance for testing.

    Uses centralized mock_imap from conftest.py and overrides return value
    for body-specific tests.
    """
    # Override centralized fixture return value for body tests
    mock_imap.fetch_message_body.return_value = ("plain text content", "<p>html content</p>")
    return MessageBody(imap=mock_imap, folder="INBOX", uid=42)


def test_body_initialization(message_body, mock_imap):
    """Test constructor stores imap, folder, uid correctly."""
    assert message_body._imap is mock_imap
    assert message_body._folder == "INBOX"
    assert message_body._uid == 42
    assert message_body._text is None
    assert message_body._html is None
    assert message_body._fetched is False


@pytest.mark.asyncio
async def test_body_get_text_fetches_from_imap(message_body, mock_imap):
    """Test first get_text() calls imap.fetch_message_body()."""
    text = await message_body.get_text()

    # Verify IMAP was called
    mock_imap.fetch_message_body.assert_called_once_with(folder="INBOX", uid=42)

    # Verify result
    assert text == "plain text content"
    assert message_body._fetched is True
    assert message_body._text == "plain text content"
    assert message_body._html == "<p>html content</p>"


@pytest.mark.asyncio
async def test_body_get_html_fetches_from_imap(message_body, mock_imap):
    """Test first get_html() calls imap.fetch_message_body()."""
    html = await message_body.get_html()

    # Verify IMAP was called
    mock_imap.fetch_message_body.assert_called_once_with(folder="INBOX", uid=42)

    # Verify result
    assert html == "<p>html content</p>"
    assert message_body._fetched is True
    assert message_body._text == "plain text content"
    assert message_body._html == "<p>html content</p>"


@pytest.mark.asyncio
async def test_body_caching_after_first_fetch(message_body, mock_imap):
    """Test second get_text() returns cached, no IMAP call."""
    # First call fetches
    text1 = await message_body.get_text()
    assert text1 == "plain text content"
    assert mock_imap.fetch_message_body.call_count == 1

    # Second call uses cache
    text2 = await message_body.get_text()
    assert text2 == "plain text content"
    assert mock_imap.fetch_message_body.call_count == 1  # Still 1, not called again


@pytest.mark.asyncio
async def test_body_fetch_both_on_first_call(message_body, mock_imap):
    """Test either get_text() or get_html() fetches both and caches."""
    # Call get_text first
    text = await message_body.get_text()
    assert text == "plain text content"
    assert message_body._text == "plain text content"
    assert message_body._html == "<p>html content</p>"
    assert mock_imap.fetch_message_body.call_count == 1

    # Call get_html - should use cached value, no new fetch
    html = await message_body.get_html()
    assert html == "<p>html content</p>"
    assert mock_imap.fetch_message_body.call_count == 1  # Still 1


@pytest.mark.asyncio
async def test_body_handles_none_text(mock_imap):
    """Test handles None plain text gracefully."""
    mock_imap.fetch_message_body = AsyncMock(return_value=(None, "<p>html only</p>"))
    body = MessageBody(imap=mock_imap, folder="INBOX", uid=99)

    text = await body.get_text()
    assert text is None
    assert body._html == "<p>html only</p>"


@pytest.mark.asyncio
async def test_body_handles_none_html(mock_imap):
    """Test handles None HTML gracefully."""
    mock_imap.fetch_message_body = AsyncMock(return_value=("text only", None))
    body = MessageBody(imap=mock_imap, folder="INBOX", uid=99)

    html = await body.get_html()
    assert html is None
    assert body._text == "text only"


def test_body_repr(message_body):
    """Test __repr__ works correctly."""
    # Before fetch
    repr_before = repr(message_body)
    assert "MessageBody(" in repr_before
    assert "folder='INBOX'" in repr_before
    assert "uid=42" in repr_before
    assert "not fetched" in repr_before

    # After fetch (simulate)
    message_body._fetched = True
    repr_after = repr(message_body)
    assert "fetched" in repr_after
    assert "not fetched" not in repr_after
