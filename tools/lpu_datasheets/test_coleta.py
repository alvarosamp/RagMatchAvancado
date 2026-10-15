import unittest
from coletar import exact_pages
from estruturar import structured


def doc(text):
    return {'paginas': [{'pagina': 1, 'texto': text}]}


class MatchingTests(unittest.TestCase):
    def test_different_suffixes_are_not_equivalent(self):
        self.assertEqual(exact_pages(doc('KSFP03-0085ML05X'), ['KSFP03-0085ML05C']), [])

    def test_prefix_not_an_exact_model(self):
        self.assertEqual(exact_pages(doc('TL-SG3428MP'), ['TL-SG3428']), [])
        self.assertEqual(exact_pages(doc('PRE-SFP-TMI'), ['PRE-SFP-TM']), [])

    def test_power_variant_not_base_model(self):
        self.assertEqual(exact_pages(doc('ISCOM S2600-24T4X-DC'), ['ISCOM S2600-24T4X']), [])

    def test_spacing_and_hyphen_changes(self):
        self.assertTrue(exact_pages(doc('KSFP10     -3327SL20X transceiver'), ['KSFP10-3327SL20X']))
        self.assertTrue(exact_pages(doc('ISCOM S2600-24S4X-AC/S, 24 ports'), ['ISCOM S2600-24S4X-AC/S']))

    def test_manual_filter_does_not_get_other_model_row(self):
        p = {'dados_tecnicos_lpu': [], 'origens_lpu': [], 'descricoes_lpu': [],
             'datasheets': [],
             'part_number_fabricante': 'ABC-1', 'codigos_tor': [],
             'transcricao_integral': [{'documento_sha256': 'test', 'paginas': [
                 {'pagina': 1, 'texto': '', 'tabelas': [
                     [['Model', 'Ports'], ['ABC-1', '24'], ['ABC-2', '48']]]}]}]}
        actual = structured(p)['especificacoes_tecnicas']
        self.assertEqual(len(actual), 1)
        self.assertEqual(actual[0]['valor'], '24')
        self.assertEqual(actual[0]['validacao'], 'revisar_aplicabilidade')

    def test_fallback_keeps_description_and_units(self):
        p = {'dados_tecnicos_lpu': [{'taxa': '100M', 'distancia': '20km'}],
             'origens_lpu': [], 'descricoes_lpu': ['1310nm, 100Mbps SFP 20km'],
             'datasheets': [], 'part_number_fabricante': 'X-1', 'codigos_tor': [],
             'transcricao_integral': []}
        result = structured(p)
        self.assertTrue(result['fallback_lpu'])
        self.assertEqual(result['fonte_principal_especificacoes'], 'lpu')
        f = {x['nome']: x for x in result['especificacoes_tecnicas']}
        self.assertEqual(f['taxa_nominal']['valor'], 0.1)
        self.assertEqual(f['alcance_ou_comprimento']['valor'], 20000)
        self.assertEqual(f['descricao_tecnica_original']['valor'], p['descricoes_lpu'][0])


if __name__ == '__main__':
    unittest.main()
