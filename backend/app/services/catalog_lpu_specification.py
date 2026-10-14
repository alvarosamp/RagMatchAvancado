"""Refresh commercial LPU facts without replacing reviewed datasheet attributes."""
from __future__ import annotations

import json
import re
from typing import Any
from app.services.technical_matching.normalizer import canonical_name

GENERATOR = 'catalog_lpu_import_v1'


def refresh_lpu_specification(existing: Any, record: dict, *, values: dict,
                              sheet: str, row: int) -> str:
    try:
        payload = json.loads(existing) if isinstance(existing, str) else existing
    except (TypeError, ValueError):
        payload = None
    payload = dict(payload) if isinstance(payload, dict) else {}
    attrs = dict(payload.get('atributos') or {}) if isinstance(payload.get('atributos'), dict) else {}
    # Remove only our generated facts, including facts no longer present in the LPU.
    attrs = {k: v for k, v in attrs.items()
             if not (isinstance(v, dict) and v.get('gerado_por') == GENERATOR
                     and v.get('validacao') == 'informado_na_lpu')}
    generated = {}
    description = record['description']
    source = {'tipo': 'lpu', 'drive_url': record['lpu_drive_url'],
              'versao': record['lpu_version'], 'aba': sheet, 'linha': row}

    def add(name, value, unit=None, excerpt=None):
        generated[name] = {'valor': value, 'unidade': unit, 'origem': {**source, 'trecho': excerpt or description},
                           'gerado_por': GENERATOR, 'validacao': 'informado_na_lpu',
                           'evidencias': []}

    for suffix, name in [(r'RJ[- ]?45', 'portas_rj45'), (r'SFP\+(?!\+)', 'portas_sfp_plus'),
                         (r'SFP(?!\+|\d)', 'portas_sfp'), (r'SFP28', 'portas_sfp28'),
                         (r'QSFP28', 'portas_qsfp28')]:
        numbers = {int(v) for v in re.findall(
            r'\b(\d+)\s*[x×]\s*\d+(?:[.,]\d+)?[MG]?(?:/\d+(?:[.,]\d+)?[MG]?)*\s*' + suffix + r'(?!\w)', description, re.I)}
        if len(numbers) == 1:
            add(name, numbers.pop())
    layers = set(re.findall(r'\bL([23])\b', description, re.I))
    if len(layers) == 1:
        add('camada', 'L' + layers.pop())
    if re.search(r'\b(?:n[ãa]o\s+gerenci[áa]vel|unmanaged)\b', description, re.I):
        add('gerenciavel', False)
    elif re.search(r'\b(?:gerenci[áa]vel|manageable|managed)\b', description, re.I):
        add('gerenciavel', True)
    # Unspecified support remains unknown; absence is never a negative fact.
    if re.search(r'\b(?:sem|n[ãa]o(?:\s+suporta)?)\s+PoE\b', description, re.I):
        add('poe', False)
    elif re.search(r'\bPoE(?:\+)?\b', description, re.I):
        add('poe', True)
    for key in ('distancia', 'distance'):
        raw = str(values.get(key) or '').strip()
        match = re.fullmatch(r'(\d+(?:[.,]\d+)?)\s*(km|m)', raw, re.I)
        if match:
            add('alcance_m', float(match[1].replace(',', '.')) * (1000 if match[2].lower() == 'km' else 1), 'm', raw)
            break
    # Generated values are fallback only. Documented/manual fields take precedence.
    protected_names = {canonical_name(name) for name in attrs}
    for name, value in generated.items():
        if canonical_name(name) not in protected_names:
            attrs[name] = value
    payload.setdefault('schema_version', '1.0')
    payload.update(sku=record['sku'], categoria=record['category'], atributos=attrs)
    payload['dados_lpu'] = {**source, 'descricao_original': description,
                           'marca': record.get('brand'), 'modelo': record.get('model'),
                           'part_number_fabricante': record.get('manufacturer_part_number'),
                           'campos_originais': values, 'atributos_extraidos': generated}
    return json.dumps(payload, ensure_ascii=False, default=str)
