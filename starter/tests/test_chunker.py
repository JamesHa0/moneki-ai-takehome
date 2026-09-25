"""文档切块回归测试：chunk 必须覆盖正文结尾。"""

from __future__ import annotations

from pathlib import Path

from kbqa.chunker import CHUNK_SIZE, chunk_document
from kbqa.loader import Document


def test_all_chunks_cover_the_end_of_document(tmp_path: Path):
    tail = "TAIL-MUST-BE-INDEXED"
    text = "甲" * (CHUNK_SIZE * 2 + 17) + tail
    document = Document(
        doc_id="KB-999",
        title="长文",
        text=text,
        path=tmp_path / "KB-999_长文.md",
        fmt="md",
    )

    chunks = chunk_document(document)
    reconstructed = "".join(chunk.source_text for chunk in chunks)

    assert reconstructed == text
    assert reconstructed.endswith(tail)
