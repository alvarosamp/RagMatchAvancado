"""Supplier exports use tenant-scoped catalog links and actual per-item results."""
from playwright.sync_api import expect


def test_brand_report_downloads_and_loss_reason_persistence(page, identities, api, unique):
    response = api.post('/crm/query/catalog_products/insert', json={'values': {
        'name': f'QA supplier {unique}', 'brand': f'Marca QA {unique}', 'model': f'QA-MODEL-{unique}',
    }})
    assert response.status_code == 200, response.text
    catalog_id = response.json()['data'][0]['id']
    response = api.post('/analysis/documents', json={'source_kind': 'edital', 'source_name': 'qa-supplier.json', 'result': {
        'schema_version': '7.4.4', 'n_interno': f'QA-SUPPLIER-{unique}',
        'edital': {'orgao': 'Órgão QA fornecedor', 'numero_pregao': unique, 'uf': 'SP'},
        'itens_elegiveis': [{'numero_item_edital': '1', 'categoria': 'Switch',
                            'descricao_original': f'Switch QA {unique}', 'quantidade': 10, 'preco_unitario': 150}],
    }})
    assert response.status_code == 200, response.text
    document = response.json()
    product = api.get('/crm/query/notice_products').json()['data']
    product = next(p for p in product if p['notice_id'] == document['crm_sync']['notice_id'])
    response = api.patch('/crm/query/notice_products', json={'values': {'catalog_product_id': catalog_id, 'unit_price': 120},
        'filters': [{'column': 'id', 'op': 'eq', 'value': product['id']}]})
    assert response.status_code == 200, response.text
    response = api.post('/crm/query/notice_item_results/insert', json={'values': {
        'notice_id': product['notice_id'], 'notice_product_id': product['id'], 'winner_type': 'competitor',
        'winning_price': 100, 'winning_quantity': 10, 'notes': 'private QA observation\n[motivo_perda:price]',
    }})
    assert response.status_code == 200, response.text
    page.context.add_cookies([{'name': name, 'value': value, 'url': 'http://127.0.0.1:13089'}
                              for name, value in identities['alpha', 'admin'].items()])
    assert page.goto('http://127.0.0.1:13089/crm/inteligencia-mercado').status == 200
    page.get_by_text('Refinar a análise · período, categoria e atributos', exact=True).click()
    page.get_by_placeholder('Buscar marca, modelo, produto, UF ou portal...').fill(unique)
    page.get_by_label('Marca do fornecedor').select_option(label=f'Marca QA {unique}')
    section = page.locator('section[aria-labelledby="brand-report-title"]')
    expect(section.locator('tbody tr')).to_have_count(1)
    expect(section.get_by_text('Preço não competitivo', exact=True)).to_be_visible()
    with page.expect_download() as download:
        section.get_by_role('button', name='Exportar itens CSV').click()
    csv = download.value.path().read_text(encoding='utf-8-sig')
    assert 'Preço não competitivo' in csv and '120,00' in csv and '100,00' in csv
    assert 'private QA observation' not in csv
    with page.expect_download() as download:
        section.get_by_role('button', name='Relatório para impressão / PDF').click()
    html = download.value.path().read_text(encoding='utf-8')
    assert 'Demanda e associação à marca' in html and 'private QA observation' not in html

    page.goto(f'http://127.0.0.1:13089/crm/editais/{product["notice_id"]}')
    page.get_by_role('tab', name='Itens (1)').click()
    page.get_by_role('button', name='Detalhes', exact=True).click()
    with page.expect_response(lambda r: '/query/notice_item_results' in r.url and r.request.method == 'PATCH'):
        page.get_by_label('Motivo da perda do item').select_option('technical')
    saved = next(r for r in api.get('/crm/query/notice_item_results').json()['data'] if r['notice_product_id'] == product['id'])
    assert '[motivo_perda:technical]' in saved['notes'] and 'private QA observation' in saved['notes']
    notes = page.get_by_placeholder('Observacoes sobre este resultado')
    notes.fill('private QA edited observation')
    with page.expect_response(lambda r: '/query/notice_item_results' in r.url and r.request.method == 'PATCH'):
        notes.press('Tab')
    saved = next(r for r in api.get('/crm/query/notice_item_results').json()['data'] if r['notice_product_id'] == product['id'])
    assert '[motivo_perda:technical]' in saved['notes'] and 'private QA edited observation' in saved['notes']
