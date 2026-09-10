#!/usr/bin/env python3
"""Descarga los feeds RSS de las fuentes y genera:
  data/raw/latest.json  (items completos, indexados por id)
  data/raw/latest.md    (lista compacta para leer y elegir notas)
Uso: python3 tools/fetch_feeds.py [--edicion manana|tarde|auto] [--horas N] [--max N]
"""
import argparse, html, json, re, sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
BA = timezone(timedelta(hours=-3))
UA = "Mozilla/5.0 (compatible; ResumenDiario/1.0)"

SOURCES = {
    "CL": {"nombre": "Clarín", "web": "https://www.clarin.com", "feeds": {
        "portada": "https://www.clarin.com/rss/lo-ultimo/",
        "politica": "https://www.clarin.com/rss/politica/",
        "economia": "https://www.clarin.com/rss/economia/",
        "mundo": "https://www.clarin.com/rss/mundo/",
        "sociedad": "https://www.clarin.com/rss/sociedad/",
        "deportes": "https://www.clarin.com/rss/deportes/",
        "viajes": "https://www.clarin.com/rss/viajes/"}},
    "LN": {"nombre": "La Nación", "web": "https://www.lanacion.com.ar", "feeds": {
        "portada": "https://www.lanacion.com.ar/arc/outboundfeeds/rss/?outputType=xml",
        "politica": "https://www.lanacion.com.ar/arc/outboundfeeds/rss/category/politica/?outputType=xml",
        "economia": "https://www.lanacion.com.ar/arc/outboundfeeds/rss/category/economia/?outputType=xml",
        "mundo": "https://www.lanacion.com.ar/arc/outboundfeeds/rss/category/el-mundo/?outputType=xml",
        "sociedad": "https://www.lanacion.com.ar/arc/outboundfeeds/rss/category/sociedad/?outputType=xml",
        "deportes": "https://www.lanacion.com.ar/arc/outboundfeeds/rss/category/deportes/?outputType=xml",
        "turismo": "https://www.lanacion.com.ar/arc/outboundfeeds/rss/category/turismo/?outputType=xml"}},
    "IB": {"nombre": "Infobae", "web": "https://www.infobae.com", "feeds": {
        "portada": "https://www.infobae.com/arc/outboundfeeds/rss/",
        "politica": "https://www.infobae.com/arc/outboundfeeds/rss/category/politica/",
        "economia": "https://www.infobae.com/arc/outboundfeeds/rss/category/economia/",
        "mundo": "https://www.infobae.com/arc/outboundfeeds/rss/category/america/mundo/",
        "sociedad": "https://www.infobae.com/arc/outboundfeeds/rss/category/sociedad/",
        "deportes": "https://www.infobae.com/arc/outboundfeeds/rss/category/deportes/",
        "turismo": "https://www.infobae.com/arc/outboundfeeds/rss/category/turismo/"}},
    "IP": {"nombre": "iProfesional", "web": "https://www.iprofesional.com", "feeds": {
        "portada": "https://www.iprofesional.com/rss/home",
        "economia": "https://www.iprofesional.com/rss/economia",
        "finanzas": "https://www.iprofesional.com/rss/finanzas",
        "negocios": "https://www.iprofesional.com/rss/negocios",
        "impuestos": "https://www.iprofesional.com/rss/impuestos",
        "legales": "https://www.iprofesional.com/rss/legales",
        "management": "https://www.iprofesional.com/rss/management",
        "realestate": "https://www.iprofesional.com/rss/realestate",
        "comex": "https://www.iprofesional.com/rss/comex",
        "turismo": "https://www.iprofesional.com/rss/turismo"}},
    "CR": {"nombre": "El Cronista", "web": "https://www.cronista.com", "feeds": {
        "portada": "https://www.cronista.com/files/rss/news.xml",
        "economia": "https://www.cronista.com/files/rss/economia-politica.xml",
        "finanzas": "https://www.cronista.com/files/rss/finanzas.xml",
        "negocios": "https://www.cronista.com/files/rss/negocios.xml"}},
    "AM": {"nombre": "Ámbito", "web": "https://www.ambito.com", "feeds": {
        "portada": "https://www.ambito.com/rss/pages/home.xml",
        "economia": "https://www.ambito.com/rss/pages/economia.xml",
        "politica": "https://www.ambito.com/rss/pages/politica.xml",
        "finanzas": "https://www.ambito.com/rss/pages/finanzas.xml",
        "deportes": "https://www.ambito.com/rss/pages/deportes.xml",
        "negocios": "https://www.ambito.com/rss/pages/negocios.xml"}},
    "GC": {"nombre": "Le Grand Continent", "web": "https://legrandcontinent.eu/es", "feeds": {
        "europa": "https://legrandcontinent.eu/es/feed/"}},
}

