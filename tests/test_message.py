"""Tests for Message class."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock

import pytest

from mailcore.body import MessageBody
from mailcore.message import Message
from mailcore.types import EmailAddress, MessageFlag


@pytest.fixture
def mock_imap():
    """Create mock IMAP connection."""
    mock = Mock()
    mock.fetch_message_body = AsyncMock(return_value=("text body", "<p>html body</p>"))
    mock.update_message_flags = AsyncMock(return_value=({MessageFlag.SEEN}, set()))
    mock.move_message = AsyncMock(return_value=43)
    mock.copy_message = AsyncMock(return_value=44)
    mock.delete_message = AsyncMock()
    return mock


@pytest.fixture
def sample_message(mock_imap):
    """Create sample message for testing."""
    return Message(
        imap=mock_imap,
        uid=42,
        folder="INBOX",
        message_id="<msg-123@example.com>",
        from_=EmailAddress("alice@example.com", "Alice Smith"),
        to=[EmailAddress("bob@example.com", "Bob Jones")],
        cc=[EmailAddress("charlie@example.com")],
        subject="Test Subject",
        date=datetime(2025, 12, 15, 10, 30, tzinfo=timezone.utc),
        flags=["\\Seen", "\\Flagged"],
        size=1024,
        in_reply_to="<prev-msg@example.com>",
        references=["<ref1@example.com>", "<ref2@example.com>"],
    )


def test_message_initialization(sample_message, mock_imap):
    """Test message constructor stores all parameters correctly."""
    assert sample_message._imap is mock_imap
    assert sample_message._uid == 42
    assert sample_message._folder == "INBOX"
    assert sample_message._message_id == "<msg-123@example.com>"
    assert sample_message._from.email == "alice@example.com"
    assert len(sample_message._to) == 1
    assert sample_message._to[0].email == "bob@example.com"
    assert len(sample_message._cc) == 1
    assert sample_message._subject == "Test Subject"
    assert sample_message._flags == ["\\Seen", "\\Flagged"]
    assert sample_message._size == 1024
    assert sample_message._in_reply_to == "<prev-msg@example.com>"
    assert sample_message._references == ["<ref1@example.com>", "<ref2@example.com>"]
    assert sample_message._smtp is None
    assert sample_message._body is None


def test_message_metadata_properties(sample_message):
    """Test all metadata properties return correct values (no network)."""
    assert sample_message.uid == 42
    assert sample_message.folder == "INBOX"
    assert sample_message.message_id == "<msg-123@example.com>"
    assert sample_message.from_.email == "alice@example.com"
    assert sample_message.from_.name == "Alice Smith"
    assert len(sample_message.to) == 1
    assert sample_message.to[0].email == "bob@example.com"
    assert len(sample_message.cc) == 1
    assert sample_message.cc[0].email == "charlie@example.com"
    assert sample_message.subject == "Test Subject"
    assert sample_message.date == datetime(2025, 12, 15, 10, 30, tzinfo=timezone.utc)
    assert sample_message.flags == ["\\Seen", "\\Flagged"]
    assert sample_message.size == 1024
    assert sample_message.in_reply_to == "<prev-msg@example.com>"
    assert sample_message.references == ["<ref1@example.com>", "<ref2@example.com>"]


def test_message_is_reply_computed(mock_imap):
    """Test is_reply computed from in_reply_to field."""
    # Message with in_reply_to
    reply_msg = Message(
        imap=mock_imap,
        uid=1,
        folder="INBOX",
        message_id="<msg1@example.com>",
        from_=EmailAddress("alice@example.com"),
        to=[EmailAddress("bob@example.com")],
        cc=[],
        subject="Re: Test",
        date=datetime.now(timezone.utc),
        flags=[],
        size=100,
        in_reply_to="<original@example.com>",
    )
    assert reply_msg.is_reply is True

    # Message without in_reply_to
    new_msg = Message(
        imap=mock_imap,
        uid=2,
        folder="INBOX",
        message_id="<msg2@example.com>",
        from_=EmailAddress("alice@example.com"),
        to=[EmailAddress("bob@example.com")],
        cc=[],
        subject="New Thread",
        date=datetime.now(timezone.utc),
        flags=[],
        size=100,
    )
    assert new_msg.is_reply is False


def test_message_body_lazy_creation(sample_message):
    """Test body property creates MessageBody on first access."""
    # Body not created yet
    assert sample_message._body is None

    # First access creates MessageBody
    body = sample_message.body
    assert isinstance(body, MessageBody)
    assert sample_message._body is body

    # Second access returns same instance
    body2 = sample_message.body
    assert body2 is body


def test_message_smtp_injection(sample_message):
    """Test _smtp field can be set and accessed."""
    mock_smtp = Mock()

    # Initially None
    assert sample_message._smtp is None

    # Inject SMTP
    sample_message._smtp = mock_smtp
    assert sample_message._smtp is mock_smtp


@pytest.mark.asyncio
async def test_message_mark_read(sample_message, mock_imap):
    """Test mark_read calls IMAP correctly."""
    await sample_message.mark_read()

    mock_imap.update_message_flags.assert_called_once_with(folder="INBOX", uid=42, add_flags={MessageFlag.SEEN})


@pytest.mark.asyncio
async def test_message_mark_unread(sample_message, mock_imap):
    """Test mark_unread calls IMAP correctly."""
    await sample_message.mark_unread()

    mock_imap.update_message_flags.assert_called_once_with(folder="INBOX", uid=42, remove_flags={MessageFlag.SEEN})


@pytest.mark.asyncio
async def test_message_mark_flagged(sample_message, mock_imap):
    """Test mark_flagged calls IMAP correctly."""
    await sample_message.mark_flagged()

    mock_imap.update_message_flags.assert_called_once_with(folder="INBOX", uid=42, add_flags={MessageFlag.FLAGGED})


@pytest.mark.asyncio
async def test_message_mark_unflagged(sample_message, mock_imap):
    """Test mark_unflagged calls IMAP correctly."""
    await sample_message.mark_unflagged()

    mock_imap.update_message_flags.assert_called_once_with(folder="INBOX", uid=42, remove_flags={MessageFlag.FLAGGED})


@pytest.mark.asyncio
async def test_message_mark_answered(sample_message, mock_imap):
    """Test mark_answered calls IMAP correctly."""
    await sample_message.mark_answered()

    mock_imap.update_message_flags.assert_called_once_with(folder="INBOX", uid=42, add_flags={MessageFlag.ANSWERED})


@pytest.mark.asyncio
async def test_message_move_to(sample_message, mock_imap):
    """Test move_to calls IMAP correctly."""
    await sample_message.move_to("Archive")

    mock_imap.move_message.assert_called_once_with(uid=42, from_folder="INBOX", to_folder="Archive")


@pytest.mark.asyncio
async def test_message_copy_to(sample_message, mock_imap):
    """Test copy_to calls IMAP correctly."""
    await sample_message.copy_to("Archive")

    mock_imap.copy_message.assert_called_once_with(uid=42, from_folder="INBOX", to_folder="Archive")


@pytest.mark.asyncio
async def test_message_delete_to_trash(sample_message, mock_imap):
    """Test delete(permanent=False) calls IMAP correctly."""
    await sample_message.delete(permanent=False)

    mock_imap.delete_message.assert_called_once_with(folder="INBOX", uid=42, permanent=False)


@pytest.mark.asyncio
async def test_message_delete_permanent(sample_message, mock_imap):
    """Test delete(permanent=True) calls IMAP correctly."""
    await sample_message.delete(permanent=True)

    mock_imap.delete_message.assert_called_once_with(folder="INBOX", uid=42, permanent=True)


@pytest.mark.asyncio
async def test_message_mark_deleted(sample_message, mock_imap):
    """Test mark_deleted calls IMAP correctly."""
    await sample_message.mark_deleted()

    mock_imap.update_message_flags.assert_called_once_with(folder="INBOX", uid=42, add_flags={MessageFlag.DELETED})


def test_message_reply_not_implemented(sample_message):
    """Test reply() raises NotImplementedError."""
    with pytest.raises(NotImplementedError) as exc_info:
        sample_message.reply()

    assert "Draft class not yet implemented - Story 3.6" in str(exc_info.value)


def test_message_forward_not_implemented(sample_message):
    """Test forward() raises NotImplementedError."""
    with pytest.raises(NotImplementedError) as exc_info:
        sample_message.forward()

    assert "Draft class not yet implemented - Story 3.6" in str(exc_info.value)


def test_message_reply_all_not_implemented(sample_message):
    """Test reply_all() raises NotImplementedError."""
    with pytest.raises(NotImplementedError) as exc_info:
        sample_message.reply_all()

    assert "Draft class not yet implemented - Story 3.6" in str(exc_info.value)


def test_message_repr(sample_message):
    """Test __repr__ works correctly."""
    repr_str = repr(sample_message)
    assert "Message(" in repr_str
    assert "uid=42" in repr_str
    assert "folder='INBOX'" in repr_str
    assert "from=alice@example.com" in repr_str
    assert "subject='Test Subject'" in repr_str
