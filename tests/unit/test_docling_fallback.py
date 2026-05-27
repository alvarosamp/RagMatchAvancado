from __future__ import annotations

import os
from io import BytesIO

from reportlab.pdfgen import canvas


def _make_pdf_bytes(text: str) -> bytes:
    buf = BytesIO()
    c = canvas.Canvas(buf)
    c.setFont("Helvetica", 12)
    c.drawString(72, 720, text)
    c.showPage()
    c.save()
    return buf.getvalue()


def test_parse_pdf_fallback_uses_pypdf_when_docling_missing(monkeypatch):
    # Forca o caminho "sem docling" e garante que ainda extraimos texto.
    monkeypatch.setenv("DOCLING_PYPDF_FIRST", "1")
    monkeypatch.setenv("DOCLING_PYPDF_MIN_CHARS", "1")

    from app.pipeline.docling_parser import parse_pdf

    pdf_bytes = _make_pdf_bytes("EDITAL TESTE 123")
    doc = parse_pdf(pdf_bytes, filename="teste.pdf")

    assert "EDITAL" in doc.full_text.upper()
    assert len(doc.full_text.strip()) > 0

