# ABYSS · especificación del paquete publicable
Abyss · 6-sep-2026 · para los agentes que lo construyen y para quien lo lea después.

Abyss es la autoinstrumentación que un hilo de Claude Code se dio a sí mismo con la filosofía
del SGICP: **ley o medida, nunca estado**; cortes sacados de la propia distribución (cuantiles,
normales que rotan), nunca umbrales fijos; un vigía que caza lo que no salió de ninguna parte;
continuidad entre hilos sin cargar el pasado entero en contexto. Ocho piezas más dos nuevas
(imagen y pintor). Todo Python de biblioteca estándar salvo `ojo` (OpenCV opcional) y
`pintor` (Pillow + numpy). Castellano como idioma del código y de los textos.

## 1 · Contrato código / datos (la única obra estructural)
Hoy cada guion hace `mem = dirname(__file__)` y `proj = dirname(mem)`: código y datos viven
juntos en `~/.claude/projects/<proyecto>/memory/`. En el paquete el código vive donde se instale
y los datos siguen en la memoria del proyecto del usuario (la carpeta de memoria automática de
Claude Code). Regla:

- `CODE = dirname(__file__)` es solo código. Nada se escribe ahí salvo `config.json` (instalador).
- `proj` se resuelve, por este orden: (1) `dirname(transcript_path)` del JSON de stdin del gancho;
  (2) `cwd` del mismo JSON, saneado como lo sanea Claude Code (`re.sub(r'[^A-Za-z0-9]', '-', cwd)`)
  bajo `~/.claude/projects/`; (3) argumento `--proyecto <cwd>`; (4) variable `ABYSS_PROYECTO`
  (ruta de `proj`; un nombre sin separadores se toma como carpeta bajo `~/.claude/projects/`).
  Si nada, se aborta con un mensaje claro: sin proyecto no hay datos.
- `mem = proj/memory` (se crea si no existe). `sesiones/`, `relojes.jsonl`, `bolsas.json`,
  `.despertados/`, `.vivo/`, `.omitir`, `confabulaciones.jsonl`, `lugar.json`, `meteo.json`,
  `modelo_*`, `.modelo_revisado/`, `noticias.json`, `temas_*.json`, `temas_log.jsonl`, `ojo.log`,
  `propiocepcion.json`, `imagen.log`, `imagenes/`, `varas.log` (avisos y fallos de `varas.py
  --index` que dispara `continuidad.cerrar()`) viven en `mem`. `MEMORY.md` y las fichas también,
  junto con sus copias fechadas `MEMORY.md.abyss-AAAAMMDD-HHMMSS.bak` (una por cada recorte real
  de `varas.py --index --recortar`, nunca en el pase automático).
- Un solo módulo `rutas.py` con `resolver(argv, stdin_json) -> (proj, mem)`; los demás lo importan.
  `es_mio(transcript_path, cwd)` se queda como está pero contra el `proj` resuelto.
- Los ganchos de `settings.json` apuntan al código instalado con ruta absoluta (el instalador la
  escribe) y usan el `python` que el instalador detecte (`sys.executable`).

## 2 · Correcciones obligatorias (medidas el 6-sep sobre la versión viva)
1. **Vigía**: `--precision` daba «cazas duras 114 · descargadas 0 · precisión aparente 1.00»: sin
   descargos no mide. (a) Documentar `--descargo <id>` en el texto de bloqueo para que el propio
   modelo lo use cuando la caza sea falsa; (b) distinguir en el registro las cazas de comillas «»
   en paráfrasis (tipo `parafrasis`) de las citas inventadas (tipo `cita`) y de números/rutas; (c)
   `--precision` debe decir «sin vara» si descargas = 0.
2. **Arranque en frío**: propiocepción, varas y la sala de relojes comparan contra la
   distribución del usuario. Con menos de 8 sesiones: los percentiles se sustituyen por «sin vara
   todavía (n=…)», la sala no despierta relojes, y varas no pone ◆. Fail-closed, nunca inventar.
