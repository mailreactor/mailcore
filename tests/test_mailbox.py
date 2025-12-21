"""Tests for Mailbox class - main entry point for email operations.

Story 3.9: Refactored to use centralized mock fixtures from conftest.py.
Eliminated 2 duplicate fixtures (mock_imap, mock_smtp).
"""

from datetime import datetime

import pytest

from mailcore.draft import Draft
from mailcore.email_address import EmailAddress
from mailcore.folder import Folder
from mailcore.mailbox import FolderDict, Mailbox
from mailcore.message import Message
from mailcore.message_list import MessageList
from mailcore.protocols import IMAPConnection, SMTPConnection
from mailcore.types import FolderInfo


@pytest.fixture
def mailbox(mock_imap: IMAPConnection, mock_smtp: SMTPConnection) -> Mailbox:
    """Create Mailbox instance with mock connections.

    Uses centralized mock_imap and mock_smtp from conftest.py.
    Story 3.14: mock_smtp has username='user@example.com' so auto-detect works.
    """
    return Mailbox(imap=mock_imap, smtp=mock_smtp)


# Test: Constructor stores connections
def test_mailbox_initialization(mock_imap: IMAPConnection, mock_smtp: SMTPConnection) -> None:
    """Test mailbox constructor stores IMAP and SMTP connections."""
    mailbox = Mailbox(imap=mock_imap, smtp=mock_smtp)

    assert mailbox._imap is mock_imap
    assert mailbox._smtp is mock_smtp
    assert isinstance(mailbox._folders, FolderDict)


# Test: inbox property returns Folder
def test_inbox_property_returns_folder(mailbox: Mailbox, mock_imap: IMAPConnection, mock_smtp: SMTPConnection) -> None:
    """Test inbox property creates Folder('INBOX') instance."""
    inbox = mailbox.inbox

    assert isinstance(inbox, Folder)
    assert inbox._name == "INBOX"


# Test: inbox property injects both connections
def test_inbox_property_injects_both_connections(
    mailbox: Mailbox, mock_imap: IMAPConnection, mock_smtp: SMTPConnection
) -> None:
    """Test inbox Folder has both IMAP and SMTP connections."""
    inbox = mailbox.inbox

    assert inbox._imap is mock_imap
    assert inbox._smtp is mock_smtp


# Test: folders dict access returns Folder
def test_folders_dict_access_returns_folder(
    mailbox: Mailbox, mock_imap: IMAPConnection, mock_smtp: SMTPConnection
) -> None:
    """Test folders['Archive'] creates Folder instance."""
    archive = mailbox.folders["Archive"]

    assert isinstance(archive, Folder)
    assert archive._name == "Archive"
    assert archive._imap is mock_imap
    assert archive._smtp is mock_smtp


# Test: FolderDict no caching
def test_folders_dict_creates_new_folder_each_time(mailbox: Mailbox) -> None:
    """Test FolderDict returns new Folder instance every time (no caching)."""
    folder1 = mailbox.folders["Archive"]
    folder2 = mailbox.folders["Archive"]

    assert folder1 is not folder2  # Different instances


# Test: list_folders calls IMAP
@pytest.mark.asyncio
async def test_list_folders_calls_imap(mailbox: Mailbox, mock_imap: IMAPConnection) -> None:
    """Test list_folders() calls imap.get_folders()."""
    # Mock response
    mock_imap.get_folders.return_value = [
        FolderInfo(name="INBOX", flags=[], has_children=False),
        FolderInfo(name="Sent", flags=["\\Sent"], has_children=False),
        FolderInfo(name="Archive", flags=[], has_children=False),
    ]

    folders = await mailbox.list_folders()

    mock_imap.get_folders.assert_called_once()
    assert folders == ["INBOX", "Sent", "Archive"]


# Test: list_folders with pattern
@pytest.mark.asyncio
async def test_list_folders_with_pattern(mailbox: Mailbox, mock_imap: IMAPConnection) -> None:
    """Test list_folders(pattern) filters folders by glob pattern."""
    # Mock response
    mock_imap.get_folders.return_value = [
        FolderInfo(name="Projects/2025", flags=[], has_children=False),
        FolderInfo(name="Projects/2024", flags=[], has_children=False),
        FolderInfo(name="Archive", flags=[], has_children=False),
    ]

    folders = await mailbox.list_folders("Projects/*")

    mock_imap.get_folders.assert_called_once()
    assert folders == ["Projects/2025", "Projects/2024"]


# Test: create_folder calls IMAP and returns Folder
@pytest.mark.asyncio
async def test_create_folder_calls_imap_and_returns_folder(
    mailbox: Mailbox, mock_imap: IMAPConnection, mock_smtp: SMTPConnection
) -> None:
    """Test create_folder() calls imap.create_folder() and returns Folder."""
    folder = await mailbox.create_folder("Archive")

    mock_imap.create_folder.assert_called_once_with(name="Archive")
    assert isinstance(folder, Folder)
    assert folder._name == "Archive"
    assert folder._imap is mock_imap
    assert folder._smtp is mock_smtp


