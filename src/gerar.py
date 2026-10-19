#!/usr/bin/env python3
"""Gera o fechamento de ponto (HTML e PDF A4) pela API pública TiqueTaque.

Somente leitura. O token vem de TIQUETAQUE_API_TOKEN e não é gravado em disco.
Período, pasta de saída e arquivo de feriados são parâmetros de linha de comando.
"""

from __future__ import annotations

import argparse
import base64
import calendar
import datetime as dt
import html
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

BASE_PADRAO = 'https://api.tiquetaque.com/v2.1'
PAGE_SIZE = 50
FUSO = ZoneInfo('America/Sao_Paulo')
WD = ['seg', 'ter', 'qua', 'qui', 'sex', 'sáb', 'dom']
MESES = [
    'janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho',
    'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro',
]
LABEL = {
    'horas_normais': 'Horas normais',
    'banco_horas': 'Banco de horas',
    'falta_injustificada': 'Faltas injustificadas',
    'falta_justificada': 'Faltas justificadas',
    'abono': 'Abonos',
    'folga': 'Folgas',
    'atraso': 'Atrasos',
    'dsr': 'DSR',
    'desconto_dsr': 'Desconto DSR',
    'inss': 'INSS (afast.)',
    'atestado': 'Atestados',
    'dispensa_legal': 'Dispensa legal',
    'adicional_noturno': 'Adicional noturno',
    'hora_noturna_reduzida': 'Hora noturna reduzida',
    'afastamento_nao_remunerado': 'Afast. não remunerado',
    'sobreaviso': 'Sobreaviso',
    'suspensao': 'Suspensão',
    'ferias': 'Férias',
    'total': 'Total apurado',
}
AUSENCIAS = (
    ('atestado', 'Atestado'),
    ('abono', 'Abono'),
    ('ferias', 'Férias'),
    ('folga', 'Folga'),
    ('dispensa_legal', 'Disp. legal'),
    ('inss', 'INSS'),
    ('suspensao', 'Suspensão'),
    ('afastamento_nao_remunerado', 'Afast. n/rem.'),
)
ORDEM_RUBRICAS = [
    'atraso', 'falta_injustificada', 'falta_justificada', 'atestado', 'abono',
    'ferias', 'folga', 'dsr', 'desconto_dsr', 'adicional_noturno',
    'hora_noturna_reduzida', 'dispensa_legal', 'inss', 'suspensao',
    'afastamento_nao_remunerado', 'sobreaviso',
]
RUBRICAS_SEMPRE = [
    'horas_normais', 'extra_50', 'extra_100', 'atraso', 'falta_injustificada',
    'falta_justificada', 'atestado', 'abono', 'ferias', 'dsr', 'adicional_noturno',
]

CSS = '''@page{size:A4;margin:11mm 10mm 11mm 10mm}
*{box-sizing:border-box}body{font-family:"DejaVu Sans",Arial,sans-serif;font-size:8.3pt;color:#111;margin:0}
.page{page-break-after:always}.page:last-child{page-break-after:auto}
.modelo{background:#fff3cd;border:1px solid #e0b100;color:#7a5a00;text-align:center;font-weight:bold;padding:3px;font-size:9pt;margin-bottom:5px;letter-spacing:.3px}
.hdr{display:flex;justify-content:space-between;border-bottom:2px solid #222;padding-bottom:4px;margin-bottom:5px}
.hdr h1{font-size:13pt;margin:0}.hdr .emp{font-size:8.5pt;line-height:1.35}.hdr .right{text-align:right;font-size:8.5pt;line-height:1.35}
.info{display:grid;grid-template-columns:2.2fr 1fr 1.2fr 1.3fr;gap:2px 10px;border:1px solid #bbb;padding:4px 6px;margin-bottom:6px;font-size:8.3pt}
.info b{color:#444;font-weight:normal;font-size:7pt;text-transform:uppercase;display:block}
table{width:100%;border-collapse:collapse}
.daily th{background:#2f3b4c;color:#fff;font-weight:normal;font-size:7.2pt;padding:3px 3px;border:1px solid #2f3b4c}
.daily td{border:1px solid #c8c8c8;padding:2px 3px;font-size:7.8pt;vertical-align:middle}
.daily td.n{text-align:center;white-space:nowrap}
.daily tr.we td{background:#f2f2f2;color:#666}.daily tr.fer td{background:#e8f0fb}
.daily tr.bad td{background:#fdecea}.daily tr.bad td.obs{color:#a30000;font-weight:bold}
.daily td.obs{font-size:7pt}
.p{color:#b35c00;font-weight:bold}.m{color:#1f5fa8}
.legend{font-size:6.8pt;color:#555;margin:3px 0 6px}
.sec{font-weight:bold;font-size:9pt;margin:6px 0 3px;border-bottom:1px solid #999}
.tot td{border:1px solid #c8c8c8;padding:2.5px 5px;font-size:8pt}.tot td.v{text-align:right;white-space:nowrap;width:16%}
.tot td.k{width:34%}
.alerts{border:1px solid #e3a3a3;background:#fff6f6;padding:4px 6px;font-size:7.6pt;margin-top:6px}
.alerts ul{margin:2px 0 0 14px;padding:0}
.sign{display:flex;justify-content:space-between;margin-top:26px;gap:40px}
.sign div{flex:1;text-align:center;border-top:1px solid #000;padding-top:3px;font-size:7.8pt}
.decl{font-size:7.3pt;margin-top:8px;color:#333;text-align:justify}
.foot{font-size:6.5pt;color:#777;margin-top:8px;text-align:right}
'''


