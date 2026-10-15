"""Explicit, traceable extraction. Unsupported clauses are kept for human review."""
from __future__ import annotations

import hashlib
import math
import re
from io import BytesIO
from typing import Any

NUM = r'\d+(?:[.,]\d+)?'
PATTERNS = [
 ('portas_rj45', rf'(?P<v>{NUM})\s*(?:portas?\s*(?:de\s*)?)?(?:RJ[- ]?45|(?:10/100/1000|Gigabit)\s*(?:BASE-T)?\s+ports?)', None),
 ('portas_rj45', rf'(?:portas?\s+RJ[- ]?45|RJ[- ]?45\s+ports?)\s*[:=]\s*(?P<v>{NUM})', None),
 ('portas_sfp_plus', rf'(?P<v>{NUM})\s*(?:portas?|slots?|interfaces?)?\s*SFP\+(?!\+)', None),
 ('portas_sfp_plus', rf'(?:SFP\+\s+ports?|portas?\s+SFP\+)\s*[:=]\s*(?P<v>{NUM})', None),
 ('portas_sfp', rf'(?P<v>{NUM})\s*(?:portas?|slots?|interfaces?)?\s*SFP\b(?!\+|28)', None),
 ('portas_sfp', rf'(?:SFP\s+ports?|portas?\s+SFP)\s*[:=]\s*(?P<v>{NUM})', None),
 ('poe_budget_w', rf'(?:PoE\s+(?:power\s+)?budget|orçamento\s+(?:de\s+)?PoE|potência\s+(?:total\s+)?(?:de\s+)?PoE)\s*[:=]?\s*(?:mínim[oa]\s+(?:de\s+)?|no\s+mínimo\s+|acima\s+de\s+|até\s+)?(?P<v>{NUM})\s*W\b', 'W'),
 ('poe_budget_w', rf'PoE\s*(?:\+\+|\+)?\s*(?:de\s+)?(?P<v>{NUM})\s*W\b', 'W'),
 ('capacidade_comutacao_gbps', rf'(?:switching\s+capacity|capacidade\s+(?:de\s+)?(?:comutação|switching))\s*[:=]?\s*(?:mínima?\s+(?:de\s+)?|acima\s+de\s+|superior\s+a\s+|(?:no\s+)?mínimo\s+|(?:no\s+)?máximo\s+|de\s+)?(?P<v>{NUM})\s*(?P<u>[GM]bps)\b', 'Gbps'),
 ('alcance_m', rf'(?:alcance|reach|distance)\s*[:=]?\s*(?:mínimo\s+(?:de\s+)?|de\s+)?(?P<v>{NUM})\s*(?P<u>km|m)\b', 'm'),
 ('comprimento_onda_tx_nm', rf'(?:Tx|transmissão)\s*[:=]\s*(?P<v>{NUM})\s*nm\b', 'nm'),
 ('comprimento_onda_rx_nm', rf'(?:Rx|recepção)\s*[:=]\s*(?P<v>{NUM})\s*nm\b', 'nm'),
]
COMPLEX = re.compile(r'\b(?:ou|alternativamente|exceto|quando|caso|OM[1-5]|equivalente)\b', re.I)
LIMITS = [(r'(?:acima de|superior a|mais de)\s*$', '>'), (r'(?:inferior a|menos de)\s*$', '<'),
          (r'(?:mínim[oa]|no mínimo|pelo menos|minimum|at least)\s*(?:de)?\s*$', '>='),
          (r'(?:máxim[oa]|no máximo|até|maximum|at most|up to)\s*(?:de)?\s*$', '<=')]


def read_pdf(raw: bytes, filename: str, start: int = 1, end: int | None = None) -> dict[str, Any]:
    from pypdf import PdfReader
    from pypdf.errors import PyPdfError
    if not raw.startswith(b'%PDF-'):
        raise ValueError('O arquivo precisa ser um PDF válido.')
    try:
        reader = PdfReader(BytesIO(raw))
    except PyPdfError as exc:
        raise ValueError('Não foi possível ler o PDF. Confira se o arquivo está íntegro.') from exc
    if reader.is_encrypted:
        raise ValueError('PDF protegido por senha: envie uma cópia desbloqueada.')
    count = len(reader.pages)
    if count > 300:
        raise ValueError('PDF com mais de 300 páginas: selecione um arquivo menor.')
    last = count if end is None else end
    if start < 1 or last < start or last > count or last - start >= 80:
        raise ValueError('Selecione um intervalo válido de até 80 páginas.')
    try:
        pages = [{'pagina': n, 'texto': reader.pages[n-1].extract_text() or ''} for n in range(start, last+1)]
    except PyPdfError as exc:
        raise ValueError('Falha ao extrair as páginas do PDF.') from exc
    if sum(len(p['texto']) for p in pages) > 2_000_000:
        raise ValueError('Muito texto no intervalo selecionado. Reduza o número de páginas.')
    digest = hashlib.sha256(raw).hexdigest()
    return {'arquivo': filename, 'hash': digest, 'documento_id': 'preview-' + digest,
            'versao_documento': 1, 'total_paginas': count, 'paginas': pages}


