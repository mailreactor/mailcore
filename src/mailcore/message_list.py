"""MessageList container for query results."""

from typing import Any


class MessageList:
    """List-like container for message query results with pagination metadata.

    Provides list-like interface (__len__, __iter__, __getitem__) for messages
    along with pagination metadata (total_matches, total_in_folder).

    Attributes:
        messages: List of Message objects from query
        total_matches: Total messages matching query (before limit/offset)
        total_in_folder: Total messages in folder (unfiltered)
        folder: Folder name

    Example:
        >>> from mailcore.message_list import MessageList
        >>> result = MessageList(
        ...     messages=[],
        ...     total_matches=42,
        ...     total_in_folder=100,
        ...     folder="INBOX"
        ... )
        >>> len(result)
        0
        >>> result.total_matches
        42
        >>> result.folder
        'INBOX'
        >>> result  # REPL-friendly repr
        MessageList(returned=0, total_matches=42, total_in_folder=100, folder='INBOX')
    """

    def __init__(
        self,
        messages: list[Any],  # list[Message] but avoiding circular import
        total_matches: int,
        total_in_folder: int,
        folder: str,
    ) -> None:
        """Initialize MessageList with messages and metadata.

        Args:
            messages: List of Message domain objects
            total_matches: Total messages matching query criteria
            total_in_folder: Total messages in folder
            folder: Folder name
        """
        self.messages = messages
        self.total_matches = total_matches
        self.total_in_folder = total_in_folder
        self.folder = folder

    def __len__(self) -> int:
        """Return number of messages in this result.

        Returns:
            Number of messages (after limit/offset applied)

        Example:
            >>> result = MessageList(messages=[1, 2, 3], total_matches=10, total_in_folder=50, folder="INBOX")
            >>> len(result)
            3
        """
        return len(self.messages)

    def __iter__(self) -> Any:
        """Iterate over messages.

        Returns:
            Iterator over messages

        Example:
            >>> result = MessageList(messages=[1, 2, 3], total_matches=10, total_in_folder=50, folder="INBOX")
            >>> for msg in result:
            ...     print(msg)
            1
            2
            3
        """
        return iter(self.messages)

    def __getitem__(self, index: int | slice) -> Any:
        """Access message by index or slice.

        Args:
            index: Integer index or slice

        Returns:
            Message at index or list of messages for slice

        Example:
            >>> result = MessageList(messages=[1, 2, 3], total_matches=10, total_in_folder=50, folder="INBOX")
            >>> result[0]
            1
            >>> result[1:3]
            [2, 3]
        """
        return self.messages[index]

    @property
    def returned_count(self) -> int:
        """Number of messages in this result (same as len(self)).

        Returns:
            Number of messages returned in this result

        Example:
            >>> result = MessageList(messages=[1, 2, 3], total_matches=10, total_in_folder=50, folder="INBOX")
            >>> result.returned_count
            3
        """
        return len(self.messages)

    @property
    def has_more(self) -> bool:
        """Whether more results are available beyond this result.

        Returns:
            True if total_matches > returned_count

        Example:
            >>> result = MessageList(messages=[1, 2, 3], total_matches=10, total_in_folder=50, folder="INBOX")
            >>> result.has_more
            True
        """
        return self.total_matches > len(self.messages)

    def __repr__(self) -> str:
        """Developer-friendly representation showing key stats.

        Returns:
            MessageList(returned=X, total_matches=Y, total_in_folder=Z, folder='...')

        Example:
            >>> messages = MessageList(
            ...     messages=[1, 2, 3],
            ...     total_matches=73,
            ...     total_in_folder=1542,
            ...     folder="INBOX"
            ... )
            >>> messages
            MessageList(returned=3, total_matches=73, total_in_folder=1542, folder='INBOX')
        """
        return (
            f"MessageList("
            f"returned={len(self.messages)}, "
            f"total_matches={self.total_matches}, "
            f"total_in_folder={self.total_in_folder}, "
            f"folder={self.folder!r})"
        )
