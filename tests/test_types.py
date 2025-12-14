"""Tests for domain types in types.py."""

from mailcore.types import EmailAddress, FolderInfo, FolderStatus, MessageFlag, SendResult


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
