import html
import json
import re
import sys
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

TARGET_YEAR = 2026
PAGE_LIMIT = 2000


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
        return response.read(), response.headers.get("Content-Type", ""), response.status


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


def extract_next_url(page_html, current_url):
    """Encontra a próxima página de resultados da BNP.

    A BNP/WinLib não expõe a paginação sempre como um <a>. Em algumas
    respostas, o controlo "20 seguintes" é um input/botão ou é construído
    por JavaScript. Por isso tentamos, por ordem:
      1) href de links cujo texto indica "seguintes";
      2) atributos onclick/action associados ao controlo de paginação;
      3) URLs do próprio catálogo que aparecem na vizinhança de "seguintes".
    """
    current = urlparse(current_url)

    def normalise_candidate(value):
        if not value:
            return None
        value = html.unescape(str(value)).strip()
        value = value.replace('\\/', '/')
        value = value.replace('\\"', '"').replace("\\'", "'")

        # Remover prefixos JavaScript comuns.
        value = re.sub(r'^\s*(?:javascript:\s*)?(?:window\.)?location(?:\.href)?\s*=\s*', '', value, flags=re.I)
        value = value.strip(' \t\r\n\"\'()')

        # Procurar directamente uma URL do catálogo dentro do atributo/JS.
        match = re.search(
            r'(https?://[^\s\"\'<>]+/bnp/bnp\.exe/[^\s\"\'<>]+|'
            r'/?(?:bnp/)?bnp\.exe/[^\s\"\'<>]+)',
            value,
            re.I,
        )
        if match:
            value = match.group(1)

        absolute = urljoin(current_url, value)
        parsed = urlparse(absolute)
        if (
            absolute != current_url
            and parsed.scheme in ("http", "https")
            and parsed.netloc == current.netloc
            and "/bnp/bnp.exe/" in parsed.path
            and not re.search(r"/bnp/bnp\.exe/registo(?:\?|$)", parsed.path + ("?" + parsed.query if parsed.query else ""), re.I)
        ):
            return absolute
        return None

    # 1) Links normais.
    for match in re.finditer(
        r"<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a\s*>",
        page_html,
        re.I | re.S,
    ):
        label = strip_tags(match.group(2)).lower()
        if re.search(r"\b(?:\d+\s+)?seguintes?\b", label):
            candidate = normalise_candidate(match.group(1))
            if candidate:
                return candidate

    # 2) Controlo de paginação como input/button/form com onclick/action.
    tag_pattern = r"<(?:input|button|form)\b[^>]*>"
    for tag_match in re.finditer(tag_pattern, page_html, re.I | re.S):
        tag = tag_match.group(0)
        plain = strip_tags(tag).lower()
        value_match = re.search(r"\bvalue=[\"']([^\"']*)[\"']", tag, re.I)
        label = value_match.group(1).lower() if value_match else plain
        if not re.search(r"\b(?:\d+\s+)?seguintes?\b", label):
            continue
        for attr in ("onclick", "onchange", "action"):
            attr_match = re.search(
                rf"\b{attr}=[\"'](.*?)[\"']", tag, re.I | re.S
            )
            if not attr_match:
                continue
            candidate = normalise_candidate(attr_match.group(1))
            if candidate:
                return candidate

    # 3) Algumas páginas constroem o controlo através de JavaScript.
    # Procuramos URLs do catálogo perto da palavra "seguintes".
    for text_match in re.finditer(r"seguintes?", page_html, re.I):
        inicio = max(0, text_match.start() - 1800)
        fim = min(len(page_html), text_match.end() + 1800)
        context = page_html[inicio:fim]
        for url_match in re.finditer(
            r"(?:https?://[^\s\"'<>]+/bnp/bnp\.exe/[^\s\"'<>]+|"
            r"/?(?:bnp/)?bnp\.exe/[^\s\"'<>]+)",
            context,
            re.I,
        ):
            candidate = normalise_candidate(url_match.group(0))
            if candidate:
                return candidate

    return None


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

    if not full_title or not year or int(year) != TARGET_YEAR:
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
        "publication_year": TARGET_YEAR,
        "bibliographic_reference": reference,
    }


def harvest_bnp(source):
    start_urls = source.get("query_urls") or [source["query_url"]]
    records, seen = [], set()
    visited_urls = set()

    for start_url in start_urls:
        url = start_url
        pages = 0

        while url and url not in visited_urls and pages < PAGE_LIMIT:
            visited_urls.add(url)
            raw, content_type, status = fetch(url)
            page, encoding = decode_html(raw, content_type)
            pages += 1

            blocks = extract_bnp_blocks(page)
            page_found = 0
            for block in blocks:
                record = parse_bnp_record(block, source)
                if not record:
                    continue
                key = record["isbn"] or record["bnp_record_id"]
                if key in seen:
                    continue
                seen.add(key)
                records.append(record)
                page_found += 1

            next_url = extract_next_url(page, url)
            print(
                f"[BNP] consulta={url} | página={pages} | "
                f"blocos={len(blocks)} | novos_2026={page_found}"
            )

            # Nunca aceitar silenciosamente uma recolha truncada. Se a BNP
            # indica que existem resultados seguintes mas o extractor não
            # conseguiu descobrir o destino, a execução deve falhar para que
            # o catálogo não seja publicado como se estivesse completo.
            has_next_hint = bool(
                re.search(r"\b(?:\d+\s+)?seguintes?\b", page, re.I)
            )
            if not next_url and has_next_hint and len(blocks) >= 20:
                raise RuntimeError(
                    "A BNP indica paginação ('seguintes'), mas não foi possível "
                    "determinar a URL da página seguinte. Recolha interrompida "
                    "para evitar um catálogo incompleto."
                )

            url = next_url

    print(
        f"[BNP] páginas percorridas: {len(visited_urls)} | "
        f"registos únicos de {TARGET_YEAR}: {len(records)}"
    )
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
    print(f"Extractor BNP: bnp_catalog_html | ano-alvo: {TARGET_YEAR}")
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
            print(f'[OK] {source["name"]}: {len(found)} registos de {TARGET_YEAR}')
        except Exception as exc:
            print(f'[ERRO] {source["name"]}: {exc}', file=sys.stderr)

    books = [b for b in books if b.get("publication_year") == TARGET_YEAR]
    books.sort(key=lambda item: (item.get("publication_year", 0), item.get("title") or ""), reverse=True)
    BOOKS.write_text(json.dumps(books, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"Concluído: {added} novos registos; {updated} registos actualizados; "
        f"{len(books)} livros de {TARGET_YEAR} no catálogo."
    )


if __name__ == "__main__":
    main()
