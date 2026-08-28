from openpyxl import Workbook

from app.crm import lpu_importer
from app.crm.lpu_importer import LpuImportSummary, _norm, _row_to_record


def _record(row):
    header = ["Marca", "PN TOR", "Description", "Disponibilidade", "Part No", "Custo Final", "Preco Minimo"]
    return _row_to_record(header, [_norm(value) for value in header], row, "Transceivers")


def test_lpu_row_skips_blocked_pn_values():
    base = ("TOR", None, "Produto bloqueado", "Estoque", "MFR-1", 10.0, 20.0)

    assert _record(base) is None
    assert _record(("TOR", "-", *base[2:])) is None
    assert _record(("TOR", "XWDM - NAO VENDER", *base[2:])) is None


def test_lpu_row_skips_blocked_availability_values():
    assert _record(("TOR", "PN-1", "Produto bloqueado", None, "MFR-1", 10.0, 20.0)) is None
    assert _record(("TOR", "PN-1", "Produto bloqueado", "-", "MFR-1", 10.0, 20.0)) is None
    assert _record(("TOR", "PN-1", "Produto bloqueado", "XWDM - NAO VENDER", "MFR-1", 10.0, 20.0)) is None


def test_lpu_row_keeps_checked_availability_values():
    assert _record(("TOR", "PN-1", "Produto sob encomenda", "Encomenda", "MFR-1", 10.0, 20.0)) is not None
    assert _record(("TOR", "PN-2", "Produto em estoque", "Estoque", "MFR-2", 10.0, 20.0)) is not None
    assert _record(("TOR", "PN-3", "Produto trinta dias", "30 DU", "MFR-3", 10.0, 20.0)) is not None


def test_lpu_row_uses_pn_as_sku_for_valid_item():
    record = _record(("TOR", "UACC-CM-RJ45-MG", "Modulo RJ45", "Estoque", "MFR-1", 10.0, 20.0))

    assert record is not None
    assert record["sku"] == "UACC-CM-RJ45-MG"
    assert record["manufacturer_part_number"] == "MFR-1"
    assert record["min_price"] == 20.0


def test_lpu_summary_enumerates_imported_items():
    summary = LpuImportSummary(
        processed=7,
        created=4,
        updated=3,
        lpu_drive_url="https://drive.google.com/file/d/lpu",
    )

    payload = summary.as_dict()

    assert payload["items"] == 7
    assert payload["total_items"] == 7
    assert payload["created"] == 4
    assert payload["updated"] == 3
    assert payload["lpu_drive_url"] == "https://drive.google.com/file/d/lpu"


def test_import_lpu_requires_google_drive_link():
    try:
        lpu_importer.import_lpu_catalog("lpu.xlsx", db=object(), tenant_id=1, user_id=2, lpu_drive_url="")
    except ValueError as exc:
        assert "link do Drive" in str(exc)
    else:
        raise AssertionError("Importacao de LPU sem link do Drive deveria falhar.")


def test_import_lpu_updates_duplicate_pn_in_same_workbook(monkeypatch):
    class Field:
        def __init__(self, name):
            self.name = name

        def __eq__(self, other):
            return (self.name, other)

        def in_(self, values):
            return (self.name, set(values))

        def notin_(self, values):
            return (f"{self.name}__notin", set(values))

    class FakeProduct:
        tenant_id = Field("tenant_id")
        sku = Field("sku")
        category = Field("category")

        def __init__(self, **values):
            for key, value in values.items():
                setattr(self, key, value)

    class FakeQuery:
        def __init__(self, db):
            self.db = db
            self.filters = {}

        def filter(self, *clauses):
            self.filters.update(dict(clauses))
            return self

        def first(self):
            key = (self.filters.get("tenant_id"), self.filters.get("sku"))
            return self.db.products.get(key)

        def all(self):
            tenant_id = self.filters.get("tenant_id")
            categories = self.filters.get("category")
            excluded_skus = self.filters.get("sku__notin", set())
            return [
                product
                for product in self.db.products.values()
                if product.tenant_id == tenant_id
                and product.category in categories
                and product.sku not in excluded_skus
            ]

    class FakeDb:
        def __init__(self):
            self.products = {}

        def query(self, _model):
            return FakeQuery(self)

        def add(self, product):
            self.products[(product.tenant_id, product.sku)] = product

        def delete(self, product):
            self.products.pop((product.tenant_id, product.sku), None)

        def flush(self):
            return None

        def commit(self):
            return None

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Transceivers"
    sheet.append(["Marca", "PN TOR", "Description", "Disponibilidade", "Part No", "Custo Final", "Preco Minimo"])
    sheet.append(["TOR", "PN-1", "Descricao antiga", "Estoque", "MFR-1", 10.0, 20.0])
    sheet.append(["TOR", "PN-1", "Descricao nova", "Estoque", "MFR-2", 11.0, 21.0])
    monkeypatch.setattr(lpu_importer, "CrmCatalogProduct", FakeProduct)
    monkeypatch.setattr(lpu_importer, "load_workbook", lambda _path, data_only=True: workbook)

    db = FakeDb()
    db.add(
        FakeProduct(
            tenant_id=1,
            sku="PN-FORA-DA-LPU",
            category="transceiver",
            name="Produto antigo",
            description="Produto antigo",
            cost=1.0,
        )
    )
    summary = lpu_importer.import_lpu_catalog(
        "lpu.xlsx",
        db=db,
        tenant_id=1,
        user_id=2,
        lpu_drive_url="https://drive.google.com/file/d/lpu",
    )

    assert summary["created"] == 1
    assert summary["updated"] == 1
    assert summary["items"] == 2
    assert summary["duplicate_updates"] == 1
    assert summary["removed_stale"] == 1
    assert summary["lpu_version"]
    assert summary["lpu_drive_url"] == "https://drive.google.com/file/d/lpu"
    assert db.products[(1, "PN-1")].lpu_version == summary["lpu_version"]
    assert db.products[(1, "PN-1")].lpu_drive_url == summary["lpu_drive_url"]
    assert db.products[(1, "PN-1")].description == "Descricao nova"
    assert (1, "PN-FORA-DA-LPU") not in db.products
