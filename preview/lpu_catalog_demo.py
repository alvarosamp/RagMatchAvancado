"""Populate only explicitly named demo records in the localhost preview."""
import argparse
import json
from pathlib import Path
from urllib.parse import urlparse
import requests
from app.services.catalog_lpu_specification import refresh_lpu_specification

parser = argparse.ArgumentParser()
parser.add_argument('--base', default='http://localhost:8000')
parser.add_argument('--sources', required=True)
parser.add_argument('--output', required=True)
args = parser.parse_args()
if urlparse(args.base).hostname not in ('localhost', '127.0.0.1'):
    raise SystemExit('Demonstração permitida somente na prévia local.')
sources = json.loads(Path(args.sources).read_text())
api = requests.Session()
def req(method, path, **kwargs):
    r = api.request(method, args.base + path, timeout=45, **kwargs)
    r.raise_for_status()
    return r.json()
req('POST', '/auth/login', json={'email': 'alpha-admin@example.com', 'password': 'Quality-Test-Only-2026!'})

def ensure(table, column, value, values, update=False):
    filters = [{'column': column, 'op': 'eq', 'value': value}]
    if table == 'notice_products':
        filters.append({'column': 'notice_id', 'op': 'eq', 'value': values['notice_id']})
    rows = req('GET', '/crm/query/' + table, params={'filters': json.dumps(filters)})['data']
    if rows:
        if update:
            req('PATCH', '/crm/query/' + table, json={'filters': filters, 'values': values})
        return rows[0]
    return req('POST', '/crm/query/' + table + '/insert', json={'values': {column: value, **values}})['data'][0]

notice = ensure('notices', 'number', 'DEMO-LPU-JSON-2026',
                {'title': 'DEMONSTRAÇÃO — catálogo LPU e requisitos dos JSONs enviados'})
products = []
for p in sources['produtos']:
    sku = 'DEMO-LPU-' + p['id']
    description = p['descricoes_lpu'][0]
    fields = p['registros_tecnicos_lpu'][0]['campos']
    record = {'sku': sku, 'category': 'switch', 'description': description,
              'brand': p['marca'], 'model': p['part_number_fabricante'],
              'manufacturer_part_number': p['part_number_fabricante'],
              'lpu_version': 'DEMO-LPU-2026-10-14',
              'lpu_drive_url': 'https://drive.google.com/DEMO-LPU-LOCAL'}
    sheet = refresh_lpu_specification(None, record, values=fields,
                sheet=p['registros_tecnicos_lpu'][0]['aba'], row=p['registros_tecnicos_lpu'][0]['linha'])
    product = ensure('catalog_products', 'sku', sku, {
        'name': 'DEMO LPU — ' + p['part_number_fabricante'],
        'model': p['part_number_fabricante'], 'brand': p['marca'], 'category': 'switch',
        'description': description, 'specification': sheet, 'notes': 'Demonstração local baseada na LPU; revisar datasheet.',
        'lpu_version': record['lpu_version'], 'lpu_drive_url': record['lpu_drive_url'],
    }, update=True)
    products.append({'id': product['id'], 'sku': sku, 'modelo': p['part_number_fabricante']})
    existing = req('GET', f"/crm/catalog-products/{product['id']}/datasheets")
    if p.get('pdf_demo') and not existing:
        pdf = Path(p['pdf_demo'])
        with pdf.open('rb') as f:
            req('POST', f"/crm/catalog-products/{product['id']}/datasheets",
                files={'file': (p['part_number_fabricante'].replace('/', '_') + '.pdf', f, 'application/pdf')})
items = []
for index, source in enumerate(sources['itens'], 1):
    raw = source['item']
    item = ensure('notice_products', 'description', raw['descricao_original'], {
        'notice_id': notice['id'], 'item_number': f'DEMO-{index}', 'category': 'switch',
        'quantity': 1, 'raw_payload': {**raw, 'schema_version': '7.4',
            'demo_origem': source['arquivo'], 'demo_quantidade': 'Uma unidade apenas para demonstração'},
        'bi_features': raw.get('caracteristicas_bi', {}),
    })
    items.append({'id': item['id'], 'numero': f'DEMO-{index}', 'arquivo_origem': source['arquivo']})
result = {'notice_id': notice['id'], 'itens': items, 'produtos': products,
          'url': 'http://localhost:13089/crm/editais/' + notice['id']}
Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2))
print(json.dumps(result, ensure_ascii=False))