class ApiError(Exception):
    def __init__(self, status: int, path: str, message: str):
        super().__init__(message)
        self.status = status
        self.path = path
        self.message = message


class TiqueTaque:
    """Cliente mínimo da API pública. Respeita a janela de 60 req/min."""

    def __init__(self, token: str, base: str = BASE_PADRAO, limite_por_minuto: int = 55):
        self.base = base.rstrip('/')
        self._auth = 'Basic ' + base64.b64encode(f'public:{token}'.encode()).decode()
        self._limite = limite_por_minuto
        self._hits: list[float] = []
        self.requisicoes = 0

    def _esperar_janela(self) -> None:
        agora = time.monotonic()
        self._hits = [t for t in self._hits if agora - t < 60]
        if len(self._hits) >= self._limite:
            time.sleep(60 - (agora - self._hits[0]) + 0.05)
            agora = time.monotonic()
            self._hits = [t for t in self._hits if agora - t < 60]
        self._hits.append(time.monotonic())

    def get(self, path: str, params: dict | None = None, *, allow_status: tuple[int, ...] = ()) -> dict:
        query = urllib.parse.urlencode(params or {})
        url = self.base + path + (('?' + query) if query else '')
        espera = 1.0
        for tentativa in range(5):
            self._esperar_janela()
            req = urllib.request.Request(url)
            req.add_header('Authorization', self._auth)
            req.add_header('Accept', 'application/json')
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    self.requisicoes += 1
                    bruto = resp.read().decode('utf-8')
                    return json.loads(bruto) if bruto else {}
            except urllib.error.HTTPError as exc:
                self.requisicoes += 1
                detalhe = exc.read().decode('utf-8', errors='replace')
                if exc.code == 429 and tentativa < 4:
                    retry = exc.headers.get('Retry-After') if exc.headers else None
                    time.sleep(float(retry) if retry and str(retry).isdigit() else espera)
                    espera = min(espera * 2, 60)
                    continue
                if exc.code in allow_status:
                    return {'_error': True, '_http_status': exc.code}
                raise ApiError(exc.code, path, _mensagem_api(detalhe)) from None
        raise ApiError(429, path, 'limite de requisições da API')

    def get_all(self, path: str, params: dict | None = None) -> list:
        itens: list = []
        pagina = 1
        while pagina <= 1000:
            consulta = dict(params or {})
            consulta['page'] = pagina
            consulta['max_results'] = PAGE_SIZE
            dados = self.get(path, consulta)
            lote = dados.get('_items') or []
            itens.extend(lote)
            total = (dados.get('_meta') or {}).get('total')
            if not lote:
                break
            if total is not None and len(itens) >= total:
                break
            if total is None and len(lote) < PAGE_SIZE:
                break
            pagina += 1
        else:
            raise ApiError(0, path, 'paginação excedeu o limite de segurança')
        return itens


def _mensagem_api(corpo: str) -> str:
    try:
        dados = json.loads(corpo)
    except json.JSONDecodeError:
        return 'resposta de erro sem JSON'
    erro = dados.get('_error') or {}
    return str(erro.get('ui_message') or erro.get('message') or 'erro na API')


def token_do_ambiente() -> str:
    token = os.environ.get('TIQUETAQUE_API_TOKEN', '').strip()
    if not token:
        raise SystemExit(
            'Defina TIQUETAQUE_API_TOKEN com o token de integração do TiqueAdmin. '
            'Não grave o token no repositório.'
        )
    return token


def parse_data(valor: str) -> dt.date:
    try:
        return dt.date.fromisoformat(valor)
    except ValueError as exc:
        raise SystemExit(f'Data inválida: {valor}. Use AAAA-MM-DD.') from exc


def parse_data_opcional(valor: str | None) -> dt.date | None:
    if not valor:
        return None
    try:
        return dt.date.fromisoformat(valor[:10])
    except ValueError:
        return None


