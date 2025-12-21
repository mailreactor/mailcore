"""Message class with metadata and lazy body/attachment loading."""

from datetime import datetime
from typing import TYPE_CHECKING

from mailcore.attachment import Attachment
from mailcore.body import MessageBody
from mailcore.email_address import EmailAddress
from mailcore.protocols import IMAPConnection, SMTPConnection
from mailcore.types import MessageData, MessageFlag

if TYPE_CHECKING:
    from mailcore.draft import Draft


class Message:
    """Email message with metadata and lazy body/attachment loading.

    Metadata is always available (from IMAP SEARCH + BODYSTRUCTURE). Body content
    is fetched on-demand when accessed via the body property.

    Message receives both IMAP and SMTP connections at creation. Use Message.from_data()
    factory method to create from adapter DTOs.

    Note:
        Prefer Message.from_data() factory for production code (converts DTOs to entities).
        Direct instantiation via __init__ is mainly for testing.

    Example:
        >>> # Created directly (e.g., in tests)
        >>> message = Message(
        ...     imap=mock_imap,
        ...     smtp=mock_smtp,
        ...     default_sender='me@example.com',
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
        smtp: SMTPConnection | None,
        default_sender: str | None,
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
        """Initialize message with metadata and connections.

        Args:
            imap: IMAP connection for operations (mark_read, move_to, etc.)
            smtp: SMTP connection for compose operations (reply, forward) - None if not available
            default_sender: Default sender email for compose operations - None if not available
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
        """
        self._imap = imap
        self._smtp = smtp
        self._default_sender = default_sender
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
        self._body: MessageBody | None = None

    @classmethod
    def from_data(
        cls,
        data: MessageData,
        imap: IMAPConnection,
        smtp: SMTPConnection,
        default_sender: str,
    ) -> "Message":
        """Create Message entity from MessageData DTO.

        Factory method that converts adapter DTOs to domain entities.
        Injects BOTH imap and smtp at creation (no lazy injection).

        Args:
            data: MessageData DTO from adapter
            imap: IMAP connection for operations
            smtp: SMTP connection for compose operations
            default_sender: Default sender email (from Mailbox)

        Returns:
            Message entity with both IMAP and SMTP injected

        Example:
            >>> from mailcore import MessageData, EmailAddress, MessageFlag
            >>> from datetime import datetime
            >>> data = MessageData(
            ...     uid=42,
            ...     folder='INBOX',
            ...     message_id='<test@example.com>',
            ...     from_=EmailAddress('alice@example.com'),
            ...     to=[EmailAddress('bob@example.com')],
            ...     cc=[],
            ...     subject='Test',
            ...     date=datetime.now(),
            ...     flags={MessageFlag.SEEN},
            ...     size=1024,
            ...     custom_flags=set(),
            ...     in_reply_to=None,
            ...     references=[],
            ...     attachments=[]
            ... )
            >>> message = Message.from_data(data, mock_imap, mock_smtp, 'me@example.com')
            >>> message.uid
            42
            >>> message._smtp is not None
            True
        """
        return cls(
            imap=imap,
            smtp=smtp,
            default_sender=default_sender,
            uid=data.uid,
            folder=data.folder,
            message_id=data.message_id,
            from_=data.from_,
            to=data.to,
            cc=data.cc,
            subject=data.subject,
            date=data.date,
            flags=data.flags,
            size=data.size,
            custom_flags=data.custom_flags,
            in_reply_to=data.in_reply_to,
            references=data.references,
            attachments=data.attachments,
        )

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

    async def delete(self, permanent: bool = False, trash_folder: str | None = None) -> None:
        """Delete message.

        Args:
            permanent: True = permanently delete, False = move to trash
            trash_folder: Required when permanent=False. Folder name for trash.

        Raises:
            ValueError: If permanent=False and trash_folder is None

        Examples:
            >>> # Move to trash
            >>> await message.delete(trash_folder="INBOX.Trash")

            >>> # Permanent delete
            >>> await message.delete(permanent=True)
        """
        if permanent:
            # Permanent delete - call adapter directly
            await self._imap.delete_message(folder=self._folder, uid=self._uid)
        else:
            # Move to trash - validate then call move_message
            if trash_folder is None:
                raise ValueError(
                    "trash_folder parameter required when permanent=False. "
                    "Specify the trash folder name explicitly, e.g., "
                    "message.delete(trash_folder='INBOX.Trash')"
                )
            await self._imap.move_message(uid=self._uid, from_folder=self._folder, to_folder=trash_folder)

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
            imap=self._imap,
            default_sender=self._default_sender or "",
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
            imap=self._imap,
            default_sender=self._default_sender or "",
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

    def forward(self, include_attachments: bool = True, include_body: bool = True) -> "Draft":
        """Create forward draft.

        Args:
            include_attachments: Include original attachments (fetched during send())
            include_body: Include original message body with formatted header (fetched during send())

        Returns:
            Draft pre-configured for forward

        Raises:
            ValueError: If SMTP connection not available

        Example:
            >>> draft = message.forward()
            >>> await draft.to('colleague@example.com').body('FYI').send()

            >>> # Forward without body
            >>> draft = message.forward(include_body=False)
            >>> await draft.to('colleague@example.com').send()
        """
        # Lazy import to avoid circular import at module level
        from mailcore.draft import Draft

        # Require SMTP connection (injected by Folder after IMAP query)
        if self._smtp is None:
            raise ValueError("SMTP connection not available - Message must come from Folder query")

        # Create Draft with forward settings
        draft = Draft(
            smtp=self._smtp,
            imap=self._imap,
            default_sender=self._default_sender or "",
            reference_message=self,
            include_attachments=include_attachments,
            include_body=include_body,
        )

        # Pre-populate subject: Add "Fwd:" prefix if not already present
        if self._subject.startswith("Fwd:"):
            draft.subject(self._subject)
        else:
            draft.subject(f"Fwd: {self._subject}")

        return draft

    async def edit(self) -> "Draft":
        """Convert message to editable draft.

        Only messages with \\Draft flag can be edited (security requirement).
        Fetches body immediately (eager loading).
        Returned draft tracks origin (UID, folder, flags) for smart save behavior.

        Returns:
            Draft pre-populated with message fields

        Raises:
            ValueError: If message does not have \\Draft flag or SMTP connection not available

        Note:
            Only saved drafts can be edited. Sent or received messages cannot be edited
            (security/safety requirement).

        Examples:
            >>> # Edit saved draft
            >>> drafts = await mailbox.folders['Drafts'].list()
            >>> draft_msg = drafts[0]
            >>> editable = await draft_msg.edit()
            >>> editable.body('Updated content')
            >>> await editable.send()

            >>> # Or save again
            >>> uid = await editable.save(folder='Drafts')  # Replaces original
        """
        # Lazy import to avoid circular import at module level
        from mailcore.draft import Draft

        # SECURITY: Only allow editing actual drafts
        if MessageFlag.DRAFT not in self._flags:
            raise ValueError(
                "Cannot edit message without \\Draft flag. "
                "Only saved drafts can be edited (sent/received messages are immutable)."
            )

        # Require SMTP connection
        if self._smtp is None:
            raise ValueError("SMTP connection not available - Message must come from Folder query")

        # Create Draft with origin tracking
        draft = Draft(
            smtp=self._smtp,
            imap=self._imap,
            default_sender=self._default_sender or "",
            original_message_uid=self._uid,
            original_message_folder=self._folder,
            original_message_flags=self._flags.copy(),
            original_custom_flags=self._custom_flags.copy(),
        )

        # Pre-populate: to, cc, subject
        draft.to([addr.to_rfc5322() for addr in self._to])
        if self._cc:
            draft.cc([addr.to_rfc5322() for addr in self._cc])
        draft.subject(self._subject)

        # Fetch and populate body (eager loading)
        text = await self.body.get_text()
        if text:
            draft.body(text)

        html = await self.body.get_html()
        if html:
            draft.body_html(html)

        # Copy attachments
        for att in self._attachments:
            draft.attach(att)

        return draft

    def __repr__(self) -> str:
        """Developer-friendly representation."""
        return f"Message(uid={self._uid}, folder='{self._folder}', from={self._from.email}, subject='{self._subject}')"
