"""Folder class providing fluent query API for email messages.

Folders are mutable objects with fluent methods for building queries:
    inbox.unseen().from_("alice@example.com").list(limit=10)

Connection Injection Pattern (from Tech Spec):
- Folder receives BOTH imap and smtp at construction: Folder(imap, smtp, name)
- Messages created by IMAP adapter have only _imap reference
- Folder injects _smtp after receiving MessageList: for msg in messages: msg._smtp = self._smtp
- This enables Message.reply() and Message.forward() operations
"""

from collections.abc import AsyncIterator

from mailcore.message import Message
from mailcore.message_list import MessageList
from mailcore.protocols import IMAPConnection, SMTPConnection
from mailcore.query import Query


class Folder:
    """IMAP folder with immutable fluent query API and SMTP injection.

    Provides chainable methods for building IMAP queries and executing them.
    Each fluent method returns a NEW Folder instance, leaving the original unchanged.
    Injects SMTP connection into messages for reply/forward operations.

    Example:
        >>> inbox = Folder(imap=imap_adapter, smtp=smtp_adapter, name='INBOX', default_sender='me@example.com')
        >>> inbox  # REPL-friendly repr
        Folder('INBOX')
        >>>
        >>> # Each method returns a new instance
        >>> messages = await inbox.from_('alice@example.com').unseen().list(limit=50)
        >>>
        >>> # Original inbox is unchanged - can reuse safely
        >>> other_messages = await inbox.from_('bob@example.com').list()
        >>>
        >>> # Can save intermediate filters
        >>> alice_messages = inbox.from_('alice')
        >>> alice_messages  # Shows filter count
        Folder('INBOX', filters=1)
        >>> urgent = await alice_messages.subject('urgent').list()
        >>> reports = await alice_messages.subject('report').list()
    """

    def __init__(self, imap: IMAPConnection, smtp: SMTPConnection, name: str, default_sender: str) -> None:
        """Initialize folder with IMAP and SMTP connections.

        Args:
            imap: IMAP connection adapter
            smtp: SMTP connection adapter
            name: Folder name (e.g., "INBOX", "Sent")
            default_sender: Default sender email address for message composition
        """
        self._imap = imap
        self._smtp = smtp
        self._name = name
        self._default_sender = default_sender
        self._query_parts: list[Query] = []

    def _clone_with_query(self, query: Query) -> "Folder":
        """Create new Folder instance with added query part.

        Args:
            query: Query to add to the query parts

        Returns:
            New Folder instance with query added
        """
        new_folder = Folder(self._imap, self._smtp, self._name, self._default_sender)
        new_folder._query_parts = self._query_parts.copy()
        new_folder._query_parts.append(query)
        return new_folder

    def from_(self, address: str) -> "Folder":
        """Filter by FROM address.

        Args:
            address: Email address or partial match

        Returns:
            New Folder instance with filter added
        """
        return self._clone_with_query(Query.from_(address))

    def to(self, address: str) -> "Folder":
        """Filter by TO address.

        Args:
            address: Email address or partial match

        Returns:
            New Folder instance with filter added
        """
        return self._clone_with_query(Query.to(address))

    def subject(self, text: str) -> "Folder":
        """Filter by SUBJECT contains.

        Args:
            text: Text to search in subject

        Returns:
            New Folder instance with filter added
        """
        return self._clone_with_query(Query.subject(text))

    def body(self, text: str) -> "Folder":
        """Filter by BODY contains.

        Args:
            text: Text to search in body

        Returns:
            New Folder instance with filter added
        """
        return self._clone_with_query(Query.body(text))

    def seen(self) -> "Folder":
        """Filter to only seen messages.

        Returns:
            New Folder instance with filter added
        """
        return self._clone_with_query(Query.seen())

    def unseen(self) -> "Folder":
        """Filter to only unseen messages.

        Returns:
            New Folder instance with filter added
        """
        return self._clone_with_query(Query.unseen())

    def answered(self) -> "Folder":
        """Filter to only answered messages.

        Returns:
            New Folder instance with filter added
        """
        return self._clone_with_query(Query.answered())

    def flagged(self) -> "Folder":
        """Filter to only flagged messages.

        Returns:
            New Folder instance with filter added
        """
        return self._clone_with_query(Query.flagged())

    def deleted(self) -> "Folder":
        """Filter to only deleted messages.

        Returns:
            New Folder instance with filter added
        """
        return self._clone_with_query(Query.deleted())

    def draft(self) -> "Folder":
        """Filter to only draft messages.

        Returns:
            New Folder instance with filter added
        """
        return self._clone_with_query(Query.draft())

    def recent(self) -> "Folder":
        """Filter to only recent messages.

        Returns:
            New Folder instance with filter added
        """
        return self._clone_with_query(Query.recent())

    async def list(self, limit: int | None = None, offset: int = 0) -> MessageList:
        """Execute query and return messages.

        Combines accumulated query parts with AND logic, executes via IMAP,
        and injects SMTP connection into returned messages.

        Args:
            limit: Maximum messages to return (None = unlimited)
            offset: Skip first N messages (for pagination)

        Returns:
            MessageList with SMTP injected into each message
        """
        # Build query from accumulated parts
        if not self._query_parts:
            query = Query.all()
        else:
            query = self._query_parts[0]
            for q in self._query_parts[1:]:
                query = query & q

        # Execute query via IMAP (query is already a Query instance)
        message_list = await self._imap.query_messages(self._name, query, limit=limit, offset=offset)

        # Inject SMTP and default_sender into all messages
        for msg in message_list:
            msg._smtp = self._smtp
            msg._default_sender = self._default_sender

        return message_list

    async def __aiter__(self) -> AsyncIterator[Message]:
        """Async iteration - stream all matching messages (no limit).

        Yields messages one at a time by calling list() internally.
        Note: This loads all messages first, then yields. For true
        streaming, would need IMAP FETCH in batches.

        Yields:
            Message instances one at a time

        Example:
            async for message in folder.unseen():
                print(message.subject)
        """
        message_list = await self.list()
        for message in message_list.messages:
            yield message

    async def first(self, **kwargs: str) -> Message | None:
        """Get first matching message.

        Args:
            **kwargs: Optional fluent filters (e.g., from_='alice')

        Returns:
            First message or None if no matches
        """
        # Apply kwargs as fluent methods
        folder = self
        for key, value in kwargs.items():
            method = getattr(folder, key, None)
            if method and callable(method):
                folder = method(value)  # Get new instance with filter

        # Get first message
        messages = await folder.list(limit=1)
        return messages[0] if messages else None

    async def count(self) -> int:
        """Count matching messages without fetching.

        Returns:
            Total messages matching query
        """
        # Build query
        if not self._query_parts:
            query = Query.all()
        else:
            query = self._query_parts[0]
            for q in self._query_parts[1:]:
                query = query & q

        # Execute with limit=0 to get count only (query is already a Query instance)
        message_list = await self._imap.query_messages(self._name, query, limit=0)

        return message_list.total_matches

    def __repr__(self) -> str:
        """Developer-friendly representation showing folder and active filters.

        Returns:
            Folder('name') or Folder('name', filters=N)

        Example:
            >>> inbox = Folder(imap, smtp, "INBOX", "me@example.com")
            >>> inbox
            Folder('INBOX')

            >>> filtered = inbox.from_('alice').unseen()
            >>> filtered
            Folder('INBOX', filters=2)
        """
        if not self._query_parts:
            return f"Folder({self._name!r})"

        return f"Folder({self._name!r}, filters={len(self._query_parts)})"
