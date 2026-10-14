"""Conservative description suggestions; source text and review are preserved."""
import copy
from types import SimpleNamespace
import pytest
from app.services.item_requirement_suggestions import suggest_requirements, bi_suggestions
from app.services.manual_match import import_item, required_payload, validate_state


def suggest(text,category='switch'):
    return suggest_requirements(text,category,{'arquivo':'entrada.json','pagina':None},'001')


def test_explicit_points_operators_and_uplink_units():
    rows=suggest('Switch gerenciável, mínimo de 24 portas RJ45, 4 uplinks SFP+ 10G')
    mapped={r['campo_normalizado']:r for r in rows}
    assert mapped['portas_rj45']['valor']==24
    assert mapped['portas_rj45']['operador']=='>='
    assert mapped['portas_sfp_plus']['valor']==4
    assert mapped['velocidade_uplink_mbps']['valor']==10000
    assert mapped['gerenciavel']['valor'] is True
    assert all(r['revisao_necessaria'] and not r['revisado'] for r in rows)
    assert len({r['id'] for r in rows})==len(rows)
    assert mapped['portas_rj45']['origem']['trecho']=='mínimo de 24 portas RJ45'
    assert mapped['portas_rj45']['origem']['pagina'] is None
    assert rows==suggest('Switch gerenciável, mínimo de 24 portas RJ45, 4 uplinks SFP+ 10G')


@pytest.mark.parametrize('text,op',[('mínimo de 24 portas RJ45','>='),('máximo de 24 portas RJ45','<='),('acima de 24 portas RJ45','>'),('24 portas RJ45','==')])
def test_operators_are_attached_to_their_own_number(text,op):
    assert suggest(text)[0]['operador']==op


def test_optical_formats_do_not_collapse():
    rows=suggest('18 portas SFP28; 4 portas QSFP28; 4 portas SFP+; 2 portas SFP')
    assert {r['campo_normalizado'] for r in rows}=={'portas_sfp28','portas_qsfp28','portas_sfp_plus','portas_sfp'}


def test_unknowns_conditions_and_decimal_ambiguity_remain_visible():
    rows=suggest('24 portas RJ45 ou 48 portas RJ45; licenças incluídas; taxa agregada mínima 1.700 Mbps','access_point')
    assert all(r['operador']=='nao_mapeado' for r in rows)
    assert len(rows)==3
    assert '1.700' in rows[-1]['texto_original']
    assert 'licenças' in rows[1]['texto_original']


def test_poe_standard_is_not_lost_after_extracting_base_support():
    rows=suggest('PoE IEEE 802.3at')
    assert any(r['campo_normalizado']=='poe' and r['valor'] is True for r in rows)
    assert any(r['operador']=='nao_mapeado' and '802.3at' in r['texto_original'] for r in rows)


@pytest.mark.parametrize('label,field',[('PoE+','poe_plus'),('PoE++','poe_plus_plus')])
def test_poe_plus_does_not_collapse_to_basic_support(label,field):
    assert any(r['campo_normalizado']==field for r in suggest(label))


def test_bi_negative_does_not_become_a_requirement():
    rows=suggest('mínimo 24 portas RJ45')
    assert not any(r['campo_normalizado'] in ('poe','gerenciavel') for r in rows)
    bi=bi_suggestions({'alimentacao_poe':'Nao PoE','gerenciamento':'Nao Gerenciavel','uplinks':'N/C'})
    assert len(bi)==2
    assert all(r['origem']=='caracteristicas_bi' for r in bi)


def test_decimal_comma_is_not_a_clause_separator():
    rows=suggest('alcance mínimo de 2,4 km; gerenciável')
    assert rows[0]['valor']==2400
    assert rows[0]['operador']=='>='


def test_missing_or_large_description_stays_pending():
    assert suggest(None)[0]['operador']=='nao_mapeado'
    text=';'.join(['24 portas RJ45']*205)
    rows=suggest(text)
    assert len(rows)==1 and rows[0]['texto_original']==text


def test_unreviewed_and_removed_source_points_block_confirmation():
    payload={'item':{'numero':'001','categoria':'switch'},'requisitos_atomicos':suggest('24 portas RJ45')}
    item=SimpleNamespace(id='example',item_number='001',category='switch')
    state=import_item(payload,item)
    state['descricao_revisada']=True
    assert required_payload(state)['conflitos_documentais']
    state['requisitos'][0]['revisao_necessaria']=False
    state=validate_state(state)
    assert state['requisitos'][0]['revisao_necessaria'] is True
    assert required_payload(state)['conflitos_documentais']
    state['requisitos'][0]['revisado']=True
    assert not required_payload(state).get('conflitos_documentais')
    removed=copy.deepcopy(state);removed['requisitos']=[]
    assert validate_state(removed)['pendencias']


def test_real_http_suggestions_are_read_only_and_isolated(clients,unique):
    api=clients('empty','admin')
    def create(table,values):
        response=api.post('/crm/query/'+table+'/insert',json={'values':values})
        assert response.status_code==200,response.text
        return response.json()['data'][0]
    notice=create('notices',{'number':'SUGGEST-'+unique,'title':'EXEMPLO SIMULADO'})
    item=create('notice_products',{'notice_id':notice['id'],'item_number':'001','category':'switch','description':'mínimo de 24 portas RJ45, gerenciável','quantity':3,'unit_price':123,'bi_features':{'alimentacao_poe':'Nao PoE'},'raw_payload':{'preservar':'fonte'}})
    base=f"/crm/notices/{notice['id']}/products/{item['id']}/manual-match"
    response=api.post(base+'/suggest')
    assert response.status_code==200,response.text
    state=response.json()['state']
    assert state['filtros']==[] and not state['descricao_revisada']
    assert state['sugestoes_bi']
    assert any(r['atributo']=='portas_rj45' and r['valor']==24 for r in state['requisitos'])
    assert not any(r['atributo']=='poe' for r in state['requisitos'])
    assert clients('beta','admin').post(base+'/suggest').status_code==404
    before=api.get(base).json()['base_revision']
    assert before==response.json()['base_revision']


@pytest.mark.parametrize('suggestions',['invalid',[{'campo':'poe','motivo':{}}]])
def test_malformed_bi_suggestions_are_rejected(suggestions):
    item=SimpleNamespace(id='example',item_number='001',category='switch')
    with pytest.raises(ValueError,match='Sugestões BI'):
        import_item({'requisitos':[],'sugestoes_bi':suggestions},item)


def test_source_obligations_require_review_and_cannot_disappear():
    item=SimpleNamespace(id='example',item_number='001',category='switch')
    state=import_item({'requisitos':[],'obrigacoes_gerais':{'garantia_meses':60}},item)
    state['descricao_revisada']=True
    assert any(r['id']=='obligations_review' for r in required_payload(state)['conflitos_documentais'])
    state['obrigacoes_gerais']={}
    state=validate_state(state)
    assert state['obrigacoes_gerais']['garantia_meses']==60
    state['obrigacoes_revisadas']=True
    assert not required_payload(state).get('conflitos_documentais')
