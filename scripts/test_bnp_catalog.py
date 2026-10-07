"""Teste controlado da Bibliografia Nacional Portuguesa através do catálogo público.
Não altera books.json. Faz uma única consulta a uma página pública da BNP.
"""
import re
from html.parser import HTMLParser
from urllib.request import Request, urlopen

URL = "https://bibliografia.bnportugal.gov.pt/bnp/bnp.exe/queryCDU?ambito=20250902&scdu=00"
UA = "NovidadesEditorialLusofona/1.0 (+https://github.com/prazeres-interrompidos/novidades-editoriais-lingua-portuguesa)"

class TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts=[]
        self.links=[]
        self.in_a=False
        self.href=''
        self.link_text=[]
    def handle_data(self, data):
        t=data.strip()
        if t:
            self.parts.append(t)
            if self.in_a:
                self.link_text.append(t)
    def handle_starttag(self, tag, attrs):
        if tag.lower()=='a':
            self.in_a=True
            self.href=dict(attrs).get('href','')
            self.link_text=[]
    def handle_endtag(self, tag):
        if tag.lower()=='a' and self.in_a:
            self.links.append((self.href,' '.join(self.link_text)))
            self.in_a=False

print('=== TESTE BNP / CATÁLOGO PÚBLICO ===')
print(f'[1] URL: {URL}')
req=Request(URL, headers={'User-Agent':UA, 'Accept':'text/html,application/xhtml+xml;q=0.9,*/*;q=0.8'})
with urlopen(req, timeout=45) as r:
    raw=r.read()
    print(f'[2] HTTP: {r.status}')
    print(f'[3] bytes recebidos: {len(raw)}')

html=raw.decode('utf-8', errors='replace')
p=TextParser(); p.feed(html)
text=' '.join(p.parts)
text=re.sub(r'\s+',' ',text)

m=re.search(r'(\d[\d\s]*)registos encontrados', text, re.I)
print(f'[4] Registos indicados pela BNP: {m.group(1).strip() if m else "não identificado"}')

# Os resultados da BNP aparecem como "1 - ... ISBN ...". Extraímos os primeiros ISBNs.
pattern=re.compile(r'\b(?:ISBN\s+)?((?:97[89][\s-]?)?\d[\d\s-]{8,16}[\dXx])\b')
records=[]
for match in pattern.finditer(text):
    isbn=re.sub(r'[^0-9Xx]','',match.group(1)).upper()
    if len(isbn) in (10,13) and isbn not in [x[0] for x in records]:
        before=text[max(0,match.start()-500):match.start()]
        before=re.sub(r'^.*?\b\d+\s*-\s*','',before)
        records.append((isbn,before[-300:]))
    if len(records)>=10:
        break

print(f'[5] ISBNs detectados nos resultados: {len(records)}')
for i,(isbn,context) in enumerate(records,1):
    print(f'    {i}. ISBN {isbn} | {context}')

if len(records)>=3:
    print('=== RESULTADO BNP: FUNCIONAL PARA TESTE DE CATÁLOGO ===')
else:
    print('=== RESULTADO BNP: RESPOSTA RECEBIDA, MAS PARSING INSUFICIENTE ===')
    raise SystemExit(2)
