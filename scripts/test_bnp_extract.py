"""Teste de extracção de registos do catálogo público da BNP.
Não altera books.json. Testa a codificação da resposta e extrai os registos
bibliográficos visíveis numa página de resultados.
"""
import re
from html.parser import HTMLParser
from urllib.request import Request, urlopen

URL = "https://bibliografia.bnportugal.gov.pt/bnp/bnp.exe/queryCDU?ambito=20250902&scdu=00"
UA = "NovidadesEditorialLusofona/1.0 (+https://github.com/prazeres-interrompidos/novidades-editoriais-lingua-portuguesa)"

class ResultParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.parts = []
    def handle_data(self, data):
        if data:
            self.parts.append(data)
    def handle_entityref(self, name):
        self.parts.append(f"&{name};")
    def handle_charref(self, name):
        self.parts.append(f"&#{name};")
    def handle_starttag(self, tag, attrs):
        if tag.lower() in {'br','p','div','tr','li'}:
            self.parts.append('\n')
    def handle_endtag(self, tag):
        if tag.lower() in {'p','div','tr','li'}:
            self.parts.append('\n')

def decode_response(raw, content_type):
    # 1) HTTP charset, if the server declares one.
    m = re.search(r'charset\s*=\s*["\']?\s*([\w.-]+)', content_type or '', re.I)
    candidates = []
    if m:
        candidates.append(m.group(1))
    # 2) BOM / HTML meta charset.
    if raw.startswith(b'\xef\xbb\xbf'):
        candidates.insert(0, 'utf-8-sig')
    elif raw.startswith(b'\xff\xfe'):
        candidates.insert(0, 'utf-16')
    elif raw.startswith(b'\xfe\xff'):
        candidates.insert(0, 'utf-16-be')
    head = raw[:8192].decode('latin-1', errors='ignore')
    m2 = re.search(r'<meta[^>]+charset\s*=\s*["\']?\s*([\w.-]+)', head, re.I)
    if m2:
        candidates.insert(0, m2.group(1))
    candidates += ['utf-8', 'cp1252', 'iso-8859-1']

    seen = set()
    best = None
    for enc in candidates:
        enc = enc.lower()
        if enc in seen:
            continue
        seen.add(enc)
        try:
            text = raw.decode(enc, errors='strict')
            # Prefer a decode with no replacement and with common Portuguese chars intact.
            score = (text.count('\ufffd') * -1000) + sum(text.count(c) for c in 'áàãâéêíóôõúçÁÀÃÂÉÊÍÓÔÕÚÇ')
            if best is None or score > best[0]:
                best = (score, enc, text)
        except UnicodeDecodeError:
            continue
    if best:
        return best[1], best[2]
    return 'utf-8-replace', raw.decode('utf-8', errors='replace')

def clean(s):
    s = re.sub(r'&nbsp;?', ' ', s, flags=re.I)
    s = re.sub(r'&#160;', ' ', s, flags=re.I)
    s = re.sub(r'\s+', ' ', s)
    return s.strip()

def normalize_isbn(value):
    return re.sub(r'[^0-9Xx]', '', value).upper()

def extract_records(text):
    # The public BNP page renders numbered records. Preserve enough structure to split them.
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{2,}', '\n', text)
    chunks = re.split(r'(?m)(?=^\s*\d+\.\s+ISBN\s+)', text)
    out = []
    for chunk in chunks:
        chunk = clean(chunk)
        if not re.match(r'^\d+\.\s+ISBN\s+', chunk):
            continue
        m = re.search(r'\bISBN\s+([0-9Xx][0-9Xx\- ]{8,20})', chunk, re.I)
        if not m:
            continue
        isbn = normalize_isbn(m.group(1))
        if len(isbn) not in (10,13):
            continue
        body = chunk[m.end():].strip(' |.-')
        out.append({'isbn': isbn, 'raw': body})
    # fallback: if line splitting did not work, use ISBN anchors and nearby text
    if len(out) < 3:
        out = []
        matches = list(re.finditer(r'\bISBN\s+([0-9Xx][0-9Xx\- ]{8,20})', text, re.I))
        for i, m in enumerate(matches):
            isbn = normalize_isbn(m.group(1))
            if len(isbn) not in (10,13):
                continue
            end = matches[i+1].start() if i+1 < len(matches) else min(len(text), m.end()+700)
            body = clean(text[m.end():end])
            out.append({'isbn': isbn, 'raw': body})
    # deduplicate
    unique=[]; seen=set()
    for r in out:
        if r['isbn'] not in seen:
            seen.add(r['isbn']); unique.append(r)
    return unique

print('=== TESTE BNP / EXTRACÇÃO DE REGISTOS ===')
print(f'[1] URL: {URL}')
req = Request(URL, headers={'User-Agent': UA, 'Accept': 'text/html,application/xhtml+xml;q=0.9,*/*;q=0.8'})
with urlopen(req, timeout=45) as r:
    raw = r.read()
    status = r.status
    content_type = r.headers.get('Content-Type','')
print(f'[2] HTTP: {status}')
print(f'[3] Content-Type: {content_type}')
print(f'[4] bytes recebidos: {len(raw)}')
encoding, html = decode_response(raw, content_type)
print(f'[5] codificação detectada: {encoding}')
print(f'[6] caracteres de substituição (�): {html.count(chr(0xfffd))}')

p = ResultParser(); p.feed(html)
text = ''.join(p.parts)
text = text.replace('&amp;', '&')
text = re.sub(r'\n\s*\n+', '\n', text)

m = re.search(r'(\d[\d\s]*)registos encontrados', text, re.I)
print(f'[7] Registos indicados pela BNP: {m.group(1).strip() if m else "não identificado"}')
records = extract_records(text)
print(f'[8] Registos extraídos com ISBN: {len(records)}')
for i, r in enumerate(records[:10], 1):
    print(f'    {i}. ISBN {r["isbn"]} | {r["raw"][:500]}')

if len(records) >= 10 and html.count(chr(0xfffd)) == 0:
    print('=== RESULTADO BNP: EXTRACÇÃO E CODIFICAÇÃO FUNCIONAIS ===')
else:
    print('=== RESULTADO BNP: AINDA PRECISA DE AJUSTES ===')
    raise SystemExit(2)
