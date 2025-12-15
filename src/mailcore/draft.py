"""Draft class for composing outgoing emails with fluent builder interface."""

from pathlib import Path

from mailcore.attachment import Attachment
from mailcore.message import Message
from mailcore.protocols import SMTPConnection
from mailcore.types import EmailAddress


class Draft:
    """Outgoing message builder with fluent interface.

    Returned by `mailbox.compose()`, `message.reply()`, `message.forward()`.
    All builder methods return self for chaining.

    Builder behavior:
    - Singular values (to, cc, bcc, subject, body, body_html): overwrite on multiple calls
    - Attachments: append on multiple `.attach()` calls

    Args:
        smtp: SMTP connection for sending (required)
        reference_message: Original message (for reply/forward)
        in_reply_to: Message-ID this replies to (for threading)
        references: Thread chain (list of Message-IDs)
        quote: Include original message quote (for reply - fetched during send())
        include_attachments: Include original attachments (for forward - fetched during send())

    Note:
        Not typically instantiated directly - use mailbox.compose(),
        message.reply(), or message.forward()

    Example:
        >>> # Created by mailbox.compose()
        >>> draft = Draft(smtp=smtp_connection)
        >>> draft.to('alice@example.com').subject('Hi').body('Hello').send()

        >>> # Created by message.reply()
        >>> reply = message.reply(quote=True)
        >>> reply.body('Thanks!').send()
    """

    def __init__(
        self,
        smtp: SMTPConnection,
        *,
        reference_message: Message | None = None,
        in_reply_to: str | None = None,
        references: list[str] | None = None,
        quote: bool = False,
        include_attachments: bool = False,
    ) -> None:
        """Initialize draft with SMTP connection.

        Args:
            smtp: SMTP connection for sending
            reference_message: Original message (for reply/forward)
            in_reply_to: Message-ID this replies to (for threading)
            references: Thread chain (list of Message-IDs)
            quote: Include original message quote (for reply - used during send())
            include_attachments: Include original attachments (for forward - used during send())

        Note:
            Not typically instantiated directly - use mailbox.compose(),
            message.reply(), or message.forward()
        """
        # Connection
        self._smtp = smtp

        # Reference message for reply/forward
        self._reference_message = reference_message
        self._in_reply_to = in_reply_to
        self._references = references if references is not None else []
        self._quote = quote
        self._include_attachments = include_attachments

        # Builder state - mutable fields
        self._to: list[str] | None = None
        self._cc: list[str] | None = None
        self._bcc: list[str] | None = None
        self._subject: str | None = None
        self._body: str | None = None
        self._body_html: str | None = None
        self._attachments: list[Attachment] = []

    def to(self, email: str | list[str]) -> "Draft":
        """Set recipient(s). Overwrites previous value.

        Args:
            email: Single email or list of emails

        Returns:
            Self for chaining

        Examples:
            >>> draft.to('alice@example.com')
            >>> draft.to(['alice@example.com', 'bob@example.com'])
        """
        if isinstance(email, str):
            self._to = [email]
        else:
            self._to = email
        return self

    def cc(self, email: str | list[str]) -> "Draft":
        """Set CC recipient(s). Overwrites previous value.

        Args:
            email: Single email or list of emails

        Returns:
            Self for chaining

        Examples:
            >>> draft.cc('charlie@example.com')
            >>> draft.cc(['charlie@example.com', 'dave@example.com'])
        """
        if isinstance(email, str):
            self._cc = [email]
        else:
            self._cc = email
        return self

    def bcc(self, email: str | list[str]) -> "Draft":
        """Set BCC recipient(s). Overwrites previous value.

        Args:
            email: Single email or list of emails

        Returns:
            Self for chaining

        Examples:
            >>> draft.bcc('archive@example.com')
        """
        if isinstance(email, str):
            self._bcc = [email]
        else:
            self._bcc = email
        return self

    def subject(self, text: str) -> "Draft":
        """Set email subject. Overwrites previous value.

        Args:
            text: Subject line

        Returns:
            Self for chaining

        Examples:
            >>> draft.subject('Monthly Report')
        """
        self._subject = text
        return self

    def body(self, text: str) -> "Draft":
        """Set plain text body. Overwrites previous value.

        Args:
            text: Plain text body content

        Returns:
            Self for chaining

        Examples:
            >>> draft.body('Please review the attached report.')
        """
        self._body = text
        return self

    def body_html(self, html: str) -> "Draft":
        """Set HTML body. Overwrites previous value.

        Args:
            html: HTML body content

        Returns:
            Self for chaining

        Note:
            Can be used with or without plain text body.
            Best practice: provide both body() and body_html() for clients
            that don't support HTML.

        Examples:
            >>> draft.body_html('<p>Please review the attached report.</p>')
        """
        self._body_html = html
        return self

    def attach(
        self,
        source: str | Path | Attachment,
        filename: str | None = None,
        content_type: str | None = None,
    ) -> "Draft":
        """Attach content from various sources. Appends to attachments list.

        Can be called multiple times to add multiple attachments.

        Args:
            source:
                - Local path: '/path/to/file.pdf' or Path object
                - HTTP URL: 'https://example.com/file.pdf'
                - Data URI: 'data:image/png;base64,...'
                - Existing Attachment: message.attachments[0]
            filename: Override filename (optional)
            content_type: Override content type (optional)

        Returns:
            Self for chaining

        Examples:
            >>> # Local file
            >>> draft.attach('/home/user/report.pdf')

            >>> # HTTP URL
            >>> draft.attach('https://cdn.example.com/chart.png')

            >>> # Forward existing attachment
            >>> draft.attach(original_message.attachments[0])

            >>> # Path object
            >>> draft.attach(Path('/tmp/file.txt'))

            >>> # Override filename
            >>> draft.attach('/tmp/data.bin', filename='report.pdf', content_type='application/pdf')
        """
        # If already an Attachment, use directly
        if isinstance(source, Attachment):
            att = source
            # Override properties if provided
            if filename is not None:
                # Create new Attachment with updated filename
                att = Attachment(
                    uri=att.uri,
                    filename=filename,
                    content_type=content_type or att.content_type,
                    size=att.size,
                    _resolver=att._resolver,
                )
            self._attachments.append(att)
            return self

        # Convert str to proper type based on pattern
        source_str = str(source)

        # Check if URL (http:// or https://)
        if source_str.startswith("http://") or source_str.startswith("https://"):
            att = Attachment.from_url(source_str, filename=filename)
            if content_type is not None:
                att = Attachment(
                    uri=att.uri,
                    filename=att.filename,
                    content_type=content_type,
                    size=att.size,
                    _resolver=att._resolver,
                )
            self._attachments.append(att)
            return self

        # Treat as file path
        att = Attachment.from_file(source_str)
        if filename is not None or content_type is not None:
            att = Attachment(
                uri=att.uri,
                filename=filename or att.filename,
                content_type=content_type or att.content_type,
                size=att.size,
                _resolver=att._resolver,
            )
        self._attachments.append(att)
        return self

    async def send(self, **kwargs: str | list[str]) -> str:
        """Send the draft, optionally overriding properties at send time.

        Kwargs are applied by calling the corresponding Draft builder methods
        before sending. This allows last-minute modifications without breaking
        the fluent chain.

        Args:
            **kwargs: Draft builder method names with values (applied before sending)

        Supported kwargs (match Draft builder methods):
            to, cc, bcc (str or list[str]) - overwrites
            subject (str) - overwrites
            body (str) - plain text, overwrites
            body_html (str) - HTML version, overwrites

        Returns:
            Message-ID of sent message

        Raises:
            ValueError: If required fields missing (to, subject, body/body_html)

        Examples:
            >>> # Basic send
            >>> message_id = await draft.send()

            >>> # Override properties at send time
            >>> message_id = await draft.send(cc='manager@example.com')

            >>> # Add multiple overrides
            >>> message_id = await draft.send(
            ...     cc='team@example.com',
            ...     bcc='archive@example.com'
            ... )

            >>> # Works on any draft source
            >>> await message.reply().send(body='Thanks!', cc='team@example.com')
            >>> await message.forward().send(to='colleague@example.com', body='FYI')
            >>> await mailbox.compose().send(to='alice@example.com', subject='Hi', body='Hello')
        """
        # Apply kwargs via builder methods
        for key, value in kwargs.items():
            if key == "to" and isinstance(value, (str, list)):
                self.to(value)
            elif key == "cc" and isinstance(value, (str, list)):
                self.cc(value)
            elif key == "bcc" and isinstance(value, (str, list)):
                self.bcc(value)
            elif key == "subject" and isinstance(value, str):
                self.subject(value)
            elif key == "body" and isinstance(value, str):
                self.body(value)
            elif key == "body_html" and isinstance(value, str):
                self.body_html(value)

        # Validate required fields
        if self._to is None:
            raise ValueError("Draft.send() requires 'to' recipient(s)")
        if self._subject is None:
            raise ValueError("Draft.send() requires 'subject'")
        if self._body is None and self._body_html is None:
            raise ValueError("Draft.send() requires at least one of 'body' or 'body_html'")

        # Handle quote logic (lazy fetch during send)
        body_text = self._body
        if self._quote and self._reference_message is not None:
            # Fetch body from reference message
            original_text = await self._reference_message.body.get_text()
            if original_text is not None:
                # Prepend quoted text
                from_addr = self._reference_message.from_.to_rfc5322()
                date_str = self._reference_message.date.strftime("%Y-%m-%d %H:%M")
                quote_text = f"On {date_str}, {from_addr} wrote:\n"
                # Quote each line
                quoted_lines = [f"> {line}" for line in original_text.splitlines()]
                quote_text += "\n".join(quoted_lines)
                # Combine with current body
                if body_text:
                    body_text = f"{body_text}\n\n{quote_text}"
                else:
                    body_text = quote_text

        # Handle include_attachments logic (lazy fetch during send)
        attachments_to_send = self._attachments.copy()
        if self._include_attachments and self._reference_message is not None:
            # Fetch content for each attachment in reference message
            for att in self._reference_message.attachments:
                # Read content (will cache if already fetched)
                await att.read()
                # Append to attachments list
                attachments_to_send.append(att)

        # Parse email strings to EmailAddress objects
        def parse_email(email_str: str) -> EmailAddress:
            # Simple parsing: "Name <email@example.com>" or "email@example.com"
            if "<" in email_str and ">" in email_str:
                # Has name part
                parts = email_str.split("<", 1)
                name = parts[0].strip()
                email = parts[1].rstrip(">").strip()
                return EmailAddress(email, name)
            else:
                # Just email
                return EmailAddress(email_str.strip())

        # Convert email strings to EmailAddress objects
        to_addrs = [parse_email(email) for email in self._to]
        cc_addrs = [parse_email(email) for email in self._cc] if self._cc else None
        bcc_addrs = [parse_email(email) for email in self._bcc] if self._bcc else None

        # TODO: Get from_ address - for now use first to address as placeholder
        # In real implementation, this should come from account config
        from_addr_obj = to_addrs[0]  # Placeholder EmailAddress object

        # Call SMTP connection
        result = await self._smtp.send_message(
            from_=from_addr_obj,
            to=to_addrs,
            subject=self._subject,
            body_text=body_text,
            body_html=self._body_html,
            cc=cc_addrs,
            bcc=bcc_addrs,
            attachments=attachments_to_send if attachments_to_send else None,
            in_reply_to=self._in_reply_to,
            references=self._references if self._references else None,
        )

        return result.message_id
