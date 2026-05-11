"""tests/unit/test_pipelinellm_prompt_ajustado.py

Testes unitários do pipeline LLM de extração de itens de Ata.

Objetivo:
- Validar chunking e heurísticas (item-mode)
- Validar normalização/limpeza (CNPJ, numero_item, lote)
- Validar filtros de falsos positivos (texto jurídico/institucional/total)
- Validar dedupe
- Validar fluxo de `analisar_ata` sem depender de Ollama real (mocks)

Como rodar:
    pytest tests/unit/test_pipelinellm_prompt_ajustado.py -v
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


_MOD_PATH = Path(__file__).resolve().parents[2] / "Pncp" / "AnaliseAtaLLM" / "pipelinellm_prompt_ajustado.py"
_spec = importlib.util.spec_from_file_location("pipelinellm_prompt_ajustado_mod", _MOD_PATH)
_mod = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
sys.modules.setdefault(_spec.name, _mod)
_spec.loader.exec_module(_mod)


class TestChunkingAndHeuristics:
    def test_dividir_em_chunks_respeita_max_chars_e_nao_cria_vazios(self):
        texto = "\n".join(["A" * 40, "B" * 40, "C" * 40, "D" * 40])
        chunks = _mod._dividir_em_chunks(texto, max_chars=90)
        assert len(chunks) >= 2
        assert all(c.strip() for c in chunks)
        assert all(len(c) <= 90 for c in chunks)

    def test_split_into_item_blocks_so_ativa_com_3_ou_mais_itens(self):
        texto2 = "Item 1\nX\nItem 2\nY\n"
        assert _mod._split_into_item_blocks(texto2) == []

        texto3 = "Item 1\nX\nItem 2\nY\nItem 3\nZ\n"
        blocks = _mod._split_into_item_blocks(texto3)
        assert len(blocks) == 3
        assert blocks[0].lower().startswith("item 1")

    def test_reparar_quebra_pagina_insere_item_antes_de_descricao(self):
        texto = """Item: 12

---

Descrição: Switch 24 portas\n"""
        repaired = _mod._reparar_quebra_pagina(texto)
        # Deve ter duas ocorrências: a original e a injetada.
        assert repaired.lower().count("item:") >= 2

    def test_inferir_lote_por_item_mapeia_proximo(self):
        texto = """LOTE 2
ITEM: 10
Alguma coisa

