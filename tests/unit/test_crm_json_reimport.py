from types import SimpleNamespace

from app.crm.json_analysis_importer import _find_existing_notice


class _Field:
    def __eq__(self, other):
        return (self, other)


class _Notice:
    tenant_id = _Field()
    import_key = _Field()
    tor_id = _Field()
    number = _Field()


class _Query:
    def __init__(self, result):
        self.result = result

    def filter(self, *conditions):
        return self

    def first(self):
        return self.result


class _Db:
    def __init__(self, results):
        self.results = list(results)
        self.query_count = 0

    def query(self, model):
        self.query_count += 1
        return _Query(self.results.pop(0))


def test_reimport_falls_back_to_stable_tor_id_when_import_key_changed():
    existing = SimpleNamespace(id="notice-1", import_key="analysis-json|old")
    db = _Db([None, existing])

    found = _find_existing_notice(
        db,
        _Notice,
        tenant_id=7,
        import_key="analysis-json|new",
        tor_id="2026_09_11_10",
    )

    assert found is existing
    assert db.query_count == 2


def test_reimport_prefers_exact_import_key_match():
    existing = SimpleNamespace(id="notice-1", import_key="analysis-json|same")
    db = _Db([existing])

    found = _find_existing_notice(
        db,
        _Notice,
        tenant_id=7,
        import_key="analysis-json|same",
        tor_id="2026_09_11_10",
    )

    assert found is existing
    assert db.query_count == 1


def test_reimport_supports_legacy_notice_with_number_only():
    existing = SimpleNamespace(id="notice-1", number="2026_09_11_10")
    db = _Db([None, None, existing])

    found = _find_existing_notice(
        db,
        _Notice,
        tenant_id=7,
        import_key="analysis-json|new",
        tor_id="2026_09_11_10",
    )

    assert found is existing
    assert db.query_count == 3
