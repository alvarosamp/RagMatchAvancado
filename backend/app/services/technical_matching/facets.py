"""Category-aware facets with counts recalculated against the other filters."""
import json
import math
from .normalizer import RULES, canonical_name, canonical_category, normalize_value


def values_of(payload):
    attributes = payload.get('atributos', {})
    result = {}
    if not isinstance(attributes, dict):
        return result
    for name, entry in attributes.items():
        name = canonical_name(name)
        value = entry.get('valor') if isinstance(entry, dict) else entry
        values = value if isinstance(value, list) else [value]
        for value in values:
            if isinstance(value, float) and not math.isfinite(value):
                continue
            if value is not None and isinstance(value, (str, int, float, bool)):
                definition = RULES['attributes'].get(name)
                if definition:
                    try:
                        value = normalize_value({'valor': value, 'unidade': entry.get('unidade')} if isinstance(entry, dict) and entry.get('unidade') else value,
                                                kind=definition['type'], unit=definition.get('unit'))
                        if definition.get('integer') and (not float(value).is_integer() or value < definition.get('minimum', 0)):
                            continue
                    except (ValueError, TypeError, OverflowError):
                        continue
                if isinstance(value, float) and value.is_integer():
                    value = int(value)
                token = json.dumps(value, ensure_ascii=False, allow_nan=False)
                result.setdefault(name, set()).add(token)
    return result


def build_facets(item, products, filters=None):
    filters = filters or {}
    if not isinstance(filters, dict):
        raise ValueError('Filtros devem ser um objeto por atributo')
    selected = {}
    for name, values in filters.items():
        if not isinstance(name, str) or not isinstance(values, list) or any(isinstance(v, (dict, list)) for v in values):
            raise ValueError('Cada filtro deve conter uma lista de valores simples')
        selected[canonical_name(name)] = {json.dumps(v, ensure_ascii=False, allow_nan=False) for v in values}
    category = canonical_category(item.get('categoria'))
    pool = [(p, values_of(p)) for p in products if not category or canonical_category(p.get('categoria')) == category]
    def eligible(values, omit=None):
        return all(not options or bool(options.intersection(values.get(name, set()))) for name, options in selected.items() if name != omit)
    candidates = [p['id'] for p, values in pool if eligible(values)]
    facets = {}
    for _, values in pool:
        for name, tokens in values.items():
            if not eligible(values, omit=name):
                continue
            for token in tokens:
                facets.setdefault(name, {}).setdefault(token, 0)
                facets[name][token] += 1
    return {'categoria': category, 'total': len(pool), 'filtered_total': len(candidates), 'catalog_product_ids': candidates,
            'facets': {name: [{'value': json.loads(token), 'count': count} for token, count in sorted(options.items())] for name, options in sorted(facets.items())}}
