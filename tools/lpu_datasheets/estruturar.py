#!/usr/bin/env python3
"""Estrutura características e tabelas por regras, para revisão e filtro técnico sem IA."""
import argparse
import json
import re
import csv
from collections import Counter
from pathlib import Path
from coletar import norm, save_json


def slug(value):
    return re.sub(r'[^a-z0-9]+', '_', str(value).lower()).strip('_')


def numeric(value):
    if isinstance(value, dict):
        return {k: numeric(v) for k, v in value.items()}
    if isinstance(value, str) and re.fullmatch(r'[+-]?\d+(?:[.,]\d+)?', value.strip()):
        return float(value.strip().replace(',', '.'))
    return value


ALIASES = {
    'receiver_sensitivity': 'sensibilidade_rx', 'sensitivity': 'sensibilidade_rx',
    'output_optical_power': 'potencia_tx', 'average_output_power': 'potencia_tx',
    'optical_output_power': 'potencia_tx', 'transmitter_output_power': 'potencia_tx',
    'supply_voltage': 'tensao_alimentacao', 'power_supply_voltage': 'tensao_alimentacao',
    'power_consumption': 'consumo_potencia', 'power_dissipation': 'consumo_potencia',
    'operating_temperature': 'temperatura_operacao', 'operating_case_temperature': 'temperatura_operacao',
    'case_operating_temperature': 'temperatura_operacao', 'storage_temperature': 'temperatura_armazenamento',
    'center_wavelength': 'comprimento_onda', 'wavelength': 'comprimento_onda',
    'data_rate': 'taxa_dados', 'bit_rate': 'taxa_dados', 'extinction_ratio': 'razao_extincao',
    'dimensions': 'dimensoes', 'weight': 'peso', 'humidity': 'umidade',
}


