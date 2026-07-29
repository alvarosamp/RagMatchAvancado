from __future__ import annotations

import re
from collections import Counter, defaultdict
from io import BytesIO
from typing import TYPE_CHECKING, Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

if TYPE_CHECKING:
    from app.db.models import AnalysisDocument


BLUE = colors.HexColor("#1F3F68")
BLUE_LIGHT = colors.HexColor("#EAF1F8")
TEXT = colors.HexColor("#111827")
MUTED = colors.HexColor("#64748B")
BORDER = colors.HexColor("#D9E0EA")
SURFACE = colors.HexColor("#F6F8FB")
RED = colors.HexColor("#B91C1C")
GREEN = colors.HexColor("#047857")
PAGE_SIZE = landscape(A4)
CONTENT_WIDTH = 27.7 * cm


def export_analysis_pdf(document: "AnalysisDocument") -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=PAGE_SIZE,
        rightMargin=1.0 * cm,
        leftMargin=1.0 * cm,
        topMargin=1.0 * cm,
        bottomMargin=1.0 * cm,
        title=f"BI Editais - Analise {document.id}",
    )
    styles = _styles()
    story: list[Any] = []
    result = document.result or {}
    edital = result.get("edital") or {}
    items = list(document.items or [])
    total_units = sum(float(item.quantity or 0) for item in items)
    total_value = sum(float(item.total_value or 0) for item in items)
    risk_count = sum(1 for item in items if item.has_risco)
    categories = Counter(_text(item.categoria) or "N/C" for item in items)

    story.extend(_cover(styles, document, edital, items, total_units, total_value, risk_count, categories))
    story.append(Spacer(1, 0.35 * cm))
    story.extend(_category_summary(styles, items))
    story.append(PageBreak())
    story.extend(_items_section(styles, items))
    story.append(PageBreak())
    story.extend(_documents_section(styles, result))

    doc.build(story, onFirstPage=_page_footer, onLaterPages=_page_footer)
    return buffer.getvalue()


def export_analysis_report_pdf(
    documents: list["AnalysisDocument"],
    *,
    period_label: str,
    generated_at: str,
) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=PAGE_SIZE,
        rightMargin=1.0 * cm,
        leftMargin=1.0 * cm,
        topMargin=1.0 * cm,
        bottomMargin=1.0 * cm,
        title=f"BI Editais - Relatorio {period_label}",
    )
    styles = _styles()
    story: list[Any] = []
    items = [item for document in documents for item in list(document.items or [])]
    total_units = sum(float(item.quantity or 0) for item in items)
    total_value = sum(float(item.total_value or 0) for item in items)
    risk_docs = sum(1 for document in documents if _document_has_risk(document))
    me_epp_docs = sum(1 for document in documents if _document_has_me_epp(document))
    categories = Counter(_text(item.categoria) or "N/C" for item in items)

    story.extend(_report_cover(styles, period_label, generated_at, documents, items, total_units, total_value, risk_docs, me_epp_docs))
    story.append(Spacer(1, 0.35 * cm))
    story.extend(_category_summary(styles, items))
    story.append(PageBreak())
    story.extend(_report_documents_section(styles, documents, categories))
    story.append(PageBreak())
    story.extend(_items_section(styles, items[:300]))

    doc.build(story, onFirstPage=_page_footer, onLaterPages=_page_footer)
    return buffer.getvalue()


