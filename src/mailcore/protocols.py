"""Abstract base classes defining connection protocol contracts for IMAP and SMTP adapters.

CRITICAL: Adapter implementations MUST base64 decode attachment content before returning.
IMAPClient returns base64-encoded bytes - use base64.b64decode() to prevent corrupt attachments.

Validated in Story 3.0: DOCX attachment 24,184 bytes base64 -> 17,671 bytes decoded.
"""

from abc import ABC, abstractmethod
from typing import Any

# TODO: Story 3.2 will implement full ABC contracts with type hints
# NOTE: _part_index MUST be str not int (IMAP uses "1", "2", "1.1" for nested parts)


class IMAPConnection(ABC):
    """Abstract base class for IMAP connection adapters.

    Implementations provide protocol-specific logic (IMAPClient, aioimaplib, etc.)
    while exposing a unified async interface.
    """

    @abstractmethod
    async def query_messages(self, folder: str, query: Any, limit: int | None = None) -> Any:
        """Query messages in a folder."""
        ...


class SMTPConnection(ABC):
    """Abstract base class for SMTP connection adapters.

    Implementations provide protocol-specific logic (aiosmtplib, etc.)
    while exposing a unified async interface.
    """

    @abstractmethod
    async def send_message(self, message: Any) -> str:
        """Send an email message and return message ID."""
        ...
