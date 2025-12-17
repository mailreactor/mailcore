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
async def test_send_requires_body_or_html(mock_smtp):
    """Test send() raises ValueError if both body and body_html missing."""
    draft = Draft(smtp=mock_smtp, default_sender="test@example.com")
    draft.to("alice@example.com").subject("Test")

    with pytest.raises(ValueError, match="requires at least one of 'body' or 'body_html'"):
        await draft.send()


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
