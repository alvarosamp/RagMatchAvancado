"""Deterministic suggestions from the original item text; always human reviewed.

BI is retained separately and never substitutes an explicit requirement. Unknown
clauses remain table rows instead of disappearing from the final comparison.
"""
from __future__ import annotations
import hashlib
import re
from app.services.technical_matching.normalizer import canonical_category

NUMBER = r'(?<![\d.,])\d+(?:[.,]\d+)?'
PATTERNS = [
 ('portas_acesso', rf'({NUMBER})\s*portas?\s+(?:10/100/1000|Gigabit\s+Ethernet)', None),
 ('portas_expansao', rf'({NUMBER})\s*portas?\s+(?:de\s+)?expans[ãa]o', None),
 ('velocidade_uplink_mbps', rf'({NUMBER})\s*Gigabit\s+Ethernet', 'Mbps'),
 ('portas_rj45', rf'({NUMBER})\s*(?:portas?\s*(?:Ethernet\s*)?)?RJ[- ]?45\b', None),
 ('portas_sfp_plus', rf'({NUMBER})\s*(?:portas?|slots?|uplinks?|interfaces?)?\s*SFP\+(?!\+)', None),
 ('velocidade_uplink_mbps', rf'(?:uplinks?\s+)?SFP\+\s*[/ ]?\s*({NUMBER})\s*(Gbps|G)\b(?![/\d])', 'Mbps'),
 ('portas_sfp', rf'({NUMBER})\s*(?:portas?|slots?|uplinks?|interfaces?)?\s*SFP\b(?!\+|\d)', None),
 ('portas_sfp28', rf'({NUMBER})\s*(?:portas?|slots?|uplinks?)?\s*SFP28\b', None),
 ('portas_qsfp28', rf'({NUMBER})\s*(?:portas?|slots?|uplinks?)?\s*QSFP28\b', None),
 ('capacidade_comutacao_gbps', rf'(?:backplane|capacidade\s+(?:de\s+)?comuta[çc][ãa]o)\s*(?:m[íi]nim[oa]\s*)?(?:de\s*)?({NUMBER})\s*(Gbps|Mbps)', 'Gbps'),
 ('poe_budget_w', rf'(?:or[çc]amento\s+(?:de\s+)?PoE|pot[êe]ncia\s+(?:total\s+)?(?:de\s+)?PoE)\s*(?:m[íi]nim[oa]\s*)?(?:de\s*)?({NUMBER})\s*W\b', 'W'),
 ('velocidade_wifi_mbps', rf'taxa\s+agregada\s*(?:m[íi]nima\s*)?(?:de\s*)?({NUMBER})\s*(Mbps|Gbps)', 'Mbps'),
 ('alcance_m', rf'alcance\s*(?:m[íi]nimo\s*)?(?:de\s*)?({NUMBER})\s*(km|m)\b', 'm'),
]
COMPLEX = re.compile(r'\b(?:ou|alternativamente|exceto|caso|quando|equivalente|breakout)\b', re.I)


def _number(text):
    # A dot followed by exactly three digits can mean decimal or thousands.
    # Keep that ambiguity visible, even in a Portuguese input.
    if re.fullmatch(r'\d+[.]\d{3}', text):
        raise ValueError('Separador numérico exige revisão: decimal ou milhar.')
    value = float(text.replace(',', '.'))
    return int(value) if value.is_integer() else value


def _operator(prefix):
    if re.search(r'(?:acima\s+de|superior\s+a|mais\s+de)\s*$', prefix, re.I):return '>'
    if re.search(r'(?:inferior\s+a|menos\s+de)\s*$', prefix, re.I):return '<'
    if re.search(r'(?:m[íi]nim[oa]|pelo\s+menos|no\s+m[íi]nimo)\s*(?:de\s*)?$', prefix, re.I):return '>='
    if re.search(r'(?:m[áa]xim[oa]|at[ée]|no\s+m[áa]ximo)\s*(?:de\s*)?$', prefix, re.I):return '<='
    return '=='


