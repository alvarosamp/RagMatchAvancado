"""Human controlled requirement mapping and progressive catalogue filtering."""
import copy
import hashlib
import json
import re

from app.services.technical_matching.adapter import adapt_item
from app.services.technical_matching.engine import compare_item_product, _hash
from app.services.technical_matching.normalizer import RULES, canonical_category, canonical_name

FIELD_LABELS = {
    'camada': 'Camada de rede', 'tecnologia_wifi': 'Padrão Wi-Fi', 'ambiente': 'Ambiente',
    'bandas_wifi': 'Bandas Wi-Fi', 'velocidade_wifi_mbps': 'Velocidade Wi-Fi',
    'portas_rj45': 'Portas RJ45', 'portas_sfp': 'Portas SFP', 'portas_sfp_plus': 'Portas SFP+',
    'gerenciavel': 'Gerenciável', 'poe': 'Suporte a PoE', 'poe_budget_w': 'Orçamento de PoE',
    'capacidade_comutacao_gbps': 'Capacidade de comutação', 'velocidade_uplink_mbps': 'Velocidade do uplink',
    'velocidades_porta_mbps': 'Velocidades das portas', 'alcance_m': 'Alcance',
    'conector': 'Conector', 'tipo_fibra': 'Tipo de fibra', 'temperatura_operacao_c': 'Temperatura de operação',
    'comprimento_onda_tx_nm': 'Comprimento de onda Tx', 'comprimento_onda_rx_nm': 'Comprimento de onda Rx',
}
CATEGORY_FIELDS = {
    'switch': ['camada', 'portas_rj45', 'portas_sfp', 'portas_sfp_plus', 'gerenciavel', 'poe', 'poe_budget_w',
               'capacidade_comutacao_gbps', 'velocidade_uplink_mbps', 'velocidades_porta_mbps', 'temperatura_operacao_c'],
    'access_point': ['tecnologia_wifi', 'ambiente', 'bandas_wifi', 'velocidade_wifi_mbps', 'poe', 'gerenciavel', 'temperatura_operacao_c'],
    'transceiver': ['alcance_m', 'conector', 'tipo_fibra', 'comprimento_onda_tx_nm', 'comprimento_onda_rx_nm',
                    'temperatura_operacao_c', 'velocidades_porta_mbps'],
}
OPERATORS = {'==', '>=', '<=', '>', '<', 'em', 'contem_todos', 'contem_algum', 'cobre_faixa'}


def parse_json(text):
    if not isinstance(text, str) or len(text.encode('utf-8')) > 1_000_000:
        raise ValueError('Use um JSON de até 1 MB.')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f'Chave JSON duplicada: {key}')
            result[key] = value
        return result
    def invalid(value):
        raise ValueError(f'Número JSON inválido: {value}')
    try:
        payload = json.loads(text, object_pairs_hook=unique, parse_constant=invalid)
    except (json.JSONDecodeError, RecursionError) as exc:
        raise ValueError('JSON inválido. Confira a sintaxe do arquivo.') from exc
    if not isinstance(payload, dict):
        raise ValueError('O arquivo deve conter um objeto JSON de um item.')
    return payload


def revision(item):
    return _hash({'raw': item.raw_payload, 'description': item.description,
                  'category': item.category, 'catalog_product_id': item.catalog_product_id})


