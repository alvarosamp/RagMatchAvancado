from types import SimpleNamespace
import json
from app.services.manual_match import preview


def product(id, category='switch', **attrs):
    return SimpleNamespace(id=id, sku=id, name=id, brand='TEST', model=id,
        description='', category=category, specification=json.dumps({'categoria':category,'atributos':attrs}))


def state(**filters):
    return {'categoria':'switch','requisitos':[],'filtros':[], 'catalog_filters':filters}


def test_facets_shrink_to_surviving_products_and_restore_on_clear():
    catalog=[product('A', portas_rj45=24, poe=True), product('B', portas_rj45=48, poe=False),
             product('C', category='transceiver', alcance_m=1000)]
    initial=preview(state(),catalog)
    assert initial['facetas']['portas_rj45']==[24,48]
    assert 'alcance_m' not in initial['facetas']
    narrowed=preview(state(poe=True),catalog)
    assert narrowed['facetas']['portas_rj45']==[24]
    assert narrowed['facetas']['poe']==[True]
    assert [c['id'] for c in narrowed['candidatos'] if c['status_filtro']=='ATENDE']==['A']
    assert preview(state(),catalog)['facetas']==initial['facetas']


def test_exact_choice_is_not_a_minimum_and_missing_data_is_not_offered():
    result=preview(state(portas_rj45=24),[product('A', portas_rj45=24),product('B', portas_rj45=48),product('C')])
    assert result['contagens']=={'ATENDE':1,'NAO_ATENDE':1,'VERIFICAR':1}
    assert result['facetas']['portas_rj45']==[24]


def test_units_are_normalized_in_available_options():
    result=preview({'categoria':'transceiver','requisitos':[],'filtros':[],'catalog_filters':{}},
                   [product('A', category='transceiver', alcance_m={'valor':10,'unidade':'km'})])
    assert result['facetas']['alcance_m']==[10000]


def test_original_requirements_survive_catalog_selections():
    s=state(portas_rj45=24)
    s['requisitos']=[{'id':'R1','atributo':'portas_rj45','valor':48,'operador':'>='}]
    assert preview(s,[product('A',portas_rj45=24)])['state']['requisitos'][0]['valor']==48
