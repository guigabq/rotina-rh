# Rotina de fechamento mensal

No dia 1, o RH recebe o fechamento do mês anterior: um espelho imprimível em A4 por funcionário e um PDF com todos.

## Quando e qual período

- Roda no **dia 1** de cada mês, por volta das **08:00**, fuso **America/Sao_Paulo**.
- O período é o **mês anterior**.
- Os três empregadores (Casa da Malha, CDM Confecções e WayUp.gg) usam `period_cut_day` 31, então a folha é do dia 1 ao último dia daquele mês.

Exemplo: em 1º de outubro de 2026 o fechamento cobre 01/09/2026 a 30/09/2026.

O banco de horas só vem na API quando o intervalo é essa folha inteira. O comando abaixo pede o mês cheio de propósito.

## Como gerar

O script `src/gerar.py` lê o token de `TIQUETAQUE_API_TOKEN`, consulta a API e grava os arquivos. Passo a passo de ambiente está no [README](../README.md).

```bash
python3 src/gerar.py \
  --inicio 2026-09-01 \
  --fim 2026-09-30 \
  --saida output/2026-09 \
  --feriados config/feriados.txt
```

Troque início, fim e a pasta de saída para o mês que está fechando. Os feriados do mês precisam estar em `config/feriados.txt` (o 12/10 é uma das datas já listadas). Sem o Chrome, `--somente-html` deixa as páginas prontas para imprimir do navegador.

Arquivos em `--saida`:

| Caminho | Conteúdo |
| --- | --- |
| `funcionarios/<nome>.pdf` | Um A4 por funcionário, para imprimir e colher assinatura |
| `fechamento-ponto-<início>_<fim>-consolidado.pdf` | Todos os espelhos, um depois do outro |
| `html/` | HTML usado na conversão. Não é o documento que se envia |
| `inconsistencias.json` | Achados por funcionário. Dado pessoal: não commitar |

A pasta `output/` e os PDF/HTML/PNG estão no `.gitignore`.

Quem entra é o funcionário ativo (`GET /employees`) cujo contrato cruza o período: admitido depois do fim fica de fora; desligado antes do início também. A API só lista ativos. Alguém desligado ainda no mês anterior pode já ter saído dessa lista — o RH confere esses casos no TiqueAdmin para não fechar o mês sem eles.

## Conteúdo de cada espelho

Cabeçalho:

- empregador (razão social, CNPJ e endereço vindos de `/payment-sources`);
- nome do funcionário, matrícula, CPF, admissão, cargo/setor, PIS/NIS;
- nome da escala (`description` de `/work-schedules/summary`);
- competência e período.

Tabela diária, um linha por dia do período:

| Coluna | Origem |
| --- | --- |
| Data e dia da semana | calendário do período |
| Marcações | `GET /times` daquele funcionário. Hora em `HH:MM`. Sufixo ᴹ = ajuste manual; ᴾ = pendente de aprovação |
| Horas normais | espelho do dia |
| Extras | soma das rubricas `extra_N` do dia |
| Atraso | rubrica `atraso` |
| Faltas | `falta_injustificada` e `falta_justificada` |
| Atestado / abono / férias | também folga, dispensa legal, INSS, suspensão e afastamento não remunerado, quando houver |
| Observações | feriado da lista, inconsistências e ajustes manuais |

A linha fica destacada quando há inconsistência: marcação ímpar, dia útil sem batida e sem afastamento/atestado, só duas batidas (intervalo não registrado), batida pendente, ou total do dia acima de 14 horas (indício de escala mal configurada). Feriado listado no arquivo de feriados não é tratado como falta. Ajuste manual e batida desconsiderada aparecem na observação.

Totais do período, em `hh:mm`, com o valor centesimal da API entre parênteses:

- horas normais, extras por faixa, atraso, faltas, atestado, abono, férias, folga;
- **DSR** e desconto de DSR;
- **adicional noturno**, adicional noturno sobre extra e hora noturna reduzida;
- **banco de horas** — na folha cheia, o valor de `totals.banco_horas` e, quando a API manda, o resumo (`hours_bank_summary`: saldo anterior, gerado no período, lançado manualmente, saldo final). Em período parcial, o campo fica como não disponível;
- total apurado.

Abaixo dos totais, a lista de inconsistências a revisar antes de considerar o mês fechado. Em seguida, o texto de ciência do funcionário e duas linhas de assinatura: funcionário e empresa, com local (cidade/UF do empregador) e data em branco.

Um período que não é a folha inteira sai com tarja de modelo. O fechamento do dia 1 usa o mês cheio e não leva essa tarja.

## Envio

O pacote (PDF consolidado e PDFs individuais) segue por dois caminhos:

- **nota no chat** do RH, com os arquivos do mês;
- **e-mail** para `rh@tempersonalizados.com.br`.

O envio parte da mesma conta Gmail da checagem diária, `administrativo@tempersonalizados.com.br`.

## Contabilidade

A contabilidade é a **Índice Contabilidade**. O e-mail para o escritório é enviado manualmente pela empresa. Esta rotina não manda mensagem para a contabilidade e não escolhe o que anexar nesse encaminhamento.

## Espelho oficial no TiqueAdmin

O PDF deste repositório é montado com os dados da API pública (marcações, espelho e cadastros). Ele serve para a revisão interna e para a assinatura.

O PDF oficial do espelho, o que o TiqueTaque gera no produto, **não tem endpoint**. O plano é baixá-lo pelo painel web, em <https://admin.tiquetaque.app>, funcionário a funcionário, e arquivar junto deste fechamento. Até esse download existir, o arquivo oficial continua sendo obtido à mão no TiqueAdmin.
