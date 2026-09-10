#!/usr/bin/env python3
"""Convierte data/ediciones/<slug>.json en la página estática dentro de site/.
Uso: python3 tools/build_site.py [data/ediciones/<slug>.json]
Sin argumento: usa la edición cuyo slug coincide con data/raw/latest.json, o la más nueva.

Resuelve los ids (ej. "LN-03") contra data/raw/latest.json para completar url, imagen,
fuente y hora; reescribe el JSON de la edición ya resuelto (así el archivo histórico
no depende del material crudo) y genera:
  site/ediciones/<slug>.html, site/index.html, site/archivo.html
"""
import html, json, re, shutil, sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "ediciones"
RAW = ROOT / "data" / "raw" / "latest.json"
SITE = ROOT / "site"

FUENTES = {
    "CL": ("Clarín", "https://www.clarin.com"),
    "LN": ("La Nación", "https://www.lanacion.com.ar"),
    "IB": ("Infobae", "https://www.infobae.com"),
    "IP": ("iProfesional", "https://www.iprofesional.com"),
    "CR": ("El Cronista", "https://www.cronista.com"),
    "AM": ("Ámbito", "https://www.ambito.com"),
    "GC": ("Le Grand Continent", "https://legrandcontinent.eu/es"),
}
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]
EDICION_NOMBRE = {"manana": "Edición de la mañana", "tarde": "Edición de la tarde"}
EDICION_CORTA = {"manana": "Mañana", "tarde": "Tarde"}


def esc(s):
    return html.escape(str(s or ""), quote=True)


def slugify(s):
    s = s.lower()
    s = re.sub(r"[áàä]", "a", s); s = re.sub(r"[éèë]", "e", s); s = re.sub(r"[íìï]", "i", s)
    s = re.sub(r"[óòö]", "o", s); s = re.sub(r"[úùü]", "u", s); s = s.replace("ñ", "n")
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "seccion"


def fecha_larga(fecha):
    d = datetime.strptime(fecha, "%Y-%m-%d")
    return f"{DIAS[d.weekday()].capitalize()} {d.day} de {MESES[d.month - 1]} de {d.year}"


def fecha_corta(fecha):
    d = datetime.strptime(fecha, "%Y-%m-%d")
    return f"{DIAS[d.weekday()].capitalize()} {d.day} de {MESES[d.month - 1]}"


def minutos_audio(texto):
    palabras = len((texto or "").split())
    return max(1, round(palabras / 150))


# ---------- resolución de ids ----------

def cargar_raw():
    if not RAW.exists():
        return {}
    raw = json.loads(RAW.read_text(encoding="utf-8"))
    idx = {}
    for code, f in raw.get("fuentes", {}).items():
        for it in f.get("items", []):
            idx[it["id"]] = it
    return idx


def resolver_nota(nota, idx, errores, ctx):
    nid = nota.get("id")
    if nid and not nota.get("url"):
        it = idx.get(nid)
        if not it:
            errores.append(f"{ctx}: id {nid} no existe en data/raw/latest.json")
            return nota
        nota["url"] = it["url"]
        nota.setdefault("imagen", it.get("imagen"))
        nota["fuente_codigo"] = it["fuente"]
        nota["fuente"] = FUENTES[it["fuente"]][0]
        nota["hora"] = it.get("hora")
        nota["autor"] = it.get("autor")
        nota.setdefault("titulo_original", it["titulo"])
    elif nota.get("url") and not nota.get("fuente"):
        code = nota.get("fuente_codigo", "")
        nota["fuente"] = FUENTES.get(code, ("Fuente", ""))[0]
    rel_out = []
    for r in nota.get("relacionadas", []) or []:
        if isinstance(r, dict):
            rel_out.append(r)
            continue
        it = idx.get(r)
        if not it:
            errores.append(f"{ctx}: id relacionado {r} no existe")
            continue
        if it["url"] == nota.get("url"):
            continue
        rel_out.append({"id": r, "fuente_codigo": it["fuente"], "fuente": FUENTES[it["fuente"]][0],
                        "titulo": it["titulo"], "url": it["url"]})
    nota["relacionadas"] = rel_out
    return nota


