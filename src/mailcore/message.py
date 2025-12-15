"""Message class with metadata and lazy body/attachment loading."""

from datetime import datetime
from typing import TYPE_CHECKING

from mailcore.body import MessageBody
from mailcore.protocols import IMAPConnection, SMTPConnection
from mailcore.types import EmailAddress, MessageFlag

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
        flags: IMAP flags (\\Seen, \\Flagged, etc.)
        size: Message size in bytes
        in_reply_to: Message-ID this replies to (for threading)
        references: Thread chain (list of Message-IDs)

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
        ...     flags=['\\\\Seen'],
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
        flags: list[str],
        size: int,
        in_reply_to: str | None = None,
        references: list[str] | None = None,
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
        self._size = size
        self._in_reply_to = in_reply_to
        self._references = references if references is not None else []
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
    def flags(self) -> list[str]:
        """IMAP flags (\\Seen, \\Flagged, etc.)."""
        return self._flags

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

        NOT IMPLEMENTED - Draft class will be implemented in Story 3.6.

        Args:
            quote: Include original message quote

        Returns:
            Draft pre-configured for reply

        Raises:
            NotImplementedError: Draft class not yet implemented

        Note:
            This is a stub for Story 3.6 (Implement Draft).
        """
        raise NotImplementedError("Draft class not yet implemented - Story 3.6")

    def reply_all(self, quote: bool = True) -> "Draft":
        """Create reply-all draft.

        NOT IMPLEMENTED - Draft class will be implemented in Story 3.6.

        Args:
            quote: Include original message quote

        Returns:
            Draft pre-configured for reply-all

        Raises:
            NotImplementedError: Draft class not yet implemented

        Note:
            This is a stub for Story 3.6 (Implement Draft).
        """
        raise NotImplementedError("Draft class not yet implemented - Story 3.6")

    def forward(self, include_attachments: bool = True) -> "Draft":
        """Create forward draft.

        NOT IMPLEMENTED - Draft class will be implemented in Story 3.6.

        Args:
            include_attachments: Include original attachments

        Returns:
            Draft pre-configured for forward

        Raises:
            NotImplementedError: Draft class not yet implemented

        Note:
            This is a stub for Story 3.6 (Implement Draft).
        """
        raise NotImplementedError("Draft class not yet implemented - Story 3.6")

    def __repr__(self) -> str:
        """Developer-friendly representation."""
        return f"Message(uid={self._uid}, folder='{self._folder}', from={self._from.email}, subject='{self._subject}')"