def normalize_requirements(requirements):
    if isinstance(requirements, dict):
        requirements = [{**v, 'atributo': k} if isinstance(v, dict) else {'atributo': k, 'valor': v}
                        for k, v in requirements.items()]
    if not isinstance(requirements, list) or len(requirements) > 200:
        raise ValueError('Informe até 200 requisitos em uma lista ou objeto.')
    result, ids = [], set()
    for index, entry in enumerate(requirements):
        if not isinstance(entry, dict):
            raise ValueError('Cada requisito precisa ser um objeto JSON.')
        row = copy.deepcopy(entry)
        row['id'] = str(row.get('id') or f'R{index + 1}')
        if row['id'] in ids or len(row['id']) > 100:
            raise ValueError('Os identificadores dos requisitos precisam ser únicos e curtos.')
        ids.add(row['id'])
        name = row.get('campo_normalizado') or row.get('campo') or row.get('atributo') or ''
        if not isinstance(name, str):
            raise ValueError('O campo do requisito deve ser texto.')
        row['atributo'] = canonical_name(name)
        row['revisao_necessaria'] = row.get('revisao_necessaria') is True
        row['revisado'] = row.get('revisado') is True
        if row.get('motivo_revisao') is not None and not isinstance(row['motivo_revisao'], str):
            raise ValueError('O motivo de revisão deve ser texto.')
        # Keep original labels and text even when the human maps a field.
        row['texto_original'] = str(row.get('texto_original') or row.get('descricao') or name)
        row.pop('campo_normalizado', None)
        row.pop('campo', None)
        row['operador'] = '==' if row.get('operador', '==') == '=' else row.get('operador', '==')
        if row['operador'] is None:
            row['operador'] = 'nao_mapeado'
        if not isinstance(row['operador'], str):
            raise ValueError('O operador do requisito deve ser texto.')
        if row['operador'] not in OPERATORS:
            # Unsupported imported operators stay visible and pending in the engine.
            row['operador'] = str(row['operador'])
        if 'obrigatorio' not in row:
            row['obrigatorio'] = True
        if row.get('unidade') in ('', None):
            row.pop('unidade', None)
        result.append(row)
    return result


def import_item(payload, item, filename='JSON do item'):
    if 'itens' in payload:
        raise ValueError('Importe o JSON de um único item, exportado ao lado de Detalhes.')
    identity = payload.get('item') or {}
    if not isinstance(identity, dict):
        raise ValueError('A identificação do item deve ser um objeto.')
    if identity.get('id_interno') and str(identity['id_interno']) != item.id:
        raise ValueError('Esse JSON pertence a outro item. Exporte o item correto.')
    if identity.get('numero') and item.item_number and str(identity['numero']) != str(item.item_number):
        raise ValueError('O número do item no JSON é diferente do item selecionado.')
    adapted = adapt_item(payload, item.category) or {'categoria': identity.get('categoria'), 'requisitos': []}
    manual = payload.get('match_manual')
    if isinstance(manual, dict):
        adapted = manual
    rows = normalize_requirements(adapted.get('requisitos', []))
    pending = []
    for key in ('conflitos_documentais', 'divergencias_documentais', 'requisitos_gerais_aplicaveis'):
        if payload.get(key):
            pending.append({'campo': key, 'conteudo': payload[key]})
    if not isinstance(payload.get('obrigacoes_gerais') or {}, dict):
        raise ValueError('Obrigações gerais precisam ser um objeto.')
    suggestions = payload.get('sugestoes_bi', [])
    if not isinstance(suggestions, list) or len(suggestions) > 200 or any(not isinstance(r, dict) or not isinstance(r.get('campo'), str) or not isinstance(r.get('motivo', ''), str) for r in suggestions):
        raise ValueError('Sugestões BI precisam ser uma lista de até 200 campos.')
    return {'categoria': canonical_category(adapted.get('categoria') or identity.get('categoria')),
            'requisitos': rows, 'filtros': [], 'descricao_revisada': False,
            'fonte_json': {'arquivo': str(filename)[:200], 'hash': _hash(payload), 'payload': payload},
            'pendencias': pending, 'sugestoes_bi': copy.deepcopy(suggestions),
            'obrigacoes_gerais': copy.deepcopy(payload.get('obrigacoes_gerais') or {}), 'obrigacoes_revisadas': False}


