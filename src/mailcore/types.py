"""Domain types for email addresses, message flags, and other email concepts."""

from dataclasses import dataclass
from enum import Enum


class EmailAddress:
    """RFC 5322 compliant email address with name and address parts.

    Immutable value object representing an email address with optional display name.

    Args:
        email: Email address (e.g., "alice@example.com")
        name: Display name (optional, e.g., "Alice Smith")

    Example:
        >>> addr = EmailAddress("alice@example.com", "Alice Smith")
        >>> addr.to_rfc5322()
        'Alice Smith <alice@example.com>'
        >>> addr_no_name = EmailAddress("bob@example.com")
        >>> addr_no_name.to_rfc5322()
        'bob@example.com'
    """

    def __init__(self, email: str, name: str | None = None) -> None:
        """Initialize email address.

        Args:
            email: Email address (required)
            name: Display name (optional)
        """
        self.email = email
        self.name = name

    def to_rfc5322(self) -> str:
        """Format email address for RFC 5322 headers.

        Returns:
            RFC 5322 formatted address string.
            If name is present: "Name <email@example.com>"
            If name is None: "email@example.com"

        Example:
            >>> EmailAddress("alice@example.com", "Alice Smith").to_rfc5322()
            'Alice Smith <alice@example.com>'
            >>> EmailAddress("bob@example.com").to_rfc5322()
            'bob@example.com'
        """
        if self.name:
            return f"{self.name} <{self.email}>"
        return self.email


class MessageFlag(Enum):
    """Standard IMAP message flags.

    Enumeration of standard IMAP flags as defined in RFC 3501.

    Values:
        SEEN: Message has been read
        ANSWERED: Message has been replied to
        FLAGGED: Message is flagged/starred
        DELETED: Message is marked for deletion
        DRAFT: Message is a draft
        RECENT: Message is recent (new to this session)

    Example:
        >>> MessageFlag.SEEN
        <MessageFlag.SEEN: '\\\\Seen'>
        >>> MessageFlag.FLAGGED.value
        '\\\\Flagged'
    """

    SEEN = "\\Seen"
    ANSWERED = "\\Answered"
    FLAGGED = "\\Flagged"
    DELETED = "\\Deleted"
    DRAFT = "\\Draft"
    RECENT = "\\Recent"


@dataclass
class FolderInfo:
    """Folder metadata from IMAP LIST.

    Dataclass representing IMAP folder information.

    Attributes:
        name: Folder name (e.g., "INBOX", "Sent")
        flags: IMAP folder flags (e.g., ["\\HasNoChildren"])
        has_children: True if folder has subfolders

    Example:
        >>> info = FolderInfo(name="INBOX", flags=["\\HasNoChildren"], has_children=False)
        >>> info.name
        'INBOX'
        >>> info.has_children
        False
    """

    name: str
    flags: list[str]
    has_children: bool


@dataclass
class FolderStatus:
    """Folder statistics from IMAP STATUS.

    Dataclass representing IMAP folder status.

    Attributes:
        message_count: Total messages in folder
        unseen_count: Number of unseen messages
        uidnext: Next UID that will be assigned

    Example:
        >>> status = FolderStatus(message_count=42, unseen_count=5, uidnext=100)
        >>> status.message_count
        42
        >>> status.unseen_count
        5
    """

    message_count: int
    unseen_count: int
    uidnext: int


@dataclass
class SendResult:
    """Result of SMTP send operation.

    Dataclass representing the result of sending an email via SMTP.

    Attributes:
        message_id: RFC 5322 Message-ID of sent message
        accepted: List of accepted recipient email addresses
        rejected: Dict of rejected recipients mapping email -> (smtp_code, reason)

    Example:
        >>> result = SendResult(
        ...     message_id="<msg123@example.com>",
        ...     accepted=["alice@example.com"],
        ...     rejected={"bob@invalid.com": (550, "No such user")}
        ... )
        >>> result.message_id
        '<msg123@example.com>'
        >>> len(result.accepted)
        1
        >>> len(result.rejected)
        1
    """

    message_id: str
    accepted: list[str]
    rejected: dict[str, tuple[int, str]]