def carregar_feriados(caminho: str | None) -> dict[dt.date, str]:
    if not caminho:
        return {}
    feriados: dict[dt.date, str] = {}
    with open(caminho, encoding='utf-8-sig') as arquivo:
        for numero, linha in enumerate(arquivo, 1):
            texto = linha.strip()
            if not texto or texto.startswith('#'):
                continue
            pedacos = texto.split(None, 1)
            feriados[_data_feriado(pedacos[0], numero, caminho)] = (
                pedacos[1].strip() if len(pedacos) > 1 else 'Feriado'
            )
    return feriados


def _data_feriado(valor: str, linha: int, caminho: str) -> dt.date:
    for formato in ('%Y-%m-%d', '%d/%m/%Y'):
        try:
            return dt.datetime.strptime(valor, formato).date()
        except ValueError:
            continue
    raise SystemExit(f'{caminho}:{linha}: data inválida "{valor}". Use AAAA-MM-DD ou DD/MM/AAAA.')


def folha_do_empregador(referencia: dt.date, corte: int | None) -> tuple[dt.date, dt.date]:
    """Folha cujo fim cai no mês de `referencia`. Corte 31 = mês civil."""
    ultimo = calendar.monthrange(referencia.year, referencia.month)[1]
    if corte is None or corte >= 31 or corte >= ultimo:
        return dt.date(referencia.year, referencia.month, 1), dt.date(referencia.year, referencia.month, ultimo)
    fim = dt.date(referencia.year, referencia.month, corte)
    if referencia.month == 1:
        ano_ant, mes_ant = referencia.year - 1, 12
    else:
        ano_ant, mes_ant = referencia.year, referencia.month - 1
    ultimo_ant = calendar.monthrange(ano_ant, mes_ant)[1]
    dia_ini = corte + 1
    if dia_ini > ultimo_ant:
        inicio = dt.date(referencia.year, referencia.month, 1)
    else:
        inicio = dt.date(ano_ant, mes_ant, dia_ini)
    return inicio, fim


def periodo_completo(inicio: dt.date, fim: dt.date, corte: int | None) -> bool:
    folha_ini, folha_fim = folha_do_empregador(fim, corte)
    return inicio == folha_ini and fim == folha_fim


def hm(valor) -> str:
    if valor in (None, ''):
        return ''
    numero = float(valor)
    sinal = '-' if numero < 0 else ''
    numero = abs(numero)
    horas = int(numero)
    minutos = round((numero - horas) * 60)
    if minutos == 60:
        horas += 1
        minutos = 0
    return f'{sinal}{horas:02d}:{minutos:02d}'


def cent(valor) -> str:
    if valor in (None, ''):
        return ''
    return f'{float(valor):.2f}'.replace('.', ',')


def fmt_cpf(valor: str | None) -> str:
    if valor and valor.isdigit() and len(valor) == 11:
        return f'{valor[:3]}.{valor[3:6]}.{valor[6:9]}-{valor[9:]}'
    return valor or '—'


def fmt_cnpj(valor: str | None) -> str:
    if valor and valor.isdigit() and len(valor) == 14:
        return f'{valor[:2]}.{valor[2:5]}.{valor[5:8]}/{valor[8:12]}-{valor[12:]}'
    return valor or '—'


def br(dia: dt.date) -> str:
    return dia.strftime('%d/%m/%Y')


def competencia(dia: dt.date) -> str:
    return f'{MESES[dia.month - 1].capitalize()}/{dia.year}'


def lab(chave: str) -> str:
    if chave in LABEL:
        return LABEL[chave]
    noturno = re.fullmatch(r'adicional_noturno_extra_(\d+)', chave)
    if noturno:
        return f'Ad. noturno extra {noturno.group(1)}%'
    extra = re.fullmatch(r'extra_(\d+)', chave)
    if extra:
        return f'Horas extras {extra.group(1)}%'
    return chave


def slug(nome: str) -> str:
    normalizado = unicodedata.normalize('NFKD', nome).encode('ascii', 'ignore').decode()
    return re.sub(r'[^A-Za-z0-9]+', '-', normalizado).strip('-').lower() or 'funcionario'


def hoje_sp() -> dt.date:
    return dt.datetime.now(FUSO).date()


def cobre_periodo(funcionario: dict, inicio: dt.date, fim: dt.date) -> bool:
    contrato = funcionario.get('contract_data') or {}
    admissao = parse_data_opcional(contrato.get('admission_date'))
    desligamento = parse_data_opcional(contrato.get('dismissal_date'))
    if admissao and admissao > fim:
        return False
    if desligamento and desligamento < inicio:
        return False
    return True