def validar_y_resolver(ed, idx):
    errores = []
    for k in ("fecha", "edicion", "titulo", "apertura", "secciones", "audio_guion"):
        if not ed.get(k):
            errores.append(f"falta el campo '{k}'")
    if ed.get("edicion") not in ("manana", "tarde"):
        errores.append("'edicion' debe ser 'manana' o 'tarde'")
    if not isinstance(ed.get("claves"), list) or len(ed.get("claves", [])) < 3:
        errores.append("'claves' debe ser una lista con al menos 3 puntos")
    if errores:
        return errores
    ed["slug"] = ed.get("slug") or f"{ed['fecha']}-{ed['edicion']}"
    for si, sec in enumerate(ed["secciones"]):
        if not sec.get("nombre"):
            errores.append(f"seccion {si}: falta 'nombre'")
        sec["id"] = slugify(sec.get("nombre", f"seccion-{si}"))
        notas = sec.get("notas") or []
        if not notas:
            errores.append(f"seccion '{sec.get('nombre')}': sin notas")
        for ni, nota in enumerate(notas):
            ctx = f"seccion '{sec.get('nombre')}' nota {ni + 1}"
            if not nota.get("titulo"):
                errores.append(f"{ctx}: falta 'titulo'")
            if not nota.get("resumen"):
                errores.append(f"{ctx}: falta 'resumen'")
            if not (nota.get("id") or nota.get("url")):
                errores.append(f"{ctx}: falta 'id' (o 'url')")
                continue
            resolver_nota(nota, idx, errores, ctx)
    return errores


# ---------- render ----------

def render_nota(n):
    img = ""
    if n.get("imagen"):
        img = (f'<a class="thumb" href="{esc(n["url"])}" target="_blank" rel="noopener">'
               f'<img loading="lazy" src="{esc(n["imagen"])}" alt=""></a>')
    code = n.get("fuente_codigo", "XX")
    rel = ""
    if n.get("relacionadas"):
        links = " · ".join(
            f'<a href="{esc(r["url"])}" target="_blank" rel="noopener" title="{esc(r.get("titulo"))}">{esc(r["fuente"])}</a>'
            for r in n["relacionadas"])
        rel = f'<p class="rel">También en: {links}</p>'
    hora = f'<span class="hora">{esc(n["hora"])}</span>' if n.get("hora") else ""
    return f'''<article class="card{" sin-img" if not img else ""}">
  {img}
  <div class="body">
    <div class="tags"><span class="fuente f-{code}">{esc(n.get("fuente"))}</span>{hora}</div>
    <h3><a href="{esc(n["url"])}" target="_blank" rel="noopener">{esc(n["titulo"])}</a></h3>
    <p class="resumen">{esc(n["resumen"])}</p>
    {rel}
  </div>
</article>'''


def render_cifras(cifras):
    if not cifras:
        return ""
    partes = []
    for c in cifras:
        if not (c.get("nombre") and c.get("valor")):
            continue
        var = ""
        if c.get("variacion"):
            v = str(c["variacion"])
            clase = "neg" if v.strip().startswith("-") else "pos"
            var = '<span class="v ' + clase + '">' + esc(v) + "</span>"
        partes.append('<div class="cifra"><span class="n">' + esc(c["nombre"]) + "</span><strong>"
                      + esc(c["valor"]) + "</strong>" + var + "</div>")
    if not partes:
        return ""
    return '<section class="cifras" aria-label="Cifras del día">' + "".join(partes) + "</section>"


