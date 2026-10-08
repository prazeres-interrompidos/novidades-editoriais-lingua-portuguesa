"""Testes locais da detecção da paginação da BNP."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from update import extract_next_url  # noqa: E402

CURRENT = "https://bibliografia.bnportugal.gov.pt/bnp/bnp.exe/queryCDU?ambito=20250902&scdu=00"
EXPECTED = "https://bibliografia.bnportugal.gov.pt/bnp/bnp.exe/queryCDU?ambito=20250902&scdu=00&start=21"
EXPECTED_FORM = EXPECTED + "&next=20+seguintes"

CASES = {
    "anchor": f'''<a href="{EXPECTED}">20 seguintes</a>''',
    "input": f'''<input type="button" value="20 seguintes" onclick="window.location='{EXPECTED}'">''',
    "javascript": f'''<script>document.write('<a href="{EXPECTED}">20 seguintes</a>');</script>''',
    "form_get": f'''<form action="{CURRENT}" method="get"><input type="hidden" name="ambito" value="20250902"><input type="hidden" name="scdu" value="00"><input type="hidden" name="start" value="21"><input type="submit" name="next" value="20 seguintes"></form>''',
}

for name, html in CASES.items():
    got = extract_next_url(html, CURRENT)
    expected = EXPECTED_FORM if name == "form_get" else EXPECTED
    if got != expected:
        raise SystemExit(f"Falhou {name}: esperado {expected!r}, obtido {got!r}")
    print(f"[OK] {name}: {got}")

export_html = '''<a href="/bnp/bnp.exe/query.php?iso2709">ISO2709</a>
20 seguintes'''
if extract_next_url(export_html, CURRENT) is not None:
    raise SystemExit("Falha: a exportação ISO2709 foi confundida com paginação")
print("[OK] exportação ISO2709 não é confundida com paginação")

record_html = '''<a href="/bnp/bnp.exe/registo?2291997">ficha</a>
20 seguintes'''
if extract_next_url(record_html, CURRENT) is not None:
    raise SystemExit("Falha: a ficha /registo foi confundida com paginação")
print("[OK] ligações /registo não são confundidas com paginação")

print("=== PAGINAÇÃO BNP: TESTES LOCAIS OK ===")