def _styles() -> dict[str, ParagraphStyle]:
    sample = getSampleStyleSheet()
    return {
        "eyebrow": ParagraphStyle(
            "eyebrow",
            parent=sample["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=MUTED,
            uppercase=True,
            spaceAfter=4,
        ),
        "title": ParagraphStyle(
            "title",
            parent=sample["Title"],
            fontName="Helvetica-Bold",
            fontSize=28,
            leading=32,
            textColor=TEXT,
            spaceAfter=8,
            alignment=TA_CENTER,
        ),
        "subtitle": ParagraphStyle(
            "subtitle",
            parent=sample["Normal"],
            fontSize=10,
            leading=14,
            textColor=MUTED,
            spaceAfter=10,
        ),
        "section": ParagraphStyle(
            "section",
            parent=sample["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=18,
            textColor=TEXT,
            spaceBefore=12,
            spaceAfter=8,
        ),
        "body": ParagraphStyle(
            "body",
            parent=sample["Normal"],
            fontSize=8,
            leading=10,
            textColor=TEXT,
        ),
        "small": ParagraphStyle(
            "small",
            parent=sample["Normal"],
            fontSize=7,
            leading=9,
            textColor=MUTED,
        ),
        "right": ParagraphStyle(
            "right",
            parent=sample["Normal"],
            fontSize=8,
            leading=10,
            textColor=TEXT,
            alignment=TA_RIGHT,
        ),
    }


def _cover(
    styles: dict[str, ParagraphStyle],
    document: AnalysisDocument,
    edital: dict[str, Any],
    items: list[Any],
    total_units: float,
    total_value: float,
    risk_count: int,
    categories: Counter,
) -> list[Any]:
    title = _text(edital.get("orgao")) or _text(document.source_name) or f"Analise #{document.id}"
    rows = [
        [Paragraph("BUSINESS INTELLIGENCE", styles["eyebrow"])],
        [Paragraph("Relatorio BI de Editais", styles["title"])],
        [_para(_line([title, edital.get("numero_pregao"), edital.get("uf"), edital.get("cidade")]), styles["subtitle"])],
    ]
    header = Table(rows, colWidths=[CONTENT_WIDTH])
    header.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), SURFACE),
                ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 14),
                ("RIGHTPADDING", (0, 0), (-1, -1), 14),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )

    kpis = [
        ("Itens mapeados", _num(len(items))),
        ("Unidades", _num(total_units)),
        ("Valor mapeado", _money(total_value)),
        ("Categorias", _num(len(categories))),
        ("Itens com risco", _num(risk_count)),
    ]
    kpi_table = Table(
        [[Paragraph(label, styles["small"]), Paragraph(value, styles["body"])] for label, value in kpis],
        colWidths=[4.0 * cm, 3.5 * cm],
    )
    kpi_table.setStyle(_plain_table_style())

    info_table = Table(
        [
            ["Data da disputa", _text(edital.get("data_disputa")) or "-"],
            ["Hora", _text(edital.get("hora_disputa")) or "-"],
            ["Criterio", _text(edital.get("criterio")) or "-"],
            ["Portal", _text(edital.get("local")) or "-"],
            ["UASG", _text(edital.get("uasg")) or "-"],
            ["ME/EPP", _text(edital.get("exclusividade_me_epp")) or "-"],
            ["Validade proposta", _text(edital.get("validade_proposta")) or "-"],
            ["Fonte", _text(document.source_name) or "-"],
        ],
        colWidths=[3.6 * cm, 16.0 * cm],
    )
    info_table.setStyle(_plain_table_style())

    return [
        header,
        Spacer(1, 0.35 * cm),
        Paragraph("Visao geral", styles["section"]),
        Table([[kpi_table, info_table]], colWidths=[7.8 * cm, 19.9 * cm]),
    ]


def _category_summary(styles: dict[str, ParagraphStyle], items: list[Any]) -> list[Any]:
    story: list[Any] = [Paragraph("Resumo por categoria", styles["section"])]
    grouped: dict[str, list[Any]] = defaultdict(list)
    for item in items:
        grouped[_text(item.categoria) or "N/C"].append(item)

    if not grouped:
        story.append(Paragraph("Nenhum item elegivel listado.", styles["body"]))
        return story

    data = [["Categoria", "Itens", "Unidades", "Valor mapeado", "Principais UFs"]]
    for category, rows in sorted(grouped.items(), key=lambda entry: (-sum(float(i.quantity or 0) for i in entry[1]), entry[0])):
        ufs = Counter(_text(item.uf) or "N/C" for item in rows)
        data.append(
            [
                _para(category, styles["body"]),
                _num(len(rows)),
                _num(sum(float(item.quantity or 0) for item in rows)),
                _money(sum(float(item.total_value or 0) for item in rows)),
                _para(", ".join(f"{uf} ({_num(count)})" for uf, count in ufs.most_common(4)), styles["body"]),
            ]
        )

    table = Table(data, colWidths=[5.5 * cm, 2.2 * cm, 2.6 * cm, 4.0 * cm, 13.4 * cm], repeatRows=1)
    table.setStyle(_grid_table_style())
    story.append(table)

    for category, rows in list(grouped.items())[:4]:
        breakdown = _breakdown_rows(rows)
        if not breakdown:
            continue
        story.append(Spacer(1, 0.25 * cm))
        story.append(KeepTogether([_para(category, styles["section"]), _breakdown_table(styles, breakdown)]))
    return story


