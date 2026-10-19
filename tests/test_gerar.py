"""Testes do gerador de espelhos, sem rede e sem dados reais de funcionário."""

from __future__ import annotations

import base64
import datetime as dt
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

import gerar  # noqa: E402


def funcionario():
    return {
        '_id': 'id-exemplo',
        'full_name': 'Pessoa Exemplo',
        'cpf': '00000000000',
        'nis': '00000000000',
        'work_schedule': 'escala-1',
        'contract_data': {
            'registration_number': '1',
            'payment_source': 'empregador-1',
            'admission_date': '2020-01-15',
            'department': 'Produção',
            'job_role': 'Costura',
        },
    }


def empregador(corte=31):
    return {
        '_id': 'empregador-1',
        'name': 'Empregador Exemplo Ltda',
        'cnpj': '00000000000000',
        'period_cut_day': corte,
        'address': {
            'street_name': 'Rua Exemplo',
            'street_number': '100',
            'city': 'Cidade',
            'state': 'SC',
        },
    }


class FormatoTest(unittest.TestCase):
    def test_horas_centesimais(self):
        self.assertEqual(gerar.hm('2.50'), '02:30')
        self.assertEqual(gerar.hm('-1.25'), '-01:15')
        self.assertEqual(gerar.hm(0.999), '01:00')
        self.assertEqual(gerar.hm(None), '')
        self.assertEqual(gerar.cent('1.5'), '1,50')

    def test_documentos_so_com_digitos(self):
        self.assertEqual(gerar.fmt_cpf('00000000000'), '000.000.000-00')
        self.assertEqual(gerar.fmt_cpf('123'), '123')
        self.assertEqual(gerar.fmt_cnpj('11222333000181'), '11.222.333/0001-81')
        self.assertEqual(gerar.fmt_cnpj('AB12CD34EF5600'), 'AB12CD34EF5600')

    def test_folha_corte_31_e_corte_20(self):
        inicio, fim = gerar.folha_do_empregador(dt.date(2026, 10, 18), 31)
        self.assertEqual(inicio, dt.date(2026, 10, 1))
        self.assertEqual(fim, dt.date(2026, 10, 31))
        self.assertTrue(gerar.periodo_completo(dt.date(2026, 10, 1), dt.date(2026, 10, 31), 31))
        self.assertFalse(gerar.periodo_completo(dt.date(2026, 10, 1), dt.date(2026, 10, 18), 31))
        inicio, fim = gerar.folha_do_empregador(dt.date(2026, 2, 20), 20)
        self.assertEqual((inicio, fim), (dt.date(2026, 1, 21), dt.date(2026, 2, 20)))

    def test_feriados_e_12_de_outubro(self):
        feriados = gerar.carregar_feriados(str(ROOT / 'config' / 'feriados.txt'))
        self.assertEqual(feriados[dt.date(2026, 10, 12)], 'Nossa Senhora Aparecida')
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', delete=False) as arquivo:
            arquivo.write('# comentario\n\n12/10/2026 Feriado municipal\n')
            nome = arquivo.name
        try:
            lidos = gerar.carregar_feriados(nome)
        finally:
            os.unlink(nome)
        self.assertEqual(lidos[dt.date(2026, 10, 12)], 'Feriado municipal')

    def test_data_de_feriado_invalida(self):
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', delete=False) as arquivo:
            arquivo.write('32/13/2026 Quebrado\n')
            nome = arquivo.name
        try:
            with self.assertRaises(SystemExit):
                gerar.carregar_feriados(nome)
        finally:
            os.unlink(nome)


