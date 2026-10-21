# Rotina: Fechamento mensal do ponto por funcionário

- Agenda: dia 1º de cada mês por volta das 08:00 America/Sao_Paulo, flexível ±15 min (cron `0 8 1 * *`)
- Pasta da rotina: `fechamento-mensal-do-ponto-por-funcion-rio`

## Prompt salvo (dados sensíveis substituídos por marcadores)

On the 1st of each month, prepare the monthly ponto closing for the PREVIOUS month (1st to last day) for every active employee, using the OFFICIAL espelho de ponto PDF from the TiqueAdmin web panel (<GESTOR> requires the official PDF, not a self-made layout).

1. Official PDFs (box browser, via a browser subagent): the box browser is already signed in to https://admin.tiquetaque.app. Go to Gestão de ponto → Espelho de ponto (https://admin.tiquetaque.app/time-closures), select "Período anterior" (the previous month), and for each employee open "Ver espelho" and use "+ Ações" → "Salvar em PDF" (or "Salvar prévia em PDF" if the espelho is not closed yet). Download each PDF and save them under /workspace/fechamentos/AAAA-MM/oficial/ named by employee. Do NOT close, reopen, generate, sign, approve, edit or delete any espelho or record; only view and download. If the session expired and the login page appears, stop and ping <GESTOR> in this chat to sign in again (a run cannot fill passwords), then continue after he does. Then merge all PDFs into one combined file for printing (each employee starting on a new page).

2. Consistency check (read-only API): https://api.tiquetaque.com/v2.1, Basic Auth user "public", password from env TIQUETAQUE_API_TOKEN (never print it); spec at /workspace/tiquetaque/openapi.yaml. Call /timesheets for the full month and /times per employee (under 60 requests/minute) to list days still inconsistent (missing punches, pending approval, falta injustificada, schedule misconfiguration) that should be fixed in TiqueAdmin before printing, and whether each espelho shows as Aberto or Fechado.

Delivery: attach the combined official PDF to <GESTOR> in this Grok Bot chat with a short summary (employees included, which PDFs are prévia vs fechado, and the inconsistencies to fix before printing). Also email the combined PDF and the individual PDFs to <EMAIL_RH> from the user's connected Gmail account (<EMAIL_REMETENTE>), subject "Fechamento do ponto MM/AAAA"; <GESTOR> explicitly asked for this to be sent by the routine. Send nothing to anyone else, including the accounting firm.
