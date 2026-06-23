from app.services.analysis_store import build_source_hash


def test_build_source_hash_is_stable_for_same_document():
    first = build_source_hash("edital", "texto extraido", "edital.pdf")
    second = build_source_hash("edital", "texto extraido", "edital.pdf")

    assert first == second


def test_build_source_hash_changes_when_content_changes():
    first = build_source_hash("edital", "texto extraido", "edital.pdf")
    second = build_source_hash("edital", "texto alterado", "edital.pdf")

    assert first != second
