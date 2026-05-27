from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


def _load_pipeline_module(monkeypatch):
    if "app" not in sys.modules:
        monkeypatch.setitem(sys.modules, "app", types.ModuleType("app"))
    if "app.pipeline" not in sys.modules:
        monkeypatch.setitem(sys.modules, "app.pipeline", types.ModuleType("app.pipeline"))

    # Stubs to avoid pulling heavy runtime dependencies in unit tests.
    fake_docling = types.ModuleType("app.pipeline.docling_parser")

    class ParsedDocument:
        def __init__(self, full_text: str = "") -> None:
            self.full_text = full_text

    fake_docling.ParsedDocument = ParsedDocument
    fake_docling.parse_pdf = lambda source, filename=None: ParsedDocument("")  # noqa: E731
    fake_docling.release_converter = lambda: None  # noqa: E731

    fake_extrator = types.ModuleType("extrator_evidencia")
    fake_extrator.build_llm_input_from_merged_text = lambda text: text  # noqa: E731

    monkeypatch.setitem(sys.modules, "app.pipeline.docling_parser", fake_docling)
    monkeypatch.setitem(sys.modules, "extrator_evidencia", fake_extrator)

    mod_path = Path(__file__).resolve().parents[2] / "AutomatizadorDePlanilha" / "pipeline.py"
    spec = importlib.util.spec_from_file_location("automatizador_planilha_pipeline_utils_mod", mod_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_sanitize_csv_value_normaliza_basico(monkeypatch) -> None:
    mod = _load_pipeline_module(monkeypatch)
    assert mod.sanitize_csv_value(None) == "N/C"
    assert mod.sanitize_csv_value("") == "N/C"
    assert mod.sanitize_csv_value("  a   b  ") == "a b"
    assert mod.sanitize_csv_value("x;y") == "x,y"


def test_norm_key_remove_acentos(monkeypatch) -> None:
    mod = _load_pipeline_module(monkeypatch)
    assert mod._norm_key("Nº Pregão") == "no pregao"
    assert mod._norm_key("Órgão") == "orgao"
    assert mod._norm_key("  UF  ") == "uf"


def test_to_float_brl_parse(monkeypatch) -> None:
    mod = _load_pipeline_module(monkeypatch)
    assert mod._to_float_brl("R$ 1.234,56") == 1234.56
    assert mod._to_float_brl("123,40") == 123.4
    assert mod._to_float_brl("N/C") is None


def test_format_brl(monkeypatch) -> None:
    mod = _load_pipeline_module(monkeypatch)
    assert mod._format_brl(1234.5) == "R$ 1.234,50"


def test_safe_stem(monkeypatch) -> None:
    mod = _load_pipeline_module(monkeypatch)
    assert mod._safe_stem("foo bar.pdf") == "foo_bar"
    assert mod._safe_stem("..") == "document"