def _operator(text: str, position: int) -> str:
    prefix = text[max(0, position-55):position]
    for pattern, op in LIMITS:
        if re.search(pattern, prefix, re.I):
            return op
    return '=='


def extract_document(source: dict[str, Any], *, offered: bool = False) -> dict[str, Any]:
    records, unresolved = [], []
    for page in source['paginas']:
        for line in page['texto'].splitlines():
            for clause in re.split(r';\s*', line):
                clause = clause.strip()
                if not clause:
                    continue
                identity = hashlib.sha256(f"{source['hash']}:{page['pagina']}:{clause}".encode()).hexdigest()[:20]
                if COMPLEX.search(clause):
                    unresolved.append({'id': identity, 'pagina': page['pagina'], 'trecho': clause,
                                       'motivo': 'Alternativas, condições ou escopos exigem análise explícita.'})
                    continue
                spans, local = [], []
                for name, pattern, unit in PATTERNS:
                    for match in re.finditer(pattern, clause, re.I):
                        if any(a <= match.start() < b for a, b in spans):
                            continue
                        if re.fullmatch(r'\d+[.,]\d{3}', match['v']):
                            unresolved.append({'id':identity,'pagina':page['pagina'],'trecho':clause,
                                               'motivo':'Separador numérico ambíguo: decimal ou milhar.'})
                            spans.append(match.span())
                            continue  # Decimal versus thousands separator is ambiguous.
                        value = float(match['v'].replace(',', '.'))
                        given_unit = match.groupdict().get('u')
                        if given_unit and given_unit.lower() == 'km': value *= 1000
                        if given_unit and given_unit.lower() == 'mbps' and unit == 'Gbps': value /= 1000
                        if not math.isfinite(value): continue
                        if value.is_integer(): value = int(value)
                        # Port counts are never rounded and invalid counts stay unresolved.
                        if name.startswith('portas_') and (not isinstance(value, int) or value < 0): continue
                        position = match.start('v')
                        op = _operator(clause, position)
                        # "capacidade mínima de 96" places the limit inside the matched label.
                        if op == '==':
                            for pat, candidate_op in LIMITS:
                                if re.search(pat, clause[:position], re.I): op = candidate_op; break
                        local.append((name, value, unit, op, match.span()))
                        spans.append(match.span())
                for name, pattern, positive, negative in [
                    ('gerenciavel', r'\b(?:não\s+gerenciável|nao\s+gerenciavel|unmanaged|gerenciável|gerenciavel|managed)\b', True, r'^(?:não|nao|unmanaged)'),
                    ('poe', r'\b(?:sem\s+PoE|não\s+(?:suporta\s+)?PoE|PoE(?:\+\+|\+)?)\b', True, r'^(?:sem|não)'),
                    ('tipo_fibra', r'\b(?:monomodo|multimodo|single.mode|multi.mode)\b', None, None),
                    ('conector', r'\b(?:conector|connector)\s*[:=]\s*(?:LC|SC|RJ45)\b', None, None),
                ]:
                    for match in re.finditer(pattern, clause, re.I):
                        if name == 'poe' and any(a <= match.start() < b for a, b in spans): continue
                        value = (not bool(re.search(negative, match[0], re.I))) if positive else match[0].split(':')[-1].split('=')[-1].strip().lower()
                        if name == 'tipo_fibra': value = 'monomodo' if value in ('monomodo','single-mode','single mode') else 'multimodo'
                        local.append((name, value, None, '==', match.span()));spans.append(match.span())
                for index, (name, value, unit, op, span) in enumerate(local):
                    evidence = {'documento_id': source['documento_id'], 'hash_documento': source['hash'],
                                'arquivo': source['arquivo'], 'versao_documento': source['versao_documento'],
                                'pagina': page['pagina'], 'trecho': clause, 'revisado': False}
                    records.append({'id': f'{identity}-{index}', 'campo_normalizado': name,
                                    'valor': value, 'unidade': unit, 'operador': '==' if offered else op,
                                    'obrigatorio': True, 'texto_original': clause, 'evidencias': [evidence]})
                residual = clause
                for a, b in sorted(spans, reverse=True): residual = residual[:a] + ' ' + residual[b:]
                residual = re.sub(r'\b(?:switch|portas?|ports?|de|do|da|a|o|e|com|no|pelo|menos|mínimo|mínima|máximo|máxima|minimum|maximum|at|least|most|acima|superior|inferior|mais|total|the|shall|have|must|budget)\b', '', residual, flags=re.I)
                if re.search(r'[\w]', residual):
                    unresolved.append({'id': identity, 'pagina': page['pagina'], 'trecho': clause,
                                       'motivo': 'Há conteúdo não convertido em atributo; confira o trecho completo.'})
    if not any(p['texto'].strip() for p in source['paginas']):
        unresolved.append({'id': 'sem-texto', 'pagina': None, 'trecho': '',
                           'motivo': 'PDF sem texto extraível. Precisa de OCR; nada foi presumido.'})
    return {'registros': records, 'pendencias': unresolved, 'fonte': source}


