"""Mailbox class - main entry point for email operations.

Provides three-tier folder access pattern:
1. Fixed shortcut (property): mailbox.inbox
2. Dict access: mailbox.folders['Archive']
3. Methods: send(), compose(), list_folders(), etc.

Connection injection pattern:
- Mailbox stores IMAP and SMTP connections
- inbox property creates Folder with both connections
- FolderDict creates Folder instances with both connections
- compose() creates Draft with SMTP connection
- All lazy (no network calls until methods are called)
"""

from collections import defaultdict
from collections.abc import Iterable

from mailcore.draft import Draft
from mailcore.email_address import EmailAddress
from mailcore.folder import Folder
from mailcore.message import Message
from mailcore.message_list import MessageList
from mailcore.protocols import IMAPConnection, SMTPConnection


class FolderDict:
    """Dict-like accessor for folders by name with direct connection injection.

    Returns new Folder instance on each access (no caching).
    Stores IMAP and SMTP connections directly (NO parent Mailbox reference).

    Args:
        imap: IMAP connection for folder operations
        smtp: SMTP connection for message composition
        default_sender: Default sender email address for message composition

    Example:
        >>> folders = FolderDict(imap=imap_adapter, smtp=smtp_adapter, default_sender='user@example.com')
        >>> archive = folders['Archive']  # Returns Folder('Archive')
        >>> sent = folders['Sent']        # Returns Folder('Sent')
        >>> # No caching - new instance every time
        >>> folder1 = folders['Archive']
        >>> folder2 = folders['Archive']
        >>> assert folder1 is not folder2  # True
    """

    def __init__(self, imap: IMAPConnection, smtp: SMTPConnection, default_sender: str) -> None:
        """Initialize FolderDict with connections.

        Args:
            imap: IMAP connection (injected directly)
            smtp: SMTP connection (injected directly)
            default_sender: Default sender email address (validated by Mailbox)
        """
        self._imap = imap
        self._smtp = smtp
        self._default_sender = default_sender

    def __getitem__(self, name: str) -> Folder:
        """Get folder by name (creates new instance, no caching).

        Args:
            name: Folder name (e.g., "Archive", "Sent", "Projects/2025")

        Returns:
            New Folder instance with connections injected

        Example:
            >>> folders = FolderDict(imap, smtp, default_sender)
            >>> archive = folders['Archive']
            >>> projects = folders['Projects/2025']
        """
        return Folder(imap=self._imap, smtp=self._smtp, name=name, default_sender=self._default_sender)