LOTE 3
ITEM: 11
"""
        mapping = _mod._inferir_lote_por_item(texto, max_line_distance=10)
        assert mapping["10"] == "2"
        assert mapping["11"] == "3"


class TestCleaningAndFiltering:
    def test_clean_item_dict_move_cnpj_de_numero_item_e_normaliza(self):
        d = {
            "numero_item": "11.222.333/0001-44",
            "descricao": "ITEM 7: Cabo de rede CAT6",
            "raw_descricao": None,
            "fornecedor": "Fornecedor X",
            "cnpj_fornecedor": None,
            "especificacoes": ["CAT6", "  "],
        }
        cleaned = _mod._clean_item_dict(d)
        assert cleaned["numero_item"] == "7"
        assert cleaned["cnpj_fornecedor"] == "11.222.333/0001-44"
        assert cleaned["raw_descricao"] is not None
        assert cleaned["especificacoes"] == ["CAT6"]

    def test_filter_invalid_items_remove_juridico_e_total(self):
        items = [
            {
                "numero_item": None,
                "descricao": "7. DAS SANÇÕES E PENALIDADES",
                "raw_descricao": "7. DAS SANÇÕES E PENALIDADES",
                "quantidade": 1,
                "valor_unitario": None,
                "valor_total": None,
                "fornecedor": None,
                "marca": None,
                "modelo": None,
                "unidade": None,
            },
            {
                "numero_item": None,
                "descricao": "TOTAL DO ITEM",
                "raw_descricao": "TOTAL DO ITEM",
                "quantidade": None,
                "valor_unitario": None,
                "valor_total": 123.45,
                "fornecedor": None,
                "marca": None,
                "modelo": None,
                "unidade": None,
            },
            {
                "numero_item": "1",
                "descricao": "Cabo de rede CAT6",
                "raw_descricao": "ITEM 1 - Cabo de rede CAT6",
                "quantidade": 10,
                "unidade": "un",
                "valor_unitario": 12.3,
                "valor_total": 123.0,
                "fornecedor": "ABC LTDA",
                "marca": None,
                "modelo": None,
            },
        ]
        out = _mod._filter_invalid_items(items)
        assert len(out) == 1
        assert out[0]["descricao"] == "Cabo de rede CAT6"

    def test_dedupe_items_soma_quantidade_e_valor_total(self):
        items = [
            {"raw_descricao": "Item 1: Cabo CAT6", "descricao": "Cabo CAT6", "fornecedor": "ABC", "valor_unitario": 10.0, "quantidade": 2, "valor_total": 20.0, "especificacoes": ["CAT6"]},
            {"raw_descricao": "Item 1: Cabo CAT6", "descricao": "Cabo CAT6", "fornecedor": "ABC", "valor_unitario": 10.0, "quantidade": 3, "valor_total": 30.0, "especificacoes": ["UTP"]},
        ]
        out = _mod._dedupe_items(items)
        assert len(out) == 1
        assert out[0]["quantidade"] == 5
        assert out[0]["valor_total"] == 50.0
        assert "CAT6" in out[0]["especificacoes"]
        assert "UTP" in out[0]["especificacoes"]


class TestAnalisarAtaFlow:
    def test_analisar_ata_em_chunk_mode_com_mock(self, monkeypatch, tmp_path: Path):
        # Redireciona a pasta textos_md para o tmp do pytest.
        _mod.__file__ = str(tmp_path / "pipelinellm_prompt_ajustado.py")

        def fake_chamar_llm(_texto_chunk: str):
            payload = {
                "numero_ata": "123",
                "orgao": "Prefeitura X",
                "data_assinatura": None,
                "vigencia": None,
                "objeto": "Aquisição de cabos",
                "itens": [
                    {
                        "numero_item": "ITEM 1",
                        "descricao": "ITEM 1: Cabo de rede CAT6",
                        "raw_descricao": "ITEM 1: Cabo de rede CAT6",
                        "quantidade": "10",
                        "unidade": "un",
                        "valor_unitario": "R$ 12,30",
                        "valor_total": "123,00",
                        "fornecedor": "ABC LTDA (11.222.333/0001-44)",
                        "cnpj_fornecedor": None,
                        "especificacoes": ["CAT6"],
                        "observacoes": None,
                        "marca": None,
                        "modelo": None,
                        "tipo": None,
                    }
                ],
            }
            return payload, 100

        monkeypatch.setattr(_mod, "_chamar_llm", fake_chamar_llm)
        # Garantia: não deve tentar chamar item-mode
        monkeypatch.setattr(_mod, "_chamar_llm_item", lambda _t: (_t, 0))

        texto = "Texto curto sem muitos marcadores de item (chunk-mode)."
        res = _mod.analisar_ata(texto, id_pncp="999/2025", persistir=False)
        assert res.id_pncp == "999/2025"
        assert res.numero_ata == "123"
        assert len(res.itens) == 1
        item = res.itens[0]
        assert item.numero_item == "1"
        assert item.cnpj_fornecedor == "11.222.333/0001-44"
        assert item.valor_unitario == 12.3
        assert item.valor_total == 123.0
        assert res.tokens_usados == 100

    def test_analisar_ata_em_item_mode_com_mock_e_lote(self, monkeypatch, tmp_path: Path):
        _mod.__file__ = str(tmp_path / "pipelinellm_prompt_ajustado.py")

        def fake_meta(_texto_chunk: str):
            return {"numero_ata": "777", "orgao": "Órgão Y", "itens": []}, 10

        def fake_item(texto_item: str):
            # Retorna um item e um falso positivo jurídico para exercitar filtros.
            if "Item 2" in texto_item:
                return {
                    "numero_item": "2",
                    "descricao": "Switch 24 portas",
                    "raw_descricao": texto_item,
                    "quantidade": 1,
                    "unidade": "un",
                    "valor_unitario": 100.0,
                    "valor_total": 100.0,
                    "fornecedor": "Fornecedor Z",
                    "cnpj_fornecedor": None,
                    "especificacoes": ["24 portas"],
                    "observacoes": None,
                    "marca": None,
                    "modelo": None,
                    "tipo": None,
                }, 20
            return {
                "numero_item": None,
                "descricao": "7. DAS SANÇÕES",
                "raw_descricao": texto_item,
                "quantidade": 1,
                "unidade": None,
                "valor_unitario": None,
                "valor_total": None,
                "fornecedor": None,
                "cnpj_fornecedor": None,
                "especificacoes": [],
                "observacoes": None,
                "marca": None,
                "modelo": None,
                "tipo": None,
            }, 5

        monkeypatch.setattr(_mod, "_chamar_llm", fake_meta)
        monkeypatch.setattr(_mod, "_chamar_llm_item", fake_item)

        texto = """LOTE 3
Item 1
texto qualquer
Item 2
Descrição: Switch
Item 3
7. DAS SANÇÕES
"""
        res = _mod.analisar_ata(texto, id_pncp="1/2026", persistir=False)

        # Só deve sobrar o item real.
        assert res.numero_ata == "777"
        assert len(res.itens) == 1
        assert res.itens[0].numero_item == "2"
        # Deve anexar lote via inferência.
        assert res.itens[0].observacoes is not None
        assert "LOTE 3" in res.itens[0].observacoes
        assert res.tokens_usados == 10 + 5 + 20 + 5


class TestJsonRepair:
    def test_repair_json_with_ollama_usa_cliente_mockado(self, monkeypatch, tmp_path: Path):
        _mod.__file__ = str(tmp_path / "pipelinellm_prompt_ajustado.py")

        class FakeClient:
            def chat(self, **_kwargs):
                return {"message": {"content": json.dumps({"ok": True})}}

        monkeypatch.setattr(_mod, "_get_client", lambda: FakeClient())
        repaired = _mod._repair_json_with_ollama("{ invalid ")
        assert json.loads(repaired)["ok"] is True
