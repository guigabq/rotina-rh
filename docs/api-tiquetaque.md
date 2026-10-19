# API pública TiqueTaque

Resumo operacional da API usada no ponto da T&M Personalizados. A spec completa, sem edição, está em [`openapi.yaml`](openapi.yaml) (OpenAPI 3.0.2, versão 2.1).

## Acesso

| | |
| --- | --- |
| Base | `https://api.tiquetaque.com/v2.1` |
| Autenticação | HTTP Basic em toda requisição. Usuário `public`, senha = token gerado em TiqueAdmin → Integrações. |
| Variável local | `TIQUETAQUE_API_TOKEN` (só a senha; o usuário é sempre `public`) |
| Limite | 60 requisições por janela deslizante de 1 minuto. Acima disso a API responde `429 Too Many Requests`. |
| Paginação | Listas devolvem `_items`, `_meta` (`page`, `max_results`, `total`) e `_links`. `max_results` padrão é 25. |
| Concorrência | `PATCH` e `DELETE` exigem o header `If-Match` com o `_etag` atual do documento. `412` é etag velho; `428` é etag ausente. |
| Datas | `AAAA-MM-DD`. Horário de batida: `AAAA-MM-DDTHH:MM`, sem fuso no campo `time`. |
| Horas de rubrica | Horas centesimais em string (`1.50` = 1h30). Não são `HH:MM`. |
| Erros | Corpo com `_status: ERR`, `_error.code`, `_error.message` e `_error.ui_message`. |

O token não é commitado. Quem for chamar a API lê a variável de ambiente na hora.

## Empregadores da conta

`GET /payment-sources` devolve os empregadores ativos. Na conta da T&M Personalizados são três: Casa da Malha, CDM Confecções e WayUp.gg. Cada um tem `period_cut_day` 31, então a folha é o mês civil, do dia 1 ao último dia. Depois de criado o empregador, `period_cut_day` não pode ser alterado por esta API.

O nome, o CNPJ e o endereço usados no cabeçalho do espelho vêm deste recurso. Não há apelido fixo no código: o PDF usa o `name` cadastrado.

## Leitura

### Funcionários — `GET /employees` e `GET /employees/{id}`

Lista e detalhe só de funcionários ativos. Dá para filtrar a lista por `payment_source` (id do empregador). O cadastro traz nome, CPF ou CNPJ, NIS, cidade/UF de alocação, `work_schedule` e `contract_data` (matrícula, empregador, admissão, desligamento, cargo, departamento e as permissões de registro, entre elas `allow_external_api_record`).

A cidade do funcionário entra na conta de feriado que o TiqueTaque faz por conta própria. A API não devolve esse calendário.

### Usuários — `GET /users` e `GET /users/{id}`

Usuários gestores da conta (não são os funcionários).

### Unidades — `GET /sites` e `GET /sites/{id}`

Unidades ativas, com fuso e a cerca geográfica (`geofence_location`: raio em metros e longitude/latitude).

### Escalas — `GET /work-schedules/summary`

Lista paginada só de escalas ativas e visíveis: `_id` e `description` (o nome da escala). As horas da jornada não vêm neste endpoint. A referência 08:00–12:00 / 13:00–18:00 (e o grupo 07:00–17:00) é conhecimento do RH, não um campo da API.

### Batidas — `GET /times?employee_id&start_date&end_date`

Uma chamada por funcionário (`employee_id` ou `employee_external_id`; os dois juntos dão erro). Não há paginação nesse retorno: o corpo é `{ "employee_id", "times": [...] }`.

Cada item de `times`:

| Campo | Conteúdo |
| --- | --- |
| `time` | `AAAA-MM-DDTHH:MM` |
| `approved` | `true` ou `false`. Pendente (`false`) não entra no cálculo do espelho. |
| `type` | `pré-assinalado`, `aparelho`, `web`, `desconsiderado`, `app`, `reconhecimento facial`, `offline`, `ajuste manual`, `registro externo`, `N/D` |
| `justification` | Texto, quando existe. A API devolve; não há como gravar justificativa. |
| `location` | Longitude e latitude, quando a batida tem geolocalização. |

`desconsiderado` é batida ignorada. Cadastro incompleto (sem escala ou sem empregador) responde `409`.

### Espelho — `GET /timesheets?start_date&end_date`

Totais e o dia a dia. Sem filtro de funcionário, a resposta é uma lista paginada dos ativos que têm espelho no período (cadastro incompleto é ignorado). Com `employee_id` ou `employee_external_id`, volta um único objeto.

Cada espelho tem `employee_id`, `period`, `totals` e `days`. Em `days`, a chave é a data (`AAAA-MM-DD`) e o valor traz `horarios` (batidas válidas `HH:MM`) mais as rubricas daquele dia.

