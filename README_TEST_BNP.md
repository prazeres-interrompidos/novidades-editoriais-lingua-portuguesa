# Teste BNP — extração de registos

Este teste não altera `data/books.json`.

O workflow `.github/workflows/test-bnp-extract.yml` consulta uma página pública da Bibliografia Nacional Portuguesa e verifica:

- HTTP e Content-Type;
- codificação real da resposta;
- ausência de caracteres de substituição `�`;
- número de registos indicado pela BNP;
- extracção de pelo menos 10 ISBNs e respetivo texto bibliográfico.

Só depois de este teste passar é que o conector será integrado no actualizador principal.

## Teste 4 — Diagnóstico HTML

O workflow `Testar BNP — Diagnóstico HTML` descarrega a mesma página de resultados da BNP usada nos testes anteriores, localiza o primeiro ISBN e mostra a estrutura HTML existente em redor desse ISBN.

O workflow também guarda como artefactos:
- `bnp-diagnostico.html` — página completa recebida;
- `bnp-amostra-isbn.html` — janela de HTML em redor do primeiro ISBN.

Este teste não altera `data/books.json`, `data/catalog.js` ou `data/sources.json`.