def _hora_marcacao(registro: dict) -> str:
    bruto = str(registro.get('time') or '')
    hora = bruto[11:16] if len(bruto) >= 16 else bruto
    if not re.fullmatch(r'\d{2}:\d{2}', hora):
        hora = html.escape(hora)
    if not registro.get('approved'):
        return f'<span class="p">{hora}ᴾ</span>'
    if registro.get('type') == 'ajuste manual':
        return f'<span class="m">{hora}ᴹ</span>'
    return hora


def analisar_dia(dia: dt.date, registros: list, espelho_dia: dict, feriados: dict[dt.date, str]) -> dict:
    registros = sorted(registros, key=lambda item: item.get('time') or '')
    validos = [item for item in registros if item.get('type') != 'desconsiderado']
    marcacoes = [_hora_marcacao(item) for item in validos]
    if not registros and espelho_dia.get('horarios'):
        marcacoes = [html.escape(str(hora)) for hora in espelho_dia.get('horarios') or []]

    extras = sum(
        float(valor)
        for chave, valor in espelho_dia.items()
        if isinstance(chave, str) and re.fullmatch(r'extra_\d+', chave) and valor not in (None, '')
    )
    faltas = []
    if espelho_dia.get('falta_injustificada'):
        faltas.append('Inj. ' + hm(espelho_dia['falta_injustificada']))
    if espelho_dia.get('falta_justificada'):
        faltas.append('Just. ' + hm(espelho_dia['falta_justificada']))
    ausencias = [
        f'{rotulo} {hm(espelho_dia[chave])}'
        for chave, rotulo in AUSENCIAS
        if espelho_dia.get(chave)
    ]

    quantidade = len(validos) if registros else len(espelho_dia.get('horarios') or [])
    pendentes = [item for item in validos if not item.get('approved')]
    manuais = [item for item in validos if item.get('type') == 'ajuste manual']
    desconsideradas = [item for item in registros if item.get('type') == 'desconsiderado']
    feriado = dia in feriados
    fim_de_semana = dia.weekday() >= 5
    obs: list[str] = []
    grave = False
    if feriado:
        obs.append(feriados[dia])
    if quantidade % 2 == 1:
        obs.append('Marcação ímpar – falta registro de saída' if quantidade >= 3 else 'Marcação ímpar')
        grave = True
    if not fim_de_semana and not feriado and quantidade == 0 and not ausencias and not faltas:
        obs.append('Sem registros e sem justificativa')
        grave = True
    if not fim_de_semana and not feriado and quantidade == 2 and not ausencias:
        obs.append('Intervalo não registrado')
        grave = True
    if pendentes:
        obs.append(f'{len(pendentes)} marcação(ões) pendente(s) de aprovação')
        grave = True
    if desconsideradas:
        obs.append(f'{len(desconsideradas)} desconsiderada(s)')
    if manuais and len(manuais) == quantidade and quantidade > 0:
        obs.append('Todas as marcações por ajuste manual')
    elif manuais:
        obs.append(f'{len(manuais)} ajuste(s) manual(is)')
    total = float(espelho_dia.get('total') or 0)
    if total > 14:
        obs.append('Total diário anômalo – verificar escala')
        grave = True
    if fim_de_semana and quantidade == 0 and not feriado:
        obs.append('Descanso')

    if grave:
        classe = 'bad'
    elif feriado:
        classe = 'fer'
    elif fim_de_semana:
        classe = 'we'
    else:
        classe = ''

    horas_normais = espelho_dia.get('horas_normais')
    if horas_normais is None and espelho_dia.get('total') and not ausencias:
        horas_normais = espelho_dia.get('total')

    return {
        'classe': classe,
        'marcacoes': marcacoes,
        'horas_normais': horas_normais,
        'extras': extras,
        'atraso': espelho_dia.get('atraso'),
        'faltas': faltas,
        'ausencias': ausencias,
        'obs': obs,
        'grave': grave,
        'feriado': feriados.get(dia),
    }


