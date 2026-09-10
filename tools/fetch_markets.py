#!/usr/bin/env python3
"""Descarga series de mercado e indicadores y las guarda en data/mercados.json.
Oro (COMEX via Yahoo Finance), dólar oficial/blue/MEP/mayorista, riesgo país e inflación
(ArgentinaDatos). Si una fuente falla, conserva la serie anterior del archivo y lo marca.
Uso: python3 tools/fetch_markets.py
"""
import json, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "mercados.json"
UA = "Mozilla/5.0 (compatible; ResumenDiario/1.0)"
DIAS_DIARIAS = 400   # ~13 meses de puntos diarios
MESES_MENSUALES = 26

AD = "https://api.argentinadatos.com/v1"

SERIES = {
    "oro": {"nombre": "Oro", "detalle": "onza troy, futuro COMEX", "unidad": "US$", "decimales": 1,
            "frecuencia": "diaria", "fuente": "COMEX vía Yahoo Finance"},
    "dolar_oficial": {"nombre": "Dólar oficial", "detalle": "venta, Banco Nación", "unidad": "$", "decimales": 0,
                      "frecuencia": "diaria", "fuente": "ArgentinaDatos"},
    "dolar_blue": {"nombre": "Dólar blue", "detalle": "venta", "unidad": "$", "decimales": 0,
                   "frecuencia": "diaria", "fuente": "ArgentinaDatos"},
    "dolar_mep": {"nombre": "Dólar MEP", "detalle": "bolsa, venta", "unidad": "$", "decimales": 1,
                  "frecuencia": "diaria", "fuente": "ArgentinaDatos"},
    "dolar_mayorista": {"nombre": "Dólar mayorista", "detalle": "venta, A3500", "unidad": "$", "decimales": 1,
                        "frecuencia": "diaria", "fuente": "ArgentinaDatos"},
    "riesgo_pais": {"nombre": "Riesgo país", "detalle": "EMBI+ Argentina", "unidad": "pb", "decimales": 0,
                    "frecuencia": "diaria", "fuente": "ArgentinaDatos"},
    "inflacion_mensual": {"nombre": "Inflación mensual", "detalle": "IPC INDEC, variación mensual", "unidad": "%",
                          "decimales": 1, "frecuencia": "mensual", "fuente": "INDEC vía ArgentinaDatos"},
    "inflacion_interanual": {"nombre": "Inflación interanual", "detalle": "IPC INDEC, últimos 12 meses", "unidad": "%",
                             "decimales": 1, "frecuencia": "mensual", "fuente": "INDEC vía ArgentinaDatos"},
}


def get_json(url):
    req = Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urlopen(req, timeout=40) as r:
        return json.loads(r.read().decode("utf-8"))


def oro():
    d = get_json("https://query1.finance.yahoo.com/v8/finance/chart/GC=F?range=2y&interval=1d")
    res = d["chart"]["result"][0]
    ts = res["timestamp"]
    closes = res["indicators"]["quote"][0]["close"]
    pts = []
    for t, c in zip(ts, closes):
        if c is None:
            continue
        pts.append([datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%d"), round(float(c), 2)])
    # el último punto refleja el precio de mercado actual si Yahoo lo informa
    meta = res.get("meta", {})
    if meta.get("regularMarketPrice") and meta.get("regularMarketTime"):
        fecha = datetime.fromtimestamp(meta["regularMarketTime"], tz=timezone.utc).strftime("%Y-%m-%d")
        if pts and pts[-1][0] == fecha:
            pts[-1][1] = round(float(meta["regularMarketPrice"]), 2)
        elif not pts or pts[-1][0] < fecha:
            pts.append([fecha, round(float(meta["regularMarketPrice"]), 2)])
    return pts


def dolar(casa):
    d = get_json(f"{AD}/cotizaciones/dolares/{casa}")
    pts = [[x["fecha"], float(x["venta"])] for x in d if x.get("venta") is not None]
    # dolarapi trae la cotización intradiaria de hoy
    try:
        hoy = get_json("https://dolarapi.com/v1/dolares")
        for x in hoy:
            if x.get("casa") == casa and x.get("venta") is not None:
                fecha = (x.get("fechaActualizacion") or "")[:10]
                if fecha:
                    if pts and pts[-1][0] == fecha:
                        pts[-1][1] = float(x["venta"])
                    elif not pts or pts[-1][0] < fecha:
                        pts.append([fecha, float(x["venta"])])
    except Exception as e:
        print(f"aviso: dolarapi no respondió ({e}); se usa el último cierre", file=sys.stderr)
    return pts


def riesgo_pais():
    d = get_json(f"{AD}/finanzas/indices/riesgo-pais")
    return [[x["fecha"], float(x["valor"])] for x in d if x.get("valor") is not None]


def inflacion(endpoint):
    d = get_json(f"{AD}/finanzas/indices/{endpoint}")
    return [[x["fecha"], float(x["valor"])] for x in d if x.get("valor") is not None]


FETCHERS = {
    "oro": oro,
    "dolar_oficial": lambda: dolar("oficial"),
    "dolar_blue": lambda: dolar("blue"),
    "dolar_mep": lambda: dolar("bolsa"),
    "dolar_mayorista": lambda: dolar("mayorista"),
    "riesgo_pais": riesgo_pais,
    "inflacion_mensual": lambda: inflacion("inflacion"),
    "inflacion_interanual": lambda: inflacion("inflacionInteranual"),
}


def recortar(pts, frecuencia):
    pts = sorted({p[0]: p[1] for p in pts}.items())  # dedupe por fecha, orden cronológico
    pts = [[f, v] for f, v in pts]
    if frecuencia == "mensual":
        return pts[-MESES_MENSUALES:]
    desde = (datetime.now(timezone.utc) - timedelta(days=DIAS_DIARIAS)).strftime("%Y-%m-%d")
    return [p for p in pts if p[0] >= desde]


def main():
    previo = {}
    if OUT.exists():
        try:
            previo = json.loads(OUT.read_text(encoding="utf-8")).get("series", {})
        except Exception:
            previo = {}
    salida = {"actualizado": datetime.now(timezone.utc).isoformat(), "series": {}}
    ok = 0
    for clave, meta in SERIES.items():
        serie = dict(meta)
        try:
            pts = recortar(FETCHERS[clave](), meta["frecuencia"])
            if not pts:
                raise ValueError("serie vacía")
            serie["puntos"] = pts
            serie["error"] = None
            ok += 1
        except Exception as e:
            print(f"ERROR {clave}: {e}", file=sys.stderr)
            serie["puntos"] = (previo.get(clave) or {}).get("puntos", [])
            serie["error"] = str(e)[:200]
        salida["series"][clave] = serie
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(salida, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"OK mercados: {ok}/{len(SERIES)} series actualizadas -> data/mercados.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