def validate_state(state):
    if not isinstance(state, dict):
        raise ValueError('Configuração de match inválida.')
    # Reject non-finite values, deeply recursive objects and large drafts early.
    try:
        encoded = json.dumps(state, ensure_ascii=False, allow_nan=False)
    except (ValueError, TypeError, RecursionError) as exc:
        raise ValueError('Configuração JSON inválida.') from exc
    if len(encoded.encode()) > 1_500_000:
        raise ValueError('Configuração muito grande.')
    result = copy.deepcopy(state)
    result['categoria'] = canonical_category(result.get('categoria'))
    result['requisitos'] = normalize_requirements(result.get('requisitos', []))
    ids = {r['id'] for r in result['requisitos']}
    filters = result.get('filtros', [])
    if not isinstance(filters, list) or any(not isinstance(v, str) or v not in ids for v in filters):
        raise ValueError('Os filtros precisam referenciar requisitos existentes.')
    result['filtros'] = list(dict.fromkeys(filters))
    result['descricao_revisada'] = result.get('descricao_revisada') is True
    if not isinstance(result.get('obrigacoes_gerais', {}), dict):
        raise ValueError('Obrigações gerais precisam ser um objeto.')
    result['obrigacoes_revisadas'] = result.get('obrigacoes_revisadas') is True
    source = result.get('fonte_json')
    if source:
        if not isinstance(source, dict) or not isinstance(source.get('payload'), dict):
            raise ValueError('Fonte JSON inválida.')
        result['fonte_json']['hash'] = _hash(source['payload'])
        obligations = source['payload'].get('obrigacoes_gerais') or {}
        if not isinstance(obligations, dict):
            raise ValueError('Obrigações gerais precisam ser um objeto.')
        result['obrigacoes_gerais'] = copy.deepcopy(obligations)
        # Imported conflicts must not disappear when a filter checkbox is cleared.
        pending = []
        for key in ('conflitos_documentais', 'divergencias_documentais', 'requisitos_gerais_aplicaveis'):
            if source['payload'].get(key):
                pending.append({'campo': key, 'conteudo': source['payload'][key]})
        source_rows = source['payload'].get('requisitos_atomicos', [])
        if isinstance(source_rows, list):
            required_review = {r.get('id') for r in source_rows if isinstance(r, dict) and r.get('revisao_necessaria')}
            for row in result['requisitos']:
                if row['id'] in required_review:
                    row['revisao_necessaria'] = True
            for row in source_rows:
                if isinstance(row, dict) and row.get('revisao_necessaria') and row.get('id') not in ids:
                    pending.append({'id': row.get('id'), 'motivo': 'Ponto da descrição original removido; reimporte e revise o requisito.'})
        result['pendencias'] = pending
    else:
        result['pendencias'] = []
    return result


def catalog_payload(row, *, signals=False):
    try:
        def invalid_number(value):
            raise ValueError('Número inválido na ficha técnica')
        sheet = json.loads(row.specification or '{}', parse_constant=invalid_number)
    except (ValueError, TypeError, RecursionError):
        sheet = {}
    sheet = sheet if isinstance(sheet, dict) else {}
    attrs = copy.deepcopy(sheet.get('atributos', sheet))
    attrs = attrs if isinstance(attrs, dict) else {}
    if signals and not sheet:
        # These explicit commercial signals are useful for preselection, but
        # never become reviewed datasheet evidence or modify the catalogue.
        text = ' '.join([row.description or '', row.specification or ''])
        for suffix, name in [('RJ45', 'portas_rj45'), ('SFP\+', 'portas_sfp_plus'), ('SFP(?!\+)', 'portas_sfp')]:
            counts = set(int(v) for v in re.findall(r'\b(\d+)\s*[x×]\s*\d+(?:[.,]\d+)?[MG]?(?:/\d+(?:[.,]\d+)?[MG]?)*\s*' + suffix, text, re.I))
            if len(counts) == 1:
                attrs[name] = {'valor': counts.pop(), 'origem': 'Descrição comercial da LPU', 'evidencias': []}
        layers = set(re.findall(r'\bL([23])\b', text, re.I))
        if len(layers) == 1:
            attrs['camada'] = {'valor': 'L' + layers.pop(), 'origem': 'Descrição comercial da LPU', 'evidencias': []}
        managed = re.search(r'\b(?:gerenci[áa]vel|managed|manageable)\b', text, re.I)
        unmanaged = re.search(r'\b(?:n[ãa]o gerenci[áa]vel|unmanaged)\b', text, re.I)
        if managed or unmanaged:
            attrs['gerenciavel'] = {'valor': not bool(unmanaged), 'origem': 'Descrição comercial da LPU', 'evidencias': []}
        if re.search(r'\b(?:sem|n[ãa]o)\s+PoE\b', text, re.I):
            attrs['poe'] = {'valor': False, 'origem': 'Descrição comercial da LPU', 'evidencias': []}
        elif re.search(r'\bPoE(?:\+)?\b', text, re.I):
            attrs['poe'] = {'valor': True, 'origem': 'Descrição comercial da LPU', 'evidencias': []}
    return {'sku': row.sku, 'categoria': sheet.get('categoria') or row.category, 'atributos': attrs,
            'revisao': sheet.get('revisao'), 'variante': sheet.get('variante')}


