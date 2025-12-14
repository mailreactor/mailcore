"""Tests for MessageList in message_list.py."""

from mailcore.message_list import MessageList


def test_message_list_len() -> None:
    """Verify MessageList.__len__() returns correct count."""
    result = MessageList(
        messages=[1, 2, 3],
        total_matches=10,
        total_in_folder=50,
        folder="INBOX",
    )
    assert len(result) == 3


def test_message_list_iter() -> None:
    """Verify MessageList.__iter__() allows iteration."""
    result = MessageList(
        messages=[1, 2, 3],
        total_matches=10,
        total_in_folder=50,
        folder="INBOX",
    )
    items = list(result)
    assert items == [1, 2, 3]


def test_message_list_getitem_index() -> None:
    """Verify MessageList[index] access works."""
    result = MessageList(
        messages=["a", "b", "c"],
        total_matches=10,
        total_in_folder=50,
        folder="INBOX",
    )
    assert result[0] == "a"
    assert result[1] == "b"
    assert result[2] == "c"


def test_message_list_getitem_slice() -> None:
    """Verify MessageList[slice] access works."""
    result = MessageList(
        messages=[1, 2, 3, 4, 5],
        total_matches=10,
        total_in_folder=50,
        folder="INBOX",
    )
    assert result[1:3] == [2, 3]
    assert result[:2] == [1, 2]
    assert result[3:] == [4, 5]


def test_message_list_metadata() -> None:
    """Verify MessageList preserves pagination metadata."""
    result = MessageList(
        messages=[],
        total_matches=42,
        total_in_folder=100,
        folder="Sent",
    )
    assert result.total_matches == 42
    assert result.total_in_folder == 100
    assert result.folder == "Sent"
