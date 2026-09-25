"""重建命令与索引缓存：契约 §8「索引必须能感知知识库的变化」。

这些测试在修复前都是红的 —— 先让它们红，再动手。
"""

from __future__ import annotations

from types import SimpleNamespace

from kbqa import rebuild
from kbqa.index import content_key


def _write_doc(kb_dir, doc_id, body):
    (kb_dir / ("%s_测试.md" % doc_id)).write_text(
        "---\ndoc_id: %s\ntitle: %s\n---\n\n%s\n" % (doc_id, doc_id, body),
        encoding="utf-8",
    )


def test_content_key_tracks_knowledge_base_content(tmp_path):
    """知识库加了一篇文档，缓存键必须跟着变。

    现在它只哈希三个版本号字符串，和知识库内容无关 —— 所以换库、加文档、
    改文档都不会让缓存失效。
    """
    kb = tmp_path / "kb"
    kb.mkdir()
    _write_doc(kb, "KB-001", "第一篇的内容")
    before = content_key(kb)

    _write_doc(kb, "KB-002", "第二篇的内容")
    after = content_key(kb)

    assert after != before, "知识库内容变了，缓存键却没变（契约 §8）"


def test_content_key_tracks_existing_document_changes(tmp_path):
    """同一个文件原地改内容也必须换缓存键。

    只把相对路径纳入摘要不够，正文变化同样会让旧索引过期。
    修改前后正文等长，避免“只哈希文件大小”也能误过。
    """
    kb = tmp_path / "kb"
    kb.mkdir()
    _write_doc(kb, "KB-001", "第一篇内容")
    before = content_key(kb)

    _write_doc(kb, "KB-001", "第一篇正文")
    after = content_key(kb)

    assert after != before, "同一路径的正文变了，缓存键却没变（契约 §8）"


def test_rebuild_command_forces_index_rebuild(tmp_path, monkeypatch):
    """重建命令必须真的重算索引，不能因为缓存键匹配就直接读缓存。

    rebuild.py 现在调的是 load_index(kb_dir, index_path)，rebuild 参数取默认值
    False；而 load_index 见缓存键匹配就把缓存文件原样返回。
    """
    captured = {}

    def fake_load_index(kb_dir, path, rebuild=False):
        captured["rebuild"] = rebuild
        return SimpleNamespace(docs_meta={}, chunks=[], key="0" * 12, warnings=[])

    monkeypatch.setattr(
        rebuild,
        "load_settings",
        lambda: SimpleNamespace(
            data_dir=tmp_path / "data",
            kb_dir=tmp_path / "kb",
            clean_db=tmp_path / "var" / "clean.db",
            source_db=tmp_path / "data" / "pos.db",
            index_path=tmp_path / "index.json",
        ),
    )
    # 不碰真实数据库
    monkeypatch.setattr(
        rebuild, "build_clean_db", lambda source, target: SimpleNamespace(as_dict=lambda: {})
    )
    monkeypatch.setattr(rebuild, "load_index", fake_load_index)

    rebuild.main()

    assert captured["rebuild"] is True, "重建命令没有强制重建索引，吃的是缓存"
