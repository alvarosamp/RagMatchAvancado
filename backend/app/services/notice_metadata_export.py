"""Read-only snapshot of an edital already stored in the CRM."""
from __future__ import annotations

import copy
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any


def _value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return copy.deepcopy(value)


def _fields(record: Any, names: str) -> dict[str, Any]:
    return {name: _value(getattr(record, name, None)) for name in names.split()}


def build_notice_metadata_export(notice, products, documents, analysis=None, *, include_text=False):
    items = []
    warnings = []
    for product in products:
        item = _fields(product, "id item_number lot product_code description category quantity unit "
                       "reference_price reference_total_price warranty delivery_deadline "
                       "technical_characteristics bi_features raw_payload risk_associated "
                       "brand_direction_exists brand_direction_model brand_direction_type "
                       "brand_direction_justification selected_for_dispute notes")
        raw = product.raw_payload if isinstance(product.raw_payload, dict) else {}
        raw = raw.get('_raw_input') if isinstance(raw.get('_raw_input'), dict) else raw
        keys = [key for key in ('requisitos', 'criterios_comparacao', 'requisitos_atomicos',
                                'requisitos_tecnicos') if key in raw]
        # Preserve the supplied representation, including explicit empty lists.
        item['criterios_originais'] = {key: copy.deepcopy(raw[key]) for key in keys}
        item['diagnostico'] = {'possui_criterios': any(bool(raw[key]) for key in keys),
                              'campos_criterios': keys,
                              'possui_payload_original': bool(raw)}
        if not item['diagnostico']['possui_criterios']:
            warnings.append({'item_id': product.id, 'codigo': 'SEM_CRITERIOS_ESTRUTURADOS',
                             'mensagem': 'Descrições e BI não comprovam requisitos completos do edital.'})
        items.append(item)

    source = None
    if analysis is not None:
        source = _fields(analysis, "id source_name source_kind source_hash schema_name schema_version "
                         "business_key status created_at updated_at result")
        source['texto_disponivel'] = bool(analysis.full_text)
        source['texto_incluido'] = bool(include_text and analysis.full_text)
        if include_text:
            source['texto_extraido'] = analysis.full_text
    else:
        warnings.append({'codigo': 'SEM_ANALISE_VINCULADA',
                         'mensagem': 'O CRM não possui JSON de análise vinculado a este edital.'})

    header = _fields(notice, "id number tor_id bid_number title stage outcome municipality_name state "
                     "modality auction_date uasg estimated_value address zipcode drive_link "
                     "proposal_validity document_delivery_moment analysis_status analysis_mode "
                     "analysis_confidence bi_item_summary bi_criterion bi_interval bi_exclusivity "
                     "bi_risk_identified bi_risk_operational bi_risk_documental bi_general_risks "
                     "particularities operational_checks import_batch_id analysis_document_id "
                     "created_at updated_at")
    # Linked records must belong to the same tenant too.
    for name, fields in [('organ', 'id name city state'), ('portal', 'id name url')]:
        record = getattr(notice, name, None)
        header[name] = _fields(record, fields) if record is not None and record.tenant_id == notice.tenant_id else None

    return {
        'metadados_exportacao': {'schema': 'tor.edital-metadata', 'schema_version': '1.0.0',
                                'gerado_em': datetime.now(timezone.utc).isoformat(),
                                'origem': 'crm', 'finalidade': 'inspecao_dos_dados_do_edital',
                                'extracao': 'dados_ja_armazenados', 'include_text': include_text},
        'edital': header, 'itens': items,
        'documentos': [_fields(doc, "id name category status is_required source_kind source_url "
                              "attached_document_file_id notes expires_at created_at updated_at") for doc in documents],
        'analise_original': source,
        'diagnostico': {'quantidade_itens': len(items), 'quantidade_documentos': len(documents),
                        'itens_com_criterios': sum(item['diagnostico']['possui_criterios'] for item in items),
                        'avisos': warnings},
    }
