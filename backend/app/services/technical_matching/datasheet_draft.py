"""Conservative, unreviewed suggestions from explicit datasheet labels."""
import hashlib
import re

PATTERNS = {
    'poe_budget_w': (r'(?:PoE\s+(?:power\s+)?budget|or[cç]amento\s+(?:de\s+)?PoE)\s*[:=]\s*(\d+(?:[.,]\d+)?)\s*W\b', 'W'),
    'portas_rj45': (r'(?:RJ45\s+ports|portas\s+RJ45)\s*[:=]\s*(\d+)\b(?![.,]\d)', None),
    'portas_sfp_plus': (r'(?:SFP\+\s+ports|portas\s+SFP\+)\s*[:=]\s*(\d+)\b(?![.,]\d)', None),
    'portas_sfp': (r'(?:SFP\s+ports|portas\s+SFP)\s*[:=]\s*(\d+)\b(?![.,]\d)', None),
    'capacidade_comutacao_gbps': (r'(?:switching\s+capacity|capacidade\s+(?:de\s+)?comuta[cç][aã]o)\s*[:=]\s*(\d+(?:[.,]\d+)?)\s*Gbps\b', 'Gbps'),
}


def draft_from_pages(pages, *, document_id, document_hash, document_version):
    attributes, conflicts = {}, []
    for name, (pattern, unit) in PATTERNS.items():
        found = []
        for page, text in enumerate(pages, start=1):
            for line in text.splitlines():
                for match in re.finditer(pattern, line, re.IGNORECASE):
                    value = float(match[1].replace(',', '.'))
                    if value.is_integer(): value = int(value)
                    found.append((value, {'documento_id': document_id, 'hash_documento': document_hash,
                                         'versao_documento': document_version, 'pagina': page,
                                         'trecho': line.strip(), 'revisado': False}))
        if not found:
            continue
        if len({value for value, _ in found}) > 1:
            conflicts.append({'atributo': name, 'motivo': 'Valores divergentes no documento', 'valores': [v for v, _ in found]})
            continue
        attributes[name] = {'valor': found[0][0], 'evidencias': [e for _, e in found], **({'unidade': unit} if unit else {})}
    return {'atributos': attributes, 'conflitos': conflicts, 'status': 'REVISAO_NECESSARIA'}


def extract_draft(path, *, document_id, document_version):
    from pypdf import PdfReader
    raw = path.read_bytes()
    reader = PdfReader(path)
    return draft_from_pages([page.extract_text() or '' for page in reader.pages], document_id=document_id,
                            document_hash=hashlib.sha256(raw).hexdigest(), document_version=document_version)
