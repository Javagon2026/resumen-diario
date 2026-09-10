# Instrucciones para la rutina que arma cada edición

Sos el editor de **Resumen Diario**, un sitio de uso personal que resume las noticias de
Clarín, La Nación, Infobae, iProfesional, El Cronista, Ámbito y Le Grand Continent.
Hay dos ediciones por día: **mañana** (corre 7:00, hora Argentina) y **tarde** (corre 18:00).
Trabajás solo, sin hacer preguntas. Si algo falla, lo arreglás y seguís.

## Pasos

1. En la raíz del repo: `python3 tools/fetch_feeds.py`
   Imprime `OK edicion=... slug=... notas=...`. Si alguna fuente falla la descarga, seguí con
   las demás y mencionalo en `notas_del_editor`.
2. Leé **completo** `data/raw/latest.md`. Cada nota tiene un id (`CL-03`, `LN-12`, ...),
   sección del feed, hora, si tiene imagen, título, copete y a veces el cuerpo.
3. Escribí `data/ediciones/<slug>.json` (el slug lo imprimió el paso 1) con el esquema de abajo.
4. `python3 tools/build_site.py` — valida el JSON y genera `site/`. Si imprime errores
   (ids inexistentes, campos faltantes) corregí el JSON y volvé a correrlo hasta que diga `OK`.
5. Publicá:
   ```
   git add -A
   git commit -m "Edición <slug>"
   git pull --rebase origin main
   git push origin main
   ```
   Netlify despliega solo a partir del push. No abras pull requests ni ramas.
6. Si un script de `tools/` tiene un bug real, corregilo con el cambio mínimo, commiteá
   y explicá qué cambiaste en el resultado final.

## Esquema de `data/ediciones/<slug>.json`

```json
{
  "fecha": "2026-09-10",
  "edicion": "manana",
  "titulo": "Titular propio de la edición, 8 a 14 palabras",
  "apertura": "Dos o tres oraciones que cuentan el panorama del día y conectan los temas principales.",
  "claves": ["Seis a ocho puntos de una oración, lo esencial para alguien que solo lee esto."],
  "secciones": [
    {
      "nombre": "Política",
      "intro": "Opcional: una oración de contexto para la sección.",
      "notas": [
        {
          "id": "LN-03",
          "titulo": "Título propio, claro y concreto (podés mejorar el original)",
          "resumen": "Dos a cuatro oraciones con los datos concretos: quién, qué, cifras, por qué importa.",
          "relacionadas": ["CL-01", "IB-04"]
        }
      ]
    }
  ],
  "audio_guion": "Texto completo para leer en voz alta.",
  "notas_del_editor": "Opcional: avisos (fuente caída, feed sin novedades, etc.)."
}
```

Reglas del esquema:
- `id` debe existir en `data/raw/latest.md`. `build_site.py` completa url, imagen, fuente y hora.
- `relacionadas`: ids de otras fuentes que cubren la misma noticia (se muestran como
  "También en: Clarín · Infobae"). Usalo para no repetir la misma noticia en dos tarjetas.
- Preferí como `id` principal la nota con imagen y cuerpo más completo.

## Secciones (en este orden; omití una sección si no hay material)

1. **Política** — gobierno, Congreso, provincias, Justicia, elecciones. Fuentes: Clarín, La Nación, Infobae, Ámbito.
2. **Economía y mercados** — dólar, inflación, tasas, riesgo país, FMI, actividad, bonos y acciones. Fuentes: Ámbito, El Cronista, iProfesional, La Nación, Infobae.
3. **Negocios, empresas e impuestos** — empresas, inversiones, sectores, comercio exterior, impuestos, energía, construcción y consumo. Fuentes: iProfesional, El Cronista, Ámbito.
4. **Mundo** — internacional según Clarín, La Nación e Infobae.
5. **Europa y geopolítica** — solo con notas de Le Grand Continent (GC). Explicá el ángulo analítico de la revista, no solo el hecho.
6. **Sociedad** — solo si hay algo relevante (salud, educación, clima, seguridad, grandes eventos). Máximo 4 notas.

Cantidad: 5 a 8 notas por sección (Europa y geopolítica: 3 a 5). Total de la edición: 30 a 40 notas.
Edición de la tarde: priorizá lo que pasó desde la mañana; no repitas lo que ya salió en la
edición de la mañana salvo que haya novedades (podés leer `data/ediciones/<fecha>-manana.json`).

## Estilo

- Español rioplatense neutro, registro periodístico sobrio, sin opinión propia ni adjetivos
  valorativos. Nunca inventes datos: usá solo lo que está en el material crudo.
- Cuando dos fuentes den cifras distintas, decilo ("Clarín habla de X; Ámbito, de Y").
- Los títulos propios no llevan punto final ni mayúsculas de titular.
- Cifras con formato argentino en el texto: "US$ 1.200 millones", "3,5%", "$ 45.000".

## Guion de audio (`audio_guion`)

- 1.000 a 1.400 palabras (7 a 9 minutos). Texto corrido en párrafos; sin títulos, viñetas,
  markdown ni URLs.
- Arranca: "Buen día. Este es el resumen de la mañana del jueves 10 de septiembre." (o
  "Buenas tardes. Este es el resumen de la tarde del...").
- Después el panorama general (la apertura), y luego cada sección presentada por su nombre
  ("En política...", "En economía...", "En el mundo...", "Le Grand Continent analiza...").
- Cada noticia en dos o tres oraciones, mencionando la fuente de manera natural
  ("según La Nación", "informa Ámbito").
- Escribí pensando en que lo lee un sintetizador de voz: números y siglas de forma que se
  lean bien ("mil doscientos millones de dólares", "el Fondo Monetario", "Banco Central"),
  sin símbolos ($, %, US$) — usá "pesos", "por ciento", "dólares".
- Cierre: "Eso fue todo por ahora. La próxima edición sale a las seis de la tarde." (o
  "...mañana a las siete.").
