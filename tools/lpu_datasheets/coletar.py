#!/usr/bin/env python3
"""Inventário LPU + coleta oficial/local + transcrição auditável, sem chave de API."""
import argparse
import csv
import hashlib
import json
import re
import shutil
import time
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse, quote
from urllib.request import Request, urlopen

import openpyxl
from pypdf import PdfReader


def norm(value):
    return re.sub(r'[^A-Z0-9]', '', unicodedata.normalize('NFKD', str(value or '')).upper())


def clean(value):
    if value is None or str(value).strip() in ('', '-', '#REF!', '#N/A'):
        return None
    return str(value).strip()


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    temp.replace(path)


def inventory(path):
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    products, ignored = {}, []
    for sheet in workbook:
        header = None
        for row_number, row in enumerate(sheet.values, 1):
            names = [norm(v) for v in row]
            if ('PNTOR' in names or 'PARTNUMBER' in names) and any(x in names for x in ('DESCRIPTION', 'DESCRICAO')):
                header = {v: i for i, v in enumerate(names) if v}
                continue
            if header is None or not any(v is not None for v in row):
                continue
            def get(*keys):
                return next((clean(row[header[k]]) for k in keys if k in header and clean(row[header[k]])), None)
            tor = get('PNTOR')
            mfr = get('PARTNOMFR', 'PARTNO', 'PARTNUMBER')
            description = get('DESCRIPTION', 'DESCRICAO')
            brand = get('MARCA') or ('RAISECOM' if 'Raisecom' in sheet.title else None)
            if not (tor or mfr) or not brand:
                ignored.append({'aba': sheet.title, 'linha': row_number, 'motivo': 'sem marca ou identificador'})
                continue
            if not description and not re.search(r'\d', mfr or tor or ''):
                ignored.append({'aba': sheet.title, 'linha': row_number, 'motivo': 'cabeçalho de seção, sem código de produto ou descrição'})
                continue
            # Only punctuation is normalized. X/C, AC/DC, length and revision remain distinct.
            key = norm(brand) + ':' + norm(mfr or tor)
            if key not in products:
                label = re.sub(r'[^A-Za-z0-9_-]+', '_', mfr or tor).strip('_')[:110]
                products[key] = {
                    'id': norm(brand) + '_' + label + '_' + hashlib.sha256(key.encode()).hexdigest()[:8],
                    'marca': brand, 'part_number_fabricante': mfr, 'codigos_tor': [],
                    'descricoes_lpu': [], 'origens_lpu': [], 'dados_tecnicos_lpu': [],
                    'registros_tecnicos_lpu': [],
                }
            p = products[key]
            if tor and tor not in p['codigos_tor']:
                p['codigos_tor'].append(tor)
            if description and description not in p['descricoes_lpu']:
                p['descricoes_lpu'].append(description)
            p['origens_lpu'].append({'arquivo': str(path.resolve()), 'aba': sheet.title, 'linha': row_number})
            p['registros_tecnicos_lpu'].append({
                'aba': sheet.title, 'linha': row_number,
                'campos': {k: clean(row[index]) for k, index in header.items() if k in {
                    'MARCA', 'PNTOR', 'SIMILAR', 'DESCRIPTION', 'DESCRICAO', 'TAXA', 'RATE',
                    'DISTANCIA', 'DISTANCE', 'PARTNOMFR', 'PARTNO', 'PARTNUMBER', 'FORN', 'VERSIONS',
                }},
            })
            technical = {k: get(*keys) for k, keys in {
                'taxa': ('TAXA', 'RATE'), 'distancia': ('DISTANCIA', 'DISTANCE'),
                'fornecedor': ('FORN',), 'versao': ('VERSIONS',),
            }.items() if get(*keys)}
            if technical and technical not in p['dados_tecnicos_lpu']:
                p['dados_tecnicos_lpu'].append(technical)
    workbook.close()
    return list(products.values()), ignored


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.links.extend(v for k, v in attrs if k == 'href' and v)


ALLOWED = ('tp-link.com', 'raisecom.com', 'raisecom.com.br', 'opticking.com', 'opticking.cn', 'precisionot.com', 'ui.com', 'tor.tec.br', 'omadanetworks.com', 'assets.belden.com')


def official(url):
    parsed = urlparse(url)
    host = (parsed.hostname or '').lower()
    return parsed.scheme in ('http', 'https') and any(host == d or host.endswith('.' + d) for d in ALLOWED)


def technical_pdf_url(url):
    path = urlparse(url).path.lower()
    return '.pdf' in path and not any(word in path for word in (
        'configuration-guide', 'configuration_guide', 'user-guide', 'user_guide',
        'installation-guide', 'installation_guide', 'quick-install', 'declaration',
        'license', 'gpl', 'configuracao', 'certification', 'compliance', 'leaflet',
    ))


