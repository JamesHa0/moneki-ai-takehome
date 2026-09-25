"""文档版本状态持久化与生效版本过滤。"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace

from kbqa.aliases import AliasTable
from kbqa.chunker import Chunk
from kbqa.docfacts import DocFacts
from kbqa.index import BM25Index
from kbqa.loader import Document
from kbqa.retriever import Retriever

ORIGINAL_SEARCH = Retriever.search


def _document(tmp_path: Path, doc_id: str, status: str, effective: date, superseded: str | None = None):
    return Document(
        doc_id=doc_id,
        title=doc_id,
        text="alpha alpha",
        path=tmp_path / (doc_id + ".md"),
        fmt="md",
        status=status,
        effective_from=effective,
        superseded_by=superseded,
    )


def test_document_meta_uses_status_key(tmp_path):
    document = _document(tmp_path, "KB-001", "已废止", date(2025, 1, 1), "KB-002")

    assert document.meta()["status"] == "已废止"


def test_retriever_filters_superseded_document_from_serialized_meta(tmp_path):
    old = _document(tmp_path, "KB-001", "已废止", date(2025, 1, 1), "KB-002")
    current = _document(tmp_path, "KB-002", "现行", date(2026, 5, 1))
    chunks = [
        Chunk("KB-001", "KB-001#1", "alpha alpha", "alpha alpha", "旧版"),
        Chunk("KB-002", "KB-002#1", "alpha alpha", "alpha alpha", "现行版"),
    ]
    index = BM25Index(
        chunks=chunks,
        docs_meta={old.doc_id: old.meta(), current.doc_id: current.meta()},
        aliases=AliasTable(),
        key="test",
        texts={old.doc_id: old.text, current.doc_id: current.text},
    )
    retriever = Retriever(index, date(2026, 9, 1))

    result = ORIGINAL_SEARCH(retriever, "alpha", top_k=2)

    assert any(item["doc_id"] == "KB-001" for item in result.filtered)
    assert all(hit.doc_id != "KB-001" for hit in result.hits)


def test_version_note_accepts_legacy_state_key():
    facts = DocFacts(SimpleNamespace())
    note = facts.version_note(
        {
            "state": "已废止",
            "effective_from": "2025-01-01",
            "superseded_by": "KB-002",
        }
    )

    assert "已废止" in note
    assert "KB-002" in note