NS = {
    "media": "http://search.yahoo.com/mrss/",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "dc": "http://purl.org/dc/elements/1.1/",
}
TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")
IMG_RE = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.I)


def clean_text(s, limit=None):
    if not s:
        return ""
    s = re.sub(r"(?is)<script.*?</script>|<style.*?</style>|<iframe.*?</iframe>|<noscript.*?</noscript>", " ", s)
    s = TAG_RE.sub(" ", s)
    s = html.unescape(s)
    s = WS_RE.sub(" ", s).strip()
    s = re.sub(r"The post .* appeared first on .*$", "", s).strip()
    if limit and len(s) > limit:
        s = s[:limit].rsplit(" ", 1)[0] + "…"
    return s


def shrink_image(url):
    """Reduce imágenes de resizers Arc (La Nación, Infobae, Cronista) a ~900px de ancho."""
    if not url:
        return url
    m = re.search(r"width=(\d+)&height=(\d+)", url)
    if m and "resizer" in url:
        w, h = int(m.group(1)), int(m.group(2))
        if w > 900 and h > 0:
            nh = round(900 * h / w)
            url = url.replace(m.group(0), f"width=900&height={nh}")
    return url


def find_image(item):
    enc = item.find("enclosure")
    if enc is not None:
        u = enc.get("url", "")
        if u and (enc.get("type", "").startswith("image") or re.search(r"\.(jpe?g|png|webp|gif)(\?|$)", u, re.I)):
            return shrink_image(u)
    for tag in ("media:content", "media:thumbnail"):
        for el in item.findall(tag, NS):
            u = el.get("url", "")
            t = el.get("type", "")
            if u and (t.startswith("image") or el.get("medium") == "image" or re.search(r"\.(jpe?g|png|webp)(\?|$)", u, re.I)):
                return shrink_image(u)
    for text in (item.findtext("content:encoded", default="", namespaces=NS), item.findtext("description", default="")):
        m = IMG_RE.search(text or "")
        if m:
            return shrink_image(html.unescape(m.group(1)))
    return None


def parse_date(s):
    try:
        d = parsedate_to_datetime(s)
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d
    except Exception:
        return None


def fetch(url):
    req = Request(url, headers={"User-Agent": UA, "Accept": "application/rss+xml, application/xml, text/xml, */*"})
    with urlopen(req, timeout=30) as r:
        return r.read()


def parse_feed(code, seccion, url):
    try:
        raw = fetch(url)
    except Exception as e:
        return code, seccion, [], f"descarga fallida: {e}"
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        try:
            root = ET.fromstring(re.sub(rb"[\x00-\x08\x0b\x0c\x0e-\x1f]", b"", raw))
        except ET.ParseError as e:
            return code, seccion, [], f"XML invalido: {e}"
    items = []
    for it in root.iter("item"):
        title = clean_text(it.findtext("title", default=""))
        link = (it.findtext("link") or it.findtext("guid") or "").strip()
        if not title or not link.startswith("http"):
            continue
        desc = clean_text(it.findtext("description", default=""), 600)
        body = clean_text(it.findtext("content:encoded", default="", namespaces=NS), 2500)
        if body and body[:200] == desc[:200]:
            body = ""
        d = parse_date(it.findtext("pubDate", default="") or it.findtext("dc:date", default="", namespaces=NS))
        cats = [clean_text(c.text) for c in it.findall("category") if c is not None and c.text]
        items.append({
            "fuente": code, "seccion_feed": seccion, "titulo": title, "url": link,
            "descripcion": desc, "cuerpo": body, "imagen": find_image(it),
            "autor": clean_text(it.findtext("dc:creator", default="", namespaces=NS)),
            "categorias": cats[:3],
            "fecha": d.isoformat() if d else None,
        })
    return code, seccion, items, None


