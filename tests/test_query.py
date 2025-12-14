"""Tests for Query (and Q alias) in query.py."""

from mailcore.query import Q, Query


# Verify Q is alias for Query
def test_q_is_alias_for_query() -> None:
    """Verify Q is an alias for Query class."""
    assert Q is Query


# Query Boolean Operator Tests


def test_q_from_static_method() -> None:
    """Verify Q.from_() creates FROM query."""
    q = Q.from_("alice@example.com")
    assert q.to_imap_criteria() == ["FROM", "alice@example.com"]


def test_q_to_static_method() -> None:
    """Verify Q.to() creates TO query."""
    q = Q.to("bob@example.com")
    assert q.to_imap_criteria() == ["TO", "bob@example.com"]


def test_q_subject_static_method() -> None:
    """Verify Q.subject() creates SUBJECT query."""
    q = Q.subject("urgent")
    assert q.to_imap_criteria() == ["SUBJECT", "urgent"]


def test_q_body_static_method() -> None:
    """Verify Q.body() creates BODY query."""
    q = Q.body("hello")
    assert q.to_imap_criteria() == ["BODY", "hello"]


def test_q_seen_static_method() -> None:
    """Verify Q.seen() creates SEEN query."""
    q = Q.seen()
    assert q.to_imap_criteria() == ["SEEN"]


def test_q_unseen_static_method() -> None:
    """Verify Q.unseen() creates UNSEEN query (NOT SEEN)."""
    q = Q.unseen()
    assert q.to_imap_criteria() == ["UNSEEN"]


def test_q_answered_static_method() -> None:
    """Verify Q.answered() creates ANSWERED query."""
    q = Q.answered()
    assert q.to_imap_criteria() == ["ANSWERED"]


def test_q_flagged_static_method() -> None:
    """Verify Q.flagged() creates FLAGGED query."""
    q = Q.flagged()
    assert q.to_imap_criteria() == ["FLAGGED"]


def test_q_deleted_static_method() -> None:
    """Verify Q.deleted() creates DELETED query."""
    q = Q.deleted()
    assert q.to_imap_criteria() == ["DELETED"]


def test_q_draft_static_method() -> None:
    """Verify Q.draft() creates DRAFT query."""
    q = Q.draft()
    assert q.to_imap_criteria() == ["DRAFT"]


def test_q_recent_static_method() -> None:
    """Verify Q.recent() creates RECENT query."""
    q = Q.recent()
    assert q.to_imap_criteria() == ["RECENT"]


def test_q_all_static_method() -> None:
    """Verify Q.all() creates ALL query."""
    q = Q.all()
    assert q.to_imap_criteria() == ["ALL"]


def test_q_and_operator() -> None:
    """Verify Q & Q produces AND (flattened list)."""
    q = Q.from_("alice") & Q.unseen()
    assert q.to_imap_criteria() == ["FROM", "alice", "UNSEEN"]


def test_q_or_operator() -> None:
    """Verify Q | Q produces OR."""
    q = Q.from_("alice") | Q.from_("bob")
    assert q.to_imap_criteria() == ["OR", "FROM", "alice", "FROM", "bob"]


def test_q_not_operator() -> None:
    """Verify ~Q produces NOT."""
    q = ~Q.seen()
    assert q.to_imap_criteria() == ["NOT", "SEEN"]


def test_q_complex_nested_query() -> None:
    """Verify complex nested query: (from alice AND unseen) OR flagged."""
    q = (Q.from_("alice") & Q.unseen()) | Q.flagged()
    # (FROM alice UNSEEN) OR FLAGGED
    assert q.to_imap_criteria() == ["OR", "FROM", "alice", "UNSEEN", "FLAGGED"]


def test_q_complex_three_way_or() -> None:
    """Verify three-way OR: alice OR bob OR charlie."""
    q = Q.from_("alice") | Q.from_("bob") | Q.from_("charlie")
    # OR is binary, so: OR (OR alice bob) charlie
    assert q.to_imap_criteria() == ["OR", "OR", "FROM", "alice", "FROM", "bob", "FROM", "charlie"]


def test_q_and_chain() -> None:
    """Verify chained AND: from alice AND unseen AND flagged."""
    q = Q.from_("alice") & Q.unseen() & Q.flagged()
    # AND flattens
    assert q.to_imap_criteria() == ["FROM", "alice", "UNSEEN", "FLAGGED"]


def test_q_not_and() -> None:
    """Verify NOT (from alice AND unseen)."""
    q = ~(Q.from_("alice") & Q.unseen())
    assert q.to_imap_criteria() == ["NOT", "FROM", "alice", "UNSEEN"]


def test_q_not_or() -> None:
    """Verify NOT (from alice OR from bob)."""
    q = ~(Q.from_("alice") | Q.from_("bob"))
    assert q.to_imap_criteria() == ["NOT", "OR", "FROM", "alice", "FROM", "bob"]
