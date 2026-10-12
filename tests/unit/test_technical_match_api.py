"""Exercise the actual endpoint bodies with isolated DB/auth dependencies.

The full application needs infrastructure; these tests compile the selected
route definitions unchanged, keeping their FastAPI validation and HTTP errors.
"""
import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
import pytest
from fastapi import FastAPI, APIRouter, Body, Depends, HTTPException, BackgroundTasks, status
from fastapi.testclient import TestClient


@pytest.fixture
def api():
    user = SimpleNamespace(id=1, tenant_id=2, role='editor', tenant=object())
    run = MagicMock(return_value={'items':[]})
    ai = MagicMock(side_effect=AssertionError('rules must not require AI'))
    namespace = dict(Any=object, Session=object, User=object, APIRouter=APIRouter, router=APIRouter(),
                     Body=Body, Depends=Depends, HTTPException=HTTPException, BackgroundTasks=BackgroundTasks,
                     status=status, get_db=lambda:object(), get_current_user=lambda:user,
                     _raise_match_paused=lambda:None, require_ai_enabled=ai, run_notice_item_match=run)
    source = ast.parse(Path('backend/app/routers/crm.py').read_text())
    route = next(node for node in source.body if isinstance(node, ast.FunctionDef) and node.name == 'crm_run_notice_matches')
    module = ast.Module(body=[route], type_ignores=[])
    exec(compile(module, 'crm.py', 'exec'), namespace)
    app = FastAPI(); app.include_router(namespace['router'])
    return TestClient(app), user, run, ai


def test_rules_api_propagates_mode_without_ai_flag(api):
    client, user, run, ai = api
    response = client.post('/notices/n/matches/run', json={'mode':'rules','notice_product_id':'item'})
    assert response.status_code == 200
    assert run.call_args.kwargs['mode'] == 'rules'
    assert run.call_args.kwargs['notice_product_id'] == 'item'
    assert run.call_args.args[1].tenant_id == 2
    ai.assert_not_called()


def test_rules_api_enforces_editor_permission_and_validates_mode(api):
    client, user, run, ai = api
    user.role = 'viewer'
    assert client.post('/notices/n/matches/run', json={'mode':'rules'}).status_code == 403
    user.role = 'editor'
    assert client.post('/notices/n/matches/run', json={'mode':'invalid'}).status_code == 400
    run.assert_not_called()


def test_rules_api_maps_missing_notice_and_input_errors(api):
    client, user, run, ai = api
    run.side_effect = LookupError('missing notice')
    assert client.post('/notices/missing/matches/run', json={'mode':'rules'}).status_code == 404
    run.side_effect = ValueError('invalid criteria')
    assert client.post('/notices/n/matches/run', json={'mode':'rules'}).status_code == 400
