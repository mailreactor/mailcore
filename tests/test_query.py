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


def test_query_repr_simple() -> None:
    """Verify Query repr for simple queries."""
    q = Q.from_("alice@example.com")
    repr_str = repr(q)
    assert "Query(type='from'" in repr_str
    assert "value='alice@example.com'" in repr_str


def test_query_repr_flag() -> None:
    """Verify Query repr for flag queries."""
    q = Q.unseen()
    assert "Query(type='unseen')" in repr(q)


def test_query_repr_compound_and() -> None:
    """Verify Query repr for AND queries."""
    q = Q.from_("alice") & Q.unseen()
    repr_str = repr(q)
    assert "Query(type='and'" in repr_str
    assert "left=" in repr_str
    assert "right=" in repr_str


def test_query_repr_compound_or() -> None:
    """Verify Query repr for OR queries."""
    q = Q.from_("alice") | Q.from_("bob")
    repr_str = repr(q)
    assert "Query(type='or'" in repr_str
    assert "left=" in repr_str
    assert "right=" in repr_str


def test_query_repr_not() -> None:
    """Verify Query repr for NOT queries."""
    q = ~Q.seen()
    repr_str = repr(q)
    assert "Query(type='not'" in repr_str
    assert "query=" in repr_str


# Date filter tests


def test_q_since_static_method() -> None:
    """Verify Q.since() creates SINCE query with DD-Mon-YYYY format."""
    from datetime import date

    q = Q.since(date(2025, 12, 21))
    assert q.to_imap_criteria() == ["SINCE", "21-Dec-2025"]


def test_q_before_static_method() -> None:
    """Verify Q.before() creates BEFORE query with DD-Mon-YYYY format."""
    from datetime import date

    q = Q.before(date(2025, 1, 1))
    assert q.to_imap_criteria() == ["BEFORE", "01-Jan-2025"]


def test_q_on_static_method() -> None:
    """Verify Q.on() creates ON query with DD-Mon-YYYY format."""
    from datetime import date

    q = Q.on(date(2025, 12, 21))
    assert q.to_imap_criteria() == ["ON", "21-Dec-2025"]


def test_q_sentsince_static_method() -> None:
    """Verify Q.sentsince() creates SENTSINCE query."""
    from datetime import date

    q = Q.sentsince(date(2025, 12, 1))
    assert q.to_imap_criteria() == ["SENTSINCE", "01-Dec-2025"]


def test_q_sentbefore_static_method() -> None:
    """Verify Q.sentbefore() creates SENTBEFORE query."""
    from datetime import date

    q = Q.sentbefore(date(2025, 1, 1))
    assert q.to_imap_criteria() == ["SENTBEFORE", "01-Jan-2025"]


# Size filter tests


def test_q_larger_static_method() -> None:
    """Verify Q.larger() creates LARGER query with integer to string conversion."""
    q = Q.larger(1_000_000)
    assert q.to_imap_criteria() == ["LARGER", "1000000"]


def test_q_smaller_static_method() -> None:
    """Verify Q.smaller() creates SMALLER query with integer to string conversion."""
    q = Q.smaller(10_000)
    assert q.to_imap_criteria() == ["SMALLER", "10000"]


# Content filter tests


def test_q_text_static_method() -> None:
    """Verify Q.text() creates TEXT query."""
    q = Q.text("budget")
    assert q.to_imap_criteria() == ["TEXT", "budget"]


# Address filter tests


def test_q_cc_static_method() -> None:
    """Verify Q.cc() creates CC query."""
    q = Q.cc("team@example.com")
    assert q.to_imap_criteria() == ["CC", "team@example.com"]


# Flag filter tests


def test_q_unanswered_static_method() -> None:
    """Verify Q.unanswered() creates UNANSWERED query."""
    q = Q.unanswered()
    assert q.to_imap_criteria() == ["UNANSWERED"]


def test_q_unflagged_static_method() -> None:
    """Verify Q.unflagged() creates UNFLAGGED query."""
    q = Q.unflagged()
    assert q.to_imap_criteria() == ["UNFLAGGED"]


# Custom filter tests


def test_q_keyword_static_method() -> None:
    """Verify Q.keyword() creates KEYWORD query."""
    q = Q.keyword("Important")
    assert q.to_imap_criteria() == ["KEYWORD", "Important"]


def test_q_header_static_method() -> None:
    """Verify Q.header() creates HEADER query with field and value."""
    q = Q.header("X-Priority", "1")
    assert q.to_imap_criteria() == ["HEADER", "X-Priority", "1"]


# Complex query tests with new filters


def test_q_date_and_size_query() -> None:
    """Verify complex query with date and size filters."""
    from datetime import date

    q = Q.since(date(2025, 12, 1)) & Q.larger(100_000)
    assert q.to_imap_criteria() == ["SINCE", "01-Dec-2025", "LARGER", "100000"]


def test_q_multi_criteria_or() -> None:
    """Verify OR query with different criteria types."""
    q = Q.from_("alice") | Q.subject("urgent")
    assert q.to_imap_criteria() == ["OR", "FROM", "alice", "SUBJECT", "urgent"]


def test_q_complex_nested_with_new_filters() -> None:
    """Verify complex nested query: (since date AND larger) OR text search."""
    from datetime import date

    q = (Q.since(date(2025, 12, 1)) & Q.larger(100_000)) | Q.text("budget")
    assert q.to_imap_criteria() == ["OR", "SINCE", "01-Dec-2025", "LARGER", "100000", "TEXT", "budget"]


# UID range tests (Story 3.28)


def test_q_uid_range_numeric_end() -> None:
    """Verify uid_range with numeric end creates correct IMAP criteria."""
    q = Q.uid_range(100, 200)
    assert q.to_imap_criteria() == ["100:200"]


def test_q_uid_range_star_end() -> None:
    """Verify uid_range with '*' end creates correct IMAP criteria (IDLE pattern)."""
    q = Q.uid_range(173, "*")
    assert q.to_imap_criteria() == ["173:*"]


def test_q_uid_range_single_message() -> None:
    """Verify uid_range for single message (start == end)."""
    q = Q.uid_range(42, 42)
    assert q.to_imap_criteria() == ["42:42"]


def test_q_uid_range_with_boolean_operators() -> None:
    """Verify uid_range combines with boolean operators."""
    q = Q.uid_range(100, "*") & Q.unseen()
    assert q.to_imap_criteria() == ["100:*", "UNSEEN"]


def test_q_uid_range_or_query() -> None:
    """Verify uid_range with OR operator."""
    q = Q.uid_range(1, 50) | Q.uid_range(200, 250)
    assert q.to_imap_criteria() == ["OR", "1:50", "200:250"]
