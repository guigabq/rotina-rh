# API pública TiqueTaque

Resumo operacional da API usada no ponto da T&M Personalizados. A spec completa, no formato OpenAPI 3.0.2, está em [openapi.yaml](openapi.yaml). Este texto fixa o que as rotinas de RH dependem e o que a API não oferece.

## Base, autenticação e limite

| Item | Valor |
| --- | --- |
| Base | `https://api.tiquetaque.com/v2.1` |
| Autenticação | Basic Auth em todas as chamadas |
| Usuário | `public` |
| Senha | token gerado em TiqueAdmin → Integrações |
| Limite | 60 requisições por janela deslizante de 1 minuto |
| Acima do limite | HTTP `429 Too Many Requests` |
| Fuso das rotinas | `America/Sao_Paulo` |

O token vive na variável de ambiente `TIQUETAQUE_API_TOKEN`. Ele não é gravado no repositório.

Listagens paginadas aceitam `page` (padrão 1) e `max_results` (padrão 25). A resposta traz `_items`, `_meta` (`page`, `max_results`, `total`) e `_links`. Quem percorre funcionários, empregadores, usuários, unidades ou espelhos precisa somar as páginas até cobrir `_meta.total`.

Atualização (`PATCH`) e exclusão (`DELETE`) exigem o header `If-Match` com o `_etag` atual do documento. Sem o header a API responde 428; com etag velho, 412.

## Empregadores desta conta

A conta tem três empregadores, todos com `period_cut_day` 31. Com corte 31, a folha de cada mês vai do dia 1 ao último dia do mês.

| Empregador | Corte | Folha |
| --- | --- | --- |
| Casa da Malha | 31 | dia 1 ao último dia do mês |
| CDM Confecções | 31 | dia 1 ao último dia do mês |
| WayUp.gg | 31 | dia 1 ao último dia do mês |

`period_cut_day` não pode ser alterado por esta API depois que o empregador foi criado. Os nomes e o CNPJ vêm de `GET /payment-sources`; o código não guarda o id interno de cada um.

## Leitura

### `GET /employees` e `GET /employees/{id}`

Lista paginada dos funcionários **ativos**. A ausência de um campo significa que ele ainda não foi preenchido. Dá para filtrar por `payment_source` (id do empregador).

Campos usados no fechamento: `_id`, `full_name`, `cpf`, `nis`, `work_schedule` (id da escala), `contract_data.registration_number`, `contract_data.payment_source`, `contract_data.admission_date`, `contract_data.dismissal_date`, `contract_data.department`, `contract_data.job_role`.

`GET /employees` não devolve desligados. Quem foi inativado no mês anterior pode ficar de fora do fechamento automático e precisa ser conferido no TiqueAdmin.

### `GET /users` e `GET /users/{id}`

Usuários do painel (admin, admin-supervisor, supervisor, read-only), não a lista de funcionários.

### `GET /sites` e `GET /sites/{id}`

Unidades. O vínculo do funcionário com a unidade restringe o que um usuário não admin enxerga.

### `GET /payment-sources` e `GET /payment-sources/{id}`

Empregadores: razão social (`name`), `cpf` ou `cnpj`, endereço e `period_cut_day`. Filtros opcionais: `cnpj` e `cpf`, sem máscara.

### `GET /work-schedules/summary`

Lista paginada de escalas ativas e visíveis. Cada item tem só `_id` e `description` (o nome da escala). **A API não devolve os horários da escala.** O padrão de jornada (cerca de 08–12 / 13–18, e em alguns casos 07–17) não pode ser lido daqui; a checagem trata isso como heurística, e o ajuste da escala é no TiqueAdmin.

### `GET /times?employee_id&start_date&end_date`

Marcações brutas de **um** funcionário por chamada. Informe `employee_id` ou `employee_external_id`, nunca os dois. `start_date` e `end_date` são obrigatórios (`AAAA-MM-DD`).

Cada item de `times` traz:

| Campo | Significado |
| --- | --- |
| `time` | Data e hora, `AAAA-MM-DDTHH:MM` |
| `approved` | `true` ou `false`. Pendente não entra no cálculo do espelho |
| `type` | `pré-assinalado`, `aparelho`, `web`, `desconsiderado`, `app`, `reconhecimento facial`, `ajuste manual`, `offline`, `registro externo`, `N/D` |
| `justification` | Texto, quando existe |
| `location` | Longitude e latitude, quando a batida tem geolocalização |

Não há listagem de marcações de todos os funcionários numa chamada só. Com dezenas de pessoas, some `GET /times` e `GET /work-leaves` e respeite as 60 requisições por minuto.

Cadastro incompleto (sem escala ou sem empregador) pode responder 409. Funcionário inexistente responde 404.

### `GET /timesheets?start_date&end_date`

Espelho do período: totais e o mapa `days` (dia → rubricas e `horarios`). Sem filtro de funcionário, a resposta é uma lista paginada dos ativos que têm espelho no intervalo. Com `employee_id` ou `employee_external_id`, volta um único objeto. Os dois filtros juntos são erro. Funcionário com cadastro incompleto é ignorado na lista.

