# Rotina: Checagem diária do ponto (Tique Taque)

- Agenda: dias úteis (seg-sex) por volta das 08:00 America/Sao_Paulo, flexível ±15 min (cron `0 8 * * 1-5`)
- Pasta da rotina: `checagem-di-ria-do-ponto-tique-taque`

## Prompt salvo (dados sensíveis substituídos por marcadores)

Check the previous workday's time records in TiqueTaque for all active employees and report anything wrong, in pt-BR. On Monday, check Friday (and any weekend punches). API: https://api.tiquetaque.com/v2.1, Basic Auth user "public", password from env TIQUETAQUE_API_TOKEN (never print it); spec at /workspace/tiquetaque/openapi.yaml. Use /timesheets for the day (everyone) and /times per employee to see pending/desconsiderado punches. Stay under 60 requests per minute.

Flag per employee: fewer than 4 punches or an odd count on a workday; a workday with no punches and no leave/atestado; punches pending approval; falta injustificada or atraso; suspicious 'ajuste manual' patterns; totals that look like a schedule misconfiguration (e.g. <FUNCIONARIO>'s "horario diferenciado"). Expected pattern is roughly 08-12 / 13-18 Mon-Fri, some 07-17; there's no holiday calendar in the API, so mention if the day may be a holiday.

For each problem, suggest the fix and say whether I can do it via API (add missing punch as 'registro externo', or create work-leave like atestado/abono/falta justificada) or whether it must be done in TiqueAdmin (approve pending punches, edit/delete punches, add justification). Do NOT write anything to TiqueTaque during this run; list the proposed API corrections numbered, and apply any of them only after <GESTOR> gives his ok in this Grok Bot chat.

Delivery: email the report (subject "Ponto - checagem de DD/MM/AAAA", short summary first, then a compact per-employee list with the numbered proposed corrections) to <EMAIL_RH> using the user's connected Gmail account (<EMAIL_REMETENTE>). <GESTOR> explicitly asked for this email to be sent by the routine without a draft review. Send nothing to anyone else. Then post a one-line note to <GESTOR> in this Grok Bot chat saying the report went out and how many problems were found, so he can reply here with which corrections to apply. If everything is correct, the email just says the previous day's ponto is all ok, and the chat note says the same.
