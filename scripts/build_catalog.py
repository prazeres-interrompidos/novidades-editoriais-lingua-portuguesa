import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'
books=json.loads((DATA/'books.json').read_text(encoding='utf-8'))
sources=json.loads((DATA/'sources.json').read_text(encoding='utf-8'))
out='window.__EDITORIAL_DATA__='+json.dumps({'books':books,'sources':sources},ensure_ascii=False,separators=(',',':'))+';\n'
(DATA/'catalog.js').write_text(out,encoding='utf-8')
print(f'Catálogo local gerado: {len(books)} livros, {len(sources)} fontes.')
