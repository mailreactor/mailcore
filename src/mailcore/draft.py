"""Draft class for composing outgoing emails with fluent builder interface."""

from pathlib import Path

from mailcore.attachment import Attachment
from mailcore.email_address import EmailAddress
from mailcore.message import Message
from mailcore.protocols import IMAPConnection, SMTPConnection
from mailcore.types import MessageFlag


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
        >>> draft = Draft(smtp=smtp_connection, default_sender='me@example.com')
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
        default_sender: str,
        *,
        imap: IMAPConnection | None = None,
        reference_message: Message | None = None,
        in_reply_to: str | None = None,
        references: list[str] | None = None,
        quote: bool = False,
        include_attachments: bool = False,
        include_body: bool = False,
        original_message_uid: int | None = None,
        original_message_folder: str | None = None,
        original_message_flags: set[MessageFlag] | None = None,
        original_custom_flags: set[str] | None = None,
    ) -> None:
        """Initialize draft with SMTP connection.

        Args:
            smtp: SMTP connection for sending
            default_sender: Default sender email address (REQUIRED)
            imap: IMAP connection for saving drafts (optional - required for save())
            reference_message: Original message (for reply/forward)
            in_reply_to: Message-ID this replies to (for threading)
            references: Thread chain (list of Message-IDs)
            quote: Include original message quote (for reply - used during send())
            include_attachments: Include original attachments (for forward - used during send())
            include_body: Include original message body (for forward - used during send())
            original_message_uid: UID of original draft (for edit tracking)
            original_message_folder: Folder of original draft (for smart replace)
            original_message_flags: Flags to preserve when saving (for edit)
            original_custom_flags: Custom flags to preserve when saving (for edit)

        Note:
            Not typically instantiated directly - use mailbox.draft(),
            message.reply(), or message.forward()
        """
        # Connection
        self._smtp = smtp
        self._imap = imap
        self._default_sender = default_sender

        # Reference message for reply/forward
        self._reference_message = reference_message
        self._in_reply_to = in_reply_to
        self._references = references if references is not None else []
        self._quote = quote
        self._include_attachments = include_attachments
        self._include_body = include_body

        # Original message tracking (for edit/save workflow)
        self._original_message_uid = original_message_uid
        self._original_message_folder = original_message_folder
        self._original_message_flags = original_message_flags or set()
        self._original_custom_flags = original_custom_flags or set()

        # Builder state - mutable fields
        self._from: str | None = None
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

    async def save(self, folder: str) -> int:
        """Save draft to IMAP folder without sending.

        If draft originated from message.edit(), replaces original
        when saving to same folder (deletes old, keeps new).
        Preserves flags from original message (except \\Recent).

        Args:
            folder: Target folder name (must exist)

        Returns:
            UID of newly saved draft message (positive integer), or 0 if server
            doesn't support APPENDUID capability. The UID represents the NEW message
            (after append), not the original (which is deleted on replace).

        Raises:
            ValueError: If IMAP connection not available or BCC is set
            FolderNotFoundError: If folder doesn't exist

        Note:
            - BCC cannot be safely preserved in IMAP (security requirement).
              Save will raise ValueError if BCC is set. Add BCC when sending instead.
            - Incomplete drafts allowed: to/subject/body can be empty
            - Modern IMAP servers (Gmail, Outlook) support APPENDUID and return UID > 0
            - Legacy servers without APPENDUID return 0 (can't determine UID)

        Examples:
            >>> # Save new draft
            >>> draft = mailbox.draft().to('alice').subject('Hi').body('Draft')
            >>> uid = await draft.save(folder='Drafts')

            >>> # Edit and save (replaces original if same folder)
            >>> drafts = await mailbox.folders['Drafts'].list()
            >>> editable = await drafts[0].edit()
            >>> editable.body('Updated content')
            >>> uid = await editable.save(folder='Drafts')  # NEW UID, original deleted
        """
        # Validate IMAP connection available
        if self._imap is None:
            raise ValueError(
                "Draft.save() requires IMAP connection. Create draft via mailbox.draft() to enable saving."
            )

        # SECURITY: BCC validation - cannot be safely preserved in IMAP
        if self._bcc:
            raise ValueError(
                "Draft.save() cannot preserve BCC recipients. "
                "BCC must not appear in saved messages (security requirement). "
                "Either send draft immediately with .send() or remove BCC before saving. "
                "Add BCC when loading draft later: draft.to_draft().bcc('email').send()"
            )

        # Determine flags to preserve
        flags_to_set = {MessageFlag.DRAFT}  # Always include \Draft

        if self._original_message_flags:
            # Preserve all flags except \Recent (server-controlled)
            flags_to_set |= {flag for flag in self._original_message_flags if flag != MessageFlag.RECENT}

        # Preserve custom flags
        custom_flags_to_set = self._original_custom_flags.copy() if self._original_custom_flags else set()

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

        # Sender address
        from_email = self._from if self._from is not None else self._default_sender
        from_addr_obj = parse_email(from_email)

        # Subject (can be empty for incomplete drafts)
        subject = self._subject if self._subject is not None else ""

        # Build final body with quotes/forwards materialized
        final_body = await self._build_final_body()

        # Append new message with preserved flags
        new_uid = await self._imap.append_message(
            folder=folder,
            from_=from_addr_obj,
            to=to_addrs,
            subject=subject,
            body_text=final_body,
            body_html=self._body_html,
            cc=cc_addrs,
            attachments=self._attachments if self._attachments else None,
            in_reply_to=self._in_reply_to,
            references=self._references if self._references else None,
            flags=flags_to_set,
            custom_flags=custom_flags_to_set if custom_flags_to_set else None,
        )

        # If editing same folder, delete original (atomic replace)
        # Only delete if we have a valid UID (> 0) - servers without APPENDUID return 0
        if (
            self._original_message_uid is not None
            and self._original_message_uid > 0
            and folder == self._original_message_folder
        ):
            try:
                await self._imap.delete_message(
                    folder=self._original_message_folder,
                    uid=self._original_message_uid,
                )
            except Exception:
                pass  # Original might already be deleted

        # Update tracking for subsequent saves
        # Note: Always update even if new_uid is 0 (no APPENDUID support)
        # because the old UID was deleted and is no longer valid
        self._original_message_uid = new_uid
        self._original_message_folder = folder
        self._original_message_flags = flags_to_set
        self._original_custom_flags = custom_flags_to_set

        return new_uid

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

        # Sender address: explicit override > default_sender (REQUIRED parameter)
        from_email = self._from if self._from is not None else self._default_sender
        from_addr_obj = parse_email(from_email)

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

    def __repr__(self) -> str:
        """Developer-friendly representation showing composition state.

        Returns:
            Draft(to=[...], subject='...', body=True/False, attachments=N)

        Example:
            >>> draft = Draft(smtp=smtp_conn, default_sender='me@example.com')
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
