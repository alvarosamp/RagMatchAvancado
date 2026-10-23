"""Explicit range/set operators; no extraction of numbers from prose."""
from typing import Any
from .normalizer import normalize_value

RANGE_OPERATORS = {'cobre_faixa', 'range_covers'}
SET_OPERATORS = {'contem_todos', 'contains_all', 'contem_algum', 'contains_any', 'em', 'in'}


def sample_of(value: Any) -> Any:
    if isinstance(value, dict):
        return sample_of(value.get('valor', value.get('min', value.get('minimo'))))
    if isinstance(value, list):
        return sample_of(value[0]) if value else None
    return value


def normalize_operand(value: Any, op: str, *, kind: str, unit: str | None) -> Any:
    source_unit = None
    if isinstance(value, dict) and 'valor' in value:
        source_unit, value = value.get('unidade'), value['valor']
    def scalar(v):
        return normalize_value({'valor': v, 'unidade': source_unit} if source_unit else v, kind=kind, unit=unit)
    if op in RANGE_OPERATORS:
        if kind != 'number' or not isinstance(value, dict):
            raise ValueError('Faixa deve conter min e max numericos')
        source_unit = value.get('unidade') or source_unit
        low = scalar(value.get('min', value.get('minimo')))
        high = scalar(value.get('max', value.get('maximo')))
        if low > high:
            raise ValueError('Faixa invertida')
        return [low, high]
    if op in SET_OPERATORS:
        if not isinstance(value, list) or not value:
            raise ValueError('Conjunto deve ser uma lista nao vazia')
        values = [scalar(v) for v in value]
        # Typed tuples prevent boolean True from equaling numeric 1.
        return sorted({(type(v).__name__, v) for v in values}, key=repr)
    return normalize_value({'valor': value, 'unidade': source_unit} if source_unit else value, kind=kind, unit=unit)


def satisfies(found: Any, expected: Any, op: str) -> bool:
    if op in RANGE_OPERATORS:
        return found[0] <= expected[0] and found[1] >= expected[1]
    if op in {'contem_todos', 'contains_all'}:
        return set(expected).issubset(found)
    if op in {'contem_algum', 'contains_any'}:
        return bool(set(expected).intersection(found))
    if op in {'em', 'in'}:
        return (type(found).__name__, found) in expected
    raise ValueError('Operador desconhecido')


def scoped_sources(sources, scope):
    """Require an exact, explicit context, e.g. {'tipo_fibra': 'OM3'}."""
    if not scope:
        return sources
    if not isinstance(scope, dict) or not scope or any(isinstance(v, (dict, list)) for v in scope.values()):
        raise ValueError('Condicao deve ser um objeto de valores explicitos')
    selected = []
    for name, value in sources:
        variants = value.get('variantes') if isinstance(value, dict) else None
        entries = variants if isinstance(variants, list) else [value]
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            context = entry.get('escopo', entry.get('condicao'))
            if not isinstance(context, dict):
                continue
            if all(type(context.get(k)) is type(v) and context.get(k) == v for k, v in scope.items()):
                selected.append((name, entry))
    if not selected:
        raise ValueError('Produto sem valor documentado para a condicao exigida')
    return selected


def aggregate_groups(details):
    groups = {}
    effective = []
    for row in details:
        group = row.get('grupo_logico')
        if group:
            groups.setdefault(str(group), []).append(row)
        else:
            effective.append(row)
    summaries = []
    for group, rows in groups.items():
        logics = {r.get('operador_logico', 'E') for r in rows}
        obligations = {r['obrigatorio'] for r in rows}
        status = 'VERIFICAR'
        if len(logics) == 1 and len(obligations) == 1:
            logic = next(iter(logics))
            statuses = [r['status'] for r in rows]
            if logic in {'OU', 'OR', 'or'}:
                status = 'ATENDE' if 'ATENDE' in statuses else 'VERIFICAR' if 'VERIFICAR' in statuses else 'NAO_ATENDE'
            elif logic in {'E', 'AND', 'and'}:
                status = 'NAO_ATENDE' if 'NAO_ATENDE' in statuses else 'VERIFICAR' if 'VERIFICAR' in statuses else 'ATENDE'
        summary = {'atributo': f'grupo:{group}', 'status': status,
                   'obrigatorio': rows[0]['obrigatorio'] if len(obligations) == 1 else True,
                   'peso': max(r['peso'] for r in rows), 'criterios': [r.get('id') for r in rows]}
        summaries.append(summary)
        effective.append(summary)
    return effective, summaries


def numeric_scalars(value):
    if isinstance(value, tuple) and len(value) == 2 and isinstance(value[0], str):
        return [value[1]]
    if isinstance(value, list):
        return [scalar for entry in value for scalar in numeric_scalars(entry)]
    return [value]
