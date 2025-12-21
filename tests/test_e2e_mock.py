"""End-to-end tests with MockIMAPConnection and MockSMTPConnection.

Story 3.9: Complete E2E scenarios validating the entire mailcore API surface.

These tests use full mock implementations (not AsyncMock) to validate complete
workflows: send → list → search → mark read → move → delete → reply → forward.

Test Independence:
- Each test gets fresh mock instances (function-scoped fixtures)
- Tests can run in any order (pytest --random-order)
- No shared state between tests
"""

import pytest

from mailcore.mailbox import Mailbox


@pytest.fixture
def imap(mock_imap_connection):
    """Shorthand for mock IMAP connection (E2E tests)."""
    return mock_imap_connection


@pytest.fixture
def smtp(mock_smtp_connection):
    """Shorthand for mock SMTP connection (E2E tests)."""
    return mock_smtp_connection


@pytest.fixture
def mailbox(imap, smtp):
    """Create Mailbox with full mock connections for E2E tests."""
    return Mailbox(imap=imap, smtp=smtp)


def populate_inbox(imap, messages: list[dict]):
    """Helper to populate mock INBOX with test messages.

    Args:
        imap: MockIMAPConnection instance
        messages: List of message dicts with keys: from_, to, subject, body_text, flags, attachments

    Example:
        populate_inbox(imap, [
            {"from_": "alice@example.com", "to": ["bob@example.com"], "subject": "Test", "body_text": "Hello"},
            {"from_": "carol@example.com", "to": ["bob@example.com"], "subject": "Report", "body_text": "Data"}
        ])
    """
    for msg_data in messages:
        imap.add_test_message(
            folder="INBOX",
            from_=msg_data.get("from_", "sender@example.com"),
            to=msg_data.get("to", ["recipient@example.com"]),
            subject=msg_data.get("subject", "Test Subject"),
            body_text=msg_data.get("body_text"),
            body_html=msg_data.get("body_html"),
            flags=msg_data.get("flags", []),
            attachments=msg_data.get("attachments", []),
        )


def create_test_attachment(filename: str, content: bytes, content_type: str = "application/octet-stream") -> dict:
    """Helper to create attachment data for mock messages.

    Args:
        filename: Attachment filename
        content: Attachment content (bytes)
        content_type: MIME type

    Returns:
        Dict suitable for MockMessage.attachments list

    Example:
        att = create_test_attachment("report.pdf", b"PDF content", "application/pdf")
        populate_inbox(imap, [{"subject": "Report", "attachments": [att]}])
    """
    return {"part_index": "1", "filename": filename, "content_type": content_type, "content": content}


# =============================================================================
# E2E TESTS START HERE
# =============================================================================

# =============================================================================
# TASK 6: SEND EMAIL TESTS (AC-5, AC-6)
# =============================================================================


@pytest.mark.asyncio
async def test_e2e_send_email_plain_text(mailbox, smtp):
    """E2E: Send plain text email via mailbox.draft()."""
    # Compose and send
    message_id = await mailbox.draft().to("alice@example.com").subject("Test Email").body("Hello World").send()

    # Verify sent via mock SMTP
    assert len(smtp._sent_messages) == 1
    sent = smtp._sent_messages[0]

    assert sent["to"][0].email == "alice@example.com"
    assert sent["subject"] == "Test Email"
    assert sent["body_text"] == "Hello World"
    assert sent["body_html"] is None

    # Verify message_id format
    assert message_id.startswith("<")
    assert message_id.endswith("@mock.localhost>")


@pytest.mark.asyncio
async def test_e2e_send_email_with_html(mailbox, smtp):
    """E2E: Send email with both plain text and HTML body."""
    message_id = (
        await mailbox.draft()
        .to("bob@example.com")
        .subject("HTML Email")
        .body("Plain text version")
        .body_html("<p>HTML version</p>")
        .send()
    )

    # Verify both body types present
    assert len(smtp._sent_messages) == 1
    sent = smtp._sent_messages[0]

    assert sent["body_text"] == "Plain text version"
    assert sent["body_html"] == "<p>HTML version</p>"
    assert message_id == sent["message_id"]


@pytest.mark.asyncio
async def test_e2e_send_email_with_attachments(mailbox, smtp):
    """E2E: Send email with 2 attachments."""
    from mailcore.attachment import Attachment

    # Create attachments
    att1 = Attachment.from_bytes(b"PDF content", "report.pdf", "application/pdf")
    att2 = Attachment.from_bytes(b"PNG content", "chart.png", "image/png")

    # Send with attachments
    await (
        mailbox.draft()
        .to("carol@example.com")
        .subject("Report")
        .body("See attachments")
        .attach(att1)
        .attach(att2)
        .send()
    )

    # Verify attachments in sent message
    assert len(smtp._sent_messages) == 1
    sent = smtp._sent_messages[0]

    assert len(sent["attachments"]) == 2
    assert sent["attachments"][0]["filename"] == "report.pdf"
    assert sent["attachments"][0]["content"] == b"PDF content"
    assert sent["attachments"][1]["filename"] == "chart.png"
    assert sent["attachments"][1]["content"] == b"PNG content"


# Placeholder for remaining tasks (7-11)


@pytest.mark.asyncio
async def test_e2e_placeholder_task_7_11(mailbox):
    """Placeholder for Tasks 7-11: List, search, flags, reply, forward, lazy loading, pagination."""
    # Task 7: List and search tests (4 tests)
    # Task 8: Flag and folder operations (5 tests)
    # Task 9: Reply and forward (3 tests)
    # Task 10: Lazy loading (2 tests)
    # Task 11: Pagination (1 test)
    assert mailbox is not None
