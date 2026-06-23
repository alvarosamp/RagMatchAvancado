from __future__ import annotations

from pathlib import Path


def test_parse_pdf_fallback_uses_pypdf_when_docling_missing(monkeypatch):
    # Forca o caminho "sem docling" e garante que ainda extraimos texto.
    monkeypatch.setenv("DOCLING_PYPDF_FIRST", "1")
    monkeypatch.setenv("DOCLING_PYPDF_MIN_CHARS", "1")

    from app.pipeline.docling_parser import parse_pdf

    pdf_path = Path("data/editais/UFBA.pdf")
    doc = parse_pdf(pdf_path, filename=pdf_path.name)

    assert "PREGÃO" in doc.full_text.upper() or "PREGAO" in doc.full_text.upper()
    assert len(doc.full_text.strip()) > 0

