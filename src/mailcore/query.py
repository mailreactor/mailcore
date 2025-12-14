"""Q query builder for constructing email search queries with boolean logic."""

# TODO: Story 3.3 will implement Q query builder


class Q:
    """Query builder for email search with boolean operators (AND, OR, NOT).

    Example:
        query = Q(subject="invoice") & Q(unseen=True)
        query = Q(from_="alice@example.com") | Q(from_="bob@example.com")
    """

    def __init__(self, **kwargs: str | bool | int) -> None:
        """Initialize query with field=value pairs.

        Args:
            **kwargs: Query field constraints (subject, from_, to, unseen, etc.)
        """
        self.constraints = kwargs
