from __future__ import annotations

import re
from io import BytesIO
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


TOR_RED = colors.HexColor("#9B0000")
TOR_RED_DARK = colors.HexColor("#780000")
TEXT = colors.HexColor("#111827")
MUTED = colors.HexColor("#667085")
BORDER = colors.HexColor("#D7DCE3")
SOFT = colors.HexColor("#F2F4F7")


def build_tor_datasheet_preview(
    extracted: dict[str, Any],
    *,
    pn_tor: str | None = None,
    category: str | None = None,
) -> dict[str, Any]:
    specs = extracted.get("specs") or {}
    raw_text = extracted.get("raw_text") or ""
    model = _clean(pn_tor) or _clean(extracted.get("model")) or _model_from_text(raw_text)
    categoria = _category_label(category or extracted.get("category") or _infer_category(model, specs, raw_text))
    title = _title_for(model, categoria, specs, raw_text)
    resumo = _summary_for(categoria, specs, raw_text)
    tags = _tags_for(categoria, specs, raw_text)

    return {
        "pn_tor": model,
        "categoria": categoria,
        "titulo": title,
        "resumo": resumo,
        "tags": tags,
        "caracteristicas": _features_for(categoria, specs, raw_text),
        "aplicacoes": _applications_for(categoria, specs, raw_text),
        "descricao": _description_for(model, categoria, specs, raw_text),
        "tabela_tecnica": _technical_table_for(categoria, specs, raw_text),
        "conformidades": _standards_for(categoria, specs, raw_text),
        "observacao_origem": "Dados tecnicos consolidados a partir do datasheet original do fabricante, com PN convertido para o padrao TOR.",
        "fonte": {
            "fabricante": _clean(extracted.get("manufacturer")) or "N/C",
            "modelo_original": _clean(extracted.get("model")) or "N/C",
        },
    }


def export_tor_datasheet_pdf(payload: dict[str, Any]) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.3 * cm,
        leftMargin=1.3 * cm,
        topMargin=1.0 * cm,
        bottomMargin=1.0 * cm,
        title=f"TOR - {payload.get('pn_tor') or 'Datasheet'}",
    )
    styles = _styles()
    story: list[Any] = []

    pn = _clean(payload.get("pn_tor")) or "PN TOR"
    title = _clean(payload.get("titulo")) or "Datasheet tecnico"
    resumo = _clean(payload.get("resumo"))
    tags = payload.get("tags") if isinstance(payload.get("tags"), list) else []

    story.extend(_hero(styles, pn, title, resumo, tags))
    story.append(Spacer(1, 0.35 * cm))
    story.extend(_two_column_opening(styles, payload))
    story.append(Spacer(1, 0.45 * cm))
    story.extend(_section_text(styles, "Descricao do Produto", payload.get("descricao")))
    story.append(Spacer(1, 0.35 * cm))
    story.extend(_technical_section(styles, payload))
    story.append(Spacer(1, 0.25 * cm))
    story.extend(_standards_section(styles, payload))

    doc.build(
        story,
        onFirstPage=lambda canvas, doc_obj: _footer(canvas, doc_obj, pn),
        onLaterPages=lambda canvas, doc_obj: _footer(canvas, doc_obj, pn),
    )
    return buffer.getvalue()


def _styles() -> dict[str, ParagraphStyle]:
    sample = getSampleStyleSheet()
    return {
        "brand": ParagraphStyle("brand", parent=sample["Normal"], fontName="Helvetica-Bold", fontSize=30, leading=34, textColor=TEXT, alignment=TA_RIGHT),
        "pn": ParagraphStyle("pn", parent=sample["Heading1"], fontName="Helvetica-Bold", fontSize=20, leading=24, textColor=TOR_RED_DARK, alignment=TA_CENTER),
        "title": ParagraphStyle("title", parent=sample["Heading2"], fontSize=16, leading=20, textColor=TOR_RED_DARK, alignment=TA_CENTER),
        "summary": ParagraphStyle("summary", parent=sample["Normal"], fontSize=11, leading=14, textColor=TEXT, alignment=TA_CENTER),
        "tag": ParagraphStyle("tag", parent=sample["Normal"], fontSize=8, leading=10, textColor=MUTED, alignment=TA_CENTER),
        "section": ParagraphStyle("section", parent=sample["Heading2"], fontName="Helvetica-Bold", fontSize=13, leading=16, textColor=colors.white, alignment=TA_CENTER),
        "body": ParagraphStyle("body", parent=sample["Normal"], fontSize=8.5, leading=11.5, textColor=TEXT),
        "small": ParagraphStyle("small", parent=sample["Normal"], fontSize=7.5, leading=10, textColor=MUTED),
        "right": ParagraphStyle("right", parent=sample["Normal"], fontSize=8.5, leading=11, textColor=TEXT, alignment=TA_RIGHT),
    }


