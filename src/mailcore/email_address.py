"""EmailAddress value object for email addresses with RFC 5322 formatting."""

from email.utils import formataddr, parseaddr


class EmailAddress:
    """Immutable value object for email addresses.

    Represents an email address with optional display name. Supports RFC 5322
    formatting for email headers, parsing from multiple string formats, and
    equality/hashing based on email only (case-insensitive).

    Attributes:
        email: Email address (e.g., 'alice@example.com')
        name: Display name (e.g., 'Alice Smith'), optional

    Examples:
        >>> addr = EmailAddress('alice@example.com')
        >>> addr.email
        'alice@example.com'
        >>> addr.name
        None

        >>> addr = EmailAddress('alice@example.com', 'Alice Smith')
        >>> str(addr)
        'Alice Smith <alice@example.com>'

        >>> addr1 = EmailAddress('alice@example.com', 'Alice')
        >>> addr2 = EmailAddress('ALICE@example.com', 'A. Smith')
        >>> addr1 == addr2
        True
    """

    def __init__(self, email: str, name: str | None = None) -> None:
        """Initialize email address.

        Args:
            email: Email address (e.g., 'alice@example.com')
            name: Display name (e.g., 'Alice Smith'), optional

        Raises:
            ValueError: If email format is invalid

        Examples:
            >>> EmailAddress('alice@example.com')
            EmailAddress(email='alice@example.com', name=None)

            >>> EmailAddress('alice@example.com', 'Alice Smith')
            EmailAddress(email='alice@example.com', name='Alice Smith')

            >>> EmailAddress('invalid')
            Traceback (most recent call last):
                ...
            ValueError: Invalid email format: invalid
        """
        # Basic validation: must contain @ and have domain part
        if not email or "@" not in email:
            raise ValueError(f"Invalid email format: {email}")

        # Check for domain part (at least one char after @)
        parts = email.split("@")
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise ValueError(f"Invalid email format: {email}")

        self._email = email
        self._name = name

    @property
    def email(self) -> str:
        """Email address.

        Returns:
            Email address string

        Example:
            >>> addr = EmailAddress('alice@example.com')
            >>> addr.email
            'alice@example.com'
        """
        return self._email

    @property
    def name(self) -> str | None:
        """Display name (optional).

        Returns:
            Display name or None

        Example:
            >>> addr = EmailAddress('alice@example.com', 'Alice Smith')
            >>> addr.name
            'Alice Smith'
        """
        return self._name

    @classmethod
    def parse(cls, address: str) -> "EmailAddress":
        """Parse email address from string.

        Supports formats:
        - 'alice@example.com'
        - 'Alice Smith <alice@example.com>'
        - '<alice@example.com>'

        Args:
            address: Email address string

        Returns:
            EmailAddress instance

        Raises:
            ValueError: If address format is invalid

        Examples:
            >>> EmailAddress.parse('alice@example.com')
            EmailAddress(email='alice@example.com', name=None)

            >>> EmailAddress.parse('Alice Smith <alice@example.com>')
            EmailAddress(email='alice@example.com', name='Alice Smith')

            >>> EmailAddress.parse('<alice@example.com>')
            EmailAddress(email='alice@example.com', name=None)

            >>> EmailAddress.parse('not-an-email')
            Traceback (most recent call last):
                ...
            ValueError: Invalid email format: not-an-email
        """
        name, email = parseaddr(address)

        # parseaddr returns empty string for email if unparseable
        if not email or "@" not in email:
            raise ValueError(f"Invalid email format: {address}")

        # If name is empty string, treat as None
        return cls(email=email, name=name if name else None)

    def to_rfc5322(self) -> str:
        """Format as RFC 5322 address for email headers.

        Handles special characters and encoding:
        - Quotes names with special chars (quotes, commas)
        - Encodes non-ASCII characters
        - Returns email only if no name

        Returns:
            RFC 5322 formatted address string

        Examples:
            >>> EmailAddress('alice@example.com').to_rfc5322()
            'alice@example.com'

            >>> EmailAddress('alice@example.com', 'Alice Smith').to_rfc5322()
            'Alice Smith <alice@example.com>'

            >>> EmailAddress('alice@example.com', 'Smith, Alice').to_rfc5322()
            '"Smith, Alice" <alice@example.com>'

            >>> EmailAddress('alice@example.com', 'André Müller').to_rfc5322()
            '=?utf-8?b?QW5kcsOpIE3DvGxsZXI=?= <alice@example.com>'
        """
        if self.name:
            return formataddr((self.name, self.email))
        else:
            return self.email

    def __str__(self) -> str:
        """String representation (human-readable, not RFC 5322).

        Returns:
            'Name <email>' if name present, otherwise 'email'

        Examples:
            >>> str(EmailAddress('alice@example.com', 'Alice Smith'))
            'Alice Smith <alice@example.com>'

            >>> str(EmailAddress('bob@example.com'))
            'bob@example.com'
        """
        if self.name:
            return f"{self.name} <{self.email}>"
        else:
            return self.email

    def __repr__(self) -> str:
        """Developer-friendly representation.

        Returns:
            EmailAddress(email='...', name='...')

        Example:
            >>> repr(EmailAddress('alice@example.com', 'Alice Smith'))
            "EmailAddress(email='alice@example.com', name='Alice Smith')"
        """
        return f"EmailAddress(email={self.email!r}, name={self.name!r})"

    def __eq__(self, other: object) -> bool:
        """Equality comparison (compares email only, ignores name).

        Args:
            other: Object to compare with

        Returns:
            True if both have same email address (case-insensitive)

        Examples:
            >>> EmailAddress('alice@example.com', 'Alice') == EmailAddress('alice@example.com', 'A. Smith')
            True

            >>> EmailAddress('ALICE@example.com') == EmailAddress('alice@example.com')
            True

            >>> EmailAddress('alice@example.com') == EmailAddress('bob@example.com')
            False
        """
        if not isinstance(other, EmailAddress):
            return False
        return self.email.lower() == other.email.lower()

    def __hash__(self) -> int:
        """Hash based on email only (for use in sets/dicts).

        Returns:
            Hash of lowercase email address

        Example:
            >>> addr1 = EmailAddress('alice@example.com', 'Alice')
            >>> addr2 = EmailAddress('ALICE@example.com', 'A. Smith')
            >>> hash(addr1) == hash(addr2)
            True
        """
        return hash(self.email.lower())
