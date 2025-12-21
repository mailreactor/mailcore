"""Abstract base classes defining connection protocol contracts for IMAP and SMTP adapters.

CRITICAL: Adapter implementations MUST base64 decode attachment content before returning.
IMAPClient returns base64-encoded bytes - use base64.b64decode() to prevent corrupt attachments.

Validated in Story 3.0: DOCX attachment 24,184 bytes base64 -> 17,671 bytes decoded.

IDLE Protocol Support (Story 3.28):
This module defines IDLE protocol methods (RFC 2177) to enable real-time email monitoring.
IDLE belongs in mailreactor (application layer), NOT mailcore (library layer).
mailcore provides protocol contracts - mailreactor implements infrastructure (event loops, webhooks).
"""

from abc import ABC, abstractmethod
from typing import Any

from mailcore.email_address import EmailAddress
from mailcore.query import Query
from mailcore.types import FolderInfo, FolderStatus, MessageFlag, MessageListData, SendResult


class IMAPConnection(ABC):
    """Abstract IMAP connection interface using high-level domain operations.

    All methods are stateless - folder is specified per operation.
    Adapter orchestrates low-level IMAP protocol (SELECT, SEARCH, FETCH, etc.).

    Adapter returns DTOs (MessageListData) - domain converts to entities.
    Separates data (what adapters return) from behavior (what domain adds).

    Note:
        Connection management (connect, disconnect, pooling, reconnection)
        is the implementation's responsibility. Mailbox just uses the connection.

        DTO Pattern (Story 3.21):
        - Adapter creates MessageData DTOs (pure data, no behavior)
        - Returns MessageListData with pagination metadata
        - Folder receives DTOs, converts to Message entities via Message.from_data()
        - Folder injects BOTH imap AND smtp at creation (no lazy injection)
        - Messages returned to user have both IMAP and SMTP
    """

    @abstractmethod
    async def query_messages(
        self,
        folder: str,
        query: Query,
        include_body: bool = False,
        include_attachment_metadata: bool = True,
        limit: int | None = None,
        offset: int = 0,
    ) -> MessageListData:
        """Query messages from folder matching criteria.

        Combines IMAP operations: SELECT + SEARCH + FETCH + STATUS
        Creates MessageData DTOs (pure data, no behavior).
        Returns MessageListData with pagination metadata.

        Adapter returns DTOs - Folder converts to Message entities with behavior.

        Args:
            folder: Folder name
            query: Query object with search criteria (use query.to_imap_criteria() to get IMAP list)
            include_body: If True, fetch body text/html (lazy loaded if False)
            include_attachment_metadata: If True, parse attachment metadata from BODYSTRUCTURE.
                                          Attachment content is ALWAYS lazy-loaded via attachment.read()
                                          regardless of this flag.
            limit: Maximum messages to return (None = unlimited)
            offset: Skip first N messages (for pagination)

        Returns:
            MessageListData with:
                - messages: List of MessageData DTOs (pure data)
                - total_matches: Total messages matching query (before limit)
                - total_in_folder: Total messages in folder (unfiltered)
                - folder: Folder name

            MessageData always includes: uid, folder, message_id, from_, to, cc, subject, date,
                                         flags, size
            Conditionally includes: body text/html (if include_body=True),
                                    attachments (if include_attachment_metadata=True)

        Note:
            Adapter decides HOW to fetch efficiently based on what's requested.
            Adapter returns DTOs - no behavior, just data.
            Folder converts DTOs to Message entities with Message.from_data(dto, imap, smtp).
            Core domain uses domain language (include_body), not IMAP concepts (FETCH BODY[TEXT]).

        Example:
            from mailcore import Q

            # Build query using Q builder
            query = Q.from_('alice@example.com') & Q.unseen()

            data = await imap.query_messages(
                'INBOX',
                query,
                include_body=False,                # Don't fetch body yet
                include_attachment_metadata=True,  # Parse attachment metadata from BODYSTRUCTURE
                limit=50
            )

            # Returns MessageListData with MessageData DTOs
            # Folder converts to Message entities with behavior
        """
        ...

    @abstractmethod
    async def fetch_message_body(self, folder: str, uid: int) -> tuple[str | None, str | None]:
        """Fetch message body parts (lazy loading).

        Combines IMAP operations: SELECT + FETCH BODY[TEXT] + FETCH BODY[HTML]

        Args:
            folder: Folder name
            uid: Message UID

        Returns:
            Tuple of (plain_text, html) - either can be None

        Example:
            text, html = await imap.fetch_message_body('INBOX', 42)
        """
        ...

    @abstractmethod
    async def fetch_attachment_content(self, folder: str, uid: int, part_index: str) -> bytes:
        """Fetch attachment content from IMAP (lazy loading).

        Combines IMAP operations: SELECT + FETCH BODY[part]

        Args:
            folder: Folder name
            uid: Message UID
            part_index: IMAP MIME part number (e.g., "2", "1.2", "3.1")

        Returns:
            Decoded attachment content as bytes

        Note:
            Adapter MUST base64 decode the content before returning.
            This was validated in Story 3.0: IMAPClient returns base64-encoded bytes.

            Called by IMAPResolver when attachment.read() is invoked.
            The part_index comes from the attachment's imap:// URI.

        Example:
            # Called internally by IMAPResolver
            content = await imap.fetch_attachment_content(
                folder='INBOX',
                uid=42,
                part_index='2'  # Extracted from imap://INBOX/42/part/2
            )
        """
        ...

    @abstractmethod
    async def update_message_flags(
        self,
        folder: str,
        uid: int,
        add_flags: set[MessageFlag] | None = None,
        remove_flags: set[MessageFlag] | None = None,
        add_custom: set[str] | None = None,
        remove_custom: set[str] | None = None,
    ) -> tuple[set[MessageFlag], set[str]]:
        """Update message flags.

        Combines IMAP operations: SELECT + STORE

        Args:
            folder: Folder name
            uid: Message UID
            add_flags: Standard flags to add
            remove_flags: Standard flags to remove
            add_custom: Custom keywords to add
            remove_custom: Custom keywords to remove

        Returns:
            Tuple of (new_flags, new_custom_flags) after update

        Example:
            new_flags, custom = await imap.update_message_flags(
                'INBOX',
                42,
                add_flags={MessageFlag.SEEN},
                remove_flags={MessageFlag.FLAGGED}
            )
        """
        ...

    @abstractmethod
    async def move_message(self, uid: int, from_folder: str, to_folder: str) -> int:
        """Move message between folders.

        Combines IMAP operations: SELECT + MOVE (or SELECT + COPY + STORE + EXPUNGE)

        Args:
            uid: Message UID in source folder
            from_folder: Source folder name
            to_folder: Destination folder name

        Returns:
            New UID in destination folder (if server supports COPYUID/MOVE)
            Returns original UID if server doesn't provide new UID

        Note:
            Adapter handles MOVE extension vs fallback to COPY + EXPUNGE

        Example:
            new_uid = await imap.move_message(42, 'INBOX', 'Archive')
        """
        ...

    @abstractmethod
    async def copy_message(self, uid: int, from_folder: str, to_folder: str) -> int:
        """Copy message between folders.

        Combines IMAP operations: SELECT + COPY

        Args:
            uid: Message UID in source folder
            from_folder: Source folder name
            to_folder: Destination folder name

        Returns:
            New UID in destination folder (if server supports COPYUID)
            Returns 0 if server doesn't provide new UID

        Example:
            new_uid = await imap.copy_message(42, 'INBOX', 'Archive')
        """
        ...

    @abstractmethod
    async def delete_message(self, folder: str, uid: int) -> None:
        """Permanently delete message from folder.

        IMAP operations: SELECT folder + STORE \\Deleted + EXPUNGE

        WARNING: This is permanent deletion - no trash, no recovery.
        If you want to move to trash first, use move_message() before calling this.

        Args:
            folder: Folder name
            uid: Message UID

        Raises:
            IMAPError: If delete operation fails

        Example:
            # Move to trash (safe delete)
            await imap.move_message(42, 'INBOX', 'Trash')

            # Permanent delete (no trash)
            await imap.delete_message('INBOX', 42)
        """
        ...

    @abstractmethod
    async def get_folders(self) -> list[FolderInfo]:
        """Get all folders with metadata.

        IMAP operation: LIST

        Returns:
            List of folder information (name, special_use, has_children, etc.)

        Example:
            folders = await imap.get_folders()
            for folder in folders:
                print(f"{folder.name} - {folder.special_use}")
        """
        ...

    @abstractmethod
    async def get_folder_status(self, folder: str) -> FolderStatus:
        """Get folder statistics without selecting it.

        IMAP operation: STATUS (or SELECT if STATUS not supported)

        Args:
            folder: Folder name

        Returns:
            Folder status (message counts, UIDs, flags)

        Example:
            status = await imap.get_folder_status('INBOX')
            print(f"Unseen: {status.unseen_count}/{status.message_count}")
        """
        ...

    @abstractmethod
    async def create_folder(self, name: str) -> FolderInfo:
        """Create new folder.

        IMAP operation: CREATE + LIST (to get metadata)

        Args:
            name: Folder name (use '/' for hierarchy: 'Projects/2025')

        Returns:
            Created folder info

        Example:
            folder = await imap.create_folder('Archive/2025')
        """
        ...

    @abstractmethod
    async def delete_folder(self, name: str) -> None:
        """Delete folder (must be empty).

        IMAP operation: DELETE

        Args:
            name: Folder name to delete

        Raises:
            FolderNotEmptyError: If folder contains messages

        Example:
            await imap.delete_folder('OldArchive')
        """
        ...

    @abstractmethod
    async def rename_folder(self, old_name: str, new_name: str) -> FolderInfo:
        """Rename folder.

        IMAP operation: RENAME + LIST (to get new metadata)

        Args:
            old_name: Current folder name
            new_name: New folder name

        Returns:
            Renamed folder info

        Example:
            folder = await imap.rename_folder('Drafts', 'MyDrafts')
        """
        ...

    @abstractmethod
    async def append_message(
        self,
        folder: str,
        from_: EmailAddress,
        to: list[EmailAddress],
        subject: str,
        body_text: str | None = None,
        body_html: str | None = None,
        cc: list[EmailAddress] | None = None,
        attachments: list[Any] | None = None,  # list[Attachment] but avoiding circular import
        in_reply_to: str | None = None,
        references: list[str] | None = None,
        flags: set[MessageFlag] | None = None,
        custom_flags: set[str] | None = None,
    ) -> int:
        """Append message to IMAP folder.

        Adapter builds RFC 5322 MIME message from domain types.
        BCC intentionally excluded (security requirement).
        Preserves both standard and custom flags when provided.

        IMAP operation: SELECT + APPEND

        Args:
            folder: Folder name
            from_: Sender address
            to: Recipients (required)
            subject: Email subject
            body_text: Plain text body (optional)
            body_html: HTML body (optional)
            cc: CC recipients (optional)
            attachments: File attachments (optional)
            in_reply_to: Message-ID this replies to (optional)
            references: Thread chain (optional)
            flags: Standard IMAP flags (e.g., {MessageFlag.DRAFT, MessageFlag.SEEN})
            custom_flags: Custom IMAP keywords (e.g., {'$Forwarded', '$MDNSent'})

        Returns:
            UID of appended message

        Raises:
            FolderNotFoundError: If folder doesn't exist

        Note:
            Consistent with update_message_flags() signature (both support custom flags).
            Adapter is responsible for building RFC 5322 MIME message.

        Example:
            uid = await imap.append_message(
                folder='Drafts',
                from_=EmailAddress('sender@example.com'),
                to=[EmailAddress('recipient@example.com')],
                subject='Draft Message',
                body_text='Draft content',
                flags={MessageFlag.DRAFT, MessageFlag.SEEN},
                custom_flags={'$Forwarded'}
            )
        """
        ...

    @abstractmethod
    async def select_folder(self, folder: str) -> dict[str, Any]:
        """SELECT folder for operations (required before IDLE).

        IMAP operation: SELECT

        RFC 2177 IDLE requires an active folder selection before entering IDLE mode.
        This method explicitly selects a folder and returns server response with mailbox state.

        Args:
            folder: Folder name to select (e.g., 'INBOX')

        Returns:
            Dictionary with folder status after SELECT:
                - exists: Total message count in folder
                - recent: Count of messages with \\Recent flag
                - uidvalidity: UIDVALIDITY value (changes when UIDs reset)

        Raises:
            FolderNotFoundError: If folder doesn't exist

        Note:
            This is infrastructure-level (required for IDLE protocol), not domain logic.
            Most mailcore operations (query_messages, fetch_message_body, etc.) perform
            SELECT internally as needed. This method exposes SELECT for IDLE support.

        Example:
            # Prepare for IDLE monitoring
            status = await imap.select_folder('INBOX')
            print(f"Monitoring {status['exists']} messages")

            # Start IDLE mode (see idle_start)
            await imap.idle_start()
        """
        ...

    @abstractmethod
    async def idle_start(self) -> None:
        """Enter IDLE mode on selected folder (RFC 2177).

        IMAP operation: IDLE

        RFC 2177 IDLE allows server to push real-time notifications when folder state changes.
        Must call select_folder() first to choose which folder to monitor.

        Returns:
            None - enters IDLE mode (use idle_wait to receive events)

        Raises:
            RuntimeError: If no folder selected (must call select_folder first)
            NotImplementedError: If adapter doesn't support IDLE (e.g., IMAPClientAdapter)

        Note:
            IDLE is application-layer infrastructure, NOT library domain.
            mailcore defines protocol contract - mailreactor implements event loops.
            IMAPClientAdapter cannot support IDLE (synchronous IMAPClient limitation).
            For IDLE support, use mailcore-aioimaplib adapter.

        Example:
            # Select folder and start IDLE
            await imap.select_folder('INBOX')
            await imap.idle_start()

            # Wait for events (see idle_wait)
            events = await imap.idle_wait(timeout=1800)
        """
        ...

    @abstractmethod
    async def idle_wait(self, timeout: int = 1800) -> list[str]:
        """Wait for IDLE events (RFC 2177).

        IMAP operation: Wait for server responses during IDLE mode

        RFC 2177 default timeout: 1800 seconds (30 minutes).
        Server pushes notifications when folder state changes (new messages, deletions, flag changes).

        Args:
            timeout: Seconds to wait for events (default: 1800 per RFC 2177)
                     Client should send DONE before server timeout to maintain connection.

        Returns:
            List of event type strings from server:
                - "EXISTS": New message arrived
                - "EXPUNGE": Message deleted
                - "FETCH": Message flags changed
                - "RECENT": Recent count changed

        Raises:
            RuntimeError: If IDLE not started (must call idle_start first)
            NotImplementedError: If adapter doesn't support IDLE

        Note:
            After receiving events, call idle_done() to exit IDLE mode, then query
            folder to get updated state. For new messages, use uid_range(last_uid + 1, "*")
            to fetch only messages added since last check.

        Example:
            # Wait for events
            events = await imap.idle_wait(timeout=1800)

            if "EXISTS" in events:
                # Exit IDLE to query new messages
                await imap.idle_done()

                # Fetch messages after last seen UID
                new_messages = await folder.uid_range(last_uid + 1, "*").list()
        """
        ...

    @abstractmethod
    async def idle_done(self) -> None:
        """Exit IDLE mode (RFC 2177).

        IMAP operation: DONE (terminate IDLE)

        Exits IDLE mode and returns connection to normal command/response state.
        Must call this before executing other IMAP operations (SEARCH, FETCH, etc.).

        Returns:
            None - exits IDLE mode

        Raises:
            RuntimeError: If IDLE not active
            NotImplementedError: If adapter doesn't support IDLE

        Note:
            After DONE, folder remains selected - safe to immediately query for updates.
            To monitor again, call idle_start() (no need to re-select folder).

        Example:
            # Exit IDLE mode
            await imap.idle_done()

            # Now safe to execute queries
            messages = await folder.unseen().list()

            # Re-enter IDLE if desired
            await imap.idle_start()
        """
        ...


