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
