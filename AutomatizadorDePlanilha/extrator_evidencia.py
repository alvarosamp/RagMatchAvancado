from __future__ import annotations

import re
import json
import unicodedata
from dataclasses import dataclass, asdict, field
from typing import Any, Iterable, Sequence


# =========================================================
# ESTRUTURAS
# =========================================================

@dataclass
class Evidence:
    kind: str
    score: int
    text: str
    filename: str | None = None
    page: int | None = None
    section: str | None = None
    chunk_idx: int | None = None
    signals: list[str] = field(default_factory=list)
    autonomy: str | None = None
    reason: str | None = None


@dataclass
class EvidencePack:
    cabecalho: list[Evidence] = field(default_factory=list)
    itens_candidatos: list[Evidence] = field(default_factory=list)
    trechos_switch: list[Evidence] = field(default_factory=list)
    trechos_transceiver: list[Evidence] = field(default_factory=list)
    trechos_risco: list[Evidence] = field(default_factory=list)
    trechos_habilitacao: list[Evidence] = field(default_factory=list)
    trechos_valores: list[Evidence] = field(default_factory=list)

    def to_prompt_text(self) -> str:
        parts = []
        for title, items in [
            ("CABEÇALHO", self.cabecalho),
            ("ITENS", self.itens_candidatos),
            ("SWITCH", self.trechos_switch),
            ("TRANSCEIVER", self.trechos_transceiver),
            ("RISCO", self.trechos_risco),
            ("HABILITAÇÃO", self.trechos_habilitacao),
            ("VALORES", self.trechos_valores),
        ]:
            if not items:
                continue

            parts.append(f"\n## {title}")
            for ev in items:
                parts.append(f"- {ev.text}")

        return "\n".join(parts)


# =========================================================
# NORMALIZAÇÃO
# =========================================================

def norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text.lower()


# =========================================================
# PADRÕES
# =========================================================

SWITCH_KEYWORDS = [
    "switch", "comutador", "gigabit", "ethernet",
    "vlan", "poe", "layer 2", "layer 3", "uplink", "sfp"
]

TRANSCEIVER_KEYWORDS = [
    "transceiver", "transceptor", "sfp", "sfp+", "gbic", "qsfp"
]

RISK_KEYWORDS = [
    "instalação", "configuração", "treinamento",
    "on-site", "visita técnica", "suporte presencial"
]

HABILITACAO_KEYWORDS = [
    "habilitação", "certidão", "balanço", "atestado"
]


# =========================================================
# CLASSIFICADORES
# =========================================================

def detect_switch(text: str) -> bool:
    t = norm(text)
    return any(k in t for k in SWITCH_KEYWORDS)


def detect_transceiver(text: str) -> bool:
    t = norm(text)
    return any(k in t for k in TRANSCEIVER_KEYWORDS)


def detect_risk(text: str) -> bool:
    t = norm(text)
    return any(k in t for k in RISK_KEYWORDS)


def detect_habilitacao(text: str) -> bool:
    t = norm(text)
    return any(k in t for k in HABILITACAO_KEYWORDS)


# =========================================================
# EXTRAÇÃO PRINCIPAL
# =========================================================

def extract_evidence_pack(parsed_docs: Any) -> EvidencePack:
    pack = EvidencePack()

    docs = parsed_docs if isinstance(parsed_docs, list) else [parsed_docs]

    for doc in docs:
        for chunk in doc.chunks:
            text = chunk.text.strip()

            if not text:
                continue

            if detect_switch(text):
                pack.trechos_switch.append(Evidence("switch", 80, text))

            if detect_transceiver(text):
                pack.trechos_transceiver.append(Evidence("transceiver", 80, text))

            if detect_risk(text):
                pack.trechos_risco.append(Evidence("risco", 80, text))

            if detect_habilitacao(text):
                pack.trechos_habilitacao.append(Evidence("habilitacao", 80, text))

            if any(x in norm(text) for x in ["item", "lote", "quantidade", "valor"]):
                pack.itens_candidatos.append(Evidence("item", 70, text))

            if any(x in norm(text) for x in ["pregão", "uasg", "data", "hora"]):
                pack.cabecalho.append(Evidence("cabecalho", 60, text))

    return pack


# =========================================================
# FUNÇÃO PARA PIPELINE
# =========================================================

def build_llm_input_from_merged_text(merged_text: str) -> str:
    class DummyChunk:
        def __init__(self, text, idx):
            self.text = text
            self.chunk_idx = idx

    class DummyDoc:
        def __init__(self, text):
            parts = re.split(r"\n{2,}", text)
            self.chunks = [DummyChunk(p, i) for i, p in enumerate(parts)]

    doc = DummyDoc(merged_text)

    pack = extract_evidence_pack(doc)

    return pack.to_prompt_text()