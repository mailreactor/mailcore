"""Folder class providing fluent query API for email messages.

Folders are mutable objects with fluent methods for building queries:
    inbox.unseen().from_sender("alice@example.com").list(limit=10)
"""

from typing import Any

# TODO: Story 3.3 will implement Folder with fluent query API


class Folder:
    """Represents a mailbox folder with fluent query interface."""

    def __init__(self, name: str, imap_connection: Any) -> None:
        """Initialize folder with name and IMAP connection.

        Args:
            name: Folder name (e.g., "INBOX", "Sent")
            imap_connection: IMAPConnection adapter instance
        """
        self.name = name
        self._imap = imap_connection
