"""Tests for Draft class (fluent builder for composing emails).

Story 3.9: Refactored to use centralized mock fixtures from conftest.py.
Eliminated 1 duplicate fixture (mock_smtp) - now uses centralized version.
"""

from unittest.mock import AsyncMock, Mock

import pytest

from mailcore.attachment import Attachment
from mailcore.body import MessageBody
from mailcore.draft import Draft
from mailcore.email_address import EmailAddress
from mailcore.message import Message
from mailcore.protocols import SMTPConnection


@pytest.fixture
def mock_message(mock_smtp):
    """Mock Message for reply/forward tests.

    Uses centralized mock_smtp from conftest.py.
    """
    mock_imap = Mock()
    msg = Message(
        imap=mock_imap,
        smtp=None,
        default_sender="sender@example.com",  # Add default sender for reply/forward
        uid=42,
        folder="INBOX",
        message_id="<original@example.com>",
        from_=EmailAddress("alice@example.com", "Alice"),
        to=[EmailAddress("bob@example.com", "Bob")],
        cc=[EmailAddress("charlie@example.com", "Charlie")],
        subject="Original Subject",
        date=Mock(strftime=Mock(return_value="2025-12-15 10:00")),
        flags=[],
        size=1024,
        references=["<thread-1@example.com>"],
    )
    # Inject SMTP
    msg._smtp = mock_smtp
    return msg


def test_draft_initialization(mock_smtp):
    """Test Draft constructor stores all parameters correctly."""
    ref_msg = Mock()
    draft = Draft(
        smtp=mock_smtp,
        default_sender="test@example.com",
        reference_message=ref_msg,
        in_reply_to="<msg-123@example.com>",
        references=["<msg-1@example.com>", "<msg-2@example.com>"],
        quote=True,
        include_attachments=False,
    )

    assert draft._smtp == mock_smtp
    assert draft._default_sender == "test@example.com"
    assert draft._reference_message == ref_msg
    assert draft._in_reply_to == "<msg-123@example.com>"
    assert draft._references == ["<msg-1@example.com>", "<msg-2@example.com>"]
    assert draft._quote is True
    assert draft._include_attachments is False


def test_to_overwrites_previous(mock_smtp):
    """Test calling to() twice overwrites previous value."""
    draft = Draft(smtp=mock_smtp, default_sender="test@example.com")
    draft.to("alice@example.com")
    assert draft._to == ["alice@example.com"]

    draft.to("bob@example.com")
    assert draft._to == ["bob@example.com"]  # Overwrote alice


def test_to_accepts_string_or_list(mock_smtp):
    """Test to() handles both str and list[str]."""
    draft = Draft(smtp=mock_smtp, default_sender="test@example.com")

    # String input
    draft.to("alice@example.com")
    assert draft._to == ["alice@example.com"]

    # List input
    draft.to(["bob@example.com", "charlie@example.com"])
    assert draft._to == ["bob@example.com", "charlie@example.com"]


def test_cc_overwrites_previous(mock_smtp):
    """Test calling cc() twice overwrites previous value."""
    draft = Draft(smtp=mock_smtp, default_sender="test@example.com")
    draft.cc("alice@example.com")
    assert draft._cc == ["alice@example.com"]

    draft.cc("bob@example.com")
    assert draft._cc == ["bob@example.com"]


def test_bcc_overwrites_previous(mock_smtp):
    """Test calling bcc() twice overwrites previous value."""
    draft = Draft(smtp=mock_smtp, default_sender="test@example.com")
    draft.bcc("archive@example.com")
    assert draft._bcc == ["archive@example.com"]

    draft.bcc("backup@example.com")
    assert draft._bcc == ["backup@example.com"]


def test_subject_overwrites_previous(mock_smtp):
    """Test calling subject() twice overwrites previous value."""
    draft = Draft(smtp=mock_smtp, default_sender="test@example.com")
    draft.subject("First Subject")
    assert draft._subject == "First Subject"

    draft.subject("Second Subject")
    assert draft._subject == "Second Subject"


