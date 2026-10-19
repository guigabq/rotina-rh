# Changelog

## 2026-10-19

- Documentação inicial, em português, do processo de ponto da T&M Personalizados na API pública do TiqueTaque: visão geral, referência da API, rotina de checagem diária e rotina de fechamento mensal.
- Spec OpenAPI 2.1 arquivada em `docs/openapi.yaml`.
- Gerador de espelhos em PDF (`src/gerar.py`), com período, diretório de saída e arquivo de feriados parametrizados. O token é lido de `TIQUETAQUE_API_TOKEN`.
- `.gitignore` para o token, dumps da API, dados pessoais e relatórios gerados (PDF, PNG, HTML).
