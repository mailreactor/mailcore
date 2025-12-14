"""Query class for IMAP search criteria."""


class Query:
    """IMAP search query builder.

    Stores IMAP search criteria as a list or string and provides
    a method to convert to IMAP-compatible list format.

    Args:
        criteria: IMAP search criteria as list or string

    Example:
        >>> query = Query(['FROM', 'alice'])
        >>> query.to_imap_criteria()
        ['FROM', 'alice']
        >>> query2 = Query('ALL')
        >>> query2.to_imap_criteria()
        ['ALL']
    """

    def __init__(self, criteria: list[str] | str) -> None:
        """Initialize Query with IMAP criteria.

        Args:
            criteria: IMAP search criteria as list or string
        """
        self.criteria = criteria

    def to_imap_criteria(self) -> list[str]:
        """Convert Query to IMAP search criteria list.

        Returns IMAP-compatible criteria list.

        Returns:
            IMAP criteria list (e.g., ['FROM', 'alice'] or ['ALL'])

        Example:
            >>> Query(['FROM', 'alice', 'UNSEEN']).to_imap_criteria()
            ['FROM', 'alice', 'UNSEEN']
            >>> Query('ALL').to_imap_criteria()
            ['ALL']
        """
        if isinstance(self.criteria, str):
            return [self.criteria]
        return self.criteria