def test_body_overwrites_previous(mock_smtp):
    """Test calling body() twice overwrites previous value."""
    draft = Draft(smtp=mock_smtp, default_sender="test@example.com")
    draft.body("First body")
    assert draft._body == "First body"

    draft.body("Second body")
    assert draft._body == "Second body"


def test_body_html_overwrites_previous(mock_smtp):
    """Test calling body_html() twice overwrites previous value."""
    draft = Draft(smtp=mock_smtp, default_sender="test@example.com")
    draft.body_html("<p>First</p>")
    assert draft._body_html == "<p>First</p>"

    draft.body_html("<p>Second</p>")
    assert draft._body_html == "<p>Second</p>"


def test_attach_appends_to_list(mock_smtp):
    """Test calling attach() multiple times appends to list."""
    draft = Draft(smtp=mock_smtp, default_sender="test@example.com")

    att1 = Attachment(uri="file:///tmp/file1.pdf", filename="file1.pdf")
    att2 = Attachment(uri="file:///tmp/file2.pdf", filename="file2.pdf")

    draft.attach(att1)
    assert len(draft._attachments) == 1
    assert draft._attachments[0] == att1

    draft.attach(att2)
    assert len(draft._attachments) == 2
    assert draft._attachments[1] == att2


def test_attach_from_file_creates_attachment(mock_smtp, tmp_path):
    """Test attach(path) creates Attachment from file."""
    # Create temporary file
    test_file = tmp_path / "report.pdf"
    test_file.write_bytes(b"fake pdf content")

    draft = Draft(smtp=mock_smtp, default_sender="test@example.com")
    draft.attach(str(test_file))

    assert len(draft._attachments) == 1
    assert draft._attachments[0].uri.startswith("file://")
    assert draft._attachments[0].filename == "report.pdf"


def test_attach_from_url_creates_attachment(mock_smtp):
    """Test attach(url) creates Attachment from URL."""
    draft = Draft(smtp=mock_smtp, default_sender="test@example.com")
    draft.attach("https://example.com/chart.png", filename="chart.png")

    assert len(draft._attachments) == 1
    assert draft._attachments[0].uri == "https://example.com/chart.png"
    assert draft._attachments[0].filename == "chart.png"


def test_attach_existing_attachment(mock_smtp):
    """Test attach(Attachment) appends directly."""
    draft = Draft(smtp=mock_smtp, default_sender="test@example.com")
    att = Attachment(uri="imap://INBOX/42/part/2", filename="document.pdf", size=1024, content_type="application/pdf")

    draft.attach(att)

    assert len(draft._attachments) == 1
    assert draft._attachments[0] == att


def test_builder_methods_return_self(mock_smtp):
    """Test all builder methods return self for chaining."""
    draft = Draft(smtp=mock_smtp, default_sender="test@example.com")

    # Chain all methods
    result = (
        draft.to("alice@example.com")
        .cc("bob@example.com")
        .bcc("archive@example.com")
        .subject("Test")
        .body("Hello")
        .body_html("<p>Hello</p>")
        .attach(Attachment(uri="file:///tmp/file.pdf", filename="file.pdf"))
    )

    assert result is draft


@pytest.mark.asyncio
async def test_send_calls_smtp_connection(mock_smtp):
    """Test send() calls smtp.send_message() with correct parameters."""
    draft = Draft(smtp=mock_smtp, default_sender="test@example.com")
    draft.to("alice@example.com").subject("Test").body("Hello World")

    message_id = await draft.send()

    # Verify send was called
    mock_smtp.send_message.assert_called_once()

    # Check message_id returned
    assert message_id == "<sent-123@example.com>"


@pytest.mark.asyncio
async def test_send_requires_to_and_subject(mock_smtp):
    """Test send() raises ValueError if to or subject missing."""
    draft = Draft(smtp=mock_smtp, default_sender="test@example.com")

    # Missing to
    draft.subject("Test").body("Hello")
    with pytest.raises(ValueError, match="requires 'to'"):
        await draft.send()

    # Missing subject
    draft = Draft(smtp=mock_smtp, default_sender="test@example.com")
    draft.to("alice@example.com").body("Hello")
    with pytest.raises(ValueError, match="requires 'subject'"):
        await draft.send()


