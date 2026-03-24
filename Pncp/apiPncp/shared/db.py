from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "pncp_pipeline.db"


def _connect() -> sqlite3.Connection:
	DATA_DIR.mkdir(parents=True, exist_ok=True)
	conn = sqlite3.connect(DB_PATH, timeout=30)
	conn.row_factory = sqlite3.Row
	return conn


def init_db() -> None:
	with _connect() as conn:
		conn.execute("PRAGMA journal_mode=WAL;")
		conn.execute("PRAGMA foreign_keys=ON;")

		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS licitacoes (
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
			CREATE TABLE IF NOT EXISTS itens_api (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				id_pncp TEXT NOT NULL,
				numero_item TEXT,
				descricao_api TEXT,
				quantidade REAL,
				unidade_medida TEXT,
				valor_estimado REAL,
				valor_homologado REAL,
				valor_total_homolog REAL,
				nome_vencedor TEXT,
				cnpj_vencedor TEXT,
				porte_vencedor TEXT,
				data_resultado TEXT,
				situacao_item TEXT,
				srp INTEGER,
				principal_regex INTEGER,
				marca_regex TEXT,
				modelo_regex TEXT,
				principal_ollama INTEGER,
				marca_ollama TEXT,
				modelo_ollama TEXT,
				criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
				FOREIGN KEY (id_pncp) REFERENCES licitacoes(id_pncp)
			)
			"""
		)

		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS itens_ata (
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
				criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
				FOREIGN KEY (id_pncp) REFERENCES licitacoes(id_pncp)
			)
			"""
		)


def upsert_licitacao(id_pncp: str, cnpj: str | None, ano: int | None, sequencial: int | None) -> None:
	with _connect() as conn:
		conn.execute(
			"""
			INSERT INTO licitacoes (id_pncp, cnpj, ano, sequencial, status_api, status_ata)
			VALUES (?, ?, ?, ?, COALESCE((SELECT status_api FROM licitacoes WHERE id_pncp = ?), 'pendente'), COALESCE((SELECT status_ata FROM licitacoes WHERE id_pncp = ?), 'pendente'))
			ON CONFLICT(id_pncp) DO UPDATE SET
				cnpj = excluded.cnpj,
				ano = excluded.ano,
				sequencial = excluded.sequencial,
				atualizado_em = CURRENT_TIMESTAMP
			""",
			(id_pncp, cnpj, ano, sequencial, id_pncp, id_pncp),
		)


def atualizar_status(id_pncp: str, pipeline: str, status: str) -> None:
	coluna = "status_api" if pipeline == "api" else "status_ata"
	with _connect() as conn:
		conn.execute(
			f"""
			UPDATE licitacoes
			   SET {coluna} = ?,
				   atualizado_em = CURRENT_TIMESTAMP
			 WHERE id_pncp = ?
			""",
			(status, id_pncp),
		)


def inserir_item_api(id_pncp: str, registro: dict[str, Any]) -> None:
	upsert_licitacao(
		id_pncp=id_pncp,
		cnpj=None,
		ano=None,
		sequencial=None,
	)

	with _connect() as conn:
		conn.execute(
			"""
			INSERT INTO itens_api (
				id_pncp, numero_item, descricao_api, quantidade, unidade_medida,
				valor_estimado, valor_homologado, valor_total_homolog,
				nome_vencedor, cnpj_vencedor, porte_vencedor, data_resultado,
				situacao_item, srp, principal_regex, marca_regex, modelo_regex,
				principal_ollama, marca_ollama, modelo_ollama
			)
			VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
			""",
			(
				id_pncp,
				registro.get("numero_item"),
				registro.get("descricao"),
				registro.get("quantidade"),
				registro.get("unidade_medida"),
				registro.get("valor_estimado"),
				registro.get("valor_homologado"),
				registro.get("valor_total_homolog"),
				registro.get("nome_vencedor"),
				registro.get("cnpj_vencedor"),
				registro.get("porte_vencedor"),
				registro.get("data_resultado"),
				registro.get("situacao_item"),
				registro.get("srp"),
				registro.get("principal_regex"),
				registro.get("marca_regex"),
				registro.get("modelo_regex"),
				registro.get("principal_ollama"),
				registro.get("marca_ollama"),
				registro.get("modelo_ollama"),
			),
		)


def inserir_item_ata(id_pncp: str, registro: dict[str, Any]) -> None:
	upsert_licitacao(
		id_pncp=id_pncp,
		cnpj=None,
		ano=None,
		sequencial=None,
	)

	with _connect() as conn:
		conn.execute(
			"""
			INSERT INTO itens_ata (
				id_pncp, sequencial_ata, sequencial_doc, nome_arquivo, caminho_pdf,
				status_download, descricao_ocr, marca_extraida, modelo_extraido,
				status_ocr, mensagem_erro
			)
			VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
			""",
			(
				id_pncp,
				registro.get("sequencial_ata"),
				registro.get("sequencial_doc"),
				registro.get("nome_arquivo"),
				registro.get("caminho_pdf"),
				registro.get("status_download"),
				registro.get("descricao_ocr"),
				registro.get("marca_extraida"),
				registro.get("modelo_extraido"),
				registro.get("status_ocr"),
				registro.get("mensagem_erro"),
			),
		)


def relatorio_final() -> list[dict[str, Any]]:
	with _connect() as conn:
		rows = conn.execute(
			"""
			SELECT
				l.id_pncp,
				l.cnpj,
				l.ano,
				l.sequencial,
				l.status_api,
				l.status_ata,
				a.numero_item,
				a.descricao_api,
				a.quantidade,
				a.unidade_medida,
				a.valor_estimado,
				a.valor_homologado,
				a.valor_total_homolog,
				a.nome_vencedor,
				a.cnpj_vencedor,
				a.porte_vencedor,
				a.data_resultado,
				a.situacao_item,
				a.principal_regex,
				a.marca_regex,
				a.modelo_regex,
				a.principal_ollama,
				a.marca_ollama,
				a.modelo_ollama,
				t.sequencial_ata,
				t.sequencial_doc,
				t.nome_arquivo,
				t.caminho_pdf,
				t.status_download,
				t.descricao_ocr,
				t.marca_extraida,
				t.modelo_extraido,
				t.status_ocr,
				t.mensagem_erro
			FROM licitacoes l
			LEFT JOIN itens_api a ON a.id_pncp = l.id_pncp
			LEFT JOIN itens_ata t ON t.id_pncp = l.id_pncp
			ORDER BY l.id_pncp DESC, a.id DESC, t.id DESC
			"""
		).fetchall()

	return [dict(r) for r in rows]
