# Rotina: Checagem diária do ponto (Tique Taque)

- Agenda: dias úteis (seg-sex) por volta das 08:00 America/Sao_Paulo, flexível ±15 min (cron `0 8 * * 1-5`)
- Pasta da rotina: `checagem-di-ria-do-ponto-tique-taque`

## Prompt salvo (dados sensíveis substituídos por marcadores)

Run the skill "Conferência do ponto no TiqueTaque" (id confer-ncia-do-ponto-no-tiquetaque; load it with Skill and follow it) for the previous workday (on Monday, check Friday plus any weekend punches). If the skill can't be loaded, fall back to the backup at /workspace/backups-skills/nina/2026-10-23/rotina-checagem-diaria.md and say so in the chat note.

Read-only: do NOT write anything to TiqueTaque during this run. List the proposed API corrections numbered, and apply any of them only after <GESTOR> gives his ok in this Grok Bot chat.

Delivery: email the report (subject "Ponto - checagem de DD/MM/AAAA", short summary first, then a compact per-employee list with the numbered proposed corrections) to <EMAIL_RH> using the user's connected Gmail account (<EMAIL_REMETENTE>). <GESTOR> explicitly asked for this email to be sent by the routine without a draft review. Send nothing to anyone else. Then post a one-line note to <GESTOR> in this Grok Bot chat saying the report went out and how many problems were found, so he can reply here with which corrections to apply. If everything is correct, the email just says the previous day's ponto is all ok, and the chat note says the same.

## Versão anterior

Até 23/10/2026 o prompt tinha todo o passo a passo inline; hoje ele está na skill (`backup/skills/conferencia-do-ponto-no-tiquetaque.md`) e no histórico do git.