@pytest.mark.asyncio
async def test_send_allows_empty_body(mock_smtp):
    """Test send() allows empty body (e.g., attachment-only emails)."""
    draft = Draft(smtp=mock_smtp, default_sender="test@example.com")
    draft.to("alice@example.com").subject("Test")

    # Send without body or body_html (should succeed with empty body)
    message_id = await draft.send()

    # Verify send was called with empty body_text
    mock_smtp.send_message.assert_called_once()
    call_args = mock_smtp.send_message.call_args
    assert call_args.kwargs["body_text"] == ""
    assert message_id is not None  # Returns a message_id


@pytest.mark.asyncio
async def test_send_with_kwargs_overrides(mock_smtp):
    """Test send(to='...', cc='...') applies kwargs before sending."""
    draft = Draft(smtp=mock_smtp, default_sender="test@example.com")
    draft.to("alice@example.com").subject("Test").body("Hello")

    # Override cc at send time
    await draft.send(cc="manager@example.com")

    # Verify cc was applied
    call_args = mock_smtp.send_message.call_args
    assert call_args.kwargs["cc"] is not None
    assert len(call_args.kwargs["cc"]) == 1
    assert call_args.kwargs["cc"][0].email == "manager@example.com"


@pytest.mark.asyncio
async def test_send_with_quote_fetches_body(mock_smtp, mock_message):
    """Test quote=True fetches reference_message.body during send()."""
    # Mock body fetch
    mock_body = AsyncMock(spec=MessageBody)
    mock_body.get_text = AsyncMock(return_value="Original message text.\nLine 2.")
    mock_message._body = mock_body

    # Create reply draft with quote
    draft = Draft(smtp=mock_smtp, default_sender="test@example.com", reference_message=mock_message, quote=True)
    draft.to("alice@example.com").subject("Re: Test").body("My reply")

    await draft.send()

    # Verify body was fetched
    mock_body.get_text.assert_called_once()

    # Verify quoted text was prepended
    call_args = mock_smtp.send_message.call_args
    body_text = call_args.kwargs["body_text"]
    assert "My reply" in body_text
    assert "On 2025-12-15 10:00, Alice <alice@example.com> wrote:" in body_text
    assert "> Original message text." in body_text
    assert "> Line 2." in body_text


@pytest.mark.asyncio
async def test_send_with_attachments_fetches_content(mock_smtp, mock_message):
    """Test include_attachments=True fetches attachment content during send()."""
    # Create mock attachment with read()
    mock_att = AsyncMock(spec=Attachment)
    mock_att.read = AsyncMock(return_value=b"attachment content")
    mock_att.uri = "imap://INBOX/42/part/2"
    mock_att.filename = "document.pdf"
    mock_message._attachments = [mock_att]

    # Create forward draft with include_attachments
    draft = Draft(
        smtp=mock_smtp,
        default_sender="test@example.com",
        reference_message=mock_message,
        include_attachments=True,
    )
    draft.to("colleague@example.com").subject("Fwd: Test").body("FYI")

    await draft.send()

    # Verify attachment content was fetched
    mock_att.read.assert_called_once()

    # Verify attachment was included in send
    call_args = mock_smtp.send_message.call_args
    attachments = call_args.kwargs["attachments"]
    assert attachments is not None
    assert len(attachments) == 1
    assert attachments[0] == mock_att


# Story 3.22: Forward body inclusion tests


@pytest.mark.asyncio
async def test_send_with_forward_body_fetches_original(mock_smtp, mock_message):
    """Test include_body=True fetches reference_message.body during send()."""
    # Mock body fetch
    mock_body = AsyncMock(spec=MessageBody)
    mock_body.get_text = AsyncMock(return_value="Original message content.")
    mock_message._body = mock_body

    # Create forward draft with include_body
    draft = Draft(
        smtp=mock_smtp,
        default_sender="test@example.com",
        reference_message=mock_message,
        include_body=True,
    )
    draft.to("colleague@example.com").subject("Fwd: Test")

    await draft.send()

    # Verify body was fetched
    mock_body.get_text.assert_called_once()

    # Verify forward header and original content included
    call_args = mock_smtp.send_message.call_args
    body_text = call_args.kwargs["body_text"]
    assert "---------- Forwarded message ---------" in body_text
    assert "From: Alice <alice@example.com>" in body_text
    assert "Date: 2025-12-15 10:00" in body_text
    assert "Subject: Original Subject" in body_text  # From mock_message fixture
    assert "To: Bob <bob@example.com>" in body_text
    assert "Original message content." in body_text


