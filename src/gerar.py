#!/usr/bin/env python3
"""Modelo LEGADO do espelho de ponto (PDF A4) a partir da API TiqueTaque.

Não é o documento do fechamento mensal. Desde 2026-10-19 o fechamento usa o
PDF oficial salvo no TiqueAdmin (Gestão de ponto → Espelho de ponto). Este
script fica como fallback quando esse PDF não pôde ser salvo.

O token é lido de TIQUETAQUE_API_TOKEN. Período, diretório de saída e a lista
de feriados vêm da linha de comando. Nada de cadastro ou batida fica no código.

Uso:
    python src/gerar.py --inicio 2026-09-01 --fim 2026-09-30 --saida output/2026-09-modelo
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import html
import json
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections import deque
from pathlib import Path

API_BASE = os.environ.get("TIQUETAQUE_API_BASE", "https://api.tiquetaque.com/v2.1").rstrip("/")
TOKEN_ENV = "TIQUETAQUE_API_TOKEN"
MESES = (
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
)
WD = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]
LABEL = {
    "horas_normais": "Horas normais",
    "banco_horas": "Banco de horas",
    "falta_injustificada": "Faltas injustificadas",
    "falta_justificada": "Faltas justificadas",
    "abono": "Abonos",
    "folga": "Folgas",
    "atraso": "Atrasos",
    "dsr": "DSR",
    "desconto_dsr": "Desconto DSR",
    "inss": "INSS (afast.)",
    "atestado": "Atestados",
    "dispensa_legal": "Dispensa legal",
    "adicional_noturno": "Adicional noturno",
    "hora_noturna_reduzida": "Hora noturna reduzida",
    "afastamento_nao_remunerado": "Afast. não remunerado",
    "sobreaviso": "Sobreaviso",
    "suspensao": "Suspensão",
    "ferias": "Férias",
    "total": "Total apurado",
}
AUSENCIAS = (
    ("atestado", "Atestado"),
    ("abono", "Abono"),
    ("ferias", "Férias"),
    ("folga", "Folga"),
    ("dispensa_legal", "Disp. legal"),
    ("inss", "INSS"),
    ("suspensao", "Suspensão"),
    ("afastamento_nao_remunerado", "Afast. n/rem."),
)
SHOWN_TOTALS = (
    "horas_normais",
    "extra_50",
    "extra_100",
    "atraso",
    "falta_injustificada",
    "falta_justificada",
    "atestado",
    "abono",
    "ferias",
    "dsr",
    "adicional_noturno",
)
ISO_TIME = re.compile(r"^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})")
HHMM = re.compile(r"^\d{2}:\d{2}$")
CHROME_CANDIDATES = (
    "google-chrome",
    "google-chrome-stable",
    "chromium",
    "chromium-browser",
    "chrome",
)

CSS = """@page{size:A4;margin:11mm 10mm 11mm 10mm}
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
.p{color:#b35c00;font-weight:bold}.m{color:#1f5fa8}.e{color:#0b6b4f}
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
"""


class ApiError(RuntimeError):
    pass


class RateLimiter:
    """Mantém as chamadas abaixo do teto de 60 req/min em janela deslizante."""

    def __init__(self, max_calls: int = 50, window: float = 60.0) -> None:
        self.max_calls = max_calls
        self.window = window
        self._times: deque[float] = deque()

    def wait(self) -> None:
        now = time.monotonic()
        while self._times and now - self._times[0] >= self.window:
            self._times.popleft()
        if len(self._times) >= self.max_calls:
            time.sleep(self.window - (now - self._times[0]) + 0.05)
        self._times.append(time.monotonic())


class ApiClient:
    def __init__(self, token: str, base: str = API_BASE) -> None:
        if not token.strip():
            raise ApiError(f"Defina {TOKEN_ENV} com o token da integração TiqueTaque.")
        encoded = base64.b64encode(f"public:{token}".encode()).decode()
        self.base = base.rstrip("/")
        self._headers = {
            "Authorization": f"Basic {encoded}",
            "Accept": "application/json",
            "User-Agent": "rotina-rh/fechamento",
        }
        self._limiter = RateLimiter()

    def get(self, path: str, params: dict | None = None) -> dict:
        query = urllib.parse.urlencode(params or {})
        url = f"{self.base}{path}"
        if query:
            url = f"{url}?{query}"
        request = urllib.request.Request(url, headers=self._headers, method="GET")
        return self._send(request)

    def list_items(self, path: str, params: dict | None = None) -> list[dict]:
        items: list[dict] = []
        page = 1
        while True:
            query = dict(params or {})
            query["page"] = page
            query["max_results"] = 25
            payload = self.get(path, query)
            batch = payload.get("_items") or []
            items.extend(batch)
            total = (payload.get("_meta") or {}).get("total")
            if not batch or total is None or len(items) >= total:
                return items
            page += 1

    def _send(self, request: urllib.request.Request, attempt: int = 0) -> dict:
        self._limiter.wait()
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            if exc.code == 429 and attempt < 3:
                time.sleep(20 * (attempt + 1))
                return self._send(request, attempt + 1)
            raise ApiError(f"HTTP {exc.code} em {request.full_url}: {_error_message(body)}") from exc
        except urllib.error.URLError as exc:
            raise ApiError(f"Falha ao chamar {request.full_url}: {exc.reason}") from exc
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ApiError(f"Resposta não é JSON em {request.full_url}.") from exc


def _error_message(body: str) -> str:
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return body.strip()[:300] or "sem detalhe"
    error = payload.get("_error") or {}
    return error.get("ui_message") or error.get("message") or body.strip()[:300]


def parse_date(value: str) -> dt.date:
    try:
        return dt.date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Data inválida: {value}. Use AAAA-MM-DD.") from exc


def periodo_completo(start: dt.date, end: dt.date) -> bool:
    """Folha cheia quando period_cut_day é 31: dia 1 até o último dia do mês."""
    if start.year != end.year or start.month != end.month or start.day != 1:
        return False
    next_month = (start.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
    return end == next_month - dt.timedelta(days=1)


def load_feriados(path: Path | None, start: dt.date, end: dt.date) -> dict[dt.date, str]:
    if path is None or not path.is_file():
        print(f"Aviso: lista de feriados não encontrada ({path}). Nenhum feriado será marcado.", file=sys.stderr)
        return {}
    found: dict[dt.date, str] = {}
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        token, _, description = line.partition(" ")
        description = description.strip() or "Feriado"
        dates = _expand_feriado(token, start, end)
        if not dates:
            raise SystemExit(f"{path}:{lineno}: data de feriado inválida ({token!r}). Use DD/MM ou AAAA-MM-DD.")
        for day in dates:
            found[day] = description
    return found


def _expand_feriado(token: str, start: dt.date, end: dt.date) -> list[dt.date]:
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", token):
        day = dt.date.fromisoformat(token)
        return [day] if start <= day <= end else []
    match = re.fullmatch(r"(\d{1,2})/(\d{1,2})(?:/(\d{4}))?", token)
    if not match:
        return []
    day_n, month_n = int(match.group(1)), int(match.group(2))
    if match.group(3):
        try:
            day = dt.date(int(match.group(3)), month_n, day_n)
        except ValueError:
            return []
        return [day] if start <= day <= end else []
    dates = []
    for year in range(start.year, end.year + 1):
        try:
            day = dt.date(year, month_n, day_n)
        except ValueError:
            continue
        if start <= day <= end:
            dates.append(day)
    return dates


def default_feriados_path() -> Path:
    candidates = (
        Path.cwd() / "config" / "feriados.txt",
        Path(__file__).resolve().parent.parent / "config" / "feriados.txt",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[-1]


def lab(key: str) -> str:
    if key in LABEL:
        return LABEL[key]
    match = re.fullmatch(r"adicional_noturno_extra_(\d+)", key)
    if match:
        return f"Ad. noturno extra {match.group(1)}%"
    match = re.fullmatch(r"extra_(\d+)", key)
    if match:
        return f"Horas extras {match.group(1)}%"
    return key


def hm(value) -> str:
    if value in (None, ""):
        return ""
    number = float(value)
    sign = "-" if number < 0 else ""
    number = abs(number)
    hours = int(number)
    minutes = round((number - hours) * 60)
    if minutes == 60:
        hours += 1
        minutes = 0
    return f"{sign}{hours:02d}:{minutes:02d}"


def cent(value) -> str:
    if value in (None, ""):
        return ""
    return f"{float(value):.2f}".replace(".", ",")


def fmtcpf(value: str | None) -> str:
    digits = value or ""
    if len(digits) == 11 and digits.isdigit():
        return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"
    return digits


def fmtcnpj(value: str | None) -> str:
    digits = value or ""
    if len(digits) == 14 and digits.isdigit():
        return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"
    return digits


def br(day: dt.date) -> str:
    return day.strftime("%d/%m/%Y")


def clock(value: str | None) -> str | None:
    if not value:
        return None
    match = ISO_TIME.match(value)
    if match:
        return match.group(2)
    if HHMM.match(value):
        return value
    return None


def slug(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "-", normalized).strip("-").lower() or "funcionario"


def load_from_api(start: dt.date, end: dt.date, token: str) -> tuple[list[dict], dict, dict, dict, dict]:
    client = ApiClient(token)
    print("Consultando funcionários, escalas, empregadores e espelhos...", file=sys.stderr)
    employees = client.list_items("/employees")
    schedules = {item["_id"]: item.get("description") or "" for item in client.list_items("/work-schedules/summary")}
    employers = {item["_id"]: item for item in client.list_items("/payment-sources")}
    sheets = {
        item["employee_id"]: item
        for item in client.list_items(
            "/timesheets",
            {"start_date": start.isoformat(), "end_date": end.isoformat()},
        )
        if item.get("employee_id")
    }
    times: dict[str, list] = {}
    for index, employee in enumerate(employees, start=1):
        employee_id = employee["_id"]
        print(f"Batidas {index}/{len(employees)}", file=sys.stderr)
        payload = client.get(
            "/times",
            {
                "employee_id": employee_id,
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
            },
        )
        times[employee_id] = payload.get("times") or []
    return employees, schedules, employers, sheets, times


def load_from_dir(path: Path) -> tuple[list[dict], dict, dict, dict, dict]:
    def read_json(name: str) -> dict:
        file_path = path / name
        if not file_path.is_file():
            raise SystemExit(f"Dump incompleto: falta {file_path}.")
        return json.loads(file_path.read_text(encoding="utf-8"))

    employees = read_json("employees.json").get("_items") or []
    schedules = {item["_id"]: item.get("description") or "" for item in (read_json("schedules.json").get("_items") or [])}
    employers = {item["_id"]: item for item in (read_json("payment_sources.json").get("_items") or [])}
    sheets = {
        item["employee_id"]: item
        for item in (read_json("timesheets.json").get("_items") or [])
        if item.get("employee_id")
    }
    times = {}
    times_dir = path / "times"
    for employee in employees:
        employee_id = employee["_id"]
        file_path = times_dir / f"{employee_id}.json"
        if file_path.is_file():
            times[employee_id] = json.loads(file_path.read_text(encoding="utf-8")).get("times") or []
        else:
            times[employee_id] = []
    return employees, schedules, employers, sheets, times


def build_page(
    employee: dict,
    timesheet: dict,
    punches: list[dict],
    schedule_name: str,
    employer: dict,
    start: dt.date,
    end: dt.date,
    feriados: dict[dt.date, str],
    completo: bool,
) -> tuple[str, list[str]]:
    contract = employee.get("contract_data") or {}
    totals = timesheet.get("totals") or {}
    days = timesheet.get("days") or {}
    by_day: dict[str, list] = {}
    for punch in punches:
        moment = punch.get("time") or ""
        if len(moment) >= 10:
            by_day.setdefault(moment[:10], []).append(punch)

    rows: list[str] = []
    alerts: dict[str, list[str]] = {}
    day = start
    while day <= end:
        key = day.isoformat()
        info = days.get(key) or {}
        if not isinstance(info, dict):
            info = {}
        weekday = day.weekday()
        records = sorted(by_day.get(key, []), key=lambda item: item.get("time") or "")
        valid = [item for item in records if item.get("type") != "desconsiderado"]
        rendered = []
        for item in valid:
            shown = clock(item.get("time"))
            if not shown:
                continue
            if not item.get("approved"):
                shown = f'<span class="p">{shown}ᴾ</span>'
            elif item.get("type") == "ajuste manual":
                shown = f'<span class="m">{shown}ᴹ</span>'
            elif item.get("type") == "registro externo":
                shown = f'<span class="e">{shown}ᴱ</span>'
            rendered.append(shown)
        if not records:
            for horario in info.get("horarios") or []:
                shown = clock(str(horario))
                if shown:
                    rendered.append(html.escape(shown))

        extras = sum(float(value) for rubrica, value in info.items() if re.fullmatch(r"extra_\d+", rubrica))
        faltas = []
        if info.get("falta_injustificada"):
            faltas.append("Inj. " + hm(info["falta_injustificada"]))
        if info.get("falta_justificada"):
            faltas.append("Just. " + hm(info["falta_justificada"]))
        ausencias = [f"{label} {hm(info[rubrica])}" for rubrica, label in AUSENCIAS if info.get(rubrica)]

        count = len(valid) if records else len(info.get("horarios") or [])
        pending = [item for item in valid if not item.get("approved")]
        manual = [item for item in valid if item.get("type") == "ajuste manual"]
        discarded = [item for item in records if item.get("type") == "desconsiderado"]
        holiday = day in feriados
        weekend = weekday >= 5
        observations: list[str] = []
        bad = False

        def flag(text: str, highlight: bool = True) -> None:
            nonlocal bad
            observations.append(text)
            if highlight:
                bad = True
                alerts.setdefault(text, []).append(day.strftime("%d/%m"))

        if holiday:
            observations.append(feriados[day])
        if count % 2 == 1:
            flag("Marcação ímpar – falta registro de saída" if count >= 3 else "Marcação ímpar")
        if not weekend and not holiday and count == 0 and not ausencias and not faltas:
            if records and not valid:
                flag("Marcações existentes foram desconsideradas")
            elif not records:
                flag("Sem registros e sem justificativa")
        if not weekend and not holiday and count == 2 and not ausencias:
            flag("Intervalo não registrado")
        if pending:
            flag(f"{len(pending)} marcação(ões) pendente(s) de aprovação")
        if discarded:
            observations.append(f"{len(discarded)} desconsiderada(s)")
        if manual and len(manual) == count and count > 0:
            flag("Todas as marcações por ajuste manual")
        elif manual:
            observations.append(f"{len(manual)} ajuste(s) manual(is)")
        if info.get("falta_injustificada"):
            flag("Falta injustificada")
        if info.get("atraso"):
            alerts.setdefault("Atraso", []).append(day.strftime("%d/%m"))
        try:
            daily_total = float(info.get("total") or 0)
        except (TypeError, ValueError):
            daily_total = 0
        if daily_total > 14:
            flag("Total diário anômalo – verificar escala")
        if weekend and count == 0 and not holiday:
            observations.append("Descanso")

        if not timesheet and day == start:
            flag("Sem espelho no período")

        css = "bad" if bad else ("fer" if holiday else ("we" if weekend else ""))
        normais = info.get("horas_normais")
        if normais is None and info.get("total") and not ausencias:
            normais = info.get("total")
        rows.append(
            f'<tr class="{css}"><td class="n">{day.strftime("%d/%m")}</td>'
            f'<td class="n">{WD[weekday]}</td>'
            f'<td class="n">{" &nbsp;".join(rendered)}</td>'
            f'<td class="n">{hm(normais) if normais else ""}</td>'
            f'<td class="n">{hm(extras) if extras else ""}</td>'
            f'<td class="n">{hm(info.get("atraso")) if info.get("atraso") else ""}</td>'
            f'<td class="n">{"<br>".join(html.escape(item) for item in faltas)}</td>'
            f'<td class="n">{"<br>".join(html.escape(item) for item in ausencias)}</td>'
            f'<td class="obs">{html.escape("; ".join(item for item in observations if item))}</td></tr>'
        )
        day += dt.timedelta(days=1)

    alert_lines = [f"{label}: {', '.join(dates)}" for label, dates in alerts.items()]
    page = _render_page(
        employee,
        employer,
        schedule_name,
        totals,
        rows,
        alert_lines,
        start,
        end,
        completo,
    )
    return page, alert_lines


def _total_keys(totals: dict) -> list[str]:
    extras = sorted(
        (key for key in totals if re.fullmatch(r"extra_\d+", key)),
        key=lambda key: int(key.split("_")[1]),
    )
    night = sorted(key for key in totals if key.startswith("adicional_noturno_extra"))
    order = [
        "horas_normais",
        "extra_50",
        "extra_100",
        *extras,
        "atraso",
        "falta_injustificada",
        "falta_justificada",
        "atestado",
        "abono",
        "ferias",
        "folga",
        "dsr",
        "desconto_dsr",
        "adicional_noturno",
        *night,
        "hora_noturna_reduzida",
        "dispensa_legal",
        "inss",
        "suspensao",
        "afastamento_nao_remunerado",
        "sobreaviso",
    ]
    keys: list[str] = []
    for key in order:
        if (key in totals or key in SHOWN_TOTALS) and key not in keys:
            keys.append(key)
    keys.extend(key for key in totals if key not in keys and key not in {"total", "banco_horas"})
    return keys


def _render_page(
    employee: dict,
    employer: dict,
    schedule_name: str,
    totals: dict,
    rows: list[str],
    alerts: list[str],
    start: dt.date,
    end: dt.date,
    completo: bool,
) -> str:
    contract = employee.get("contract_data") or {}
    address = employer.get("address") or {}
    name = employee.get("full_name") or "—"
    employer_name = employer.get("name") or "—"
    cells = [
        (
            f'<td class="k">{html.escape(lab(key))}</td>'
            f'<td class="v">{hm(totals.get(key, 0)) if totals.get(key) else "00:00"} '
            f'<span style="color:#888">({cent(totals.get(key, 0)) or "0,00"})</span></td>'
        )
        for key in _total_keys(totals)
    ]
    if "banco_horas" in totals:
        bank = f"{hm(totals['banco_horas'])} <span style=\"color:#888\">({cent(totals['banco_horas'])})</span>"
    elif completo:
        bank = "<i>n/d</i>"
    else:
        bank = "<i>n/d – período parcial</i>"
    cells.append(f'<td class="k"><b>Banco de horas</b></td><td class="v">{bank}</td>')
    cells.append(
        f'<td class="k"><b>{html.escape(lab("total"))}</b></td>'
        f'<td class="v"><b>{hm(totals.get("total", 0))}</b> '
        f'<span style="color:#888">({cent(totals.get("total", 0)) or "0,00"})</span></td>'
    )
    if len(cells) % 2:
        cells.append("<td></td><td></td>")
    total_rows = "".join(f"<tr>{cells[index]}{cells[index + 1]}</tr>" for index in range(0, len(cells), 2))
    if alerts:
        items = "".join(f"<li>{html.escape(item)}</li>" for item in alerts)
        alert_html = f'<div class="alerts"><b>Inconsistências a revisar antes do fechamento ({len(alerts)}):</b><ul>{items}</ul></div>'
    else:
        alert_html = '<div class="alerts" style="background:#f3fbf3;border-color:#9c9">Nenhuma inconsistência identificada no período.</div>'

    legacy = (
        '<div class="modelo">MODELO LEGADO (fallback) – o fechamento mensal usa o PDF oficial do TiqueAdmin, '
        "não este layout.</div>"
    )
    if completo:
        banner = legacy
        declaration = (
            "Declaro que as marcações acima correspondem à minha jornada de trabalho no período indicado. "
            "Documento gerado a partir dos dados do sistema TiqueTaque (API pública v2.1). "
            "Este arquivo é o modelo legado, usado só como fallback. Não substitui o espelho oficial emitido no TiqueAdmin."
        )
    else:
        banner = (
            legacy
            + f'<div class="modelo">Período parcial {br(start)} a {br(end)} · documento não definitivo · '
            "banco de horas só é apurado no mês completo</div>"
        )
        declaration = (
            "Declaro que as marcações acima correspondem à minha jornada de trabalho no período indicado. "
            "Documento gerado a partir dos dados do sistema TiqueTaque (API pública v2.1). "
            f"Este é um modelo com período parcial ({br(start)} a {br(end)}); o banco de horas só é apurado "
            "quando o intervalo é a folha cheia, do dia 1 ao último dia do mês. "
            "Não substitui o espelho oficial emitido no TiqueAdmin."
        )
    competencia = (
        f"{MESES[start.month - 1].capitalize()}/{start.year}"
        if start.year == end.year and start.month == end.month
        else f"{br(start)} a {br(end)}"
    )
    admission = contract.get("admission_date")
    admission_label = br(dt.date.fromisoformat(admission)) if admission else "—"
    place = ""
    if address.get("city") and address.get("state"):
        place = f"{address['city']}/{address['state']}, "
    street = ", ".join(
        part
        for part in (
            address.get("street_name") or "",
            str(address.get("street_number") or ""),
        )
        if part
    )
    city = "/".join(part for part in (address.get("city") or "", address.get("state") or "") if part)
    address_line = " · ".join(part for part in (f"CNPJ {fmtcnpj(employer.get('cnpj'))}" if employer.get("cnpj") else "", " – ".join(part for part in (street, city) if part)) if part)

    return f"""<div class="page">
{banner}<div class="hdr"><div><h1>Espelho de Ponto – Fechamento Mensal</h1>
<div class="emp"><b>{html.escape(employer_name)}</b><br>{html.escape(address_line)}</div></div>
<div class="right">Competência: <b>{html.escape(competencia)}</b><br>Período: <b>{br(start)} a {br(end)}</b><br>Emitido em {dt.date.today().strftime("%d/%m/%Y")}</div></div>
<div class="info">
<div><b>Funcionário</b>{html.escape(name)}</div><div><b>Matrícula</b>{html.escape(str(contract.get("registration_number") or "—"))}</div><div><b>CPF</b>{html.escape(fmtcpf(employee.get("cpf")))}</div><div><b>Admissão</b>{admission_label}</div>
<div><b>Cargo / Setor</b>{html.escape(contract.get("job_role") or "—")} / {html.escape(contract.get("department") or "—")}</div><div><b>Escala</b>{html.escape(schedule_name or "—")}</div><div><b>PIS/NIS</b>{html.escape(str(employee.get("nis") or "—"))}</div><div><b>Empregador</b>{html.escape(employer_name)}</div>
</div>
<table class="daily"><thead><tr><th style="width:7%">Data</th><th style="width:5%">Dia</th><th style="width:25%">Marcações</th><th style="width:7.5%">Horas<br>normais</th><th style="width:6.5%">Extras</th><th style="width:6.5%">Atraso</th><th style="width:7.5%">Faltas</th><th style="width:10%">Atestado/<br>Abono/Férias</th><th>Observações</th></tr></thead>
<tbody>{"".join(rows)}</tbody></table>
<div class="legend"><span class="m">ᴹ</span> ajuste manual &nbsp;·&nbsp; <span class="p">ᴾ</span> pendente de aprovação (não considerada no cálculo) &nbsp;·&nbsp; <span class="e">ᴱ</span> registro externo (incluído pela API) &nbsp;·&nbsp; Linhas em vermelho: inconsistência &nbsp;·&nbsp; Valores em hh:mm; entre parênteses, horas centesimais.</div>
<div class="sec">Totais do período</div>
<table class="tot">{total_rows}</table>
{alert_html}
<div class="decl">{declaration}</div>
<div class="sign"><div>{html.escape(name)}<br>Funcionário(a)</div><div>{html.escape(employer_name)}<br>Empresa</div></div>
<div class="foot">{html.escape(place)}____/____/________</div>
</div>"""


def wrap_document(body: str, title: str) -> str:
    return (
        "<!doctype html><html lang=\"pt-BR\"><head><meta charset=\"utf-8\">"
        f"<title>{html.escape(title)}</title><style>{CSS}</style></head><body>{body}</body></html>"
    )


def find_chrome(explicit: str | None) -> str:
    if explicit:
        if Path(explicit).is_file() or shutil.which(explicit):
            return explicit
        raise SystemExit(f"Chrome/Chromium não encontrado em {explicit}.")
    env_path = os.environ.get("CHROME_PATH")
    if env_path:
        return env_path
    for candidate in CHROME_CANDIDATES:
        found = shutil.which(candidate)
        if found:
            return found
    raise SystemExit(
        "Chrome ou Chromium não encontrado. Instale um deles ou passe --chrome. "
        "Use --sem-pdf para gerar só o HTML."
    )


def write_pdf(chrome: str, html_path: Path, pdf_path: Path) -> None:
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        chrome,
        "--headless=new",
        "--no-sandbox",
        "--disable-gpu",
        "--no-pdf-header-footer",
        f"--print-to-pdf={pdf_path}",
        html_path.resolve().as_uri(),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0 or not pdf_path.is_file():
        detail = (result.stderr or result.stdout or "").strip()
        raise SystemExit(f"Falha ao gerar {pdf_path.name} com {chrome}.\n{detail}")


def employee_sort_key(employee: dict, employers: dict) -> tuple[str, str]:
    contract = employee.get("contract_data") or {}
    employer = employers.get(contract.get("payment_source")) or {}
    return ((employer.get("name") or "").casefold(), (employee.get("full_name") or "").casefold())


def generate(employees, schedules, employers, sheets, times, start, end, feriados, output: Path, make_pdf: bool, chrome: str | None) -> dict:
    completo = periodo_completo(start, end)
    html_dir = output / "html"
    pdf_dir = output / "funcionarios"
    html_dir.mkdir(parents=True, exist_ok=True)
    if make_pdf:
        pdf_dir.mkdir(parents=True, exist_ok=True)
        chrome_bin = find_chrome(chrome)
    else:
        chrome_bin = ""

    employees = sorted(employees, key=lambda item: employee_sort_key(item, employers))
    pages: list[str] = []
    summary = []
    used_slugs: set[str] = set()
    for employee in employees:
        employee_id = employee["_id"]
        contract = employee.get("contract_data") or {}
        employer = employers.get(contract.get("payment_source")) or {}
        page, alerts = build_page(
            employee,
            sheets.get(employee_id) or {},
            times.get(employee_id) or [],
            schedules.get(employee.get("work_schedule")) or "",
            employer,
            start,
            end,
            feriados,
            completo,
        )
        pages.append(page)
        summary.append(
            {
                "nome": employee.get("full_name") or "",
                "empregador": employer.get("name") or "",
                "alertas": alerts,
            }
        )
        base = slug(employee.get("full_name") or "")
        file_slug = base if base not in used_slugs else f"{base}-{employee_id[-6:]}"
        used_slugs.add(file_slug)
        html_path = html_dir / f"{file_slug}.html"
        html_path.write_text(wrap_document(page, employee.get("full_name") or file_slug), encoding="utf-8")
        if make_pdf:
            write_pdf(chrome_bin, html_path, pdf_dir / f"{file_slug}.pdf")

    tag = f"{start:%Y-%m}" if start.year == end.year and start.month == end.month else f"{start:%Y-%m-%d}_{end:%Y-%m-%d}"
    suffix = "" if completo else "-parcial"
    combined_name = f"fechamento-ponto-{tag}{suffix}"
    combined_html = html_dir / f"{combined_name}.html"
    combined_html.write_text(wrap_document("".join(pages), f"Fechamento ponto {tag}"), encoding="utf-8")
    if make_pdf:
        write_pdf(chrome_bin, combined_html, output / f"{combined_name}.pdf")

    report = {
        "periodo": {"inicio": start.isoformat(), "fim": end.isoformat(), "folha_completa": completo},
        "funcionarios": summary,
    }
    (output / "inconsistencias.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Modelo LEGADO (fallback) do espelho de ponto. O fechamento mensal usa o PDF oficial do TiqueAdmin."
    )
    parser.add_argument("--inicio", required=True, type=parse_date, help="Data inicial AAAA-MM-DD.")
    parser.add_argument("--fim", required=True, type=parse_date, help="Data final AAAA-MM-DD.")
    parser.add_argument("--saida", required=True, type=Path, help="Diretório de saída dos HTML, PDF e inconsistências.")
    parser.add_argument("--feriados", type=Path, default=None, help="Arquivo de feriados. Padrão: config/feriados.txt.")
    parser.add_argument("--dados", type=Path, default=None, help="Diretório com dump JSON local, em vez de chamar a API.")
    parser.add_argument("--sem-pdf", action="store_true", help="Gera só HTML, sem chamar o Chrome.")
    parser.add_argument("--chrome", default=None, help="Caminho do binário Chrome/Chromium.")
    return parser


def main(argv: list[str] | None = None) -> int:
    print(
        "Aviso: src/gerar.py é o modelo legado (fallback). "
        "O fechamento mensal usa o PDF oficial do TiqueAdmin.",
        file=sys.stderr,
    )
    args = build_parser().parse_args(argv)
    if args.inicio > args.fim:
        raise SystemExit("--inicio não pode ser posterior a --fim.")
    feriados_path = args.feriados or default_feriados_path()
    feriados = load_feriados(feriados_path, args.inicio, args.fim)
    if args.dados:
        employees, schedules, employers, sheets, times = load_from_dir(args.dados)
    else:
        token = os.environ.get(TOKEN_ENV, "")
        if not token.strip():
            raise SystemExit(f"Defina {TOKEN_ENV} ou passe --dados com um dump local.")
        try:
            employees, schedules, employers, sheets, times = load_from_api(args.inicio, args.fim, token)
        except ApiError as exc:
            raise SystemExit(str(exc)) from exc
    report = generate(
        employees,
        schedules,
        employers,
        sheets,
        times,
        args.inicio,
        args.fim,
        feriados,
        args.saida,
        make_pdf=not args.sem_pdf,
        chrome=args.chrome,
    )
    flagged = sum(1 for item in report["funcionarios"] if item["alertas"])
    print(f"{len(report['funcionarios'])} funcionários, {flagged} com apontamentos, em {args.saida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
