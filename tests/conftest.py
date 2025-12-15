"""pytest configuration and fixtures for mailcore tests."""

from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from mailcore.message import Message
from mailcore.types import EmailAddress

# pytest-asyncio configuration is handled in pyproject.toml [tool.pytest.ini_options]


@pytest.fixture
def mock_imap_connection():
    """Mock IMAP connection for testing."""
    # TODO: Story 3.9 will implement MockIMAPConnection
    return None


@pytest.fixture
def mock_smtp_connection():
    """Mock SMTP connection for testing."""
    # TODO: Story 3.9 will implement MockSMTPConnection
    return None


def create_mock_message(
    uid: int = 1,
    folder: str = "INBOX",
    message_id: str | None = None,
    subject: str = "Test",
    from_email: str = "sender@example.com",
    mock_imap: Mock | None = None,
) -> Message:
    """Helper to create a mock Message for testing.

    Args:
        uid: Message UID
        folder: Folder name
        message_id: Message ID (auto-generated if None)
        subject: Subject line
        from_email: Sender email
        mock_imap: Mock IMAP connection (creates one if None)

    Returns:
        Message instance for testing
    """
    if mock_imap is None:
        mock_imap = Mock()

    if message_id is None:
        message_id = f"<msg-{uid}@example.com>"

    return Message(
        imap=mock_imap,
        uid=uid,
        folder=folder,
        message_id=message_id,
        from_=EmailAddress(from_email),
        to=[EmailAddress("recipient@example.com")],
        cc=[],
        subject=subject,
        date=datetime.now(timezone.utc),
        flags=[],
        size=100,
    )