@pytest.mark.asyncio
async def test_forward_body_prepends_to_user_body(mock_smtp, mock_message):
    """Test user body appears before forward header when both present."""
    # Mock body fetch
    mock_body = AsyncMock(spec=MessageBody)
    mock_body.get_text = AsyncMock(return_value="Original content.")
    mock_message._body = mock_body

    # Create forward draft with user body
    draft = Draft(
        smtp=mock_smtp,
        default_sender="test@example.com",
        reference_message=mock_message,
        include_body=True,
    )
    draft.to("colleague@example.com").subject("Fwd: Test").body("FYI")

    await draft.send()

    # Verify user body appears first
    call_args = mock_smtp.send_message.call_args
    body_text = call_args.kwargs["body_text"]

    # Find positions
    fyi_pos = body_text.find("FYI")
    header_pos = body_text.find("---------- Forwarded message ---------")
    original_pos = body_text.find("Original content.")

    # Assert ordering: user body < forward header < original content
    assert fyi_pos < header_pos < original_pos


@pytest.mark.asyncio
async def test_forward_without_body_skips_fetch(mock_smtp, mock_message):
    """Test include_body=False does NOT fetch original message body."""
    # Mock body fetch (should NOT be called)
    mock_body = AsyncMock(spec=MessageBody)
    mock_body.get_text = AsyncMock(return_value="Original message content.")
    mock_message._body = mock_body

    # Create forward draft with include_body=False
    draft = Draft(
        smtp=mock_smtp,
        default_sender="test@example.com",
        reference_message=mock_message,
        include_body=False,
    )
    draft.to("colleague@example.com").subject("Fwd: Test").body("Check this out")

    await draft.send()

    # Verify body was NOT fetched
    mock_body.get_text.assert_not_called()

    # Verify only user body present (no forward header)
    call_args = mock_smtp.send_message.call_args
    body_text = call_args.kwargs["body_text"]
    assert body_text == "Check this out"
    assert "---------- Forwarded message ---------" not in body_text


# Story 3.14: Draft default_sender and from_() tests


def test_draft_requires_default_sender(mock_smtp: SMTPConnection) -> None:
    """Test Draft raises TypeError when default_sender not provided."""
    with pytest.raises(TypeError, match="missing 1 required positional argument: 'default_sender'"):
        Draft(smtp=mock_smtp)  # type: ignore  # Intentionally missing parameter


@pytest.mark.asyncio
async def test_draft_from_override(mock_smtp: SMTPConnection) -> None:
    """Test Draft.from_() override takes precedence over default_sender."""
    draft = Draft(smtp=mock_smtp, default_sender="default@example.com")
    draft.from_("override@example.com").to("recipient@example.com").subject("Test").body("Test")

    await draft.send()

    # Verify smtp.send_message called with override address
    mock_smtp.send_message.assert_called_once()
    call_args = mock_smtp.send_message.call_args
    from_addr = call_args.kwargs["from_"]
    assert from_addr.email == "override@example.com"


@pytest.mark.asyncio
async def test_draft_uses_default_sender(mock_smtp: SMTPConnection) -> None:
    """Test Draft uses default_sender when no from_() override."""
    draft = Draft(smtp=mock_smtp, default_sender="default@example.com")
    draft.to("recipient@example.com").subject("Test").body("Test")

    await draft.send()

    # Verify smtp.send_message called with default_sender
    mock_smtp.send_message.assert_called_once()
    call_args = mock_smtp.send_message.call_args
    from_addr = call_args.kwargs["from_"]
    assert from_addr.email == "default@example.com"


