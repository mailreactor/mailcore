"""Tests for Draft standard email headers (Story 3.34).

Tests cover reply_to, request_read_receipt, request_delivery_receipt,
priority, and sender methods, plus header application in send().
"""

import pytest
from mocks import MockIMAPConnection, MockSMTPConnection

from mailcore import Draft, DSNReturn, Priority


@pytest.fixture
def smtp():
    """Mock SMTP connection."""
    return MockSMTPConnection()


@pytest.fixture
def imap():
    """Mock IMAP connection."""
    return MockIMAPConnection()


@pytest.fixture
def draft(smtp):
    """Basic draft for testing."""
    return Draft(smtp=smtp, default_from="sender@example.com")


# =============================================================================
# reply_to() method tests
# =============================================================================


def test_reply_to_single_email(draft):
    """reply_to() accepts single email string."""
    result = draft.reply_to("support@example.com")
    assert result is draft  # Fluent interface
    assert draft._reply_to == ["support@example.com"]


def test_reply_to_list_of_emails(draft):
    """reply_to() accepts list of emails."""
    emails = ["team@example.com", "manager@example.com"]
    draft.reply_to(emails)
    assert draft._reply_to == emails


def test_reply_to_overwrites_previous(draft):
    """reply_to() overwrites previous value."""
    draft.reply_to("first@example.com")
    draft.reply_to("second@example.com")
    assert draft._reply_to == ["second@example.com"]


async def test_reply_to_applied_in_send(draft, smtp):
    """reply_to addresses are passed to SMTP adapter."""
    await draft.to("recipient@example.com").subject("Test").body("Body").reply_to("support@example.com").send()

    sent = smtp._sent_messages[0]
    assert len(sent["reply_to"]) == 1
    assert sent["reply_to"][0].email == "support@example.com"


async def test_reply_to_multiple_applied_in_send(draft, smtp):
    """Multiple reply_to addresses are passed to SMTP adapter."""
    reply_addrs = ["team@example.com", "manager@example.com"]
    await draft.to("recipient@example.com").subject("Test").body("Body").reply_to(reply_addrs).send()

    sent = smtp._sent_messages[0]
    assert len(sent["reply_to"]) == 2
    assert sent["reply_to"][0].email == "team@example.com"
    assert sent["reply_to"][1].email == "manager@example.com"


# =============================================================================
# request_read_receipt() method tests
# =============================================================================


def test_request_read_receipt_explicit_email(draft):
    """request_read_receipt() accepts explicit email."""
    result = draft.request_read_receipt("receipts@example.com")
    assert result is draft  # Fluent interface
    assert draft._request_read_receipt is True
    assert draft._read_receipt_to == "receipts@example.com"


def test_request_read_receipt_defaults_to_from(draft):
    """request_read_receipt() defaults to None (resolved at send time)."""
    draft.request_read_receipt()
    assert draft._request_read_receipt is True
    assert draft._read_receipt_to is None  # Resolved at send()


async def test_request_read_receipt_uses_default_from(draft, smtp):
    """Read receipt defaults to default_from when no explicit email."""
    await draft.to("recipient@example.com").subject("Test").body("Body").request_read_receipt().send()

    sent = smtp._sent_messages[0]
    assert sent["disposition_notification_to"] == "sender@example.com"  # default_from


async def test_request_read_receipt_uses_from_override(draft, smtp):
    """Read receipt uses from_() override when no explicit email."""
    await (
        draft.to("recipient@example.com")
        .subject("Test")
        .body("Body")
        .from_("alias@example.com")
        .request_read_receipt()
        .send()
    )

    sent = smtp._sent_messages[0]
    assert sent["disposition_notification_to"] == "alias@example.com"  # from_() override


async def test_request_read_receipt_builder_order_independent(draft, smtp):
    """Read receipt resolves correctly regardless of builder order."""
    # Test both orders produce same result
    draft1 = Draft(smtp=smtp, default_from="sender@example.com")
    await (
        draft1.request_read_receipt()
        .from_("alias@example.com")
        .to("recipient@example.com")
        .subject("Test")
        .body("Body")
        .send()
    )

    draft2 = Draft(smtp=smtp, default_from="sender@example.com")
    await (
        draft2.from_("alias@example.com")
        .request_read_receipt()
        .to("recipient@example.com")
        .subject("Test")
        .body("Body")
        .send()
    )

    assert smtp._sent_messages[0]["disposition_notification_to"] == "alias@example.com"
    assert smtp._sent_messages[1]["disposition_notification_to"] == "alias@example.com"