def compare_extractions(required, offered, review: dict[str, Any], *, category='switch'):
    from .engine import compare_item_product
    checked_requirements = set(review.get('requisitos', []))
    checked_attributes = set(review.get('atributos', []))
    reasons = review.get('descartes', {})
    if not isinstance(reasons, dict) or any(not isinstance(v, str) or (v.strip() and len(v.strip()) < 5) for v in reasons.values()):
        raise ValueError('Informe uma justificativa de pelo menos cinco caracteres para cada trecho descartado.')
    requirements, attributes = [], {}
    pending = []
    for row in required['registros']:
        rule = {**row, 'atributo': row['campo_normalizado']}
        if row['id'] not in checked_requirements:
            pending.append({'id': row['id'], 'motivo': 'Requisito extraído ainda não revisado.'})
        requirements.append(rule)
    by_attribute = {}
    for row in offered['registros']: by_attribute.setdefault(row['campo_normalizado'], []).append(row)
    conflicts = []
    for name, rows in by_attribute.items():
        # Choosing a value is allowed only from an extracted, hash-bound candidate.
        chosen_id = review.get('escolhas', {}).get(name)
        chosen = [r for r in rows if r['id'] == chosen_id] if chosen_id else rows
        values = {str(r['valor']) for r in chosen}
        if not chosen or len(values) != 1:
            conflicts.append({'atributo': name, 'candidatos': rows});continue
        value = chosen[0]
        evidences = [{**r['evidencias'][0], 'revisado': r['id'] in checked_attributes} for r in chosen]
        attributes[name] = {'valor': value['valor'], 'evidencias': evidences,
                            **({'unidade': value['unidade']} if value['unidade'] else {})}
        if not any(e['revisado'] for e in evidences):
            pending.append({'id': name, 'motivo': 'Valor do datasheet ainda não revisado.'})
    for row in [*required['pendencias'], *offered['pendencias']]:
        explicit_requirement = re.search(r'\b(?:obrigatório|obrigatoria|deverá|must|shall|required)\b', row.get('trecho',''), re.I)
        if not reasons.get(row['id']) or explicit_requirement or row.get('bloqueante'): pending.append(row)
    # Source provenance for triage descriptions cannot invent PDF page numbers.
    if any(e.get('pagina') is None for r in required['registros'] for e in r['evidencias']):
        pending.append({'id':'origem-sem-pagina','motivo':'Vincule o PDF do item para comprovar a página de origem.'})
    result = compare_item_product({'categoria': category, 'requisitos': requirements, 'exigir_evidencia': True},
                                  {'categoria': category, 'atributos': attributes})
    result['status_regras'] = result['status']
    verified_failure = any(d['status'] == 'NAO_ATENDE' and d.get('id') in checked_requirements
                           and any(e['revisado'] for e in attributes.get(d['atributo'], {}).get('evidencias', []))
                           for d in result['detalhes'])
    for detail in result['detalhes']:
        if detail['atributo'] == 'categoria':
            detail['status'] = 'CONTEXTO'
            detail['motivo'] = 'Categoria declarada para selecionar as regras; não extraída dos PDFs.'
            continue
        reviewed = detail.get('id') in checked_requirements and any(
            e['revisado'] for e in attributes.get(detail['atributo'], {}).get('evidencias', []))
        if not reviewed and detail['status'] != 'VERIFICAR':
            detail['status_calculado'] = detail['status']
            detail['status'] = 'VERIFICAR'
            detail['motivo'] = 'Aguardando revisão do requisito e da evidência documental.'
    technical_details = [d for d in result['detalhes'] if d['atributo'] != 'categoria']
    result['cobertura'] = sum(d['status'] != 'VERIFICAR' for d in technical_details) / max(1,len(technical_details))
    result['score'] = sum(d['status'] == 'ATENDE' for d in technical_details) / max(1,len(technical_details))
    if result['status'] == 'NAO_ATENDE' and not verified_failure: result['status'] = 'VERIFICAR'
    if (pending or conflicts) and result['status'] == 'ATENDE': result['status'] = 'VERIFICAR'
    result.update(preliminar=True, pendencias_extracao=pending, conflitos_datasheet=conflicts,
                  revisao=review, aviso='Prévia: não altera requisitos, fichas ou decisões confirmadas no CRM.')
    return result