@pytest.mark.asyncio
async def test_draft_send_with_correct_from_address(mock_smtp: SMTPConnection) -> None:
    """Integration test: verify from_ parameter passed to smtp.send_message."""
    draft = Draft(smtp=mock_smtp, default_sender="sender@example.com")
    draft.to("recipient@example.com").subject("Test").body("Hello")

    await draft.send()

    # Verify SMTP called with correct from_ parameter
    mock_smtp.send_message.assert_called_once()
    call_args = mock_smtp.send_message.call_args
    assert "from_" in call_args.kwargs
    from_addr = call_args.kwargs["from_"]
    assert isinstance(from_addr, EmailAddress)
    assert from_addr.email == "sender@example.com"


def test_draft_repr_minimal(mock_smtp):
    """Verify Draft repr with minimal fields."""
    draft = Draft(smtp=mock_smtp, default_sender="me@example.com")
    draft.to("alice@example.com").subject("Hello")

    repr_str = repr(draft)
    assert "Draft" in repr_str
    assert "to=['alice@example.com']" in repr_str
    assert "subject='Hello'" in repr_str
    assert "body=False" in repr_str
    assert "attachments=0" in repr_str


def test_draft_repr_with_body_and_attachments(mock_smtp):
    """Verify Draft repr shows body and attachment presence."""
    draft = Draft(smtp=mock_smtp, default_sender="me@example.com")
    draft.to("alice@example.com").subject("Report").body("Some text")
    draft._attachments = [Mock(), Mock()]

    repr_str = repr(draft)
    assert "body=True" in repr_str
    assert "attachments=2" in repr_str


def test_draft_repr_long_subject(mock_smtp):
    """Verify Draft repr truncates long subject."""
    long_subject = "A" * 60  # 60 characters
    draft = Draft(smtp=mock_smtp, default_sender="me@example.com")
    draft.subject(long_subject)

    repr_str = repr(draft)
    assert "..." in repr_str  # Truncated
    assert len(repr_str) < 200  # Reasonable length


# Draft.save() tests


@pytest.mark.asyncio
async def test_draft_save_requires_imap_connection(mock_smtp):
    """Test that save() raises error if IMAP connection not available."""
    draft = Draft(smtp=mock_smtp, imap=None, default_sender="me@example.com")
    draft.to("alice@example.com").subject("Test")

    with pytest.raises(ValueError, match="requires IMAP connection"):
        await draft.save(folder="Drafts")


@pytest.mark.asyncio
async def test_draft_save_allows_empty_draft(mock_smtp, mock_imap):
    """Test that save() allows incomplete drafts (no to, no subject, no body)."""
    mock_imap.append_message = AsyncMock(return_value=123)

    # Completely empty draft
    draft = Draft(smtp=mock_smtp, imap=mock_imap, default_sender="me@example.com")

    # Should save without errors
    uid = await draft.save(folder="Drafts")

    assert uid == 123
    assert mock_imap.append_message.called

    # Verify empty values passed correctly
    call_args = mock_imap.append_message.call_args
    assert call_args.kwargs["to"] == []  # Empty list
    assert call_args.kwargs["subject"] == ""  # Empty string


@pytest.mark.asyncio
async def test_draft_save_rejects_bcc(mock_smtp, mock_imap):
    """Test that save() raises clear error if BCC is set (security requirement)."""
    draft = Draft(smtp=mock_smtp, imap=mock_imap, default_sender="me@example.com")
    draft.to("alice@example.com").subject("Test").bcc("secret@example.com")

    with pytest.raises(ValueError) as exc_info:
        await draft.save(folder="Drafts")

    error_msg = str(exc_info.value)
    assert "cannot preserve BCC" in error_msg
    assert "security" in error_msg
    assert "send() or remove BCC" in error_msg


