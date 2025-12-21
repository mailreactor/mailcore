"""Tests for ABC runtime verification in protocols.py."""

from typing import Any

import pytest

from mailcore.attachment import Attachment
from mailcore.email_address import EmailAddress
from mailcore.protocols import IMAPConnection, SMTPConnection
from mailcore.query import Query
from mailcore.types import FolderInfo, FolderStatus, MessageFlag, SendResult


def test_cannot_instantiate_imap_connection_directly() -> None:
    """Verify IMAPConnection ABC cannot be instantiated without implementing all methods."""
    with pytest.raises(TypeError) as exc_info:
        IMAPConnection()  # type: ignore[abstract]

    assert "Can't instantiate abstract class" in str(exc_info.value)


def test_cannot_instantiate_smtp_connection_directly() -> None:
    """Verify SMTPConnection ABC cannot be instantiated without implementing all methods."""
    with pytest.raises(TypeError) as exc_info:
        SMTPConnection()  # type: ignore[abstract]

    assert "Can't instantiate abstract class" in str(exc_info.value)


def test_incomplete_imap_implementation_raises_typeerror() -> None:
    """Verify incomplete IMAPConnection implementation raises TypeError at instantiation."""

    class IncompleteIMAPAdapter(IMAPConnection):
        """Incomplete adapter missing all abstract methods."""

        pass

    with pytest.raises(TypeError) as exc_info:
        IncompleteIMAPAdapter()  # type: ignore[abstract]

    assert "abstract methods" in str(exc_info.value)


@pytest.mark.asyncio
async def test_complete_imap_implementation_succeeds() -> None:
    """Verify complete IMAPConnection implementation can be instantiated."""
    from mailcore.message_list import MessageList

    class CompleteIMAPAdapter(IMAPConnection):
        """Complete adapter implementing all 12 abstract methods."""

        async def query_messages(
            self,
            folder: str,
            query: Query,
            include_body: bool = False,
            include_attachment_metadata: bool = True,
            limit: int | None = None,
            offset: int = 0,
        ) -> MessageList:
            return MessageList(messages=[], total_matches=0, total_in_folder=0, folder=folder)

        async def fetch_message_body(self, folder: str, uid: int) -> tuple[str | None, str | None]:
            return None, None

        async def fetch_attachment_content(self, folder: str, uid: int, part_index: str) -> bytes:
            return b""

        async def update_message_flags(
            self,
            folder: str,
            uid: int,
            add_flags: set[MessageFlag] | None = None,
            remove_flags: set[MessageFlag] | None = None,
            add_custom: set[str] | None = None,
            remove_custom: set[str] | None = None,
        ) -> tuple[set[MessageFlag], set[str]]:
            return set(), set()

        async def move_message(self, uid: int, from_folder: str, to_folder: str) -> int:
            return uid

        async def copy_message(self, uid: int, from_folder: str, to_folder: str) -> int:
            return 0

        async def delete_message(self, folder: str, uid: int, permanent: bool = False) -> None:
            pass

        async def get_folders(self) -> list[FolderInfo]:
            return []

        async def get_folder_status(self, folder: str) -> FolderStatus:
            return FolderStatus(message_count=0, unseen_count=0, uidnext=1)

        async def create_folder(self, name: str) -> FolderInfo:
            return FolderInfo(name=name, flags=[], has_children=False)

        async def delete_folder(self, name: str) -> None:
            pass

        async def rename_folder(self, old_name: str, new_name: str) -> FolderInfo:
            return FolderInfo(name=new_name, flags=[], has_children=False)

        async def append_message(
            self,
            folder: str,
            from_: EmailAddress,
            to: list[EmailAddress],
            subject: str,
            body_text: str | None = None,
            body_html: str | None = None,
            cc: list[EmailAddress] | None = None,
            attachments: list[Attachment] | None = None,
            in_reply_to: str | None = None,
            references: list[str] | None = None,
            flags: set[MessageFlag] | None = None,
            custom_flags: set[str] | None = None,
        ) -> int:
            return 1

        async def select_folder(self, folder: str) -> dict[str, Any]:
            return {"exists": 0, "recent": 0, "uidvalidity": 1}

        async def idle_start(self) -> None:
            pass

        async def idle_wait(self, timeout: int = 1800) -> list[str]:
            return []

        async def idle_done(self) -> None:
            pass

    # Should instantiate without errors
    imap = CompleteIMAPAdapter()
    assert isinstance(imap, IMAPConnection)

    # Verify methods work
    result = await imap.query_messages("INBOX", Query("ALL"))
    assert len(result) == 0
    assert result.folder == "INBOX"


@pytest.mark.asyncio
async def test_complete_smtp_implementation_succeeds() -> None:
    """Verify complete SMTPConnection implementation can be instantiated."""

    class CompleteSMTPAdapter(SMTPConnection):
        """Complete adapter implementing send_message."""

        @property
        def username(self) -> str:
            """Get SMTP authentication username."""
            return "test@example.com"

        async def send_message(
            self,
            from_: EmailAddress,
            to: list[EmailAddress],
            subject: str,
            body_text: str | None = None,
            body_html: str | None = None,
            cc: list[EmailAddress] | None = None,
            bcc: list[EmailAddress] | None = None,
            attachments: list | None = None,
            in_reply_to: str | None = None,
            references: list[str] | None = None,
        ) -> SendResult:
            return SendResult(
                message_id="<test@example.com>",
                accepted=[addr.email for addr in to],
                rejected={},
            )

    # Should instantiate without errors
    smtp = CompleteSMTPAdapter()
    assert isinstance(smtp, SMTPConnection)

    # Verify method works
    result = await smtp.send_message(
        from_=EmailAddress("sender@example.com"),
        to=[EmailAddress("recipient@example.com")],
        subject="Test",
        body_text="Hello",
    )
    assert result.message_id == "<test@example.com>"
    assert len(result.accepted) == 1
    assert result.accepted[0] == "recipient@example.com"
