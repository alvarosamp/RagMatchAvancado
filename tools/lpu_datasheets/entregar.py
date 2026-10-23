#!/usr/bin/env python3
"""Empacota e verifica artefatos gerados, sem substituir uma entrega existente."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path
from coletar import save_json, technical_pdf_url

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--origem', required=True)
parser.add_argument('--destino', required=True)
parser.add_argument('--fontes-coletadas')
args = parser.parse_args()
origin = Path(args.origem).resolve()
target = Path(args.destino).resolve()
if target.exists():
    raise SystemExit('A pasta de entrega já existe; escolha outro destino para preservar os arquivos.')
shutil.copytree(origin, target, ignore=shutil.ignore_patterns('*.tmp', '__pycache__'))
shutil.copytree(Path(__file__).parent, target / 'scripts', ignore=shutil.ignore_patterns('__pycache__'))
if args.fontes_coletadas:
    shutil.copy2(args.fontes_coletadas, target / 'scripts' / 'fontes_coletadas.json')

def relocate(value):
    if isinstance(value, dict):
        return {k: relocate(v) for k, v in value.items()}
    if isinstance(value, list):
        return [relocate(v) for v in value]
    if isinstance(value, str) and value.startswith(str(origin) + '/'):
        return str(target) + value[len(str(origin)):]
    return value

for path in target.rglob('*.json'):
    data = relocate(json.loads(path.read_text(encoding='utf-8')))
    if path.parent.name == 'produtos':
        for reference in data['datasheets'] + data['candidatos']:
            reference['pdf_local'] = 'datasheets/' + reference['sha256'] + '.pdf'
    save_json(path, data)

# Exclude ancillary configuration manuals obtained before narrowing PDF discovery.
for path in (target / 'cache_web').glob('*.json'):
    entry = json.loads(path.read_text(encoding='utf-8'))
    if not technical_pdf_url(entry['url']):
        pdf = Path(entry['arquivo'])
        if pdf.is_relative_to(target) and pdf.exists():
            pdf.unlink()
        path.unlink()

inventory = json.loads((target / 'inventario.json').read_text(encoding='utf-8'))
files = list((target / 'produtos').glob('*.json'))
assert {p.stem for p in files} == {p['id'] for p in inventory}
originals = {p['id']: p for p in inventory}
checked_pdfs = set()
for path in files:
    p = json.loads(path.read_text(encoding='utf-8'))
    assert p['descricoes_lpu'] == originals[p['id']]['descricoes_lpu']
    assert p['registros_tecnicos_lpu'] == originals[p['id']]['registros_tecnicos_lpu']
    assert p['fallback_lpu'] == (not bool(p['datasheets']))
    for ref in p['datasheets'] + p['candidatos']:
        assert (target / ref['documento_json']).exists()
        pdf = target / ref['pdf_local']
        assert pdf.exists()
        if pdf not in checked_pdfs:
            assert hashlib.sha256(pdf.read_bytes()).hexdigest() == ref['sha256']
            checked_pdfs.add(pdf)
save_json(target / 'verificacao.json', {
    'jsons_individuais_validos': len(files),
    'identificadores_conferidos_com_inventario': True,
    'dados_tecnicos_lpu_preservados': True,
    'pdfs_referenciados_conferidos_sha256': len(checked_pdfs),
    'completude_tecnica': 'revisão manual necessária; fallback LPU identificado',
})
print(str(target))
print(f'{len(files)} JSONs individuais verificados; {len(checked_pdfs)} PDFs referenciados íntegros.')
