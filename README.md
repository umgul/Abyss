# Abyss

*[English version](README.en.md)*

Abyss es un conjunto de *skills* y ganchos para Claude Code que un asistente usa
sobre su propia memoria, su propio comportamiento y su propio entorno: sentidos
hacia fuera, memoria entre hilos, un vigía contra la confabulación, y un par de
manos para generar y pintar imágenes. Nada de estado guardado a ojo — todo lo
que dice cada pieza sale de medir algo real o de aplicar una regla fija.

## Filosofía, en cinco líneas

1. **Ley o medida, nunca estado**: cada pieza mide algo del transcript o aplica
   una regla fija; nada se decreta a ojo ("hoy estoy cansado").
2. **Cortes por cuantiles, nunca umbrales fijos**: lo que cuenta como
   "destacado" sale de la propia distribución acumulada hasta ese momento, y
   rota con ella.
3. **El nulo como suelo**: antes de decir "esto se parece", hay que saber
   cuánto vale el ruido de fondo, medido contra frases que no tienen nada que
   ver con el proyecto.
4. **Cazar lo que no salió de ninguna parte**: un vigía contrasta cada
   respuesta con la evidencia real de la sesión (lo dicho por el usuario, lo
   devuelto por herramientas) y bloquea una vez lo que no tiene fuente.
5. **Fail-closed, nunca inventar**: sin proyecto no hay datos, sin sesiones
   suficientes no hay percentil, sin red no hay lugar ni meteo — la respuesta
   siempre es "sin dato" o "sin vara todavía", jamás un valor puesto a mano.