def fetch(url):
    if not official(url):
        raise ValueError('Somente domínios oficiais permitidos: ' + url)
    request = Request(url, headers={'User-Agent': 'LPU-Datasheet-Collector/1.0'})
    with urlopen(request, timeout=30) as response:
        if not official(response.url):
            raise ValueError('Redirecionamento fora dos domínios oficiais')
        data = response.read(40 * 1024 * 1024 + 1)
        if len(data) > 40 * 1024 * 1024:
            raise ValueError('Documento excede 40 MB')
        return data, response.url


def download_sources(out, urls, errors):
    result = []
    seen = set()
    queue = list(urls)
    # Landing pages are expanded only one level to avoid crawling the whole website.
    for url in queue:
        if url in seen:
            continue
        seen.add(url)
        try:
            url_id = hashlib.sha256(url.encode()).hexdigest()[:16]
            cached = out / 'cache_web' / (url_id + '.json')
            if cached.exists():
                saved = json.loads(cached.read_text())
                if Path(saved['arquivo']).exists():
                    result.append(saved)
                    continue
            data, final = fetch(url)
            if data.startswith(b'%PDF-'):
                sha = hashlib.sha256(data).hexdigest()
                target = out / 'datasheets' / (sha + '.pdf')
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                entry = {'arquivo': str(target.resolve()), 'url': final, 'tipo_origem': 'site_oficial', 'sha256': sha}
                save_json(cached, entry)
                result.append(entry)
            else:
                parser = Links()
                parser.feed(data.decode('utf-8', errors='replace'))
                for href in parser.links:
                    absolute = urljoin(final, href)
                    if technical_pdf_url(absolute) and official(absolute) and absolute not in seen:
                        queue.append(absolute)
            time.sleep(0.25)
        except Exception as exc:
            errors.append({'fonte': url, 'erro': str(exc)})
    return result


def pdf_document(path, out, origin):
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    cached = out / 'documentos' / (sha + '.json')
    if cached.exists():
        doc = json.loads(cached.read_text(encoding='utf-8'))
        doc['origens'] = [origin]
        if doc.get('extracao_texto') != 'plain_v1':
            reader = PdfReader(path)
            for i, page in enumerate(reader.pages):
                doc['paginas'][i]['texto'] = page.extract_text() or ''
            doc['extracao_texto'] = 'plain_v1'
            doc['ocr_necessario'] = any(len(p['texto'].strip()) < 30 for p in doc['paginas'])
            save_json(cached, doc)
        return doc
    reader = PdfReader(path)
    pages = []
    for i, page in enumerate(reader.pages, 1):
        text = page.extract_text() or ''
        pages.append({'pagina': i, 'texto': text, 'tabelas': []})
    # Retain all tables, including multi-model matrices, without guessing a column.
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages):
            pages[i]['tabelas'] = page.extract_tables() or []
    doc = {'sha256': sha, 'origens': [origin], 'paginas': pages,
           'extracao_texto': 'plain_v1',
           'ocr_necessario': any(len(p['texto'].strip()) < 30 for p in pages),
           'escopo': 'documento_integral; pode incluir outros modelos e variantes'}
    save_json(cached, doc)
    return doc


def exact_pages(doc, identifiers):
    matches = []
    for p in doc['paginas']:
        for identifier in identifiers:
            # Punctuation variants accepted; additional alphanumeric suffixes rejected.
            chars = [re.escape(c) for c in norm(identifier)]
            if not chars:
                continue
            pattern = r'(?<![A-Za-z0-9])' + r'[\s_\-/]*'.join(chars) + r'(?![A-Za-z0-9]|[\-_/][A-Za-z0-9])'
            if re.search(pattern, p['texto'], re.I):
                matches.append({'pagina': p['pagina'], 'identificador': identifier})
    return matches