def linhas_totais(totais: dict, completo: bool) -> str:
    extras = sorted(
        (chave for chave in totais if re.fullmatch(r'extra_\d+', chave)),
        key=lambda chave: int(chave.split('_')[1]),
    )
    noturnos = sorted(chave for chave in totais if chave.startswith('adicional_noturno_extra'))
    ordem = ['horas_normais', 'extra_50', 'extra_100', *extras, *ORDEM_RUBRICAS[:10], *noturnos, *ORDEM_RUBRICAS[10:]]
    chaves: list[str] = []
    for chave in ordem:
        if (chave in totais or chave in RUBRICAS_SEMPRE) and chave not in chaves:
            chaves.append(chave)
    for chave in totais:
        if chave not in chaves and chave not in ('total', 'banco_horas'):
            chaves.append(chave)

    celulas = [
        f'<td class="k">{html.escape(lab(chave))}</td>'
        f'<td class="v">{hm(totais.get(chave, 0)) or "00:00"} '
        f'<span style="color:#888">({cent(totais.get(chave, 0)) or "0,00"})</span></td>'
        for chave in chaves
    ]
    if 'banco_horas' in totais:
        banco = f'{hm(totais["banco_horas"])} <span style="color:#888">({cent(totais["banco_horas"])})</span>'
    elif completo:
        banco = '<i>n/d – não retornado pela API</i>'
    else:
        banco = '<i>n/d – período parcial</i>'
    celulas.append(f'<td class="k"><b>Banco de horas</b></td><td class="v">{banco}</td>')
    celulas.append(
        f'<td class="k"><b>{html.escape(lab("total"))}</b></td>'
        f'<td class="v"><b>{hm(totais.get("total", 0)) or "00:00"}</b> '
        f'<span style="color:#888">({cent(totais.get("total", 0)) or "0,00"})</span></td>'
    )
    if len(celulas) % 2:
        celulas.append('<td></td><td></td>')
    return ''.join(f'<tr>{celulas[i]}{celulas[i + 1]}</tr>' for i in range(0, len(celulas), 2))


def linhas_banco(resumo: dict | None) -> str:
    if not resumo:
        return ''
    pares = (
        ('Saldo anterior (banco)', resumo.get('previous_balance')),
        ('Gerado no período', resumo.get('generated_balance')),
        ('Lançado manualmente', resumo.get('created_balance')),
        ('Saldo final (banco)', resumo.get('final_balance')),
    )
    celulas = []
    for rotulo, valor in pares:
        if valor in (None, ''):
            continue
        celulas.append(
            f'<td class="k">{rotulo}</td><td class="v">{hm(valor)} '
            f'<span style="color:#888">({cent(valor)})</span></td>'
        )
    if not celulas:
        return ''
    if len(celulas) % 2:
        celulas.append('<td></td><td></td>')
    return ''.join(f'<tr>{celulas[i]}{celulas[i + 1]}</tr>' for i in range(0, len(celulas), 2))


