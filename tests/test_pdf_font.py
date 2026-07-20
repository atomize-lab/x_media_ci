"""Tests for portable PDF font selection."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "tools" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

pdf_builder = importlib.import_module("make_article_pdf")


def test_cjk_font_falls_back_to_reportlab_cid_without_system_font(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CJK_FONT_PATH", raising=False)
    monkeypatch.setattr(pdf_builder.platform, "system", lambda: "Linux")
    monkeypatch.setattr(pdf_builder.os.path, "exists", lambda _path: False)

    font_name = pdf_builder.register_cjk_font()

    assert font_name == "STSong-Light"
    assert pdf_builder.pdfmetrics.getFont(font_name) is not None
