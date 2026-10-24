# Skill: Conferência do ponto no TiqueTaque

- Id: `confer-ncia-do-ponto-no-tiquetaque`
- Criada em 23/10/2026 com aprovação do Guilherme.

## Texto salvo

---
name: Conferência do ponto no TiqueTaque
description: >-
  Use para conferir as marcações de ponto de um dia (ou período) no TiqueTaque
  via API, apontar problemas por funcionário e propor correções numeradas, sem
  gravar nada.
---
# Conferência do ponto no TiqueTaque (somente leitura)

Entrada: a data a conferir (padrão: dia útil anterior; na segunda, a sexta + marcações do fim de semana). Saída: relatório em pt-BR com resumo + lista por funcionário + correções propostas numeradas.

## Acesso
- API: `https://api.tiquetaque.com/v2.1`, Basic Auth usuário `public`, senha no env `TIQUETAQUE_API_TOKEN` (nunca imprimir). Spec: `/workspace/tiquetaque/openapi.yaml`.
- Limite: menos de 60 requisições por minuto.
- Scripts de referência (última versão que funcionou): `/workspace/tiquetaque/daily/<data>/fetch.py`, `build.py`, `wl.py`; backup em `/workspace/backups-skills/nina/2026-10-23/scripts-checagem-diaria/`. Salvar dados do dia em `/workspace/tiquetaque/daily/AAAA-MM-DD/` (nunca em repositório).

## Passos
1. Listar funcionários ativos (`/employees`).
2. `/timesheets` do dia para todos (horas, faltas, atrasos, escala).
3. `/times` por funcionário para ver marcações pendentes de aprovação, desconsideradas e ajustes manuais.
4. Afastamentos do período (work leaves: atestado, abono, falta justificada) para não acusar falta já justificada.
5. Avaliar por funcionário:
   - dia útil com menos de 4 marcações ou número ímpar;
   - dia útil sem marcação e sem afastamento;
   - marcações pendentes de aprovação;
   - falta injustificada, atraso, saída antecipada (padrão ~08-12/13-18 seg-sex, alguns 07-17); repetição por vários dias merece destaque;
   - padrão suspeito de 'ajuste manual' (ex.: dia inteiro lançado manualmente = não usa o app);
   - totais que indicam escala mal configurada (ex.: escala "horario diferenciado" com 24h ou 17h/dia).
   - A API não tem calendário de feriados: avisar se o dia pode ser feriado.
6. Comparar com a conferência anterior: dizer o que já foi resolvido (ex.: aprovado/ajustado no TiqueAdmin).
7. Para cada problema, propor a correção e dizer onde se faz:
   - via API: incluir marcação faltante como `registro externo`; criar afastamento (atestado, abono parcial/total, falta justificada);
   - só no TiqueAdmin: aprovar pendentes, editar/excluir marcações, justificar.
   Numerar as propostas de API e marcar horários que precisam de confirmação.

## Regras
- NÃO gravar nada no TiqueTaque nesta conferência. Correções só depois do ok explícito do responsável no chat, uma a uma conforme aprovado.
- Nunca fechar, reabrir ou assinar espelhos.
- Não enviar dados de funcionários para terceiros (inclusive contabilidade); o destino do relatório é definido por quem chama a skill (rotina ou pedido).
