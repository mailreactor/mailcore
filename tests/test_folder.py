"""Tests for Folder in folder.py."""

from unittest.mock import AsyncMock

import pytest

from mailcore.folder import Folder
from mailcore.message import Message
from mailcore.message_list import MessageList
from mailcore.protocols import IMAPConnection, SMTPConnection


@pytest.fixture
def mock_imap() -> AsyncMock:
    """Create mock IMAPConnection."""
    mock = AsyncMock(spec=IMAPConnection)
    return mock


@pytest.fixture
def mock_smtp() -> AsyncMock:
    """Create mock SMTPConnection."""
    mock = AsyncMock(spec=SMTPConnection)
    return mock


@pytest.fixture
def folder(mock_imap: AsyncMock, mock_smtp: AsyncMock) -> Folder:
    """Create Folder instance with mock connections."""
    return Folder(imap=mock_imap, smtp=mock_smtp, name="INBOX")


def test_folder_initialization(mock_imap: AsyncMock, mock_smtp: AsyncMock) -> None:
    """Verify Folder constructor stores imap, smtp, name correctly."""
    folder = Folder(imap=mock_imap, smtp=mock_smtp, name="INBOX")
    assert folder._imap is mock_imap
    assert folder._smtp is mock_smtp
    assert folder._name == "INBOX"
    assert folder._query_parts == []


def test_folder_fluent_chaining(folder: Folder) -> None:
    """Verify fluent methods return NEW instances (immutable) and are chainable."""
    result1 = folder.from_("alice")
    assert result1 is not folder  # Returns NEW instance
    assert len(folder._query_parts) == 0  # Original unchanged
    assert len(result1._query_parts) == 1  # New has filter

    result2 = result1.unseen()
    assert result2 is not result1  # Returns NEW instance
    assert len(result1._query_parts) == 1  # Previous unchanged
    assert len(result2._query_parts) == 2  # New has both filters

    # Verify chaining works
    chain_result = folder.from_("bob").to("charlie").flagged()
    assert chain_result is not folder
    assert len(folder._query_parts) == 0  # Original still unchanged
    assert len(chain_result._query_parts) == 3  # Chain accumulated


def test_folder_builds_query_correctly(folder: Folder) -> None:
    """Verify fluent methods build correct Query objects in _query_parts."""
    f1 = folder.from_("alice@example.com")
    assert len(f1._query_parts) == 1
    assert f1._query_parts[0].to_imap_criteria() == ["FROM", "alice@example.com"]

    f2 = f1.unseen()
    assert len(f2._query_parts) == 2
    assert f2._query_parts[1].to_imap_criteria() == ["UNSEEN"]

    f3 = f2.subject("test")
    assert len(f3._query_parts) == 3
    assert f3._query_parts[2].to_imap_criteria() == ["SUBJECT", "test"]


@pytest.mark.asyncio
async def test_folder_list_calls_imap(folder: Folder, mock_imap: AsyncMock, mock_smtp: AsyncMock) -> None:
    """Verify list() calls imap.query_messages with correct params."""
    # Setup mock to return MessageList
    message_list = MessageList(
        messages=[],
        total_matches=5,
        total_in_folder=10,
        folder="INBOX",
    )
    mock_imap.query_messages.return_value = message_list

    # Call list() on the filtered folder
    filtered = folder.from_("alice").unseen()
    result = await filtered.list(limit=50, offset=0)

    # Verify IMAP was called
    mock_imap.query_messages.assert_called_once()
    call_args = mock_imap.query_messages.call_args

    # Verify folder name
    assert call_args[0][0] == "INBOX"

    # Verify query built correctly (Q.from_('alice') & Q.unseen())
    query = call_args[0][1]
    assert query.to_imap_criteria() == ["FROM", "alice", "UNSEEN"]

    # Verify limit/offset
    assert call_args[1]["limit"] == 50
    assert call_args[1]["offset"] == 0

    assert result is message_list


@pytest.mark.asyncio
async def test_folder_injects_smtp(folder: Folder, mock_imap: AsyncMock, mock_smtp: AsyncMock) -> None:
    """Verify messages returned from list() have ._smtp injected."""
    # Create mock messages without SMTP
    msg1 = Message(uid="1", folder="INBOX")
    msg1._smtp = None

    msg2 = Message(uid="2", folder="INBOX")
    msg2._smtp = None

    message_list = MessageList(
        messages=[msg1, msg2],
        total_matches=2,
        total_in_folder=2,
        folder="INBOX",
    )

    mock_imap.query_messages.return_value = message_list

    # Call list()
    result = await folder.list()

    # Verify SMTP injected
    assert result[0]._smtp is mock_smtp
    assert result[1]._smtp is mock_smtp


@pytest.mark.asyncio
async def test_folder_list_with_pagination(folder: Folder, mock_imap: AsyncMock) -> None:
    """Verify limit and offset passed to IMAP correctly."""
    message_list = MessageList(
        messages=[],
        total_matches=100,
        total_in_folder=100,
        folder="INBOX",
    )
    mock_imap.query_messages.return_value = message_list

    await folder.list(limit=20, offset=40)

    call_args = mock_imap.query_messages.call_args
    assert call_args[1]["limit"] == 20
    assert call_args[1]["offset"] == 40