# Test: delete_folder calls IMAP
@pytest.mark.asyncio
async def test_delete_folder_calls_imap(mailbox: Mailbox, mock_imap: IMAPConnection) -> None:
    """Test delete_folder() calls imap.delete_folder()."""
    await mailbox.delete_folder("Archive")

    mock_imap.delete_folder.assert_called_once_with(name="Archive")


# Test: rename_folder calls IMAP
@pytest.mark.asyncio
async def test_rename_folder_calls_imap(mailbox: Mailbox, mock_imap: IMAPConnection) -> None:
    """Test rename_folder() calls imap.rename_folder()."""
    await mailbox.rename_folder("Old", "New")

    mock_imap.rename_folder.assert_called_once_with(old_name="Old", new_name="New")


# Test: send composes and sends in one call
@pytest.mark.asyncio
async def test_send_composes_and_sends_in_one_call(mailbox: Mailbox, mock_smtp: SMTPConnection) -> None:
    """Test send() creates Draft and sends in one call."""
    from mailcore.types import SendResult

    # Mock send_message to return message_id
    mock_smtp.send_message.return_value = SendResult(
        message_id="<msg-123@example.com>",
        accepted=["alice@example.com"],
        rejected={},
    )

    message_id = await mailbox.send(to="alice@example.com", subject="Hello", body="World")

    assert message_id == "<msg-123@example.com>"
    mock_smtp.send_message.assert_called_once()


# Test: send with all parameters
@pytest.mark.asyncio
async def test_send_with_all_parameters(mailbox: Mailbox, mock_smtp: SMTPConnection) -> None:
    """Test send(to, cc, bcc, subject, body, body_html) passes all parameters."""
    from mailcore.types import SendResult

    mock_smtp.send_message.return_value = SendResult(
        message_id="<msg-123@example.com>",
        accepted=["alice@example.com"],
        rejected={},
    )

    message_id = await mailbox.send(
        to=["alice@example.com", "bob@example.com"],
        cc="manager@example.com",
        bcc="archive@example.com",
        subject="Report",
        body="Text version",
        body_html="<h1>HTML version</h1>",
    )

    assert message_id == "<msg-123@example.com>"
    mock_smtp.send_message.assert_called_once()


# Test: compose returns Draft with SMTP
def test_compose_returns_draft_with_smtp(mailbox: Mailbox, mock_smtp: SMTPConnection) -> None:
    """Test compose() returns Draft with SMTP connection."""
    draft = mailbox.draft()

    assert isinstance(draft, Draft)
    assert draft._smtp is mock_smtp


# Test: move groups by folder and calls IMAP
@pytest.mark.asyncio
async def test_move_groups_by_folder_and_calls_imap(mailbox: Mailbox, mock_imap: IMAPConnection) -> None:
    """Test move() groups messages by folder and calls imap.move_message() per folder."""
    # Create messages from different folders
    msg1 = Message(
        imap=mock_imap,
        smtp=None,
        default_sender=None,
        uid=1,
        folder="INBOX",
        message_id="<msg1@example.com>",
        from_=EmailAddress("sender@example.com"),
        to=[EmailAddress("recipient@example.com")],
        cc=[],
        subject="Message 1",
        date=datetime.now(),
        flags=[],
        size=1024,
    )
    msg2 = Message(
        imap=mock_imap,
        smtp=None,
        default_sender=None,
        uid=2,
        folder="INBOX",
        message_id="<msg2@example.com>",
        from_=EmailAddress("sender@example.com"),
        to=[EmailAddress("recipient@example.com")],
        cc=[],
        subject="Message 2",
        date=datetime.now(),
        flags=[],
        size=1024,
    )
    msg3 = Message(
        imap=mock_imap,
        smtp=None,
        default_sender=None,
        uid=10,
        folder="Archive",
        message_id="<msg3@example.com>",
        from_=EmailAddress("sender@example.com"),
        to=[EmailAddress("recipient@example.com")],
        cc=[],
        subject="Message 3",
        date=datetime.now(),
        flags=[],
        size=1024,
    )

    messages = [msg1, msg2, msg3]

    await mailbox.move(messages, to_folder="Spam")

    # Should call move_message 3 times (2 from INBOX, 1 from Archive)
    assert mock_imap.move_message.call_count == 3