def norm_link(u):
    return re.sub(r"[?#].*$", "", u).rstrip("/").lower()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--edicion", default="auto", choices=["auto", "manana", "tarde"])
    ap.add_argument("--horas", type=int, default=0, help="ventana de horas hacia atras (0 = automatico)")
    ap.add_argument("--max", type=int, default=26, help="maximo de items por fuente")
    args = ap.parse_args()

    now = datetime.now(timezone.utc)
    now_ba = now.astimezone(BA)
    edicion = args.edicion
    if edicion == "auto":
        edicion = "manana" if now_ba.hour < 13 else "tarde"
    horas = args.horas or (16 if edicion == "manana" else 12)
    desde = now - timedelta(hours=horas)
    slug = f"{now_ba:%Y-%m-%d}-{edicion}"

    jobs = [(code, sec, url) for code, src in SOURCES.items() for sec, url in src["feeds"].items()]
    errores = []
    por_fuente = {code: [] for code in SOURCES}
    with ThreadPoolExecutor(max_workers=8) as ex:
        for code, sec, items, err in ex.map(lambda j: parse_feed(*j), jobs):
            if err:
                errores.append(f"{SOURCES[code]['nombre']}/{sec}: {err}")
            por_fuente[code].extend(items)

    index = {}
    fuentes_out = {}
    for code, items in por_fuente.items():
        vistos = set()
        sel = []
        for it in items:
            k = norm_link(it["url"])
            if k in vistos:
                continue
            vistos.add(k)
            d = datetime.fromisoformat(it["fecha"]) if it["fecha"] else None
            if d and d < desde:
                continue
            sel.append(it)
        sel.sort(key=lambda x: x["fecha"] or "", reverse=True)
        # Cuota por sección del feed (deportes, mundo, etc.) para que ninguna quede
        # afuera del recorte por fuente; el resto se completa por recencia.
        cuota, elegidos, ids_elegidos = 3, [], set()
        for sec in set(it["seccion_feed"] for it in sel):
            for it in [x for x in sel if x["seccion_feed"] == sec][:cuota]:
                elegidos.append(it)
                ids_elegidos.add(id(it))
        for it in sel:
            if len(elegidos) >= args.max:
                break
            if id(it) not in ids_elegidos:
                elegidos.append(it)
                ids_elegidos.add(id(it))
        sel = sorted(elegidos[: max(args.max, len(elegidos))], key=lambda x: x["fecha"] or "", reverse=True)
        for i, it in enumerate(sel, 1):
            it["id"] = f"{code}-{i:02d}"
            if it["fecha"]:
                it["hora"] = datetime.fromisoformat(it["fecha"]).astimezone(BA).strftime("%H:%M")
            index[it["id"]] = it
        fuentes_out[code] = {"nombre": SOURCES[code]["nombre"], "web": SOURCES[code]["web"], "items": sel}

    out = {
        "slug": slug, "fecha": f"{now_ba:%Y-%m-%d}", "edicion": edicion,
        "generado": now.isoformat(), "generado_ba": now_ba.strftime("%d/%m/%Y %H:%M"),
        "ventana_horas": horas, "errores": errores, "fuentes": fuentes_out,
    }
    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / "latest.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    md = [f"# Material crudo - edicion `{slug}` - generado {out['generado_ba']} (hora Argentina)",
          f"Ventana: ultimas {horas} horas. Total de notas: {len(index)}.", ""]
    if errores:
        md.append("Errores de descarga: " + "; ".join(errores))
        md.append("")
    for code, f in fuentes_out.items():
        md.append(f"## {f['nombre']} ({code}) - {len(f['items'])} notas")
        for it in f["items"]:
            extra = it["cuerpo"][:700] if it["cuerpo"] else ""
            img = "img" if it["imagen"] else "sin img"
            md.append(f"- **{it['id']}** [{it['seccion_feed']} · {it.get('hora','--:--')} · {img}] {it['titulo']}")
            if it["descripcion"]:
                md.append(f"    - {it['descripcion']}")
            if extra:
                md.append(f"    - Cuerpo: {extra}")
        md.append("")
    (RAW / "latest.md").write_text("\n".join(md), encoding="utf-8")

    print(f"OK edicion={edicion} slug={slug} notas={len(index)} archivo=data/raw/latest.md")
    for e in errores:
        print("AVISO", e, file=sys.stderr)


if __name__ == "__main__":
    main()
