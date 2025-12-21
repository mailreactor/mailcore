"""mailcore exception classes."""


class MailcoreError(Exception):
    """Base exception for all mailcore errors."""


class FolderNotFoundError(MailcoreError):
    """Raised when IMAP folder doesn't exist.

    Attributes:
        folder: The folder name that was not found
    """

    def __init__(self, folder: str) -> None:
        """Initialize FolderNotFoundError.

        Args:
            folder: Folder name that doesn't exist
        """
        self.folder = folder
        super().__init__(f"Folder '{folder}' does not exist")


class SMTPError(MailcoreError):
    """Raised when SMTP operation fails.

    Base exception for all SMTP-related errors including connection
    failures, authentication errors, and send failures.
    """

    def __init__(self, message: str) -> None:
        """Initialize SMTPError.

        Args:
            message: Description of the SMTP error
        """
        super().__init__(message)
