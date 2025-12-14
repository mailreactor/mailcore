"""Query class for IMAP search criteria with boolean operators."""


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
        >>> q.to_imap_criteria()
        ['FROM', 'alice@example.com']

        >>> # AND query (flattened)
        >>> q = Q.from_('alice') & Q.unseen()
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


# Alias for shorter syntax
Q = Query
