"""Full mock implementations of IMAPConnection and SMTPConnection for E2E tests.

Story 3.9: These mocks implement the complete ABC contracts with in-memory storage.
They provide realistic IMAP/SMTP behavior for E2E testing without external servers.

Usage:
    For unit tests: Use AsyncMock fixtures from conftest.py (mock_imap, mock_smtp)
    For E2E tests: Use these full implementations (MockIMAPConnection, MockSMTPConnection)
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from mailcore.attachment import Attachment, IMAPResolver
from mailcore.email_address import EmailAddress
from mailcore.exceptions import FolderNotFoundError
from mailcore.protocols import IMAPConnection, SMTPConnection
from mailcore.query import Query
from mailcore.types import FolderInfo, FolderStatus, MessageData, MessageFlag, MessageListData, SendResult


@dataclass
class MockMessage:
    """Internal storage for mock IMAP message."""

    uid: int
    folder: str
    message_id: str
    from_: EmailAddress
    to: list[EmailAddress]
    cc: list[EmailAddress]
    subject: str
    date: datetime
    flags: set[MessageFlag] = field(default_factory=set)
    custom_flags: set[str] = field(default_factory=set)
    size: int = 100
    in_reply_to: str | None = None
    references: list[str] = field(default_factory=list)
    body_text: str | None = None
    body_html: str | None = None
    attachments: list[dict[str, Any]] = field(
        default_factory=list
    )  # List of {part_index, filename, content_type, content}


class MockIMAPConnection(IMAPConnection):
    """Full mock IMAP connection for E2E tests.

    Implements all 12 IMAPConnection abstract methods with in-memory storage.
    Provides realistic behavior (UIDs, flags, folders) without real IMAP server.

    Features:
    - In-memory message storage per folder
    - Auto-incrementing UIDs per folder
    - Flag operations (add/remove)
    - Folder operations (create, delete, rename)
    - Query filtering with IMAP criteria
    - Thread-safe with asyncio locks
    """

    def __init__(self):
        """Initialize mock IMAP with empty storage."""
        self._folders: dict[str, list[MockMessage]] = {"INBOX": []}
        self._uid_counters: dict[str, int] = {"INBOX": 1}
        self._lock = asyncio.Lock()

    async def query_messages(
        self,
        folder: str,
        query: Query,
        include_body: bool = False,
        include_attachment_metadata: bool = True,
        limit: int | None = None,
        offset: int = 0,
    ) -> MessageListData:
        """Query messages from folder matching criteria - returns DTOs."""
        async with self._lock:
            if folder not in self._folders:
                return MessageListData(messages=[], total_matches=0, total_in_folder=0, folder=folder)

            all_messages = self._folders[folder]

            # Filter by query criteria
            criteria = query.to_imap_criteria()
            filtered = self._filter_messages(all_messages, criteria)

            total_matches = len(filtered)
            total_in_folder = len(all_messages)

            # Apply pagination
            paginated = filtered[offset : offset + limit] if limit else filtered[offset:]

            # Convert to MessageData DTOs (pure data, no connections)
            message_data_list = []
            for mock_msg in paginated:
                # Create attachment metadata if requested
                attachments = []
                if include_attachment_metadata:
                    for att_data in mock_msg.attachments:
                        uri = f"imap://{folder}/{mock_msg.uid}/part/{att_data['part_index']}"
                        att = Attachment(
                            uri=uri,
                            filename=att_data["filename"],
                            content_type=att_data["content_type"],
                            size=len(att_data["content"]),
                            _resolver=IMAPResolver(self),
                        )
                        attachments.append(att)

                data = MessageData(
                    uid=mock_msg.uid,
                    folder=folder,
                    message_id=mock_msg.message_id,
                    from_=mock_msg.from_,
                    to=mock_msg.to,
                    cc=mock_msg.cc,
                    subject=mock_msg.subject,
                    date=mock_msg.date,
                    flags=mock_msg.flags,
                    custom_flags=mock_msg.custom_flags,
                    size=mock_msg.size,
                    in_reply_to=mock_msg.in_reply_to,
                    references=mock_msg.references,
                    attachments=attachments,
                )

                message_data_list.append(data)

            return MessageListData(
                messages=message_data_list,
                total_matches=total_matches,
                total_in_folder=total_in_folder,
                folder=folder,
            )

    def _filter_messages(self, messages: list[MockMessage], criteria: list[str]) -> list[MockMessage]:
        """Filter messages by IMAP criteria."""
        if not criteria:
            return messages

        filtered = messages[:]

        # Parse criteria (simplified IMAP syntax)
        i = 0
        while i < len(criteria):
            criterion = criteria[i]

            if criterion == "FROM":
                sender = criteria[i + 1]
                filtered = [m for m in filtered if sender.lower() in m.from_.email.lower()]
                i += 2
            elif criterion == "TO":
                recipient = criteria[i + 1]
                filtered = [m for m in filtered if any(recipient.lower() in to.email.lower() for to in m.to)]
                i += 2
            elif criterion == "SUBJECT":
                subject_text = criteria[i + 1]
                filtered = [m for m in filtered if subject_text.lower() in m.subject.lower()]
                i += 2
            elif criterion == "BODY":
                body_text = criteria[i + 1]
                filtered = [
                    m
                    for m in filtered
                    if (m.body_text and body_text.lower() in m.body_text.lower())
                    or (m.body_html and body_text.lower() in m.body_html.lower())
                ]
                i += 2
            elif criterion == "UNSEEN":
                filtered = [m for m in filtered if MessageFlag.SEEN not in m.flags]
                i += 1
            elif criterion == "SEEN":
                filtered = [m for m in filtered if MessageFlag.SEEN in m.flags]
                i += 1
            elif criterion == "ANSWERED":
                filtered = [m for m in filtered if MessageFlag.ANSWERED in m.flags]
                i += 1
            elif criterion == "FLAGGED":
                filtered = [m for m in filtered if MessageFlag.FLAGGED in m.flags]
                i += 1
            elif criterion == "DELETED":
                filtered = [m for m in filtered if MessageFlag.DELETED in m.flags]
                i += 1
            elif criterion == "DRAFT":
                filtered = [m for m in filtered if MessageFlag.DRAFT in m.flags]
                i += 1
            elif criterion == "RECENT":
                filtered = [m for m in filtered if MessageFlag.RECENT in m.flags]
                i += 1
            elif criterion == "ALL":
                # No filtering
                i += 1
            else:
                # Unknown criterion - skip
                i += 1

        return filtered

    async def fetch_message_body(self, folder: str, uid: int) -> tuple[str | None, str | None]:
        """Fetch message body parts (lazy loading)."""
        async with self._lock:
            if folder not in self._folders:
                return (None, None)

            for msg in self._folders[folder]:
                if msg.uid == uid:
                    return (msg.body_text, msg.body_html)

            return (None, None)

    async def fetch_attachment_content(self, folder: str, uid: int, part_index: str) -> bytes:
        """Fetch attachment content (base64 decoded)."""
        async with self._lock:
            if folder not in self._folders:
                raise ValueError(f"Folder {folder} not found")

            for msg in self._folders[folder]:
                if msg.uid == uid:
                    for att in msg.attachments:
                        if att["part_index"] == part_index:
                            return att["content"]  # Already decoded bytes

            raise ValueError(f"Attachment {part_index} not found for message {uid}")

    async def update_message_flags(
        self,
        folder: str,
        uid: int,
        add_flags: set[MessageFlag] | None = None,
        remove_flags: set[MessageFlag] | None = None,
        add_custom: set[str] | None = None,
        remove_custom: set[str] | None = None,
    ) -> tuple[set[MessageFlag], set[str]]:
        """Update message flags."""
        async with self._lock:
            if folder not in self._folders:
                return (set(), set())

            for msg in self._folders[folder]:
                if msg.uid == uid:
                    # Add standard flags
                    if add_flags:
                        msg.flags.update(add_flags)

                    # Remove standard flags
                    if remove_flags:
                        msg.flags.difference_update(remove_flags)

                    # Add custom flags
                    if add_custom:
                        msg.custom_flags.update(add_custom)

                    # Remove custom flags
                    if remove_custom:
                        msg.custom_flags.difference_update(remove_custom)

                    return (msg.flags, msg.custom_flags)

            return (set(), set())

    async def move_message(self, uid: int, from_folder: str, to_folder: str) -> int:
        """Move message between folders."""
        async with self._lock:
            if from_folder not in self._folders or to_folder not in self._folders:
                raise ValueError(f"Folder not found: {from_folder} or {to_folder}")

            # Find and remove from source
            msg = None
            for i, m in enumerate(self._folders[from_folder]):
                if m.uid == uid:
                    msg = self._folders[from_folder].pop(i)
                    break

            if msg is None:
                raise ValueError(f"Message {uid} not found in {from_folder}")

            # Assign new UID in destination
            new_uid = self._uid_counters[to_folder]
            self._uid_counters[to_folder] += 1

            msg.uid = new_uid
            msg.folder = to_folder

            # Add to destination
            self._folders[to_folder].append(msg)

            return new_uid

    async def copy_message(self, uid: int, from_folder: str, to_folder: str) -> int:
        """Copy message between folders."""
        async with self._lock:
            if from_folder not in self._folders or to_folder not in self._folders:
                raise ValueError(f"Folder not found: {from_folder} or {to_folder}")

            # Find message
            msg = None
            for m in self._folders[from_folder]:
                if m.uid == uid:
                    msg = m
                    break

            if msg is None:
                raise ValueError(f"Message {uid} not found in {from_folder}")

            # Create copy with new UID
            new_uid = self._uid_counters[to_folder]
            self._uid_counters[to_folder] += 1

            # Deep copy the message
            from copy import deepcopy

            msg_copy = deepcopy(msg)
            msg_copy.uid = new_uid
            msg_copy.folder = to_folder

            # Add to destination
            self._folders[to_folder].append(msg_copy)

            return new_uid

    async def delete_message(self, folder: str, uid: int) -> None:
        """Permanently delete message from folder."""
        async with self._lock:
            if folder in self._folders:
                self._folders[folder] = [m for m in self._folders[folder] if m.uid != uid]

    async def get_folders(self) -> list[FolderInfo]:
        """Get all folders with metadata."""
        async with self._lock:
            return [FolderInfo(name=name, flags=[], has_children=False) for name in sorted(self._folders.keys())]

    async def get_folder_status(self, folder: str) -> FolderStatus:
        """Get folder statistics."""
        async with self._lock:
            if folder not in self._folders:
                return FolderStatus(message_count=0, unseen_count=0, uidnext=1)

            messages = self._folders[folder]
            unseen = sum(1 for m in messages if "\\Seen" not in m.flags)

            return FolderStatus(
                message_count=len(messages), unseen_count=unseen, uidnext=self._uid_counters.get(folder, 1)
            )

    async def create_folder(self, name: str) -> FolderInfo:
        """Create new folder."""
        async with self._lock:
            if name in self._folders:
                raise ValueError(f"Folder {name} already exists")

            self._folders[name] = []
            self._uid_counters[name] = 1

            return FolderInfo(name=name, flags=[], has_children=False)

    async def delete_folder(self, name: str) -> None:
        """Delete folder (must be empty)."""
        async with self._lock:
            if name not in self._folders:
                raise ValueError(f"Folder {name} not found")

            if self._folders[name]:
                raise ValueError(f"Folder {name} is not empty")

            del self._folders[name]
            del self._uid_counters[name]

    async def rename_folder(self, old_name: str, new_name: str) -> FolderInfo:
        """Rename folder."""
        async with self._lock:
            if old_name not in self._folders:
                raise ValueError(f"Folder {old_name} not found")

            if new_name in self._folders:
                raise ValueError(f"Folder {new_name} already exists")

            self._folders[new_name] = self._folders.pop(old_name)
            self._uid_counters[new_name] = self._uid_counters.pop(old_name)

            # Update folder field in all messages
            for msg in self._folders[new_name]:
                msg.folder = new_name

            return FolderInfo(name=new_name, flags=[], has_children=False)

    # Helper methods for E2E test setup

    def add_test_message(
        self,
        folder: str,
        from_: str | EmailAddress,
        to: list[str | EmailAddress],
        subject: str,
        body_text: str | None = None,
        body_html: str | None = None,
        flags: list[str] | None = None,
        attachments: list[dict[str, Any]] | None = None,
    ) -> int:
        """Helper to add message to mock storage (for E2E test setup)."""
        if folder not in self._folders:
            self._folders[folder] = []
            self._uid_counters[folder] = 1

        uid = self._uid_counters[folder]
        self._uid_counters[folder] += 1

        # Convert strings to EmailAddress
        if isinstance(from_, str):
            from_ = EmailAddress(from_)
        to_list = [EmailAddress(t) if isinstance(t, str) else t for t in to]

        msg = MockMessage(
            uid=uid,
            folder=folder,
            message_id=f"<msg-{uid}@example.com>",
            from_=from_,
            to=to_list,
            cc=[],
            subject=subject,
            date=datetime.now(timezone.utc),
            flags=set(flags or []),
            body_text=body_text,
            body_html=body_html,
            attachments=attachments or [],
        )

        self._folders[folder].append(msg)
        return uid

    async def append_message(
        self,
        folder: str,
        from_: EmailAddress,
        to: list[EmailAddress],
        subject: str,
        body_text: str | None = None,
        body_html: str | None = None,
        cc: list[EmailAddress] | None = None,
        attachments: list[Any] | None = None,
        in_reply_to: str | None = None,
        references: list[str] | None = None,
        flags: set[MessageFlag] | None = None,
        custom_flags: set[str] | None = None,
    ) -> int:
        """Append message to folder with specified flags.

        Delegates to _add_message helper with flags support.
        """
        # Ensure folder exists
        if folder not in self._folders:
            self._folders[folder] = []
            self._uid_counters[folder] = 1

        uid = self._uid_counters[folder]
        self._uid_counters[folder] += 1

        # Build combined flags set
        all_flags = set(flags) if flags else set()

        msg = MockMessage(
            uid=uid,
            folder=folder,
            message_id=f"<msg-{uid}@example.com>",
            from_=from_,
            to=to,
            cc=cc or [],
            subject=subject,
            date=datetime.now(timezone.utc),
            flags=all_flags,
            custom_flags=custom_flags or set(),
            body_text=body_text,
            body_html=body_html,
            attachments=attachments or [],
        )

        self._folders[folder].append(msg)
        return uid

    async def select_folder(self, folder: str) -> dict[str, Any]:
        """SELECT folder for operations (mock implementation).

        Returns mock folder status for testing.

        Args:
            folder: Folder name to select

        Returns:
            Dictionary with mock folder status:
                - exists: Total message count
                - recent: Recent message count
                - uidvalidity: Mock UIDVALIDITY value
        """
        # Check if folder exists in mock storage
        if folder in self._folders:
            # Return mock status (exists = total messages in folder)
            return {"exists": len(self._folders[folder]), "recent": 0, "uidvalidity": 1}

        # Folder not found
        raise FolderNotFoundError(folder)

    async def idle_start(self) -> None:
        """Enter IDLE mode (NOT SUPPORTED by MockIMAPConnection).

        Raises:
            NotImplementedError: Mock does not support IDLE (consistent with IMAPClientAdapter)
        """
        raise NotImplementedError(
            "IDLE not supported by MockIMAPConnection. This mock mimics IMAPClientAdapter behavior for testing."
        )

    async def idle_wait(self, timeout: int = 1800) -> list[str]:
        """Wait for IDLE events (NOT SUPPORTED by MockIMAPConnection).

        Args:
            timeout: Unused (IDLE not supported)

        Raises:
            NotImplementedError: IDLE not supported by mock
        """
        raise NotImplementedError("IDLE not supported by MockIMAPConnection.")

    async def idle_done(self) -> None:
        """Exit IDLE mode (NOT SUPPORTED by MockIMAPConnection).

        Raises:
            NotImplementedError: IDLE not supported by mock
        """
        raise NotImplementedError("IDLE not supported by MockIMAPConnection.")


class MockSMTPConnection(SMTPConnection):
    """Full mock SMTP connection for E2E tests.

    Implements SMTPConnection abstract method with in-memory storage.
    Provides realistic send behavior without real SMTP server.

    Features:
    - Stores sent messages for verification
    - Generates RFC 5322 Message-IDs
    - Simulates recipient acceptance/rejection
    - Fetches attachment content during send
    """

    def __init__(self):
        """Initialize mock SMTP with empty sent messages list."""
        self._sent_messages: list[dict[str, Any]] = []
        self._message_counter = 1
        self._username = "mock@example.com"

    @property
    def username(self) -> str:
        """Get SMTP authentication username."""
        return self._username

    async def send_message(
        self,
        from_: EmailAddress,
        to: list[EmailAddress],
        subject: str,
        body_text: str | None = None,
        body_html: str | None = None,
        cc: list[EmailAddress] | None = None,
        bcc: list[EmailAddress] | None = None,
        attachments: list[Attachment] | None = None,
        in_reply_to: str | None = None,
        references: list[str] | None = None,
    ) -> SendResult:
        """Send email message."""
        # Generate message ID
        message_id = f"<sent-{self._message_counter}@mock.localhost>"
        self._message_counter += 1

        # Fetch attachment content if present (validates lazy loading)
        attachment_data = []
        if attachments:
            for att in attachments:
                content = await att.read()  # Triggers lazy fetch
                attachment_data.append(
                    {"filename": att.filename, "content_type": att.content_type, "size": att.size, "content": content}
                )

        # Store sent message
        sent = {
            "message_id": message_id,
            "from": from_,
            "to": to,
            "cc": cc or [],
            "bcc": bcc or [],
            "subject": subject,
            "body_text": body_text,
            "body_html": body_html,
            "attachments": attachment_data,
            "in_reply_to": in_reply_to,
            "references": references or [],
        }

        self._sent_messages.append(sent)

        # All recipients accepted (mock success)
        accepted = [addr.email for addr in to]

        return SendResult(message_id=message_id, accepted=accepted, rejected={})