def _hero(styles: dict[str, ParagraphStyle], pn: str, title: str, resumo: str, tags: list[Any]) -> list[Any]:
    top_bar = Table([[""]], colWidths=[18.4 * cm], rowHeights=[0.45 * cm])
    top_bar.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), TOR_RED)]))

    product_box = Table(
        [
            [Paragraph("TOR", styles["brand"])],
            [Paragraph(escape(pn), styles["pn"])],
            [Paragraph(escape(title), styles["title"])],
            [Paragraph(escape(resumo or "-"), styles["summary"])],
            [Paragraph(escape(" | ".join(str(tag) for tag in tags if tag) or "-"), styles["tag"])],
        ],
        colWidths=[18.4 * cm],
    )
    product_box.setStyle(TableStyle([("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    return [top_bar, Spacer(1, 0.5 * cm), product_box]


def _two_column_opening(styles: dict[str, ParagraphStyle], payload: dict[str, Any]) -> list[Any]:
    features = payload.get("caracteristicas") if isinstance(payload.get("caracteristicas"), list) else []
    apps = payload.get("aplicacoes") if isinstance(payload.get("aplicacoes"), list) else []
    left = [
        _section_header(styles, "Caracteristicas do Produto", width=11.7 * cm),
        _bullet_table(styles, features),
    ]
    right = [
        _section_header(styles, "Aplicacoes", width=6.4 * cm),
        _red_box(styles, apps),
    ]
    return [Table([[left, right]], colWidths=[11.7 * cm, 6.4 * cm], hAlign="LEFT")]


def _section_text(styles: dict[str, ParagraphStyle], title: str, text: Any) -> list[Any]:
    return [_section_header(styles, title), Spacer(1, 0.18 * cm), Paragraph(escape(_clean(text) or "-"), styles["body"])]


def _technical_section(styles: dict[str, ParagraphStyle], payload: dict[str, Any]) -> list[Any]:
    rows = [["Parametro", "Especificacao"]]
    table_data = payload.get("tabela_tecnica") if isinstance(payload.get("tabela_tecnica"), dict) else {}
    for key, value in table_data.items():
        if _clean(value):
            rows.append([_label(key), Paragraph(escape(str(value)), styles["body"])])
    if len(rows) == 1:
        rows.append(["-", "-"])
    table = Table(rows, colWidths=[5.6 * cm, 12.5 * cm], repeatRows=1)
    table.setStyle(_grid_style())
    return [_section_header(styles, "Especificacoes Tecnicas"), Spacer(1, 0.18 * cm), table]


def _standards_section(styles: dict[str, ParagraphStyle], payload: dict[str, Any]) -> list[Any]:
    standards = payload.get("conformidades") if isinstance(payload.get("conformidades"), list) else []
    note = _clean(payload.get("observacao_origem"))
    parts = []
    if standards:
        parts.append(f"Interfaces e conformidades: {', '.join(str(item) for item in standards if item)}.")
    if note:
        parts.append(note)
    box = Table([[Paragraph(escape(" ".join(parts) or "-"), styles["small"])]], colWidths=[18.1 * cm])
    box.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), SOFT), ("BOX", (0, 0), (-1, -1), 0.4, SOFT), ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    return [box]


def _section_header(styles: dict[str, ParagraphStyle], title: str, *, width: float = 18.1 * cm) -> Table:
    table = Table([[Paragraph(escape(title), styles["section"])]], colWidths=[width])
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), TOR_RED_DARK), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    return table


def _bullet_table(styles: dict[str, ParagraphStyle], rows: list[Any]) -> Table:
    data = [[Paragraph("-", styles["body"]), Paragraph(escape(str(item)), styles["body"])] for item in rows if _clean(item)]
    if not data:
        data = [["", Paragraph("-", styles["body"])]]
    table = Table(data, colWidths=[0.5 * cm, 10.8 * cm])
    table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 2), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))
    return table


def _red_box(styles: dict[str, ParagraphStyle], rows: list[Any]) -> Table:
    data = [[Paragraph(escape(str(item)), styles["body"])] for item in rows if _clean(item)]
    if not data:
        data = [[Paragraph("-", styles["body"])]]
    table = Table(data, colWidths=[6.0 * cm])
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFF5F5")), ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#F0C6C6")), ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
    return table


def _grid_style() -> TableStyle:
    return TableStyle([("BACKGROUND", (0, 0), (-1, 0), TOR_RED_DARK), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 8), ("GRID", (0, 0), (-1, -1), 0.35, BORDER), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, SOFT]), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)])