def structured(product):
    features = []
    def add(name, value, unit, source, condition='', status='revisar_aplicabilidade'):
        features.append({'nome': name, 'valor': value, 'unidade': unit,
                         'chave_padronizada': ALIASES.get(name, name), 'valor_normalizado': numeric(value),
                         'condicao': condition, 'fonte': source, 'validacao': status})
    # LPU information remains explicitly separate from manufacturer validation.
    for values in product['dados_tecnicos_lpu']:
        for key, multiplier, unit in [('taxa', 1, 'Gbps'), ('distancia', 1, 'm')]:
            raw = values.get(key, '')
            match = re.fullmatch(r'\s*(\d+(?:[.,]\d+)?)\s*(G|M|km|m)\s*', raw, re.I)
            if match:
                number = float(match[1].replace(',', '.'))
                suffix = match[2]
                if key == 'taxa':
                    number *= 0.001 if suffix.upper() == 'M' else 1
                else:
                    number *= 1000 if suffix.lower() == 'km' else 1
                add('taxa_nominal' if key == 'taxa' else 'alcance_ou_comprimento', number, unit,
                    {'tipo': 'lpu', 'origens': product['origens_lpu'], 'evidencia': raw},
                    status='informado_na_lpu')
    # No interpretation from the part number: only explicit description values.
    for description in product['descricoes_lpu']:
        source = {'tipo': 'lpu', 'origens': product['origens_lpu'], 'evidencia': description}
        add('descricao_tecnica_original', description, None, source, status='informado_na_lpu')
        for format_name in ['QSFP-DD', 'QSFP28', 'QSFP+', 'SFP28', 'SFP+', 'XFP', 'SFP']:
            if re.search(r'(?<![A-Z0-9])' + re.escape(format_name) + r'(?![A-Z0-9+\-])', description, re.I):
                add('formato', format_name, None, source, status='informado_na_lpu')
        for match in re.finditer(r'(?:(Tx|Rx)\s*)?(\d{3,4}(?:\.\d+)?)\s*nm', description, re.I):
            name = 'comprimento_onda_' + (match[1].lower() if match[1] else 'nao_especificado')
            add(name, float(match[2]), 'nm', source, status='informado_na_lpu')
        for match in re.finditer(r'(\d+)\s*AWG', description, re.I):
            add('bitola', int(match[1]), 'AWG', source, status='informado_na_lpu')
        for match in re.finditer(r'(?<![\d/])(\d+(?:[.,]\d+)?)\s*(Gbps|Gb/s|Gbit/s|G\b|Mbps|Mb/s|Mbit/s)', description, re.I):
            number = float(match[1].replace(',', '.'))
            if match[2].upper().startswith('M'):
                number /= 1000
            add('taxa_mencionada', number, 'Gbps', source,
                condition='taxa citada na descrição; conferir taxa nominal e taxas suportadas', status='informado_na_lpu')
        for match in re.finditer(r'(\d+(?:[.,]\d+)?)\s*(km|metros?|m\b)', description, re.I):
            number = float(match[1].replace(',', '.')) * (1000 if match[2].lower() == 'km' else 1)
            add('alcance_ou_comprimento', number, 'm', source, status='informado_na_lpu')
        for match in re.finditer(r'(?<![\d])(-?\d+(?:\.\d+)?)\s*(?:~|a|to)\s*([+-]?\d+(?:\.\d+)?)\s*[˚°º]?\s*C\b', description, re.I):
            add('temperatura_faixa_citada', {'minimo': float(match[1]), 'maximo': float(match[2])}, '°C', source,
                condition='faixa citada; conferir se operação, armazenamento ou temperatura do encapsulamento', status='informado_na_lpu')
        for match in re.finditer(r'(\d+)\s*[x×]\s*((?:\d+(?:\.\d+)?(?:\s*[GM])?\s*/)*\d+(?:\.\d+)?\s*[GM])\s*(RJ45|SFP28|SFP\+?|QSFP28|QSFP\+?)(?:\s*(PoE\+\+?|PoE))?', description, re.I):
            add('grupo_portas', {'quantidade': int(match[1]), 'taxas_texto': match[2],
                                'tipo': match[3], 'poe_texto': match[4]}, None, source, status='informado_na_lpu')
        for label, pattern in [('conector', r'\b(?:RJ45|LC|SC|MPO|MTP)\b'),
                               ('fibra', r'\b(?:SMF|MMF|single.mode|multi.mode|single.fiber|dual.fiber)\b'),
                               ('poe', r'\bPoE(?:\+\+|\+)?'),
                               ('padrao', r'\b(?:IEEE\s*)?802\.\d+[a-z]*(?:/\d+[a-z]*)?'),
                               ('gerenciamento', r'\b(?:L2\+?|L3|fanless|gerenciável|manageable)\b')]:
            for match in re.finditer(pattern, description, re.I):
                add(label, match[0], None, source, status='informado_na_lpu')
    for values in product['dados_tecnicos_lpu']:
        if values.get('versao'):
            add('versao_informada', values['versao'], None,
                {'tipo': 'lpu', 'origens': product['origens_lpu'], 'evidencia': values['versao']}, status='informado_na_lpu')
    ids = [product['part_number_fabricante']] if product['part_number_fabricante'] else product['codigos_tor']
    ids = {norm(x) for x in ids if x}
    for document in product['transcricao_integral']:
        for page in document['paginas']:
            base = {'tipo': 'datasheet', 'documento_sha256': document['documento_sha256'], 'pagina': page['pagina']}
            # Preserve every named parameter, all limits, symbols, units and notes.
            for table_number, table in enumerate(page['tabelas'], 1):
                if not table or len(table) < 2:
                    continue
                header = [str(x or '').strip() for x in table[0]]
                if len(header) < 2 or not any(header):
                    continue
                is_models = any(norm(x) in ('PARTNUMBER', 'MODEL', 'MODELS', 'PN') for x in header)
                for row_number, row in enumerate(table[1:], 2):
                    cells = [str(x or '').strip() for x in row]
                    if not cells or not any(cells):
                        continue
                    if is_models:
                        if norm(cells[0]) not in ids:
                            continue
                        for index, value in enumerate(cells[1:], 1):
                            if value and index < len(header):
                                add(slug(header[index]), value, None,
                                    dict(base, tabela=table_number, linha=row_number, evidencia=cells),
                                    condition='linha do identificador exato; revisar versão e região')
                    elif cells[0] and len(cells[0]) < 160 and any(cells[1:]):
                        named = {header[i] or f'coluna_{i+1}': val for i, val in enumerate(cells) if i and i < len(header) and val}
                        # Repeated header names remain losslessly available in original tables.
                        add(slug(cells[0]), named, named.get('Unit') or named.get('Units'),
                            dict(base, tabela=table_number, linha=row_number, evidencia=cells),
                            condition='tabela do documento; validar coluna, variante, condições e notas')
            # Bullets preserve technical conditions as written, never infer absent values.
            for line_number, line in enumerate(page['texto'].splitlines(), 1):
                line = line.strip()
                if re.match(r'^[•●⚫◆\u2022]\s*\S', line):
                    add('caracteristica_textual', line.lstrip('•●⚫◆ ').strip(), None,
                        dict(base, linha_texto=line_number, evidencia=line))
    # Deduplicate full records; distinct source/condition/value remain distinct.
    unique = {json.dumps(f, sort_keys=True, ensure_ascii=False): f for f in features}
    product['especificacoes_tecnicas'] = list(unique.values())
    product['fonte_principal_especificacoes'] = 'datasheet_e_lpu' if product['datasheets'] else 'lpu'
    product['fallback_lpu'] = not bool(product['datasheets'])
    product['descricao_original_preservada'] = True
    product['completude'] = 'Todos os dados técnicos disponíveis na LPU preservados; completude do fabricante não garantida.'
    product['especificacoes_normalizadas_status'] = 'extraidas_por_regras_revisao_tecnica_pendente'
    product['uso_no_filtro'] = {
        'metodo': 'comparacao_manual_ou_regras_sem_IA',
        'regra': 'Não tratar característica ausente como falsa ou zero. Validar aplicabilidade antes de filtrar.',
        'campos_validados': [],
        'criterios_a_revisar': ['modelo/revisão/região', 'quantidades e tipos de portas', 'taxas e protocolos',
                              'alcance e fibra', 'Tx/Rx e potência óptica', 'sensibilidade e orçamento óptico',
                              'alimentação e consumo', 'PoE', 'dimensões e peso', 'temperatura e umidade',
                              'recursos L2/L3, gerenciamento e segurança', 'padrões e certificações'],
    }
    return product


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    folder = Path(args.output)
    count = 0
    report = []
    origin_counts = Counter()
    empty = []
    for file in sorted((folder / 'produtos').glob('*.json')):
        product = structured(json.loads(file.read_text(encoding='utf-8')))
        count += len(product['especificacoes_tecnicas'])
        save_json(file, product)
        origin_counts[product['fonte_principal_especificacoes']] += 1
        if not product['especificacoes_tecnicas']:
            empty.append(product['id'])
        report.append({'id': product['id'], 'marca': product['marca'],
                       'part_number': product['part_number_fabricante'],
                       'codigos_tor': ';'.join(product['codigos_tor']), 'status': product['status'],
                       'fonte_principal': product['fonte_principal_especificacoes'],
                       'fallback_lpu': product['fallback_lpu'],
                       'caracteristicas': len(product['especificacoes_tecnicas']),
                       'datasheets': len(product['datasheets']),
                       'json': 'produtos/' + file.name})
    with (folder / 'relatorio.csv').open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=list(report[0]) if report else ['id'])
        writer.writeheader()
        writer.writerows(report)
    summary = json.loads((folder / 'resumo.json').read_text(encoding='utf-8'))
    summary.update(produtos=len(report), status=dict(Counter(x['status'] for x in report)),
                   fontes_principais=dict(origin_counts), caracteristicas_extraidas=count,
                   produtos_sem_caracteristicas_na_lpu_ou_ficha=empty)
    save_json(folder / 'resumo.json', summary)
    print(f'{count} características transcritas por regras; validação técnica pendente.')
