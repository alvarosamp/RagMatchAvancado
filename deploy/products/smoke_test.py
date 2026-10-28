"""Verify the deployed branch through Nginx, auth, PostgreSQL and CRM over HTTP."""
import argparse
import http.cookiejar
import json
from pathlib import Path
import urllib.error
import urllib.request
import uuid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', required=True)
    parser.add_argument('--env-file', type=Path, required=True)
    args = parser.parse_args()
    settings = dict(line.split('=', 1) for line in args.env_file.read_text().splitlines()
                    if line and not line.startswith('#') and '=' in line)
    base = args.base_url.rstrip('/')
    cookies = http.cookiejar.CookieJar()
    client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies))

    def request(path, data=None, origin=base):
        headers = {'Origin': origin}
        if data is not None:
            headers['Content-Type'] = 'application/json'
        req = urllib.request.Request(base + path,
                                     data=json.dumps(data).encode() if data is not None else None,
                                     headers=headers)
        return client.open(req, timeout=45)

    assert request('/login').status == 200
    assert request('/crm/inteligencia-mercado').status == 200
    health = json.load(request('/api/health/ready'))
    print('Frontend, rota CRM e readiness HTTP: OK')
    credentials = {'email': settings['ADMIN_EMAIL'], 'password': settings['ADMIN_PASSWORD']}
    try:
        request('/api/auth/login', credentials, origin='http://untrusted.invalid')
    except urllib.error.HTTPError as error:
        assert error.code == 403, error.code
    else:
        raise AssertionError('CSRF accepted an untrusted origin')
    assert request('/api/auth/login', credentials).status == 200
    assert any(cookie.name == 'access_token' for cookie in cookies)
    assert json.load(request('/api/auth/me'))['email'] == settings['ADMIN_EMAIL']
    print('CSRF, login e cookie pelo proxy: OK')
    unique = uuid.uuid4().hex[:12]
    payload = {'source_kind': 'edital', 'source_name': 'HOSTINGER-SMOKE-FICTICIO.json', 'result': {
        'schema_version': '7.4.4', 'n_interno': f'DEMO-HOSTINGER-{unique}',
        'edital': {'orgao': 'DEMONSTRACAO FICTICIA — smoke test', 'uf': 'SP', 'numero_pregao': unique},
        'itens_elegiveis': [{'numero_item_edital': '1', 'categoria': 'Switch', 'quantidade': '2',
                            'preco_unitario': 'R$ 100,00', 'descricao_original': 'Switch ficticio QA 24 portas Gigabit',
                            'caracteristicas_bi': {'quantidade_portas': '24 Portas', 'portas_acesso': 'Gigabit'}}]}}
    document = json.load(request('/api/analysis/documents', payload))
    assert document['crm_sync']['products'] == 1, document
    stored = json.load(request(f"/api/analysis/documents/{document['id']}"))
    assert len(stored['items']) == 1
    assert stored['items'][0]['caracteristicas_bi']['quantidade_portas'] == '24 Portas'
    products = json.load(request('/api/crm/query/notice_products'))['data']
    assert any(p['notice_id'] == document['crm_sync']['notice_id'] for p in products)
    print('Importacao JSON, persistencia e leitura CRM com usuario restrito: OK')
    print('Smoke test concluido. Foi criado um edital explicitamente ficticio DEMO-HOSTINGER.')


if __name__ == '__main__':
    main()
