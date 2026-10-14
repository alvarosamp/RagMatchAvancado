"""Conservative compatibility view for legacy text and generated product archives."""
import copy
import json
from app.services.catalog_identity import product_category
from app.services.technical_matching.normalizer import canonical_name
from app.services.catalog_lpu_specification import refresh_lpu_specification
from app.services.catalog_json_import import merge_specification


def effective_sheet(product):
    raw = product.specification
    try:
        sheet = json.loads(raw or '{}', parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Número não finito')))
    except (ValueError, TypeError):
        sheet = {'descricao_anterior': raw} if raw else {}
    sheet = copy.deepcopy(sheet) if isinstance(sheet, dict) else {}
    category = product_category(product.category, product.description, getattr(product, 'model', None))
    if not isinstance(sheet.get('atributos'), dict):
        sheet['atributos'] = {}
    if product.description:
        # Fallback facts are sourced from the product itself, never the notice.
        record = {'sku': product.sku, 'category': category, 'description': product.description,
                  'brand': getattr(product, 'brand', None), 'model': getattr(product, 'model', None), 'manufacturer_part_number': getattr(product, 'manufacturer_part_number', None),
                  'lpu_drive_url': getattr(product, 'lpu_drive_url', None), 'lpu_version': getattr(product, 'lpu_version', None)}
        # Preserve existing generated attributes; compatibility view only fills absent fields.
        extra = json.loads(refresh_lpu_specification(None, record, values={}, sheet='Cadastro legado', row=0))
        protected = {canonical_name(key) for key in sheet['atributos']}
        for key, value in extra['atributos'].items():
            if canonical_name(key) in protected:
                continue
            if not getattr(product, 'lpu_version', None):
                value['origem']['tipo'] = 'cadastro'
            sheet['atributos'].setdefault(key, value)
    archive = sheet.get('importacao_json_produto')
    if isinstance(archive, dict) and isinstance(archive.get('especificacoes_tecnicas'), list):
        # LPU facts are usable; archive tables of uncertain scope remain separately reviewable.
        sheet = json.loads(merge_specification(json.dumps(sheet), archive))
    sheet.setdefault('categoria', category)
    return sheet
