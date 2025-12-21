"""Tests for domain types in types.py."""

from datetime import datetime

from mailcore.attachment import Attachment
from mailcore.email_address import EmailAddress
from mailcore.types import (
    FolderInfo,
    FolderStatus,
    MessageData,
    MessageFlag,
    MessageListData,
    SendResult,
)


def test_email_address_to_rfc5322_with_name() -> None:
    """Verify EmailAddress.to_rfc5322() formats correctly with name."""
    addr = EmailAddress("alice@example.com", "Alice Smith")
    assert addr.to_rfc5322() == "Alice Smith <alice@example.com>"


def test_email_address_to_rfc5322_without_name() -> None:
    """Verify EmailAddress.to_rfc5322() formats correctly without name."""
    addr = EmailAddress("bob@example.com")
    assert addr.to_rfc5322() == "bob@example.com"


def test_message_flag_enum_values() -> None:
    """Verify MessageFlag enum has all 6 required values."""
    assert MessageFlag.SEEN.value == "\\Seen"
    assert MessageFlag.ANSWERED.value == "\\Answered"
    assert MessageFlag.FLAGGED.value == "\\Flagged"
    assert MessageFlag.DELETED.value == "\\Deleted"
    assert MessageFlag.DRAFT.value == "\\Draft"
    assert MessageFlag.RECENT.value == "\\Recent"

    # Verify all 6 flags exist
    flags = list(MessageFlag)
    assert len(flags) == 6


def test_message_flag_from_imap_standard_flags() -> None:
    """Verify MessageFlag.from_imap() converts standard IMAP flags."""
    assert MessageFlag.from_imap("\\Seen") == MessageFlag.SEEN
    assert MessageFlag.from_imap("\\Answered") == MessageFlag.ANSWERED
    assert MessageFlag.from_imap("\\Flagged") == MessageFlag.FLAGGED
    assert MessageFlag.from_imap("\\Deleted") == MessageFlag.DELETED
    assert MessageFlag.from_imap("\\Draft") == MessageFlag.DRAFT
    assert MessageFlag.from_imap("\\Recent") == MessageFlag.RECENT


def test_message_flag_from_imap_custom_flags() -> None:
    """Verify MessageFlag.from_imap() returns None for custom flags."""
    assert MessageFlag.from_imap("$Forwarded") is None
    assert MessageFlag.from_imap("$MDNSent") is None
    assert MessageFlag.from_imap("CustomFlag") is None
    assert MessageFlag.from_imap("\\InvalidFlag") is None


def test_folder_info_dataclass() -> None:
    """Verify FolderInfo dataclass structure."""
    info = FolderInfo(
        name="INBOX",
        flags=["\\HasNoChildren"],
        has_children=False,
    )
    assert info.name == "INBOX"
    assert info.flags == ["\\HasNoChildren"]
    assert info.has_children is False


def test_folder_status_dataclass() -> None:
    """Verify FolderStatus dataclass structure."""
    status = FolderStatus(
        message_count=42,
        unseen_count=5,
        uidnext=100,
    )
    assert status.message_count == 42
    assert status.unseen_count == 5
    assert status.uidnext == 100


def test_send_result_dataclass() -> None:
    """Verify SendResult dataclass structure."""
    result = SendResult(
        message_id="<msg123@example.com>",
        accepted=["alice@example.com", "bob@example.com"],
        rejected={"invalid@domain.com": (550, "No such user")},
    )
    assert result.message_id == "<msg123@example.com>"
    assert len(result.accepted) == 2
    assert result.accepted[0] == "alice@example.com"
    assert len(result.rejected) == 1
    assert result.rejected["invalid@domain.com"] == (550, "No such user")


