"""Regression tests for authentication and tenant isolation boundaries."""

from __future__ import annotations

import importlib.util
import inspect
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException


ROOT = Path(__file__).resolve().parents[2]


class _Field:
    def __init__(self, name: str):
        self.name = name

    def __eq__(self, value):
        return (self.name, value)


class _Query:
    def __init__(self, result=None):
        self.result = result
        self.filters = []
        self.joins = []

    def filter(self, *conditions):
        self.filters.extend(conditions)
        return self

    def join(self, *args):
        self.joins.append(args)
        return self

    def first(self):
        return self.result

    def all(self):
        return [] if self.result is None else self.result


class _Db:
    def __init__(self, result=None):
        self.query_result = _Query(result)

    def query(self, _model):
        return self.query_result


def _module(name: str, **attributes) -> ModuleType:
    module = ModuleType(name)
    for key, value in attributes.items():
        setattr(module, key, value)
    return module


def _load(relative_path: str, module_name: str, stubs: dict[str, ModuleType]):
    path = ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    with patch.dict(sys.modules, stubs):
        spec.loader.exec_module(module)
    return module


def _export_module():
    class Edital:
        id = _Field("edital.id")
        tenant_id = _Field("edital.tenant_id")

    stubs = {
        "app.auth.dependencies": _module("app.auth.dependencies", get_current_user=lambda: None),
        "app.auth.models": _module("app.auth.models", User=type("User", (), {})),
        "app.db.session": _module("app.db.session", get_db=lambda: None),
        "app.db.models": _module("app.db.models", Edital=Edital),
        "app.services.export_service": _module(
            "app.services.export_service",
            export_xlsx=MagicMock(return_value=b""),
            export_pdf=MagicMock(return_value=b""),
            export_csv=MagicMock(return_value=b""),
        ),
        "app.logs.config": _module("app.logs.config", logger=MagicMock()),
        "app.services.object_storage": _module(
            "app.services.object_storage",
            object_storage_enabled=MagicMock(return_value=False),
            put_export=MagicMock(),
        ),
    }
    return _load("backend/app/routers/export.py", "export_security_under_test", stubs)


def test_export_lookup_is_scoped_to_authenticated_tenant():
    export = _export_module()
    db = _Db(result=None)

    with pytest.raises(HTTPException) as exc_info:
        export._build_results_data(42, 7, db)

    assert exc_info.value.status_code == 404
    assert ("edital.id", 42) in db.query_result.filters
    assert ("edital.tenant_id", 7) in db.query_result.filters


def test_all_export_endpoints_require_current_user_dependency():
    export = _export_module()

    for endpoint in (export.download_xlsx, export.download_pdf, export.download_csv):
        assert "current_user" in inspect.signature(endpoint).parameters


def test_export_archival_rechecks_tenant_boundary():
    export = _export_module()
    export.object_storage_enabled.return_value = True
    db = _Db(result=SimpleNamespace(tenant_id=7))

    export._archive_export(db, 42, 7, "result.csv", b"data", "text/csv")

    assert ("edital.id", 42) in db.query_result.filters
    assert ("edital.tenant_id", 7) in db.query_result.filters
    export.put_export.assert_called_once_with(
        7, 42, "result.csv", b"data", "text/csv"
    )


def _switches_module():
    class Product:
        category = _Field("product.category")

    class MatchingResult:
        requirement_id = _Field("matching_result.requirement_id")

    class Requirement:
        id = _Field("requirement.id")
        edital_id = _Field("requirement.edital_id")

    class Edital:
        id = _Field("edital.id")
        tenant_id = _Field("edital.tenant_id")

    stubs = {
        "app.services.requirements_checker": _module(
            "app.services.requirements_checker", check_requirements=MagicMock()
        ),
        "app.auth.dependencies": _module("app.auth.dependencies", get_current_user=lambda: None),
        "app.auth.models": _module("app.auth.models", User=type("User", (), {})),
        "app.db.session": _module("app.db.session", get_db=lambda: None),
        "app.db.models": _module(
            "app.db.models",
            Product=Product,
            MatchingResult=MatchingResult,
            Requirement=Requirement,
            Edital=Edital,
        ),
        "app.logs.config": _module("app.logs.config", logger=MagicMock()),
    }
    return _load("backend/app/routers/switches.py", "switches_security_under_test", stubs)


def test_legacy_matching_results_are_scoped_to_authenticated_tenant():
    switches = _switches_module()
    db = _Db()
    user = SimpleNamespace(tenant_id=7, tenant=SimpleNamespace(slug="tenant-a"))

    assert switches.get_matching_results(current_user=user, db=db) == []
    assert ("edital.tenant_id", 7) in db.query_result.filters
    assert len(db.query_result.joins) == 2


def test_all_legacy_catalog_endpoints_require_authentication():
    switches = _switches_module()

    for endpoint in (
        switches.list_switches,
        switches.verify_all_switches,
        switches.get_matching_results,
    ):
        assert "current_user" in inspect.signature(endpoint).parameters


def _dependencies_module(user, *, auth_version=0):
    class User:
        id = _Field("user.id")
        email = _Field("user.email")

    stubs = {
        "jose": _module("jose", JWTError=type("JWTError", (Exception,), {})),
        "app.db.session": _module(
            "app.db.session",
            get_db=lambda: None,
            set_tenant_context=MagicMock(),
        ),
        "app.auth.models": _module(
            "app.auth.models", User=User, Tenant=type("Tenant", (), {})
        ),
        "app.auth.security": _module(
            "app.auth.security",
            decode_access_token=lambda _token: {
                "user_id": 7,
                "sub": "user@example.com",
                "auth_version": auth_version,
            },
        ),
        "app.logs.config": _module("app.logs.config", logger=MagicMock()),
    }
    dependencies = _load(
        "backend/app/auth/dependencies.py", "auth_dependencies_security_under_test", stubs
    )
    return dependencies, _Db(result=user)


def test_inactive_tenant_is_rejected_by_primary_auth_dependency():
    user = SimpleNamespace(
        is_active=True,
        tenant=SimpleNamespace(is_active=False),
    )
    dependencies, db = _dependencies_module(user)
    request = SimpleNamespace(cookies={})

    with pytest.raises(HTTPException) as exc_info:
        dependencies.get_current_user(request=request, token="token", db=db)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Tenant desativado. Entre em contato com o suporte."


def test_revoked_session_version_is_rejected():
    user = SimpleNamespace(
        id=7,
        email="user@example.com",
        auth_version=2,
        is_active=True,
        tenant=SimpleNamespace(is_active=True),
    )
    dependencies, db = _dependencies_module(user, auth_version=1)

    with pytest.raises(HTTPException) as exc_info:
        dependencies.get_current_user(
            request=SimpleNamespace(cookies={}),
            token="old-token",
            db=db,
        )

    assert exc_info.value.status_code == 401


def test_authenticated_session_receives_database_tenant_context():
    user = SimpleNamespace(
        id=7,
        email="user@example.com",
        tenant_id=23,
        auth_version=0,
        is_active=True,
        tenant=SimpleNamespace(is_active=True),
    )
    dependencies, db = _dependencies_module(user)
    dependencies.set_tenant_context = MagicMock()

    result = dependencies.get_current_user(
        request=SimpleNamespace(cookies={}),
        token="valid-token",
        db=db,
    )

    assert result is user
    dependencies.set_tenant_context.assert_called_once_with(db, 23)
