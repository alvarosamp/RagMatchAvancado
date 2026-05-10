from __future__ import annotations

import importlib.util
import sqlite3
import sys
from pathlib import Path


_MOD_PATH = Path(__file__).resolve().parents[2] / "Pncp" / "apiPncp" / "shared" / "db.py"
_SPEC = importlib.util.spec_from_file_location("pncp_shared_db_mod", _MOD_PATH)
_MOD = importlib.util.module_from_spec(_SPEC)
assert _SPEC and _SPEC.loader
sys.modules.setdefault(_SPEC.name, _MOD)
_SPEC.loader.exec_module(_MOD)


def _configure_temp_db(tmp_path: Path) -> None:
    _MOD.DATA_DIR = tmp_path
    _MOD.DB_PATH = tmp_path / "pncp_pipeline.db"


def test_init_db_migra_schema_antigo(tmp_path: Path) -> None:
    _configure_temp_db(tmp_path)

    with sqlite3.connect(_MOD.DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE licitacoes (
                id_pncp TEXT PRIMARY KEY,
                cnpj TEXT,
                ano INTEGER,
                sequencial INTEGER,
                status_api TEXT,
                status_ata TEXT,
                criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
                atualizado_em DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE itens_ata (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_pncp TEXT NOT NULL,
                sequencial_ata TEXT,
                sequencial_doc TEXT,
                nome_arquivo TEXT,
                caminho_pdf TEXT,
                status_download TEXT,
                descricao_ocr TEXT,
                marca_extraida TEXT,
                modelo_extraido TEXT,
                status_ocr TEXT,
                mensagem_erro TEXT,
                criado_em DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

    _MOD.init_db()

    with sqlite3.connect(_MOD.DB_PATH) as conn:
        licitacoes_cols = {row[1] for row in conn.execute("PRAGMA table_info(licitacoes)").fetchall()}
        itens_ata_cols = {row[1] for row in conn.execute("PRAGMA table_info(itens_ata)").fetchall()}

    assert "status_llm" in licitacoes_cols
    for column_name in (
        "numero_item",
        "descricao_llm",
        "tipo",
        "quantidade",
        "unidade",
        "valor_unitario",
        "valor_total",
        "fornecedor",
        "cnpj_fornecedor",
        "especificacoes",
        "observacoes",
        "status_llm",
    ):
        assert column_name in itens_ata_cols


def test_persistencia_llm_grava_status_e_campos_novos(tmp_path: Path) -> None:
    _configure_temp_db(tmp_path)
    _MOD.init_db()

    _MOD.upsert_licitacao("pncp-123", "12345678000190", 2026, 77)
    _MOD.atualizar_status("pncp-123", "llm", "ok")
    _MOD.inserir_item_ata(
        "pncp-123",
        {
            "numero_item": "7",
            "descricao_llm": "Switch 24 portas gerenciavel",
            "tipo": "Switch",
            "quantidade": 2,
            "unidade": "unidade",
            "valor_unitario": 1499.9,
            "valor_total": 2999.8,
            "fornecedor": "Fornecedor X",
            "cnpj_fornecedor": "11.222.333/0001-44",
            "especificacoes": '["24 portas", "poe"]',
            "observacoes": "LOTE 3",
            "status_llm": "ok",
        },
    )

    rows = _MOD.relatorio_final()
    assert len(rows) == 1

    row = rows[0]
    assert row["status_llm"] == "ok"
    assert row["numero_item_ata"] == "7"
    assert row["descricao_llm"] == "Switch 24 portas gerenciavel"
    assert row["valor_unitario"] == 1499.9
    assert row["status_llm_item"] == "ok"