def _report_cover(
    styles: dict[str, ParagraphStyle],
    period_label: str,
    generated_at: str,
    documents: list["AnalysisDocument"],
    items: list[Any],
    total_units: float,
    total_value: float,
    risk_docs: int,
    me_epp_docs: int,
) -> list[Any]:
    rows = [
        [Paragraph("BUSINESS INTELLIGENCE", styles["eyebrow"])],
        [Paragraph("Relatorio BI de Editais", styles["title"])],
        [_para(f"Periodo: {period_label} - Gerado em {generated_at}", styles["subtitle"])],
    ]
    header = Table(rows, colWidths=[CONTENT_WIDTH])
    header.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), SURFACE),
                ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 14),
                ("RIGHTPADDING", (0, 0), (-1, -1), 14),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    kpis = [
        ("Editais", _num(len(documents))),
        ("Itens mapeados", _num(len(items))),
        ("Unidades", _num(total_units)),
        ("Valor mapeado", _money(total_value)),
        ("Editais com risco", _num(risk_docs)),
        ("Com ME/EPP", _num(me_epp_docs)),
    ]
    kpi_table = Table(
        [[Paragraph(label, styles["small"]), Paragraph(value, styles["body"])] for label, value in kpis],
        colWidths=[4.4 * cm, 4.1 * cm],
    )
    kpi_table.setStyle(_plain_table_style())
    return [header, Spacer(1, 0.35 * cm), Paragraph("Visao geral", styles["section"]), kpi_table]


def _report_documents_section(
    styles: dict[str, ParagraphStyle],
    documents: list["AnalysisDocument"],
    categories: Counter,
) -> list[Any]:
    story: list[Any] = [Paragraph("Editais do periodo", styles["section"])]
    if categories:
        category_rows = [["Categoria", "Itens"]]
        for category, count in categories.most_common(12):
            category_rows.append([_para(category, styles["body"]), _num(count)])
        category_table = Table(category_rows, colWidths=[21.7 * cm, 6.0 * cm], repeatRows=1)
        category_table.setStyle(_grid_table_style())
        story.append(category_table)
        story.append(Spacer(1, 0.35 * cm))

    data = [["Edital", "Orgao", "UF", "Disputa", "Itens", "Unidades", "Valor", "Status"]]
    for document in documents:
        result = document.result or {}
        edital = result.get("edital") or {}
        items = list(document.items or [])
        data.append(
            [
                _para(_text(edital.get("numero_pregao")) or _text(document.source_name) or f"#{document.id}", styles["body"], 60),
                _para(edital.get("orgao"), styles["body"], 80),
                _para(edital.get("uf"), styles["body"]),
                _para(edital.get("data_disputa"), styles["body"], 35),
                _num(len(items)),
                _num(sum(float(item.quantity or 0) for item in items)),
                _money(sum(float(item.total_value or 0) for item in items)),
                _para("Risco" if _document_has_risk(document) else "Sem risco", styles["body"]),
            ]
        )
    if len(data) == 1:
        data.append(["-", "Nenhum edital encontrado no periodo.", "-", "-", "-", "-", "-", "-"])
    table = Table(
        data,
        colWidths=[3.6 * cm, 7.0 * cm, 1.3 * cm, 2.6 * cm, 1.6 * cm, 2.2 * cm, 3.4 * cm, 6.0 * cm],
        repeatRows=1,
    )
    table.setStyle(_grid_table_style())
    story.append(table)
    return story