def _footer(canvas, doc, pn: str) -> None:
    canvas.saveState()
    canvas.setStrokeColor(BORDER)
    canvas.line(doc.leftMargin, 0.75 * cm, A4[0] - doc.rightMargin, 0.75 * cm)
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(MUTED)
    canvas.drawString(doc.leftMargin, 0.45 * cm, f"TOR | {pn} | Especificacoes sujeitas a alteracoes sem aviso previo")
    canvas.drawRightString(A4[0] - doc.rightMargin, 0.45 * cm, f"Pagina {doc.page}")
    canvas.restoreState()


def _technical_table_for(categoria: str, specs: dict[str, Any], raw_text: str) -> dict[str, str]:
    fields = {
        "Formato": _pick(specs, "Formato", "Form factor", "Fator de forma") or _guess_format(raw_text),
        "Velocidade": _pick(specs, "Velocidade", "Data Rate", "Taxa de dados") or _find(raw_text, r"(\d+(?:[,.]\d+)?\s*(?:Gb/s|Gbps|G))"),
        "Alcance": _pick(specs, "Alcance", "Distance", "Reach") or _find(raw_text, r"(\d+(?:[,.]\d+)?\s*(?:km|m))"),
        "Fibra / meio": _pick(specs, "Fibra", "Tipo de fibra", "Media", "Meio") or _guess_media(raw_text),
        "Conector": _pick(specs, "Conector", "Connector") or _find(raw_text, r"(LC/UPC|LC|RJ45|MPO|MTP)"),
        "DDM": _pick(specs, "DDM", "Digital Diagnostics") or ("Sim" if re.search(r"\bDDM\b|diagnostico digital|digital diagnostic", raw_text, re.I) else ""),
        "Alimentacao": _pick(specs, "Alimentacao", "Power Requirement / Tensao de Entrada", "Voltage") or _find(raw_text, r"(\+?3[,.]3\s*V)"),
        "Consumo maximo": _pick(specs, "Consumo", "Power Consumption") or _find(raw_text, r"(\d+(?:[,.]\d+)?\s*W)"),
        "Temperatura de operacao": _pick(specs, "Temperatura", "Operating Temperature") or _find(raw_text, r"(-?\d+\s*°?\s*C\s*(?:a|to|\~|-)\s*\+?\d+\s*°?\s*C)"),
    }
    if categoria in {"Switch", "Access Point"}:
        fields.update({key: str(value) for key, value in specs.items() if _clean(value)})
    return {key: value for key, value in fields.items() if _clean(value)}


def _features_for(categoria: str, specs: dict[str, Any], raw_text: str) -> list[str]:
    if categoria in {"Transceiver", "Modulo optico"}:
        features = [
            _sentence("Links bidirecionais de ate", _technical_table_for(categoria, specs, raw_text).get("Velocidade")),
            _sentence("Fator de forma", _technical_table_for(categoria, specs, raw_text).get("Formato"), "com insercao a quente"),
            _sentence("Alcance de ate", _technical_table_for(categoria, specs, raw_text).get("Alcance")),
            _sentence("Conector optico", _technical_table_for(categoria, specs, raw_text).get("Conector")),
            _sentence("Alimentacao unica de", _technical_table_for(categoria, specs, raw_text).get("Alimentacao")),
        ]
        if re.search(r"\bRoHS\b", raw_text, re.I):
            features.append("Produto compativel com RoHS")
        if re.search(r"\bDDM\b|diagnostico digital|digital diagnostic", raw_text, re.I):
            features.append("Funcoes de diagnostico digital integradas")
        return [item for item in features if _clean(item)]
    return [f"{_label(key)}: {value}" for key, value in specs.items() if _clean(value)][:12]


def _applications_for(categoria: str, specs: dict[str, Any], raw_text: str) -> list[str]:
    text = raw_text.lower()
    apps = []
    for label, pattern in (
        ("100GBASE-LR4 Ethernet", r"100gbase|100g"),
        ("40GBASE Ethernet", r"40gbase|40g"),
        ("25GBASE-LR", r"25gbase|25g"),
        ("10GBASE Ethernet", r"10gbase|10g"),
        ("1000BASE Ethernet", r"1000base|1g"),
        ("CPRI", r"\bcpri\b"),
        ("Data center", r"data center|datacenter"),
    ):
        if re.search(pattern, text):
            apps.append(label)
    return apps[:5] or ["Redes corporativas", "Data center", "Infraestrutura de telecomunicacoes"]


