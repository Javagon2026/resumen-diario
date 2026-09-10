#!/usr/bin/env python3
"""Genera el MP3 de las últimas ediciones con voces neuronales de Microsoft Edge (edge-tts).
Corre en el build de Netlify (ver netlify.toml). Nunca falla el build: cualquier problema
se informa y se sale con código 0; la página cae a la voz del navegador si no hay MP3.
Uso: python3 tools/make_audio.py [--ultimas N] [--voz es-AR-TomasNeural]
"""
import argparse, asyncio, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "ediciones"
OUT = ROOT / "site" / "audio"

REEMPLAZOS = [
    (r"\bu\$s\s?", "dólares "), (r"\bUS\$\s?", "dólares "), (r"\bUSD\s?", "dólares "),
    (r"\bU\$S\s?", "dólares "), (r"\$\s?", "pesos "), (r"\bFMI\b", "Fondo Monetario Internacional"),
    (r"\bBCRA\b", "Banco Central"), (r"\bYPF\b", "I P F"), (r"\bAFIP\b", "AFIP"),
    (r"\bARCA\b", "ARCA"), (r"\bCABA\b", "Ciudad de Buenos Aires"), (r"\bEE\.?\s?UU\.?", "Estados Unidos"),
    (r"\bUE\b", "Unión Europea"), (r"\bOTAN\b", "OTAN"), (r"\bp\.p\.\b", "puntos porcentuales"),
    (r"https?://\S+", ""), (r"[*_#>`]", ""),
]


def preparar(texto):
    t = texto
    for pat, rep in REEMPLAZOS:
        t = re.sub(pat, rep, t)
    t = re.sub(r"[ \t]+", " ", t)
    return t.strip()


async def sintetizar(texto, voz, destino):
    import edge_tts
    tmp = destino.with_suffix(".tmp.mp3")
    com = edge_tts.Communicate(texto, voz, rate="+4%")
    await com.save(str(tmp))
    tmp.replace(destino)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ultimas", type=int, default=3)
    ap.add_argument("--voz", default="es-AR-TomasNeural")
    ap.add_argument("--forzar", action="store_true")
    args = ap.parse_args()
    try:
        import edge_tts  # noqa: F401
    except ImportError:
        print("edge-tts no está instalado (pip install edge-tts); se omite el audio.")
        return 0
    OUT.mkdir(parents=True, exist_ok=True)
    eds = sorted(DATA.glob("*.json"))[-args.ultimas:]
    ok = 0
    for p in eds:
        destino = OUT / f"{p.stem}.mp3"
        if destino.exists() and not args.forzar:
            print(f"ya existe {destino.name}")
            ok += 1
            continue
        try:
            ed = json.loads(p.read_text(encoding="utf-8"))
            texto = preparar(ed.get("audio_guion") or "")
            if len(texto) < 200:
                print(f"{p.name}: guion demasiado corto, se omite")
                continue
            voz = ed.get("voz") or args.voz
            asyncio.run(sintetizar(texto, voz, destino))
            print(f"OK {destino.name} ({destino.stat().st_size // 1024} KB)")
            ok += 1
        except Exception as e:  # nunca romper el build
            print(f"ERROR generando audio de {p.name}: {e}", file=sys.stderr)
    print(f"Audios listos: {ok}/{len(eds)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