Rubricas possíveis em `totals` e no dia: `total`, `horas_normais`, `banco_horas`, `falta_injustificada`, `falta_justificada`, `abono`, `folga`, `atraso`, `dsr`, `desconto_dsr`, `inss`, `atestado`, `dispensa_legal`, `adicional_noturno`, `adicional_noturno_extra_N`, `hora_noturna_reduzida`, `afastamento_nao_remunerado`, `sobreaviso`, `suspensao`, `ferias`, `extra_N` (o `N` é a faixa, por exemplo `extra_50`).

Banco de horas (`banco_horas` em `totals` e em `days`, e o objeto `hours_bank_summary`) só é calculado quando o intervalo pedido é exatamente uma folha cheia, do início ao fim do período de pagamento. Com `period_cut_day` 31, isso é do dia 1 ao último dia do mês. Qualquer recorte parcial volta o resto do espelho e omite o banco de horas. `hours_bank_summary`, quando existe, traz saldo anterior, saldo gerado no período, saldo lançado à mão e saldo final.

### Afastamentos — `GET /work-leaves`

Exige `employee_id` ou `employee_external_id`, mais `start_date` e `end_date`. Devolve os afastamentos que cruzam o intervalo, paginados. Dá para filtrar por `type` e `status` (`aprovado`, `pendente`, `reprovado`).

Tipos: `abono`, `afastamento`, `atestado`, `dispensa_legal`, `falta_justificada`, `falta_injustificada`, `ferias`, `folga`, `inss`, `suspensao`.

## Escrita

Nada disso é disparado pelo gerador de PDF. Correção pela API, quando for o caso, só depois da aprovação do Guilherme. Ver as rotinas.

### `POST /times` — incluir batida

Cria uma batida, sempre com `type` `registro externo`. Corpo: `employee_id` ou `employee_external_id`, e `time` (`AAAA-MM-DDTHH:MM`). Não há campo de justificativa.

Exige a permissão de registros externos na conta. Sem ela a API responde `403` com `No permission for external records`. No funcionário, `allow_external_api_record` também precisa permitir o registro (o padrão do cadastro é `true`).

A batida só aparece no TiqueAdmin se o funcionário já tiver escala e empregador. Se esses campos forem preenchidos depois, as batidas antigas passam a aparecer.

### `POST /work-leaves` — incluir afastamento

Corpo: funcionário (`employee_id` ou `employee_external_id`), `type`, `start_date` e `end_date`. Para afastamento parcial, informar também `start_time` e `end_time`; dia inteiro leva só as datas.

- `PATCH /work-leaves/{id}/approve` aprova
- `PATCH /work-leaves/{id}/reject` reprova
- `DELETE /work-leaves/{id}` exclui
- `GET /work-leaves/{id}` lê um afastamento

Aprovar, reprovar e excluir exigem `If-Match`.

### Cadastros

Funcionário, usuário, unidade e empregador têm criação, leitura, atualização e exclusão:

| Recurso | Criar | Ler | Atualizar | Excluir |
| --- | --- | --- | --- | --- |
| Funcionários | `POST /employees` e `POST /employees/bulk` (até 100, atômico) | `GET /employees`, `GET /employees/{id}` | `PATCH /employees/{id}` | `DELETE /employees/{id}` |
| Usuários | `POST /users` | `GET /users`, `GET /users/{id}` | `PATCH /users/{id}` | `DELETE /users/{id}` |
| Unidades | `POST /sites` | `GET /sites`, `GET /sites/{id}` | `PATCH /sites/{id}` | `DELETE /sites/{id}` |
| Empregadores | `POST /payment-sources` | `GET /payment-sources`, `GET /payment-sources/{id}` | `PATCH /payment-sources/{id}` | `DELETE /payment-sources/{id}` |

Atualização e exclusão pedem `If-Match`. O `POST` de empregador não configura layout de exportação. O lote de funcionários valida todos os itens antes de gravar: se um falha, nenhum é criado.

## O que a API não faz

Estas operações existem só no painel TiqueAdmin (`https://admin.tiquetaque.app`):

- editar uma batida
- apagar uma batida
- aprovar batida pendente
- gravar ou alterar justificativa
- editar a escala (horários); a API só lista o nome em `/work-schedules/summary`
- baixar o PDF oficial do espelho de ponto

O PDF oficial do espelho sai do painel, no fluxo descrito na rotina de [fechamento mensal](rotina-fechamento-mensal.md). `src/gerar.py` monta um modelo A4 com os dados da API e ficou como fallback; não é o documento do fechamento.
