"""Message class representing email message with metadata and lazy body loading."""

from typing import Any

# TODO: Story 3.4 will implement Message with lazy body loading


class Message:
    """Represents an email message with metadata and lazy-loaded body."""

    def __init__(self, uid: str, folder: Any) -> None:
        """Initialize message with UID and folder reference.

        Args:
            uid: Message unique identifier
            folder: Folder instance containing this message
        """
        self.uid = uid
        self._folder = folder