def _description_for(model: str, categoria: str, specs: dict[str, Any], raw_text: str) -> str:
    table = _technical_table_for(categoria, specs, raw_text)
    if categoria in {"Transceiver", "Modulo optico"}:
        return (
            f"O {model} e um transceptor optico de alto desempenho para enlaces Ethernet"
            f"{_with_value(' de ate ', table.get('Velocidade'))}{_with_value(' e alcance de ate ', table.get('Alcance'))}."
            f" O modulo utiliza formato {table.get('Formato') or 'compativel'}, conector {table.get('Conector') or 'optico'}"
            f" e foi consolidado para aplicacao no padrao comercial TOR."
        )
    return f"O {model} e um equipamento de rede consolidado no padrao TOR, com especificacoes tecnicas revisadas a partir do datasheet original do fabricante."


def _title_for(model: str, categoria: str, specs: dict[str, Any], raw_text: str) -> str:
    if categoria in {"Transceiver", "Modulo optico"}:
        fmt = _guess_format(raw_text) or _pick(specs, "Formato")
        wavelength = _find(raw_text, r"(\d{3,4}\s*nm)")
        return " ".join(part for part in ["Transceptor", fmt, wavelength] if part) or model
    return model


def _summary_for(categoria: str, specs: dict[str, Any], raw_text: str) -> str:
    table = _technical_table_for(categoria, specs, raw_text)
    return " - ".join(part for part in [table.get("Velocidade"), table.get("Alcance")] if part) or "Especificacao tecnica TOR"


def _tags_for(categoria: str, specs: dict[str, Any], raw_text: str) -> list[str]:
    table = _technical_table_for(categoria, specs, raw_text)
    return [item for item in [table.get("Conector"), table.get("Fibra / meio"), table.get("DDM") and "DDM"] if item]


def _standards_for(categoria: str, specs: dict[str, Any], raw_text: str) -> list[str]:
    standards = []
    for pattern in (r"SFP28 MSA", r"QSFP28 MSA", r"SFF-\d+", r"IEEE\s+802\.[A-Za-z0-9.]+", r"RoHS(?:-\d)?"):
        standards.extend(re.findall(pattern, raw_text, flags=re.I))
    return list(dict.fromkeys(item.upper().replace("IEEE ", "IEEE ") for item in standards))[:8]


def _category_label(value: str) -> str:
    folded = _clean(value).lower().replace("_", " ")
    if "access" in folded:
        return "Access Point"
    if "switch" in folded:
        return "Switch"
    if "modulo" in folded or "module" in folded:
        return "Modulo optico"
    if "transceiver" in folded or "transceptor" in folded or "sfp" in folded or "qsfp" in folded:
        return "Transceiver"
    return "Outro"


def _infer_category(model: str, specs: dict[str, Any], raw_text: str) -> str:
    haystack = f"{model} {jsonish(specs)} {raw_text[:1000]}"
    return _category_label(haystack)


def _guess_format(text: str) -> str:
    for fmt in ("QSFP28", "QSFP+", "SFP28", "SFP+", "SFP"):
        if re.search(re.escape(fmt), text, re.I):
            return fmt
    return ""


def _guess_media(text: str) -> str:
    if re.search(r"monomodo|single.?mode|\bSMF\b", text, re.I):
        return "SMF"
    if re.search(r"multimodo|multi.?mode|\bMMF\b", text, re.I):
        return "MMF"
    if re.search(r"RJ45|cobre|copper", text, re.I):
        return "RJ45"
    return ""


def _model_from_text(text: str) -> str:
    first = next((line.strip() for line in text.splitlines() if line.strip()), "")
    return re.sub(r"[^A-Za-z0-9+_.-]", "", first)[:48] or "PN-TOR"


def _pick(specs: dict[str, Any], *names: str) -> str:
    folded = {_fold(key): value for key, value in specs.items()}
    for name in names:
        direct = folded.get(_fold(name))
        if _clean(direct):
            return str(direct)
    for key, value in specs.items():
        if any(_fold(name) in _fold(key) for name in names) and _clean(value):
            return str(value)
    return ""


def _find(text: str, pattern: str) -> str:
    match = re.search(pattern, text, flags=re.I)
    return match.group(1).strip() if match else ""


def _label(value: str) -> str:
    text = str(value).replace("_", " ").strip()
    upper = {"ddm", "msa", "rohs", "ieee", "sfp", "qsfp", "sfp28", "qsfp28"}
    return " ".join(part.upper() if part.lower() in upper else part.capitalize() for part in text.split())


def _sentence(prefix: str, value: Any, suffix: str = "") -> str:
    if not _clean(value):
        return ""
    return " ".join(part for part in [prefix, str(value), suffix] if part).strip()


def _with_value(prefix: str, value: Any) -> str:
    return f"{prefix}{value}" if _clean(value) else ""


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _fold(value: Any) -> str:
    return re.sub(r"\s+", " ", _clean(value).lower())


def jsonish(value: Any) -> str:
    return " ".join(f"{key} {val}" for key, val in (value or {}).items())
