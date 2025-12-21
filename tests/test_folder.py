"""Tests for Folder in folder.py.

Story 3.9: Refactored to use centralized mock fixtures from conftest.py.
Eliminated 2 duplicate fixtures (mock_imap, mock_smtp).
"""

from unittest.mock import AsyncMock

import pytest
from conftest import create_message_data

from mailcore.folder import Folder
from mailcore.message_list import MessageList
from mailcore.types import MessageListData


@pytest.fixture
def folder(mock_imap: AsyncMock, mock_smtp: AsyncMock) -> Folder:
    """Create Folder instance with mock connections.

    Uses centralized mock_imap and mock_smtp from conftest.py.
    """
    return Folder(imap=mock_imap, smtp=mock_smtp, name="INBOX", default_sender="test@example.com")


def test_folder_initialization(mock_imap: AsyncMock, mock_smtp: AsyncMock) -> None:
    """Verify Folder constructor stores imap, smtp, name correctly."""
    folder = Folder(imap=mock_imap, smtp=mock_smtp, name="INBOX", default_sender="test@example.com")
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
    # Setup mock to return MessageListData (DTO)
    list_data = MessageListData(
        messages=[],
        total_matches=5,
        total_in_folder=10,
        folder="INBOX",
    )
    mock_imap.query_messages.return_value = list_data

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

    # Verify MessageList created from DTO with correct values
    assert isinstance(result, MessageList)
    assert result.total_matches == 5
    assert result.total_in_folder == 10
    assert result.folder == "INBOX"


@pytest.mark.asyncio
async def test_folder_injects_smtp(folder: Folder, mock_imap: AsyncMock, mock_smtp: AsyncMock) -> None:
    """Verify messages returned from list() have ._smtp injected."""
    # Create MessageData DTOs (no SMTP at DTO level)
    data1 = create_message_data(uid=1, folder="INBOX")
    data2 = create_message_data(uid=2, folder="INBOX")

    list_data = MessageListData(
        messages=[data1, data2],
        total_matches=2,
        total_in_folder=2,
        folder="INBOX",
    )

    mock_imap.query_messages.return_value = list_data

    # Call list() - converts DTOs to entities with SMTP
    result = await folder.list()

    # Verify SMTP injected during entity creation
    assert result[0]._smtp is mock_smtp
    assert result[1]._smtp is mock_smtp


@pytest.mark.asyncio
async def test_folder_list_with_pagination(folder: Folder, mock_imap: AsyncMock) -> None:
    """Verify limit and offset passed to IMAP correctly."""
    list_data = MessageListData(
        messages=[],
        total_matches=100,
        total_in_folder=100,
        folder="INBOX",
    )
    mock_imap.query_messages.return_value = list_data

    await folder.list(limit=20, offset=40)

    call_args = mock_imap.query_messages.call_args
    assert call_args[1]["limit"] == 20
    assert call_args[1]["offset"] == 40


