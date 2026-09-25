"""会话存储的隔离、截断和容量约束。"""

from __future__ import annotations

from kbqa.sessions import SessionStore


def test_sessions_are_isolated_and_turns_are_capped():
    store = SessionStore(max_sessions=10, max_turns=2)
    store.append("A", {"question": "a1"})
    store.append("B", {"question": "b1"})
    store.append("A", {"question": "a2"})
    store.append("A", {"question": "a3"})

    assert [turn["question"] for turn in store.history("A")] == ["a2", "a3"]
    assert [turn["question"] for turn in store.history("B")] == ["b1"]
    assert store.history("missing") == []

    snapshot = store.history("A")
    snapshot.append({"question": "changed"})
    assert [turn["question"] for turn in store.history("A")] == ["a2", "a3"]


def test_session_capacity_evicts_oldest_bucket():
    store = SessionStore(max_sessions=2, max_turns=6)
    store.append("A", {"question": "a1"})
    store.append("B", {"question": "b1"})
    store.append("C", {"question": "c1"})

    assert store.history("A") == []
    assert store.history("B")[0]["question"] == "b1"
    assert store.history("C")[0]["question"] == "c1"
