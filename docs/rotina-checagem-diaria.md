# Checagem diária do ponto

Conferência do dia útil anterior, para o RH da T&M Personalizados agir no mesmo dia em vez de descobrir o furo no fechamento.

## Quando

Dias úteis, por volta das 08:00, fuso `America/Sao_Paulo`. Não roda sábado nem domingo.

O dia analisado é o dia útil anterior:

- de terça a sexta, olha o dia de ontem
- na segunda, olha a sexta

A API não tem calendário de feriados. O arquivo [`config/feriados.txt`](../config/feriados.txt) diz se o dia analisado é feriado (12/10, Nossa Senhora Aparecida, é um deles). Feriado não é tratado como falta: o relatório marca o feriado. Se a segunda for feriado e a checagem daquele dia não rodar, a terça seguinte precisa revisar a sexta, que continua sendo o último dia útil pendente, e não só a segunda.

## Quem entra

Todos os funcionários ativos (`GET /employees` já devolve só os ativos), dos três empregadores: Casa da Malha, CDM Confecções e WayUp.gg.

## De onde vêm os dados

Para o dia D (um único `start_date` = `end_date` = D):

| Chamada | Para quê |
| --- | --- |
| `GET /employees` | Quem está ativo, escala, empregador, admissão. |
| `GET /work-schedules/summary` | Nome da escala. Não traz a grade de horários. |
| `GET /timesheets?start_date=D&end_date=D` | Rubricas do dia: horas normais, extras, atraso, faltas, atestado, abono, férias e o total. Como o período é de um dia, não vem banco de horas. |
| `GET /times?employee_id&start_date=D&end_date=D` | Batidas cruas, uma chamada por funcionário: horário, `type`, `approved`, `justification`. |
| `GET /work-leaves?employee_id&start_date=D&end_date=D` | Afastamento, atestado, férias e os demais tipos que expliquem a ausência. Este endpoint exige o funcionário. |

São duas chamadas por funcionário (batidas e afastamentos) mais as listas. O limite é 60 requisições por minuto em janela deslizante; a checagem espera quando se aproxima do teto e, em `429`, espera a janela virar.

## Jornada esperada

Segunda a sexta, quatro batidas: entrada, saída para o almoço, volta do almoço e saída. O horário usual é 08:00–12:00 e 13:00–18:00. Parte das pessoas faz 07:00–17:00, também com o intervalo no meio. Sábado e domingo são descanso.

A escala no TiqueTaque só aparece pelo nome. Total do dia muito fora dessa jornada é tratado como sinal de escala errada, não como hora extra automática.

## O que é apontado

Para cada funcionário ativo, no dia D, se D é dia útil e não é feriado:

1. Menos de quatro batidas, ou quantidade ímpar. Quatro é o esperado. Uma ou três batidas é marcação ímpar (falta a par). Duas batidas, sem afastamento, é intervalo não registrado. Zero batidas entra no item seguinte.
2. Dia útil sem nenhuma batida e sem afastamento nem atestado (nem rubrica de atestado/abono/férias/folga no espelho, nem registro em `/work-leaves`). Isso é falta sem justificativa.
3. Batida com `approved: false`. Pendente não entra na conta do espelho até alguém aprovar no TiqueAdmin.
4. `falta_injustificada` ou `atraso` nas rubricas do dia.
5. Padrão suspeito de `ajuste manual`: o dia em que toda batida válida é `ajuste manual`. Um ajuste isolado no meio de batidas de app ou aparelho aparece na observação do dia, porque pode ser uma correção legítima, e não dispara o mesmo alerta.
6. Total do dia acima de 14 horas. Isso indica escala mal configurada (ou batida de outro dia puxada para a jornada), não um dia normal de hora extra.

Batida `desconsiderado` não conta como marcação válida. Se o dia só tem batida desconsiderada, o relatório diz isso em vez de tratar como “nunca bateu”.

Feriado e fim de semana sem batida não geram falta. Se a pessoa bateu ponto no feriado, as batidas aparecem com a observação do feriado.

## Para onde vai o relatório

Um resumo do dia, com o nome de quem teve apontamento e o motivo, é enviado por e-mail para `rh@tempersonalizados.com.br`. O remetente é a conta Gmail `administrativo@tempersonalizados.com.br`.

O mesmo resumo vai como nota no chat do RH. O canal fica definido na implantação; este repositório ainda não publica essa mensagem.

Quem não teve apontamento não precisa ocupar o corpo do relatório: basta o total de conferidos e a data analisada, para ficar claro que a checagem rodou.

## Correções

A checagem só aponta. Ela não grava nada na API.

Depois que o Guilherme aprova a correção:

| Situação | Onde se corrige |
| --- | --- |
| Faltou uma batida e o horário é conhecido | `POST /times` com o funcionário e o `time`. A API grava `registro externo`, sem justificativa. Exige a permissão de registros externos na conta e `allow_external_api_record` no funcionário. |
| Atestado, abono, férias ou outro afastamento | `POST /work-leaves`. Se nascer pendente, `PATCH /work-leaves/{id}/approve` com o `If-Match`. |

O restante não tem endpoint. É feito no TiqueAdmin (`https://admin.tiquetaque.app`):

- editar ou apagar uma batida
- aprovar batida pendente
- escrever a justificativa (a API não aceita esse campo no `POST /times`)
- corrigir a escala

O PDF oficial do espelho também só existe no painel. A checagem diária não gera esse PDF.
