"""live 模式：日期与数值分开校验，工具调用必须收敛。"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from kbqa import live
from kbqa.llm import LLMError, LLMReply
from kbqa.planner import Plan
from kbqa.schemas import Answer
from kbqa.trace import Trace
from kbqa.live import LiveEngine, _numbers_in


class _Answerer:
    def __init__(self, texts: dict[str, str]) -> None:
        self.calls = 0
        self.retriever = SimpleNamespace(
            index=SimpleNamespace(
                docs_meta={doc_id: {} for doc_id in texts},
                texts=texts,
            )
        )
        self.facts = SimpleNamespace(
            rank=lambda query, doc_id, limit=1: [
                (1.0, SimpleNamespace(text=texts[doc_id]))
            ],
            cite=lambda doc_id, text: {"doc_id": doc_id, "quote": text},
        )

    def answer(self, plan, trace=None):
        self.calls += 1
        return Answer(answer="模板回退", answer_type="doc", notes=[])


class _Client:
    def __init__(self, replies: list):
        self.replies = list(replies)
        self.calls: list[dict] = []

    def chat_with_retry(self, messages, tools=None, budget=None, on_call=None):
        self.calls.append({"messages": list(messages), "tools": tools})
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def _plan() -> Plan:
    return Plan(
        question="供应商最后赔了多少钱？",
        standalone="供应商最后赔了多少钱？",
        search_query="供应商 赔付",
    )


def _tool_reply(name: str, params: dict, call_id: str) -> LLMReply:
    call = {
        "id": call_id,
        "type": "function",
        "function": {
            "name": name,
            "arguments": json.dumps(params, ensure_ascii=False),
        },
    }
    message = {"role": "assistant", "content": "", "tool_calls": [call]}
    return LLMReply(
        message=message,
        finish_reason="tool_calls",
        content="",
        tool_calls=[call],
        elapsed=0.0,
    )


def _text_reply(content: str) -> LLMReply:
    message = {"role": "assistant", "content": content}
    return LLMReply(
        message=message,
        finish_reason="stop",
        content=content,
        tool_calls=[],
        elapsed=0.0,
    )


def _engine(client, answerer, run_tool) -> LiveEngine:
    return LiveEngine(
        client=client,
        answerer=answerer,
        run_tool=run_tool,
        today="2026-09-01",
        data_period={"start": "2026-05-01", "end": "2026-08-31"},
    )


def test_numbers_in_excludes_date_components():
    text = "例如 2026-08-30、2026/8/30、2026 年 8 月 30 日、8 月 30 日，赔付 8,600.00 元。"

    assert _numbers_in(text) == [8600.0]


def test_example_date_without_document_source_does_not_trigger_fallback():
    answerer = _Answerer({"KB-013": "外卖订单在订单送达后 24 小时内可以申请退款。"})
    engine = LiveEngine.__new__(LiveEngine)
    engine.answerer = answerer
    trace = Trace(trace_id="t-date", question="退款时限怎么规定？")
    content = "例如 8 月 30 日的订单 9 月 1 日才退。[KB-013]"

    answer = engine._finalise(_plan(), content, [], {}, trace)

    assert "8 月 30 日" in answer.answer
    assert answerer.calls == 0


def test_date_example_does_not_hide_an_unmatched_number():
    answerer = _Answerer({"KB-013": "外卖订单在订单送达后 24 小时内可以申请退款。"})
    engine = LiveEngine.__new__(LiveEngine)
    engine.answerer = answerer
    trace = Trace(trace_id="t-bad-number", question="退款时限怎么规定？")
    content = "比如 8 月 30 日的订单赔付 9999 元。[KB-013]"

    answer = engine._finalise(_plan(), content, [], {}, trace)

    assert answer.answer == "模板回退"
    assert answerer.calls == 1


def test_repeated_tool_call_closes_out_with_collected_results():
    params = {"query": "三文鱼 赔付", "top_k": 5}
    client = _Client(
        [
            _tool_reply("search_kb", params, "call-1"),
            _tool_reply("search_kb", params, "call-2"),
            _text_reply("供应商最后赔付 8600 元。[KB-022]"),
        ]
    )
    answerer = _Answerer({"KB-022": "供应商赔付 8,600 元。"})
    run_calls = []

    def run_tool(name, args):
        run_calls.append((name, args))
        return {"results": [{"doc_id": "KB-022", "text": "供应商赔付 8,600 元。"}]}

    engine = _engine(client, answerer, run_tool)
    trace = Trace(trace_id="t-repeat", question="供应商最后赔了多少钱？")

    answer = engine.answer(_plan(), trace, [])

    assert len(run_calls) == 1
    assert len(client.calls) == 3
    assert client.calls[-1]["tools"] is None
    assert "8600" in answer.answer
    assert any(step["step"] == "tool_loop_repeat" for step in trace.steps)


def test_tool_round_limit_closes_out_without_raising(monkeypatch):
    monkeypatch.setattr(live, "MAX_TOOL_ROUNDS", 1)
    client = _Client(
        [
            _tool_reply("search_kb", {"query": "赔付"}, "call-1"),
            _text_reply("供应商最后赔付 8600 元。[KB-022]"),
        ]
    )
    answerer = _Answerer({"KB-022": "供应商赔付 8,600 元。"})
    engine = _engine(
        client,
        answerer,
        lambda name, args: {"results": [{"doc_id": "KB-022", "text": "供应商赔付 8,600 元。"}]},
    )
    trace = Trace(trace_id="t-limit", question="供应商最后赔了多少钱？")

    answer = engine.answer(_plan(), trace, [])

    assert len(client.calls) == 2
    assert client.calls[-1]["tools"] is None
    assert "8600" in answer.answer
    assert any(step["step"] == "tool_loop_limit" for step in trace.steps)


def test_close_out_failure_falls_back_to_template():
    params = {"query": "三文鱼 赔付", "top_k": 5}
    client = _Client(
        [
            _tool_reply("search_kb", params, "call-1"),
            _tool_reply("search_kb", params, "call-2"),
            LLMError("empty_content", "收口回答为空"),
        ]
    )
    answerer = _Answerer({"KB-022": "供应商赔付 8,600 元。"})
    engine = _engine(client, answerer, lambda name, args: {"results": []})
    trace = Trace(trace_id="t-fallback", question="供应商最后赔了多少钱？")

    answer = engine.answer(_plan(), trace, [])

    assert answer.answer == "模板回退"
    assert answerer.calls == 1
    assert any(step["step"] == "tool_loop_close_out_failed" for step in trace.steps)
