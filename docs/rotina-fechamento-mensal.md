# Fechamento mensal do ponto

No dia 1, o RH fecha o mês anterior com o **espelho oficial em PDF do TiqueAdmin**, um arquivo por funcionário, e junta esses PDFs num só para impressão. O layout montado por conta própria não é mais o documento do fechamento.

Desde 2026-10-19 o PDF que segue para o RH, para o chat e para a impressão é o que o painel salva. `src/gerar.py` continua no repositório só como modelo legado, para o caso de o PDF oficial não poder ser salvo.

## Quando

Dia 1 de cada mês, por volta das 08:00, fuso `America/Sao_Paulo`. O período é o mês civil anterior, do dia 1 ao último dia. Os três empregadores (Casa da Malha, CDM Confecções e WayUp.gg) usam `period_cut_day` 31, então essa é a folha cheia.

## De onde sai o PDF

Sessão já autenticada em `https://admin.tiquetaque.app`. A rotina não guarda senha e não faz login sozinha.

1. Gestão de ponto
2. Espelho de ponto (`/time-closures`)
3. Período anterior
4. Para cada funcionário: Ver espelho
5. `+ Ações`
6. `Salvar em PDF` quando o espelho está fechado. Se ainda está aberto, `Salvar prévia em PDF`

A rotina não fecha, não reabre, não gera e não assina espelho. Ela só salva o PDF que o painel já oferece. Espelho aberto continua aberto; o arquivo, nesse caso, é a prévia, com esse nome.

Se a sessão expirar, a rotina para e pede ao Guilherme para entrar de novo. Sem uma sessão válida ela não segue para o próximo funcionário nem troca para outro jeito de produzir o PDF.

Os arquivos oficiais são dado pessoal. Ficam no diretório de saída da máquina que rodou o fechamento (coberto pelo `.gitignore`) e não entram no git.

## Um arquivo só para impressão

Os PDFs salvos, um por funcionário, são juntados num único arquivo para impressão. A ordem é empregador e, dentro dele, nome. Individuais e o consolidado seguem juntos: o consolidado é a via de impressão; o individual é a via daquela pessoa.

## Checagem de consistência, só leitura

A API pública não entrega esse PDF. No fechamento ela entra apenas como checagem de consistência, em leitura. Nenhuma chamada cria batida, afastamento ou qualquer outro dado, e nada na API fecha o espelho.

A checagem registra, por funcionário:

- os dias inconsistentes do mês: marcação ímpar ou com menos de quatro batidas, dia útil sem batida e sem afastamento ou atestado, batida pendente de aprovação, falta injustificada, atraso, dia inteiro em ajuste manual, total diário que indica escala mal configurada
- a situação do espelho: Aberto ou Fechado

Aberto ou Fechado é o que define o rótulo no painel (`Salvar prévia em PDF` ou `Salvar em PDF`). A checagem anota a situação. Não muda.

Os dias saem de `GET /timesheets` e `GET /times` no mês, e de `GET /work-leaves` quando precisa confirmar afastamento. O limite continua 60 requisições por minuto. O relatório dessa checagem vai junto com os PDFs, para o RH ver o que ainda precisa de correção antes de tratar o mês como conferido. Não substitui o espelho oficial.

## Entrega

O PDF consolidado (e os individuais) segue por e-mail para `rh@tempersonalizados.com.br`. O remetente é a conta Gmail `administrativo@tempersonalizados.com.br`. A mesma entrega é avisada no chat do RH.

## Contabilidade

Os e-mails para a Índice Contabilidade são enviados manualmente pela empresa. Nenhuma rotina deste repositório escreve para o escritório.

## Correções antes de considerar o mês conferido

Os dias inconsistentes são revisados antes do envio. Vale a mesma regra da [checagem diária](rotina-checagem-diaria.md): batida faltante (`POST /times`, como `registro externo`) e afastamento (`POST /work-leaves`) só depois da aprovação do Guilherme. Editar ou apagar batida, aprovar pendência, lançar justificativa e corrigir escala é no TiqueAdmin.

A rotina de fechamento, ela mesma, não aplica essas correções e não fecha o espelho depois. Quem for corrigir faz isso à parte, com a aprovação do Guilherme. Em seguida os PDFs oficiais são salvos de novo. Espelho que seguiu Aberto continua saindo como prévia.

## Modelo legado (`src/gerar.py`)

O gerador em `src/gerar.py` monta um espelho A4 a partir da API (cabeçalho, tabela diária, totais, banco de horas, linhas de assinatura). É fallback. Não é o documento do fechamento e não substitui o PDF do TiqueAdmin.

Serve quando o painel não deixa salvar o oficial (sessão indisponível por tempo demais, ou falha do `Salvar em PDF`) e o RH precisa de uma via de trabalho enquanto o oficial não sai. O arquivo deixa isso explícito no topo: modelo legado.

O mês inteiro é obrigatório para o banco de horas nesse modelo. Fora da folha cheia, a API omite `banco_horas` e o PDF legado marca `n/d`. Os feriados desse modelo saem de [`config/feriados.txt`](../config/feriados.txt); 12/10 já está na lista. A API não fornece o calendário.

```bash
export TIQUETAQUE_API_TOKEN="cole-o-token-aqui"
python src/gerar.py --inicio 2026-09-01 --fim 2026-09-30 --saida output/2026-09-modelo
```

O token não é commitado. A saída (HTML, PDF e `inconsistencias.json`) também não.
