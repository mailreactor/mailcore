"""Domain types for message flags, folder info, and SMTP results."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mailcore.attachment import Attachment
    from mailcore.email_address import EmailAddress


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
        >>> MessageFlag.from_imap("\\\\Seen")
        <MessageFlag.SEEN: '\\\\Seen'>
        >>> MessageFlag.from_imap("$Forwarded")  # Custom flag
        None
    """

    SEEN = "\\Seen"
    ANSWERED = "\\Answered"
    FLAGGED = "\\Flagged"
    DELETED = "\\Deleted"
    DRAFT = "\\Draft"
    RECENT = "\\Recent"

    @classmethod
    def from_imap(cls, flag_str: str) -> "MessageFlag | None":
        """Convert IMAP flag string to MessageFlag enum.

        Uses enum value lookup to convert IMAP protocol strings to domain types.
        Returns None for custom/non-standard flags.

        Args:
            flag_str: IMAP flag string (e.g., "\\Seen", "\\Flagged")

        Returns:
            MessageFlag enum or None if not a standard flag

        Example:
            >>> MessageFlag.from_imap("\\Seen")
            <MessageFlag.SEEN: '\\Seen'>
            >>> MessageFlag.from_imap("$Forwarded")
            None
        """
        try:
            return cls(flag_str)
        except ValueError:
            return None


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


@dataclass
class MessageData:
    """Data returned by IMAP adapter - NOT a full entity.

    Pure data container with no behavior. Domain converts this to Message entity.

    Attributes:
        uid: IMAP UID (unique within folder)
        folder: Folder name (e.g., "INBOX")
        message_id: RFC 5322 Message-ID header
        from_: Sender email address (EmailAddress value object)
        to: List of recipient email addresses
        cc: List of CC email addresses
        subject: Email subject line
        date: Date/time message was sent
        flags: Set of standard IMAP flags
        size: Message size in bytes
        custom_flags: Set of custom/non-standard IMAP flags
        in_reply_to: Message-ID of message being replied to (optional)
        references: List of Message-IDs in thread (optional)
        attachments: List of attachment metadata (Attachment value objects)

    Example:
        >>> from mailcore import EmailAddress, MessageFlag, Attachment
        >>> data = MessageData(
        ...     uid=42,
        ...     folder="INBOX",
        ...     message_id="<test@example.com>",
        ...     from_=EmailAddress("alice@example.com"),
        ...     to=[EmailAddress("bob@example.com")],
        ...     cc=[],
        ...     subject="Test",
        ...     date=datetime.now(),
        ...     flags={MessageFlag.SEEN},
        ...     size=1024,
        ...     custom_flags=set(),
        ...     in_reply_to=None,
        ...     references=[],
        ...     attachments=[]
        ... )
        >>> data.uid
        42
        >>> data.subject
        'Test'
    """

    uid: int
    folder: str
    message_id: str
    from_: "EmailAddress"
    to: list["EmailAddress"]
    cc: list["EmailAddress"]
    subject: str
    date: datetime
    flags: set[MessageFlag]
    size: int
    custom_flags: set[str]
    in_reply_to: str | None
    references: list[str]
    attachments: list["Attachment"]


@dataclass
class MessageListData:
    """Data returned by IMAP adapter.

    Container for query results with pagination metadata.

    Attributes:
        messages: List of MessageData DTOs
        total_matches: Total messages matching query (before limit)
        total_in_folder: Total messages in folder (regardless of query)
        folder: Folder name

    Example:
        >>> data = MessageListData(
        ...     messages=[...],
        ...     total_matches=100,
        ...     total_in_folder=500,
        ...     folder="INBOX"
        ... )
        >>> len(data.messages)
        50
        >>> data.total_matches
        100
    """

    messages: list[MessageData]
    total_matches: int
    total_in_folder: int
    folder: str