@pytest.mark.asyncio
async def test_folder_first_returns_first_message(folder: Folder, mock_imap: AsyncMock, mock_smtp: AsyncMock) -> None:
    """Verify first() returns first message or None when empty."""
    # Test with messages - use DTO
    data = create_message_data(uid=1, folder="INBOX")

    list_data = MessageListData(
        messages=[data],
        total_matches=1,
        total_in_folder=1,
        folder="INBOX",
    )
    mock_imap.query_messages.return_value = list_data

    result = await folder.first()
    assert result is not None
    assert result.uid == 1
    assert result._smtp is mock_smtp

    # Verify limit=1 was passed
    call_args = mock_imap.query_messages.call_args
    assert call_args[1]["limit"] == 1

    # Test with empty result
    empty_list = MessageListData(
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
    data = create_message_data(uid=1, folder="INBOX", from_email="sender@example.com")

    list_data = MessageListData(
        messages=[data],
        total_matches=1,
        total_in_folder=1,
        folder="INBOX",
    )
    mock_imap.query_messages.return_value = list_data

    # Call first() with kwargs
    result = await folder.first(from_="alice@example.com")

    # Verify query includes from_ filter
    call_args = mock_imap.query_messages.call_args
    query = call_args[0][1]
    assert "FROM" in query.to_imap_criteria()
    assert "alice@example.com" in query.to_imap_criteria()

    assert result is not None
    assert result.uid == 1


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
    data = create_message_data(uid=1, folder="INBOX")

    list_data = MessageListData(
        messages=[data],
        total_matches=1,
        total_in_folder=1,
        folder="INBOX",
    )
    mock_imap.query_messages.return_value = list_data

    # Call first() with invalid kwarg (should be ignored)
    result = await folder.first(invalid_param="ignored")

    # Should still work
    assert result is not None
    assert result.uid == 1


# Story 3.3.1: Async Iteration Protocol Tests


@pytest.mark.asyncio
async def test_folder_async_iteration_all_messages(folder: Folder, mock_imap: AsyncMock, mock_smtp: AsyncMock) -> None:
    """Verify async for iterates over all messages in folder."""
    # Setup mock to return MessageListData with 3 messages
    data1 = create_message_data(uid=1, folder="INBOX")
    data2 = create_message_data(uid=2, folder="INBOX")
    data3 = create_message_data(uid=3, folder="INBOX")

    list_data = MessageListData(
        messages=[data1, data2, data3],
        total_matches=3,
        total_in_folder=3,
        folder="INBOX",
    )
    mock_imap.query_messages.return_value = list_data

    # Collect messages via async for
    collected = []
    async for message in folder:
        collected.append(message)

    # Verify count and messages (by UID, not identity)
    assert len(collected) == 3
    assert collected[0].uid == 1
    assert collected[1].uid == 2
    assert collected[2].uid == 3

    # Verify SMTP was injected (by from_data() factory)
    assert collected[0]._smtp is mock_smtp
    assert collected[1]._smtp is mock_smtp
    assert collected[2]._smtp is mock_smtp


@pytest.mark.asyncio
async def test_folder_async_iteration_with_query(folder: Folder, mock_imap: AsyncMock, mock_smtp: AsyncMock) -> None:
    """Verify async for applies query filters correctly."""
    # Setup mock to return unseen messages
    data1 = create_message_data(uid=1, folder="INBOX")
    data2 = create_message_data(uid=2, folder="INBOX")

    list_data = MessageListData(
        messages=[data1, data2],
        total_matches=2,
        total_in_folder=10,
        folder="INBOX",
    )
    mock_imap.query_messages.return_value = list_data

    # Apply query and iterate
    collected = []
    async for message in folder.unseen():
        collected.append(message)

    # Verify query was applied
    call_args = mock_imap.query_messages.call_args
    query = call_args[0][1]
    assert "UNSEEN" in query.to_imap_criteria()

    # Verify messages yielded (by UID, not identity)
    assert len(collected) == 2
    assert collected[0].uid == 1
    assert collected[1].uid == 2


@pytest.mark.asyncio
async def test_folder_async_iteration_empty_folder(folder: Folder, mock_imap: AsyncMock) -> None:
    """Verify async for on empty folder completes without error."""
    # Setup mock to return empty MessageListData
    list_data = MessageListData(
        messages=[],
        total_matches=0,
        total_in_folder=0,
        folder="INBOX",
    )
    mock_imap.query_messages.return_value = list_data

    # Iterate over empty folder
    collected = []
    async for message in folder:
        collected.append(message)

    # Verify no iterations performed
    assert len(collected) == 0


@pytest.mark.asyncio
async def test_folder_async_iteration_matches_list(folder: Folder, mock_imap: AsyncMock, mock_smtp: AsyncMock) -> None:
    """Verify async for yields same messages as .list() in same order."""
    # Setup mock data
    data1 = create_message_data(uid=1, folder="INBOX")
    data2 = create_message_data(uid=2, folder="INBOX")
    data3 = create_message_data(uid=3, folder="INBOX")

    list_data = MessageListData(
        messages=[data1, data2, data3],
        total_matches=3,
        total_in_folder=3,
        folder="INBOX",
    )
    mock_imap.query_messages.return_value = list_data

    # Collect via async for
    collected_iter = []
    async for message in folder:
        collected_iter.append(message)

    # Reset mock call count
    mock_imap.query_messages.reset_mock()
    mock_imap.query_messages.return_value = list_data

    # Collect via .list()
    list_result = await folder.list()

    # Verify equivalence (by UID, since each call creates new Message objects)
    assert len(collected_iter) == len(list_result.messages)
    for i, msg in enumerate(collected_iter):
        assert msg.uid == list_result.messages[i].uid


def test_folder_repr_no_filters(mock_imap: AsyncMock, mock_smtp: AsyncMock) -> None:
    """Verify Folder repr without filters."""
    folder = Folder(mock_imap, mock_smtp, "INBOX", "me@example.com")

    assert repr(folder) == "Folder('INBOX')"


def test_folder_repr_with_filters(mock_imap: AsyncMock, mock_smtp: AsyncMock) -> None:
    """Verify Folder repr with active filters."""
    folder = Folder(mock_imap, mock_smtp, "INBOX", "me@example.com")
    filtered = folder.from_("alice").unseen()

    repr_str = repr(filtered)
    assert "Folder('INBOX'" in repr_str
    assert "filters=2" in repr_str


# Date filter tests


def test_folder_since_filter(mock_imap, mock_smtp) -> None:
    """Verify folder.since() creates date filter."""
    from datetime import date

    folder = Folder(mock_imap, mock_smtp, "INBOX", "sender@example.com")

    filtered = folder.since(date(2025, 12, 21))
    assert len(filtered._query_parts) == 1
    assert filtered._query_parts[0].to_imap_criteria() == ["SINCE", "21-Dec-2025"]


def test_folder_before_filter(mock_imap, mock_smtp) -> None:
    """Verify folder.before() creates date filter."""
    from datetime import date

    folder = Folder(mock_imap, mock_smtp, "INBOX", "sender@example.com")

    filtered = folder.before(date(2025, 1, 1))
    assert len(filtered._query_parts) == 1
    assert filtered._query_parts[0].to_imap_criteria() == ["BEFORE", "01-Jan-2025"]


def test_folder_on_filter(mock_imap, mock_smtp) -> None:
    """Verify folder.on() creates date filter."""
    from datetime import date

    folder = Folder(mock_imap, mock_smtp, "INBOX", "sender@example.com")

    filtered = folder.on(date(2025, 12, 21))
    assert len(filtered._query_parts) == 1
    assert filtered._query_parts[0].to_imap_criteria() == ["ON", "21-Dec-2025"]


def test_folder_sentsince_filter(mock_imap, mock_smtp) -> None:
    """Verify folder.sentsince() creates date filter."""
    from datetime import date

    folder = Folder(mock_imap, mock_smtp, "INBOX", "sender@example.com")

    filtered = folder.sentsince(date(2025, 12, 1))
    assert len(filtered._query_parts) == 1
    assert filtered._query_parts[0].to_imap_criteria() == ["SENTSINCE", "01-Dec-2025"]


def test_folder_sentbefore_filter(mock_imap, mock_smtp) -> None:
    """Verify folder.sentbefore() creates date filter."""
    from datetime import date

    folder = Folder(mock_imap, mock_smtp, "INBOX", "sender@example.com")

    filtered = folder.sentbefore(date(2025, 1, 1))
    assert len(filtered._query_parts) == 1
    assert filtered._query_parts[0].to_imap_criteria() == ["SENTBEFORE", "01-Jan-2025"]


# Size filter tests


def test_folder_larger_filter(mock_imap, mock_smtp) -> None:
    """Verify folder.larger() creates size filter."""
    folder = Folder(mock_imap, mock_smtp, "INBOX", "sender@example.com")

    filtered = folder.larger(1_000_000)
    assert len(filtered._query_parts) == 1
    assert filtered._query_parts[0].to_imap_criteria() == ["LARGER", "1000000"]


def test_folder_smaller_filter(mock_imap, mock_smtp) -> None:
    """Verify folder.smaller() creates size filter."""
    folder = Folder(mock_imap, mock_smtp, "INBOX", "sender@example.com")

    filtered = folder.smaller(10_000)
    assert len(filtered._query_parts) == 1
    assert filtered._query_parts[0].to_imap_criteria() == ["SMALLER", "10000"]


# Multi-address filter tests


def test_folder_from_single_address(mock_imap, mock_smtp) -> None:
    """Verify folder.from_() works with single address (backward compatibility)."""
    folder = Folder(mock_imap, mock_smtp, "INBOX", "sender@example.com")

    filtered = folder.from_("alice@example.com")
    assert len(filtered._query_parts) == 1
    assert filtered._query_parts[0].to_imap_criteria() == ["FROM", "alice@example.com"]


def test_folder_from_multiple_addresses_or_logic(mock_imap, mock_smtp) -> None:
    """Verify folder.from_(['a', 'b']) creates OR query."""
    folder = Folder(mock_imap, mock_smtp, "INBOX", "sender@example.com")

    filtered = folder.from_(["alice@example.com", "bob@example.com"])
    assert len(filtered._query_parts) == 1
    assert filtered._query_parts[0].to_imap_criteria() == ["OR", "FROM", "alice@example.com", "FROM", "bob@example.com"]


def test_folder_to_single_address(mock_imap, mock_smtp) -> None:
    """Verify folder.to() works with single address (backward compatibility)."""
    folder = Folder(mock_imap, mock_smtp, "INBOX", "sender@example.com")

    filtered = folder.to("alice@example.com")
    assert len(filtered._query_parts) == 1
    assert filtered._query_parts[0].to_imap_criteria() == ["TO", "alice@example.com"]


def test_folder_to_multiple_addresses_or_logic(mock_imap, mock_smtp) -> None:
    """Verify folder.to(['a', 'b']) creates OR query."""
    folder = Folder(mock_imap, mock_smtp, "INBOX", "sender@example.com")

    filtered = folder.to(["alice@example.com", "bob@example.com"])
    assert len(filtered._query_parts) == 1
    assert filtered._query_parts[0].to_imap_criteria() == ["OR", "TO", "alice@example.com", "TO", "bob@example.com"]


def test_folder_cc_single_address(mock_imap, mock_smtp) -> None:
    """Verify folder.cc() works with single address."""
    folder = Folder(mock_imap, mock_smtp, "INBOX", "sender@example.com")

    filtered = folder.cc("team@example.com")
    assert len(filtered._query_parts) == 1
    assert filtered._query_parts[0].to_imap_criteria() == ["CC", "team@example.com"]


def test_folder_cc_multiple_addresses_or_logic(mock_imap, mock_smtp) -> None:
    """Verify folder.cc(['a', 'b']) creates OR query."""
    folder = Folder(mock_imap, mock_smtp, "INBOX", "sender@example.com")

    filtered = folder.cc(["team@example.com", "manager@example.com"])
    assert len(filtered._query_parts) == 1
    assert filtered._query_parts[0].to_imap_criteria() == ["OR", "CC", "team@example.com", "CC", "manager@example.com"]


# Content filter tests


def test_folder_text_filter(mock_imap, mock_smtp) -> None:
    """Verify folder.text() creates TEXT search filter."""
    folder = Folder(mock_imap, mock_smtp, "INBOX", "sender@example.com")

    filtered = folder.text("budget")
    assert len(filtered._query_parts) == 1
    assert filtered._query_parts[0].to_imap_criteria() == ["TEXT", "budget"]


# Flag filter tests


def test_folder_unanswered_filter(mock_imap, mock_smtp) -> None:
    """Verify folder.unanswered() creates UNANSWERED filter."""
    folder = Folder(mock_imap, mock_smtp, "INBOX", "sender@example.com")

    filtered = folder.unanswered()
    assert len(filtered._query_parts) == 1
    assert filtered._query_parts[0].to_imap_criteria() == ["UNANSWERED"]


def test_folder_unflagged_filter(mock_imap, mock_smtp) -> None:
    """Verify folder.unflagged() creates UNFLAGGED filter."""
    folder = Folder(mock_imap, mock_smtp, "INBOX", "sender@example.com")

    filtered = folder.unflagged()
    assert len(filtered._query_parts) == 1
    assert filtered._query_parts[0].to_imap_criteria() == ["UNFLAGGED"]


# Custom filter tests


def test_folder_keyword_single(mock_imap, mock_smtp) -> None:
    """Verify folder.keyword() works with single keyword."""
    folder = Folder(mock_imap, mock_smtp, "INBOX", "sender@example.com")

    filtered = folder.keyword("Important")
    assert len(filtered._query_parts) == 1
    assert filtered._query_parts[0].to_imap_criteria() == ["KEYWORD", "Important"]


def test_folder_keyword_multiple_or_logic(mock_imap, mock_smtp) -> None:
    """Verify folder.keyword(['a', 'b']) creates OR query."""
    folder = Folder(mock_imap, mock_smtp, "INBOX", "sender@example.com")

    filtered = folder.keyword(["Important", "FollowUp"])
    assert len(filtered._query_parts) == 1
    assert filtered._query_parts[0].to_imap_criteria() == ["OR", "KEYWORD", "Important", "KEYWORD", "FollowUp"]


def test_folder_header_filter(mock_imap, mock_smtp) -> None:
    """Verify folder.header() creates HEADER filter."""
    folder = Folder(mock_imap, mock_smtp, "INBOX", "sender@example.com")

    filtered = folder.header("X-Priority", "1")
    assert len(filtered._query_parts) == 1
    assert filtered._query_parts[0].to_imap_criteria() == ["HEADER", "X-Priority", "1"]


# Query method tests


def test_folder_query_method(mock_imap, mock_smtp) -> None:
    """Verify folder.query() accepts Q expression."""
    from mailcore.query import Q

    folder = Folder(mock_imap, mock_smtp, "INBOX", "sender@example.com")

    q = Q.from_("alice") | Q.subject("urgent")
    filtered = folder.query(q)
    assert len(filtered._query_parts) == 1
    assert filtered._query_parts[0].to_imap_criteria() == ["OR", "FROM", "alice", "SUBJECT", "urgent"]


# Chaining tests with new filters


def test_folder_complex_chaining_with_new_filters(mock_imap, mock_smtp) -> None:
    """Verify complex chaining with date, size, and multi-address filters."""
    from datetime import date

    folder = Folder(mock_imap, mock_smtp, "INBOX", "sender@example.com")

    filtered = folder.from_(["alice@example.com", "bob@example.com"]).since(date(2025, 12, 1)).larger(1_000_000)

    assert len(filtered._query_parts) == 3
    # First part: OR of FROM addresses
    assert filtered._query_parts[0].to_imap_criteria() == ["OR", "FROM", "alice@example.com", "FROM", "bob@example.com"]
    # Second part: SINCE date
    assert filtered._query_parts[1].to_imap_criteria() == ["SINCE", "01-Dec-2025"]
    # Third part: LARGER size
    assert filtered._query_parts[2].to_imap_criteria() == ["LARGER", "1000000"]


# UID range tests (Story 3.28)


def test_folder_uid_range_numeric_end(mock_imap, mock_smtp) -> None:
    """Verify folder.uid_range() with numeric end creates correct query."""
    folder = Folder(mock_imap, mock_smtp, "INBOX", "sender@example.com")

    filtered = folder.uid_range(100, 200)
    assert len(filtered._query_parts) == 1
    assert filtered._query_parts[0].to_imap_criteria() == ["100:200"]


def test_folder_uid_range_star_end(mock_imap, mock_smtp) -> None:
    """Verify folder.uid_range() with '*' end creates correct query (IDLE pattern)."""
    folder = Folder(mock_imap, mock_smtp, "INBOX", "sender@example.com")

    filtered = folder.uid_range(173, "*")
    assert len(filtered._query_parts) == 1
    assert filtered._query_parts[0].to_imap_criteria() == ["173:*"]


def test_folder_uid_range_immutability(mock_imap, mock_smtp) -> None:
    """Verify folder.uid_range() returns NEW Folder instance (immutable pattern)."""
    folder = Folder(mock_imap, mock_smtp, "INBOX", "sender@example.com")

    filtered = folder.uid_range(100, 200)
    assert folder is not filtered
    assert folder._query_parts == []
    assert len(filtered._query_parts) == 1


def test_folder_uid_range_chainable(mock_imap, mock_smtp) -> None:
    """Verify folder.uid_range() is chainable with other filters."""
    folder = Folder(mock_imap, mock_smtp, "INBOX", "sender@example.com")

    # IDLE pattern: new messages that are unseen
    filtered = folder.uid_range(100, "*").unseen()
    assert len(filtered._query_parts) == 2
    assert filtered._query_parts[0].to_imap_criteria() == ["100:*"]
    assert filtered._query_parts[1].to_imap_criteria() == ["UNSEEN"]
