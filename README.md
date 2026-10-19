# Rotina de ponto — T&M Personalizados

Este repositório documenta o processo de ponto eletrônico da T&M Personalizados e guarda o código que apoia esse processo. O ponto roda no TiqueTaque. A integração usa a API pública, documentada em [docs/api-tiquetaque.md](docs/api-tiquetaque.md) e na spec [docs/openapi.yaml](docs/openapi.yaml).

Há duas rotinas:

1. **Checagem diária** — dias úteis, por volta das 08:00 (America/Sao_Paulo). Revisa o dia útil anterior de todos os funcionários ativos e avisa o RH. Descrição em [docs/rotina-checagem-diaria.md](docs/rotina-checagem-diaria.md).
2. **Fechamento mensal** — dia 1 de cada mês, por volta das 08:00. Monta o espelho do mês anterior, um PDF A4 por funcionário e um PDF consolidado. Descrição em [docs/rotina-fechamento-mensal.md](docs/rotina-fechamento-mensal.md).

O código deste repositório gera esses PDFs (`src/gerar.py`). Ele só lê a API. Correções de ponto (registro externo, afastamento) entram na API apenas depois da aprovação do Guilherme, como descrito na checagem diária. O que a API não faz — editar ou apagar batida, aprovar batida pendente, gravar justificativa, alterar escala, baixar o PDF oficial — continua no [TiqueAdmin](https://admin.tiquetaque.app).

Os empregadores da conta são Casa da Malha, CDM Confecções e WayUp.gg. O `period_cut_day` deles é 31: a folha vai do dia 1 ao último dia do mês.

## Como rodar o gerador

Requisitos: Python 3.11 ou superior e Google Chrome ou Chromium (para o PDF). Não há pacote pip; veja [requirements.txt](requirements.txt).

O token de integração sai do TiqueAdmin (Integrações) e fica só no ambiente, na variável `TIQUETAQUE_API_TOKEN`. O usuário da autenticação Basic é `public`; a senha é o token. Não commite o token, não o cole em issue, documento ou nome de arquivo.

```bash
cp .env.example .env
# edite .env e preencha TIQUETAQUE_API_TOKEN
set -a && source .env && set +a

python3 src/gerar.py \
  --inicio 2026-09-01 \
  --fim 2026-09-30 \
  --saida output/2026-09 \
  --feriados config/feriados.txt
```

| Argumento | Função |
| --- | --- |
| `--inicio` | Primeiro dia do período (`AAAA-MM-DD`). |
| `--fim` | Último dia do período (`AAAA-MM-DD`). |
| `--saida` | Diretório dos HTML, PDFs e do JSON de inconsistências. |
| `--feriados` | Arquivo de feriados. Opcional. O modelo versionado é `config/feriados.txt` (12/10, Nossa Senhora Aparecida, é uma das datas). |
| `--somente-html` | Não chama o Chrome; deixa só o HTML. |
| `--chrome` | Caminho do Chrome/Chromium. Se omitido, usa `CHROME_BIN` ou o executável do PATH. |

A base da API é `https://api.tiquetaque.com/v2.1`. Dá para apontar outro host com `TIQUETAQUE_API_BASE`.

Saída, para um fechamento de setembro:

```text
output/2026-09/
  html/                          páginas usadas na impressão
  funcionarios/*.pdf             um A4 por funcionário
  fechamento-ponto-2026-09-01_2026-09-30-consolidado.pdf
  inconsistencias.json           achados por funcionário
```

Esse diretório, os PDF, os HTML, os PNG e qualquer dump da API estão no `.gitignore`. O JSON de inconsistências traz nome de funcionário: é dado pessoal e não entra no git.

O gerador limita as chamadas para ficar abaixo de 60 requisições por minuto (janela deslizante da API). Banco de horas só aparece quando o período pedido é a folha inteira do empregador. Num recorte parcial o PDF sai marcado como modelo e o banco de horas fica como não disponível.

Para um período que não é o mês fechado:

```bash
python3 src/gerar.py \
  --inicio 2026-10-01 \
  --fim 2026-10-18 \
  --saida output/2026-10-parcial \
  --feriados config/feriados.txt \
  --somente-html
```

## O que não versionar

- `TIQUETAQUE_API_TOKEN` e qualquer arquivo `.env` com o valor real.
- Exportações e dumps (`employees.json`, marcações, espelhos, cache).
- PDF, HTML e PNG gerados.
- Nome, CPF, PIS, telefone, e-mail ou qualquer outro dado de funcionário.

O `.gitignore` cobre esses casos. A lista de feriados em `config/feriados.txt` é só data e nome do feriado.

## Layout do repositório

```text
README.md
CHANGELOG.md
requirements.txt
.env.example
.gitignore
config/feriados.txt
docs/api-tiquetaque.md
docs/openapi.yaml
docs/rotina-checagem-diaria.md
docs/rotina-fechamento-mensal.md
src/gerar.py
tests/test_gerar.py
```
