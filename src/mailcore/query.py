"""Query class for IMAP search criteria with boolean operators."""

import datetime


class Query:
    """Boolean query builder for IMAP search with composable conditions.

    Provides factory methods for common search criteria and boolean operators
    (AND, OR, NOT) for building complex IMAP queries with natural Python syntax.

    IMAP Criteria Format:
        - Single criterion: ['FROM', 'alice']
        - AND (implicit flattened): ['FROM', 'alice', 'UNSEEN']
        - OR (explicit): ['OR', 'FROM', 'alice', 'FROM', 'bob']
        - NOT (prefix): ['NOT', 'SEEN']
        - Complex nested: ['OR', 'FROM', 'alice', 'UNSEEN', 'FLAGGED']

    Boolean Operators:
        - AND: Q.from_('alice') & Q.unseen()
        - OR: Q.from_('alice') | Q.from_('bob')
        - NOT: ~Q.seen()

    Example:
        >>> # Simple query
        >>> q = Q.from_('alice@example.com')
        >>> q  # REPL-friendly repr
        Query(type='from', value='alice@example.com')
        >>> q.to_imap_criteria()
        ['FROM', 'alice@example.com']

        >>> # AND query (flattened)
        >>> q = Q.from_('alice') & Q.unseen()
        >>> q  # Shows nested structure
        Query(type='and', left=Query(type='from', value='alice'), right=Query(type='unseen'))
        >>> q.to_imap_criteria()
        ['FROM', 'alice', 'UNSEEN']

        >>> # OR query
        >>> q = Q.from_('alice') | Q.from_('bob')
        >>> q.to_imap_criteria()
        ['OR', 'FROM', 'alice', 'FROM', 'bob']

        >>> # NOT query
        >>> q = ~Q.seen()
        >>> q.to_imap_criteria()
        ['NOT', 'SEEN']

        >>> # Complex nested query: (from alice AND unseen) OR flagged
        >>> q = (Q.from_('alice') & Q.unseen()) | Q.flagged()
        >>> q.to_imap_criteria()
        ['OR', 'FROM', 'alice', 'UNSEEN', 'FLAGGED']

    Use Cases:
        - OR across different criteria: Q.from_('alice') | Q.subject('urgent')
        - NOT operator: ~Q.subject('spam')
        - Complex boolean logic: (Q.from_('alice') | Q.from_('bob')) & Q.unseen()

    Note:
        For OR within same criteria type, use list on Folder methods instead:
        folder.from_(['alice', 'bob']) is cleaner than Q.from_('alice') | Q.from_('bob')
    """

    def __init__(
        self,
        operation: str | None = None,
        left: "Query | None" = None,
        right: "Query | None" = None,
        criteria: list[str] | None = None,
    ) -> None:
        """Initialize Query with operation metadata.

        Args:
            operation: 'AND', 'OR', 'NOT', or None (leaf criterion)
            left: Left operand for binary operations
            right: Right operand for binary operations
            criteria: Leaf criterion (e.g., ['FROM', 'alice'])
        """
        self._operation = operation
        self._left = left
        self._right = right
        self._criteria = criteria

    def __and__(self, other: "Query") -> "Query":
        """AND operator: Q & Q.

        Args:
            other: Right operand

        Returns:
            New Q representing AND operation
        """
        return Q(operation="AND", left=self, right=other)

    def __or__(self, other: "Query") -> "Query":
        """OR operator: Q | Q.

        Args:
            other: Right operand

        Returns:
            New Q representing OR operation
        """
        return Q(operation="OR", left=self, right=other)

    def __invert__(self) -> "Query":
        """NOT operator: ~Q.

        Returns:
            New Q representing NOT operation
        """
        return Q(operation="NOT", left=self)

    def to_imap_criteria(self) -> list[str]:
        """Convert Q to IMAP search criteria list.

        Returns:
            IMAP criteria list with operations

        Example:
            >>> Q.from_('alice').to_imap_criteria()
            ['FROM', 'alice']
            >>> (Q.from_('alice') & Q.unseen()).to_imap_criteria()
            ['FROM', 'alice', 'UNSEEN']
            >>> (Q.from_('alice') | Q.from_('bob')).to_imap_criteria()
            ['OR', 'FROM', 'alice', 'FROM', 'bob']
            >>> (~Q.seen()).to_imap_criteria()
            ['NOT', 'SEEN']
        """
        if self._criteria is not None:
            # Leaf criterion
            return self._criteria

        if self._operation == "AND":
            # Flatten AND: [left..., right...]
            assert self._left is not None and self._right is not None
            left_criteria = self._left.to_imap_criteria()
            right_criteria = self._right.to_imap_criteria()
            return left_criteria + right_criteria

        if self._operation == "OR":
            # OR: ['OR', left..., right...]
            assert self._left is not None and self._right is not None
            left_criteria = self._left.to_imap_criteria()
            right_criteria = self._right.to_imap_criteria()
            return ["OR"] + left_criteria + right_criteria

        if self._operation == "NOT":
            # NOT: ['NOT', inner...]
            assert self._left is not None
            inner_criteria = self._left.to_imap_criteria()
            return ["NOT"] + inner_criteria

        # Unreachable
        return []

    # Factory methods for common criteria

    @staticmethod
    def from_(address: str) -> "Query":
        """FROM header filter.

        Args:
            address: Email address or partial match

        Returns:
            Q object for FROM criterion
        """
        return Q(criteria=["FROM", address])

    @staticmethod
    def to(address: str) -> "Query":
        """TO header filter.

        Args:
            address: Email address or partial match

        Returns:
            Q object for TO criterion
        """
        return Q(criteria=["TO", address])

    @staticmethod
    def subject(text: str) -> "Query":
        """SUBJECT contains filter.

        Args:
            text: Text to search in subject

        Returns:
            Q object for SUBJECT criterion
        """
        return Q(criteria=["SUBJECT", text])

    @staticmethod
    def body(text: str) -> "Query":
        """BODY contains filter.

        Args:
            text: Text to search in body

        Returns:
            Q object for BODY criterion
        """
        return Q(criteria=["BODY", text])

    @staticmethod
    def seen() -> "Query":
        """Messages with \\Seen flag.

        Returns:
            Q object for SEEN criterion
        """
        return Q(criteria=["SEEN"])

    @staticmethod
    def unseen() -> "Query":
        """Messages without \\Seen flag.

        Returns:
            Q object for UNSEEN criterion
        """
        return Q(criteria=["UNSEEN"])

    @staticmethod
    def answered() -> "Query":
        """Messages with \\Answered flag.

        Returns:
            Q object for ANSWERED criterion
        """
        return Q(criteria=["ANSWERED"])

    @staticmethod
    def flagged() -> "Query":
        """Messages with \\Flagged flag.

        Returns:
            Q object for FLAGGED criterion
        """
        return Q(criteria=["FLAGGED"])

    @staticmethod
    def deleted() -> "Query":
        """Messages with \\Deleted flag.

        Returns:
            Q object for DELETED criterion
        """
        return Q(criteria=["DELETED"])

    @staticmethod
    def draft() -> "Query":
        """Messages with \\Draft flag.

        Returns:
            Q object for DRAFT criterion
        """
        return Q(criteria=["DRAFT"])

    @staticmethod
    def recent() -> "Query":
        """Messages with \\Recent flag.

        Returns:
            Q object for RECENT criterion
        """
        return Q(criteria=["RECENT"])

    @staticmethod
    def all() -> "Query":
        """All messages (matches everything).

        Returns:
            Query object for ALL criterion
        """
        return Query(criteria=["ALL"])

    # UID range filter

    @staticmethod
    def uid_range(start: int, end: int | str) -> "Query":
        """Filter by UID range.

        Args:
            start: Starting UID (inclusive)
            end: Ending UID (inclusive) or "*" for highest UID in folder

        Returns:
            Query object for UID range criterion

        Note:
            IDLE pattern: Use uid_range(last_uid + 1, "*") to fetch only new messages
            after last seen UID. This is essential for IDLE event handling.

            IMAP Protocol Note:
            UID ranges are NOT search criteria - they're sequence sets used in SEARCH.
            IMAPClient.search() always returns UIDs, so we pass just the range string.
            The adapter doesn't need special handling for UID queries.

        Example:
            >>> Q.uid_range(100, 200)
            Query(criteria=['100:200'])
            >>> Q.uid_range(173, "*")
            Query(criteria=['173:*'])

            # IDLE pattern - fetch messages after last seen UID
            >>> last_uid = 42
            >>> new_messages_query = Q.uid_range(last_uid + 1, "*")
        """
        # UID range is a sequence set, not a search criterion
        # Pass just the range - IMAPClient.search() handles UID mode
        return Query(criteria=[f"{start}:{end}"])

    # Date filters

    @staticmethod
    def since(date: "datetime.date") -> "Query":
        """Messages on or after date (IMAP internal date).

        Args:
            date: Date to filter from (inclusive)

        Returns:
            Query object for SINCE criterion

        Example:
            >>> from datetime import date
            >>> Q.since(date(2025, 12, 21))
            Query(type='since', value='21-Dec-2025')
        """

        date_str = date.strftime("%d-%b-%Y")
        return Query(criteria=["SINCE", date_str])

    @staticmethod
    def before(date: "datetime.date") -> "Query":
        """Messages before date (IMAP internal date).

        Args:
            date: Date to filter before (exclusive)

        Returns:
            Query object for BEFORE criterion

        Example:
            >>> from datetime import date
            >>> Q.before(date(2025, 1, 1))
            Query(type='before', value='01-Jan-2025')
        """

        date_str = date.strftime("%d-%b-%Y")
        return Query(criteria=["BEFORE", date_str])

    @staticmethod
    def on(date: "datetime.date") -> "Query":
        """Messages on specific date (IMAP internal date).

        Args:
            date: Date to filter on (exact match)

        Returns:
            Query object for ON criterion

        Example:
            >>> from datetime import date
            >>> Q.on(date(2025, 12, 21))
            Query(type='on', value='21-Dec-2025')
        """

        date_str = date.strftime("%d-%b-%Y")
        return Query(criteria=["ON", date_str])

    @staticmethod
    def sentsince(date: "datetime.date") -> "Query":
        """Messages sent on or after date (IMAP Date header).

        Args:
            date: Date to filter from (inclusive)

        Returns:
            Query object for SENTSINCE criterion

        Example:
            >>> from datetime import date
            >>> Q.sentsince(date(2025, 12, 1))
            Query(type='sentsince', value='01-Dec-2025')
        """

        date_str = date.strftime("%d-%b-%Y")
        return Query(criteria=["SENTSINCE", date_str])

    @staticmethod
    def sentbefore(date: "datetime.date") -> "Query":
        """Messages sent before date (IMAP Date header).

        Args:
            date: Date to filter before (exclusive)

        Returns:
            Query object for SENTBEFORE criterion

        Example:
            >>> from datetime import date
            >>> Q.sentbefore(date(2025, 1, 1))
            Query(type='sentbefore', value='01-Jan-2025')
        """

        date_str = date.strftime("%d-%b-%Y")
        return Query(criteria=["SENTBEFORE", date_str])

    # Size filters

    @staticmethod
    def larger(bytes: int) -> "Query":
        """Messages larger than size in bytes.

        Args:
            bytes: Minimum size in bytes

        Returns:
            Query object for LARGER criterion

        Example:
            >>> Q.larger(1_000_000)  # >1MB
            Query(type='larger', value='1000000')
        """
        return Query(criteria=["LARGER", str(bytes)])

    @staticmethod
    def smaller(bytes: int) -> "Query":
        """Messages smaller than size in bytes.

        Args:
            bytes: Maximum size in bytes

        Returns:
            Query object for SMALLER criterion

        Example:
            >>> Q.smaller(10_000)  # <10KB
            Query(type='smaller', value='10000')
        """
        return Query(criteria=["SMALLER", str(bytes)])

    # Content filters

    @staticmethod
    def text(text: str) -> "Query":
        """Search in subject OR body (IMAP TEXT command).

        Args:
            text: Text to search for

        Returns:
            Query object for TEXT criterion

        Example:
            >>> Q.text('budget')
            Query(type='text', value='budget')
        """
        return Query(criteria=["TEXT", text])

    # Address filters

    @staticmethod
    def cc(email: str) -> "Query":
        """Filter by CC recipient (single value).

        Args:
            email: Email address or partial match

        Returns:
            Query object for CC criterion

        Note:
            For multiple CC addresses with OR logic, use Folder.cc(['a', 'b'])

        Example:
            >>> Q.cc('team@example.com')
            Query(type='cc', value='team@example.com')
        """
        return Query(criteria=["CC", email])

    # Flag filters

    @staticmethod
    def unanswered() -> "Query":
        """Messages without \\Answered flag (not replied to).

        Returns:
            Query object for UNANSWERED criterion

        Example:
            >>> Q.unanswered()
            Query(type='unanswered')
        """
        return Query(criteria=["UNANSWERED"])

    @staticmethod
    def unflagged() -> "Query":
        """Messages without \\Flagged flag (not starred).

        Returns:
            Query object for UNFLAGGED criterion

        Example:
            >>> Q.unflagged()
            Query(type='unflagged')
        """
        return Query(criteria=["UNFLAGGED"])

    # Custom filters

    @staticmethod
    def keyword(flag: str) -> "Query":
        """Filter by custom IMAP keyword (single value).

        Args:
            flag: Custom keyword name

        Returns:
            Query object for KEYWORD criterion

        Note:
            For multiple keywords with OR logic, use Folder.keyword(['a', 'b'])

        Example:
            >>> Q.keyword('Important')
            Query(type='keyword', value='Important')
        """
        return Query(criteria=["KEYWORD", flag])

    @staticmethod
    def header(field: str, value: str) -> "Query":
        """Filter by arbitrary header field.

        Args:
            field: Header field name (e.g., 'X-Priority')
            value: Header field value

        Returns:
            Query object for HEADER criterion

        Example:
            >>> Q.header('X-Priority', '1')
            Query(type='header', value='X-Priority: 1')
        """
        return Query(criteria=["HEADER", field, value])

    def __repr__(self) -> str:
        """Developer-friendly representation showing query type.

        Returns:
            Query(type='...') or recursive for compound queries

        Example:
            >>> Q.from_('alice@example.com')
            Query(type='from', value='alice@example.com')

            >>> Q.unseen()
            Query(type='unseen')

            >>> Q.from_('alice') & Q.unseen()
            Query(type='and', left=Query(...), right=Query(...))
        """
        if self._operation == "AND":
            return f"Query(type='and', left={self._left!r}, right={self._right!r})"
        elif self._operation == "OR":
            return f"Query(type='or', left={self._left!r}, right={self._right!r})"
        elif self._operation == "NOT":
            return f"Query(type='not', query={self._left!r})"
        elif self._criteria is not None:
            # Leaf criterion - extract type and value
            if len(self._criteria) == 1:
                # Flag query (no value)
                return f"Query(type={self._criteria[0].lower()!r})"
            else:
                # Query with value (e.g., ['FROM', 'alice'])
                query_type = self._criteria[0].lower()
                value = self._criteria[1]
                return f"Query(type={query_type!r}, value={value!r})"
        else:
            return "Query()"


# Alias for shorter syntax
Q = Query
