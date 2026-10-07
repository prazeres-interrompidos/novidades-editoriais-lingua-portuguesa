from pathlib import Path
import re
from urllib.request import Request, urlopen

URL = "https://bibliografia.bnportugal.gov.pt/bnp/bnp.exe/queryCDU?ambito=20250902&scdu=00"
UA = "NovidadesEditorialLusofona/1.0 (+https://github.com/prazeres-interrompidos/novidades-editoriais-lingua-portuguesa)"

print("=== TESTE BNP / DIAGNÓSTICO HTML ===")
print(f"[1] URL: {URL}")

req = Request(
    URL,
    headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
    },
)

with urlopen(req, timeout=60) as response:
    raw = response.read()
    content_type = response.headers.get("Content-Type", "")

print(f"[2] HTTP: {response.status}")
print(f"[3] Content-Type: {content_type}")
print(f"[4] bytes recebidos: {len(raw)}")

# O teste anterior confirmou ISO-8859-1.
html = raw.decode("iso-8859-1", errors="replace")

print(f"[5] caracteres: {len(html)}")
print(f"[6] caracteres de substituição: {html.count('�')}")

# Procurar ISBNs de 13 dígitos, aceitando espaços e hífenes.
isbn_pattern = r"(?<!\d)97[89](?:[\s-]?\d){10}(?!\d)"
matches = list(re.finditer(isbn_pattern, html))

print(f"[7] possíveis ISBNs encontrados: {len(matches)}")

if not matches:
    Path("bnp-diagnostico.html").write_text(html, encoding="utf-8")
    raise SystemExit("ERRO: não foi encontrado nenhum ISBN.")

match = matches[0]
isbn = re.sub(r"[^0-9]", "", match.group(0))

print(f"[8] Primeiro ISBN: {isbn}")
print(f"[9] posição no HTML: {match.start()}")

inicio = max(0, match.start() - 5000)
fim = min(len(html), match.end() + 5000)
trecho = html[inicio:fim]

print()
print("=" * 80)
print("=== HTML À VOLTA DO PRIMEIRO ISBN ===")
print("=" * 80)
print(trecho)
print("=" * 80)

print()
print("=== LINHAS/FRAGMENTOS QUE CONTÊM O ISBN ===")

for i, linha in enumerate(trecho.splitlines(), 1):
    digits = re.sub(r"[^0-9]", "", linha)
    if isbn in digits:
        print(f"[{i}] {linha}")

# Identificação simples das tags/classes próximas do ISBN.
print()
print("=== TAGS HTML PRÓXIMAS DO ISBN ===")

tags = re.findall(r"<[^>]+>", trecho)
for tag in tags:
    if any(x in tag.lower() for x in (
        "table", "tr", "td", "div", "span", "a ", "class=", "id="
    )):
        print(tag[:500])

Path("bnp-diagnostico.html").write_text(html, encoding="utf-8")
Path("bnp-amostra-isbn.html").write_text(trecho, encoding="utf-8")

print()
print("=== FICHEIROS DE DIAGNÓSTICO CRIADOS ===")
print("bnp-diagnostico.html")
print("bnp-amostra-isbn.html")
