"""Tests for ABC protocol contracts."""

import pytest

from mailcore.protocols import IMAPConnection, SMTPConnection


def test_imap_connection_is_abstract():
    """Verify IMAPConnection cannot be instantiated without implementing abstract methods."""
    with pytest.raises(TypeError, match="Can't instantiate abstract class"):
        IMAPConnection()  # type: ignore


def test_smtp_connection_is_abstract():
    """Verify SMTPConnection cannot be instantiated without implementing abstract methods."""
    with pytest.raises(TypeError, match="Can't instantiate abstract class"):
        SMTPConnection()  # type: ignore


@pytest.mark.skip(reason="TODO: Story 3.2 will implement full ABC contract tests")
def test_imap_connection_method_signatures():
    """Verify IMAPConnection has correct method signatures."""
    pass


@pytest.mark.skip(reason="TODO: Story 3.2 will implement full ABC contract tests")
def test_smtp_connection_method_signatures():
    """Verify SMTPConnection has correct method signatures."""
    pass