def montar_pagina(
    funcionario: dict,
    espelho: dict,
    marcacoes: list,
    empregador: dict,
    escala: str,
    inicio: dt.date,
    fim: dt.date,
    feriados: dict[dt.date, str],
    avisos_extra: list[str] | None = None,
) -> tuple[str, list[str]]:
    contrato = funcionario.get('contract_data') or {}
    dias = espelho.get('days') if isinstance(espelho.get('days'), dict) else {}
    totais = espelho.get('totals') if isinstance(espelho.get('totals'), dict) else {}
    por_dia: dict[str, list] = {}
    for registro in marcacoes:
        chave = str(registro.get('time') or '')[:10]
        por_dia.setdefault(chave, []).append(registro)

    corte = empregador.get('period_cut_day')
    try:
        corte = int(corte) if corte is not None else None
    except (TypeError, ValueError):
        corte = None
    completo = periodo_completo(inicio, fim, corte)
    folha_ini, folha_fim = folha_do_empregador(fim, corte)

    linhas = []
    agregados: dict[str, list[str]] = {}
    cursor = inicio
    while cursor <= fim:
        chave = cursor.isoformat()
        analise = analisar_dia(cursor, por_dia.get(chave, []), dias.get(chave) or {}, feriados)
        obs = '; '.join(html.escape(item) for item in analise['obs'] if item)
        linhas.append(
            f'<tr class="{analise["classe"]}">'
            f'<td class="n">{cursor.strftime("%d/%m")}</td>'
            f'<td class="n">{WD[cursor.weekday()]}</td>'
            f'<td class="n">{" &nbsp;".join(analise["marcacoes"])}</td>'
            f'<td class="n">{hm(analise["horas_normais"]) if analise["horas_normais"] else ""}</td>'
            f'<td class="n">{hm(analise["extras"]) if analise["extras"] else ""}</td>'
            f'<td class="n">{hm(analise["atraso"]) if analise["atraso"] else ""}</td>'
            f'<td class="n">{"<br>".join(html.escape(item) for item in analise["faltas"])}</td>'
            f'<td class="n">{"<br>".join(html.escape(item) for item in analise["ausencias"])}</td>'
            f'<td class="obs">{obs}</td></tr>'
        )
        if analise['grave']:
            for item in analise['obs']:
                if item and item != analise['feriado'] and 'manual' not in item and 'desconsiderada' not in item:
                    agregados.setdefault(item, []).append(cursor.strftime('%d/%m'))
        cursor += dt.timedelta(days=1)

    alertas = [f'{chave}: ' + ', '.join(datas) for chave, datas in agregados.items()]
    alertas.extend(avisos_extra or [])
    if alertas:
        bloco_alerta = (
            f'<div class="alerts"><b>Inconsistências a revisar antes do fechamento ({len(alertas)}):</b><ul>'
            + ''.join(f'<li>{html.escape(item)}</li>' for item in alertas)
            + '</ul></div>'
        )
    else:
        bloco_alerta = (
            '<div class="alerts" style="background:#f3fbf3;border-color:#9c9">'
            'Nenhuma inconsistência identificada no período.</div>'
        )

    endereco = empregador.get('address') or {}
    if completo:
        tarja = ''
        declaracao = (
            'Declaro que as marcações acima correspondem à minha jornada de trabalho no período indicado. '
            'Documento gerado a partir dos dados do sistema TiqueTaque (API pública v2.1). '
            'O espelho oficial em PDF permanece disponível apenas no painel TiqueAdmin.'
        )
    else:
        tarja = (
            f'<div class="modelo">MODELO – período parcial {br(inicio)} a {br(fim)} · documento não definitivo</div>'
        )
        declaracao = (
            'Declaro que as marcações acima correspondem à minha jornada de trabalho no período indicado. '
            'Documento gerado a partir dos dados do sistema TiqueTaque (API pública v2.1). '
            f'Este é um modelo com período parcial; o banco de horas só é apurado na folha completa '
            f'({br(folha_ini)} a {br(folha_fim)}).'
        )

    local = ''
    if endereco.get('city') and endereco.get('state'):
        local = f'{html.escape(str(endereco["city"]))}/{html.escape(str(endereco["state"]))} '
    nome = funcionario.get('full_name') or 'Sem nome'
    admissao = parse_data_opcional(contrato.get('admission_date'))
    corte_txt = f'<br>Corte do espelho: dia {corte}' if corte else ''
    logradouro = ', '.join(
        parte for parte in (
            html.escape(str(endereco.get('street_name') or '')),
            html.escape(str(endereco.get('street_number') or '')),
        ) if parte
    )
    cidade = ' – '.join(
        parte for parte in (
            logradouro,
            '/'.join(
                pedaco for pedaco in (
                    html.escape(str(endereco.get('city') or '')),
                    html.escape(str(endereco.get('state') or '')),
                ) if pedaco
            ),
        ) if parte
    )

    cnpj = fmt_cnpj(empregador.get('cnpj')) if empregador.get('cnpj') else ''
    detalhe_emp = ' · '.join(parte for parte in (f'CNPJ {html.escape(cnpj)}' if cnpj else '', cidade) if parte)
    pagina = f'''<div class="page">
{tarja}
<div class="hdr"><div><h1>Espelho de Ponto – Fechamento Mensal</h1>
<div class="emp"><b>{html.escape(str(empregador.get("name") or ""))}</b>{('<br>' + detalhe_emp) if detalhe_emp else ''}</div></div>
<div class="right">Competência: <b>{competencia(fim)}</b><br>Período: <b>{br(inicio)} a {br(fim)}</b><br>Emitido em {br(hoje_sp())}{corte_txt}</div></div>
<div class="info">
<div><b>Funcionário</b>{html.escape(nome)}</div><div><b>Matrícula</b>{html.escape(str(contrato.get("registration_number") or "—"))}</div><div><b>CPF</b>{html.escape(fmt_cpf(funcionario.get("cpf")))}</div><div><b>Admissão</b>{br(admissao) if admissao else "—"}</div>
<div><b>Cargo / Setor</b>{html.escape(str(contrato.get("job_role") or "—"))} / {html.escape(str(contrato.get("department") or "—"))}</div><div><b>Escala</b>{html.escape(escala or "—")}</div><div><b>PIS/NIS</b>{html.escape(str(funcionario.get("nis") or "—"))}</div><div><b>Empregador</b>{html.escape(str(empregador.get("name") or "—"))}</div>
</div>
<table class="daily"><thead><tr><th style="width:7%">Data</th><th style="width:5%">Dia</th><th style="width:25%">Marcações</th><th style="width:7.5%">Horas<br>normais</th><th style="width:6.5%">Extras</th><th style="width:6.5%">Atraso</th><th style="width:7.5%">Faltas</th><th style="width:10%">Atestado/<br>Abono/Férias</th><th>Observações</th></tr></thead>
<tbody>{"".join(linhas)}</tbody></table>
<div class="legend"><span class="m">ᴹ</span> ajuste manual &nbsp;·&nbsp; <span class="p">ᴾ</span> pendente de aprovação (não considerada no cálculo) &nbsp;·&nbsp; Linhas em vermelho: inconsistência &nbsp;·&nbsp; Valores em hh:mm; entre parênteses, horas centesimais.</div>
<div class="sec">Totais do período</div>
<table class="tot">{linhas_totais(totais, completo)}{linhas_banco(espelho.get("hours_bank_summary") if completo else None)}</table>
{bloco_alerta}
<div class="decl">{declaracao}</div>
<div class="sign"><div>{html.escape(nome)}<br>Funcionário(a)</div><div>{html.escape(str(empregador.get("name") or ""))}<br>Empresa</div></div>
<div class="foot">{local}____/____/________ · gerado pela API TiqueTaque v2.1, sem substituir o espelho oficial do TiqueAdmin</div>
</div>'''
    return pagina, alertas


