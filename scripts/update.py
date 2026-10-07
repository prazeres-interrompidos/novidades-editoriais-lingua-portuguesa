"""Recolha automática de novidades editoriais de fontes institucionais."""
import html
import json
import re
import sys
from datetime import date
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SOURCES = DATA / "sources.json"
BOOKS = DATA / "books.json"

UA = (
    "NovidadesEditorialLusofona/1.0 "
    "(+https://github.com/prazeres-interrompidos/"
    "novidades-editoriais-lingua-portuguesa)"
)


def allowed(url):
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    try:
        rp = RobotFileParser()
        rp.set_url(robots_url)
        rp.read()
        return rp.can_fetch(UA, url)
    except HTTPError as exc:
        if exc.code == 404:
            return True
        print(f"[AVISO] robots.txt indisponível ({robots_url}): HTTP {exc.code}")
        return False
    except Exception as exc:
        print(f"[AVISO] não foi possível ler robots.txt: {exc}")
        return False


def fetch(url):
    if not allowed(url):
        raise RuntimeError(f"robots.txt não autoriza a recolha: {url}")
    request = Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
        },
    )
    with urlopen(request, timeout=60) as response:
        return response.read(), response.headers.get("Content-Type", "")


def decode_html(raw, content_type=""):
    match = re.search(r"charset\s*=\s*[\"']?\s*([\w.-]+)", content_type or "", re.I)
    encodings = [match.group(1)] if match else []
    encodings += ["iso-8859-1", "cp1252", "utf-8"]
    seen = set()
    for enc in encodings:
        enc = enc.lower()
        if enc in seen:
            continue
        seen.add(enc)
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            pass
    return raw.decode("iso-8859-1", errors="replace"), "iso-8859-1-replace"


def strip_tags(value):
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def normalise_isbn(value):
    return re.sub(r"[^0-9Xx]", "", str(value or "")).upper()


def extract_isbn(text):
    for match in re.finditer(r"97[89](?:[\s-]?\d){10}", text):
        isbn = normalise_isbn(match.group(0))
        if len(isbn) == 13:
            return isbn
    return ""


def extract_bnp_blocks(page_html):
    return [
        m.group(0)
        for m in re.finditer(r"<li\b[^>]*>(.*?)</li\s*>", page_html, re.I | re.S)
        if re.search(r"/bnp/bnp\.exe/registo\?\d+", m.group(0), re.I)
    ]


def parse_bnp_record(block, source):
    record_match = re.search(r"/bnp/bnp\.exe/registo\?(\d+)", block, re.I)
    if not record_match:
        return None
    record_id = record_match.group(1)

    title_match = re.search(
        r"<span\b[^>]*class=[\"'][^\"']*\btitulo\b[^\"']*[\"'][^>]*>(.*?)</span\s*>",
        block, re.I | re.S
    )
    title = strip_tags(title_match.group(1)) if title_match else ""

    image_match = re.search(r"<img\b[^>]*src=[\"']([^\"']+)[\"']", block, re.I)
    cover = html.unescape(image_match.group(1)).strip() if image_match else ""
    if cover:
        cover = urljoin(source.get("base_url", source.get("query_url", "")), cover)

    visible = re.sub(r"<script\b.*?</script\s*>", " ", block, flags=re.I | re.S)
    visible = re.sub(r"<noscript\b.*?</noscript\s*>", " ", visible, flags=re.I | re.S)
    visible = re.sub(r"<style\b.*?</style\s*>", " ", visible, flags=re.I | re.S)
    visible = strip_tags(visible)

    reference = visible.split("Link persistente:", 1)[0]
    reference = re.sub(r"^\s*[-–—]\s*", "", reference).strip()

    isbn = extract_isbn(reference)
    if not isbn:
        return None

    after_title = reference
    if title:
        position = reference.find(title)
        if position >= 0:
            after_title = reference[position + len(title):].lstrip(" :")

    subtitle = ""
    if " / " in after_title:
        subtitle = after_title.split(" / ", 1)[0].strip(" :")

    full_title = title
    if subtitle and subtitle.lower() != title.lower():
        full_title = f"{title} : {subtitle}"

    author = ""
    author_match = re.search(
        r"\s/\s(.+?)(?=\s+-\s+[^-]+?\s+-\s+)",
        after_title, re.S
    )
    if author_match:
        author = re.sub(r"\s+", " ", author_match.group(1)).strip().rstrip(".")

    place = publisher = year = ""
    publication_match = re.search(
        r"\s+-\s+[^-]+?\s+-\s+(.+?)\s*:\s*(.+?),\s*((?:19|20)\d{2})\b",
        after_title, re.S
    )
    if publication_match:
        place = re.sub(r"\s+", " ", publication_match.group(1)).strip()
        publisher = re.sub(r"\s+", " ", publication_match.group(2)).strip()
        year = publication_match.group(3)

    if not year:
        years = re.findall(r"\b((?:19|20)\d{2})\b", reference)
        if years:
            year = years[-1]

    permanent_match = re.search(
        r"Link persistente:\s*(https?://[^\s<]+)", visible, re.I
    )
    permanent_url = (
        html.unescape(permanent_match.group(1)).rstrip(".,;")
        if permanent_match
        else f"http://id.bnportugal.gov.pt/bib/bibnacional/{record_id}"
    )

    if not full_title or not year:
        return None

    publication_year = int(year)
    target_year = int(source.get("target_publication_year", 2026))
    if publication_year != target_year:
        return None

    return {
        "title": full_title,
        "author": author,
        "publisher": publisher,
        "country": source.get("country", "PT"),
        "genre": "",
        "date": year,
        "date_precision": "year",
        "status": "new",
        "source_name": source.get("name", "Bibliografia Nacional Portuguesa — BNP"),
        "source_url": permanent_url,
        "cover": cover,
        "isbn": isbn,
        "bnp_record_id": record_id,
        "place": place,
        "publication_year": publication_year,
        "bibliographic_reference": reference,
    }