class Mailbox:
    """Main entry point for email operations with folder access and message composition.

    Provides three-tier folder access to prevent namespace collisions:
    - Tier 1: Fixed shortcut (property) - ONLY inbox
    - Tier 2: Dict access - ALL other folders via folders['Name']
    - Tier 3: Methods - Don't collide with folder names

    Args:
        imap: IMAP connection for folder operations
        smtp: SMTP connection for sending
        default_sender: Default sender email address (optional, auto-detected from SMTP)

    Example:
        >>> from mailcore import Mailbox
        >>> from mailcore.adapters import IMAPClientAdapter, AIOSMTPAdapter
        >>>
        >>> # Create connections
        >>> imap = IMAPClientAdapter(...)
        >>> smtp = AIOSMTPAdapter(...)
        >>>
        >>> # Create mailbox
        >>> mailbox = Mailbox(imap=imap, smtp=smtp, default_sender='me@example.com')
        >>> mailbox  # REPL-friendly repr
        Mailbox(default_sender='me@example.com')
        >>>
        >>> # Tier 1: Fixed shortcut (inbox only)
        >>> inbox = mailbox.inbox
        >>>
        >>> # Tier 2: Dict access (all other folders)
        >>> sent = mailbox.folders['Sent']
        >>> archive = mailbox.folders['Archive']
        >>> compose_folder = mailbox.folders['Compose']  # No collision!
        >>>
        >>> # Tier 3: Methods (don't collide with folder names)
        >>> draft = mailbox.draft()
        >>> await mailbox.send(to='alice@example.com', subject='Hi', body='Hello')
    """

    def __init__(self, imap: IMAPConnection, smtp: SMTPConnection, default_sender: str | None = None) -> None:
        """Initialize mailbox with IMAP and SMTP connections.

        Args:
            imap: Connected and authenticated IMAP connection
            smtp: Connected and authenticated SMTP connection
            default_sender: Default sender email (optional).
                If not provided, attempts to parse smtp.username as email.

        Raises:
            ValueError: If default_sender not provided and smtp.username is not valid email

        Note:
            Connection management (connect, disconnect, pooling, reconnection)
            is the caller's responsibility.

        Example:
            >>> # Auto-detect from SMTP username (if valid email)
            >>> mailbox = Mailbox(imap=imap_adapter, smtp=smtp_adapter)
            >>>
            >>> # Explicit default_sender (required if smtp.username not email)
            >>> mailbox = Mailbox(imap=imap_adapter, smtp=smtp_adapter, default_sender='me@example.com')
        """
        self._imap = imap
        self._smtp = smtp
        self._default_sender = self._validate_default_sender(smtp, default_sender)
        # Create FolderDict with direct connection injection (NO parent reference)
        self._folders = FolderDict(imap=self._imap, smtp=self._smtp, default_sender=self._default_sender)

    @staticmethod
    def _validate_default_sender(smtp: SMTPConnection, default_sender: str | None) -> str:
        """Validate and return default sender email.

        Args:
            smtp: SMTP connection with username property
            default_sender: Optional explicit default sender

        Returns:
            Validated email address string

        Raises:
            ValueError: If default_sender invalid or smtp.username not email when auto-detecting
        """
        if default_sender is not None:
            # Explicit default_sender provided - validate it
            try:
                EmailAddress(email=default_sender)
                return default_sender
            except ValueError as e:
                raise ValueError(f"Invalid default_sender email address: '{default_sender}'. {str(e)}") from e

        # Try to use smtp.username as default_sender
        try:
            EmailAddress(email=smtp.username)
            return smtp.username
        except ValueError:
            # smtp.username is not valid email - require explicit default_sender
            raise ValueError(
                f"Cannot use SMTP username '{smtp.username}' as default sender address because "
                "it is not a valid email address. Please provide explicit default_sender parameter:\n"
                "  Mailbox(imap=imap, smtp=smtp, default_sender='your@email.com')"
            )

    @property
    def inbox(self) -> Folder:
        """Access INBOX folder (fixed shortcut).

        Returns:
            Folder instance for INBOX with IMAP and SMTP connections

        Example:
            >>> inbox = mailbox.inbox
            >>> messages = await inbox.unseen().list(limit=50)
        """
        return Folder(imap=self._imap, smtp=self._smtp, name="INBOX", default_sender=self._default_sender)

    @property
    def folders(self) -> FolderDict:
        """Access folders by name via dict interface.

        Returns:
            FolderDict for accessing any folder by name

        Example:
            >>> sent = mailbox.folders['Sent']
            >>> archive = mailbox.folders['Archive']
            >>> projects = mailbox.folders['Projects/2025']
        """
        return self._folders

    def draft(self) -> Draft:
        """Create new draft message.

        Returns:
            Draft with SMTP and IMAP connections for building, sending, and saving email

        Example:
            >>> # Compose and send
            >>> draft = mailbox.draft()
            >>> await draft.to('alice@example.com').subject('Hi').body('Hello').send()

            >>> # Save for later
            >>> draft = mailbox.draft()
            >>> draft.to('alice@example.com').subject('Hi').body('Draft')
            >>> uid = await draft.save(folder='Drafts')
        """
        return Draft(smtp=self._smtp, imap=self._imap, default_sender=self._default_sender)

    async def send(
        self,
        *,
        to: str | list[str],
        subject: str,
        body: str | None = None,
        body_html: str | None = None,
        cc: str | list[str] | None = None,
        bcc: str | list[str] | None = None,
    ) -> str:
        """Compose and send email in one call (shortcut).

        Args:
            to: Recipient(s) (required)
            subject: Email subject (required)
            body: Plain text body (optional if body_html provided)
            body_html: HTML body (optional)
            cc: CC recipient(s) (optional)
            bcc: BCC recipient(s) (optional)

        Returns:
            Message-ID of sent message

        Raises:
            ValueError: If required fields missing or invalid

        Example:
            >>> message_id = await mailbox.send(
            ...     to='alice@example.com',
            ...     subject='Hello',
            ...     body='World'
            ... )
        """
        # Create draft and apply fields
        draft = self.draft()
        draft.to(to)
        draft.subject(subject)

        if body is not None:
            draft.body(body)
        if body_html is not None:
            draft.body_html(body_html)
        if cc is not None:
            draft.cc(cc)
        if bcc is not None:
            draft.bcc(bcc)

        # Send
        return await draft.send()

    async def list_folders(self, pattern: str | None = None) -> list[str]:
        """List all folders (or filtered by pattern).

        Args:
            pattern: Optional glob pattern (e.g., "Projects/*")

        Returns:
            List of folder names

        Example:
            >>> # List all folders
            >>> all_folders = await mailbox.list_folders()
            >>> # ['INBOX', 'Sent', 'Archive', 'Trash']
            >>>
            >>> # List with pattern
            >>> projects = await mailbox.list_folders("Projects/*")
            >>> # ['Projects/2025', 'Projects/2024']
        """
        folder_infos = await self._imap.get_folders()
        folder_names = [info.name for info in folder_infos]

        # Filter by pattern if provided
        if pattern is not None:
            # Simple glob matching (*, ?)
            import fnmatch

            folder_names = [name for name in folder_names if fnmatch.fnmatch(name, pattern)]

        return folder_names

    async def create_folder(self, name: str) -> Folder:
        """Create new folder.

        Args:
            name: Folder name (use '/' for hierarchy: 'Projects/2025')

        Returns:
            Folder instance for the newly created folder

        Raises:
            FolderExistsError: If folder already exists

        Example:
            >>> archive = await mailbox.create_folder('Archive')
            >>> await archive.list()  # Works immediately
            >>>
            >>> # Create nested folder
            >>> project = await mailbox.create_folder('Projects/2025')
        """
        await self._imap.create_folder(name=name)
        return Folder(imap=self._imap, smtp=self._smtp, name=name, default_sender=self._default_sender)

    async def delete_folder(self, name: str) -> None:
        """Delete folder (must be empty).

        Args:
            name: Folder name to delete

        Raises:
            FolderNotEmptyError: If folder contains messages

        Example:
            >>> await mailbox.delete_folder('Projects/2024')
        """
        await self._imap.delete_folder(name=name)

    async def rename_folder(self, old_name: str, new_name: str) -> None:
        """Rename folder.

        Args:
            old_name: Current folder name
            new_name: New folder name

        Example:
            >>> await mailbox.rename_folder('Old Archive', 'Archive 2024')
        """
        await self._imap.rename_folder(old_name=old_name, new_name=new_name)

    async def move(
        self,
        messages: MessageList | list[Message] | Iterable[Message],
        *,
        to_folder: str,
    ) -> None:
        """Move messages to folder (automatically groups by source folder for efficiency).

        Args:
            messages: MessageList, list[Message], or Iterable[Message]
            to_folder: Destination folder name

        Example:
            >>> # Move messages from query result
            >>> spam = await inbox.from_('spam@example.com').list()
            >>> await mailbox.move(spam, to_folder='Spam')
            >>>
            >>> # Move messages from multiple folders (automatically groups)
            >>> inbox_spam = await mailbox.inbox.from_('spam').list()
            >>> archive_spam = await mailbox.folders['Archive'].from_('spam').list()
            >>> all_spam = list(inbox_spam) + list(archive_spam)
            >>> await mailbox.move(all_spam, to_folder='Spam')
            >>> # Result: One IMAP MOVE command for inbox, one for archive
        """
        # Group messages by source folder
        grouped: dict[str, list[int]] = defaultdict(list)
        for msg in messages:
            grouped[msg.folder].append(msg.uid)

        # Execute one IMAP command per source folder
        for source_folder, uids in grouped.items():
            # Call move_message for each UID (protocol expects single UID)
            for uid in uids:
                await self._imap.move_message(uid=uid, from_folder=source_folder, to_folder=to_folder)

    async def copy(
        self,
        messages: MessageList | list[Message] | Iterable[Message],
        *,
        to_folder: str,
    ) -> None:
        """Copy messages to folder (automatically groups by source folder for efficiency).

        Args:
            messages: MessageList, list[Message], or Iterable[Message]
            to_folder: Destination folder name

        Example:
            >>> # Copy important messages to archive
            >>> important = await inbox.keyword('Important').list()
            >>> await mailbox.copy(important, to_folder='Archive')
        """
        # Group messages by source folder
        grouped: dict[str, list[int]] = defaultdict(list)
        for msg in messages:
            grouped[msg.folder].append(msg.uid)

        # Execute one IMAP command per source folder
        for source_folder, uids in grouped.items():
            # Call copy_message for each UID (protocol expects single UID)
            for uid in uids:
                await self._imap.copy_message(uid=uid, from_folder=source_folder, to_folder=to_folder)

    async def delete(
        self,
        messages: MessageList | list[Message] | Iterable[Message],
        *,
        permanent: bool = False,
        trash_folder: str | None = None,
    ) -> None:
        """Delete messages (automatically groups by source folder for efficiency).

        Args:
            messages: MessageList, list[Message], or Iterable[Message]
            permanent: True = expunge, False = move to trash
            trash_folder: Required when permanent=False

        Raises:
            ValueError: If permanent=False and trash_folder is None

        Example:
            >>> # Move to trash
            >>> old_messages = await inbox.before(date(2024, 1, 1)).list()
            >>> await mailbox.delete(old_messages, trash_folder="INBOX.Trash")
            >>>
            >>> # Permanent delete
            >>> await mailbox.delete(old_messages, permanent=True)
        """
        if not permanent and trash_folder is None:
            raise ValueError(
                "trash_folder parameter required when permanent=False. "
                "Specify the trash folder name explicitly, e.g., "
                "mailbox.delete(messages, trash_folder='INBOX.Trash')"
            )

        # Group messages by source folder
        grouped: dict[str, list[int]] = defaultdict(list)
        for msg in messages:
            grouped[msg.folder].append(msg.uid)

        # Execute operations
        for source_folder, uids in grouped.items():
            if permanent:
                for uid in uids:
                    await self._imap.delete_message(folder=source_folder, uid=uid)
            else:
                # trash_folder guaranteed non-None by validation above
                assert trash_folder is not None
                for uid in uids:
                    await self._imap.move_message(uid=uid, from_folder=source_folder, to_folder=trash_folder)

    async def get(self, message_id: str) -> Message | None:
        """Search all folders for message by Message-ID.

        Sequential search across folders (optimization can come later).

        Args:
            message_id: RFC 5322 Message-ID

        Returns:
            Message if found, None if not found in any folder

        Example:
            >>> # Search all folders for message
            >>> message = await mailbox.get("msg-123@example.com")
            >>> if message:
            ...     print(f"Found in {message.folder}")
            ...     text = await message.body.get_text()
        """
        # Get all folders
        folders = await self.list_folders()

        # Search each folder sequentially
        for folder_name in folders:
            # Get all messages from folder and check message_id
            # Note: This is inefficient but Query doesn't support message_id search yet
            # In production, this would use IMAP SEARCH HEADER Message-ID
            from mailcore.query import Query

            query = Query.all()
            try:
                list_data = await self._imap.query_messages(folder=folder_name, query=query, limit=None)

                # Search for matching message_id in DTOs, convert to entity if found
                for msg_data in list_data.messages:
                    if msg_data.message_id == message_id:
                        # Convert DTO to entity with connections
                        return Message.from_data(msg_data, self._imap, self._smtp, self._default_sender)
            except Exception:
                # Folder might not exist or be accessible, continue to next
                continue

        # Not found in any folder
        return None

    def __repr__(self) -> str:
        """Developer-friendly representation showing connection info.

        Returns:
            Mailbox(default_sender='...')

        Example:
            >>> mailbox = Mailbox(imap=imap, smtp=smtp, default_sender='me@example.com')
            >>> mailbox
            Mailbox(default_sender='me@example.com')
        """
        return f"Mailbox(default_sender={self._default_sender!r})"
