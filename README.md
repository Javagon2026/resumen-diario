# Resumen Diario

Página de noticias personal, generada dos veces por día (7:00 y 18:00, hora Argentina) a partir
de Clarín, La Nación, Infobae, iProfesional, El Cronista, Ámbito y Le Grand Continent.
Cada edición tiene versión de lectura (secciones, tarjetas con imagen) y versión audio.

## Cómo funciona

```
Rutina en la nube (Claude Code, 10:00 y 21:00 UTC)
  └─ python3 tools/fetch_feeds.py      → data/raw/latest.md (material crudo, ~150 notas)
  └─ el agente lee el material y escribe data/ediciones/<slug>.json (resúmenes + guion)
  └─ python3 tools/build_site.py       → site/index.html, site/ediciones/*.html, site/archivo.html
  └─ git push origin main
Netlify (deploy automático en cada push)
  └─ pip install edge-tts && python3 tools/make_audio.py → site/audio/<slug>.mp3
  └─ publica la carpeta site/
```

- `ROUTINE.md`: instrucciones editoriales y de formato que sigue la rutina.
- `data/ediciones/`: una edición por archivo JSON (histórico completo).
- `site/`: lo que publica Netlify. `site/assets/` tiene el estilo y el reproductor.
- El audio se sintetiza con voces neuronales de Edge (`es-AR-TomasNeural`). Si falla,
  la página lee el guion con la voz del navegador.

## Correr a mano

```bash
python3 tools/fetch_feeds.py            # baja los feeds
# escribir data/ediciones/<slug>.json siguiendo ROUTINE.md
python3 tools/build_site.py             # genera el sitio
pip install edge-tts && python3 tools/make_audio.py   # opcional: audio local
```

## Netlify

Sitio conectado al repo de GitHub, rama `main`. Configuración en `netlify.toml`
(publish `site/`, build command solo para el audio).
