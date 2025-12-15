"""Mailbox class - main entry point for email operations."""

from mailcore.draft import Draft
from mailcore.protocols import IMAPConnection, SMTPConnection


class Mailbox:
    """Main entry point for email operations with folder access and message composition.

    Example:
        mailbox = Mailbox(imap=imap_connection, smtp=smtp_connection)
        await mailbox.compose().to('user@example.com').subject('Hello').send()
        await mailbox.send(to='user@example.com', subject='Hi', body='Hello')
    """

    def __init__(self, imap: IMAPConnection, smtp: SMTPConnection) -> None:
        """Initialize mailbox with IMAP and SMTP connections.

        Args:
            imap: Connected and authenticated IMAP connection
            smtp: Connected and authenticated SMTP connection

        Note:
            Connection management (connect, disconnect, pooling, reconnection)
            is the caller's responsibility.
        """
        self._imap = imap
        self._smtp = smtp

    def compose(self) -> Draft:
        """Create new draft message.

        Returns:
            Draft with SMTP connection for building and sending email

        Example:
            >>> draft = mailbox.compose()
            >>> await draft.to('alice@example.com').subject('Hi').body('Hello').send()
        """
        return Draft(smtp=self._smtp)

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
        draft = self.compose()
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
