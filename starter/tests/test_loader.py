"""知识库加载回归测试：多格式、编码和 HTML 可见正文。"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from kbqa.loader import SUPPORTED_SUFFIXES, decode_bytes, load_document, load_knowledge_base


def test_supported_suffixes_include_md_txt_and_html():
    assert {".md", ".markdown", ".txt", ".html"} <= SUPPORTED_SUFFIXES


def test_gb18030_fallback_decodes_txt_without_mojibake(tmp_path):
    text = (
        "==================================================\n"
        "合味餐饮管理（上海）有限公司   OA 公文系统   导出文件\n"
        "导出时间：2026-08-12 09:41:07\n"
        "\n"
        "标题：关于 Super Souper 门店营业时间调整的通知\n"
        "\n"
        "自 2026 年 8 月 15 日起生效。\n"
    )
    path = tmp_path / "KB-062_旧OA导出.txt"
    path.write_bytes(text.encode("gb18030"))

    warnings: list[str] = []
    assert decode_bytes(path.read_bytes(), path, warnings) == text

    document = load_document(path)
    assert document is not None
    assert document.title == "关于 Super Souper 门店营业时间调整的通知"
    assert document.effective_from == date(2026, 8, 15)


def test_txt_title_and_effective_date_come_from_body(tmp_path):
    path = tmp_path / "KB-022_供应商邮件.txt"
    path.write_text(
        "Salmon Incident Report\n\n"
        "Effective date: 2026-07-03\n\n"
        "The supplier rejected the shipment.\n",
        encoding="utf-8",
    )

    document = load_document(path)
    assert document is not None
    assert document.title == "Salmon Incident Report"
    assert document.effective_from == date(2026, 7, 3)


def test_html_is_not_indexed_as_markup(tmp_path):
    path = tmp_path / "KB-061_常见问题FAQ.html"
    path.write_text(
        """
        <html>
          <head>
            <title>常见问题 FAQ</title>
            <style>.hidden { content: "STYLE-SHOULD-NOT-APPEAR"; }</style>
            <script>const secret = "SCRIPT-SHOULD-NOT-APPEAR";</script>
          </head>
          <body>
            <h1>退款说明</h1>
            <p>外卖订单在送达后 <strong>24 小时</strong>内可以申请退款。</p>
          </body>
        </html>
        """,
        encoding="utf-8",
    )

    document = load_document(path)
    assert document is not None
    assert document.title == "常见问题 FAQ"
    assert "24 小时" in document.text
    assert "<" not in document.text
    assert "STYLE-SHOULD-NOT-APPEAR" not in document.text
    assert "SCRIPT-SHOULD-NOT-APPEAR" not in document.text


def test_load_knowledge_base_accepts_txt_and_html(tmp_path):
    (tmp_path / "KB-001_test.md").write_text(
        "---\ndoc_id: KB-001\ntitle: Markdown\n---\n正文\n",
        encoding="utf-8",
    )
    (tmp_path / "KB-002_test.txt").write_text("文本标题\n正文\n", encoding="utf-8")
    (tmp_path / "KB-003_test.html").write_text(
        "<html><head><title>HTML 标题</title></head><body>正文</body></html>",
        encoding="utf-8",
    )

    documents, warnings = load_knowledge_base(tmp_path)

    assert {document.doc_id for document in documents} == {"KB-001", "KB-002", "KB-003"}
    assert warnings == []