def required_payload(state):
    rows = copy.deepcopy(state['requisitos'])
    if not state['descricao_revisada']:
        rows.append({'id': 'manual_review', 'atributo': 'revisao_do_item', 'operador': '==', 'valor': True,
                     'texto_original': 'Confira a descrição completa e os pontos do JSON.'})
    result = {'categoria': state['categoria'], 'requisitos': rows, 'exigir_evidencia': True}
    pending = list(state.get('pendencias') or [])
    if any(v not in (None, '', [], {}) for v in state.get('obrigacoes_gerais', {}).values()) and not state.get('obrigacoes_revisadas'):
        pending.append({'id': 'obligations_review', 'motivo': 'Confira garantia, entrega e obrigações gerais do item.'})
    pending.extend({'id': r['id'], 'motivo': 'Sugestão de requisito ainda não revisada.'}
                   for r in rows if r.get('revisao_necessaria') and r.get('revisado') is not True)
    if pending:
        result['conflitos_documentais'] = pending
    return result


def comparison(state, product):
    return compare_item_product(required_payload(state), product)


def display_attributes(attributes):
    """Use canonical keys in cards without collapsing conflicting source fields."""
    grouped = {}
    for name, value in attributes.items():
        grouped.setdefault(canonical_name(name), []).append(value)
    return {name: values[0] if len(values) == 1 else {
                'valor': 'Valores múltiplos; confira a matriz', 'campos_originais': values}
            for name, values in grouped.items()}


def preview(state, catalog, selected_id=None):
    state = validate_state(state)
    selected = set(state['filtros'])
    # Include siblings of an OR group rather than applying an arbitrary branch.
    groups = {r.get('grupo_logico') for r in state['requisitos'] if r['id'] in selected and r.get('grupo_logico')}
    chosen = [dict(r, obrigatorio=True) for r in state['requisitos']
              if r['id'] in selected or (r.get('grupo_logico') and r['grupo_logico'] in groups)]
    candidates, counts, selected_result = [], {'ATENDE': 0, 'VERIFICAR': 0, 'NAO_ATENDE': 0}, None
    category_counts = {}
    options = {}
    for row in catalog:
        product = catalog_payload(row, signals=True)
        category = canonical_category(product['categoria'])
        if category:
            category_counts[category] = category_counts.get(category, 0) + 1
        if not state['categoria'] or category != state['categoria']:
            continue
        filtered = compare_item_product({'categoria': state['categoria'], 'requisitos': chosen,
                                         'exigir_evidencia': False}, product) if chosen else {'status': 'ATENDE', 'detalhes': []}
        counts[filtered['status']] += 1
        for name, attribute in product['atributos'].items():
            value = attribute.get('valor') if isinstance(attribute, dict) else attribute
            if value is not None and isinstance(value, (str, bool, int, float)):
                options.setdefault(canonical_name(name), {})[json.dumps(value)] = value
        candidates.append({'id': row.id, 'nome': ' '.join(p for p in (row.brand, row.model) if p) or row.name,
                           'sku': row.sku, 'status_filtro': filtered['status'], 'atributos': display_attributes(product['atributos']),
                           'hash_catalogo': _hash(catalog_payload(row)),
                           'motivos': [d['motivo'] for d in filtered['detalhes'] if d['status'] != 'ATENDE'][:3]})
        if row.id == selected_id:
            selected_result = comparison(state, catalog_payload(row))
    priority = {'ATENDE': 0, 'VERIFICAR': 1, 'NAO_ATENDE': 2}
    candidates.sort(key=lambda c: (priority[c['status_filtro']], c['nome']))
    return {'state': state, 'categorias': category_counts, 'contagens': counts, 'candidatos': candidates,
            'opcoes': {name: list(values.values()) for name, values in options.items()},
            'comparacao': selected_result, 'filtros_efetivos': [r['id'] for r in chosen],
            'campos': [{'nome': name, 'rotulo': FIELD_LABELS.get(name, name), **definition}
                       for name, definition in RULES['attributes'].items()], 'campos_categoria': CATEGORY_FIELDS}
