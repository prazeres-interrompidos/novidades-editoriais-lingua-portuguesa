"""Testes locais da detecção da paginação da BNP.

Não faz pedidos à BNP. Simula as três formas de paginação que o extractor
aceita: <a>, input/button e URL construída por JavaScript.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from update import extract_next_url  # noqa: E402

CURRENT = "https://bibliografia.bnportugal.gov.pt/bnp/bnp.exe/queryCDU?ambito=20250902&scdu=00"
EXPECTED = "https://bibliografia.bnportugal.gov.pt/bnp/bnp.exe/queryCDU?ambito=20250902&scdu=00&start=21"

CASES = {
    "anchor": f'''<a href="{EXPECTED}">20 seguintes</a>''',
    "input": f'''<input type="button" value="20 seguintes" onclick="window.location='{EXPECTED}'">''',
    "javascript": f'''<script>document.write('<a href="{EXPECTED}">20 seguintes</a>');</script>''',
}

for name, html in CASES.items():
    got = extract_next_url(html, CURRENT)
    if got != EXPECTED:
        raise SystemExit(f"Falhou {name}: esperado {EXPECTED!r}, obtido {got!r}")
    print(f"[OK] {name}: {got}")

# Um link de ficha bibliográfica próximo do texto "seguintes" não pode ser
# confundido com a paginação.
record_html = '''<a href="/bnp/bnp.exe/registo?2291997">ficha</a>
20 seguintes'''
if extract_next_url(record_html, CURRENT) is not None:
    raise SystemExit("Falha: a ficha /registo foi confundida com paginação")
print("[OK] ligações /registo não são confundidas com paginação")

print("=== PAGINAÇÃO BNP: TESTES LOCAIS OK ===")
