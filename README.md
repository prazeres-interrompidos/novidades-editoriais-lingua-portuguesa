# Novidades Editoriais em Língua Portuguesa

## Primeiro objetivo: Portugal — livros publicados em 2026

Esta versão é a base de produção para o primeiro objectivo do projecto:
**recolher os livros publicados em Portugal em 2026 através de uma fonte
bibliográfica institucional**.

### Fonte automática

**Bibliografia Nacional Portuguesa — Biblioteca Nacional de Portugal (BNP).**

O extractor consulta as páginas públicas de Novidades da BNP nas principais
classes CDU e segue a paginação indicada pela própria BNP (incluindo a ligação
**20 seguintes**). Cada registo é analisado individualmente e só é aceite
quando a referência bibliográfica do próprio registo indica **2026**.

São recolhidos, quando disponíveis:

- título e subtítulo;
- autores e outras responsabilidades;
- local de publicação;
- editora;
- ano de edição/publicação;
- ISBN;
- capa;
- identificador BNP;
- ligação permanente para o registo bibliográfico.

A deduplicação é feita principalmente pelo ISBN e, quando necessário, pelo
identificador BNP.

### Datas

O projecto **não inventa dia nem mês**. Quando a BNP fornece apenas o ano,
o catálogo guarda e apresenta:

**2026**

e não `01/01/2026`.

### Regra editorial

Não são usadas editoras, livrarias ou agregadores como fonte bibliográfica.
Os livros apresentados são provenientes de registos bibliográficos
institucionais da BNP.

### Outros países

As fontes institucionais dos restantes países continuam registadas em
`data/sources.json`, mas não fazem parte deste primeiro objectivo.

### Actualização automática

O GitHub Actions executa diariamente `scripts/update.py` e depois
`scripts/build_catalog.py`.

O extractor respeita `robots.txt` e não contorna regras de acesso.

### Estrutura

- `index.html`
- `styles.css`
- `app.js`
- `data/books.json`
- `data/sources.json`
- `data/catalog.js`
- `scripts/update.py`
- `scripts/build_catalog.py`
- `.github/workflows/update.yml`