@pytest.mark.asyncio
async def test_folder_first_returns_first_message(folder: Folder, mock_imap: AsyncMock, mock_smtp: AsyncMock) -> None:
    """Verify first() returns first message or None when empty."""
    # Test with messages
    msg = Message(uid="1", folder="INBOX")
    msg._smtp = None

    message_list = MessageList(
        messages=[msg],
        total_matches=1,
        total_in_folder=1,
        folder="INBOX",
    )
    mock_imap.query_messages.return_value = message_list

    result = await folder.first()
    assert result is msg
    assert result._smtp is mock_smtp

    # Verify limit=1 was passed
    call_args = mock_imap.query_messages.call_args
    assert call_args[1]["limit"] == 1

    # Test with empty result
    empty_list = MessageList(
        messages=[],
        total_matches=0,
        total_in_folder=0,
        folder="INBOX",
    )
    mock_imap.query_messages.return_value = empty_list

    result = await folder.first()
    assert result is None


@pytest.mark.asyncio
async def test_folder_first_with_kwargs(folder: Folder, mock_imap: AsyncMock) -> None:
    """Verify first(from_='alice') applies kwargs then returns first."""
    msg = Message(uid="1", folder="INBOX")
    msg._smtp = None

    message_list = MessageList(
        messages=[msg],
        total_matches=1,
        total_in_folder=1,
        folder="INBOX",
    )
    mock_imap.query_messages.return_value = message_list

    # Call first() with kwargs
    result = await folder.first(from_="alice@example.com")

    # Verify query includes from_ filter
    call_args = mock_imap.query_messages.call_args
    query = call_args[0][1]
    assert "FROM" in query.to_imap_criteria()
    assert "alice@example.com" in query.to_imap_criteria()

    assert result is msg


@pytest.mark.asyncio
async def test_folder_count(folder: Folder, mock_imap: AsyncMock) -> None:
    """Verify count() returns total_matches from MessageList."""
    message_list = MessageList(
        messages=[],
        total_matches=42,
        total_in_folder=100,
        folder="INBOX",
    )
    mock_imap.query_messages.return_value = message_list

    folder.from_("alice")
    result = await folder.count()

    # Verify count returned
    assert result == 42

    # Verify IMAP was called with limit=0 (optimization)
    call_args = mock_imap.query_messages.call_args
    assert call_args[1]["limit"] == 0


def test_folder_all_fluent_methods(folder: Folder) -> None:
    """Verify all fluent filter methods work and return NEW instances."""
    # Test each fluent method returns new instance
    assert folder.to("bob@example.com") is not folder
    assert folder.body("hello") is not folder
    assert folder.seen() is not folder
    assert folder.answered() is not folder
    assert folder.deleted() is not folder
    assert folder.draft() is not folder
    assert folder.recent() is not folder

    # Verify original is unchanged
    assert len(folder._query_parts) == 0

    # Build a chain and verify accumulation
    chained = folder.to("bob").body("hello").seen().answered().deleted().draft().recent()
    assert len(chained._query_parts) == 7


@pytest.mark.asyncio
async def test_folder_immutability_reuse(folder: Folder) -> None:
    """Verify folder can be safely reused without state pollution (HC's issue)."""
    # Save reference to folder
    myinbox = folder

    # Apply first filter
    f1 = myinbox.from_("alice")
    assert len(myinbox._query_parts) == 0  # Original unchanged
    assert len(f1._query_parts) == 1

    # Apply second filter to SAME original folder
    f2 = myinbox.from_("bob")
    assert len(myinbox._query_parts) == 0  # Still unchanged
    assert len(f2._query_parts) == 1  # Only has bob, NOT alice+bob

    # Verify f1 is also unchanged
    assert len(f1._query_parts) == 1  # Still only alice

    # Can create branches from intermediate filters
    alice_msgs = myinbox.from_("alice")
    urgent = alice_msgs.subject("urgent")
    reports = alice_msgs.subject("report")

    assert len(urgent._query_parts) == 2  # alice + urgent
    assert len(reports._query_parts) == 2  # alice + report
    assert urgent._query_parts[1].to_imap_criteria() == ["SUBJECT", "urgent"]
    assert reports._query_parts[1].to_imap_criteria() == ["SUBJECT", "report"]


@pytest.mark.asyncio
async def test_folder_first_with_invalid_kwarg(folder: Folder, mock_imap: AsyncMock) -> None:
    """Verify first() with invalid kwargs doesn't break."""
    msg = Message(uid="1", folder="INBOX")
    msg._smtp = None

    message_list = MessageList(
        messages=[msg],
        total_matches=1,
        total_in_folder=1,
        folder="INBOX",
    )
    mock_imap.query_messages.return_value = message_list

    # Call first() with invalid kwarg (should be ignored)
    result = await folder.first(invalid_param="ignored")

    # Should still work
    assert result is msg