def _items_section(styles: dict[str, ParagraphStyle], items: list[Any]) -> list[Any]:
    story = [Paragraph("Relacao de itens", styles["section"])]
    data = [["Item", "Lote", "Categoria", "Descricao resumida", "Classificacao", "Prazo", "Qtd", "Preco unit.", "Valor total"]]
    for item in sorted(items, key=_item_sort_key):
        raw = item.raw_payload or {}
        data.append(
            [
                _para(item.item_number, styles["body"]),
                _para(getattr(item, "lote_grupo", None) or raw.get("lote_grupo"), styles["body"], 18),
                _para(item.categoria, styles["body"]),
                _para(item.description, styles["body"], 170),
                _para(_item_classification(item), styles["body"], 125),
                _para(item.prazo_entrega or raw.get("prazo_entrega"), styles["body"], 45),
                Paragraph(_num(item.quantity), styles["right"]),
                Paragraph(_money(item.unit_value or raw.get("preco_unitario")), styles["right"]),
                Paragraph(_money(item.total_value or raw.get("valor_total_item")), styles["right"]),
            ]
        )
    table = Table(
        data,
        colWidths=[
            1.2 * cm,
            1.6 * cm,
            2.5 * cm,
            7.1 * cm,
            5.0 * cm,
            2.4 * cm,
            1.2 * cm,
            3.0 * cm,
            3.7 * cm,
        ],
        repeatRows=1,
    )
    table.setStyle(_grid_table_style())
    story.append(table)
    return story


def _documents_section(styles: dict[str, ParagraphStyle], result: dict[str, Any]) -> list[Any]:
    story = [Paragraph("Documentacao, declaracoes e riscos", styles["section"])]
    docs = result.get("documentacao") or []
    doc_rows = [["Categoria", "Documento"]]
    for doc in docs:
        doc_rows.append([_text(doc.get("categoria")) or "-", _para(doc.get("documento"), styles["body"])])
    if len(doc_rows) == 1:
        doc_rows.append(["-", "Nenhum documento listado."])
    table = Table(doc_rows, colWidths=[6.0 * cm, 21.7 * cm], repeatRows=1)
    table.setStyle(_grid_table_style())
    story.append(table)

    story.append(Spacer(1, 0.35 * cm))
    riscos = result.get("riscos") or {}
    risco_rows = [["Tipo", "Status", "Observacao"]]
    risco_rows.append(["Geral", _text(riscos.get("risco_identificado")) or "Nenhum", _text(riscos.get("observacao")) or "-"])
    for key in ("risco_operacional", "risco_documental"):
        value = riscos.get(key) or {}
        motivos = value.get("motivos") or []
        risco_rows.append([key.replace("_", " ").title(), "Existe" if value.get("existe") else "Nao existe", _para("; ".join(map(str, motivos)), styles["body"])])
    risk_table = Table(risco_rows, colWidths=[5.5 * cm, 3.5 * cm, 18.7 * cm], repeatRows=1)
    risk_table.setStyle(_grid_table_style())
    story.append(risk_table)

    declaracoes = result.get("declaracoes") or []
    if declaracoes:
        story.append(Spacer(1, 0.35 * cm))
        dec_rows = [["Declaracoes exigidas"]]
        for item in declaracoes:
            dec_rows.append([_para(item.get("declaracao"), styles["body"])])
        dec_table = Table(dec_rows, colWidths=[27.7 * cm], repeatRows=1)
        dec_table.setStyle(_grid_table_style())
        story.append(dec_table)
    return story


def _breakdown_rows(rows: list[Any]) -> list[tuple[str, str, float]]:
    counters: dict[str, Counter] = defaultdict(Counter)
    for item in rows:
        bi = item.caracteristicas_bi or {}
        for key, value in bi.items():
            text = _text(value)
            if text and text.upper() != "N/C":
                counters[key.replace("_", " ").title()][text] += float(item.quantity or 0) or 1
    output: list[tuple[str, str, float]] = []
    for key, counter in counters.items():
        for label, value in counter.most_common(3):
            output.append((key, label, value))
    return output[:12]


