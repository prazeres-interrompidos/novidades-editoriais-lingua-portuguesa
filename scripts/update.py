"""Recolha automática e gratuita de novidades editoriais.

- Usa apenas páginas públicas e respeita robots.txt.
- Extrai JSON-LD de tipo Book/Product e listas ItemList.
- Deduplica por ISBN e, na ausência deste, por título+autor+editora.
- Mantém a fonte original de cada registo.
- Uma fonte que falhe não impede as restantes.

Para acrescentar uma fonte, editar data/sources.json.
"""
import json, re, sys, time
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser
from urllib.request import Request, urlopen
from html.parser import HTMLParser

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
SOURCES = DATA / 'sources.json'
BOOKS = DATA / 'books.json'
UA = 'NovidadesEditorialLusofona/1.0 (GitHub Actions)'


def allowed(url):
    p = urlparse(url)
    robots_url = f'{p.scheme}://{p.netloc}/robots.txt'
    try:
        rp = RobotFileParser()
        rp.set_url(robots_url)
        rp.read()
        return rp.can_fetch(UA, url)
    except Exception:
        return False


def fetch(url):
    if not allowed(url):
        raise RuntimeError('robots.txt não autoriza a recolha automática ou não está disponível')
    req = Request(url, headers={
        'User-Agent': UA,
        'Accept': 'text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8'
    })
    with urlopen(req, timeout=30) as r:
        return r.read().decode('utf-8', 'ignore')


class MetaParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.jsonld = []
        self._json = False
        self._buf = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'script' and a.get('type', '').lower() == 'application/ld+json':
            self._json = True
            self._buf = []

    def handle_endtag(self, tag):
        if tag == 'script' and self._json:
            raw = ''.join(self._buf).strip()
            try:
                self.jsonld.append(json.loads(raw))
            except Exception:
                pass
            self._json = False

    def handle_data(self, data):
        if self._json:
            self._buf.append(data)


def first(v):
    if isinstance(v, list):
        return v[0] if v else ''
    return v


def name_of(v):
    if isinstance(v, dict):
        return v.get('name') or v.get('alternateName') or ''
    if isinstance(v, list):
        names = [name_of(x) for x in v]
        return '; '.join(x for x in names if x)
    return v or ''


def image_of(v):
    if isinstance(v, dict):
        return v.get('url') or v.get('contentUrl') or ''
    if isinstance(v, list):
        return image_of(v[0]) if v else ''
    return v or ''


def flatten_jsonld(node):
    """Extrai Book/Product de JSON-LD, incluindo ItemList e @graph."""
    if isinstance(node, list):
        out = []
        for x in node:
            out.extend(flatten_jsonld(x))
        return out
    if not isinstance(node, dict):
        return []

    out = []
    typ = node.get('@type', '')
    types = typ if isinstance(typ, list) else [typ]

    if 'ItemList' in types:
        for item in node.get('itemListElement', []) or []:
            if isinstance(item, dict):
                obj = item.get('item') or item
                out.extend(flatten_jsonld(obj))
        return out

    if '@graph' in node:
        out.extend(flatten_jsonld(node['@graph']))

    if any(t in ('Book', 'Product') for t in types):
        author = name_of(node.get('author'))
        publisher = name_of(node.get('publisher'))
        image = image_of(node.get('image'))
        offers = node.get('offers') or {}
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        out.append({
            'title': node.get('name') or node.get('headline'),
            'author': author,
            'publisher': publisher,
            'isbn': node.get('isbn') or node.get('gtin13'),
            'cover': image,
            'source_url': node.get('url') or offers.get('url'),
            'date': node.get('datePublished') or node.get('releaseDate') or offers.get('availabilityStarts'),
            'genre': node.get('genre') or ''
        })
    return out


def extract_books(html):
    parser = MetaParser()
    parser.feed(html)
    out = []
    for doc in parser.jsonld:
        out.extend(flatten_jsonld(doc))
    clean = []
    seen = set()
    for b in out:
        title = str(b.get('title') or '').strip()
        if not title:
            continue
        key = (str(b.get('isbn') or '').strip(), re.sub(r'\W+', ' ', title.lower()).strip())
        if key in seen:
            continue
        seen.add(key)
        clean.append(b)
    return clean


def norm_key(b):
    isbn = re.sub(r'[^0-9Xx]', '', str(b.get('isbn') or ''))
    if isbn:
        return ('isbn', isbn)
    text = ' '.join(str(b.get(k) or '') for k in ('title', 'author', 'publisher')).lower()
    return ('text', re.sub(r'\W+', ' ', text).strip())


def source_urls(source):
    urls = source.get('urls') or []
    if not urls and source.get('url'):
        urls = [source['url']]
    return urls


def merge_record(old, new):
    """Prefere valores não vazios do novo registo sem apagar informação existente."""
    for k, v in new.items():
        if v not in ('', None, [], {}):
            old[k] = v
    return old


def main():
    sources = json.loads(SOURCES.read_text(encoding='utf-8'))
    books = json.loads(BOOKS.read_text(encoding='utf-8'))
    index = {norm_key(b): b for b in books}
    added = 0
    updated = 0

    for source in sources:
        if not source.get('automatic'):
            continue
        for url in source_urls(source):
            try:
                html = fetch(url)
                found = extract_books(html)
                for b in found:
                    b.update({
                        'country': source.get('country', ''),
                        'source_name': source.get('name', ''),
                        'source_url': b.get('source_url') or url,
                        'status': 'upcoming' if source.get('upcoming') else 'new'
                    })
                    if not b.get('genre'):
                        b['genre'] = ''
                    key = norm_key(b)
                    if key in index:
                        before = json.dumps(index[key], sort_keys=True, ensure_ascii=False)
                        merge_record(index[key], b)
                        after = json.dumps(index[key], sort_keys=True, ensure_ascii=False)
                        if before != after:
                            updated += 1
                    else:
                        books.append(b)
                        index[key] = b
                        added += 1
                print(f'[OK] {source["name"]}: {len(found)} registos em {url}')
                time.sleep(1)
            except Exception as e:
                print(f'[AVISO] {source["name"]}: {url} -> {e}', file=sys.stderr)

    books.sort(key=lambda x: (x.get('date') or '', x.get('title') or ''), reverse=True)
    BOOKS.write_text(json.dumps(books, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Concluído: {added} novos registos; {updated} registos actualizados; {len(books)} no catálogo.')


if __name__ == '__main__':
    main()
