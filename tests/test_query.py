"""Tests for Query in query.py."""

from mailcore.query import Query


def test_query_to_imap_criteria_list() -> None:
    """Verify Query.to_imap_criteria() returns list for list input."""
    query = Query(["FROM", "alice"])
    assert query.to_imap_criteria() == ["FROM", "alice"]


def test_query_to_imap_criteria_string() -> None:
    """Verify Query.to_imap_criteria() converts string to list."""
    query = Query("ALL")
    assert query.to_imap_criteria() == ["ALL"]


def test_query_to_imap_criteria_complex() -> None:
    """Verify Query.to_imap_criteria() handles complex nested criteria."""
    query = Query(["FROM", "alice", "UNSEEN"])
    assert query.to_imap_criteria() == ["FROM", "alice", "UNSEEN"]
