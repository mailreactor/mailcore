"""Tests for Mailbox class (main entry point for email operations)."""

from unittest.mock import Mock

import pytest

from mailcore.mailbox import Mailbox


@pytest.fixture
def mock_imap():
    """Mock IMAP connection."""
    return Mock()


@pytest.mark.asyncio
async def test_mailbox_compose_returns_draft(mock_imap, mock_smtp):
    """Test compose() returns Draft with SMTP connection."""
    mailbox = Mailbox(imap=mock_imap, smtp=mock_smtp)

    draft = mailbox.compose()

    assert draft is not None
    assert draft._smtp == mock_smtp


@pytest.mark.asyncio
async def test_mailbox_send_shortcut(mock_imap, mock_smtp):
    """Test send() creates draft, applies kwargs, and sends."""
    mailbox = Mailbox(imap=mock_imap, smtp=mock_smtp)

    message_id = await mailbox.send(to="alice@example.com", subject="Hello", body="World", cc="bob@example.com")

    # Verify send was called
    mock_smtp.send_message.assert_called_once()

    # Check message_id returned
    assert message_id == "<sent-123@example.com>"

    # Verify fields were applied
    call_args = mock_smtp.send_message.call_args
    assert call_args.kwargs["subject"] == "Hello"
    assert call_args.kwargs["body_text"] == "World"
    assert call_args.kwargs["cc"] is not None
