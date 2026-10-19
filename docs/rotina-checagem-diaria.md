# Rotina de checagem diária

Revisão do dia útil anterior, para o RH da T&M Personalizados pegar buraco de batida, falta e pendência antes do fechamento do mês.

## Quando

- Dias úteis (segunda a sexta).
- Por volta das **08:00**, fuso **America/Sao_Paulo**.
- Não roda sábado nem domingo.

## Dia verificado

A rotina olha o dia útil imediatamente anterior:

| Dia em que roda | Dia verificado |
| --- | --- |
| Terça, quarta, quinta, sexta | O dia anterior |
| Segunda | A sexta-feira anterior |

Ela não volta além dessa sexta. Se a sexta for feriado, a segunda ainda confere a sexta: com a data em `config/feriados.txt`, o dia não é tratado como falta; só entram anomalias reais (batida ímpar, pendência, ajuste manual suspeito).

A API não tem calendário de feriados. Sem uma data na lista, um feriado aparece como dia de trabalho sem batida. Quem mantém a lista é o RH. O formato está no próprio arquivo; 12/10 (Nossa Senhora Aparecida) é uma das datas.

## Quem entra

Todos os funcionários ativos (`GET /employees`). A lista da API já é a dos ativos.

Para cada um, no dia verificado:

- `GET /times?employee_id&start_date&end_date` — uma chamada por funcionário.
- `GET /work-leaves?employee_id&start_date&end_date` — o endpoint exige o funcionário.
- `GET /timesheets?start_date&end_date` — uma listagem do dia, para `atraso` e `falta_injustificada`. Como o intervalo é um dia só, a resposta não traz banco de horas.

Empregador e nome da escala vêm de `GET /payment-sources` e `GET /work-schedules/summary`. A escala só tem nome, sem horário.

São da ordem de duas chamadas por funcionário, mais as listagens. O teto é 60 requisições por minuto em janela deslizante. A rotina espaça as chamadas em vez de estourar e tomar HTTP 429.

## Jornada esperada

Segunda a sexta, a maior parte do quadro marca quatro batidas: entrada perto de **08:00**, saída para almoço perto de **12:00**, volta perto de **13:00**, saída perto de **18:00**. Algumas pessoas fazem **07:00–17:00**, também em quatro batidas, com intervalo no meio.

Isso é o padrão conhecido da operação. Não dá para ler esses horários na API. A checagem usa o padrão como heurística e separa o que é buraco de batida do que parece escala errada.

## O que é verificado

Contam as batidas com `type` diferente de `desconsiderado`. Batida desconsiderada entra só como observação.

1. **Menos de quatro batidas, ou quantidade ímpar.** Quatro é o dia completo (entrada, almoço, volta, saída). Ímpar significa entrada sem saída, ou o contrário. Duas batidas num dia útil, sem afastamento, indicam intervalo não registrado.
2. **Dia útil sem batida e sem afastamento.** Sem marcação e sem afastamento aprovado que cubra o dia (atestado, abono, férias, folga, dispensa legal, INSS, afastamento, falta justificada, suspensão). Afastamento pendente ou reprovado não cobre o dia. Afastamento parcial (`start_time` / `end_time`) não dispensa as batidas do resto da jornada.
3. **Batida pendente.** Qualquer marcação com `approved: false`. Pendente não entra no cálculo do espelho e precisa de decisão no TiqueAdmin — a API não aprova batida.
4. **Falta injustificada ou atraso.** Rubricas `falta_injustificada` e `atraso` no espelho daquele dia.
5. **Ajuste manual suspeito.** O tipo `ajuste manual` pede olhar humano quando:
   - todas as batidas válidas do dia são ajuste manual;
   - há mais de um ajuste manual no mesmo dia;
   - o ajuste manual está pendente de aprovação;
   - muitos funcionários recebem ajuste manual no mesmo horário (lançamento em massa).
6. **Total que indica escala mal configurada.** O espelho do dia mostra `total` acima de 14 horas, ou quatro batidas no desenho 08–18 (ou 07–17) com total longe de cerca de 8h–9h — por exemplo horas normais zeradas, ou o dia inteiro caindo em hora extra. Como `/work-schedules/summary` não traz os horários, a correção da escala é no TiqueAdmin.

Fim de semana não é dia verificado, porque a rotina só roda em dia útil e olha o dia útil anterior. Feriado listado em `config/feriados.txt` não gera o alerta de “sem batida”.

## Relato

O relatório sai por dois caminhos, com o mesmo conteúdo:

- **E-mail**, da conta Gmail `administrativo@tempersonalizados.com.br` para `rh@tempersonalizados.com.br`.
- **Nota no chat** usado com o RH, com o resumo do dia (quantos funcionários, quem teve achado e qual foi).

Cada achado identifica empregador, funcionário, escala (nome), data verificada e o tipo do problema. O e-mail não leva dump da API nem CPF. Assunto sugerido: `Ponto — checagem dd/mm/aaaa`.

A rotina não corrige nada ao enviar o relatório.

## Correções

Toda correção escrita na API espera a **aprovação do Guilherme**. Sem essa aprovação, o achado fica só no relatório.

Depois da aprovação, o que a API alcança:

| Situação | Ação |
| --- | --- |
| Falta uma batida (dia ímpar, ou menos de quatro sem afastamento) | `POST /times` com `employee_id` e `time`. A batida entra como `registro externo`. Não há campo de justificativa. A conta precisa da permissão de registros externos. |
| Falta, atestado, abono, férias ou folga a lançar | `POST /work-leaves` (`type`, datas e, se for parcial, horários). Aprovar em seguida com `PATCH /work-leaves/{id}/approve` e o header `If-Match` igual ao `_etag`. |

Se a batida precisa de texto de justificativa, o `POST /times` não serve: o lançamento é feito no TiqueAdmin.

O restante é só no painel <https://admin.tiquetaque.app>:

- editar ou apagar batida;
- aprovar batida pendente;
- escrever justificativa;
- corrigir escala (horário, dias, tolerância).

O gerador em `src/gerar.py` não grava batida nem afastamento. Ele só lê a API para montar o PDF do fechamento.