# Test: move accepts MessageList
@pytest.mark.asyncio
async def test_move_accepts_message_list(mailbox: Mailbox, mock_imap: IMAPConnection) -> None:
    """Test move(MessageList) works."""
    msg1 = Message(
        imap=mock_imap,
        smtp=None,
        default_sender=None,
        uid=1,
        folder="INBOX",
        message_id="<msg1@example.com>",
        from_=EmailAddress("sender@example.com"),
        to=[EmailAddress("recipient@example.com")],
        cc=[],
        subject="Message 1",
        date=datetime.now(),
        flags=[],
        size=1024,
    )

    message_list = MessageList(
        messages=[msg1],
        total_matches=1,
        total_in_folder=100,
        folder="INBOX",
    )

    await mailbox.move(message_list, to_folder="Spam")

    mock_imap.move_message.assert_called_once_with(uid=1, from_folder="INBOX", to_folder="Spam")


# Test: copy groups by folder and calls IMAP
@pytest.mark.asyncio
async def test_copy_groups_by_folder_and_calls_imap(mailbox: Mailbox, mock_imap: IMAPConnection) -> None:
    """Test copy() groups messages by folder and calls imap.copy_message()."""
    msg1 = Message(
        imap=mock_imap,
        smtp=None,
        default_sender=None,
        uid=1,
        folder="INBOX",
        message_id="<msg1@example.com>",
        from_=EmailAddress("sender@example.com"),
        to=[EmailAddress("recipient@example.com")],
        cc=[],
        subject="Message 1",
        date=datetime.now(),
        flags=[],
        size=1024,
    )

    await mailbox.copy([msg1], to_folder="Archive")

    mock_imap.copy_message.assert_called_once_with(uid=1, from_folder="INBOX", to_folder="Archive")


# Test: delete non-permanent moves to Trash
@pytest.mark.asyncio
async def test_delete_non_permanent_moves_to_trash(mailbox: Mailbox, mock_imap: IMAPConnection) -> None:
    """Test delete(permanent=False) moves to Trash."""
    msg1 = Message(
        imap=mock_imap,
        smtp=None,
        default_sender=None,
        uid=1,
        folder="INBOX",
        message_id="<msg1@example.com>",
        from_=EmailAddress("sender@example.com"),
        to=[EmailAddress("recipient@example.com")],
        cc=[],
        subject="Message 1",
        date=datetime.now(),
        flags=[],
        size=1024,
    )

    await mailbox.delete([msg1], permanent=False, trash_folder="Trash")

    mock_imap.move_message.assert_called_once_with(uid=1, from_folder="INBOX", to_folder="Trash")
    mock_imap.delete_message.assert_not_called()


# Test: delete permanent calls delete_message
@pytest.mark.asyncio
async def test_delete_permanent_calls_delete_message(mailbox: Mailbox, mock_imap: IMAPConnection) -> None:
    """Test delete(permanent=True) calls imap.delete_message()."""
    msg1 = Message(
        imap=mock_imap,
        smtp=None,
        default_sender=None,
        uid=1,
        folder="INBOX",
        message_id="<msg1@example.com>",
        from_=EmailAddress("sender@example.com"),
        to=[EmailAddress("recipient@example.com")],
        cc=[],
        subject="Message 1",
        date=datetime.now(),
        flags=[],
        size=1024,
    )

    await mailbox.delete([msg1], permanent=True)

    mock_imap.delete_message.assert_called_once_with(folder="INBOX", uid=1)
    mock_imap.move_message.assert_not_called()


# Test: delete without trash_folder raises ValueError
@pytest.mark.asyncio
async def test_delete_without_trash_folder_raises(mailbox: Mailbox, mock_imap: IMAPConnection) -> None:
    """Test delete(permanent=False) without trash_folder raises ValueError."""
    msg1 = Message(
        imap=mock_imap,
        smtp=None,
        default_sender=None,
        uid=1,
        folder="INBOX",
        message_id="<msg1@example.com>",
        from_=EmailAddress("sender@example.com"),
        to=[EmailAddress("recipient@example.com")],
        cc=[],
        subject="Message 1",
        date=datetime.now(),
        flags=[],
        size=1024,
    )

    with pytest.raises(ValueError, match="trash_folder parameter required"):
        await mailbox.delete([msg1], permanent=False)


# Test: get searches all folders for message
@pytest.mark.asyncio
async def test_get_searches_all_folders_for_message(
    mailbox: Mailbox, mock_imap: IMAPConnection, mock_smtp: SMTPConnection
) -> None:
    """Test get() searches all folders and returns message from Sent."""
    # Mock get_folders to return folder list
    mock_imap.get_folders.return_value = [
        FolderInfo(name="INBOX", flags=[], has_children=False),
        FolderInfo(name="Sent", flags=["\\Sent"], has_children=False),
    ]

    # Mock query_messages to return empty for INBOX, message for Sent
    target_message = Message(
        imap=mock_imap,
        smtp=None,
        default_sender=None,
        uid=42,
        folder="Sent",
        message_id="<msg-123@example.com>",
        from_=EmailAddress("sender@example.com"),
        to=[EmailAddress("recipient@example.com")],
        cc=[],
        subject="Test",
        date=datetime.now(),
        flags=[],
        size=1024,
    )

    inbox_result = MessageList(messages=[], total_matches=0, total_in_folder=10, folder="INBOX")
    sent_result = MessageList(messages=[target_message], total_matches=1, total_in_folder=5, folder="Sent")

    mock_imap.query_messages.side_effect = [inbox_result, sent_result]

    message = await mailbox.get("<msg-123@example.com>")

    assert message is not None
    assert message.message_id == "<msg-123@example.com>"
    assert message.folder == "Sent"
    assert message._smtp is mock_smtp


