"""Teste isolado da ligação da BNP ao serviço OAI-PMH.
Não altera data/books.json nem o catálogo.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import update

sources = json.loads((ROOT / 'data' / 'sources.json').read_text(encoding='utf-8'))
bnp = next(s for s in sources if s.get('id') == 'bnp')
update.diagnose_oai(bnp)
