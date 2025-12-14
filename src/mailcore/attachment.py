"""Attachment class for email attachments with lazy content fetching."""

from typing import Any

# TODO: Story 3.5 will implement Attachment with lazy content loading


class Attachment:
    """Represents email attachment with metadata and lazy content fetching."""

    def __init__(self, message: Any, part_index: str, filename: str, content_type: str, size: int) -> None:
        """Initialize attachment with metadata.

        Args:
            message: Message instance this attachment belongs to
            part_index: IMAP part index (str like "1", "2", "1.1" for nested parts)
            filename: Attachment filename
            content_type: MIME content type
            size: Size in bytes
        """
        self._message = message
        self.part_index = part_index
        self.filename = filename
        self.content_type = content_type
        self.size = size
