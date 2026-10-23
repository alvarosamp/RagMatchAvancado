"""Adapt explicit V8/export criteria without collapsing duplicate attributes."""
from typing import Any


def adapt_item(payload: dict[str, Any], category: str | None = None) -> dict[str, Any] | None:
    if isinstance(payload.get('_raw_input'), dict):
        nested = adapt_item(payload['_raw_input'], category)
        if nested is not None:
            return nested
    if 'requisitos' in payload:
        return {**payload, 'categoria': payload.get('categoria') or category}
    key = next((k for k in ('requisitos_atomicos', 'criterios_comparacao', 'requisitos_tecnicos') if k in payload), None)
    if key is None:
        return None
    supplied = payload[key]
    criteria = []
    for i, entry in enumerate(supplied if isinstance(supplied, list) else []):
        rule = dict(entry) if isinstance(entry, dict) else {'texto_original': entry}
        rule['id'] = rule.get('id') or f'R{i + 1}'
        rule['atributo'] = rule.get('campo_normalizado') or rule.get('campo') or rule.get('atributo') or ''
        rule['operador'] = '==' if rule.get('operador', '=') == '=' else rule['operador']
        rule['obrigatorio'] = rule.get('obrigatorio', True)
        if not rule.get('unidade'):
            rule.pop('unidade', None)
        criteria.append(rule)
    return {
        'categoria': (payload.get('item') or {}).get('categoria') or payload.get('categoria') or category,
        'requisitos': criteria,
        'exigir_evidencia': True,
        'conflitos_documentais': payload.get('conflitos_documentais') or payload.get('divergencias_documentais'),
        'requisitos_gerais_aplicaveis': payload.get('requisitos_gerais_aplicaveis'),
    }