# Test: get returns None if not found
@pytest.mark.asyncio
async def test_get_returns_none_if_not_found(mailbox: Mailbox, mock_imap: IMAPConnection) -> None:
    """Test get() returns None if message not found in any folder."""
    # Mock get_folders
    mock_imap.get_folders.return_value = [
        FolderInfo(name="INBOX", flags=[], has_children=False),
        FolderInfo(name="Sent", flags=["\\Sent"], has_children=False),
    ]

    # Mock query_messages to return empty for all folders
    empty_result = MessageList(messages=[], total_matches=0, total_in_folder=0, folder="INBOX")
    mock_imap.query_messages.return_value = empty_result

    message = await mailbox.get("<not-found@example.com>")

    assert message is None


# Test: FolderDict initialization
def test_folder_dict_initialization(mock_imap: IMAPConnection, mock_smtp: SMTPConnection) -> None:
    """Test FolderDict stores connections."""
    folder_dict = FolderDict(imap=mock_imap, smtp=mock_smtp, default_sender="test@example.com")

    assert folder_dict._imap is mock_imap
    assert folder_dict._smtp is mock_smtp


# Test: FolderDict __getitem__ creates Folder
def test_folder_dict_getitem_creates_folder(mock_imap: IMAPConnection, mock_smtp: SMTPConnection) -> None:
    """Test FolderDict['Name'] creates Folder with connections."""
    folder_dict = FolderDict(imap=mock_imap, smtp=mock_smtp, default_sender="test@example.com")

    folder = folder_dict["Archive"]

    assert isinstance(folder, Folder)
    assert folder._name == "Archive"
    assert folder._imap is mock_imap
    assert folder._smtp is mock_smtp


# Test: FolderDict no caching
def test_folder_dict_no_caching(mock_imap: IMAPConnection, mock_smtp: SMTPConnection) -> None:
    """Test FolderDict returns new instance every time (no caching)."""
    folder_dict = FolderDict(imap=mock_imap, smtp=mock_smtp, default_sender="test@example.com")

    folder1 = folder_dict["Archive"]
    folder2 = folder_dict["Archive"]

    assert folder1 is not folder2  # Different instances


# Story 3.14: default_sender validation tests


def test_mailbox_auto_detects_email_username(mock_imap: IMAPConnection, mock_smtp: SMTPConnection) -> None:
    """Test Mailbox auto-detects smtp.username when it's a valid email."""
    mock_smtp.username = "user@gmail.com"
    mailbox = Mailbox(imap=mock_imap, smtp=mock_smtp)

    assert mailbox._default_sender == "user@gmail.com"


def test_mailbox_rejects_non_email_username(mock_imap: IMAPConnection, mock_smtp: SMTPConnection) -> None:
    """Test Mailbox raises ValueError when smtp.username is not email and no default_sender provided."""
    mock_smtp.username = "john.smith"

    with pytest.raises(ValueError, match="Cannot use SMTP username"):
        Mailbox(imap=mock_imap, smtp=mock_smtp)


def test_mailbox_accepts_valid_default_sender(mock_imap: IMAPConnection, mock_smtp: SMTPConnection) -> None:
    """Test Mailbox accepts explicit default_sender parameter."""
    mock_smtp.username = "john.smith"
    mailbox = Mailbox(imap=mock_imap, smtp=mock_smtp, default_sender="me@example.com")

    assert mailbox._default_sender == "me@example.com"


def test_mailbox_rejects_invalid_default_sender(mock_imap: IMAPConnection, mock_smtp: SMTPConnection) -> None:
    """Test Mailbox raises ValueError when default_sender is invalid."""
    with pytest.raises(ValueError, match="Invalid default_sender"):
        Mailbox(imap=mock_imap, smtp=mock_smtp, default_sender="invalid")


def test_mailbox_repr(mock_imap: IMAPConnection, mock_smtp: SMTPConnection) -> None:
    """Verify Mailbox repr shows default_sender."""
    mock_smtp.username = "user@example.com"
    mailbox = Mailbox(imap=mock_imap, smtp=mock_smtp, default_sender="me@example.com")

    assert repr(mailbox) == "Mailbox(default_sender='me@example.com')"