async def test_request_read_receipt_explicit_email_used(draft, smtp):
    """Explicit read receipt email takes precedence."""
    await (
        draft.to("recipient@example.com")
        .subject("Test")
        .body("Body")
        .from_("alias@example.com")
        .request_read_receipt("receipts@example.com")
        .send()
    )

    sent = smtp._sent_messages[0]
    assert sent["disposition_notification_to"] == "receipts@example.com"


# =============================================================================
# request_delivery_receipt() method tests
# =============================================================================


def test_request_delivery_receipt_sets_flag(draft):
    """request_delivery_receipt() sets internal flag."""
    result = draft.request_delivery_receipt()
    assert result is draft  # Fluent interface
    assert draft._request_delivery_receipt is True


async def test_request_delivery_receipt_applied_in_send(draft, smtp):
    """Delivery receipt flag generates NOTIFY parameter."""
    await draft.to("recipient@example.com").subject("Test").body("Body").request_delivery_receipt().send()

    sent = smtp._sent_messages[0]
    assert sent["notify"] == "SUCCESS,FAILURE,DELAY"


async def test_no_delivery_receipt_by_default(draft, smtp):
    """No NOTIFY parameter when delivery receipt not requested."""
    await draft.to("recipient@example.com").subject("Test").body("Body").send()

    sent = smtp._sent_messages[0]
    assert sent["notify"] is None


async def test_delivery_receipt_dsn_return_enum(draft, smtp):
    """Delivery receipt accepts DSNReturn enum for return_content."""
    await (
        draft.to("recipient@example.com")
        .subject("Test")
        .body("Body")
        .request_delivery_receipt(return_content=DSNReturn.FULL)
        .send()
    )

    sent = smtp._sent_messages[0]
    assert sent["notify"] == "SUCCESS,FAILURE,DELAY"
    assert sent["dsn_return"] == "full"


async def test_delivery_receipt_dsn_return_string(draft, smtp):
    """Delivery receipt accepts string for return_content with validation."""
    await (
        draft.to("recipient@example.com")
        .subject("Test")
        .body("Body")
        .request_delivery_receipt(return_content="headers")
        .send()
    )

    sent = smtp._sent_messages[0]
    assert sent["dsn_return"] == "headers"


async def test_delivery_receipt_dsn_return_defaults_to_headers(draft, smtp):
    """Delivery receipt defaults to HEADERS when return_content not specified."""
    await draft.to("recipient@example.com").subject("Test").body("Body").request_delivery_receipt().send()

    sent = smtp._sent_messages[0]
    assert sent["dsn_return"] == "headers"  # Default


def test_delivery_receipt_dsn_return_validates_string(draft):
    """Delivery receipt validates invalid return_content string."""
    with pytest.raises(ValueError, match="Invalid DSN return content: 'invalid'"):
        draft.request_delivery_receipt(return_content="invalid")


async def test_delivery_receipt_envelope_id(draft, smtp):
    """Delivery receipt accepts envelope_id for tracking."""
    await (
        draft.to("recipient@example.com")
        .subject("Test")
        .body("Body")
        .request_delivery_receipt(envelope_id="order-12345")
        .send()
    )

    sent = smtp._sent_messages[0]
    assert sent["dsn_envelope_id"] == "order-12345"


async def test_delivery_receipt_all_dsn_parameters(draft, smtp):
    """Delivery receipt with all DSN parameters (return_content + envelope_id)."""
    await (
        draft.to("recipient@example.com")
        .subject("Test")
        .body("Body")
        .request_delivery_receipt(return_content=DSNReturn.FULL, envelope_id="ticket-789")
        .send()
    )

    sent = smtp._sent_messages[0]
    assert sent["notify"] == "SUCCESS,FAILURE,DELAY"
    assert sent["dsn_return"] == "full"
    assert sent["dsn_envelope_id"] == "ticket-789"


# =============================================================================
# priority() method tests
# =============================================================================


def test_priority_accepts_enum(draft):
    """priority() accepts Priority enum."""
    result = draft.priority(Priority.HIGH)
    assert result is draft  # Fluent interface
    assert draft._priority == "high"


