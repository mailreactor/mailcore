"""Tests for EmailAddress value object."""

import pytest

from mailcore.email_address import EmailAddress

# Constructor tests


def test_email_address_initialization() -> None:
    """Test EmailAddress initialization with email and name."""
    addr = EmailAddress("alice@example.com", "Alice Smith")
    assert addr.email == "alice@example.com"
    assert addr.name == "Alice Smith"


def test_email_address_initialization_email_only() -> None:
    """Test EmailAddress initialization with email only."""
    addr = EmailAddress("alice@example.com")
    assert addr.email == "alice@example.com"
    assert addr.name is None


def test_email_address_validation_invalid_email() -> None:
    """Test EmailAddress raises ValueError for invalid email."""
    with pytest.raises(ValueError, match="Invalid email format"):
        EmailAddress("not-an-email")

    with pytest.raises(ValueError, match="Invalid email format"):
        EmailAddress("missing-domain@")

    with pytest.raises(ValueError, match="Invalid email format"):
        EmailAddress("@missing-local")

    with pytest.raises(ValueError, match="Invalid email format"):
        EmailAddress("")


# Parse tests


def test_parse_email_only() -> None:
    """Test parse with email only format."""
    addr = EmailAddress.parse("alice@example.com")
    assert addr.email == "alice@example.com"
    assert addr.name is None


def test_parse_email_with_name() -> None:
    """Test parse with 'Name <email>' format."""
    addr = EmailAddress.parse("Alice Smith <alice@example.com>")
    assert addr.email == "alice@example.com"
    assert addr.name == "Alice Smith"


def test_parse_email_angle_brackets_only() -> None:
    """Test parse with '<email>' format."""
    addr = EmailAddress.parse("<alice@example.com>")
    assert addr.email == "alice@example.com"
    assert addr.name is None


def test_parse_invalid_format() -> None:
    """Test parse raises ValueError for invalid format."""
    with pytest.raises(ValueError, match="Invalid email format"):
        EmailAddress.parse("not-an-email")

    with pytest.raises(ValueError, match="Invalid email format"):
        EmailAddress.parse("Alice Smith")


# RFC 5322 formatting tests


def test_to_rfc5322_email_only() -> None:
    """Test to_rfc5322() returns email only when no name."""
    addr = EmailAddress("alice@example.com")
    assert addr.to_rfc5322() == "alice@example.com"


def test_to_rfc5322_with_name() -> None:
    """Test to_rfc5322() returns 'Name <email>' format."""
    addr = EmailAddress("alice@example.com", "Alice Smith")
    assert addr.to_rfc5322() == "Alice Smith <alice@example.com>"


def test_to_rfc5322_special_characters() -> None:
    """Test to_rfc5322() quotes name with comma."""
    addr = EmailAddress("alice@example.com", "Smith, Alice")
    # formataddr automatically quotes names with special chars
    assert addr.to_rfc5322() == '"Smith, Alice" <alice@example.com>'


def test_to_rfc5322_non_ascii() -> None:
    """Test to_rfc5322() encodes non-ASCII characters using RFC 2047."""
    addr = EmailAddress("alice@example.com", "André Müller")
    result = addr.to_rfc5322()
    # formataddr uses RFC 2047 base64 encoding for non-ASCII
    # Format: =?utf-8?b?<base64>?= <email@example.com>
    assert result == "=?utf-8?b?QW5kcsOpIE3DvGxsZXI=?= <alice@example.com>"


# String representation tests


def test_str_representation() -> None:
    """Test __str__() returns readable format."""
    addr_with_name = EmailAddress("alice@example.com", "Alice Smith")
    assert str(addr_with_name) == "Alice Smith <alice@example.com>"

    addr_without_name = EmailAddress("bob@example.com")
    assert str(addr_without_name) == "bob@example.com"


def test_repr_representation() -> None:
    """Test __repr__() returns EmailAddress(...) format."""
    addr = EmailAddress("alice@example.com", "Alice Smith")
    assert repr(addr) == "EmailAddress(email='alice@example.com', name='Alice Smith')"

    addr_no_name = EmailAddress("bob@example.com")
    assert repr(addr_no_name) == "EmailAddress(email='bob@example.com', name=None)"


# Equality tests


def test_equality_same_email_different_name() -> None:
    """Test __eq__() ignores name, compares email only."""
    addr1 = EmailAddress("alice@example.com", "Alice")
    addr2 = EmailAddress("alice@example.com", "A. Smith")
    assert addr1 == addr2


def test_equality_case_insensitive() -> None:
    """Test __eq__() case-insensitive email comparison."""
    addr1 = EmailAddress("ALICE@example.com")
    addr2 = EmailAddress("alice@example.com")
    assert addr1 == addr2


def test_equality_with_non_email_address() -> None:
    """Test __eq__() returns False for non-EmailAddress objects."""
    addr = EmailAddress("alice@example.com")
    assert addr != "alice@example.com"
    assert addr != 123
    assert addr is not None


def test_hash_consistency() -> None:
    """Test __hash__() consistent with __eq__() (same email = same hash)."""
    addr1 = EmailAddress("alice@example.com", "Alice")
    addr2 = EmailAddress("ALICE@example.com", "A. Smith")
    assert hash(addr1) == hash(addr2)


def test_set_deduplication() -> None:
    """Test EmailAddress works in sets (deduplicates by email)."""
    addr1 = EmailAddress("alice@example.com", "Alice")
    addr2 = EmailAddress("ALICE@example.com", "A. Smith")
    addr3 = EmailAddress("bob@example.com", "Bob")

    addresses = {addr1, addr2, addr3}
    assert len(addresses) == 2  # Only alice and bob (addr1 and addr2 deduplicated)
