"""Recolha institucional de novidades editoriais.

O projecto privilegia fontes bibliográficas institucionais e formatos de
interoperabilidade (actualmente OAI-PMH). Fontes comerciais bloqueadas por
robots.txt não fazem parte da configuração.
"""
import json, re, sys, time
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
SOURCES = DATA / 'sources.json'
BOOKS = DATA / 'books.json'
UA = 'NovidadesEditorialLusofona/1.0 (+https://github.com/prazeres-interrompidos/novidades-editoriais-lingua-portuguesa)'


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


def fetch(url, accept='application/xml,text/xml;q=0.9,*/*;q=0.8'):
    if not allowed(url):
        raise RuntimeError('robots.txt não autoriza a recolha automática ou não está disponível')
    req = Request(url, headers={'User-Agent': UA, 'Accept': accept})
    with urlopen(req, timeout=45) as r:
        return r.read()


def text(el, path):
    node = el.find(path, NS)
    return (node.text or '').strip() if node is not None and node.text else ''


def alltext(el, path):
    return [x.text.strip() for x in el.findall(path, NS) if x.text and x.text.strip()]


def localname(tag):
    return tag.rsplit('}', 1)[-1]


def first_nonempty(values):
    for v in values:
        if v:
            return v
    return ''


def parse_oai_dc(xml_bytes, source):
    root = ET.fromstring(xml_bytes)
    records = []
    for rec in root.findall('.//oai:record', NS):
        dc = rec.find('.//dc:dc', NS)
        if dc is None:
            continue
        vals = {}
        for child in list(dc):
            key = localname(child.tag)
            value = (child.text or '').strip()
            if value:
                vals.setdefault(key, []).append(value)
        title = first_nonempty(vals.get('title', []))
        if not title:
            continue
        creators = vals.get('creator', [])
        publishers = vals.get('publisher', [])
        identifiers = vals.get('identifier', [])
        isbn = ''
        for ident in identifiers:
            m = re.search(r'(?<!\d)(97[89]\d{10}|\d{9}[\dXx])(?!\d)', ident.replace('-', ''))
            if m:
                isbn = m.group(1).upper()
                break
        dates = vals.get('date', [])
        links = [x for x in identifiers if x.startswith(('http://', 'https://'))]
        records.append({
            'title': title,
            'author': '; '.join(creators),
            'publisher': '; '.join(publishers),
            'isbn': isbn,
            'date': first_nonempty(dates),
            'source_url': first_nonempty(links) or source.get('endpoint',''),
            'genre': '; '.join(vals.get('subject', [])),
        })
    return records


def harvest_oai(source):
    endpoint = source['endpoint']
    metadata_prefix = source.get('metadata_prefix', 'oai_dc')
    # A janela curta evita descarregar todo o catálogo em cada execução.
    since = (date.today() - timedelta(days=45)).isoformat()
    params = {'verb': 'ListRecords', 'metadataPrefix': metadata_prefix, 'from': since}
    out = []
    while True:
        url = endpoint + ('&' if '?' in endpoint else '?') + urlencode(params)
        raw = fetch(url)
        root = ET.fromstring(raw)
        out.extend(parse_oai_dc(raw, source))
        token = root.find('.//oai:resumptionToken', NS)
        token_text = (token.text or '').strip() if token is not None else ''
        if not token_text:
            break
        params = {'verb': 'ListRecords', 'resumptionToken': token_text}
        time.sleep(0.5)
    return out


def norm_isbn(value):
    return re.sub(r'[^0-9Xx]', '', str(value or '')).upper()


def norm_key(book):
    isbn = norm_isbn(book.get('isbn'))
    if isbn:
        return ('isbn', isbn)
    text = ' '.join(str(book.get(k) or '') for k in ('title','author','publisher')).lower()
    return ('text', re.sub(r'\W+', ' ', text).strip())


def merge_record(old, new):
    changed = False
    for k, v in new.items():
        if v not in ('', None, [], {}):
            if old.get(k) != v:
                old[k] = v
                changed = True
    return changed


def main():
    sources = json.loads(SOURCES.read_text(encoding='utf-8'))
    books = json.loads(BOOKS.read_text(encoding='utf-8'))
    index = {norm_key(b): b for b in books}
    added = updated = 0
    active = [s for s in sources if s.get('automatic')]
    print(f'Fontes institucionais automáticas activas: {len(active)}')

    for source in active:
        try:
            connector = source.get('connector')
            if connector == 'oai_pmh':
                found = harvest_oai(source)
            else:
                print(f'[AVISO] {source["name"]}: conector {connector!r} ainda não activado')
                continue
            for b in found:
                b.update({
                    'country': source.get('country',''),
                    'source_name': source.get('name',''),
                    'source_url': b.get('source_url') or source.get('endpoint',''),
                    'status': 'new'
                })
                key = norm_key(b)
                if key in index:
                    if merge_record(index[key], b):
                        updated += 1
                else:
                    books.append(b)
                    index[key] = b
                    added += 1
            print(f'[OK] {source["name"]}: {len(found)} registos')
        except Exception as e:
            print(f'[AVISO] {source["name"]}: {e}', file=sys.stderr)

    books.sort(key=lambda x: (x.get('date') or '', x.get('title') or ''), reverse=True)
    BOOKS.write_text(json.dumps(books, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Concluído: {added} novos registos; {updated} registos actualizados; {len(books)} no catálogo.')


NS = {
    'oai': 'http://www.openarchives.org/OAI/2.0/',
    'dc': 'http://purl.org/dc/elements/1.1/'
}

if __name__ == '__main__':
    main()
