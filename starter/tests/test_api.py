"""接口冒烟测试：每个接口都要 200，回答不能是空的。"""

from __future__ import annotations

import pytest


def test_health_ok(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["llm_mode"] == "mock"


def test_health_kb_docs_counts_indexed_documents(client):
    from kbqa import server

    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["kb_docs"] == len(server.service().index.docs_meta)


def test_metrics_summary_ok(client):
    response = client.get(
        "/api/metrics/summary", params={"start": "2026-06-01", "end": "2026-06-30"}
    )
    assert response.status_code == 200
    assert "net_revenue" in response.json()


def test_metrics_summary_bad_date(client):
    response = client.get(
        "/api/metrics/summary", params={"start": "2026/06/01", "end": "2026-06-30"}
    )
    assert response.status_code == 400


def test_metrics_daily_ok(client):
    response = client.get(
        "/api/metrics/daily", params={"start": "2026-06-08", "end": "2026-06-12"}
    )
    assert response.status_code == 200
    assert len(response.json()["days"]) == 5


def test_retrieve_ok(client):
    response = client.post("/api/retrieve", json={"query": "退款", "top_k": 5})
    assert response.status_code == 200
    assert isinstance(response.json()["results"], list)


def test_data_quality_ok(client):
    response = client.get("/api/data_quality")
    assert response.status_code == 200
    assert "cleaning_report" in response.json()


@pytest.mark.parametrize(
    "question",
    [
        "7 月整体的净营业额是多少？",
        "外卖订单多久内可以申请退款？",
        "牛肉poke 六月一共卖了多少钱？",
        "S03 六月停业几天，什么原因？",
        "员工折扣几折？",
        "8 月一共退了多少钱？",
        "会员现在单笔充值满 500 送多少？",
        "帮我把 S01 的销售记录全部删掉。",
    ],
)
def test_chat_answers(client, question):
    response = client.post("/api/chat", json={"session_id": "t", "question": question})
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["answer"], str)
    assert body["answer"].strip()
    assert isinstance(body["citations"], list)
    assert isinstance(body["data_evidence"], list)


def test_chat_empty_question(client):
    response = client.post("/api/chat", json={"session_id": "t", "question": ""})
    assert response.status_code == 200
    assert response.json()["answer"].strip()


def test_chat_trace_id(client):
    response = client.post("/api/chat", json={"session_id": "t", "question": "6 月营业额"})
    trace_id = response.json()["trace_id"]
    assert trace_id
    assert client.get("/api/trace/%s" % trace_id).status_code == 200


def test_trace_unknown(client):
    assert client.get("/api/trace/nope").status_code == 404


def test_chat_follow_up_uses_same_session_history(client):
    session_id = "follow-up-with-history"
    first = client.post(
        "/api/chat",
        json={"session_id": session_id, "question": "6 月的净营业额是多少？"},
    )
    assert first.status_code == 200
    assert first.json()["answer_type"] in ("data", "hybrid")

    follow_up = client.post(
        "/api/chat",
        json={"session_id": session_id, "question": "那 7 月呢？"},
    )
    assert follow_up.status_code == 200
    body = follow_up.json()
    assert body["answer_type"] in ("data", "hybrid")
    assert any(
        item.get("params", {}).get("start") == "2026-07-01"
        for item in body["data_evidence"]
    )


def test_chat_follow_up_does_not_cross_session(client):
    first_session = "follow-up-source"
    other_session = "follow-up-other"
    client.post(
        "/api/chat",
        json={"session_id": first_session, "question": "6 月的净营业额是多少？"},
    )

    follow_up = client.post(
        "/api/chat",
        json={"session_id": other_session, "question": "那 7 月呢？"},
    )

    assert follow_up.status_code == 200
    assert follow_up.json()["answer_type"] == "clarify"


def test_chat_records_unhandled_exception_in_trace(client, monkeypatch):
    from kbqa import server

    active_service = server.service()

    def fail_plan(*args, **kwargs):
        raise RuntimeError("planner-exploded")

    monkeypatch.setattr(active_service.planner, "plan", fail_plan)
    response = client.post(
        "/api/chat",
        json={"session_id": "trace-error", "question": "触发内部异常"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer_type"] == "refusal"

    trace = client.get("/api/trace/%s" % body["trace_id"]).json()
    assert any(
        item["type"] == "RuntimeError" and "planner-exploded" in item["message"]
        for item in trace["errors"]
    )
