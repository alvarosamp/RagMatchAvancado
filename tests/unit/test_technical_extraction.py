from app.services.technical_matching.extraction import extract_document, compare_extractions

def source(text, hash='abc', page=1):
 return {'arquivo':'teste.pdf','hash':hash,'documento_id':'preview-'+hash,'versao_documento':1,'total_paginas':1,'paginas':[{'pagina':page,'texto':text}]}

def documents(watts=384):
 return extract_document(source('mínimo 24 portas RJ45\nmínimo 4 portas SFP\norçamento de PoE mínimo 370 W')), extract_document(source(f'RJ45 ports: 24\nSFP ports: 4\nPoE budget: {watts} W','def'),offered=True)

def review(required, offered):
 return {'requisitos':[r['id'] for r in required['registros']], 'atributos':[r['id'] for r in offered['registros']], 'descartes':{},'escolhas':{}}

def test_operators_traceability_and_no_unreviewed_approval():
 a,b=documents()
 assert len(a['registros'])==3
 assert all(r['operador']=='>=' for r in a['registros'])
 assert not a['pendencias'] and not b['pendencias']
 assert compare_extractions(a,b,{})['status']=='VERIFICAR'
 assert compare_extractions(a,b,review(a,b))['status']=='ATENDE'
 assert a['registros'][0]['evidencias'][0]['pagina']==1
 assert a['registros'][0]['evidencias'][0]['hash_documento']=='abc'

def test_insufficient_power_needs_review_before_rejection():
 a,b=documents(180)
 assert compare_extractions(a,b,{})['status']=='VERIFICAR'
 assert compare_extractions(a,b,review(a,b))['status']=='NAO_ATENDE'

def test_above_is_strict_not_minimum():
 a=extract_document(source('capacidade de comutação acima de 30 Gbps'))
 assert a['registros'][0]['operador']=='>'
 b=extract_document(source('switching capacity: 30 Gbps','other'),offered=True)
 assert compare_extractions(a,b,review(a,b))['status']=='NAO_ATENDE'

def test_alternatives_and_scopes_are_not_guessed():
 for clause in ['24 portas RJ45 ou 48 portas RJ45','alcance 100 m OM3','alcance 300 m quando OM4']:
  data=extract_document(source(clause))
  assert not data['registros'] and data['pendencias']

def test_unrecognized_mandatory_protocol_blocks_approval():
 a,b=documents();a['pendencias'].append({'id':'snmp','trecho':'SNMP v3 obrigatório','pagina':2,'motivo':'Não reconhecido'})
 r=review(a,b)
 assert compare_extractions(a,b,r)['status']=='VERIFICAR'
 r['descartes']={'snmp':'rodapé sem exigência neste item'}
 assert compare_extractions(a,b,r)['status']=='VERIFICAR'

def test_conflicting_values_cannot_silently_collapse():
 a,b=documents();b['registros'].append({**b['registros'][-1],'id':'second-budget','valor':180})
 r=review(a,b)
 assert compare_extractions(a,b,r)['status']=='VERIFICAR'
 r['escolhas']={'poe_budget_w':'second-budget'}
 assert compare_extractions(a,b,r)['status']=='NAO_ATENDE'
 r['escolhas']={'poe_budget_w':'invented'}
 assert compare_extractions(a,b,r)['status']=='VERIFICAR'

def test_unit_conversion_and_decimal_counts():
 assert extract_document(source('alcance mínimo 10 km'))['registros'][0]['valor']==10000
 assert extract_document(source('capacidade de comutação 30000 Mbps'))['registros'][0]['valor']==30
 assert extract_document(source('24,5 portas RJ45'))['pendencias']
 assert not extract_document(source('24,5 portas RJ45'))['registros']

def test_missing_page_does_not_invent_provenance():
 a,b=documents();a=extract_document(source('mínimo 24 portas RJ45',page=None))
 assert compare_extractions(a,b,review(a,b))['status']=='VERIFICAR'

def test_no_text_and_unsupported_datasheet_clauses():
 assert extract_document(source(''))['pendencias'][0]['id']=='sem-texto'
 a,b=documents();b['pendencias'].append({'id':'conditional','trecho':'Somente quando ligada a fonte extra','pagina':1,'motivo':'Condição'})
 assert compare_extractions(a,b,review(a,b))['status']=='VERIFICAR'

def test_ambiguous_number_format_never_guessed():
 data=extract_document(source('PoE budget: 1,200 W'))
 assert not data['registros'] and data['pendencias']

def test_invalid_pdf_and_ranges_are_input_errors():
 import pytest
 from app.services.technical_matching.extraction import read_pdf
 with pytest.raises(ValueError): read_pdf(b'not-pdf','bad.pdf')
 with pytest.raises(ValueError): read_pdf(b'%PDF-1.4\ncorrupt','bad.pdf')
