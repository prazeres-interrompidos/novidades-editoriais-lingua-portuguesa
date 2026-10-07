# Novidades Editoriais em Língua Portuguesa

Portal internacional de novidades editoriais em língua portuguesa.

O catálogo de produção é alimentado por fontes bibliográficas institucionais.
Não existem livros de demonstração ou livros de arranque no catálogo.

## Fonte automática actual

**Bibliografia Nacional Portuguesa (BNP)** — Portugal.

O conector lê a página pública da Bibliografia Nacional Portuguesa e identifica
os blocos bibliográficos reais dos resultados. Recolhe, quando disponíveis:

- título e subtítulo;
- autores e outras responsabilidades;
- local de publicação;
- editora;
- ano;
- ISBN;
- capa;
- identificador BNP;
- ligação permanente para o registo bibliográfico.

A deduplicação é feita principalmente pelo ISBN.

## Outros países

As fontes institucionais dos oito países continuam registadas em
`data/sources.json`. Apenas a BNP está actualmente automatizada. As restantes
serão activadas quando existir um conector público adequado.

## Actualização automática

O GitHub Actions executa diariamente `scripts/update.py` e depois
`scripts/build_catalog.py`.

A ausência de `robots.txt` na BNP (HTTP 404) não é tratada como bloqueio.
Outros erros de acesso ao `robots.txt` são tratados conservadoramente. O
projecto não contorna regras de robots.txt.

## Estrutura

- `index.html`
- `styles.css`
- `app.js`
- `data/books.json`
- `data/sources.json`
- `data/catalog.js`
- `scripts/update.py`
- `scripts/build_catalog.py`
- `.github/workflows/update.yml`
