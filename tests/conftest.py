"""pytest configuration and fixtures for mailcore tests."""

import pytest

# pytest-asyncio configuration is handled in pyproject.toml [tool.pytest.ini_options]


@pytest.fixture
def mock_imap_connection():
    """Mock IMAP connection for testing."""
    # TODO: Story 3.9 will implement MockIMAPConnection
    return None


@pytest.fixture
def mock_smtp_connection():
    """Mock SMTP connection for testing."""
    # TODO: Story 3.9 will implement MockSMTPConnection
    return None
