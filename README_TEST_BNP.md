# Teste BNP — extração de registos

Este teste não altera `data/books.json`.

O workflow `.github/workflows/test-bnp-extract.yml` consulta uma página pública da Bibliografia Nacional Portuguesa e verifica:

- HTTP e Content-Type;
- codificação real da resposta;
- ausência de caracteres de substituição `�`;
- número de registos indicado pela BNP;
- extracção de pelo menos 10 ISBNs e respetivo texto bibliográfico.

Só depois de este teste passar é que o conector será integrado no actualizador principal.
