"""Draft class for composing outgoing emails with fluent builder interface."""

from pathlib import Path

from mailcore.attachment import Attachment
from mailcore.email_address import EmailAddress
from mailcore.message import Message
from mailcore.protocols import IMAPConnection, SMTPConnection
from mailcore.types import DSNReturn, MessageFlag, Priority, SendResult


class Draft:
    """Outgoing message builder with fluent interface.

    Returned by `mailbox.draft()`, `message.reply()`, `message.forward()`.
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
        Not typically instantiated directly - use mailbox.draft(),
        message.reply(), or message.forward()

    Example:
        >>> # Created by mailbox.draft()
        >>> draft = Draft(smtp=smtp_connection, default_from='me@example.com')
        >>> draft.to('alice@example.com').subject('Hi').body('Hello')
        >>> draft  # REPL-friendly repr
        Draft(to=['alice@example.com'], subject='Hi', body=True, attachments=0)
        >>> await draft.send()

        >>> # Created by message.reply()
        >>> reply = message.reply(quote=True)
        >>> reply.body('Thanks!').send()
    """

    def __init__(
        self,
        smtp: SMTPConnection,
        default_from: str,
        *,
        imap: IMAPConnection | None = None,
        reference_message: Message | None = None,
        in_reply_to: str | None = None,
        references: list[str] | None = None,
        quote: bool = False,
        include_attachments: bool = False,
        include_body: bool = False,
    ) -> None:
        """Initialize draft with SMTP connection.

        Args:
            smtp: SMTP connection for sending
            default_from: Default FROM header email address (REQUIRED)
            imap: IMAP connection for saving drafts (optional - required for save())
            reference_message: Original message (for reply/forward)
            in_reply_to: Message-ID this replies to (for threading)
            references: Thread chain (list of Message-IDs)
            quote: Include original message quote (for reply - used during send())
            include_attachments: Include original attachments (for forward - used during send())
            include_body: Include original message body (for forward - used during send())

        Note:
            Not typically instantiated directly - use mailbox.draft(),
            message.reply(), or message.forward()
        """
        # Connection
        self._smtp = smtp
        self._imap = imap
        self._default_from = default_from

        # Reference message for reply/forward
        self._reference_message = reference_message
        self._in_reply_to = in_reply_to
        self._references = references if references is not None else []
        self._quote = quote
        self._include_attachments = include_attachments
        self._include_body = include_body

        # Builder state - mutable fields
        self._from: str | None = None
        self._to: list[str] | None = None
        self._cc: list[str] | None = None
        self._bcc: list[str] | None = None
        self._subject: str | None = None
        self._body: str | None = None
        self._body_html: str | None = None
        self._attachments: list[Attachment] = []

        # Header fields (Story 3.34 - Standard Email Headers)
        self._reply_to: list[str] | None = None  # RFC 5322 allows multiple
        self._request_read_receipt: bool = False  # Flag: read receipt requested?
        self._read_receipt_to: str | None = None  # MDN email (None = resolve to From at send time)
        self._request_delivery_receipt: bool = False  # DSN - notify flag
        self._delivery_receipt_return: str | None = None  # DSN return content (DSNReturn.value)
        self._delivery_receipt_envelope_id: str | None = None  # DSN envelope ID (ENVID)
        self._priority: str | None = None  # Priority.value ('highest', 'high', 'normal', 'low', 'lowest')
        self._sender: str | None = None  # RFC 5322 Sender header (transmitter, not author)

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

    def from_(self, email: str) -> "Draft":
        """Set sender email (override default).

        Args:
            email: Sender email address

        Returns:
            Self for chaining

        Example:
            >>> draft.from_('alias@example.com').to('bob@example.com').send()
        """
        self._from = email
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

    def reply_to(self, email: str | list[str]) -> "Draft":
        """Set Reply-To header. Overwrites previous value.

        RFC 5322 allows multiple Reply-To addresses. When recipient replies,
        their client will send to these addresses instead of From.

        Args:
            email: Single email or list of emails (validated at send time)

        Returns:
            Self for chaining

        Examples:
            >>> draft.reply_to('support@example.com')
            >>> draft.reply_to(['team@example.com', 'manager@example.com'])
        """
        if isinstance(email, str):
            self._reply_to = [email]
        else:
            self._reply_to = email
        return self

    def request_read_receipt(self, email: str | None = None) -> "Draft":
        """Request read receipt (MDN - Message Disposition Notification).

        Sets Disposition-Notification-To header per RFC 3798.
        Recipient's email client will prompt to send read receipt when message is opened.

        Args:
            email: Email for receipt (None = use From address, resolved at send time)

        Returns:
            Self for chaining

        Note:
            Email defaults to From address at send() time, so builder order doesn't matter:
            - draft.request_read_receipt().from_('alice@') works
            - draft.from_('alice@').request_read_receipt() works

        Examples:
            >>> draft.request_read_receipt()  # Uses From address
            >>> draft.request_read_receipt('receipts@example.com')  # Explicit email
        """
        self._request_read_receipt = True
        self._read_receipt_to = email  # None = resolve to From at send()
        return self

    def request_delivery_receipt(
        self,
        return_content: DSNReturn | str = DSNReturn.HEADERS,
        envelope_id: str | None = None,
    ) -> "Draft":
        """Request delivery receipt (DSN - Delivery Status Notification).

        Sets SMTP NOTIFY, RET, and ENVID parameters per RFC 3461. SMTP server will send
        delivery status notifications (success/failure/delay) to envelope sender (From).

        Args:
            return_content: What to return in bounce - DSNReturn.FULL or DSNReturn.HEADERS (default).
                           Can also pass string "full" or "headers" with validation.
            envelope_id: Optional tracking identifier returned in bounces (for correlation
                        with your tracking system, e.g., order IDs, ticket numbers)

        Returns:
            Self for chaining

        Note:
            Unlike read receipts, delivery receipts are sent by SMTP servers,
            not by recipient's email client. Notification goes to From address automatically.

        Example:
            >>> draft.request_delivery_receipt()  # Headers only
            >>> draft.request_delivery_receipt(DSNReturn.FULL)  # Full message
            >>> draft.request_delivery_receipt(envelope_id="order-123")  # With tracking
        """
        self._request_delivery_receipt = True

        # Validate return_content (fail-fast like priority())
        if isinstance(return_content, DSNReturn):
            self._delivery_receipt_return = return_content.value
        else:
            try:
                DSNReturn(return_content)
                self._delivery_receipt_return = return_content
            except ValueError:
                valid = [r.value for r in DSNReturn]
                raise ValueError(
                    f"Invalid DSN return content: {return_content!r}. Must be one of: {', '.join(valid)}"
                ) from None

        self._delivery_receipt_envelope_id = envelope_id
        return self

    def priority(self, level: Priority | str) -> "Draft":
        """Set email priority level. Overwrites previous value.

        Sets priority headers (X-Priority, Importance, Priority) for maximum client compatibility.
        Most email clients display priority indicator in inbox.

        Args:
            level: Priority level (Priority enum or string value)

        Returns:
            Self for chaining

        Raises:
            ValueError: If string value is not a valid Priority level

        Examples:
            >>> from mailcore import Priority
            >>> draft.priority(Priority.HIGH)
            >>> draft.priority('high')  # String validated immediately
            >>> draft.priority('urgent')  # ValueError: invalid priority
        """
        if isinstance(level, Priority):
            self._priority = level.value
        else:
            # Validate string is valid Priority value (fail fast)
            try:
                Priority(level)  # Raises ValueError if invalid
                self._priority = level
            except ValueError:
                valid = [p.value for p in Priority]
                raise ValueError(f"Invalid priority: {level!r}. Must be one of: {', '.join(valid)}") from None
        return self

    def sender(self, email: str) -> "Draft":
        """Set Sender header (RFC 5322 Section 3.6.2).

        Sender header indicates the agent who transmitted the message (different from author).
        Rare use case: secretary sending on behalf of manager.

        Args:
            email: Sender email (can be "Name <email@example.com>" format, validated at send time)

        Returns:
            Self for chaining

        Note:
            From header = author (who wrote it)
            Sender header = transmitter (who sent it)
            Most emails don't need Sender header.

        Example:
            >>> draft.from_('manager@company.com').sender('secretary@company.com')
        """
        self._sender = email
        return self

    async def _build_final_body(self) -> str:
        """Build final body text including quotes/forwards if configured.

        Materializes quote (reply) and forward body transformations based on
        _quote, _include_body, and _reference_message settings.

        Returns:
            Final body text with user content plus materialized quotes/forwards

        Note:
            - If no quote/forward flags set, returns _body unchanged
            - Gracefully handles missing reference message (returns _body only)
            - Called by both save() and send() to ensure consistency
        """
        # Start with user's body (or empty string if None)
        body_text = self._body if self._body is not None else ""

        # Handle quote logic (reply)
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

        # Handle forward body logic
        if self._include_body and self._reference_message is not None:
            # Fetch body from reference message
            original_text = await self._reference_message.body.get_text()
            if original_text is not None:
                # Format forward header
                from_addr = self._reference_message.from_.to_rfc5322()
                date_str = self._reference_message.date.strftime("%Y-%m-%d %H:%M")
                to_recipients = ", ".join([addr.to_rfc5322() for addr in self._reference_message.to])

                forward_header = (
                    "\n\n---------- Forwarded message ---------\n"
                    f"From: {from_addr}\n"
                    f"Date: {date_str}\n"
                    f"Subject: {self._reference_message.subject}\n"
                    f"To: {to_recipients}\n\n"
                )

                # Combine with user body (if any)
                if body_text:
                    body_text = f"{body_text}{forward_header}{original_text}"
                else:
                    # No user body - just forward content (strip leading newlines)
                    body_text = f"{forward_header.lstrip()}{original_text}"

        return body_text

    async def save(self, folder: str, flags: set["MessageFlag"] | None = None) -> int:
        """Save draft to IMAP folder without sending.

        Creates a new message in the specified folder. Messages in IMAP are immutable;
        this does not edit an existing message.

        Args:
            folder: Target folder name (required). Must be a valid IMAP folder.
            flags: Message flags to set. If None, no flags are set.

        Returns:
            UID of newly saved message (positive integer), or 0 if server
            doesn't support APPENDUID capability.

        Raises:
            ValueError: If folder is None or empty string
            FolderNotFoundError: If folder doesn't exist

        Examples:
            >>> draft = mailbox.draft().to('alice').subject('Hi').body('Hello')
            >>> uid = await draft.save(folder='Drafts')

            >>> # Can save same draft to multiple folders
            >>> uid2 = await draft.save(folder='Sent')
        """
        # Validate IMAP connection
        if self._imap is None:
            raise ValueError(
                "Draft.save() requires IMAP connection. Create draft via mailbox.draft() to enable saving."
            )

        # Validate folder parameter
        if not folder:
            raise ValueError(
                "folder parameter is required. "
                "Messages in IMAP are immutable; this creates a new message in the specified folder."
            )

        # Determine flags to set
        flags_to_set = flags.copy() if flags is not None else set()

        # Parse email strings to EmailAddress objects (reuse from send())
        def parse_email(email_str: str) -> EmailAddress:
            if "<" in email_str and ">" in email_str:
                parts = email_str.split("<", 1)
                name = parts[0].strip()
                email = parts[1].rstrip(">").strip()
                return EmailAddress(email, name)
            else:
                return EmailAddress(email_str.strip())

        # Convert email strings to EmailAddress objects (handle None for incomplete drafts)
        to_addrs = [parse_email(email) for email in self._to] if self._to else []
        cc_addrs = [parse_email(email) for email in self._cc] if self._cc else None
        bcc_addrs = [parse_email(email) for email in self._bcc] if self._bcc else None

        # From address
        from_email = self._from if self._from is not None else self._default_from
        from_addr_obj = parse_email(from_email)

        # Subject (can be empty for incomplete drafts)
        subject = self._subject if self._subject is not None else ""

        # Build final body with quotes/forwards materialized
        final_body = await self._build_final_body()

        # Append new message with specified flags
        new_uid = await self._imap.append_message(
            folder=folder,
            from_=from_addr_obj,
            to=to_addrs,
            subject=subject,
            body_text=final_body,
            body_html=self._body_html,
            cc=cc_addrs,
            bcc=bcc_addrs,
            attachments=self._attachments if self._attachments else None,
            in_reply_to=self._in_reply_to,
            references=self._references if self._references else None,
            flags=flags_to_set,
            custom_flags=None,
        )

        return new_uid

    async def send(self, **kwargs: str | list[str]) -> "SendResult":
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
            SendResult with message_id, accepted recipients, and rejected recipients

        Raises:
            ValueError: If required fields missing (to, subject, body/body_html)

        Examples:
            >>> # Basic send
            >>> result = await draft.send()
            >>> result.message_id
            '<abc123@example.com>'
            >>> result.accepted
            ['alice@example.com']
            >>> result.rejected
            {}

            >>> # Override properties at send time
            >>> result = await draft.send(cc='manager@example.com')

            >>> # Add multiple overrides
            >>> result = await draft.send(
            ...     cc='team@example.com',
            ...     bcc='archive@example.com'
            ... )

            >>> # Works on any draft source
            >>> await message.reply().send(body='Thanks!', cc='team@example.com')
            >>> await message.forward().send(to='colleague@example.com', body='FYI')
            >>> await mailbox.draft().send(to='alice@example.com', subject='Hi', body='Hello')
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

        # Build final body with quotes/forwards materialized
        body_text = await self._build_final_body()

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

        # From address: explicit override > default_from (REQUIRED parameter)
        from_email = self._from if self._from is not None else self._default_from
        from_addr_obj = parse_email(from_email)

        # Process new headers (Story 3.34)

        # Reply-To: parse list of emails to EmailAddress objects
        reply_to_addrs: list[EmailAddress] | None = None
        if self._reply_to:
            reply_to_addrs = [parse_email(email) for email in self._reply_to]

        # Sender: parse to EmailAddress
        sender_addr: EmailAddress | None = None
        if self._sender:
            sender_addr = parse_email(self._sender)

        # Read receipt (MDN): resolve to From if not explicit
        disposition_notification_to: str | None = None
        if self._request_read_receipt:
            receipt_email = self._read_receipt_to if self._read_receipt_to else from_email
            # Extract just the email address (no name)
            receipt_addr = parse_email(receipt_email)
            disposition_notification_to = receipt_addr.email

        # Delivery receipt (DSN): build notify, return_content, envelope_id parameters
        notify: str | None = None
        dsn_return: str | None = None
        dsn_envelope_id: str | None = None
        if self._request_delivery_receipt:
            notify = "SUCCESS,FAILURE,DELAY"
            dsn_return = self._delivery_receipt_return  # "full" or "headers"
            dsn_envelope_id = self._delivery_receipt_envelope_id  # User's tracking ID

        # Priority: already validated, just pass value
        priority: str | None = self._priority

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
            reply_to=reply_to_addrs,
            sender=sender_addr,
            priority=priority,
            disposition_notification_to=disposition_notification_to,
            notify=notify,
            dsn_return=dsn_return,
            dsn_envelope_id=dsn_envelope_id,
        )

        return result  # Return full SendResult with message_id, accepted, rejected

    def __repr__(self) -> str:
        """Developer-friendly representation showing composition state.

        Returns:
            Draft(to=[...], subject='...', body=True/False, attachments=N)

        Example:
            >>> draft = Draft(smtp=smtp_conn, default_from='me@example.com')
            >>> draft.to('alice@example.com').subject('Hello')
            >>> draft
            Draft(to=['alice@example.com'], subject='Hello', body=False, attachments=0)
        """
        to_list = self._to if self._to else []
        subject = self._subject
        if subject and len(subject) > 50:
            subject = subject[:47] + "..."
        has_body = bool(self._body or self._body_html)

        return f"Draft(to={to_list}, subject={subject!r}, body={has_body}, attachments={len(self._attachments)})"
