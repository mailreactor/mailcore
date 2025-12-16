"""Message class with metadata and lazy body/attachment loading."""

from datetime import datetime
from typing import TYPE_CHECKING

from mailcore.attachment import Attachment
from mailcore.body import MessageBody
from mailcore.email_address import EmailAddress
from mailcore.protocols import IMAPConnection, SMTPConnection
from mailcore.types import MessageFlag

if TYPE_CHECKING:
    from mailcore.draft import Draft


class Message:
    """Email message with metadata and lazy body/attachment loading.

    Metadata is always available (from IMAP SEARCH + BODYSTRUCTURE). Body content
    is fetched on-demand when accessed via the body property.

    Message receives IMAP connection at creation, SMTP is injected later by Folder
    after IMAP query completes.

    Args:
        imap: IMAP connection for operations (mark_read, move_to, etc.)
        uid: IMAP UID (folder-specific)
        folder: Folder name this message belongs to
        message_id: RFC 5322 Message-ID (globally unique)
        from_: Sender
        to: Recipients
        cc: CC recipients
        subject: Subject line
        date: Message date
        flags: Standard IMAP flags (MessageFlag enum)
        size: Message size in bytes
        custom_flags: Custom IMAP keywords (e.g., $Forwarded, $MDNSent)
        in_reply_to: Message-ID this replies to (for threading)
        references: Thread chain (list of Message-IDs)
        attachments: List of attachments (metadata from BODYSTRUCTURE)

    Note:
        Not typically instantiated directly - created during folder queries.

        Message._smtp is None at creation, injected by Folder.list() to enable
        compose operations (reply, forward).

    Example:
        >>> # Created by IMAP adapter
        >>> message = Message(
        ...     imap=mock_imap,
        ...     uid=42,
        ...     folder='INBOX',
        ...     message_id='<msg-123@example.com>',
        ...     from_=EmailAddress('alice@example.com', 'Alice Smith'),
        ...     to=[EmailAddress('bob@example.com')],
        ...     cc=[],
         ...     subject='Test Subject',
         ...     date=datetime.now(),
         ...     flags={MessageFlag.SEEN},
         ...     size=1024
        ... )
        >>> # Access metadata (no network call)
        >>> print(message.subject)  # 'Test Subject'
        >>> # Access body (lazy - creates MessageBody instance)
        >>> text = await message.body.get_text()  # Fetches from IMAP
    """

    def __init__(
        self,
        imap: IMAPConnection,
        uid: int,
        folder: str,
        message_id: str,
        from_: EmailAddress,
        to: list[EmailAddress],
        cc: list[EmailAddress],
        subject: str,
        date: datetime,
        flags: set[MessageFlag],
        size: int,
        custom_flags: set[str] | None = None,
        in_reply_to: str | None = None,
        references: list[str] | None = None,
        attachments: list[Attachment] | None = None,
    ) -> None:
        """Initialize message with metadata and IMAP connection."""
        self._imap = imap
        self._uid = uid
        self._folder = folder
        self._message_id = message_id
        self._from = from_
        self._to = to
        self._cc = cc
        self._subject = subject
        self._date = date
        self._flags = flags
        self._custom_flags = custom_flags if custom_flags is not None else set()
        self._size = size
        self._in_reply_to = in_reply_to
        self._references = references if references is not None else []
        self._attachments = attachments if attachments is not None else []
        self._smtp: SMTPConnection | None = None
        self._body: MessageBody | None = None

    @property
    def uid(self) -> int:
        """IMAP unique ID (folder-specific)."""
        return self._uid

    @property
    def folder(self) -> str:
        """Folder this message belongs to."""
        return self._folder

    @property
    def message_id(self) -> str:
        """RFC 5322 Message-ID (globally unique)."""
        return self._message_id

    @property
    def from_(self) -> EmailAddress:
        """Sender."""
        return self._from

    @property
    def to(self) -> list[EmailAddress]:
        """Recipients."""
        return self._to

    @property
    def cc(self) -> list[EmailAddress]:
        """CC recipients."""
        return self._cc

    @property
    def subject(self) -> str:
        """Subject line."""
        return self._subject

    @property
    def date(self) -> datetime:
        """Message date."""
        return self._date

    @property
    def flags(self) -> set[MessageFlag]:
        """Standard IMAP flags.

        Check membership with: MessageFlag.SEEN in message.flags

        Example:
            >>> if MessageFlag.SEEN in message.flags:
            ...     print("Message is read")
        """
        return self._flags

    @property
    def custom_flags(self) -> set[str]:
        """Custom IMAP keywords (e.g., $Forwarded, $MDNSent).

        Example:
            >>> if "$Forwarded" in message.custom_flags:
            ...     print("Message was forwarded")
        """
        return self._custom_flags

    @property
    def size(self) -> int:
        """Message size in bytes."""
        return self._size

    @property
    def in_reply_to(self) -> str | None:
        """Message-ID this replies to."""
        return self._in_reply_to

    @property
    def references(self) -> list[str]:
        """Thread chain (list of Message-IDs)."""
        return self._references

    @property
    def is_reply(self) -> bool:
        """True if has In-Reply-To header (computed from in_reply_to is not None)."""
        return self._in_reply_to is not None

    @property
    def body(self) -> MessageBody:
        """Message body (lazy - fetch on get_text()/get_html()).

        Creates MessageBody instance on first access with IMAP injection.

        Returns:
            MessageBody instance for lazy loading text/HTML content

        Example:
            >>> text = await message.body.get_text()
            >>> html = await message.body.get_html()
        """
        if self._body is None:
            self._body = MessageBody(imap=self._imap, folder=self._folder, uid=self._uid)
        return self._body

    @property
    def attachments(self) -> list[Attachment]:
        """List of attachments (metadata from IMAP BODYSTRUCTURE).

        Attachment metadata is always available. Content is fetched on-demand
        when .read() or .save() is called.

        Returns:
            List of Attachment instances

        Example:
            >>> # Access metadata (no network call)
            >>> for att in message.attachments:
            ...     print(att.filename, att.size, att.content_type)
            >>>
            >>> # Fetch content (lazy load)
            >>> if message.has_attachments:
            ...     content = await message.attachments[0].read()
        """
        return self._attachments

    @property
    def has_attachments(self) -> bool:
        """True if message has non-inline attachments.

        Inline attachments (images in HTML body) are excluded from count.

        Returns:
            True if message has attachments (excluding inline)

        Example:
            >>> if message.has_attachments:
            ...     print(f"Message has {message.attachment_count} attachments")
        """
        return any(not att.is_inline for att in self._attachments)

    @property
    def attachment_count(self) -> int:
        """Count of non-inline attachments.

        Returns:
            Number of attachments (excluding inline)

        Example:
            >>> print(f"Message has {message.attachment_count} attachments")
        """
        return sum(1 for att in self._attachments if not att.is_inline)

    @property
    def inline_count(self) -> int:
        """Count of inline attachments (images/audio/video in HTML).

        Returns:
            Number of inline attachments

        Example:
            >>> print(f"Message has {message.inline_count} inline images")
        """
        return sum(1 for att in self._attachments if att.is_inline)

    async def mark_read(self) -> None:
        """Mark message as read (\\Seen flag).

        Calls IMAP update_message_flags to add \\Seen flag.

        Example:
            >>> await message.mark_read()
        """
        await self._imap.update_message_flags(folder=self._folder, uid=self._uid, add_flags={MessageFlag.SEEN})

    async def mark_unread(self) -> None:
        """Mark message as unread (remove \\Seen flag).

        Calls IMAP update_message_flags to remove \\Seen flag.

        Example:
            >>> await message.mark_unread()
        """
        await self._imap.update_message_flags(folder=self._folder, uid=self._uid, remove_flags={MessageFlag.SEEN})

    async def mark_flagged(self) -> None:
        """Mark message as flagged/starred (\\Flagged flag).

        Calls IMAP update_message_flags to add \\Flagged flag.

        Example:
            >>> await message.mark_flagged()
        """
        await self._imap.update_message_flags(folder=self._folder, uid=self._uid, add_flags={MessageFlag.FLAGGED})

    async def mark_unflagged(self) -> None:
        """Remove flagged/starred (remove \\Flagged flag).

        Calls IMAP update_message_flags to remove \\Flagged flag.

        Example:
            >>> await message.mark_unflagged()
        """
        await self._imap.update_message_flags(folder=self._folder, uid=self._uid, remove_flags={MessageFlag.FLAGGED})

    async def mark_answered(self) -> None:
        """Mark message as answered (\\Answered flag).

        Calls IMAP update_message_flags to add \\Answered flag.

        Example:
            >>> await message.mark_answered()
        """
        await self._imap.update_message_flags(folder=self._folder, uid=self._uid, add_flags={MessageFlag.ANSWERED})

    async def move_to(self, folder: str) -> None:
        """Move message to folder.

        Calls IMAP move_message to move to destination folder.

        Args:
            folder: Destination folder name

        Example:
            >>> await message.move_to('Archive')
        """
        await self._imap.move_message(uid=self._uid, from_folder=self._folder, to_folder=folder)

    async def copy_to(self, folder: str) -> None:
        """Copy message to folder.

        Calls IMAP copy_message to copy to destination folder.

        Args:
            folder: Destination folder name

        Example:
            >>> await message.copy_to('Archive')
        """
        await self._imap.copy_message(uid=self._uid, from_folder=self._folder, to_folder=folder)

    async def delete(self, permanent: bool = False) -> None:
        """Delete message.

        Calls IMAP delete_message to delete or move to trash.

        Args:
            permanent: True = expunge immediately, False = move to trash

        Example:
            >>> await message.delete()  # Move to trash
            >>> await message.delete(permanent=True)  # Expunge immediately
        """
        await self._imap.delete_message(folder=self._folder, uid=self._uid, permanent=permanent)

    async def mark_deleted(self) -> None:
        """Mark message for deletion (\\Deleted flag, don't expunge).

        Calls IMAP update_message_flags to add \\Deleted flag.

        Example:
            >>> await message.mark_deleted()
        """
        await self._imap.update_message_flags(folder=self._folder, uid=self._uid, add_flags={MessageFlag.DELETED})

    def reply(self, quote: bool = True) -> "Draft":
        """Create reply draft.

        Args:
            quote: Include original message quote (fetched during send())

        Returns:
            Draft pre-configured for reply

        Raises:
            ValueError: If SMTP connection not available

        Example:
            >>> draft = message.reply()
            >>> await draft.body('Thanks!').send()
        """
        # Lazy import to avoid circular import at module level
        from mailcore.draft import Draft

        # Require SMTP connection (injected by Folder after IMAP query)
        if self._smtp is None:
            raise ValueError("SMTP connection not available - Message must come from Folder query")

        # Create Draft with reply headers
        draft = Draft(
            smtp=self._smtp,
            reference_message=self,
            in_reply_to=self._message_id,
            references=self._references + [self._message_id],
            quote=quote,
        )

        # Pre-populate fields
        # To: original sender
        draft.to(self._from.to_rfc5322())

        # Subject: Add "Re:" prefix if not already present
        if self._subject.startswith("Re:"):
            draft.subject(self._subject)
        else:
            draft.subject(f"Re: {self._subject}")

        return draft

    def reply_all(self, quote: bool = True) -> "Draft":
        """Create reply-all draft.

        Args:
            quote: Include original message quote (fetched during send())

        Returns:
            Draft pre-configured for reply-all (includes all original recipients)

        Raises:
            ValueError: If SMTP connection not available

        Example:
            >>> draft = message.reply_all()
            >>> await draft.body('Thanks everyone!').send()
        """
        # Lazy import to avoid circular import at module level
        from mailcore.draft import Draft

        # Require SMTP connection (injected by Folder after IMAP query)
        if self._smtp is None:
            raise ValueError("SMTP connection not available - Message must come from Folder query")

        # Create Draft with reply headers
        draft = Draft(
            smtp=self._smtp,
            reference_message=self,
            in_reply_to=self._message_id,
            references=self._references + [self._message_id],
            quote=quote,
        )

        # Pre-populate fields
        # To: original sender + all original To recipients (excluding self)
        # Note: We don't have access to "self" email, so include all recipients
        to_addrs = [self._from.to_rfc5322()] + [addr.to_rfc5322() for addr in self._to]
        draft.to(to_addrs)

        # CC: all original CC recipients
        if self._cc:
            cc_addrs = [addr.to_rfc5322() for addr in self._cc]
            draft.cc(cc_addrs)

        # Subject: Add "Re:" prefix if not already present
        if self._subject.startswith("Re:"):
            draft.subject(self._subject)
        else:
            draft.subject(f"Re: {self._subject}")

        return draft

    def forward(self, include_attachments: bool = True) -> "Draft":
        """Create forward draft.

        Args:
            include_attachments: Include original attachments (fetched during send())

        Returns:
            Draft pre-configured for forward

        Raises:
            ValueError: If SMTP connection not available

        Example:
            >>> draft = message.forward()
            >>> await draft.to('colleague@example.com').body('FYI').send()
        """
        # Lazy import to avoid circular import at module level
        from mailcore.draft import Draft

        # Require SMTP connection (injected by Folder after IMAP query)
        if self._smtp is None:
            raise ValueError("SMTP connection not available - Message must come from Folder query")

        # Create Draft with forward settings
        draft = Draft(
            smtp=self._smtp,
            reference_message=self,
            include_attachments=include_attachments,
        )

        # Pre-populate subject: Add "Fwd:" prefix if not already present
        if self._subject.startswith("Fwd:"):
            draft.subject(self._subject)
        else:
            draft.subject(f"Fwd: {self._subject}")

        return draft

    def __repr__(self) -> str:
        """Developer-friendly representation."""
        return f"Message(uid={self._uid}, folder='{self._folder}', from={self._from.email}, subject='{self._subject}')"