def suggest_requirements(description, category, origin, item_number):
    text = description.strip() if isinstance(description, str) else ''
    category = canonical_category(category)
    rows = []
    def add(clause, field='', value=None, unit=None, operator='nao_mapeado', reason=None, span=None):
        token = hashlib.sha256(f'{item_number}:{len(rows)}:{clause}:{field}'.encode()).hexdigest()[:14]
        rows.append({'id':'S-'+token,'campo_normalizado':field,'valor':value,'unidade':unit,
            'operador':operator,'obrigatorio':True,'texto_original':clause,
            'origem':{**origin,'trecho':clause,'campo_json':'descricao_original'},
            'derivado_de':'descricao_original','revisao_necessaria':True,'revisado':False,
            'motivo_revisao':reason or 'Sugestão automática; confira o trecho e a condição.',
            'intervalo_texto':list(span) if span else None})
    if not text or text.upper()=='N/C':
        add('Descrição original não informada.',reason='Não há descrição para montar os requisitos.')
        return rows
    # Commas between digits are numeric punctuation, not clause separators.
    for match in re.finditer(r'[^;\n]+',text):
        for clause in re.split(r'(?<!\d),|,(?!\d)',match[0]):
            clause=clause.strip()
            if not clause:continue
            if COMPLEX.search(clause):
                add(clause,reason='Alternativa, condição ou escopo exige mapeamento humano.')
                continue
            spans=[]
            for field,pattern,unit in PATTERNS:
                if field=='velocidade_uplink_mbps' and 'Gigabit' in pattern and not re.search(r'expans[ãa]o|uplink',clause,re.I):continue
                if field=='velocidade_wifi_mbps' and category!='access_point':continue
                for found in re.finditer(pattern,clause,re.I):
                    if any(a<=found.start(1)<b for a,b in spans):continue
                    try:value=_number(found[1])
                    except ValueError as exc:
                        add(clause,reason=str(exc));spans.append(found.span());continue
                    if field.startswith('portas_') and not isinstance(value,int):
                        add(clause,reason='Quantidade de portas precisa ser inteira.');spans.append(found.span());continue
                    supplied=found[2].lower() if found.lastindex and found.lastindex>=2 else None
                    if unit=='m' and supplied=='km':value*=1000
                    if unit=='Gbps' and supplied=='mbps':value/=1000
                    if unit=='Mbps' and (supplied in ('gbps','g') or 'Gigabit' in pattern):value*=1000
                    op=_operator(clause[:found.start(1)])
                    add(clause,field,value,unit,op,span=found.span());spans.append(found.span())
            for field,pattern in [('gerenciavel',r'\b(?:n[ãa]o\s+gerenci[áa]vel|gerenci[áa]vel|unmanaged|managed)\b'),
                                  ('poe',r'\b(?:sem\s+PoE|n[ãa]o\s+(?:suporta\s+)?PoE|PoE(?:\+\+|\+)?)(?!\w)'),
                                  ('alimentacao_bivolt',r'\bbivolt(?:\s+autom[áa]tic[oa])?\b'),
                                  ('mdi_mdix',r'\bMDI[/ -]MDI?X\b'),
                                  ('controle_fluxo_8023x',r'\bIEEE\s+802[.]3x\b'),
                                  ('rack_19',r'\brack\s+19\s+polegadas\b'),
                                  ('tecnologia_wifi',r'Wi[- ]?Fi\s*[4567](?:E)?\b')]:
                for found in re.finditer(pattern,clause,re.I):
                    if field=='tecnologia_wifi' and category!='access_point':continue
                    if field=='poe' and any(a<=found.start()<b for a,b in spans):continue
                    value=not bool(re.match(r'(?:sem|n[ãa]o|unmanaged)',found[0],re.I)) if field!='tecnologia_wifi' else re.sub(r'Wi[- ]?Fi\s*','Wi-Fi ',found[0],flags=re.I)
                    add(clause,field,value,operator='==',span=found.span());spans.append(found.span())
                    if field=='poe' and value and '+' in found[0]:
                        add(clause,'poe_plus_plus' if '++' in found[0] else 'poe_plus',True,operator='==',
                            reason='O padrão PoE avançado é distinto do suporte básico; conferir a ficha.')
            for field, pattern, convert in [
                ('camada', r'\b(L[23]\+?)\b', lambda m: m[1].upper()),
                ('vlan_802_1q', r'\bVLAN\s+(?:IEEE\s+)?802[.]1Q\b', lambda m: True),
                ('tipo_switch', r'\btipo\s+(I{1,3}|IV)\b', lambda m: m[1].upper()),
            ]:
                for found in re.finditer(pattern, clause, re.I):
                    add(clause, field, convert(found), operator='==', span=found.span())
                    spans.append(found.span())
            residual=clause
            merged=[]
            for a,b in sorted(spans):
                if merged and a<=merged[-1][1]:merged[-1]=(merged[-1][0],max(b,merged[-1][1]))
                else:merged.append((a,b))
            for a,b in reversed(merged):residual=residual[:a]+' '+residual[b:]
            residual=re.sub(r'\b(?:switch|access|point|corporativo|tipo|Mbps|Gbps|portas?|de|do|da|e|com|no|pelo|menos|m[íi]nim[oa]|m[áa]xim[oa])\b',' ',residual,flags=re.I)
            if re.search(r'\w',residual):
                add(clause,reason='Há detalhes ainda não mapeados; preserve o ponto completo ao revisar.')
    if len(rows)>200:
        # Avoid truncation: retain the full text as a single pending requirement.
        rows=[];add(text,reason='Descrição extensa: divida os pontos manualmente (limite de 200).')
    return rows


def bi_suggestions(bi):
    result=[]
    def visit(values,prefix=''):
        if not isinstance(values,dict):return
        for key,value in values.items():
            name=prefix+key
            if isinstance(value,dict):visit(value,name+'.')
            elif value is not None and str(value).strip().lower() not in ('','n/c','não informado','nao informado'):
                result.append({'campo':name,'valor':value,'origem':'caracteristicas_bi',
                    'motivo':'Resumo BI para consulta; não aplicado como requisito sem trecho explícito.'})
    visit(bi)
    return result