Valores em horas centesimais (string). Rubricas possíveis em `totals` e em cada dia: `total`, `horas_normais`, `banco_horas`, `falta_injustificada`, `falta_justificada`, `abono`, `folga`, `atraso`, `dsr`, `desconto_dsr`, `inss`, `atestado`, `dispensa_legal`, `adicional_noturno`, `adicional_noturno_extra_N`, `hora_noturna_reduzida`, `afastamento_nao_remunerado`, `sobreaviso`, `suspensao`, `ferias`, `extra_N` (por exemplo `extra_50`).

**Banco de horas só existe quando o intervalo é exatamente a folha de pagamento** (do início ao fim). Com `period_cut_day` 31, isso é o mês civil. Num período parcial — inclusive um recorte que só começa no dia 1, ou que atravessa duas folhas — o espelho volta com as outras rubricas e **sem** `banco_horas` e sem `hours_bank_summary`.

Quando a folha está completa, `hours_bank_summary` pode trazer `previous_balance`, `generated_balance`, `created_balance` e `final_balance`.

Na checagem de um único dia o período é parcial de propósito: serve para `atraso` e `falta_injustificada`, e não traz banco de horas.

### `GET /work-leaves`

Afastamentos de **um** funcionário. É obrigatório `employee_id` ou `employee_external_id`, mais `start_date` e `end_date`. Filtros opcionais: `type` e `status`.

Tipos: `abono`, `afastamento`, `atestado`, `dispensa_legal`, `falta_justificada`, `falta_injustificada`, `ferias`, `folga`, `inss`, `suspensao`.

Status: `aprovado`, `pendente`, `reprovado`. A aprovação também aparece em `approval_info.approved`.

Um afastamento de dia inteiro cobre de `start_date` a `end_date`. Se a resposta trouxer `start_time` e `end_time`, o afastamento é parcial e não dispensa as batidas do resto do dia.

## Escrita

### `POST /times`

Inclui **uma** batida. O corpo leva `employee_id` ou `employee_external_id`, e `time` (`AAAA-MM-DDTHH:MM`). A batida é gravada com `type` `registro externo`.

Não há campo de justificativa neste endpoint. A conta precisa da permissão de registros externos; sem ela a resposta é 403, com mensagem do tipo `No permission for external records`. A batida só aparece no TiqueAdmin se o funcionário já tiver escala e empregador.

A checagem diária usa este endpoint só para preencher batida faltante, e só depois da aprovação do Guilherme.

### `POST /work-leaves`, aprovação, rejeição e exclusão

Cria afastamento parcial ou de dia inteiro. Corpo: `employee_id` ou `employee_external_id`, `type`, `start_date`, `end_date`. Para parcial, incluir `start_time` e `end_time` (`HH:MM`).

| Chamada | Efeito |
| --- | --- |
| `PATCH /work-leaves/{id}/approve` | Aprova. Exige `If-Match` com o `_etag` |
| `PATCH /work-leaves/{id}/reject` | Rejeita. Exige `If-Match` |
| `DELETE /work-leaves/{id}` | Exclui. Exige `If-Match` |
| `GET /work-leaves/{id}` | Lê um afastamento |

A rotina lança atestado, abono, férias e os demais tipos por aqui, também só depois da aprovação do Guilherme.

### Cadastros

A API cria, lê, atualiza e remove funcionário, usuário, unidade e empregador:

| Recurso | Criar | Listar | Ler | Atualizar | Remover |
| --- | --- | --- | --- | --- | --- |
| Funcionário | `POST /employees`, `POST /employees/bulk` (até 100, atômico) | `GET /employees` | `GET /employees/{id}` | `PATCH /employees/{id}` | `DELETE /employees/{id}` |
| Usuário | `POST /users` | `GET /users` | `GET /users/{id}` | `PATCH /users/{id}` | `DELETE /users/{id}` |
| Unidade | `POST /sites` | `GET /sites` | `GET /sites/{id}` | `PATCH /sites/{id}` | `DELETE /sites/{id}` |
| Empregador | `POST /payment-sources` | `GET /payment-sources` | `GET /payment-sources/{id}` | `PATCH /payment-sources/{id}` | `DELETE /payment-sources/{id}` |

`PATCH` e `DELETE` desses recursos também exigem `If-Match`. O lote de funcionários valida tudo antes de gravar: se um item falha, ninguém é criado.

Esses cadastros não fazem parte da checagem diária nem do fechamento. Alteração de escala não está entre eles.

## O que a API não faz

Estas ações existem só no painel web TiqueAdmin, em <https://admin.tiquetaque.app>:

- Editar ou apagar uma batida já gravada.
- Aprovar batida pendente (`approved: false`). `POST /times` só acrescenta registro externo; não aprova o que já está na fila.
- Gravar justificativa de batida. `POST /times` não tem esse campo, e não há outro endpoint de justificativa.
- Alterar a escala (horários, dias, tolerâncias). `GET /work-schedules/summary` é somente leitura e não traz os horários.
- Baixar o PDF oficial do espelho de ponto. O PDF produzido por `src/gerar.py` é um fechamento montado com os dados da API. O espelho oficial do TiqueTaque continua no painel.

Também não há calendário de feriados. A lista usada pelas rotinas é `config/feriados.txt`, mantida pelo RH. O dia 12/10 (Nossa Senhora Aparecida) é uma das datas dessa lista.