def test_message_data_creation_with_all_fields() -> None:
    """Verify MessageData creation with all 14 fields."""
    now = datetime(2025, 12, 17, 10, 30, 0)
    data = MessageData(
        uid=42,
        folder="INBOX",
        message_id="<test@example.com>",
        from_=EmailAddress("alice@example.com", "Alice"),
        to=[EmailAddress("bob@example.com", "Bob")],
        cc=[EmailAddress("charlie@example.com")],
        subject="Test Subject",
        date=now,
        flags={MessageFlag.SEEN, MessageFlag.FLAGGED},
        size=1024,
        custom_flags={"$Forwarded", "$MDNSent"},
        in_reply_to="<original@example.com>",
        references=["<ref1@example.com>", "<ref2@example.com>"],
        attachments=[Attachment.from_bytes(b"test", "test.txt", "text/plain")],
    )

    assert data.uid == 42
    assert data.folder == "INBOX"
    assert data.message_id == "<test@example.com>"
    assert data.from_.email == "alice@example.com"
    assert len(data.to) == 1
    assert len(data.cc) == 1
    assert data.subject == "Test Subject"
    assert data.date == now
    assert MessageFlag.SEEN in data.flags
    assert MessageFlag.FLAGGED in data.flags
    assert data.size == 1024
    assert "$Forwarded" in data.custom_flags
    assert data.in_reply_to == "<original@example.com>"
    assert len(data.references) == 2
    assert len(data.attachments) == 1


def test_message_data_is_pure_dataclass() -> None:
    """Verify MessageData is pure dataclass with no methods beyond __init__."""
    data = MessageData(
        uid=1,
        folder="INBOX",
        message_id="<test@example.com>",
        from_=EmailAddress("alice@example.com"),
        to=[],
        cc=[],
        subject="Test",
        date=datetime.now(),
        flags=set(),
        size=100,
        custom_flags=set(),
        in_reply_to=None,
        references=[],
        attachments=[],
    )

    # Verify it's a dataclass
    assert hasattr(data, "__dataclass_fields__")

    # Verify no custom methods (only dunder methods from dataclass)
    custom_methods = [m for m in dir(data) if callable(getattr(data, m)) and not m.startswith("_")]
    assert len(custom_methods) == 0, f"Found custom methods: {custom_methods}"


def test_message_list_data_creation() -> None:
    """Verify MessageListData creation with 4 fields."""
    msg1 = MessageData(
        uid=1,
        folder="INBOX",
        message_id="<msg1@example.com>",
        from_=EmailAddress("alice@example.com"),
        to=[EmailAddress("bob@example.com")],
        cc=[],
        subject="Message 1",
        date=datetime.now(),
        flags={MessageFlag.SEEN},
        size=512,
        custom_flags=set(),
        in_reply_to=None,
        references=[],
        attachments=[],
    )
    msg2 = MessageData(
        uid=2,
        folder="INBOX",
        message_id="<msg2@example.com>",
        from_=EmailAddress("charlie@example.com"),
        to=[EmailAddress("bob@example.com")],
        cc=[],
        subject="Message 2",
        date=datetime.now(),
        flags=set(),
        size=768,
        custom_flags=set(),
        in_reply_to=None,
        references=[],
        attachments=[],
    )

    list_data = MessageListData(
        messages=[msg1, msg2],
        total_matches=2,
        total_in_folder=100,
        folder="INBOX",
    )

    assert len(list_data.messages) == 2
    assert list_data.total_matches == 2
    assert list_data.total_in_folder == 100
    assert list_data.folder == "INBOX"
    assert list_data.messages[0].uid == 1
    assert list_data.messages[1].uid == 2


def test_message_list_data_is_pure_dataclass() -> None:
    """Verify MessageListData is pure dataclass with no methods."""
    list_data = MessageListData(
        messages=[],
        total_matches=0,
        total_in_folder=0,
        folder="INBOX",
    )

    # Verify it's a dataclass
    assert hasattr(list_data, "__dataclass_fields__")

    # Verify no custom methods
    custom_methods = [m for m in dir(list_data) if callable(getattr(list_data, m)) and not m.startswith("_")]
    assert len(custom_methods) == 0, f"Found custom methods: {custom_methods}"