class PaginaTest(unittest.TestCase):
    def test_periodo_parcial_marca_impar_feriado_e_pendente(self):
        feriados = {dt.date(2026, 10, 12): 'Nossa Senhora Aparecida'}
        marcacoes = [
            {'time': '2026-10-01T08:01', 'approved': True, 'type': 'app'},
            {'time': '2026-10-01T12:00', 'approved': True, 'type': 'ajuste manual'},
            {'time': '2026-10-01T18:02', 'approved': True, 'type': 'app'},
            {'time': '2026-10-02T08:05', 'approved': False, 'type': 'web'},
        ]
        espelho = {
            'totals': {'horas_normais': '8.00', 'extra_50': '1.00', 'atraso': '0.25'},
            'days': {
                '2026-10-01': {'horas_normais': '8.00', 'extra_50': '1.00', 'total': '9.00'},
                '2026-10-02': {'atraso': '0.25', 'total': '0.25'},
            },
        }
        html, alertas = gerar.montar_pagina(
            funcionario(), espelho, marcacoes, empregador(), 'Comercial 08-18',
            dt.date(2026, 10, 1), dt.date(2026, 10, 2), feriados,
        )
        self.assertIn('MODELO', html)
        self.assertIn('n/d – período parcial', html)
        self.assertIn('Marcação ímpar', html)
        self.assertIn('08:01', html)
        self.assertIn('12:00ᴹ', html)
        self.assertIn('08:05ᴾ', html)
        self.assertIn('pendente', html)
        self.assertIn('Pessoa Exemplo', html)
        self.assertIn('Empregador Exemplo Ltda', html)
        self.assertIn('Comercial 08-18', html)
        self.assertIn('01/10/2026 a 02/10/2026', html)
        self.assertTrue(any('Marcação ímpar' in item for item in alertas))
        self.assertNotIn('668402270c4afc523b57d678', html)

    def test_mes_cheio_traz_banco_de_horas(self):
        espelho = {
            'totals': {
                'horas_normais': '168.00',
                'banco_horas': '2.50',
                'dsr': '32.00',
                'adicional_noturno': '1.20',
                'total': '170.50',
            },
            'days': {},
            'hours_bank_summary': {
                'previous_balance': '-1.00',
                'generated_balance': '3.50',
                'created_balance': '0.00',
                'final_balance': '2.50',
            },
        }
        html, _alertas = gerar.montar_pagina(
            funcionario(), espelho, [], empregador(), 'Comercial 08-18',
            dt.date(2026, 10, 1), dt.date(2026, 10, 31),
            {dt.date(2026, 10, 12): 'Nossa Senhora Aparecida'},
        )
        self.assertNotIn('MODELO', html)
        self.assertIn('Banco de horas', html)
        self.assertIn('02:30', html)
        self.assertIn('DSR', html)
        self.assertIn('Adicional noturno', html)
        self.assertIn('Saldo anterior (banco)', html)
        self.assertIn('Nossa Senhora Aparecida', html)
        self.assertIn('12/10', html)
        self.assertIn('class="fer"', html)

    def test_feriado_nao_e_falta(self):
        html, alertas = gerar.montar_pagina(
            funcionario(), {'totals': {}, 'days': {}}, [], empregador(), '—',
            dt.date(2026, 10, 12), dt.date(2026, 10, 12),
            {dt.date(2026, 10, 12): 'Nossa Senhora Aparecida'},
        )
        self.assertIn('Nossa Senhora Aparecida', html)
        self.assertNotIn('Sem registros', html)
        self.assertEqual(alertas, [])

    def test_total_acima_de_14h_pede_revisao_de_escala(self):
        espelho = {'totals': {}, 'days': {'2026-10-01': {'total': '15.00', 'horas_normais': '15.00'}}}
        _html, alertas = gerar.montar_pagina(
            funcionario(), espelho, [], empregador(), '—',
            dt.date(2026, 10, 1), dt.date(2026, 10, 1), {},
        )
        self.assertTrue(any('escala' in item for item in alertas))


class EscritaTest(unittest.TestCase):
    def test_grava_html_individual_e_consolidado(self):
        dados = {
            'funcionarios': [funcionario()],
            'escalas': {'escala-1': 'Comercial'},
            'empregadores': {'empregador-1': empregador()},
            'espelhos': {'id-exemplo': {'totals': {'banco_horas': '1.00', 'total': '8.00'}, 'days': {}}},
            'marcacoes': {'id-exemplo': []},
            'falhas': {},
        }
        with tempfile.TemporaryDirectory() as pasta:
            resultado = gerar.gerar(
                dados, dt.date(2026, 10, 1), dt.date(2026, 10, 31), pasta,
                {dt.date(2026, 10, 12): 'Nossa Senhora Aparecida'}, None,
            )
            self.assertEqual(resultado['funcionarios'], 1)
            self.assertTrue((Path(pasta) / 'html' / 'pessoa-exemplo.html').is_file())
            self.assertTrue((Path(pasta) / 'html' / 'consolidado.html').is_file())
            self.assertTrue((Path(pasta) / 'inconsistencias.json').is_file())
            self.assertFalse((Path(pasta) / 'funcionarios' / 'pessoa-exemplo.pdf').exists())


