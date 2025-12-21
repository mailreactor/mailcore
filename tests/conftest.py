"""pytest configuration and fixtures for mailcore tests.

Story 3.9: Centralized mock fixtures to eliminate duplication across test files.

This module provides centralized AsyncMock fixtures for IMAPConnection and SMTPConnection.
All ABC methods are pre-configured with sensible defaults. Tests can override specific
methods using `mock.method_name.return_value = custom_value` or
`mock.method_name.side_effect = exception`.

Benefits:
- DRY: Single fixture definition used by all tests
- Consistency: All tests use same mock behavior
- Maintainability: Update once, affects all tests
- Discoverability: New tests automatically get fixtures
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock

import pytest

from mailcore.email_address import EmailAddress
from mailcore.message import Message
from mailcore.protocols import IMAPConnection, SMTPConnection
from mailcore.types import FolderInfo, FolderStatus, MessageData, MessageFlag, MessageListData, SendResult

# pytest-asyncio configuration is handled in pyproject.toml [tool.pytest.ini_options]


@pytest.fixture
def mock_imap():
    """Standard mock IMAP with all ABC methods pre-configured.

    Returns AsyncMock(spec=IMAPConnection) with sensible defaults for unit tests.

    Pre-configured return values:
    - query_messages: Empty MessageListData (DTO)
    - fetch_message_body: ("Plain text body", "<p>HTML body</p>")
    - fetch_attachment_content: b"attachment content"
    - update_message_flags: ({MessageFlag.SEEN}, set())
    - move_message: 43 (new UID)
    - copy_message: 44 (new UID)
    - delete_message: None
    - get_folders: []
    - create_folder: FolderInfo with test values
    - delete_folder: None
    - rename_folder: FolderInfo with test values
    - get_folder_status: FolderStatus with reasonable defaults

    Tests can override specific methods:
        mock_imap.query_messages.return_value = custom_result
        mock_imap.fetch_message_body.side_effect = IMAPError()

    Example:
        async def test_folder_list(mock_imap):
            # Uses centralized fixture
            folder = Folder(imap=mock_imap, smtp=None, name="INBOX")

            # Override for this specific test
            mock_imap.query_messages.return_value = MessageListData(
                messages=[create_test_message_data()],
                total_matches=1,
                total_in_folder=100,
                folder="INBOX"
            )

            messages = await folder.list()
            assert len(messages) == 1
    """
    mock = AsyncMock(spec=IMAPConnection)

    # Pre-configure all 12 ABC methods with sensible defaults
    mock.query_messages.return_value = MessageListData(messages=[], total_matches=0, total_in_folder=0, folder="INBOX")
    mock.fetch_message_body.return_value = ("Plain text body", "<p>HTML body</p>")
    mock.fetch_attachment_content.return_value = b"attachment content"
    mock.update_message_flags.return_value = ({MessageFlag.SEEN}, set())
    mock.move_message.return_value = 43
    mock.copy_message.return_value = 44
    mock.delete_message.return_value = None
    mock.get_folders.return_value = []
    mock.create_folder.return_value = FolderInfo(name="NewFolder", flags=[], has_children=False)
    mock.delete_folder.return_value = None
    mock.rename_folder.return_value = FolderInfo(name="RenamedFolder", flags=[], has_children=False)
    mock.get_folder_status.return_value = FolderStatus(message_count=100, unseen_count=10, uidnext=101)

    return mock


@pytest.fixture
def mock_smtp():
    """Standard mock SMTP for sending messages.

    Returns AsyncMock(spec=SMTPConnection) pre-configured to accept all sends.

    Pre-configured return value:
    - send_message: SendResult with test message ID and accepted recipients

    Tests can override or inspect:
        assert mock_smtp.send_message.call_count == 1
        mock_smtp.send_message.side_effect = SMTPError()

    Example:
        async def test_draft_send(mock_smtp):
            # Uses centralized fixture
            draft = Draft(smtp=mock_smtp)
            message_id = await draft.to('alice').subject('Hi').body('Hello').send()

            assert mock_smtp.send_message.call_count == 1
            assert message_id == "<sent-123@example.com>"
    """
    smtp = AsyncMock(spec=SMTPConnection)
    smtp.send_message.return_value = SendResult(
        message_id="<sent-123@example.com>", accepted=["alice@example.com"], rejected={}
    )
    # Story 3.14: Add username property for default_sender validation
    smtp.username = "user@example.com"
    return smtp


@pytest.fixture
def mock_imap_connection():
    """Mock IMAP connection for E2E testing (full implementation).

    Returns MockIMAPConnection with in-memory storage and realistic IMAP behavior.

    For unit tests, use `mock_imap` fixture (AsyncMock) instead.
    For E2E tests, use this fixture for complete workflow validation.

    Example:
        async def test_e2e_send_email(mock_imap_connection, mock_smtp_connection):
            mailbox = Mailbox(imap=mock_imap_connection, smtp=mock_smtp_connection)
            # Full E2E workflow...
    """
    from mocks import MockIMAPConnection

    return MockIMAPConnection()


@pytest.fixture
def mock_smtp_connection():
    """Mock SMTP connection for E2E testing (full implementation).

    Returns MockSMTPConnection with sent message tracking.

    For unit tests, use `mock_smtp` fixture (AsyncMock) instead.
    For E2E tests, use this fixture for send verification.

    Example:
        async def test_e2e_send_email(mock_smtp_connection):
            draft = Draft(smtp=mock_smtp_connection)
            await draft.to('alice').subject('Hi').body('Hello').send()

            assert len(mock_smtp_connection._sent_messages) == 1
            assert mock_smtp_connection._sent_messages[0]['to'][0].email == 'alice@example.com'
    """
    from mocks import MockSMTPConnection

    return MockSMTPConnection()


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
        smtp=None,
        default_sender=None,
        uid=uid,
        folder=folder,
        message_id=message_id,
        from_=EmailAddress(from_email),
        to=[EmailAddress("recipient@example.com")],
        cc=[],
        subject=subject,
        date=datetime.now(timezone.utc),
        flags=set(),
        size=100,
    )


def create_message_data(
    uid: int = 1,
    folder: str = "INBOX",
    message_id: str | None = None,
    subject: str = "Test",
    from_email: str = "sender@example.com",
) -> MessageData:
    """Helper to create a MessageData DTO for testing.

    Args:
        uid: Message UID
        folder: Folder name
        message_id: Message ID (auto-generated if None)
        subject: Subject line
        from_email: Sender email

    Returns:
        MessageData DTO for testing
    """
    if message_id is None:
        message_id = f"<msg-{uid}@example.com>"

    return MessageData(
        uid=uid,
        folder=folder,
        message_id=message_id,
        from_=EmailAddress(from_email),
        to=[EmailAddress("recipient@example.com")],
        cc=[],
        subject=subject,
        date=datetime.now(timezone.utc),
        flags=set(),
        size=100,
        custom_flags=set(),
        in_reply_to=None,
        references=[],
        attachments=[],
    )