def extract_next_page_url(page_html, current_url, base_url):
    """Obtém a ligação de paginação '20 seguintes' da BNP.

    A BNP constrói a paginação no próprio HTML. Em vez de adivinhar
    parâmetros internos, seguimos a ligação que a própria página fornece.
    """
    candidates = []
    for match in re.finditer(
        r"<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a\s*>",
        page_html, re.I | re.S,
    ):
        href, label = match.group(1), strip_tags(match.group(2)).lower()
        if "seguinte" in label or "próxima" in label or "proxima" in label:
            candidates.append(urljoin(base_url, html.unescape(href)))
    # Preferir a primeira ligação de página seguinte que ainda não seja a atual.
    for url in candidates:
        if url != current_url:
            return url
    return None


def harvest_bnp(source):
    current_url = source["query_url"]
    visited = set()
    records, seen = [], set()
    max_records = int(source.get("max_records", 10000))
    page_number = 0

    while current_url and current_url not in visited and len(records) < max_records:
        visited.add(current_url)
        raw, content_type = fetch(current_url)
        page, encoding = decode_html(raw, content_type)
        page_number += 1
        blocks = extract_bnp_blocks(page)
        print(
            f"[BNP] página {page_number}: {len(raw)} bytes; "
            f"codificação: {encoding}; {len(blocks)} blocos bibliográficos"
        )

        page_added = 0
        for block in blocks:
            record = parse_bnp_record(block, source)
            if not record:
                continue
            key = record["isbn"] or record["bnp_record_id"]
            if key in seen:
                continue
            seen.add(key)
            records.append(record)
            page_added += 1
            if len(records) >= max_records:
                break

        next_url = None if len(records) >= max_records else extract_next_page_url(
            page, current_url, source.get("base_url", current_url)
        )
        print(
            f"[BNP] página {page_number}: {page_added} registos 2026; "
            f"total acumulado: {len(records)}"
        )
        if not next_url:
            break
        current_url = next_url

    print(f"[BNP] páginas percorridas: {page_number}")
    print(f"[BNP] registos 2026 válidos normalizados: {len(records)}")
    return records


def norm_key(book):
    isbn = normalise_isbn(book.get("isbn"))
    if isbn:
        return ("isbn", isbn)
    text = " ".join(str(book.get(k) or "") for k in ("title", "author", "publisher"))
    return ("text", re.sub(r"\W+", " ", text).strip().lower())


def merge_record(old, new):
    changed = False
    for key, value in new.items():
        if value not in ("", None, [], {}) and old.get(key) != value:
            old[key] = value
            changed = True
    return changed


def main():
    sources = json.loads(SOURCES.read_text(encoding="utf-8"))
    books = json.loads(BOOKS.read_text(encoding="utf-8"))
    index = {norm_key(book): book for book in books}
    added = updated = 0

    active = [s for s in sources if s.get("automatic")]
    print(f"Fontes institucionais automáticas activas: {len(active)}")

    for source in active:
        try:
            if source.get("connector") != "bnp_catalog_html":
                print(f'[AVISO] {source["name"]}: conector não activado')
                continue
            found = harvest_bnp(source)
            for book in found:
                key = norm_key(book)
                if key in index:
                    if merge_record(index[key], book):
                        updated += 1
                else:
                    books.append(book)
                    index[key] = book
                    added += 1
            print(f'[OK] {source["name"]}: {len(found)} registos')
        except Exception as exc:
            print(f'[ERRO] {source["name"]}: {exc}', file=sys.stderr)

    books.sort(key=lambda item: (item.get("date") or "", item.get("title") or ""), reverse=True)
    BOOKS.write_text(json.dumps(books, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Concluído: {added} novos registos; {updated} registos actualizados; {len(books)} no catálogo.")


if __name__ == "__main__":
    main()