class ApiClienteTest(unittest.TestCase):
    def test_basic_auth_sem_token_na_url_e_paginacao(self):
        capturados = []
        paginas = [
            {'_items': [{'_id': 'a'}], '_meta': {'total': 2, 'page': 1}},
            {'_items': [{'_id': 'b'}], '_meta': {'total': 2, 'page': 2}},
        ]

        class Resposta:
            def __init__(self, payload):
                self.payload = payload

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return json.dumps(self.payload).encode()

        def urlopen(req, timeout=60):
            capturados.append(req)
            return Resposta(paginas[len(capturados) - 1])

        with patch('gerar.urllib.request.urlopen', urlopen):
            cliente = gerar.TiqueTaque('segredo-de-teste', 'https://api.exemplo.test/v2.1')
            itens = cliente.get_all('/employees')

        self.assertEqual([item['_id'] for item in itens], ['a', 'b'])
        for req in capturados:
            self.assertNotIn('segredo-de-teste', req.full_url)
            self.assertTrue(req.full_url.startswith('https://api.exemplo.test/v2.1/employees?'))
            bruto = base64.b64decode(req.get_header('Authorization').split(' ', 1)[1]).decode()
            self.assertEqual(bruto, 'public:segredo-de-teste')

    def test_429_tenta_de_novo(self):
        chamadas = {'n': 0}

        class Resposta:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return b'{"_items":[],"_meta":{"total":0}}'

        class Cabecalhos:
            def get(self, chave):
                return '0'

        def urlopen(req, timeout=60):
            chamadas['n'] += 1
            if chamadas['n'] == 1:
                raise urllib.error.HTTPError(
                    req.full_url, 429, 'Too Many Requests', Cabecalhos(), io.BytesIO(b'{}'),
                )
            return Resposta()

        with patch('gerar.urllib.request.urlopen', urlopen):
            cliente = gerar.TiqueTaque('tok', 'https://api.exemplo.test/v2.1')
            self.assertEqual(cliente.get('/employees'), {'_items': [], '_meta': {'total': 0}})
        self.assertEqual(chamadas['n'], 2)


class CliTest(unittest.TestCase):
    def test_sem_token_nao_cria_saida(self):
        os.environ.pop('TIQUETAQUE_API_TOKEN', None)
        with tempfile.TemporaryDirectory() as pasta:
            saida = os.path.join(pasta, 'nao-deve-existir')
            with self.assertRaises(SystemExit) as cm:
                gerar.main([
                    '--inicio', '2026-10-01', '--fim', '2026-10-31', '--saida', saida,
                ])
            self.assertIn('TIQUETAQUE_API_TOKEN', str(cm.exception))
            self.assertFalse(os.path.exists(saida))

    def test_fim_antes_do_inicio(self):
        os.environ['TIQUETAQUE_API_TOKEN'] = 'nao-usado'
        try:
            with self.assertRaises(SystemExit):
                gerar.main([
                    '--inicio', '2026-10-10', '--fim', '2026-10-01',
                    '--saida', '/tmp/ignorado',
                ])
        finally:
            os.environ.pop('TIQUETAQUE_API_TOKEN', None)

    def test_codigo_sem_dado_pessoal_nem_token(self):
        texto = (ROOT / 'src' / 'gerar.py').read_text(encoding='utf-8')
        for proibido in (
            '668402270c4afc523b57d678',
            '67b609551839d8cc1641f772',
            '66844b47bf79204f62759ba3',
            'tempersonalizados',
            'administrativo@',
            'rh@',
            '/workspace/fechamentos',
        ):
            self.assertNotIn(proibido, texto)
        self.assertIn('TIQUETAQUE_API_TOKEN', texto)


class PdfTest(unittest.TestCase):
    def test_html_vira_pdf(self):
        chrome = gerar.achar_chrome(None)
        if not chrome:
            self.skipTest('Chrome não instalado')
        with tempfile.TemporaryDirectory() as pasta:
            html_path = os.path.join(pasta, 'pagina.html')
            pdf_path = os.path.join(pasta, 'pagina.pdf')
            pagina, _alertas = gerar.montar_pagina(
                funcionario(),
                {'totals': {'banco_horas': '1.00', 'total': '8.00'}, 'days': {}},
                [{'time': '2026-10-05T08:00', 'approved': True, 'type': 'app'}],
                empregador(),
                'Comercial',
                dt.date(2026, 10, 1),
                dt.date(2026, 10, 31),
                {dt.date(2026, 10, 12): 'Nossa Senhora Aparecida'},
            )
            Path(html_path).write_text(gerar.documento(pagina, 'Pessoa Exemplo'), encoding='utf-8')
            gerar.html_para_pdf(chrome, html_path, pdf_path)
            conteudo = Path(pdf_path).read_bytes()
            self.assertTrue(conteudo.startswith(b'%PDF'))
            self.assertGreater(len(conteudo), 1000)


if __name__ == '__main__':
    unittest.main()
