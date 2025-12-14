"""Draft class for composing and sending email messages with fluent builder API."""

from typing import Any

# TODO: Story 3.6 will implement Draft with fluent builder pattern


class Draft:
    """Fluent builder for composing email messages."""

    def __init__(self, smtp_connection: Any) -> None:
        """Initialize draft with SMTP connection.

        Args:
            smtp_connection: SMTPConnection adapter instance
        """
        self._smtp = smtp_connection
        self._to: list[str] = []
        self._subject: str = ""
        self._body_text: str | None = None
        self._body_html: str | None = None
