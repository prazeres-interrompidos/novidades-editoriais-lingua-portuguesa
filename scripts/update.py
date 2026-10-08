import html
import json
import re
import sys
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse
from urllib.request import HTTPCookieProcessor, build_opener
from http.cookiejar import CookieJar
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
COOKIE_JAR = CookieJar()
OPENER = build_opener(HTTPCookieProcessor(COOKIE_JAR))


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


def fetch(url, method="GET", data=None):
    if not allowed(url):
        raise RuntimeError(f"robots.txt não autoriza a recolha: {url}")

    body = None
    headers = {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
    }
    if method.upper() == "POST":
        body = urlencode(data or []).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"

    request = Request(url, data=body, headers=headers, method=method.upper())
    with OPENER.open(request, timeout=60) as response:
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


def _catalog_candidate(value, current_url):
    if not value:
        return None
    value = html.unescape(str(value)).strip()
    value = value.replace("\\/", "/")
    value = value.replace('\\"', '"').replace("\\'", "'")
    value = re.sub(r'^\s*(?:javascript:\s*)?(?:window\.)?location(?:\.href)?\s*=\s*', '', value, flags=re.I)
    value = value.strip(' \t\r\n"\'()')

    match = re.search(
        r'(https?://[^\s"\'<>]+/bnp/bnp\.exe/[^\s"\'<>]+|'
        r'/?(?:bnp/)?bnp\.exe/[^\s"\'<>]+)',
        value, re.I,
    )
    if match:
        value = match.group(1)

    absolute = urljoin(current_url, value)
    parsed = urlparse(absolute)
    path_query = parsed.path + ("?" + parsed.query if parsed.query else "")
    if absolute == current_url:
        return None
    if parsed.scheme not in ("http", "https") or parsed.netloc != urlparse(current_url).netloc:
        return None
    if "/bnp/bnp.exe/" not in parsed.path:
        return None
    if re.search(r"/bnp/bnp\.exe/registo(?:\?|$)", path_query, re.I):
        return None
    # query.php?iso2709 é uma rota de exportação, não uma página de resultados.
    if re.search(r"/bnp/bnp\.exe/query\.php(?:\?|$)", path_query, re.I):
        return None
    return absolute


def _form_next_request(form_html, current_url):
    """Extrai uma submissão de formulário associada ao controlo '20 seguintes'."""
    if not re.search(r"(?:\d+\s+)?seguintes?", form_html, re.I):
        return None

    form_match = re.match(r"<form\b([^>]*)>(.*?)</form\s*>", form_html, re.I | re.S)
    if not form_match:
        return None
    attrs, inner = form_match.group(1), form_match.group(2)

    action_match = re.search(r"\baction=[\"']([^\"']*)[\"']", attrs, re.I)
    if action_match:
        raw_action = action_match.group(1).strip()
        action = current_url if not raw_action else _catalog_candidate(raw_action, current_url)
        if action is None and urljoin(current_url, raw_action) == current_url:
            action = current_url
    else:
        action = current_url
    if action is None:
        return None

    method_match = re.search(r"\bmethod=[\"']([^\"']+)[\"']", attrs, re.I)
    method = (method_match.group(1) if method_match else "GET").upper()

    fields = []
    submit_found = False
    controls = re.findall(r"<(?:input|button)\b[^>]*>(?:.*?</button\s*>)?", inner, re.I | re.S)
    for control in controls:
        type_match = re.search(r"\btype=[\"']([^\"']*)[\"']", control, re.I)
        ctype = (type_match.group(1) if type_match else "text").lower()
        name_match = re.search(r"\bname=[\"']([^\"']+)[\"']", control, re.I)
        value_match = re.search(r"\bvalue=[\"']([^\"']*)[\"']", control, re.I)
        label = value_match.group(1) if value_match else strip_tags(control)
        is_next = bool(re.search(r"(?:\d+\s+)?seguintes?", label, re.I))

        if ctype in ("submit", "button", "image") and is_next:
            submit_found = True
            if name_match:
                fields.append((name_match.group(1), value_match.group(1) if value_match else label))
            continue

        if ctype in ("hidden", "text", "search") and name_match:
            fields.append((name_match.group(1), value_match.group(1) if value_match else ""))

    if not submit_found:
        return None

    if method == "GET":
        parsed = urlparse(action)
        query_map = dict(parse_qsl(parsed.query, keep_blank_values=True))
        for key, value in fields:
            query_map[key] = value
        next_url = urlunparse(parsed._replace(query=urlencode(query_map, doseq=True)))
        return {"method": "GET", "url": next_url, "data": None, "source": "form"}

    if method == "POST":
        return {"method": "POST", "url": action, "data": fields, "source": "form"}

    return None


def extract_next_request(page_html, current_url):
    """Encontra a próxima página da BNP e devolve método, URL e dados."""
    # 1) Formulários: é a forma mais importante no catálogo BNP.
    for form_match in re.finditer(r"<form\b[^>]*>.*?</form\s*>", page_html, re.I | re.S):
        request = _form_next_request(form_match.group(0), current_url)
        if request and request["url"] != current_url:
            return request

    # 2) Links normais.
    for match in re.finditer(
        r"<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a\s*>",
        page_html, re.I | re.S,
    ):
        label = strip_tags(match.group(2)).lower()
        if re.search(r"\b(?:\d+\s+)?seguintes?\b", label):
            candidate = _catalog_candidate(match.group(1), current_url)
            if candidate:
                return {"method": "GET", "url": candidate, "data": None, "source": "anchor"}

    # 3) Input/button com onclick que contenha directamente a página seguinte.
    for tag_match in re.finditer(r"<(?:input|button)\b[^>]*>", page_html, re.I | re.S):
        tag = tag_match.group(0)
        value_match = re.search(r"\bvalue=[\"']([^\"']*)[\"']", tag, re.I)
        label = value_match.group(1) if value_match else strip_tags(tag)
        if not re.search(r"\b(?:\d+\s+)?seguintes?\b", label, re.I):
            continue
        for attr in ("onclick", "onchange"):
            attr_match = re.search(rf"\b{attr}\s*=\s*([\"\'])(.*?)\1", tag, re.I | re.S)
            if attr_match:
                candidate = _catalog_candidate(attr_match.group(2), current_url)
                if candidate:
                    return {"method": "GET", "url": candidate, "data": None, "source": attr}

    return None


def extract_next_url(page_html, current_url):
    request = extract_next_request(page_html, current_url)
    return request["url"] if request else None


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
    visited_requests = set()

    for start_url in start_urls:
        url = start_url
        method = "GET"
        data = None
        pages = 0

        while url and pages < PAGE_LIMIT:
            request_key = (method.upper(), url, tuple(data or []))
            if request_key in visited_requests:
                break
            visited_requests.add(request_key)
            raw, content_type, status = fetch(url, method=method, data=data)
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

            next_request = extract_next_request(page, url)
            next_url = next_request["url"] if next_request else None
            print(
                f"[BNP] consulta={url} | página={pages} | "
                f"blocos={len(blocks)} | novos_2026={page_found}"
            )
            if next_request:
                print(f"[BNP] paginação detectada: método={next_request['method']} | origem={next_request['source']}")

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

            if next_request:
                url = next_request["url"]
                method = next_request["method"]
                data = next_request["data"]
            else:
                url = None
                method = "GET"
                data = None

    print(
        f"[BNP] páginas percorridas: {len(visited_requests)} | "
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