Este resumen no es una lista 1:1: `docs/leyes.md` destila SEIS leyes (añade "una
vara sin varianza no mide" y "falsar antes de fiarse"), y el detalle completo de
cada una está ahí: [`docs/leyes.md`](docs/leyes.md).

## Las piezas de esta tanda

Cada pieza tiene su propia `skills/<nombre>/SKILL.md` con el comando exacto,
qué devuelve, qué sale de la máquina y sus límites honestos — esto es solo el
mapa.

**Memoria y continuidad**
- [`continuidad`](skills/continuidad/SKILL.md) — guarda cada sesión, mide su
  reloj de esfuerzo y despierta sesiones pasadas parecidas al mensaje actual.
- [`propiocepcion`](skills/propiocepcion/SKILL.md) — mide una sesión desde su
  transcript (horas, turnos, herramientas, tokens, correcciones) y da su
  percentil contra las demás.
- [`varas`](skills/varas/SKILL.md) — recalcula el peso de uso ◆/◆◆/◆◆◆ de cada
  ficha de `MEMORY.md` por cuantiles de citas y lecturas.
- [`modelo`](skills/modelo/SKILL.md) — detecta si se está respondiendo fuera
  del modelo preferido y marca los turnos a revisar al volver.
- [`parentesis`](skills/parentesis/SKILL.md) — marca un tramo (o una sesión
  entera) para que no entre en memoria futura, y recorta el transcript local
  ya cerrado si el usuario lo pide.

**Honestidad**
- [`vigia`](skills/vigia/SKILL.md) — caza números, rutas y citas de la propia
  respuesta que no salieron de ninguna parte, y bloquea el cierre del turno
  una vez.
- [`huella`](skills/huella/SKILL.md) — registra qué ficheros, procesos y
  puertos toca un hilo fuera de su propia carpeta, para poder decir al cerrar
  qué queda vivo y limpiarlo. **APAGADO por defecto** (ver "Límites honestos").
- [`esceptico`](skills/esceptico/SKILL.md) — la ley "ningún plan sin
  escéptico" como comando: lanza un revisor con model Opus a buscar lo que
  tumba un plan antes de ejecutarlo, con veredicto por gravedad y evidencia.

**Sentidos**
- [`exterocepcion`](skills/exterocepcion/SKILL.md) — lugar (por IP y por lo
  dicho), meteo del lugar, y canal de entrada del último mensaje.
- [`noticias`](skills/noticias/SKILL.md) — portada y titulares por tema al
  arrancar, con una lista de temas automáticos autocurada.
- [`ojo`](skills/ojo/SKILL.md) — un fotograma de la webcam, solo a petición
  explícita.
- [`cuerpo`](skills/cuerpo/SKILL.md) — el cuerpo de la máquina (cpu, ram,
  disco, vram, temperatura de GPU, batería) con su propia normal por
  cuantiles; nunca ordena nada, solo mide.

**Manos**
- [`imagen`](skills/imagen/SKILL.md) — crear una imagen por cascada de
  proveedores, pintar una foto como cuadro de pinceladas 100% local en varios
  estilos (óleo, impresionista, acuarela, pastel, carbón, tinta), animar esas
  pinceladas en vídeo, renderizar una escena o modelo 3D con three.js (vista
  explosionada, `render3d.py`) y encadenarlo con el pintor, buscar una imagen
  libre ya hecha (Openverse/Wikimedia Commons) o un motivo del mundo real
  (museos, Street View, webcams — `mundo.py`), y operar con imágenes reales
  sin ningún modelo (`lienzo.py`: fundir, collage, restaurar, pintar por
  números, borrar un objeto) — con un taller local opcional (`taller.py`)
  para quien quiera esa vía.
- [`lector_pdf`](skills/lector_pdf/SKILL.md) — indexa un PDF por página y
  sección, busca por TF-IDF y lee solo la parte que toca en vez del documento
  entero.
- [`mapa_codigo`](skills/mapa_codigo/SKILL.md) — el índice greppable de un
  repo Python con `ast`: módulos, clases, funciones e imports, cada uno con
  su línea.
- [`infografia`](skills/infografia/SKILL.md) — de un CSV o JSON a un SVG
  limpio (barras, líneas, tabla), biblioteca estándar sin dependencias.

Por debajo de todas ellas, `abyss/rutas.py` es la única pieza que decide dónde
viven el código y dónde viven los datos — ninguna otra pieza calcula esa ruta
por su cuenta (ver "Dónde viven los datos" más abajo).

## Instalación

### Como plugin de Claude Code

```
/plugin marketplace add umgul/abyss
/plugin install abyss@abyss
```

(la ruta del repositorio es la prevista para su publicación; ajústala si
`umgul/abyss` cambia). Esto instala los *skills* de `skills/` y los ganchos de
[`hooks/hooks.json`](hooks/hooks.json): `continuidad.py --arranque`,
`huella.py --arranque` y `cuerpo.py --arranque` en `SessionStart`;
`continuidad.py --despertar` y `cuerpo.py --despertar` en `UserPromptSubmit`;
`--cierre` en `SessionEnd`; `huella.py --herramienta` en `PostToolUse`;
`vigia.py --verificar` y `huella.py --fin` en `Stop`. (`modelo.py` no lleva
gancho propio — Claude Code no tiene un evento «PostModelSwitch»/
«PreModelSwitch»; detecta el downgrade como librería de `continuidad.py
--despertar`, en cada prompt.) Cada comando usa `${CLAUDE_PLUGIN_ROOT}`, la
ruta absoluta que Claude Code sustituye por donde quedó instalado el plugin —
no hace falta tocar nada a mano.

**Cómo encuentran sus datos estos ganchos sin instalador**: cada uno resuelve
la carpeta de datos del proyecto a partir del JSON que Claude Code manda por
stdin (`transcript_path`/`cwd`), vía `abyss/rutas.py` — nunca de una ruta fija
ni de una variable que alguien tuviera que configurar. Por eso los ganchos del
plugin funcionan solos, en cualquier proyecto, nada más instalarlo — **con un
límite**: los nueve ganchos de [`hooks/hooks.json`](hooks/hooks.json) invocan
`python` a secas (no admiten detección de intérprete, a diferencia de
`instalar.py`). Eso exige que `python` esté en el `PATH` y sea Python 3.12+: en
Windows, si no se instaló Python desde python.org, `python` puede ser el alias
de la Microsoft Store (abre la tienda en vez de ejecutar nada); en macOS
moderno no existe `python` (solo `python3`), y en varias distribuciones Linux
tampoco. Si eso pasa, los ganchos del plugin fallan en silencio — usa
`instalar.py` en su lugar, que detecta el intérprete real (`sys.executable`, o
`--python <exe>`).

**Aviso de coste, instalando por el plugin**: a diferencia de `instalar.py`
(donde `huella` viene DESMARCADO por defecto, ver abajo), instalar el plugin
entero trae también los ganchos de `huella` — y su gancho `PostToolUse` corre
tras CADA herramienta. Si eso pesa demasiado, quita esas tres entradas de
`hooks/hooks.json` a mano, o instala con `instalar.py` en su lugar, que sí deja
elegir módulo por módulo.

Lo que el plugin **no** trae, porque necesita datos que solo puede dar una
persona: el módulo **telegram** (pide un token de bot y un chat id) y el
sembrado de plantillas de configuración (`modelo_preferido.json`,
`temas_noticias.json`, `imagen_config.json`). Para eso, o para instalar sin
usar el sistema de plugins, está `instalar.py`.

### Con `instalar.py`

```
python instalar.py --listar                       # qué módulos hay y si están instalados
python instalar.py                                 # ventana Tk: casilla por módulo + Instalar/Desinstalar/Cerrar
python instalar.py --instalar continuidad,vigia    # instala solo esos módulos, sin ventana
python instalar.py --desinstalar vigia             # desinstala un módulo
python instalar.py --sin-ventana                   # fuerza el modo CLI aunque haya Tk disponible
```

El instalador:
- detecta el intérprete de Python (`sys.executable`, o `--python <exe>`) y lo
  usa en los ganchos que escribe, con la ruta absoluta del código tal como
  quedó instalado;
- **lee y fusiona** `~/.claude/settings.json` (o el que le indiques con
  `--settings <ruta>`): guarda antes una copia fechada
  (`settings.json.abyss-AAAAMMDD-HHMMSS.bak`), añade las entradas de Abyss a
  cada evento sin tocar las que ya hubiera de otros programas, y solo toca
  claves de preferencia (como `showThinkingSummaries`) si el módulo
  correspondiente está marcado;
- apunta todo lo que añade o cambia en `memory/abyss_manifiesto.json` del
  proyecto desde el que se instala, con el valor que tenía cada clave antes de
  tocarla — es lo que permite deshacerlo exacto, incluso si `abyss/` se mueve o
  se renombra después;
- no escribe nunca en el repo del usuario ni en la carpeta de memoria salvo lo
  que cada módulo declara guardar (ver la tabla de abajo); en la carpeta del
  código solo se escribe `abyss/config.json` (qué `python` se usó la última
  vez), nunca más.

El módulo **telegram** es distinto: `notify_telegram.ps1.plantilla` viaja con
los marcadores `<TELEGRAM_BOT_TOKEN>` y `<CHAT_ID>`; el instalador pide esos
dos valores (por consola o `--telegram-token`/`--telegram-chat`) y escribe la
copia rellena **fuera del repo**, en `memory/`, nunca en el código instalado.

Tres módulos vienen **apagados por defecto** (hay que marcarlos a propósito):
**permisos** (dar a Abyss permiso `Edit` sobre `settings.json`), **huella**
(su gancho `PostToolUse` corre tras cada herramienta, con el coste que eso
implica — ver su skill) y **taller** (deja lista la configuración de un
servidor local de imagen, pero no instala `diffusers`/`torch` ni lo arranca:
eso pesa GB y minutos, y es una decisión que toma quien lo instala, no el
instalador por su cuenta). El resto de módulos — incluido **preferencias**
(`showThinkingSummaries`) — vienen marcados de partida en la ventana Tk; basta
con desmarcarlos si no se quieren.

El módulo **esceptico** es distinto de los demás: no es un guion Python, es
una *skill* (`skills/esceptico/`) que el instalador COPIA a
`~/.claude/skills/esceptico/` (o a donde apunte `--skills-dir <ruta>`), con
una marca en su frontmatter (`abyss-managed: true`) para que el desinstalador
sepa que es la nuestra — una skill que el usuario ya tuviera puesta a mano con
el mismo nombre, sin esa marca, nunca se toca al desinstalar.

**Desinstalar**: `python instalar.py --desinstalar <módulo>` (o desmarcar la
casilla) hace lo inverso: lee `memory/abyss_manifiesto.json`, quita del
`settings.json` solo las entradas cuyo comando apunte a la carpeta donde está
instalado Abyss (o, para telegram, al `.ps1` que escribimos nosotros), y
restaura cada clave de preferencia al valor que tenía antes. Después pregunta
si además hay que borrar los datos generados en `memory/` — **por defecto NO**:
las sesiones guardadas y los relojes son memoria propia del usuario, no del
programa, y no se pierden solo porque se desinstale la herramienta que los
escribió (`--borrar-datos` fuerza el borrado sin preguntar).

**Límite honesto**: el desinstalador devuelve el mismo *contenido* de
`settings.json`, no el mismo texto — `_escribir_json` siempre reescribe con su
propio `indent=2` y siempre en LF (`newline='\n'`, a propósito: sin eso, en
Windows un `settings.json` de partida en LF volvía en CRLF), así que si el
fichero original tenía otro formato (por ejemplo `indent=4`, un orden de
claves distinto, o **CRLF** — el fin de línea habitual de Windows, del Bloc
de notas o de un editor con `files.eol` a CRLF), el JSON que queda tras
instalar y desinstalar es idéntico en lo que dice pero no byte a byte igual al
de antes: un `settings.json` en CRLF vuelve en LF. El formato original no se
pierde: queda en la copia fechada `settings.json.abyss-AAAAMMDD-HHMMSS.bak`
que se hace antes de tocar nada.

<details>
<summary>Apéndice secundario: cablear los ganchos A MANO (NO recomendado)</summary>

Solo si por lo que sea no se puede usar ni el sistema de plugins ni
`instalar.py`: copiar el bloque de
[`docs/ganchos_settings_ejemplo.json`](docs/ganchos_settings_ejemplo.json)
dentro de `"hooks"` en `~/.claude/settings.json`, sustituyendo
`<RUTA_DEL_PAQUETE>` por la ruta real donde quedó `abyss/` y `<PYTHON>` por el
intérprete que se vaya a usar. Sin `instalar.py` ni el sistema de plugins no
hay manifiesto ni registro de qué se instaló, así que deshacerlo exige
recordar a mano qué se tocó.

</details>

## Dónde viven los datos

El código de Abyss se instala una vez (como plugin, o donde lo pongas con
`instalar.py`). Los datos (sesiones, relojes, bolsas, confabulaciones, lugar,
meteo, imágenes…) viven **por proyecto**, dentro de la memoria automática de
Claude Code para ese proyecto: `~/.claude/projects/<proyecto-saneado>/memory/`.
El único módulo que decide esa ruta es `abyss/rutas.py`; el resto la importa.
Como los ganchos (de plugin o de `settings.json` global) disparan en todos los
proyectos, no solo en el que estaba abierto al instalar, cada uno resuelve su
propio proyecto en cada invocación por el `transcript_path`/`cwd` que le llega
— nunca se mezcla la memoria de un proyecto con la de otro.

| Pieza | Qué hace | Gancho | Datos que guarda (en `memory/`) |
|---|---|---|---|
| `rutas.py` | Resuelve dónde viven el código y los datos para todos los demás guiones. | Ninguno (librería que importan todos) | Solo crea `memory/` si no existe. |
| `continuidad.py` | Guarda cada sesión, mide su reloj, abre la sala de los relojes y lleva el latido de qué hilos siguen vivos. `--comprimir` gzipea sesiones viejas. | `SessionStart` (`--arranque`) · `SessionEnd` (`--cierre`) · `UserPromptSubmit` (`--despertar`) | `sesiones/*.jsonl(.gz)` · `relojes.jsonl` · `bolsas.json` · `.despertados/` · `.vivo/` · `sesiones/.omitir` · `varas.log` (avisos y fallos de `varas.py --index` tras cada cierre) |
| `vigia.py` | Contrasta la última respuesta contra la evidencia real de la sesión y bloquea el cierre del turno una vez si encuentra números, rutas o citas sin fuente. | `Stop` (`--verificar`) | `confabulaciones.jsonl` |
| `propiocepcion.py` | Mide cada sesión desde su transcript y da su percentil contra todas las medidas. | Ninguno propio — librería de `continuidad.py` y `varas.py`; también CLI a mano | `propiocepcion.json` |
| `varas.py` | Recalcula el peso ◆/◆◆/◆◆◆ de cada ficha por cuantiles de citas + lecturas, y reescribe esos glifos en el índice. Si `MEMORY.md` supera 24 KB solo **avisa** por stdout; el recorte real es a mano con `varas.py --index --recortar` (deja antes una copia fechada); nunca borra una línea entera. | Ninguno propio — lo llama `continuidad.py` tras cada cierre; también CLI a mano | Reescribe `MEMORY.md` · `MEMORY.md.abyss-AAAAMMDD-HHMMSS.bak` (una por cada recorte real) |
| `parentesis.py` | Marca un tramo o una sesión entera para que no entre en memoria futura; recorta el transcript local ya cerrado (`--recortar`/`--recortar-tramo`, con copia `.antes`). | Ninguno — uso manual | `parentesis.json` · `sesiones/.omitir` (reutilizado) |
| `exterocepcion.py` | Lugar (por IP y por lo dicho), meteo del lugar, y canal de entrada del último mensaje. | Ninguno propio — librería de `continuidad.py` | `lugar.json` · `meteo.json` |
| `modelo.py` | Detecta si se responde fuera del modelo preferido y marca los turnos a revisar al volver. | Ninguno propio — no existe un evento «PostModelSwitch»/«PreModelSwitch» en Claude Code; librería de `continuidad.py --despertar` | `modelo_preferido.json` · `.modelo_revisado/` |
| `noticias.py` | Portada y titulares por tema al arrancar; temas automáticos autocurados. | Ninguno propio — librería de `continuidad.py --arranque` | `noticias.json` · `temas_auto.json` · `temas_log.jsonl` · `temas_noticias.json` (editable a mano) · `temas_veto.json` |
| `ojo.py` | Un fotograma de la webcam, solo a petición explícita en ese turno. | Ninguno — nunca por gancho | El `.jpg` donde se indique + `ojo.log` |
| `huella.py` | Registra ficheros escritos, procesos y puertos que un hilo abre fuera de su carpeta; `--informe`/`--limpiar` dicen qué sigue vivo y lo cierran si se pide. `--limpiar --si` solo borra ficheros bajo el directorio temporal del sistema o bajo una subcarpeta que ESTE paquete genera en `mem` (`huella/`, `mapas/`, `pdf/`) — nunca `MEMORY.md`, una ficha `*.md`, ni nada suelto en la raíz de `mem`, aunque un `Write` de la sesión haya pasado por ahí. **Módulo apagado por defecto** (coste de `PostToolUse`). | `SessionStart` (`--arranque`) · `PostToolUse` (`--herramienta`) · `Stop` (`--fin`) | `huella/<sesión>.jsonl` (incluye el TEXTO de cada comando de Bash/PowerShell, recortado a 200 caracteres — si sueles pasar claves por línea de comandos, quedarán ahí en local) · `huella/<sesión>.snapshot.json` · `huella/_costes.json` |
| `cuerpo.py` | El cuerpo de la máquina (cpu, ram, disco, vram, temperatura de GPU, batería) con su propia normal por cuantiles; `UserPromptSubmit` calla si todo está dentro de lo suyo. Los seis canales se muestran en `SessionStart`; en `UserPromptSubmit` se vigilan cinco — la batería no, porque su propia oscilación normal (cargando/descargando) la sacaría de su p5 cada vez que se desenchufa el cargador. | `SessionStart` (`--arranque`) · `UserPromptSubmit` (`--despertar`) | `cuerpo.jsonl` |
| `lector_pdf.py` | Indexa un PDF por página y sección (PyMuPDF o pypdf), busca por TF-IDF y lee solo la sección o el rango de páginas que toca. | Ninguno — uso manual | `pdf/<sha1 del fichero>.json` |
| `mapa_codigo.py` | El índice greppable de un repo Python con `ast`: módulos, clases, funciones e imports con su línea; mide la proporción mapa/código. | Ninguno — uso manual | `mapas/<carpeta>.txt` (y `.json` con `--json`) |
| `esceptico` (skill) | La ley "ningún plan sin escéptico": lanza un `Task` con model Opus a tumbar un plan contra el código real; veredicto por gravedad (cae/grieta/fleco) con evidencia. No es Python: se COPIA a `~/.claude/skills/esceptico/` (o `--skills-dir`), con marca en su frontmatter. | Ninguno — se invoca con `/esceptico <plan>` | `<plan>_veredicto_esceptico.md`, junto al propio plan (nunca en `memory/`) |
| `infografia.py` | De un CSV o JSON a un SVG limpio (barras, barras horizontales, líneas, tabla), biblioteca estándar. No resuelve proyecto: no escribe en `memory/`. | Ninguno — uso manual | Nada en `memory/`: solo el `.svg` pedido |
| `imagen.py` | `crear`: cascada de proveedores — tu propio servidor local (única vía que no saca el prompt de la máquina) → proveedores con clave, en el orden de `imagen_config.json` (Pollinations, Cloudflare Workers AI, Together, Hugging Face) → AI Horde anónimo. `pintar`: foto → cuadro de pinceladas, 100% local en varios estilos (delega en `pintor.py`). `video`: anima esas pinceladas a `.mp4` (delega en `video_pintura.py`). `buscar`: encuentra una imagen ya hecha con licencia libre (Openverse/Wikimedia Commons) — no monta ni compone. `render`: escena/modelo 3D → página con three.js, con `--pintar` encadena hacia `pintor.pintar` (delega en `render3d.py`). `mundo`: motivos del mundo real — museos, Street View, webcams (delega en `mundo.py`). `vias`: qué proveedores están configurados y si responden. | Ninguno — solo a petición | `imagenes/*.png` (y, con `buscar`/`mundo --descargar`, su `.txt` de atribución) · `imagen.log` (vía, bytes, ruta, prompt recortado en `crear`; entrada/salida en `render` y `render --pintar`) · `imagen_config.json` (claves de cada proveedor, todas opcionales) |
| `pintor.py` | Motor de pinceladas (Hertzmann simplificado) en varios estilos (óleo, impresionista, acuarela, pastel, carbón, tinta: mismo motor, otro dict de parámetros) que usa `imagen.py pintar`; también CLI suelta. | Ninguno | Nada propio: escribe donde le diga quien lo invoca |
| `video_pintura.py` | Anima los trazos de `pintor.py` a `.mp4` con ritmo variable, respetando el estilo y el papel del cuadro; usado por `imagen.py video`. | Ninguno | Nada propio |
| `render3d.py` | Escenas y modelos 3D (`escena.json`, `.glb`/`.gltf`/`.obj`/`.stl`) en una página autocontenida con three.js embebido (MIT), vista explosionada; `--png` la captura con un navegador sin cabeza. Usado por `imagen.py render`. | Ninguno | Nada en `memory/`: el HTML/PNG se escribe junto a la entrada, o donde se indique |
| `mundo.py` | Motivos DEL MUNDO REAL para pintar: The Met/Art Institute of Chicago/Wikimedia Commons sin clave, Street View/Mapillary/webcams de Windy con clave/token propios. `contexto()` deriva lat/lon de Wikidata+Wikipedia. Usado por `imagen.py mundo`. | Ninguno | `imagenes/*` (con `--descargar`, junto a su `.txt` de atribución); lee `imagen_config.json` (`google_maps_key`, `mapillary_token`, `windy_key`) |
| `lienzo.py` | Operar con imágenes reales sin ningún modelo: fundir, doble exposición, collage, degradado, restaurar, pintar por números, borrar un objeto (`cv2.inpaint`, o `--metodo taller` para objetos grandes). | Ninguno | Nada en `memory/` salvo `borrar --metodo taller`, que solo LEE `imagen_config.json` (`taller_url`) |
| `taller.py` | Servidor local mínimo de texto→imagen (boquilla A1111: `/health`, `/sdapi/v1/txt2img`) para la vía `local` de `crear`. No se arranca solo: lo levanta el usuario a mano. | Ninguno | Nada en `memory/`: el modelo se cachea en la carpeta de Hugging Face, no en el repo |
| `notify_telegram.ps1.plantilla` | Avisa por Telegram cuando Claude Code pide permiso o espera respuesta. Viaja como plantilla; el instalador la rellena y la guarda fuera del repo. | `Notification` (solo si se instala con `instalar.py`) | Nada propio: solo llama a la API de Telegram con el token y chat id configurados |

## Privacidad y qué sale de la máquina

- **`exterocepcion.py`**: la IP viaja a `ipinfo.io`; el nombre de lugar (dicho
  por el usuario, o cacheado por IP) viaja a `open-meteo.com` y, si hace
  falta, `nominatim.openstreetmap.org`.
- **`noticias.py`**: las consultas de portada y de tema (incluidos los nombres
  propios candidatos a tema automático) viajan a `news.google.com` (RSS, sin
  clave).
- **`imagen.py crear`**: con cualquier vía que no sea `local`, el texto del
  prompt viaja a un servidor ajeno (Pollinations, Cloudflare Workers AI,
  Together, Hugging Face, o AI Horde con su clave anónima pública si no hay
  ninguna configurada) — ningún proveedor documenta en una página legible
  cuánto tiempo guarda ese prompt. `pintar` y `video` son locales por
  completo: la foto y sus pinceladas nunca salen de la máquina.
- **`imagen.py buscar`**: el TEXTO de la búsqueda viaja a Openverse y
  Wikimedia Commons (sin clave); con `--descargar`, además se descarga la
  imagen elegida desde el host que indique cada banco. Nunca toca los
  proveedores de `crear`.
- **`imagen.py mundo`**: el TEXTO del motivo viaja a la fuente que se pida —
  The Met, Art Institute of Chicago y Wikimedia Commons sin clave; Street
  View, Mapillary y las webcams de Windy SOLO si hay clave/token propios en
  `imagen_config.json` (`google_maps_key`, `mapillary_token`, `windy_key`) —
  sin ella, esa fuente concreta no toca la red. `contexto()` (para derivar
  lat/lon cuando no se da `--lugar`) consulta Wikidata y Wikipedia, sin clave.
- **`imagen.py render`**: `--html` no toca la red (three.js va embebido);
  `--png` lanza un navegador sin cabeza LOCAL contra el propio HTML por
  `file://` — no sube ni descarga nada. Con `--pintar`, el PNG resultante se
  pinta en local, igual que `pintar`.
- **`ojo.py`**: el fotograma se queda en disco local; nada sale por red desde
  aquí.
- **`lienzo.py`**: nada sale de la máquina salvo `borrar --metodo taller`, que
  manda imagen y máscara a la URL que TÚ configures en `imagen_config.json`
  (`taller_url`) — por defecto vacía, así que sin configurarla ese método
  falla con "sin dato" en vez de mandar nada a ningún sitio.
- **`taller.py`**: el prompt que le mandes no sale de esta máquina (es
  precisamente la vía `local` de `imagen.py crear`); el modelo se descarga de
  Hugging Face la primera vez que se usa.
- **`huella.py`**, **`cuerpo.py`**, **`lector_pdf.py`**, **`mapa_codigo.py`**,
  **`infografia.py`**, **`parentesis.py`**: ninguna llamada de red — todo
  local, dentro de `memory/` o del fichero de salida que se les pida.
- **`esceptico`**: no añade una llamada de red propia; el plan y el código que
  el sub-agente lea viajan al mismo servicio de modelo que el resto de la
  sesión, por el mecanismo normal de `Task`.
- `continuidad.py` no hace red POR SÍ MISMO, pero en `--arranque` y `--despertar`
  invoca a `exterocepcion.py`/`noticias.py` como librerías (con un presupuesto de
  tiempo compartido, ver "Límites honestos"), así que el proceso del gancho SÍ
  contacta con `ipinfo.io`, `open-meteo.com`, `nominatim.openstreetmap.org` y
  `news.google.com`. `vigia.py`, `propiocepcion.py`, `varas.py` y `modelo.py` no
  hacen ninguna llamada de red: solo leen y escriben dentro de `memory/`.
- El módulo **telegram** (solo vía `instalar.py`) llama a la API de Telegram
  con el token y chat id que se configuren, para avisar de permisos/esperas.

## Límites honestos

- Los ganchos corren en cada mensaje (`UserPromptSubmit`) y en cada cierre de
  turno (`Stop`): añaden latencia y gasto de proceso a cada turno, no solo al
  arrancar o cerrar la sesión.
- `sesiones/` guarda el transcript **entero** de cada sesión, en local, sin
  cifrar. Es la fuente de todo lo demás y crece sin límite salvo
  `--comprimir` (que solo gzipea, no borra).
- El vigía bloquea como mucho una vez por turno; si insiste tras el primer
  bloqueo, lo deja pasar y solo lo apunta como "reincidente".
- Con menos de 8 sesiones medidas no hay vara: `propiocepcion.py`, `varas.py`
  y la sala de relojes de `continuidad.py` dicen "sin vara todavía" en vez de
  comparar contra un puñado de puntos que no significan nada.
- "Leída" solo ve lecturas explícitas (`Read`/`cat`): lo que Claude Code
  inyecta como memoria automática no deja huella, así que el uso medido de las
  fichas subestima el real.
- La sala de los relojes compara bolsas de palabras (TF-IDF), no ideas: puede
  despertar una sesión por vocabulario compartido sin que el tema sea
  realmente el mismo, y al revés.
- No hay vuelta automática al modelo preferido: `modelo.py` solo detecta y
  avisa; el regreso lo teclea la persona con `/model`, porque ninguna API
  expone hoy una forma de hacerlo desde un gancho.
- El lugar por IP puede equivocarse de ciudad (VPN, redes móviles) y solo se
  refresca al arrancar una sesión; "lo dicho" depende de que el mensaje use
  una fórmula reconocida, no cualquier forma de decir dónde se está.
- Los titulares y candidatos a tema son texto ajeno: dato para leer, nunca
  instrucción a seguir, pero siguen siendo contenido descargado sin revisar.
- En `imagen.py crear`, solo la vía `local` mantiene el prompt en la máquina;
  AI Horde puede completar la generación y aun así fallar la descarga final en
  redes que bloquean su host de almacenamiento.
- `pintar`/`video` dependen de dependencias opcionales (ver abajo): sin
  ellas, fallan con un mensaje claro (`sin cuadro: ...` / `sin video: ...`),
  nunca con una traza cruda.
- La parte de red de `--arranque` (ipinfo + noticias) y de `--despertar` (lugar
  dicho + meteo) va acotada por un presupuesto de tiempo compartido (por defecto
  4 s y 2,5 s; `ABYSS_PRESUPUESTO_ARRANQUE`/`ABYSS_PRESUPUESTO_DESPERTAR`): con la
  red caída o muy lenta, se corta antes de comerse el timeout del propio gancho —
  el precio es que un "casi lento" también se corta, no solo el que está muerto
  del todo.
- **`huella.py`** APAGADO por defecto: su gancho `PostToolUse` corre tras CADA
  herramienta, y la foto de puertos/procesos cuesta (medido: ~950 ms por
  PowerShell combinado en Windows) hasta que el propio guion, midiendo su
  propio coste, pasa a fotografiar solo tras comandos que parecen persistentes
  (heurística declarada, no una ley).
- **`cuerpo.py`** nunca ordena nada: no cierra procesos, no baja de modelo, no
  sugiere nada — mide, y la decisión de qué hacer con esa medida es de quien
  la lea, nunca del propio guion.
- **`imagen.py buscar`** no monta ni compone: para una escena con varios
  elementos concretos hace falta `crear`, no una búsqueda de una sola imagen.
- **`imagen.py mundo`** tampoco monta ni compone (mismo criterio que
  `buscar`): el motivo se pinta tal cual llega. `streetview`/`mapillary`/
  `webcam` necesitan lat/lon: si no se da `--lugar` y el motivo no es un
  lugar que Wikipedia reconozca con coordenadas, esa fuente se avisa
  "sin lugar: …" y no aporta candidatos — nunca se inventa un punto.
- **`imagen.py render --png`** (y por tanto `--pintar`, que lo fuerza)
  necesita un navegador sin cabeza instalado en la máquina (Edge/Chrome en
  Windows; `google-chrome`/`chromium` en Linux/macOS) — dependencia opcional
  del SISTEMA, no de `requirements.txt`; sin uno, "sin dato: no hay
  navegador sin cabeza" y código 2, aunque la página HTML ya se haya
  escrito. Es un visor y editor de vistas, no un modelador: no repara
  mallas, no simplifica, no exporta, y la vista explosionada exige piezas
  YA separadas en el fichero de entrada (un `.stl` de una sola malla no
  explosiona nada).
- **`lienzo.py borrar`** sin `--metodo taller` deja un borrón visible en
  objetos grandes o fondos con estructura (medido en su prueba, no solo
  declarado) — por eso avisa ("borrón probable…") cuando el área o la
  textura del fondo lo sugieren, en vez de dejarlo aparecer sin más; y
  `--metodo taller` necesita un A1111/Forge real detrás — el `taller.py` de
  este paquete sirve `txt2img`, no el `img2img` con máscara que ese método
  pide.
- **`taller.py`** en CPU tarda MINUTOS por imagen, no segundos; su VRAM no está
  medida en la máquina de desarrollo (sin GPU CUDA ahí) — no se afirma una
  cifra sin haberla medido de verdad.
- **`esceptico`** depende de que el entorno deje fijar `model: opus` para el
  sub-agente; si no puede, la propia skill debe decirlo en la respuesta en vez
  de callarlo (mismo principio que el aviso `[modelo]` del resto del paquete).

## Dependencias

Python 3.12 o superior, biblioteca estándar para casi todo. En
[`requirements.txt`](requirements.txt), todas comentadas por defecto (se
instalan solo si se quita el `#` de su línea):

- **Pillow + numpy** — para `pintor.py` (y el verbo `imagen.py pintar`, que lo
  usa) y para `lienzo.py` (fundir, doble, collage, degradado, restaurar,
  numeros, borrar). Import de nivel de módulo: sin ellas, falla con
  `ModuleNotFoundError` al importar, no con un dict de error silencioso.
- **imageio-ffmpeg** (trae su propio binario de ffmpeg) — para
  `video_pintura.py` (y `imagen.py video`).
- **opencv-python** (`cv2`), opcional — para `ojo.py` (sin ella, "sin cv2: no
  hay ojo") y para `lienzo.py` (reducción de ruido, arañazos, `borrar` y las
  zonas conexas y el filtro de moda de `numeros` — sin ella, cada uno de esos
  pasos usa un equivalente en Python puro: más lento, o directamente se salta
  con aviso, nunca falla en silencio).
- **PyMuPDF (`fitz`) o pypdf**, opcional — para `lector_pdf.py`. `fitz` da
  secciones por tamaño de letra real; sin ninguna de las dos, «sin dato: pip
  install pymupdf».
- **diffusers + torch**, opcional y pesada — solo para `taller.py` (ver
  "Taller local" abajo). Ninguna otra pieza de este paquete las necesita.
- **Navegador sin cabeza (Edge/Chrome en Windows; `google-chrome`/`chromium`
  en Linux/macOS)**, opcional y del SISTEMA, no de `requirements.txt` — solo
  para `render3d.py`/`imagen.py render --png` (y `--pintar`, que lo fuerza).
  Se busca en las rutas habituales; sin él, la página HTML se escribe igual
  y solo falla la captura ("sin dato: no hay navegador sin cabeza", código
  2). `render3d.py` no depende de nada más: three.js va embebido en
  `abyss/vendor/`.

### Taller local (opcional, el coste dicho sin adornos)

`taller.py` es un servidor mínimo que sirve texto→imagen en tu propia
máquina, con la misma forma que espera `imagen.py crear --via local`. Nada de
esto se instala ni se arranca por su cuenta — ni el módulo `taller` de
`instalar.py`, ni ninguna otra pieza de este paquete llama a `pip install` ni
lanza el servidor: hace falta que lo decida quien lo usa, a mano.

- **Dependencias**: `pip install diffusers` y, aparte, `torch` — con CUDA si
  hay una GPU NVIDIA (sigue las instrucciones de
  [pytorch.org/get-started/locally](https://pytorch.org/get-started/locally/)
  para la combinación exacta de tu sistema; instalar el `torch` equivocado es
  la forma más común de que esto no arranque). Sin GPU, la versión CPU
  funciona igual, solo que más despacio (ver abajo).
- **Descarga del modelo**: al PRIMER `POST /sdapi/v1/txt2img` (no al arrancar
  el servidor), `taller.py` descarga el modelo (`Lykon/dreamshaper-8` por
  defecto, unos GB) de Hugging Face a la caché que le digas con
  `--cache-dir` (por defecto, la caché propia de Hugging Face en tu perfil de
  usuario) — nunca dentro de este repositorio.
- **Velocidad**: en `cuda` o `mps`, segundos por imagen; en `cpu`, MINUTOS por
  imagen — el propio servidor lo avisa por stdout al arrancar si detecta que
  va a correr en `cpu`, antes de que llegue la primera petición.
- **VRAM**: no medida en la máquina de desarrollo (sin GPU CUDA disponible
  ahí) — este README no repite ninguna cifra de VRAM que no se haya medido de
  verdad en ese hardware.
- **Límite declarado**: `taller.py` solo sirve `txt2img`; el `img2img` con
  máscara que necesitaría `lienzo.py borrar --metodo taller` para objetos
  grandes no está implementado en este servidor — hace falta un A1111/Forge
  real, o ampliarlo.

---

Abyss no está afiliado a Anthropic; Claude y Claude Code son marcas de
Anthropic.

## Licencia

Apache License 2.0 — ver [`LICENSE`](LICENSE).
