# Rotina de ponto — T&M Personalizados

Processo de RH da T&M Personalizados para acompanhar e fechar o ponto eletrônico registrado no [TiqueTaque](https://admin.tiquetaque.app), usando a API pública documentada em [`docs/api-tiquetaque.md`](docs/api-tiquetaque.md). A spec completa está em [`docs/openapi.yaml`](docs/openapi.yaml).

O ponto é batido pelos funcionários no app, na web ou no aparelho. O RH confere todo dia útil se o dia anterior fechou e, no dia 1, monta o espelho do mês anterior. Os empregadores da conta são Casa da Malha, CDM Confecções e WayUp.gg. O corte da folha (`period_cut_day` 31) é o mês civil, do dia 1 ao último dia.

Há duas rotinas:

| Rotina | Quando | O que faz |
| --- | --- | --- |
| [Checagem diária](docs/rotina-checagem-diaria.md) | Dias úteis, por volta das 08:00 (America/Sao_Paulo) | Confere o dia útil anterior de cada funcionário ativo e avisa o RH. |
| [Fechamento mensal](docs/rotina-fechamento-mensal.md) | Dia 1 de cada mês, por volta das 08:00 | Salva o PDF oficial do espelho no TiqueAdmin, um por funcionário, e junta num arquivo só para impressão. |

A pasta [`backup/`](backup/README.md) guarda só a cópia dos textos das rotinas e das skills; as rotinas não leem essa pasta.

A jornada esperada é de segunda a sexta, em geral 08:00–12:00 e 13:00–18:00. Parte do time faz 07:00–17:00. A API não devolve as horas da escala nem um calendário de feriados. O arquivo [`config/feriados.txt`](config/feriados.txt) lista os feriados da checagem diária e do modelo legado; 12/10 (Nossa Senhora Aparecida) é um deles. O PDF oficial do mês usa o calendário do próprio TiqueAdmin.

## Fechamento: PDF oficial do painel

Desde 2026-10-19 o documento do mês é o espelho oficial salvo no TiqueAdmin, não o layout montado por este repositório. Com a sessão já aberta em `https://admin.tiquetaque.app`:

1. Gestão de ponto → Espelho de ponto (`/time-closures`) → Período anterior
2. Em cada funcionário: Ver espelho → `+ Ações` → `Salvar em PDF`
3. Se o espelho ainda está aberto, o item é `Salvar prévia em PDF`

A rotina não fecha, não reabre, não gera e não assina espelho. Os PDFs oficiais são juntados num arquivo só para impressão. A API entra só na checagem de consistência, em leitura: dias inconsistentes e a situação Aberto ou Fechado. Se a sessão expirar, a rotina pede ao Guilherme para entrar de novo. O passo a passo está em [docs/rotina-fechamento-mensal.md](docs/rotina-fechamento-mensal.md).

O código deste repositório ainda não conduz o navegador. A checagem diária também está só documentada. Correção de batida faltante (`POST /times`, gravada como `registro externo`) e de afastamento (`POST /work-leaves`) só acontece depois da aprovação do Guilherme, fora do fechamento. Editar ou apagar batida, aprovar batida pendente, lançar justificativa e alterar escala não existem na API: isso é feito no TiqueAdmin.

## Modelo legado (fallback)

`src/gerar.py` ainda gera um espelho A4 a partir da API. É o modelo antigo, usado só quando o PDF oficial não pôde ser salvo. Não é o documento do fechamento. Ao rodar, ele mesmo avisa isso.

Requisitos: Python 3.11+ e Google Chrome ou Chromium. A lista em `requirements.txt` não traz pacotes pip; o PDF legado é impresso pelo navegador em modo headless.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export TIQUETAQUE_API_TOKEN="cole-o-token-aqui"

python src/gerar.py \
  --inicio 2026-09-01 \
  --fim 2026-09-30 \
  --saida output/2026-09-modelo
```

O token sai de TiqueAdmin → Integrações. O modelo da variável está em [`.env.example`](.env.example). Não grave o token no repositório, em arquivo commitado nem na linha de comando de um script versionado.

| Argumento | Uso |
| --- | --- |
| `--inicio`, `--fim` | Período `AAAA-MM-DD`. No modelo legado, o mês civil inteiro é o que traz banco de horas. |
| `--saida` | Diretório dos HTML, dos PDF individuais, do PDF consolidado e de `inconsistencias.json`. |
| `--feriados` | Lista de feriados. O padrão é `config/feriados.txt`. |
| `--dados DIR` | Em vez da API, lê um dump local já baixado. Continua sem commitar esse diretório. |
| `--sem-pdf` | Gera só o HTML, sem chamar o Chrome. |
| `--chrome CAMINHO` | Binário do Chrome/Chromium, se não estiver no `PATH`. |

Saída do modelo, para um mês cheio:

- `output/AAAA-MM-modelo/funcionarios/<nome>.pdf` — uma página A4 por funcionário
- `output/AAAA-MM-modelo/fechamento-ponto-AAAA-MM-consolidado.pdf` — todos no mesmo arquivo
- `output/AAAA-MM-modelo/html/` — HTML intermediário
- `output/AAAA-MM-modelo/inconsistencias.json` — apontamentos do período

Um período que não seja o mês inteiro recebe o sufixo `-parcial` e um aviso no PDF. O banco de horas fica como `n/d`.

Para repetir a geração com um dump já salvo (o layout é o JSON da API: `employees.json`, `schedules.json`, `payment_sources.json`, `timesheets.json` e `times/<id-do-funcionario>.json`):

```bash
python src/gerar.py --inicio 2026-09-01 --fim 2026-09-30 --saida output/2026-09-modelo --dados dumps/2026-09
```

## O que não entra no git

O [`.gitignore`](.gitignore) deixa de fora:

- `.env` e qualquer arquivo de ambiente com o token
- dumps da API e dados pessoais (cadastro, CPF, batidas, espelhos, afastamentos)
- PDF, PNG e HTML gerados, inclusive o relatório de inconsistências

Relatório gerado é documento de RH. Ele fica na máquina que rodou o fechamento, ou no e-mail e no chat descritos nas rotinas, e não neste repositório.
