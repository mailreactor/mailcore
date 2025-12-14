"""MessageBody class for lazy loading email body text and HTML."""

from typing import Any

# TODO: Story 3.4 will implement MessageBody with lazy text/html loading


class MessageBody:
    """Represents email message body with lazy text/html loading."""

    def __init__(self, message: Any) -> None:
        """Initialize body with message reference.

        Args:
            message: Message instance this body belongs to
        """
        self._message = message
        self._text: str | None = None
        self._html: str | None = None