@pytest.mark.asyncio
async def test_draft_save_calls_imap_append_message(mock_smtp, mock_imap):
    """Test that save() calls IMAP append_message with correct parameters."""
    mock_imap.append_message = AsyncMock(return_value=123)

    draft = Draft(smtp=mock_smtp, imap=mock_imap, default_sender="me@example.com")
    draft.to("alice@example.com").subject("Test Subject").body("Test Body")

    uid = await draft.save(folder="Drafts")

    # Verify IMAP append_message was called
    assert mock_imap.append_message.called
    call_args = mock_imap.append_message.call_args

    # Verify UID returned
    assert uid == 123

    # Verify flags include DRAFT
    from mailcore.types import MessageFlag

    assert MessageFlag.DRAFT in call_args.kwargs["flags"]


@pytest.mark.asyncio
async def test_draft_save_preserves_flags_when_editing(mock_smtp, mock_imap):
    """Test that save() preserves flags from original message (except Recent)."""
    from mailcore.types import MessageFlag

    mock_imap.append_message = AsyncMock(return_value=456)
    mock_imap.delete_message = AsyncMock()

    # Create draft from edit (with original flags)
    draft = Draft(
        smtp=mock_smtp,
        imap=mock_imap,
        default_sender="me@example.com",
        original_message_uid=42,
        original_message_folder="Drafts",
        original_message_flags={MessageFlag.DRAFT, MessageFlag.SEEN, MessageFlag.RECENT},
        original_custom_flags={"$Forwarded"},
    )
    draft.to("alice@example.com").subject("Updated").body("Updated body")

    await draft.save(folder="Drafts")

    call_args = mock_imap.append_message.call_args

    # Verify flags preserved (except RECENT)
    assert MessageFlag.DRAFT in call_args.kwargs["flags"]
    assert MessageFlag.SEEN in call_args.kwargs["flags"]
    assert MessageFlag.RECENT not in call_args.kwargs["flags"]

    # Verify custom flags preserved
    assert "$Forwarded" in call_args.kwargs["custom_flags"]


@pytest.mark.asyncio
async def test_draft_save_replaces_original_same_folder(mock_smtp, mock_imap):
    """Test that save() deletes original when saving to same folder."""
    from mailcore.types import MessageFlag

    mock_imap.append_message = AsyncMock(return_value=456)
    mock_imap.delete_message = AsyncMock()

    # Create draft from edit
    draft = Draft(
        smtp=mock_smtp,
        imap=mock_imap,
        default_sender="me@example.com",
        original_message_uid=42,
        original_message_folder="Drafts",
        original_message_flags={MessageFlag.DRAFT},
        original_custom_flags=set(),
    )
    draft.to("alice@example.com").subject("Updated").body("Updated")

    # Save to same folder
    await draft.save(folder="Drafts")

    # Verify original deleted
    assert mock_imap.delete_message.called
    delete_call = mock_imap.delete_message.call_args
    assert delete_call.kwargs["folder"] == "Drafts"
    assert delete_call.kwargs["uid"] == 42


@pytest.mark.asyncio
async def test_draft_save_keeps_original_different_folder(mock_smtp, mock_imap):
    """Test that save() keeps original when saving to different folder."""
    from mailcore.types import MessageFlag

    mock_imap.append_message = AsyncMock(return_value=456)
    mock_imap.delete_message = AsyncMock()

    # Create draft from edit
    draft = Draft(
        smtp=mock_smtp,
        imap=mock_imap,
        default_sender="me@example.com",
        original_message_uid=42,
        original_message_folder="Drafts",
        original_message_flags={MessageFlag.DRAFT},
        original_custom_flags=set(),
    )
    draft.to("alice@example.com").subject("Updated").body("Updated")

    # Save to different folder
    await draft.save(folder="Archive")

    # Verify original NOT deleted
    assert not mock_imap.delete_message.called