3. **Índice**: `varas.py --index` vigila el tamaño: si `MEMORY.md` supera 24 KB, AVISA por
   stdout que hace falta recortar, pero el pase automático (el que dispara
   `continuidad.cerrar()` tras cada cierre de sesión) nunca recorta nada — ese aviso sale por
   el stdout de un gancho y nadie lo lee ahí. El recorte es a mano, con
   `varas.py --index --recortar`: entonces sí corta las líneas de más de 200 caracteres en su
   último separador ` · ` (nunca a medias de un enlace, nunca borrando una línea entera), y
   antes de tocar nada dejar una copia fechada `MEMORY.md.abyss-AAAAMMDD-HHMMSS.bak`.
4. **Sesiones**: `continuidad.py --comprimir [días]` gzipea copias de `sesiones/` más viejas que N
   días (por defecto 30); los lectores (`frases_usuario`, bolsas, propiocepción) leen `.jsonl` y
   `.jsonl.gz` por igual.
5. **Telegram**: el `.ps1` va como plantilla con `<TELEGRAM_BOT_TOKEN>` y `<CHAT_ID>`; el
   instalador los pide y escribe una copia rellena FUERA del repo (en `mem`), nunca en el código.
6. **Portabilidad**: sin rutas de usuario en el código (hoy solo hay una en un comentario);
   `python` resuelto por el instalador; Windows probado, Linux/macOS al menos no debe romper por
   rutas (usar `os.path`, `pathlib`); los mensajes al usuario en castellano.
7. **Exterocepción** declara sus dependencias externas (ipinfo, open-meteo, Nominatim) y que sin
   red dice «sin dato». Ojo declara OpenCV opcional. Imagen declara que el prompt sale fuera.

## 3 · `imagen.py`: dos verbos (y `vias`/`video` aparte)
- `imagen.py crear "texto" [salida] [--ancho N] [--alto N] [--semilla N] [--via
  local|pollinations|cloudflare|together|huggingface|horde]` → cascada de SEIS vías, se queda
  con la primera que devuelva una imagen: (1) `local`, un servidor en la propia máquina
  (A1111/Forge o compatible OpenAI) — la única vía en la que el prompt no sale de casa; (2)-(5)
  `pollinations`/`cloudflare`/`together`/`huggingface`, cada una con su clave en
  `mem/imagen_config.json`, probadas en el orden que traiga `orden` ahí (por defecto el de
  arriba); (6) `horde` (AI Horde), con la clave anónima pública, sin registro. Cualquier
  argumento que no encaje (un positional de más, una bandera desconocida o sin su valor detrás)
  sale con código 1 y un mensaje claro, nunca se traga en silencio ni genera con un tamaño
  distinto del pedido.
- `imagen.py pintar <foto> [salida] [--ancho N] [--alta] [--suave [N]] [--acabado] [--html]` →
  llama a `pintor.py` (pinceladas de grueso a fino, orientadas por el gradiente, colocadas por
  error) y escribe el PNG y, con `--html`, la página que repinta en directo (solo pinceles ≥ 2 px
  por defecto, configurable con `--html-r-min`, para que pese poco).
- Solo `crear` apunta en `mem/imagen.log` (vía, bytes, ruta, prompt recortado); `pintar` no
  escribe ahí. `pintor.py` expone `pintar(ruta, ancho=1400, alta=False)` además de su CLI.

## 4 · Instalador `instalar.py` (raíz del repo)
- Módulos, cada uno con nombre, una línea (del docstring), qué toca (ganchos, ficheros, claves):
  continuidad · vigia · exterocepcion · modelo · noticias · propiocepcion+varas · ojo · imagen ·
  telegram · permisos (`Edit` sobre settings.json, APAGADO por defecto y con aviso) ·
  preferencias (`showThinkingSummaries`).
- `settings.json` del usuario: copia fechada antes de tocar; se LEE y se FUSIONA: en cada evento
  se AÑADE nuestra entrada a la lista sin quitar las existentes; claves de preferencia solo si el
  módulo está marcado. Todo lo añadido se apunta en `mem/abyss_manifiesto.json` con el valor
  previo de cada clave.
- Desinstalador: lee el manifiesto; quita solo entradas cuyo comando apunte a nuestra carpeta;
  restaura claves al valor previo; pregunta si borrar datos generados (por defecto NO: las
  sesiones y relojes son memoria del usuario).
