"""Folder class providing fluent query API for email messages.

Folders are mutable objects with fluent methods for building queries:
    inbox.unseen().from_("alice@example.com").list(limit=10)

Connection Injection Pattern (from Tech Spec):
- Folder receives BOTH imap and smtp at construction: Folder(imap, smtp, name)
- Messages created by IMAP adapter have only _imap reference
- Folder injects _smtp after receiving MessageList: for msg in messages: msg._smtp = self._smtp
- This enables Message.reply() and Message.forward() operations
"""

import datetime
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

    def from_(self, address: str | list[str]) -> "Folder":
        """Filter by FROM address (supports multiple with OR logic).

        Args:
            address: Email address or list of addresses (OR logic)

        Returns:
            New Folder instance with filter added

        Example:
            >>> # Single address
            >>> folder.from_('alice@example.com')
            >>>
            >>> # Multiple addresses (OR)
            >>> folder.from_(['alice@example.com', 'bob@example.com'])
        """
        if isinstance(address, str):
            return self._clone_with_query(Query.from_(address))
        else:
            # Multiple addresses - build OR chain
            queries = [Query.from_(addr) for addr in address]
            combined = queries[0]
            for q in queries[1:]:
                combined = combined | q
            return self._clone_with_query(combined)

    def to(self, address: str | list[str]) -> "Folder":
        """Filter by TO address (supports multiple with OR logic).

        Args:
            address: Email address or list of addresses (OR logic)

        Returns:
            New Folder instance with filter added

        Example:
            >>> # Single address
            >>> folder.to('alice@example.com')
            >>>
            >>> # Multiple addresses (OR)
            >>> folder.to(['alice@example.com', 'bob@example.com'])
        """
        if isinstance(address, str):
            return self._clone_with_query(Query.to(address))
        else:
            # Multiple addresses - build OR chain
            queries = [Query.to(addr) for addr in address]
            combined = queries[0]
            for q in queries[1:]:
                combined = combined | q
            return self._clone_with_query(combined)

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

    # UID range filter

    def uid_range(self, start: int, end: int | str) -> "Folder":
        """Filter by UID range.

        Args:
            start: Starting UID (inclusive)
            end: Ending UID (inclusive) or "*" for highest UID in folder

        Returns:
            New Folder instance with UID range filter applied (immutable pattern)

        Note:
            IDLE pattern: Use uid_range(last_uid + 1, "*") to fetch only new messages
            after last seen UID. This is essential for IDLE event handling where you
            want to retrieve messages added since your last check.

        Example:
            # Fetch specific UID range
            >>> messages = await folder.uid_range(100, 200).list()

            # IDLE pattern - fetch all messages after last seen UID
            >>> last_uid = 42
            >>> new_messages = await folder.uid_range(last_uid + 1, "*").list()

            # Combine with other filters
            >>> unseen_new = await folder.uid_range(100, "*").unseen().list()
        """
        return self._clone_with_query(Query.uid_range(start, end))

    # Date filters

    def since(self, date: "datetime.date") -> "Folder":
        """Filter messages on or after date (IMAP internal date).

        Args:
            date: Date to filter from (inclusive)

        Returns:
            New Folder instance with filter added

        Example:
            >>> from datetime import date
            >>> folder.since(date(2025, 12, 1))
        """
        return self._clone_with_query(Query.since(date))

    def before(self, date: "datetime.date") -> "Folder":
        """Filter messages before date (IMAP internal date).

        Args:
            date: Date to filter before (exclusive)

        Returns:
            New Folder instance with filter added

        Example:
            >>> from datetime import date
            >>> folder.before(date.today())
        """
        return self._clone_with_query(Query.before(date))

    def on(self, date: "datetime.date") -> "Folder":
        """Filter messages on specific date (IMAP internal date).

        Args:
            date: Date to filter on (exact match)

        Returns:
            New Folder instance with filter added

        Example:
            >>> from datetime import date
            >>> folder.on(date(2025, 12, 21))
        """
        return self._clone_with_query(Query.on(date))

    def sentsince(self, date: "datetime.date") -> "Folder":
        """Filter messages sent on or after date (IMAP Date header).

        Args:
            date: Date to filter from (inclusive)

        Returns:
            New Folder instance with filter added

        Example:
            >>> from datetime import date
            >>> folder.sentsince(date(2025, 12, 1))
        """
        return self._clone_with_query(Query.sentsince(date))

    def sentbefore(self, date: "datetime.date") -> "Folder":
        """Filter messages sent before date (IMAP Date header).

        Args:
            date: Date to filter before (exclusive)

        Returns:
            New Folder instance with filter added

        Example:
            >>> from datetime import date
            >>> folder.sentbefore(date(2025, 1, 1))
        """
        return self._clone_with_query(Query.sentbefore(date))

    # Size filters

    def larger(self, bytes: int) -> "Folder":
        """Filter messages larger than size in bytes.

        Args:
            bytes: Minimum size in bytes

        Returns:
            New Folder instance with filter added

        Example:
            >>> folder.larger(1_000_000)  # >1MB
        """
        return self._clone_with_query(Query.larger(bytes))

    def smaller(self, bytes: int) -> "Folder":
        """Filter messages smaller than size in bytes.

        Args:
            bytes: Maximum size in bytes

        Returns:
            New Folder instance with filter added

        Example:
            >>> folder.smaller(10_000)  # <10KB
        """
        return self._clone_with_query(Query.smaller(bytes))

    # Content filter

    def text(self, text: str) -> "Folder":
        """Search in subject OR body (IMAP TEXT command).

        Args:
            text: Text to search for

        Returns:
            New Folder instance with filter added

        Example:
            >>> folder.text('budget')
        """
        return self._clone_with_query(Query.text(text))

    # Address filter

    def cc(self, email: str | list[str]) -> "Folder":
        """Filter by CC recipient (supports multiple with OR logic).

        Args:
            email: Email address or list of addresses (OR logic)

        Returns:
            New Folder instance with filter added

        Example:
            >>> # Single address
            >>> folder.cc('team@example.com')
            >>>
            >>> # Multiple addresses (OR)
            >>> folder.cc(['team@example.com', 'manager@example.com'])
        """
        if isinstance(email, str):
            return self._clone_with_query(Query.cc(email))
        else:
            # Multiple addresses - build OR chain
            queries = [Query.cc(addr) for addr in email]
            combined = queries[0]
            for q in queries[1:]:
                combined = combined | q
            return self._clone_with_query(combined)

    # Flag filters

    def unanswered(self) -> "Folder":
        """Filter to only unanswered messages (not replied to).

        Returns:
            New Folder instance with filter added

        Example:
            >>> folder.unanswered()
        """
        return self._clone_with_query(Query.unanswered())

    def unflagged(self) -> "Folder":
        """Filter to only unflagged messages (not starred).

        Returns:
            New Folder instance with filter added

        Example:
            >>> folder.unflagged()
        """
        return self._clone_with_query(Query.unflagged())

    # Custom filters

    def keyword(self, flag: str | list[str]) -> "Folder":
        """Filter by custom IMAP keyword (supports multiple with OR logic).

        Args:
            flag: Keyword name or list of keywords (OR logic)

        Returns:
            New Folder instance with filter added

        Example:
            >>> # Single keyword
            >>> folder.keyword('Important')
            >>>
            >>> # Multiple keywords (OR)
            >>> folder.keyword(['Important', 'FollowUp'])
        """
        if isinstance(flag, str):
            return self._clone_with_query(Query.keyword(flag))
        else:
            # Multiple keywords - build OR chain
            queries = [Query.keyword(kw) for kw in flag]
            combined = queries[0]
            for q in queries[1:]:
                combined = combined | q
            return self._clone_with_query(combined)

    def header(self, field: str, value: str) -> "Folder":
        """Filter by arbitrary header field.

        Args:
            field: Header field name (e.g., 'X-Priority')
            value: Header field value

        Returns:
            New Folder instance with filter added

        Example:
            >>> folder.header('X-Priority', '1')
        """
        return self._clone_with_query(Query.header(field, value))

    # Query builder integration

    def query(self, q: Query) -> "Folder":
        """Apply complex Query expression with boolean operators.

        Args:
            q: Query expression (use Q builder)

        Returns:
            New Folder instance with filter added

        Example:
            >>> from mailcore import Q
            >>> folder.query(Q.from_('alice') | Q.subject('urgent'))
            >>> folder.query((Q.from_('alice') | Q.from_('bob')) & Q.unseen())
        """
        return self._clone_with_query(q)

    async def list(self, limit: int | None = None, offset: int = 0) -> MessageList:
        """Execute query and return messages.

        Combines accumulated query parts with AND logic, executes via IMAP (returns DTOs),
        converts DTOs to Message entities with both IMAP and SMTP injected.

        Args:
            limit: Maximum messages to return (None = unlimited)
            offset: Skip first N messages (for pagination)

        Returns:
            MessageList with Message entities (IMAP and SMTP injected)
        """
        # Build query from accumulated parts
        if not self._query_parts:
            query = Query.all()
        else:
            query = self._query_parts[0]
            for q in self._query_parts[1:]:
                query = query & q

        # Execute query via IMAP - returns MessageListData (DTO)
        data = await self._imap.query_messages(self._name, query, limit=limit, offset=offset)

        # Convert MessageData DTOs to Message entities
        messages = [
            Message.from_data(msg_data, self._imap, self._smtp, self._default_sender) for msg_data in data.messages
        ]

        # Create MessageList with entities
        return MessageList(
            messages=messages,
            total_matches=data.total_matches,
            total_in_folder=data.total_in_folder,
            folder=data.folder,
        )

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
