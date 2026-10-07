# Novidades Editoriais em Língua Portuguesa

Portal estático, gratuito e preparado para actualização automática de metadados editoriais dos oito países de língua portuguesa.

## Estrutura
- `index.html` — página principal
- `styles.css` — design responsivo
- `app.js` — pesquisa, filtros e cartões
- `data/books.json` — base de dados pública
- `data/sources.json` — catálogo de fontes e países
- `scripts/update.py` — recolha automática conservadora
- `.github/workflows/update.yml` — execução diária pelo GitHub Actions

## Publicação gratuita
1. Criar um repositório público no GitHub.
2. Copiar estes ficheiros para a raiz do repositório.
3. Em Settings > Pages, escolher `Deploy from a branch`, branch `main`, pasta `/root`.
4. A página ficará disponível gratuitamente no endereço `https://UTILIZADOR.github.io/NOME-DO-REPOSITORIO/`.
5. Em Actions pode executar manualmente o workflow `Actualizar novidades editoriais`.

## Fontes
A Bibliografia Nacional Portuguesa é uma fonte especialmente adequada: a BNP informa que os metadados do serviço são disponibilizados sob CC0. A APEL é a Agência Portuguesa do ISBN e também assegura o ISBN para Angola, Cabo Verde, Moçambique, São Tomé e Príncipe, Guiné-Bissau e Timor-Leste. A CBL é a Agência Brasileira do ISBN.

As fontes comerciais (WOOK, Bertrand, FNAC) estão no catálogo de fontes como fontes de descoberta. O actualizador respeita `robots.txt` e não contorna mecanismos de acesso. Antes de activar uma fonte comercial em produção, deve ser confirmada a permissão de recolha automatizada e as condições aplicáveis.

## Importante
A versão inicial é funcional como portal e como base para automação, mas a cobertura "todas as editoras" não pode ser garantida apenas com páginas comerciais. Cada país precisa de adaptadores bibliográficos específicos e de fontes abertas/estruturadas. O sistema foi desenhado para acrescentar esses conectores sem alterar a interface.

## Teste local
O `index.html` pode ser aberto directamente no navegador. O ficheiro `data/catalog.js` é uma cópia gerada automaticamente a partir de `books.json` e `sources.json`, evitando o bloqueio de `fetch()` quando a página é aberta através de `file://`. No GitHub Pages, os dados continuam a ser actualizados pelo workflow diário.


### Capas
As capas apresentadas nos cartões são carregadas a partir das imagens públicas das fontes originais. O sistema guarda apenas a URL da imagem, não uma cópia local.

## Automatização

O catálogo não se limita aos 14 livros iniciais. Esses registos são dados de arranque para testar a interface. O workflow de GitHub Actions executa `scripts/update.py` diariamente e pode também ser executado manualmente em **Actions → Actualizar novidades editoriais → Run workflow**.

O actualizador:
- consulta as fontes marcadas como `automatic: true`;
- respeita `robots.txt`;
- procura dados estruturados JSON-LD (`Book`, `Product` e `ItemList`);
- aceita várias URLs por fonte;
- deduplica por ISBN ou por título + autor + editora;
- preserva a fonte original;
- actualiza `data/books.json` e `data/catalog.js`.

A cobertura será ampliada progressivamente. Fontes institucionais como BNP, APEL, CBL e catálogos nacionais ficam registadas como fontes de referência até existir uma interface pública que possa ser consultada automaticamente de forma adequada.