def _breakdown_table(styles: dict[str, ParagraphStyle], rows: list[tuple[str, str, float]]) -> Table:
    data = [["Atributo", "Valor", "Unidades"]]
    data.extend([[attr, _para(value, styles["body"]), _num(total)] for attr, value, total in rows])
    table = Table(data, colWidths=[6.0 * cm, 17.7 * cm, 4.0 * cm], repeatRows=1)
    table.setStyle(_grid_table_style())
    return table


def _plain_table_style() -> TableStyle:
    return TableStyle(
        [
            ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
            ("INNERGRID", (0, 0), (-1, -1), 0.3, BORDER),
            ("BACKGROUND", (0, 0), (-1, -1), colors.white),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ("TEXTCOLOR", (0, 0), (0, -1), MUTED),
            ("TEXTCOLOR", (1, 0), (1, -1), TEXT),
            ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
        ]
    )


def _grid_table_style() -> TableStyle:
    return TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), BLUE),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 6.8),
            ("LEADING", (0, 0), (-1, -1), 8.2),
            ("GRID", (0, 0), (-1, -1), 0.35, BORDER),
            ("BACKGROUND", (0, 1), (-1, -1), colors.white),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BLUE_LIGHT]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]
    )


def _page_footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(doc.leftMargin, 0.75 * cm, PAGE_SIZE[0] - doc.rightMargin, 0.75 * cm)
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(MUTED)
    canvas.drawString(doc.leftMargin, 0.45 * cm, "Categorizacao automatica - revisao recomendada")
    canvas.drawRightString(PAGE_SIZE[0] - doc.rightMargin, 0.45 * cm, f"Pagina {doc.page}")
    canvas.restoreState()


def _item_classification(item: Any) -> str:
    technical = _text(getattr(item, "caracteristicas_tecnicas", None))
    if technical:
        return technical
    bi = item.caracteristicas_bi or {}
    values = [str(value) for value in bi.values() if value and str(value).upper() != "N/C"]
    return " - ".join(values) or _text(item.item_type) or "-"


def _item_sort_key(item: Any) -> tuple[int, str, int]:
    text = _text(getattr(item, "item_number", None))
    match = re.search(r"\d+", text)
    if match:
        return (0, f"{int(match.group()):010d}", int(getattr(item, "id", 0) or 0))
    return (1, text, int(getattr(item, "id", 0) or 0))


def _document_has_risk(document: "AnalysisDocument") -> bool:
    riscos = (document.result or {}).get("riscos") or {}
    value = _text(riscos.get("risco_identificado"))
    if value and value.lower() not in ("nenhum", "sem risco", "nao existe", "não existe"):
        return True
    for key in ("risco_operacional", "risco_documental"):
        field = riscos.get(key) or {}
        if isinstance(field, dict) and field.get("existe"):
            return True
    return False


def _document_has_me_epp(document: "AnalysisDocument") -> bool:
    edital = (document.result or {}).get("edital") or {}
    value = _text(edital.get("exclusividade_me_epp"))
    return bool(value and value.lower() not in ("ampla concorrencia", "ampla concorrência", "nao", "não", "n/c"))


def _line(values: list[Any]) -> str:
    return " - ".join(_text(value) for value in values if _text(value)) or "-"


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _para(value: Any, style: ParagraphStyle, limit: int | None = None) -> Paragraph:
    text = _short(value, limit) if limit else _text(value)
    return Paragraph(escape(text or "-"), style)


def _short(value: str, limit: int) -> str:
    text = _text(value).replace("\n", " ")
    return text if len(text) <= limit else f"{text[:limit - 3]}..."


def _num(value: Any) -> str:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        return "-"
    if number.is_integer():
        return f"{int(number):,}".replace(",", ".")
    return f"{number:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _money(value: Any) -> str:
    if value in (None, ""):
        return "-"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "-"
    return "R$ " + f"{number:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