def process(args):
    out = Path(args.output).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    products, ignored = inventory(Path(args.xlsx))
    save_json(out / 'inventario.json', products)
    save_json(out / 'linhas_ignoradas.json', ignored)
    errors = []
    documents = {}
    sources = []
    if args.online:
        config = json.loads(Path(args.sources).read_text(encoding='utf-8'))
        sources.extend(download_sources(out, config.get('urls', []), errors))
        if args.precision:
            # URL convention observed on the manufacturer's website. A successful
            # download still needs exact identifier validation; guesses are never specs.
            from concurrent.futures import ThreadPoolExecutor
            urls = []
            for p in products:
                if norm(p['marca']) == 'PRECISION' and p['part_number_fabricante']:
                    pn = quote(p['part_number_fabricante'], safe='-')
                    urls.extend('https://www.precisionot.com/wp-content/uploads/' + v + '.pdf' for v in (pn.lower(), pn))
            with ThreadPoolExecutor(max_workers=6) as pool:
                for found in pool.map(lambda u: download_sources(out, [u], errors), sorted(set(urls))):
                    sources.extend(found)
    for folder in args.local:
        root = Path(folder)
        paths = [root] if root.is_file() else sorted(root.rglob('*.pdf'))
        for path in paths:
            if out in path.resolve().parents:
                continue
            sources.append({'arquivo': str(path.resolve()), 'tipo_origem': 'arquivo_local_nao_autenticado', 'url': None})
    print(f'{len(products)} produtos únicos; {len(sources)} arquivos candidatos', flush=True)
    for i, source in enumerate(sources, 1):
        try:
            doc = pdf_document(Path(source['arquivo']), out, source)
            if doc['sha256'] in documents:
                documents[doc['sha256']]['origens'].append(source)
            else:
                documents[doc['sha256']] = doc
            if i % 10 == 0:
                print(f'PDFs processados: {i}/{len(sources)}', flush=True)
        except Exception as exc:
            errors.append({'fonte': source['arquivo'], 'erro': str(exc)})
    for sha, doc in documents.items():
        save_json(out / 'documentos' / (sha + '.json'), doc)
    summary = []
    for product in products:
        identifiers = [product['part_number_fabricante']] if product['part_number_fabricante'] else product['codigos_tor']
        related, candidates = [], []
        for sha, doc in documents.items():
            matches = exact_pages(doc, identifiers)
            alias_matches = exact_pages(doc, product['codigos_tor']) if not matches else []
            reference = {'sha256': sha, 'documento_json': 'documentos/' + sha + '.json',
                         'pdf_local': 'datasheets/' + sha + '.pdf',
                         'origens': doc['origens'], 'paginas_com_identificador': matches or alias_matches}
            if matches:
                # Identifier presence is evidence of coverage, not of complete specs.
                reference['validacao'] = 'identificador_exato_no_texto; revisar_escopo_e_versao'
                related.append(reference)
            elif alias_matches:
                reference['validacao'] = 'codigo_tor; confirmar_equivalencia_com_fabricante'
                candidates.append(reference)
        product['schema_version'] = '1.0'
        product['status'] = 'datasheet_localizado_revisar' if related else 'candidato_por_codigo_tor' if candidates else 'datasheet_nao_localizado'
        product['datasheets'] = related
        product['candidatos'] = candidates
        product['especificacoes_tecnicas'] = []
        # Deliberately do not map a family table or marketing sentence to a model field.
        product['especificacoes_normalizadas_status'] = 'pendente_de_extracao_por_modelo_e_validacao'
        product['transcricao_integral'] = [
            {'documento_sha256': r['sha256'], 'paginas': documents[r['sha256']]['paginas']}
            for r in related
        ]
        product['completude'] = 'nao_garantida; tabelas transcritas sem seleção automática de coluna/modelo; imagens exigem revisão/OCR'
        product['consulta_sugerida'] = f'"{product["part_number_fabricante"] or product["codigos_tor"][0]}" datasheet PDF'
        save_json(out / 'produtos' / (product['id'] + '.json'), product)
        summary.append({'id': product['id'], 'marca': product['marca'],
                        'part_number': product['part_number_fabricante'],
                        'codigos_tor': ';'.join(product['codigos_tor']), 'status': product['status'],
                        'datasheets': len(related), 'candidatos': len(candidates),
                        'json': 'produtos/' + product['id'] + '.json'})
    with (out / 'relatorio.csv').open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=list(summary[0]) if summary else ['id'])
        writer.writeheader()
        writer.writerows(summary)
    counts = dict(Counter(p['status'] for p in products))
    save_json(out / 'resumo.json', {'gerado_em_utc': datetime.now(timezone.utc).isoformat(),
                                  'produtos': len(products), 'documentos_unicos': len(documents),
                                  'status': counts, 'erros': len(errors),
                                  'observacao': 'Nenhum produto considerado completo automaticamente.'})
    save_json(out / 'erros.json', errors)
    save_json(out / 'pendencias.json', [p for p in summary if p['status'] != 'datasheet_localizado_revisar'])
    # Keep only PDFs actually referenced by products (including candidates).
    for sha, doc in documents.items():
        if any(sha == r['sha256'] for p in products for r in p['datasheets'] + p['candidatos']):
            target = out / 'datasheets' / (sha + '.pdf')
            target.parent.mkdir(exist_ok=True)
            if not target.exists():
                shutil.copy2(doc['origens'][0]['arquivo'], target)
    print(json.dumps(counts, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xlsx', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--local', action='append', default=[], help='Pasta de PDFs ou um PDF; pode repetir')
    parser.add_argument('--online', action='store_true', help='Baixa PDFs oficiais das URLs cadastradas')
    parser.add_argument('--precision', action='store_true', help='Tenta URLs de PDFs Precision por part number, sem IA')
    parser.add_argument('--sources', default=str(Path(__file__).with_name('fontes.json')))
    process(parser.parse_args())