class SMTPConnection(ABC):
    """Abstract SMTP connection interface using mailcore domain types.

    Defines the SMTP operations mailcore requires.
    Implementations must inherit from this class.

    Note:
        Connection management (connect, disconnect, authentication)
        is the implementation's responsibility. Mailbox just uses the connection.
    """

    @property
    @abstractmethod
    def username(self) -> str:
        """Get SMTP authentication username.

        Returns:
            Username used for SMTP authentication. May be email address (user@gmail.com)
            or account identifier (john.smith).

        Note:
            This property exposes the username for sender address resolution.
            Mailbox uses this to auto-detect default_sender when not provided explicitly.

        Example:
            >>> smtp = AIOSMTPAdapter(username='user@gmail.com', ...)
            >>> print(smtp.username)
            'user@gmail.com'
        """
        ...

    @abstractmethod
    async def send_message(
        self,
        from_: EmailAddress,
        to: list[EmailAddress],
        subject: str,
        body_text: str | None = None,
        body_html: str | None = None,
        cc: list[EmailAddress] | None = None,
        bcc: list[EmailAddress] | None = None,
        attachments: list[Any] | None = None,  # list[Attachment] but avoiding circular import
        in_reply_to: str | None = None,
        references: list[str] | None = None,
    ) -> SendResult:
        """Send email message.

        Args:
            from_: Sender address
            to: Recipient addresses (required, at least one)
            subject: Email subject
            body_text: Plain text body (optional if body_html provided)
            body_html: HTML body (optional)
            cc: CC recipients (optional)
            bcc: BCC recipients (optional)
            attachments: File attachments (optional)
            in_reply_to: Message-ID this replies to (for threading)
            references: Thread chain (list of Message-IDs)

        Returns:
            SendResult with message_id and recipient acceptance status

        Raises:
            SMTPError: If sending fails
            ConnectionError: If SMTP connection lost

        Example:
            result = await smtp.send_message(
                from_=EmailAddress("sender@example.com", "Sender Name"),
                to=[EmailAddress("recipient@example.com")],
                subject="Test",
                body_text="Hello World",
                body_html="<p>Hello World</p>"
            )
            # Returns: SendResult(
            #     message_id='<msg-123@example.com>',
            #     accepted=['recipient@example.com'],
            #     rejected={}
            # )
        """
        ...
