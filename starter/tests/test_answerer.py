"""文档回答模板的对外答案必须受长度上限约束。"""

from __future__ import annotations

from types import SimpleNamespace

from kbqa.answerer import Answerer
from kbqa.chunker import Chunk
from kbqa.planner import Plan
from kbqa.retriever import Hit, SearchResult

MAX_ANSWER_CHARS = 1200


def test_doc_fallback_does_not_append_full_document():
    long_text = "长文档正文。" * 500
    hit = Hit(
        doc_id="KB-999",
        chunk_id="KB-999#1",
        score=42.0,
        text=long_text[:300],
        source_text=long_text[:300],
        meta={"title": "长文档", "status": "现行"},
    )
    result = SearchResult(
        hits=[hit],
        query="长文档",
        terms=[],
        expansions=[],
        filtered=[],
        coverage=1.0,
    )
    body = "筛选后的短答案。"
    citation = {"doc_id": "KB-999", "quote": body}

    answerer = Answerer.__new__(Answerer)
    answerer.retriever = SimpleNamespace(
        index=SimpleNamespace(
            chunks_of=lambda doc_id: [
                Chunk(
                    doc_id=doc_id,
                    chunk_id=doc_id + "#1",
                    text=long_text,
                    source_text=long_text,
                )
            ]
        )
    )
    answerer.facts = SimpleNamespace(vocab_coverage=lambda text: 1.0)
    answerer._search = lambda plan, trace=None: result
    answerer._doc_block = lambda plan, search_result: (body, [citation], 1.0)

    plan = Plan(question="长文档怎么规定？", standalone="长文档怎么规定？", search_query="长文档")
    answer = answerer._answer_doc(plan)

    assert answer.answer_type == "doc"
    assert long_text not in answer.answer
    assert len(answer.answer) <= MAX_ANSWER_CHARS


def test_doc_block_sorts_candidates_by_score_descending():
    low = {
        "score": 0.1,
        "raw": 0.1,
        "doc_id": "KB-LOW",
        "meta": {"title": "低分文档", "effective_from": "2026-01-01"},
        "effective_from": "2026-01-01",
        "unit": SimpleNamespace(text="低分候选"),
        "sentence": "低分候选",
    }
    high = {
        "score": 0.9,
        "raw": 0.9,
        "doc_id": "KB-HIGH",
        "meta": {"title": "高分文档", "effective_from": "2026-01-01"},
        "effective_from": "2026-01-01",
        "unit": SimpleNamespace(text="高分候选"),
        "sentence": "高分候选",
    }
    answerer = Answerer.__new__(Answerer)
    answerer._candidates = lambda plan, result, require_value: [low, high]
    answerer.facts = SimpleNamespace(
        cite=lambda doc_id, text: {"doc_id": doc_id, "quote": text},
        render=lambda doc_id, text: text,
        version_note=lambda meta: "",
        extend_to_cause=lambda unit: unit,
    )
    answerer.retriever = SimpleNamespace(
        index=SimpleNamespace(docs_meta={})
    )
    plan = Plan(question="测试问题", standalone="测试问题", search_query="测试问题")
    result = SearchResult(
        hits=[],
        query="测试问题",
        terms=[],
        expansions=[],
        filtered=[],
        coverage=1.0,
    )

    _, citations, _ = answerer._doc_block(plan, result)

    assert citations[0]["doc_id"] == "KB-HIGH"
