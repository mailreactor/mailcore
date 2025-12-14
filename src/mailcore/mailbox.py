"""Mailbox class - main entry point for email operations."""

from typing import Any

# TODO: Story 3.7 will implement Mailbox with folder access and compose


class Mailbox:
    """Main entry point for email operations with folder access and message composition.

    Example:
        mailbox = Mailbox(imap_connection=adapter, smtp_connection=adapter)
        await mailbox.inbox.unseen().list(limit=10)
        await mailbox.compose(to="user@example.com", subject="Hello").send()
    """

    def __init__(self, imap_connection: Any, smtp_connection: Any) -> None:
        """Initialize mailbox with IMAP and SMTP connections.

        Args:
            imap_connection: IMAPConnection adapter instance
            smtp_connection: SMTPConnection adapter instance
        """
        self._imap = imap_connection
        self._smtp = smtp_connection