def render_edicion(ed, anterior, siguiente, tiene_guion=True):
    slug = ed["slug"]
    titulo_pag = f'Resumen Diario · {fecha_corta(ed["fecha"])} · {EDICION_CORTA[ed["edicion"]]}'
    chips = "".join(f'<a href="#{esc(s["id"])}">{esc(s["nombre"])}</a>' for s in ed["secciones"])
    chips = f'<a href="#claves">Lo esencial</a>{chips}'

    # imagen de portada: primera nota con imagen
    hero_img = ""
    for s in ed["secciones"]:
        for n in s["notas"]:
            if n.get("imagen"):
                hero_img = f'<a href="{esc(n["url"])}" target="_blank" rel="noopener"><img src="{esc(n["imagen"])}" alt="" fetchpriority="high"></a>'
                break
        if hero_img:
            break

    claves = "".join(f"<li>{esc(c)}</li>" for c in ed.get("claves", []))
    secciones = []
    for s in ed["secciones"]:
        cards = "\n".join(render_nota(n) for n in s["notas"])
        intro = f'<p class="intro">{esc(s["intro"])}</p>' if s.get("intro") else ""
        secciones.append(f'<section class="seccion" id="{esc(s["id"])}"><h2>{esc(s["nombre"])}</h2>{intro}\n{cards}\n</section>')

    nav = []
    if anterior:
        nav.append(f'<a class="ant" href="/ediciones/{esc(anterior["slug"])}.html">← {esc(fecha_corta(anterior["fecha"]))}, {EDICION_CORTA[anterior["edicion"]].lower()}</a>')
    else:
        nav.append("<span></span>")
    if siguiente:
        nav.append(f'<a class="sig" href="/ediciones/{esc(siguiente["slug"])}.html">{esc(fecha_corta(siguiente["fecha"]))}, {EDICION_CORTA[siguiente["edicion"]].lower()} →</a>')
    else:
        nav.append('<a class="sig" href="/">Última edición →</a>')

    cifras_html = render_cifras(ed.get("cifras"))
    guion = ed.get("audio_guion", "")
    guion_html = "".join(f"<p>{esc(p)}</p>" for p in re.split(r"\n\s*\n|\n", guion) if p.strip())
    mins = minutos_audio(guion)
    editor = f'<p class="editor">{esc(ed["notas_del_editor"])}</p>' if ed.get("notas_del_editor") else ""
    fuentes = " · ".join(f'<a href="{u}" target="_blank" rel="noopener">{esc(n)}</a>' for n, u in FUENTES.values())
    generado = ed.get("generado_ba") or datetime.now().strftime("%d/%m/%Y %H:%M")

    return f'''<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>{esc(titulo_pag)}</title>
<meta name="description" content="{esc(ed["apertura"][:160])}">
<link rel="stylesheet" href="/assets/style.css">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Ctext y='.9em' font-size='90'%3E%F0%9F%97%9E%3C/text%3E%3C/svg%3E">
</head>
<body data-slug="{esc(slug)}">
<header class="top">
  <div class="wrap">
    <a class="brand" href="/">Resumen Diario</a>
    <div class="meta">{esc(fecha_larga(ed["fecha"]))} · {EDICION_NOMBRE[ed["edicion"]]}</div>
    <nav class="tools"><a href="/archivo.html">Archivo</a><button id="modo" type="button" aria-pressed="false">Solo títulos</button></nav>
  </div>
</header>

<div class="player-wrap"><div class="wrap player" id="player" data-audio="/audio/{esc(slug)}.mp3" data-min="{mins}">
  <button id="play" type="button" aria-label="Escuchar">▶</button>
  <div class="player-info">
    <strong>Escuchar la edición</strong>
    <span id="player-status">≈ {mins} min</span>
  </div>
  <button id="stop" type="button" hidden aria-label="Detener">■</button>
  <audio id="audio" preload="none"></audio>
</div></div>

<nav class="chips"><div class="wrap">{chips}</div></nav>

<main class="wrap">
  <section class="hero">
    {hero_img}
    <h1>{esc(ed["titulo"])}</h1>
    <p class="apertura">{esc(ed["apertura"])}</p>
  </section>

  {cifras_html}

  <section class="seccion claves" id="claves">
    <h2>Lo esencial</h2>
    <ol>{claves}</ol>
  </section>

{chr(10).join(secciones)}

  <details class="guion" id="guion">
    <summary>Guion del audio</summary>
    {guion_html}
  </details>
  {editor}

  <nav class="paginacion">{"".join(nav)}</nav>
</main>

<footer class="wrap">
  <p>Fuentes: {fuentes}.</p>
  <p>Resumen automático de uso personal, generado {esc(generado)} (hora Argentina). Los títulos enlazan a la nota original.</p>
</footer>
<script id="guion-texto" type="text/plain">{esc(guion)}</script>
<script src="/assets/app.js"></script>
</body>
</html>
'''