@pytest.mark.asyncio
async def test_draft_save_handles_no_appenduid(mock_smtp, mock_imap):
    """Test that save() handles servers without APPENDUID support (returns 0)."""
    from mailcore.types import MessageFlag

    # Server doesn't support APPENDUID - returns 0
    mock_imap.append_message = AsyncMock(return_value=0)
    mock_imap.delete_message = AsyncMock()

    draft = Draft(
        smtp=mock_smtp,
        imap=mock_imap,
        default_sender="me@example.com",
        original_message_uid=42,
        original_message_folder="Drafts",
        original_message_flags={MessageFlag.DRAFT},
        original_custom_flags=set(),
    )
    draft.to("alice@example.com").subject("Test").body("Body")

    # Save (will delete original but can't get new UID)
    uid = await draft.save(folder="Drafts")

    # Returns 0 (no APPENDUID)
    assert uid == 0

    # Original still deleted (replace happened)
    assert mock_imap.delete_message.called

    # Tracking updated to 0 (original UID 42 no longer valid after delete)
    assert draft._original_message_uid == 0

    # Second save won't try to delete UID 0 (None check prevents it)
    mock_imap.delete_message.reset_mock()
    await draft.save(folder="Drafts")
    # delete_message not called because original_uid is 0 (falsy, not None)
    assert not mock_imap.delete_message.called


# ==============================================================================
# Story 3.26: Quote/Forward Body Materialization Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_reply_quote_materialized_on_save(mock_imap, mock_smtp, mock_message):
    """Test AC #1: Reply with quote=True, save to drafts, edit → body contains quote."""
    # Setup mock message with body
    mock_body = AsyncMock()
    mock_body.get_text = AsyncMock(return_value="Original message content")
    mock_message._body = mock_body

    # Create reply with quote
    draft = mock_message.reply(quote=True)
    draft._imap = mock_imap  # Inject IMAP for save
    draft.to("recipient@example.com").subject("Re: Test").body("My response")

    # Save to Drafts
    await draft.save(folder="Drafts")

    # Verify body_text passed to append_message contains BOTH response AND quote
    call_args = mock_imap.append_message.call_args
    saved_body = call_args.kwargs["body_text"]

    assert "My response" in saved_body
    assert "> Original message content" in saved_body
    assert "wrote:" in saved_body


@pytest.mark.asyncio
async def test_forward_body_materialized_on_save(mock_imap, mock_smtp, mock_message):
    """Test AC #2: Forward with include_body=True, save to drafts → body contains forward."""
    # Setup mock message with body
    mock_body = AsyncMock()
    mock_body.get_text = AsyncMock(return_value="Original forwarded content")
    mock_message._body = mock_body

    # Create forward with include_body
    draft = mock_message.forward(include_body=True)
    draft._imap = mock_imap  # Inject IMAP for save
    draft.to("recipient@example.com").subject("Fwd: Test").body("FYI")

    # Save to Drafts
    await draft.save(folder="Drafts")

    # Verify body_text contains BOTH note AND forwarded content
    call_args = mock_imap.append_message.call_args
    saved_body = call_args.kwargs["body_text"]

    assert "FYI" in saved_body
    assert "---------- Forwarded message ---------" in saved_body
    assert "Original forwarded content" in saved_body


@pytest.mark.asyncio
async def test_reply_save_vs_send_consistency(mock_imap, mock_smtp, mock_message):
    """Test AC #3: save() and send() produce identical body for reply with quote."""
    # Setup mock message with body
    mock_body = AsyncMock()
    mock_body.get_text = AsyncMock(return_value="Original text")
    mock_message._body = mock_body

    # Create reply
    draft = mock_message.reply(quote=True)
    draft._imap = mock_imap
    draft.to("recipient@example.com").subject("Re: Test").body("Response")

    # Save and capture body
    await draft.save(folder="Drafts")
    saved_body = mock_imap.append_message.call_args.kwargs["body_text"]

    # Send and capture body
    await draft.send()
    sent_body = mock_smtp.send_message.call_args.kwargs["body_text"]

    # Bodies should be identical
    assert saved_body == sent_body
    assert "Response" in saved_body
    assert "> Original text" in saved_body


@pytest.mark.asyncio
async def test_forward_save_vs_send_consistency(mock_imap, mock_smtp, mock_message):
    """Test AC #3: save() and send() produce identical body for forward with body."""
    # Setup mock message with body
    mock_body = AsyncMock()
    mock_body.get_text = AsyncMock(return_value="Forwarded content")
    mock_message._body = mock_body

    # Create forward
    draft = mock_message.forward(include_body=True)
    draft._imap = mock_imap
    draft.to("recipient@example.com").subject("Fwd: Test").body("Note")

    # Save and capture body
    await draft.save(folder="Drafts")
    saved_body = mock_imap.append_message.call_args.kwargs["body_text"]

    # Send and capture body
    await draft.send()
    sent_body = mock_smtp.send_message.call_args.kwargs["body_text"]

    # Bodies should be identical
    assert saved_body == sent_body
    assert "Note" in saved_body
    assert "Forwarded content" in saved_body


