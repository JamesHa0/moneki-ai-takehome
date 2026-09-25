"""检索结果不变式：doc_id 必须与 chunk_id 指向同一篇文档。"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from kbqa.aliases import AliasTable
from kbqa.chunker import Chunk
from kbqa.index import BM25Index
from kbqa.retriever import Retriever

ORIGINAL_SEARCH = Retriever.search


def test_hit_doc_id_matches_chunk_id_prefix():
    chunks = [
        Chunk("KB-001", "KB-001#1", "alpha alpha", "alpha alpha", "第一篇"),
        Chunk("KB-001", "KB-001#2", "alpha alpha", "alpha alpha", "第一篇"),
        Chunk("KB-002", "KB-002#1", "alpha alpha", "alpha alpha", "第二篇"),
    ]
    index = BM25Index(
        chunks=chunks,
        docs_meta={"KB-001": {"title": "第一篇"}, "KB-002": {"title": "第二篇"}},
        aliases=AliasTable(),
        key="test",
        texts={"KB-001": "alpha alpha", "KB-002": "alpha alpha"},
    )
    retriever = Retriever(index, date(2026, 9, 1))

    result = ORIGINAL_SEARCH(retriever, "alpha", top_k=2)

    assert len(result.hits) == 2
    assert {hit.doc_id for hit in result.hits} == {"KB-001", "KB-002"}
    for hit in result.hits:
        assert hit.doc_id == hit.chunk_id.split("#", 1)[0]