def render_archivo(eds):
    por_fecha = {}
    for e in eds:
        por_fecha.setdefault(e["fecha"], []).append(e)
    bloques = []
    for fecha in sorted(por_fecha, reverse=True):
        items = "".join(
            f'<li><a href="/ediciones/{esc(e["slug"])}.html"><span class="ed">{EDICION_CORTA[e["edicion"]]}</span> {esc(e["titulo"])}</a></li>'
            for e in sorted(por_fecha[fecha], key=lambda x: x["edicion"] != "manana"))
        bloques.append(f'<section class="dia"><h2>{esc(fecha_larga(fecha))}</h2><ul>{items}</ul></section>')
    return f'''<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex">
<title>Resumen Diario · Archivo</title>
<link rel="stylesheet" href="/assets/style.css">
</head>
<body class="archivo">
<header class="top"><div class="wrap"><a class="brand" href="/">Resumen Diario</a><div class="meta">Archivo de ediciones</div><nav class="tools"><a href="/">Última edición</a></nav></div></header>
<main class="wrap">
{chr(10).join(bloques) or "<p>Todavía no hay ediciones.</p>"}
</main>
</body>
</html>
'''


def listar_ediciones():
    eds = []
    for p in sorted(DATA.glob("*.json")):
        try:
            e = json.loads(p.read_text(encoding="utf-8"))
            if e.get("fecha") and e.get("edicion") and e.get("titulo"):
                e["slug"] = e.get("slug") or p.stem
                eds.append(e)
        except Exception as ex:
            print(f"AVISO: no pude leer {p.name}: {ex}", file=sys.stderr)
    eds.sort(key=lambda e: (e["fecha"], 0 if e["edicion"] == "manana" else 1))
    return eds


def elegir_edicion(arg):
    if arg:
        return Path(arg)
    if RAW.exists():
        slug = json.loads(RAW.read_text(encoding="utf-8")).get("slug")
        p = DATA / f"{slug}.json"
        if p.exists():
            return p
    cands = sorted(DATA.glob("*.json"))
    if not cands:
        sys.exit("No hay ediciones en data/ediciones/")
    return cands[-1]


def main():
    path = elegir_edicion(sys.argv[1] if len(sys.argv) > 1 else None)
    if not path.exists():
        sys.exit(f"No existe {path}")
    ed = json.loads(path.read_text(encoding="utf-8"))
    idx = cargar_raw()
    errores = validar_y_resolver(ed, idx)
    if errores:
        print("ERRORES en la edición (corregí el JSON y volvé a correr):", file=sys.stderr)
        for e in errores:
            print(" -", e, file=sys.stderr)
        sys.exit(1)
    ed.setdefault("generado_ba", datetime.now().strftime("%d/%m/%Y %H:%M"))
    destino = DATA / f"{ed['slug']}.json"
    destino.write_text(json.dumps(ed, ensure_ascii=False, indent=1), encoding="utf-8")
    if path.resolve() != destino.resolve():
        path.unlink()

    eds = listar_ediciones()
    (SITE / "ediciones").mkdir(parents=True, exist_ok=True)
    for i, e in enumerate(eds):
        # Se rehacen todas para que la navegación anterior/siguiente quede consistente.
        ant = eds[i - 1] if i > 0 else None
        sig = eds[i + 1] if i + 1 < len(eds) else None
        htmlp = render_edicion(e, ant, sig)
        (SITE / "ediciones" / f"{e['slug']}.html").write_text(htmlp, encoding="utf-8")
        if i == len(eds) - 1:
            (SITE / "index.html").write_text(htmlp, encoding="utf-8")
    (SITE / "archivo.html").write_text(render_archivo(eds), encoding="utf-8")
    ultima = eds[-1]
    (SITE / "ultima.json").write_text(json.dumps(
        {"slug": ultima["slug"], "fecha": ultima["fecha"], "edicion": ultima["edicion"], "titulo": ultima["titulo"]},
        ensure_ascii=False), encoding="utf-8")
    print(f"OK sitio generado: {len(eds)} ediciones. Última: {ultima['slug']} -> site/index.html")


if __name__ == "__main__":
    main()
