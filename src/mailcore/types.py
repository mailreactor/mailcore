"""Domain types for email addresses, message flags, and other email concepts."""

from enum import Enum

# TODO: Story 3.8 will implement EmailAddress, MessageFlag, and other types


class EmailAddress:
    """RFC 5322 compliant email address with name and address parts.

    Example:
        addr = EmailAddress(name="Alice Smith", address="alice@example.com")
        str(addr)  # "Alice Smith <alice@example.com>"
    """

    def __init__(self, address: str, name: str | None = None) -> None:
        """Initialize email address.

        Args:
            address: Email address (required)
            name: Display name (optional)
        """
        self.address = address
        self.name = name


class MessageFlag(str, Enum):
    """IMAP message flags."""

    SEEN = "\\Seen"
    ANSWERED = "\\Answered"
    FLAGGED = "\\Flagged"
    DELETED = "\\Deleted"
    DRAFT = "\\Draft"
    RECENT = "\\Recent"
