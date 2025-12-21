"""Tests for Message class.

Story 3.9: Refactored to use centralized mock fixtures from conftest.py.
Eliminated 1 duplicate fixture (mock_imap).
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock

import pytest

from mailcore.attachment import Attachment
from mailcore.body import MessageBody
from mailcore.email_address import EmailAddress
from mailcore.message import Message
from mailcore.types import MessageData, MessageFlag


@pytest.fixture
def sample_message(mock_imap):
    """Create sample message for testing.

    Uses centralized mock_imap from conftest.py.
    """
    return Message(
        imap=mock_imap,
        smtp=None,
        default_sender=None,
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
        smtp=None,
        default_sender=None,
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
        smtp=None,
        default_sender=None,
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
    """Test delete(permanent=False) calls move_message."""
    await sample_message.delete(permanent=False, trash_folder="Trash")

    mock_imap.move_message.assert_called_once_with(uid=42, from_folder="INBOX", to_folder="Trash")


@pytest.mark.asyncio
async def test_message_delete_permanent(sample_message, mock_imap):
    """Test delete(permanent=True) calls delete_message."""
    await sample_message.delete(permanent=True)

    mock_imap.delete_message.assert_called_once_with(folder="INBOX", uid=42)


@pytest.mark.asyncio
async def test_message_delete_without_trash_folder_raises(sample_message, mock_imap):
    """Test delete(permanent=False) without trash_folder raises ValueError."""
    with pytest.raises(ValueError, match="trash_folder parameter required"):
        await sample_message.delete(permanent=False)


@pytest.mark.asyncio
async def test_message_mark_deleted(sample_message, mock_imap):
    """Test mark_deleted calls IMAP correctly."""
    await sample_message.mark_deleted()

    mock_imap.update_message_flags.assert_called_once_with(folder="INBOX", uid=42, add_flags={MessageFlag.DELETED})


def test_message_repr(sample_message):
    """Test __repr__ works correctly."""
    repr_str = repr(sample_message)
    assert "Message(" in repr_str
    assert "uid=42" in repr_str
    assert "folder='INBOX'" in repr_str
    assert "from=alice@example.com" in repr_str
    assert "subject='Test Subject'" in repr_str


def test_message_accepts_attachments_parameter(mock_imap):
    """Test Message constructor accepts attachments parameter."""
    att = Attachment(
        uri="imap://INBOX/42/part/2",
        filename="report.pdf",
        size=1024,
        content_type="application/pdf",
    )

    message = Message(
        imap=mock_imap,
        smtp=None,
        default_sender=None,
        uid=42,
        folder="INBOX",
        message_id="<msg@example.com>",
        from_=EmailAddress("alice@example.com"),
        to=[EmailAddress("bob@example.com")],
        cc=[],
        subject="Test",
        date=datetime.now(timezone.utc),
        flags=[],
        size=100,
        attachments=[att],
    )

    assert len(message._attachments) == 1
    assert message._attachments[0] is att


def test_message_attachments_property(mock_imap):
    """Test Message.attachments returns list[Attachment]."""
    att1 = Attachment(
        uri="imap://INBOX/42/part/2",
        filename="file1.pdf",
    )
    att2 = Attachment(
        uri="imap://INBOX/42/part/3",
        filename="file2.jpg",
    )

    message = Message(
        imap=mock_imap,
        smtp=None,
        default_sender=None,
        uid=42,
        folder="INBOX",
        message_id="<msg@example.com>",
        from_=EmailAddress("alice@example.com"),
        to=[EmailAddress("bob@example.com")],
        cc=[],
        subject="Test",
        date=datetime.now(timezone.utc),
        flags=[],
        size=100,
        attachments=[att1, att2],
    )

    attachments = message.attachments
    assert len(attachments) == 2
    assert attachments[0] is att1
    assert attachments[1] is att2


def test_message_has_attachments_computed(mock_imap):
    """Test Message.has_attachments excludes inline attachments."""
    # Message with non-inline attachment
    real_att = Attachment(
        uri="imap://INBOX/42/part/2",
        filename="report.pdf",
        is_inline=False,
    )

    # Message with inline attachment
    inline_att = Attachment(
        uri="imap://INBOX/42/part/3",
        filename="logo.png",
        is_inline=True,
    )

    # Message with both
    message = Message(
        imap=mock_imap,
        smtp=None,
        default_sender=None,
        uid=42,
        folder="INBOX",
        message_id="<msg@example.com>",
        from_=EmailAddress("alice@example.com"),
        to=[EmailAddress("bob@example.com")],
        cc=[],
        subject="Test",
        date=datetime.now(timezone.utc),
        flags=[],
        size=100,
        attachments=[real_att, inline_att],
    )

    assert message.has_attachments is True

    # Message with only inline attachments
    message_inline_only = Message(
        imap=mock_imap,
        smtp=None,
        default_sender=None,
        uid=43,
        folder="INBOX",
        message_id="<msg2@example.com>",
        from_=EmailAddress("alice@example.com"),
        to=[EmailAddress("bob@example.com")],
        cc=[],
        subject="Test 2",
        date=datetime.now(timezone.utc),
        flags=[],
        size=100,
        attachments=[inline_att],
    )

    assert message_inline_only.has_attachments is False


def test_message_attachment_count(mock_imap):
    """Test Message.attachment_count counts non-inline attachments."""
    att1 = Attachment(uri="uri1", filename="file1.pdf", is_inline=False)
    att2 = Attachment(uri="uri2", filename="file2.pdf", is_inline=False)
    inline = Attachment(uri="uri3", filename="logo.png", is_inline=True)

    message = Message(
        imap=mock_imap,
        smtp=None,
        default_sender=None,
        uid=42,
        folder="INBOX",
        message_id="<msg@example.com>",
        from_=EmailAddress("alice@example.com"),
        to=[EmailAddress("bob@example.com")],
        cc=[],
        subject="Test",
        date=datetime.now(timezone.utc),
        flags=[],
        size=100,
        attachments=[att1, att2, inline],
    )

    assert message.attachment_count == 2  # Only non-inline


def test_message_inline_count(mock_imap):
    """Test Message.inline_count counts inline attachments."""
    att1 = Attachment(uri="uri1", filename="file1.pdf", is_inline=False)
    inline1 = Attachment(uri="uri2", filename="img1.png", is_inline=True)
    inline2 = Attachment(uri="uri3", filename="img2.jpg", is_inline=True)

    message = Message(
        imap=mock_imap,
        smtp=None,
        default_sender=None,
        uid=42,
        folder="INBOX",
        message_id="<msg@example.com>",
        from_=EmailAddress("alice@example.com"),
        to=[EmailAddress("bob@example.com")],
        cc=[],
        subject="Test",
        date=datetime.now(timezone.utc),
        flags=[],
        size=100,
        attachments=[att1, inline1, inline2],
    )

    assert message.inline_count == 2  # Only inline


# Message Compose Methods Tests (Story 3.6)


def test_message_reply_creates_draft(mock_imap, mock_smtp):
    """Test reply() creates Draft with correct fields."""
    message = Message(
        imap=mock_imap,
        smtp=None,
        default_sender=None,
        uid=42,
        folder="INBOX",
        message_id="<original@example.com>",
        from_=EmailAddress("alice@example.com", "Alice"),
        to=[EmailAddress("bob@example.com")],
        cc=[],
        subject="Question",
        date=datetime.now(timezone.utc),
        flags=[],
        size=100,
        references=["<thread-1@example.com>"],
    )
    message._smtp = mock_smtp

    draft = message.reply()

    # Verify Draft created
    assert draft is not None
    assert draft._smtp == mock_smtp
    assert draft._reference_message == message
    assert draft._quote is True


def test_message_reply_sets_in_reply_to(mock_imap, mock_smtp):
    """Test reply() sets in_reply_to = message_id."""
    message = Message(
        imap=mock_imap,
        smtp=None,
        default_sender=None,
        uid=42,
        folder="INBOX",
        message_id="<original@example.com>",
        from_=EmailAddress("alice@example.com"),
        to=[EmailAddress("bob@example.com")],
        cc=[],
        subject="Test",
        date=datetime.now(timezone.utc),
        flags=[],
        size=100,
    )
    message._smtp = mock_smtp

    draft = message.reply()

    assert draft._in_reply_to == "<original@example.com>"


def test_message_reply_sets_references(mock_imap, mock_smtp):
    """Test reply() includes original message_id in references."""
    message = Message(
        imap=mock_imap,
        smtp=None,
        default_sender=None,
        uid=42,
        folder="INBOX",
        message_id="<original@example.com>",
        from_=EmailAddress("alice@example.com"),
        to=[EmailAddress("bob@example.com")],
        cc=[],
        subject="Test",
        date=datetime.now(timezone.utc),
        flags=[],
        size=100,
        references=["<thread-1@example.com>"],
    )
    message._smtp = mock_smtp

    draft = message.reply()

    assert draft._references == ["<thread-1@example.com>", "<original@example.com>"]


def test_message_reply_prefixes_subject(mock_imap, mock_smtp):
    """Test reply() adds 'Re:' prefix to subject."""
    message = Message(
        imap=mock_imap,
        smtp=None,
        default_sender=None,
        uid=42,
        folder="INBOX",
        message_id="<original@example.com>",
        from_=EmailAddress("alice@example.com"),
        to=[EmailAddress("bob@example.com")],
        cc=[],
        subject="Question",
        date=datetime.now(timezone.utc),
        flags=[],
        size=100,
    )
    message._smtp = mock_smtp

    draft = message.reply()

    assert draft._subject == "Re: Question"

    # Test it doesn't duplicate Re:
    message2 = Message(
        imap=mock_imap,
        smtp=None,
        default_sender=None,
        uid=43,
        folder="INBOX",
        message_id="<msg2@example.com>",
        from_=EmailAddress("alice@example.com"),
        to=[EmailAddress("bob@example.com")],
        cc=[],
        subject="Re: Question",  # Already has Re:
        date=datetime.now(timezone.utc),
        flags=[],
        size=100,
    )
    message2._smtp = mock_smtp

    draft2 = message2.reply()
    assert draft2._subject == "Re: Question"  # Not "Re: Re: Question"


def test_message_reply_requires_smtp(mock_imap):
    """Test reply() raises ValueError if _smtp is None."""
    message = Message(
        imap=mock_imap,
        smtp=None,
        default_sender=None,
        uid=42,
        folder="INBOX",
        message_id="<original@example.com>",
        from_=EmailAddress("alice@example.com"),
        to=[EmailAddress("bob@example.com")],
        cc=[],
        subject="Test",
        date=datetime.now(timezone.utc),
        flags=[],
        size=100,
    )
    # No SMTP injected

    with pytest.raises(ValueError, match="SMTP connection not available"):
        message.reply()


def test_message_reply_all_includes_all_recipients(mock_imap, mock_smtp):
    """Test reply_all() includes all original recipients in to + cc."""
    message = Message(
        imap=mock_imap,
        smtp=None,
        default_sender=None,
        uid=42,
        folder="INBOX",
        message_id="<original@example.com>",
        from_=EmailAddress("alice@example.com", "Alice"),
        to=[EmailAddress("bob@example.com", "Bob"), EmailAddress("charlie@example.com", "Charlie")],
        cc=[EmailAddress("dave@example.com", "Dave")],
        subject="Team Update",
        date=datetime.now(timezone.utc),
        flags=[],
        size=100,
    )
    message._smtp = mock_smtp

    draft = message.reply_all()

    # To: original sender + all original recipients
    assert len(draft._to) == 3
    assert "Alice <alice@example.com>" in draft._to
    assert "Bob <bob@example.com>" in draft._to
    assert "Charlie <charlie@example.com>" in draft._to

    # CC: all original CC
    assert draft._cc is not None
    assert len(draft._cc) == 1
    assert "Dave <dave@example.com>" in draft._cc


def test_message_forward_creates_draft(mock_imap, mock_smtp):
    """Test forward() creates Draft with correct fields."""
    message = Message(
        imap=mock_imap,
        smtp=None,
        default_sender=None,
        uid=42,
        folder="INBOX",
        message_id="<original@example.com>",
        from_=EmailAddress("alice@example.com"),
        to=[EmailAddress("bob@example.com")],
        cc=[],
        subject="Important Document",
        date=datetime.now(timezone.utc),
        flags=[],
        size=100,
    )
    message._smtp = mock_smtp

    draft = message.forward()

    assert draft is not None
    assert draft._smtp == mock_smtp
    assert draft._reference_message == message
    assert draft._include_attachments is True
    assert draft._include_body is True  # Default value


def test_message_forward_prefixes_subject(mock_imap, mock_smtp):
    """Test forward() adds 'Fwd:' prefix to subject."""
    message = Message(
        imap=mock_imap,
        smtp=None,
        default_sender=None,
        uid=42,
        folder="INBOX",
        message_id="<original@example.com>",
        from_=EmailAddress("alice@example.com"),
        to=[EmailAddress("bob@example.com")],
        cc=[],
        subject="Important",
        date=datetime.now(timezone.utc),
        flags=[],
        size=100,
    )
    message._smtp = mock_smtp

    draft = message.forward()

    assert draft._subject == "Fwd: Important"

    # Test it doesn't duplicate Fwd:
    message2 = Message(
        imap=mock_imap,
        smtp=None,
        default_sender=None,
        uid=43,
        folder="INBOX",
        message_id="<msg2@example.com>",
        from_=EmailAddress("alice@example.com"),
        to=[EmailAddress("bob@example.com")],
        cc=[],
        subject="Fwd: Important",  # Already has Fwd:
        date=datetime.now(timezone.utc),
        flags=[],
        size=100,
    )
    message2._smtp = mock_smtp

    draft2 = message2.forward()
    assert draft2._subject == "Fwd: Important"  # Not "Fwd: Fwd: Important"


def test_message_forward_requires_smtp(mock_imap):
    """Test forward() raises ValueError if _smtp is None."""
    message = Message(
        imap=mock_imap,
        smtp=None,
        default_sender=None,
        uid=42,
        folder="INBOX",
        message_id="<original@example.com>",
        from_=EmailAddress("alice@example.com"),
        to=[EmailAddress("bob@example.com")],
        cc=[],
        subject="Test",
        date=datetime.now(timezone.utc),
        flags=[],
        size=100,
    )
    # No SMTP injected

    with pytest.raises(ValueError, match="SMTP connection not available"):
        message.forward()


# Story 3.22: Message.forward() include_body parameter tests


def test_message_forward_includes_body_by_default(mock_imap, mock_smtp):
    """Test forward() has include_body=True by default."""
    message = Message(
        imap=mock_imap,
        smtp=None,
        default_sender=None,
        uid=42,
        folder="INBOX",
        message_id="<original@example.com>",
        from_=EmailAddress("alice@example.com"),
        to=[EmailAddress("bob@example.com")],
        cc=[],
        subject="Test",
        date=datetime.now(timezone.utc),
        flags=set(),
        size=100,
    )
    message._smtp = mock_smtp
    message._default_sender = "me@example.com"

    draft = message.forward()

    assert draft._include_body is True


def test_message_forward_without_body(mock_imap, mock_smtp):
    """Test forward(include_body=False) does not include body."""
    message = Message(
        imap=mock_imap,
        smtp=None,
        default_sender=None,
        uid=42,
        folder="INBOX",
        message_id="<original@example.com>",
        from_=EmailAddress("alice@example.com"),
        to=[EmailAddress("bob@example.com")],
        cc=[],
        subject="Test",
        date=datetime.now(timezone.utc),
        flags=set(),
        size=100,
    )
    message._smtp = mock_smtp
    message._default_sender = "me@example.com"

    draft = message.forward(include_body=False)

    assert draft._include_body is False


def test_message_from_data_creates_entity(mock_imap, mock_smtp):
    """Test Message.from_data() converts DTO to entity."""
    data = MessageData(
        uid=99,
        folder="Sent",
        message_id="<data-test@example.com>",
        from_=EmailAddress("sender@example.com", "Sender Name"),
        to=[EmailAddress("recipient@example.com")],
        cc=[EmailAddress("cc@example.com")],
        subject="Data Test",
        date=datetime(2025, 12, 17, 14, 0, tzinfo=timezone.utc),
        flags={MessageFlag.SEEN, MessageFlag.ANSWERED},
        size=2048,
        custom_flags={"$Forwarded"},
        in_reply_to="<reply-to@example.com>",
        references=["<ref1@example.com>"],
        attachments=[Attachment.from_bytes(b"test", "test.txt", "text/plain")],
    )

    message = Message.from_data(data, mock_imap, mock_smtp, "default@example.com")

    # Verify all fields copied from DTO
    assert message.uid == 99
    assert message.folder == "Sent"
    assert message.message_id == "<data-test@example.com>"
    assert message.from_.email == "sender@example.com"
    assert len(message.to) == 1
    assert message.to[0].email == "recipient@example.com"
    assert len(message.cc) == 1
    assert message.subject == "Data Test"
    assert message.date == datetime(2025, 12, 17, 14, 0, tzinfo=timezone.utc)
    assert MessageFlag.SEEN in message.flags
    assert MessageFlag.ANSWERED in message.flags
    assert message.size == 2048
    assert "$Forwarded" in message.custom_flags
    assert message.in_reply_to == "<reply-to@example.com>"
    assert len(message.references) == 1
    assert len(message.attachments) == 1


def test_message_from_data_injects_imap_and_smtp(mock_imap, mock_smtp):
    """Test Message.from_data() injects both IMAP and SMTP."""
    data = MessageData(
        uid=1,
        folder="INBOX",
        message_id="<test@example.com>",
        from_=EmailAddress("alice@example.com"),
        to=[],
        cc=[],
        subject="Test",
        date=datetime.now(timezone.utc),
        flags=set(),
        size=100,
        custom_flags=set(),
        in_reply_to=None,
        references=[],
        attachments=[],
    )

    message = Message.from_data(data, mock_imap, mock_smtp, "me@example.com")

    assert message._imap is mock_imap
    assert message._smtp is mock_smtp
    assert message._default_sender == "me@example.com"


def test_message_from_data_smtp_not_none(mock_imap, mock_smtp):
    """Test Message.from_data() creates message with SMTP immediately available."""
    data = MessageData(
        uid=1,
        folder="INBOX",
        message_id="<test@example.com>",
        from_=EmailAddress("alice@example.com"),
        to=[],
        cc=[],
        subject="Test",
        date=datetime.now(timezone.utc),
        flags=set(),
        size=100,
        custom_flags=set(),
        in_reply_to=None,
        references=[],
        attachments=[],
    )

    message = Message.from_data(data, mock_imap, mock_smtp, "me@example.com")

    # Should be able to call reply() immediately (no ValueError)
    draft = message.reply()
    assert draft is not None


# Message.edit() tests


@pytest.mark.asyncio
async def test_message_edit_requires_draft_flag(mock_imap, mock_smtp):
    """Test that edit() validates MessageFlag.DRAFT is present."""
    from mailcore.types import MessageFlag

    # Sent message (no DRAFT flag)
    message = Message(
        imap=mock_imap,
        smtp=mock_smtp,
        default_sender="me@example.com",
        uid=42,
        folder="Sent",
        message_id="<msg@example.com>",
        from_=EmailAddress("me@example.com"),
        to=[EmailAddress("alice@example.com")],
        cc=[],
        subject="Sent Message",
        date=Mock(),
        flags={MessageFlag.SEEN},  # No DRAFT flag
        size=100,
    )

    with pytest.raises(ValueError, match="Cannot edit message without.*Draft"):
        await message.edit()


@pytest.mark.asyncio
async def test_message_edit_requires_smtp_connection(mock_imap):
    """Test that edit() requires SMTP connection."""
    from mailcore.types import MessageFlag

    message = Message(
        imap=mock_imap,
        smtp=None,  # No SMTP
        default_sender="me@example.com",
        uid=42,
        folder="Drafts",
        message_id="<msg@example.com>",
        from_=EmailAddress("me@example.com"),
        to=[EmailAddress("alice@example.com")],
        cc=[],
        subject="Draft",
        date=Mock(),
        flags={MessageFlag.DRAFT},
        size=100,
    )

    with pytest.raises(ValueError, match="SMTP connection not available"):
        await message.edit()


@pytest.mark.asyncio
async def test_message_edit_populates_draft_fields(mock_imap, mock_smtp):
    """Test that edit() pre-populates Draft with message fields."""
    from mailcore.types import MessageFlag

    # Mock body fetching
    mock_body = Mock()
    mock_body.get_text = AsyncMock(return_value="Original body text")
    mock_body.get_html = AsyncMock(return_value="<p>Original body html</p>")

    message = Message(
        imap=mock_imap,
        smtp=mock_smtp,
        default_sender="me@example.com",
        uid=42,
        folder="Drafts",
        message_id="<msg@example.com>",
        from_=EmailAddress("me@example.com"),
        to=[EmailAddress("alice@example.com", "Alice")],
        cc=[EmailAddress("bob@example.com", "Bob")],
        subject="Draft Subject",
        date=Mock(),
        flags={MessageFlag.DRAFT},
        size=100,
    )
    message._body = mock_body

    draft = await message.edit()

    # Verify fields populated
    assert draft._to == ["Alice <alice@example.com>"]
    assert draft._cc == ["Bob <bob@example.com>"]
    assert draft._subject == "Draft Subject"
    assert draft._body == "Original body text"
    assert draft._body_html == "<p>Original body html</p>"


@pytest.mark.asyncio
async def test_message_edit_tracks_original_for_replace(mock_imap, mock_smtp):
    """Test that edit() tracks original UID/folder/flags for smart save."""
    from mailcore.types import MessageFlag

    mock_body = Mock()
    mock_body.get_text = AsyncMock(return_value="Text")
    mock_body.get_html = AsyncMock(return_value=None)

    message = Message(
        imap=mock_imap,
        smtp=mock_smtp,
        default_sender="me@example.com",
        uid=42,
        folder="Drafts",
        message_id="<msg@example.com>",
        from_=EmailAddress("me@example.com"),
        to=[EmailAddress("alice@example.com")],
        cc=[],
        subject="Draft",
        date=Mock(),
        flags={MessageFlag.DRAFT, MessageFlag.SEEN},
        custom_flags={"$Forwarded"},
        size=100,
    )
    message._body = mock_body

    draft = await message.edit()

    # Verify tracking fields
    assert draft._original_message_uid == 42
    assert draft._original_message_folder == "Drafts"
    assert MessageFlag.DRAFT in draft._original_message_flags
    assert MessageFlag.SEEN in draft._original_message_flags
    assert "$Forwarded" in draft._original_custom_flags


@pytest.mark.asyncio
async def test_message_edit_copies_attachments(mock_imap, mock_smtp):
    """Test that edit() copies attachments from original message."""
    from mailcore.types import MessageFlag

    mock_body = Mock()
    mock_body.get_text = AsyncMock(return_value="Text")
    mock_body.get_html = AsyncMock(return_value=None)

    # Create proper Attachment instances
    att1 = Attachment(
        uri="imap://Drafts/42/part/2",
        filename="file1.pdf",
        content_type="application/pdf",
        size=1024,
        _resolver=Mock(),
    )
    att2 = Attachment(
        uri="imap://Drafts/42/part/3",
        filename="file2.png",
        content_type="image/png",
        size=2048,
        _resolver=Mock(),
    )

    message = Message(
        imap=mock_imap,
        smtp=mock_smtp,
        default_sender="me@example.com",
        uid=42,
        folder="Drafts",
        message_id="<msg@example.com>",
        from_=EmailAddress("me@example.com"),
        to=[EmailAddress("alice@example.com")],
        cc=[],
        subject="Draft",
        date=Mock(),
        flags={MessageFlag.DRAFT},
        size=100,
        attachments=[att1, att2],
    )
    message._body = mock_body

    draft = await message.edit()

    # Verify attachments copied
    assert len(draft._attachments) == 2
    assert draft._attachments[0] == att1
    assert draft._attachments[1] == att2