def test_priority_accepts_string(draft):
    """priority() accepts valid priority string."""
    draft.priority("high")
    assert draft._priority == "high"


def test_priority_validates_string(draft):
    """priority() raises ValueError for invalid string."""
    with pytest.raises(ValueError, match="Invalid priority: 'urgent'"):
        draft.priority("urgent")


def test_priority_all_valid_levels(draft):
    """priority() accepts all Priority enum values."""
    for level in Priority:
        draft.priority(level)
        assert draft._priority == level.value

    for level_str in ["highest", "high", "normal", "low", "lowest"]:
        draft.priority(level_str)
        assert draft._priority == level_str


def test_priority_overwrites_previous(draft):
    """priority() overwrites previous value."""
    draft.priority(Priority.HIGH)
    draft.priority(Priority.LOW)
    assert draft._priority == "low"


async def test_priority_applied_in_send(draft, smtp):
    """Priority value is passed to SMTP adapter."""
    await draft.to("recipient@example.com").subject("Test").body("Body").priority(Priority.HIGH).send()

    sent = smtp._sent_messages[0]
    assert sent["priority"] == "high"


# =============================================================================
# sender() method tests
# =============================================================================


def test_sender_accepts_email(draft):
    """sender() accepts email string."""
    result = draft.sender("secretary@example.com")
    assert result is draft  # Fluent interface
    assert draft._sender == "secretary@example.com"


def test_sender_accepts_name_format(draft):
    """sender() accepts 'Name <email>' format."""
    draft.sender("Secretary <secretary@example.com>")
    assert draft._sender == "Secretary <secretary@example.com>"


def test_sender_overwrites_previous(draft):
    """sender() overwrites previous value."""
    draft.sender("first@example.com")
    draft.sender("second@example.com")
    assert draft._sender == "second@example.com"


async def test_sender_applied_in_send(draft, smtp):
    """Sender is passed to SMTP adapter."""
    await draft.to("recipient@example.com").subject("Test").body("Body").sender("secretary@example.com").send()

    sent = smtp._sent_messages[0]
    assert sent["sender"] is not None
    assert sent["sender"].email == "secretary@example.com"


async def test_sender_with_name_applied_in_send(draft, smtp):
    """Sender with name is parsed correctly."""
    await (
        draft.to("recipient@example.com")
        .subject("Test")
        .body("Body")
        .sender("Secretary <secretary@example.com>")
        .send()
    )

    sent = smtp._sent_messages[0]
    assert sent["sender"].email == "secretary@example.com"
    assert sent["sender"].name == "Secretary"


# =============================================================================
# Integration tests - multiple headers
# =============================================================================


async def test_all_headers_combined(draft, smtp):
    """All new headers can be used together."""
    await (
        draft.to("recipient@example.com")
        .subject("Test")
        .body("Body")
        .reply_to("support@example.com")
        .request_read_receipt()
        .request_delivery_receipt()
        .priority(Priority.HIGH)
        .sender("secretary@example.com")
        .send()
    )

    sent = smtp._sent_messages[0]
    assert len(sent["reply_to"]) == 1
    assert sent["reply_to"][0].email == "support@example.com"
    assert sent["disposition_notification_to"] == "sender@example.com"
    assert sent["notify"] == "SUCCESS,FAILURE,DELAY"
    assert sent["priority"] == "high"
    assert sent["sender"].email == "secretary@example.com"


async def test_headers_optional_when_not_set(draft, smtp):
    """Headers are None when not set."""
    await draft.to("recipient@example.com").subject("Test").body("Body").send()

    sent = smtp._sent_messages[0]
    assert sent["reply_to"] == []
    assert sent["disposition_notification_to"] is None
    assert sent["notify"] is None
    assert sent["priority"] is None
    assert sent["sender"] is None


# =============================================================================
# Validation tests
# =============================================================================


async def test_invalid_reply_to_email_caught_at_send(draft):
    """Invalid reply_to email raises at send time."""
    draft.to("recipient@example.com").subject("Test").body("Body").reply_to("not-an-email")

    with pytest.raises(ValueError):
        await draft.send()


async def test_invalid_sender_email_caught_at_send(draft):
    """Invalid sender email raises at send time."""
    draft.to("recipient@example.com").subject("Test").body("Body").sender("not-an-email")

    with pytest.raises(ValueError):
        await draft.send()