@pytest.mark.asyncio
async def test_no_quote_forward_unchanged_body(mock_imap, mock_smtp):
    """Test AC #4: Draft with NO quote/forward flags saves user body only."""
    # Create plain draft (no quote/forward)
    draft = Draft(smtp=mock_smtp, imap=mock_imap, default_sender="me@example.com")
    draft.to("alice@example.com").subject("Test").body("Just text")

    # Save
    await draft.save(folder="Drafts")

    # Verify body unchanged (no transformations)
    saved_body = mock_imap.append_message.call_args.kwargs["body_text"]
    assert saved_body == "Just text"


@pytest.mark.asyncio
async def test_quote_with_missing_reference_message(mock_imap, mock_smtp):
    """Test AC #5: quote=True with reference_message=None gracefully returns user body."""
    # Create draft with quote=True but NO reference message
    draft = Draft(
        smtp=mock_smtp,
        imap=mock_imap,
        default_sender="me@example.com",
        quote=True,
        reference_message=None,  # Missing reference
    )
    draft.to("alice@example.com").subject("Test").body("Text")

    # Should not crash
    await draft.save(folder="Drafts")

    # Body should be unchanged (graceful fallback)
    saved_body = mock_imap.append_message.call_args.kwargs["body_text"]
    assert saved_body == "Text"


@pytest.mark.asyncio
async def test_forward_with_missing_reference_message(mock_imap, mock_smtp):
    """Test AC #5: include_body=True with reference_message=None gracefully returns user body."""
    # Create draft with include_body=True but NO reference message
    draft = Draft(
        smtp=mock_smtp,
        imap=mock_imap,
        default_sender="me@example.com",
        include_body=True,
        reference_message=None,  # Missing reference
    )
    draft.to("alice@example.com").subject("Test").body("Text")

    # Should not crash
    await draft.save(folder="Drafts")

    # Body should be unchanged (graceful fallback)
    saved_body = mock_imap.append_message.call_args.kwargs["body_text"]
    assert saved_body == "Text"


@pytest.mark.asyncio
async def test_quote_with_empty_user_body(mock_imap, mock_smtp, mock_message):
    """Test quote-only draft (no user text) works correctly."""
    # Setup mock message
    mock_body = AsyncMock()
    mock_body.get_text = AsyncMock(return_value="Original")
    mock_message._body = mock_body

    # Create reply with NO user body
    draft = mock_message.reply(quote=True)
    draft._imap = mock_imap
    draft.to("recipient@example.com").subject("Re: Test")
    # No .body() call - empty user body

    # Save
    await draft.save(folder="Drafts")

    # Should contain only quote
    saved_body = mock_imap.append_message.call_args.kwargs["body_text"]
    assert "> Original" in saved_body
    assert saved_body.startswith("On ")  # Starts with quote header


@pytest.mark.asyncio
async def test_quote_with_multiline_original(mock_imap, mock_smtp, mock_message):
    """Test quote logic handles multiline original messages."""
    # Setup multiline original
    mock_body = AsyncMock()
    mock_body.get_text = AsyncMock(return_value="Line 1\nLine 2\nLine 3\nLine 4\nLine 5")
    mock_message._body = mock_body

    # Create reply
    draft = mock_message.reply(quote=True)
    draft._imap = mock_imap
    draft.to("recipient@example.com").subject("Re: Test").body("Response")

    # Save
    await draft.save(folder="Drafts")

    # Verify each line prefixed with "> "
    saved_body = mock_imap.append_message.call_args.kwargs["body_text"]
    assert "> Line 1" in saved_body
    assert "> Line 2" in saved_body
    assert "> Line 3" in saved_body
    assert "> Line 4" in saved_body
    assert "> Line 5" in saved_body
