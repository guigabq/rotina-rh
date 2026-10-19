# Changelog

## 2026-10-19

- Documentação inicial, em português, do processo de ponto da T&M Personalizados sobre a API pública do TiqueTaque: visão geral, checagem diária e fechamento mensal.
- Spec OpenAPI 2.1 arquivada em `docs/openapi.yaml`, com o resumo operacional em `docs/api-tiquetaque.md`.
- `src/gerar.py` parametrizado (período, diretório de saída e feriados). O token é lido só de `TIQUETAQUE_API_TOKEN`. A partir desta data ele é o modelo legado, não o documento do fechamento.
- `.gitignore` cobre `.env`, dumps da API, dados pessoais de funcionários e PDF, PNG e HTML gerados.
- Fechamento mensal passa a usar o PDF oficial do TiqueAdmin: Gestão de ponto → Espelho de ponto (`/time-closures`) → Período anterior → Ver espelho → `+ Ações` → `Salvar em PDF` (ou `Salvar prévia em PDF` se o espelho segue aberto). A rotina não fecha, não reabre, não gera e não assina espelho. Os PDFs oficiais são juntados num arquivo para impressão. A API fica restrita à checagem de consistência, só leitura (dias inconsistentes e situação Aberto/Fechado). Sessão expirada: a rotina pede ao Guilherme para entrar de novo.