def documento(corpo: str, titulo: str) -> str:
    return (
        '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
        f'<title>{html.escape(titulo)}</title><style>{CSS}</style></head><body>{corpo}</body></html>'
    )


def achar_chrome(explicito: str | None) -> str | None:
    if explicito:
        return explicito
    ambiente = os.environ.get('CHROME_BIN')
    if ambiente:
        return ambiente
    for nome in ('google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser'):
        caminho = shutil.which(nome)
        if caminho:
            return caminho
    return None


def _pdf_valido(caminho: str) -> bool:
    try:
        if os.path.getsize(caminho) < 500:
            return False
        with open(caminho, 'rb') as arquivo:
            return arquivo.read(5) == b'%PDF-'
    except OSError:
        return False


def _encerrar_processo(processo: subprocess.Popen) -> None:
    if processo.poll() is not None:
        return
    try:
        os.killpg(processo.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        processo.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(processo.pid, signal.SIGKILL)
        except ProcessLookupError:
            return
        processo.wait(timeout=5)


def html_para_pdf(chrome: str, html_path: str, pdf_path: str) -> None:
    """Converte HTML em PDF. O Chrome headless grava o arquivo e, em alguns
    builds, não termina sozinho; o processo é encerrado quando o PDF está pronto."""
    if os.path.exists(pdf_path):
        os.remove(pdf_path)
    perfil = tempfile.mkdtemp(prefix='chrome-ponto-')
    log_path = os.path.join(perfil, 'chrome.log')
    comando = [
        chrome, '--headless=new', '--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage',
        f'--user-data-dir={perfil}', '--no-pdf-header-footer',
        f'--print-to-pdf={os.path.abspath(pdf_path)}',
        'file://' + urllib.parse.quote(os.path.abspath(html_path), safe='/'),
    ]
    log = open(log_path, 'w', encoding='utf-8')
    processo = subprocess.Popen(comando, stdout=log, stderr=log, start_new_session=True)
    try:
        prazo = time.monotonic() + 45
        tamanho = -1
        estavel = 0
        while time.monotonic() < prazo:
            if _pdf_valido(pdf_path):
                atual = os.path.getsize(pdf_path)
                if atual == tamanho:
                    estavel += 1
                    if estavel >= 2:
                        return
                else:
                    estavel = 0
                tamanho = atual
            elif processo.poll() is not None:
                break
            time.sleep(0.2)
        log.flush()
        detalhe = ''
        with open(log_path, encoding='utf-8', errors='replace') as arquivo:
            linhas = [linha.strip() for linha in arquivo if linha.strip() and 'dbus' not in linha.lower()]
        detalhe = linhas[-1] if linhas else ''
        raise SystemExit('Falha ao gerar PDF com o Chrome.' + (f' {detalhe}' if detalhe else ''))
    finally:
        _encerrar_processo(processo)
        log.close()
        shutil.rmtree(perfil, ignore_errors=True)


def carregar_dados(api: TiqueTaque, inicio: dt.date, fim: dt.date) -> dict:
    params = {'start_date': inicio.isoformat(), 'end_date': fim.isoformat()}
    funcionarios = [item for item in api.get_all('/employees') if cobre_periodo(item, inicio, fim)]
    escalas = {item.get('_id'): item.get('description') or '' for item in api.get_all('/work-schedules/summary')}
    empregadores = {item.get('_id'): item for item in api.get_all('/payment-sources')}
    espelhos = {}
    for item in api.get_all('/timesheets', params):
        if item.get('employee_id'):
            espelhos[item['employee_id']] = item
    marcacoes = {}
    falhas = {}
    for funcionario in funcionarios:
        eid = funcionario.get('_id')
        if not eid:
            continue
        resposta = api.get('/times', {'employee_id': eid, **params}, allow_status=(404, 409))
        if resposta.get('_error'):
            marcacoes[eid] = []
            falhas[eid] = (
                f'Não foi possível ler as marcações (HTTP {resposta.get("_http_status")}).'
            )
        else:
            marcacoes[eid] = resposta.get('times') or []
    return {
        'funcionarios': funcionarios,
        'escalas': escalas,
        'empregadores': empregadores,
        'espelhos': espelhos,
        'marcacoes': marcacoes,
        'falhas': falhas,
    }


def gerar(dados: dict, inicio: dt.date, fim: dt.date, saida: str, feriados: dict[dt.date, str], chrome: str | None) -> dict:
    os.makedirs(os.path.join(saida, 'html'), exist_ok=True)
    os.makedirs(os.path.join(saida, 'funcionarios'), exist_ok=True)
    funcionarios = sorted(
        dados['funcionarios'],
        key=lambda item: (
            (dados['empregadores'].get((item.get('contract_data') or {}).get('payment_source')) or {}).get('name') or '',
            item.get('full_name') or '',
        ),
    )
    paginas = []
    resumo = []
    usados: set[str] = set()
    for funcionario in funcionarios:
        eid = funcionario.get('_id')
        contrato = funcionario.get('contract_data') or {}
        empregador = dados['empregadores'].get(contrato.get('payment_source')) or {}
        escala = dados['escalas'].get(funcionario.get('work_schedule')) or '—'
        avisos = []
        if eid in dados['falhas']:
            avisos.append(dados['falhas'][eid])
        if eid not in dados['espelhos']:
            avisos.append('Sem espelho de ponto no período.')
        pagina, alertas = montar_pagina(
            funcionario,
            dados['espelhos'].get(eid) or {},
            dados['marcacoes'].get(eid) or [],
            empregador,
            escala,
            inicio,
            fim,
            feriados,
            avisos,
        )
        paginas.append(pagina)
        nome = funcionario.get('full_name') or 'Sem nome'
        base = slug(nome)
        if base in usados:
            base = f'{base}-{(eid or "")[-6:]}'
        usados.add(base)
        caminho_html = os.path.join(saida, 'html', base + '.html')
        with open(caminho_html, 'w', encoding='utf-8') as arquivo:
            arquivo.write(documento(pagina, nome))
        if chrome:
            html_para_pdf(chrome, caminho_html, os.path.join(saida, 'funcionarios', base + '.pdf'))
        if alertas:
            resumo.append({
                'empregador': empregador.get('name') or '',
                'funcionario': nome,
                'alertas': alertas,
            })

    titulo = f'Fechamento ponto {br(inicio)} a {br(fim)}'
    consolidado_html = os.path.join(saida, 'html', 'consolidado.html')
    with open(consolidado_html, 'w', encoding='utf-8') as arquivo:
        arquivo.write(documento(''.join(paginas), titulo))
    nome_pdf = f'fechamento-ponto-{inicio.isoformat()}_{fim.isoformat()}-consolidado.pdf'
    if chrome:
        html_para_pdf(chrome, consolidado_html, os.path.join(saida, nome_pdf))
    caminho_json = os.path.join(saida, 'inconsistencias.json')
    with open(caminho_json, 'w', encoding='utf-8') as arquivo:
        json.dump(resumo, arquivo, ensure_ascii=False, indent=1)
    return {
        'funcionarios': len(funcionarios),
        'com_alerta': len(resumo),
        'consolidado': os.path.join(saida, nome_pdf) if chrome else consolidado_html,
        'inconsistencias': caminho_json,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Gera os espelhos de ponto (A4) de um período a partir da API pública TiqueTaque.',
    )
    parser.add_argument('--inicio', required=True, help='Primeiro dia do período, AAAA-MM-DD.')
    parser.add_argument('--fim', required=True, help='Último dia do período, AAAA-MM-DD.')
    parser.add_argument('--saida', required=True, help='Diretório dos HTML, PDFs e do JSON de inconsistências.')
    parser.add_argument('--feriados', help='Arquivo de feriados (AAAA-MM-DD e descrição).')
    parser.add_argument('--somente-html', action='store_true', help='Não converte para PDF.')
    parser.add_argument('--chrome', help='Caminho do Google Chrome ou do Chromium.')
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    inicio = parse_data(args.inicio)
    fim = parse_data(args.fim)
    if fim < inicio:
        raise SystemExit('--fim não pode ser anterior a --inicio.')
    token = token_do_ambiente()
    feriados = carregar_feriados(args.feriados)
    chrome = None if args.somente_html else achar_chrome(args.chrome)
    if not args.somente_html and not chrome:
        raise SystemExit(
            'Chrome/Chromium não encontrado. Instale o navegador, defina CHROME_BIN, '
            'ou rode com --somente-html.'
        )
    base = os.environ.get('TIQUETAQUE_API_BASE', BASE_PADRAO)
    api = TiqueTaque(token, base)
    dados = carregar_dados(api, inicio, fim)
    resultado = gerar(dados, inicio, fim, args.saida, feriados, chrome)
    print(f'Funcionários: {resultado["funcionarios"]}')
    print(f'Com inconsistência: {resultado["com_alerta"]}')
    print(f'Saída: {os.path.abspath(args.saida)}')
    print(f'Consolidado: {resultado["consolidado"]}')
    print(f'Requisições à API: {api.requisicoes}')


if __name__ == '__main__':
    main()
