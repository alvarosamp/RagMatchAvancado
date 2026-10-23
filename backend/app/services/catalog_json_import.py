"""Import the generated product archive without trusting paths or review claims."""
import copy
import json
from app.services.technical_matching.normalizer import canonical_name

MARKER = 'catalog_product_json_v1'


def validate_product(value):
    if not isinstance(value, dict) or not isinstance(value.get('codigos_tor'), list):
        raise ValueError('Selecione um JSON de produto da pasta produtos (codigos_tor obrigatório).')
    json.dumps(value, allow_nan=False)
    for key in ('marca', 'part_number_fabricante'):
        if value.get(key) is not None and not isinstance(value[key], str):
            raise ValueError(f'{key} deve ser texto.')
    descriptions = value.get('descricoes_lpu', [])
    if not isinstance(descriptions, list) or any(not isinstance(text, str) for text in descriptions):
        raise ValueError('Descrições da LPU inválidas.')
    codes = value['codigos_tor']
    if not codes or len(codes) > 100 or any(not isinstance(c, str) or not c.strip() or len(c) > 200 for c in codes):
        raise ValueError('Códigos de produto inválidos.')
    if not isinstance(value.get('especificacoes_tecnicas'), list) or not isinstance(value.get('datasheets', []), list):
        raise ValueError('Lista de especificações ou datasheets inválida.')
    return list(dict.fromkeys(c.strip() for c in codes))


def merge_specification(existing, incoming):
    try:
        previous = json.loads(existing or '{}')
    except (ValueError, TypeError):
        previous = {'descricao_anterior': existing}
    result = copy.deepcopy(previous) if isinstance(previous, dict) else {}
    attrs = result.get('atributos')
    attrs = dict(attrs) if isinstance(attrs, dict) else {}
    attrs = {k: v for k, v in attrs.items() if not (isinstance(v, dict) and v.get('gerado_por') == MARKER and not v.get('revisado') and not v.get('evidencias'))}
    protected = {canonical_name(k) for k in attrs}
    for spec in incoming['especificacoes_tecnicas']:
        if not isinstance(spec, dict) or spec.get('validacao') != 'informado_na_lpu':
            continue
        name = spec.get('chave_padronizada') or spec.get('nome')
        value = spec.get('valor_normalizado', spec.get('valor'))
        if not isinstance(name, str) or not name or not isinstance(value, (str, int, float, bool)):
            continue
        if canonical_name(name) in protected:
            continue
        attrs[name] = {'valor': value, 'unidade': spec.get('unidade'), 'origem': spec.get('fonte'),
                       'validacao': 'informado_na_lpu', 'gerado_por': MARKER, 'revisado': False, 'evidencias': []}
        protected.add(canonical_name(name))
    result['atributos'] = attrs
    # Keep ALL source fields, tables and provenance available for technical review.
    result['importacao_json_produto'] = incoming
    return json.dumps(result, ensure_ascii=False, allow_nan=False)