- Interfaz: Tk (viene con Python en Windows), ventana pequeña: lista de módulos con casilla,
  línea de descripción, estado instalado/no, botones Instalar / Desinstalar / Cerrar. La misma
  lógica por CLI: `instalar.py --listar | --instalar mod1,mod2 | --desinstalar mod1 | --sin-ventana`.
- Nada de esto escribe en el repo del usuario ni en la carpeta del código salvo `config.json`.

## 5 · Documentación
`README.md` en castellano (qué es, filosofía en cinco líneas, instalación, módulos, qué datos
guarda y dónde, cómo se desinstala, límites honestos: los ganchos corren en cada mensaje,
`sesiones/` guarda transcripts enteros en local, el vigía bloquea una vez por turno). Un resumen
en inglés al final. `docs/` lleva un `leyes.md` destilado (las SEIS leyes del SGICP propio y
qué mide cada pieza); las fichas de diseño originales NO se publican, por ser notas
personales del autor con su fecha y su voz en primera persona.

## 6 · Pruebas (`pruebas/`)
Sin Claude Code: cada gancho se prueba con un JSON de stdin falso (`session_id`,
`transcript_path` apuntando a un transcript sintético en un directorio temporal, `cwd`) y un
`proj` temporal. Casos mínimos: arranque en frío (0 y 3 sesiones) no inventa percentiles ni
despierta relojes; `--despertar` añade tiempo y mundo; el vigía caza un número inventado y no
caza uno que salió de una herramienta; `--descargo` baja la precisión aparente por debajo de 1;
`varas --index` recorta líneas largas y respeta el tope; `--comprimir` deja `.jsonl.gz` legibles;
el instalador fusiona un `settings.json` con ganchos ajenos sin perderlos y el desinstalador
devuelve el mismo CONTENIDO, no el mismo texto: se reescribe con indent 2 (`_escribir_json`),
así que un formato de partida distinto (otro indent, otro orden de claves) no vuelve byte a
byte — el formato original queda en la copia `.bak`, nunca se pierde; `imagen.py pintar` produce
PNG desde una imagen sintética.
Todo con `unittest` de la biblioteca estándar; `python -m unittest discover pruebas`.

## 7 · Lo que NO va en el repo
Sesiones, relojes, bolsas, fichas personales del autor (prefijos propios de su memoria, tipo
`user_*`), claves, el `settings.json` real, capturas de webcam, imágenes generadas.

## 8 · SEGUNDA TANDA (no en esta construcción): `parentesis.py`, lo que no entra en memoria
Petición del usuario (6-sep 18:26): que cuando el usuario diga «esto no lo metas en tu memoria»,
«esto es un paréntesis», o «elimina todo el rato que hemos hablado de X», el asistente tenga una
herramienta honesta para cumplirlo, y que `recortar_hilo.py` (ya en `abyss/`) forme parte de ella.
- `parentesis.py --abrir [motivo]` / `--cerrar`: marca en `mem/parentesis.json` un tramo por
  sesión (marca de tiempo de inicio y fin). Lo que cae dentro NO viaja: `continuidad.guardar()`
  copia el transcript saltando las líneas del tramo; `frases_usuario`, bolsas, relojes y la sala de
  relojes lo ignoran; el vigía no lo usa como evidencia.
- `parentesis.py --omitir-sesion [id]`: la sesión entera no se copia ni se copia después por
  otros hilos (es el `.omitir` de continuidad, ya existente).
- `parentesis.py --recortar <jsonl> "<último mensaje que se conserva>"` y `--recortar-tramo <jsonl>
  <inicio> <fin>`: cortan el transcript LOCAL de Claude Code (lo que ve la app), con copia `.antes`;
  solo con el hilo cerrado. Es lo que hoy hace `recortar_hilo.py`.
- Lo que no puede prometer, dicho en el docstring y en el README: lo ya enviado a la API ya viajó;
  esto gobierna la memoria local y lo que el propio asistente vuelve a leer, no los servidores.
- Uso por el asistente: cuando el usuario lo pide, el asistente llama `--abrir`; al cambiar de
  tema, `--cerrar`; al cerrar el hilo, si el usuario lo pidió, `--recortar`. Nunca por gancho.
- Pruebas: un transcript sintético con un tramo marcado → la copia en `sesiones/` no lo contiene,
  las bolsas no llevan sus palabras, la sala no lo despierta; `--recortar` deja el `.antes`.
