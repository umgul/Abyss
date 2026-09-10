# -*- coding: utf-8 -*-
"""Instalador / desinstalador de Abyss (ESPECIFICACION.md §4). Vive en la RAÍZ del
repo, junto a `abyss/` (el paquete de código) y `plantillas/` (semillas de datos).

Qué hace y qué no:
  - Escribe ganchos en TU `settings.json` (por defecto `~/.claude/settings.json`,
    cambia con `--settings <ruta>`) apuntando al código instalado aquí, con el
    `python` que detecte o el que le digas (`--python <exe>`). NUNCA quita un gancho
    ajeno: en cada evento se AÑADE una entrada nueva a la lista.
  - Como ese `settings.json` es GLOBAL, los ganchos disparan en TODOS tus proyectos
    de Claude Code, no solo en el que tenías abierto al instalar: no existe "el
    proyecto instalado". Cada gancho resuelve su propio proyecto en cada invocación
    (`rutas.resolver()`, por el `transcript_path`/`cwd` de ESE gancho) y guarda ahí
    su propia memoria — la de un proyecto nunca se mezcla con la de otro.
  - Antes de tocar `settings.json` deja una COPIA FECHADA al lado
    (`settings.json.abyss-AAAAMMDD-HHMMSS.bak`).
  - Apunta todo lo añadido (ganchos por firma, claves con su valor previo, permisos,
    telegram) en `mem/abyss_manifiesto.json`, donde `mem` es la memoria del PROYECTO
    desde el que se instala (§1: se resuelve con `rutas.resolver()`; si no hay
    `--proyecto <cwd>` ni `ABYSS_PROYECTO`, se usa el cwd actual — el instalador se
    teclea a mano, nunca hay stdin de un gancho).
  - Desinstalar quita SOLO las entradas cuyo comando apunta a nuestro código (o, para
    telegram, al `.ps1` que escribimos nosotros) y restaura las claves de preferencia
    y de permisos a su valor previo (o las borra si no existían). Pregunta antes de
    borrar sesiones/relojes/etc. generados — por defecto NO los toca.
  - Nada de esto escribe en el repo del usuario. En la carpeta del CÓDIGO (`abyss/`)
    solo se escribe `abyss/config.json` (§1/§4: la única excepción permitida), con
    el `python` detectado/usado la última vez — nada más. Las plantillas de datos
    (`plantillas/*.json`) se copian a `mem/` solo si el destino no existe todavía.

Módulos (nombre · una línea · qué toca) — ver `MODULOS` más abajo; `--listar` los
imprime todos con su estado real leído de `settings.json`.

Uso por línea de comandos:
    python instalar.py --listar
    python instalar.py --instalar continuidad,vigia,modelo
    python instalar.py --desinstalar telegram [--borrar-datos]
    python instalar.py --sin-ventana                (equivale a --listar)
    python instalar.py                               (sin más: abre la ventana Tk)
  Comunes a instalar/desinstalar: `--settings <ruta>` (pruebas, o un settings.json
  distinto del global), `--python <exe>` (si no, `sys.executable`), `--proyecto <cwd>`
  (qué `mem` usar; si no, el cwd actual). Telegram admite `--telegram-token <t>` y
  `--telegram-chat <id>` para instalarlo sin preguntar por consola. Al desinstalar,
  `--borrar-datos` limpia también `DATOS_GENERADOS` sin preguntar (por defecto NO se
  borra nada); `--sin-preguntar` evita la pregunta y deja el valor por defecto (NO).

Interfaz Tk: una ventana con la lista de módulos (casilla, nombre, estado, línea +
aviso) y botones — Instalar / Desinstalar / Dependencias / Cerrar — que llaman a
las mismas `instalar()`/`desinstalar()`/`instalar_dependencias()` de aquí abajo:
no hay una segunda implementación.

Sin rutas de usuario en el código: todo lo que toca a un usuario concreto (dónde
está `~/.claude`, qué proyecto, qué `python`) se resuelve en tiempo de ejecución.

Quinta tanda (T5.1, dependencias de terceros): `--dependencias` mira, con un
`import` REAL bajo el `python` que se vaya a usar (nunca una lista fija de "lo que
suele hacer falta"), qué le falta a cada módulo con paquetes de pip opcionales
(`DEPENDENCIAS`, más abajo) y lo dice en una tabla (falta/paquete/tamaño aprox.).
`--instalar-dependencias [mod1,mod2]` (o la casilla «Dependencias» de la ventana)
instala lo que de verdad falta con `sys.executable -m pip install <paquete>`, UNA
paquete a la vez, enseñando el comando ANTES de correrlo y el resultado DESPUÉS —
nunca en silencio, nunca desde un gancho, nunca reintenta solo un fallo. Lo que
pip no puede poner (el binario `tesseract` en Linux/macOS; `torch`+`diffusers` para
`taller.py`, detectando GPU NVIDIA con `nvidia-smi`) se dice como comando exacto
del gestor que corresponda, nunca se finge instalado. `--desinstalar-dependencias`
NO existe a propósito: quitar paquetes de Python del entorno de alguien es más
arriesgado que ponerlos.

Quinta tanda (T5.2, bilingüe): todo lo que ve el usuario en la ventana, la CLI y
los avisos pasa por `TEXTOS` (`_texto(idioma, clave, **fmt)`), con `--idioma
es|en` o, por defecto, el idioma del sistema (inglés si no empieza por "es"). Los
guiones (`abyss/*.py`) siguen documentados y con sus propios mensajes SIEMPRE en
castellano — es el idioma del código — salvo lo que este instalador imprime. Las
líneas de `MODULOS` (`linea`) son documentación del código y se muestran igual en
los dos idiomas; el detalle `toca`/`aviso` (con vocabulario castellano de control
como «ganchos») solo se imprime en `--idioma es`, para no dejar vocabulario sin
traducir en la vista inglesa — el README/SKILL en inglés cubre ese detalle.

Sexta tanda (T6, MediaPipe Tasks Vision para el visor cinético): el JS+wasm+
modelo de manos que necesita `abyss/plantillas/kinetica.html` (vía `gestos.py`)
NO se instala con pip — es un paquete de NPM que corre DENTRO DEL NAVEGADOR,
servido por jsdelivr, más el modelo de manos de Google
(`storage.googleapis.com`). Pesa ~27 MB en total (medido 8-sep-2026: seis
ficheros, ver `VENDOR_MP`) y por eso NUNCA va en el repositorio de git — a
diferencia de `three.min.js`, que sí se commitea por pesar unos cientos de KB.
`--manos` los baja a `abyss/vendor/mp/`, SOLO los que falten (si ya están
todos, no toca la red); enseña ANTES de empezar de dónde y cuánto ocupa cada
uno — nunca en silencio, nunca desde un gancho. Sin red: UN aviso limpio
(nunca una traza de Python) y se para ahí mismo, sin repetir el mismo fallo con
lo que quedara por bajar. `--dependencias` también dice si estos ficheros
están o faltan, igual que con los paquetes de pip (pero no son lo mismo: no se
instalan con `--instalar-dependencias`). La licencia (Apache License 2.0, del
propio proyecto MediaPipe) se escribe aparte, en
`abyss/vendor/mp/LICENSE-mediapipe.txt`, al terminar la descarga.
"""
import os
import sys
# La consola de Windows y la salida tienen que hablar el mismo idioma (ver abyss/consola.py:
# sin esto, una `ñ` se pinta como dos símbolos en una consola en la página 850). Aquí se
# carga POR RUTA y no con `import consola` a secas porque este guion vive en la RAÍZ del
# repositorio, no dentro de `abyss/`, así que su carpeta no tiene ese módulo al lado.
try:
    import importlib.util as _u
    _e = _u.spec_from_file_location(
        'abyss_consola', os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                       'abyss', 'consola.py'))
    _c = _u.module_from_spec(_e); _e.loader.exec_module(_c); _c.preparar()
except Exception:
    try:
        sys.stdout.reconfigure(encoding='utf-8')   # sin arreglar la consola, como antes
    except Exception:
        pass
import os
import json
import time
import shutil
import subprocess
import locale
import platform
import warnings
import socket
import urllib.request
import urllib.error

RAIZ = os.path.dirname(os.path.abspath(__file__))     # raíz del repo: aquí vive este fichero

# ── el color de la ventana ──────────────────────────────────────────────────
# Sacados del CSS de la web del proyecto, no elegidos aquí. El instalador es un panel de
# control, así que el fondo honesto es el de las páginas-informe (#0a0a0f sobre #12121a) y
# no el negro puro del vestíbulo; el puente entre los dos lenguajes es el acento #8fbdd1,
# que es justo lo que hace su cinta de navegación.
# Contraste MEDIDO sobre #0a0a0f, porque su propio CSS se impone un suelo de 4,5:1 y lo
# escribe en un comentario: #dfe6e9 da 15,6:1, #8fbdd1 9,8:1 y #00b894 7,8:1 — valen para
# texto. #636e72 (3,77:1) y #6c5ce7 (4,07:1) NO llegan, así que aquí solo se usan para
# líneas y bordes, nunca para algo que haya que leer.
C_FONDO = '#0a0a0f'
C_PANEL = '#12121a'
C_BORDE = '#2d3436'
C_TINTA = '#dfe6e9'
C_TINTA_VIVA = '#f2f4f6'
C_ACENTO = '#8fbdd1'
C_OK = '#00b894'
C_MARCA = '#6c5ce7'      # solo líneas: no llega al suelo de contraste para texto
C_APAGADO = '#636e72'    # ídem
PKG = os.path.join(RAIZ, 'abyss')                     # el paquete instalado (== rutas.CODE)
PLANTILLAS = os.path.join(RAIZ, 'plantillas')

sys.path.insert(0, PKG)
import rutas  # noqa: E402

SETTINGS_POR_DEFECTO = os.path.join(os.path.expanduser('~'), '.claude', 'settings.json')
MANIFIESTO_NOMBRE = 'abyss_manifiesto.json'

# Segunda tanda (T2.6): el módulo `esceptico` no es un guion Python — es una skill
# de Claude Code (`skills/esceptico/SKILL.md` en este repo) que se COPIA a la
# carpeta de skills del usuario, igual que `~/.claude/settings.json` es la carpeta
# de ganchos por defecto. `--skills-dir <ruta>` la cambia (pruebas, o una instalación
# a nivel de proyecto en vez de usuario). `MARCA_SKILL_LINEA` es la línea exacta que
# este instalador escribe en el frontmatter de la skill copiada: el desinstalador
# SOLO borra una carpeta de skill si la encuentra ahí — una skill de otro origen con
# el mismo nombre nunca se toca (mismo principio que "permisos": comparar la firma
# EXACTA, no "se parece a la nuestra").
RAIZ_SKILLS = os.path.join(RAIZ, 'skills')
SKILLS_DIR_POR_DEFECTO = os.path.join(os.path.expanduser('~'), '.claude', 'skills')
MARCA_SKILL_LINEA = 'abyss-managed: true'

# Datos que sí genera abyss en mem/ y que `--borrar-datos` puede limpiar en el
# desinstalador. Deliberadamente NO incluye MEMORY.md, las fichas *.md, ni ficheros
# de configuración que el usuario tecleó a mano (modelo_preferido.json,
# imagen_config.json con su huggingface_key, temas_noticias.json): eso es lo que él
# puso o su memoria de verdad, nunca "datos generados" que se puedan tirar sin más.
DATOS_GENERADOS = (
    'sesiones', 'relojes.jsonl', 'bolsas.json', '.despertados', '.vivo',
    os.path.join('sesiones', '.omitir'),  # cuelga de sesiones/, no de mem/ directamente
    'confabulaciones.jsonl', 'lugar.json', 'meteo.json', '.modelo_revisado',
    'modelo_log.jsonl', 'noticias.json', 'temas_auto.json', 'temas_veto.json',
    'temas_log.jsonl', 'ojo.log', 'propiocepcion.json', 'imagen.log', 'imagenes',
    # Segunda tanda: telemetría/caché regenerable de las piezas nuevas. NO incluye
    # `parentesis.json` (tramos que el usuario pidió a propósito, no telemetría
    # automática) ni `imagen_config.json` (claves puestas a mano) — mismo criterio
    # de arriba: solo lo que el propio programa genera por su cuenta.
    'huella', 'cuerpo.jsonl', 'pdf', 'mapas',
)


def _script(nombre):
    """Ruta absoluta a `nombre` dentro del paquete instalado (`PKG`)."""
    return os.path.join(PKG, nombre)


# ---------------------------------------------------------------------------------
# Registro de módulos: nombre · una línea (del docstring de cada guion) · qué toca.
# `hooks` es una lista de (evento, args, timeout); `args[0]` es la bandera que
# identifica la firma del gancho (para no duplicarlo ni perderlo al desinstalar).
# `claves` son claves de nivel superior en settings.json que se fijan SOLO si el
# módulo está marcado. `especial` señala un módulo con lógica propia (telegram,
# permisos) que no encaja en el patrón gancho+clave genérico.
#
# Sin `statusMessage`: no aparece en el esquema de gancho documentado (skill oficial
# `hook-development`: {type, command, timeout} para un gancho de tipo `command`) ni
# en ningún `settings.json` real encontrado en esta máquina — se quitó el 6-sep tras
# no poder verificarla contra ninguna fuente (ver ESPECIFICACION.md §4).
# ---------------------------------------------------------------------------------
MODULOS = [
    dict(id='continuidad', script='continuidad.py', defecto=True,
         linea='Cose la memoria entre hilos: arranque, sala de los relojes y cierre de cada sesión.',
         linea_en="Stitches memory across threads: startup, the clocks room, and each session's close.",
         toca='ganchos SessionStart/SessionEnd/UserPromptSubmit → continuidad.py --arranque/--cierre/--despertar',
         hooks=[
             ('SessionStart', ['--arranque'], 60),
             ('SessionEnd', ['--cierre'], 60),
             ('UserPromptSubmit', ['--despertar'], 30),
         ],
         toca_en="SessionStart/SessionEnd/UserPromptSubmit hooks → continuidad.py "
                 "--arranque/--cierre/--despertar"),
    dict(id='vigia', script='vigia.py', defecto=True,
         linea='Penaliza la confabulación: caza números, rutas y citas que no salieron de ninguna parte.',
         linea_en='Penalizes confabulation: catches numbers, paths and quotes that came from nowhere.',
         toca='gancho Stop → vigia.py --verificar; ficheros mem/confabulaciones.jsonl',
         hooks=[('Stop', ['--verificar'], 30)],
         toca_en="Stop hook → vigia.py --verificar; files: mem/confabulaciones.jsonl"),
    dict(id='exterocepcion', script='exterocepcion.py', defecto=True,
         linea='Lugar, meteo y canal en cada prompt (ipinfo.io, open-meteo.com, nominatim); sin red, «sin dato».',
         linea_en='Place, weather and channel on every prompt (ipinfo.io, open-meteo.com, nominatim); '
                  'without network, "no data".',
         toca='sin gancho propio (lo usa continuidad --despertar); ficheros mem/lugar.json, mem/meteo.json',
         hooks=[],
         toca_en="no hook of its own (continuidad --despertar uses it); files: mem/lugar.json, "
                 "mem/meteo.json"),
    dict(id='modelo', script='modelo.py', defecto=True,
         linea='Avisa si Fable bajó a Opus y qué revisar cuando se vuelve.',
         linea_en='Warns if Fable dropped to Opus, and what to check when it comes back.',
         # Sin gancho propio: no existe un evento «PostModelSwitch»/«PreModelSwitch» en
         # Claude Code (comprobado 6-sep contra la documentación de ganchos: los eventos
         # reales son PreToolUse, PostToolUse, Stop, SubagentStop, SessionStart,
         # SessionEnd, UserPromptSubmit, PreCompact, Notification). Antes se declaraba
         # aquí y en hooks/hooks.json un gancho que nunca se disparaba. `modelo.py` es
         # ahora solo una librería que usa `continuidad.py --despertar` en cada prompt.
         toca='sin gancho propio (lo usa continuidad --despertar); ficheros mem/modelo_preferido.json',
         hooks=[],
         plantilla='modelo_preferido.json',
         toca_en="no hook of its own (continuidad --despertar uses it); files: mem/modelo_preferido.json"),
    dict(id='noticias', script='noticias.py', defecto=True,
         linea='El día y lo reciente nuestro visto desde fuera (Google News RSS), al arrancar.',
         linea_en='The day and our recent activity seen from outside (Google News RSS), on startup.',
         toca='sin gancho propio (lo usa continuidad --arranque); ficheros mem/noticias.json, mem/temas_*.json',
         hooks=[], plantilla='temas_noticias.json',
         toca_en="no hook of its own (continuidad --arranque uses it); files: mem/noticias.json, "
                 "mem/temas_*.json"),
    dict(id='propiocepcion', script='propiocepcion.py', defecto=True,
         linea='Mide cada sesión contra mi propia distribución; varas.py pone los ◆ del índice (MEMORY.md).',
         linea_en='Measures each session against its own distribution; varas.py sets the ◆ marks in the '
                  'index (MEMORY.md).',
         toca='sin gancho propio (varas.py --index lo invoca continuidad --cierre); ficheros mem/propiocepcion.json',
         hooks=[],
         toca_en="no hook of its own (continuidad --cierre invokes varas.py --index); files: "
                 "mem/propiocepcion.json"),
    dict(id='ojo', script='ojo.py', defecto=True,
         linea='El ojo, con verbos: mirar (webcam), texto/fotocopia/tarjeta/manual (OCR, delega en '
               'lectura_visual.py), despiece/prompt3d (2,5D, delega en volumen.py), gestos (control por '
               'mano, delega en gestos.py) — todo a petición, ninguno por gancho.',
         linea_en='The eye, with verbs: mirar (webcam), texto/fotocopia/tarjeta/manual (OCR, delegates '
                  'to lectura_visual.py), despiece/prompt3d (2.5D, delegates to volumen.py), gestos '
                  '(hand control, delegates to gestos.py) — all on request, none by hook.',
         toca='sin gancho — nunca se dispara solo; uso manual; ficheros mem/ojo.log (verbos mirar/texto/'
              'fotocopia/tarjeta/manual); despiece/prompt3d/gestos no tocan mem',
         hooks=[], aviso='OpenCV (cv2) para mirar/fotocopia/despiece/prompt3d (numpy también para '
                          'despiece/prompt3d), tesseract opcional para el OCR de texto/fotocopia/tarjeta/'
                          'manual, mediapipe para gestos — cada verbo dice exactamente qué instalar si '
                          'falta y sale con código 2; nunca se instala nada desde aquí.',
         toca_en="no hook — it never fires by itself; manual use; files mem/ojo.log (verbs "
                 "mirar/texto/fotocopia/tarjeta/manual); despiece/prompt3d/gestos don't touch mem",
         aviso_en="OpenCV (cv2) for mirar/fotocopia/despiece/prompt3d (numpy too, for despiece/prompt3d), "
                  "tesseract optional for OCR on texto/fotocopia/tarjeta/manual, mediapipe for gestos — "
                  "each verb says exactly what to install if it's missing and exits with code 2; nothing "
                  "is ever installed from here."),
    dict(id='imagen', script='imagen.py', defecto=True,
         linea='Crear una imagen por cascada de proveedores, pintarla localmente por pinceladas (varios '
               'estilos), animarla en vídeo, renderizar una escena 3D, o buscar una imagen ya hecha o un '
               'motivo del mundo real — solo a petición.',
         linea_en='Create an image through a cascade of providers, paint it locally with brushstrokes '
                  '(several styles), animate it into a video, render a 3D scene, or search for an '
                  'already-made image or a real-world subject — only on request.',
         toca='sin gancho — uso manual; "crear" prueba local (tu propio servidor) → proveedores con '
              'clave (pollinations/cloudflare/together/huggingface, en el orden de imagen_config.json) → '
              'horde anónimo; "buscar" consulta Openverse/Wikimedia Commons; "render" delega en render3d.py '
              '(three.js embebido, navegador sin cabeza para --png) y encadena con pintor.pintar con '
              '--pintar; "mundo" delega en mundo.py (Met/AIC/Commons sin clave; Street View/Mapillary/Windy '
              'con clave); ficheros mem/imagen.log (crear, y las dos salidas de render/render --pintar), '
              'mem/imagenes/ (con --descargar, junto a un .txt de atribución), mem/imagen_config.json '
              '(las claves van SIEMPRE ahí, nunca en el repo)',
         hooks=[], plantilla='imagen_config.json',
         aviso='solo la vía "local" no saca el texto de tu máquina; el resto lo manda a un servicio ajeno. '
               '"pintar"/"video" son locales por completo. "buscar" manda el TEXTO de la búsqueda a Openverse/'
               'Wikimedia Commons (nunca a los proveedores de "crear"); solo busca y trae con atribución, no '
               'monta ni compone nada. "mundo" manda el TEXTO del motivo a la fuente que se pida (Met/AIC/'
               'Commons sin clave; streetview/mapillary/webcam solo si hay clave/token en imagen_config.json '
               '— sin ella, esa fuente ni toca la red). "render"/"render --pintar" son locales salvo por '
               '--png, que lanza un navegador sin cabeza LOCAL (nunca sube nada a un servicio: lee el HTML '
               'por file://). `lienzo.py` (fundir/collage/restaurar/pintar por números/borrar) vive '
               'en el mismo paquete, sin módulo de instalación propio (sin gancho, no toca settings.json). '
               'Opcionales: Pillow+numpy (pintar, lienzo), imageio-ffmpeg (video), OpenCV (lienzo.py: ruido/'
               'arañazos/relleno/zonas conexas — sin ella, más lento o con menos pasos, nunca falla del todo).',
         toca_en="no hook — manual use; \"crear\" tries local first (your own server) → providers with a "
                 "key (pollinations/cloudflare/together/huggingface, in the order set by "
                 "imagen_config.json) → anonymous horde; \"buscar\" queries Openverse/Wikimedia Commons; "
                 "\"render\" delegates to render3d.py (three.js embedded, headless browser for --png) and "
                 "chains into pintor.pintar via --pintar; \"mundo\" delegates to mundo.py (Met/AIC/Commons "
                 "need no key; Street View/Mapillary/Windy need a key); files mem/imagen.log (crear, and "
                 "both outputs of render/render --pintar), mem/imagenes/ (with --descargar, plus a .txt "
                 "attribution file), mem/imagen_config.json (keys ALWAYS go there, never in the repo)",
         aviso_en="only the \"local\" path never sends your text off your machine; everything else sends it "
                  "to an outside service. \"pintar\"/\"video\" are fully local. \"buscar\" sends the search "
                  "TEXT to Openverse/Wikimedia Commons (never to the \"crear\" providers); it only searches "
                  "and fetches with attribution, it doesn't assemble or compose anything. \"mundo\" sends "
                  "the subject TEXT to whichever source is requested (Met/AIC/Commons need no key; "
                  "streetview/mapillary/webcam only if there's a key/token in imagen_config.json — "
                  "without one, that source doesn't even touch the network). \"render\"/\"render --pintar\" "
                  "are local except for --png, which launches a LOCAL headless browser (it never uploads "
                  "anything to a service: it reads the HTML via file://). `lienzo.py` "
                  "(fundir/collage/restaurar/numeros/borrar — blend, collage, restore, paint-by-numbers, "
                  "erase) lives in the same package, with "
                  "no install module of its own (no hook, doesn't touch settings.json). Optional: "
                  "Pillow+numpy (pintar, lienzo), imageio-ffmpeg (video), OpenCV (lienzo.py: "
                  "noise/scratches/fill/connected regions — without it, slower or with fewer steps, but "
                  "never fails completely)."),
    dict(id='render3d', script='render3d.py', defecto=True,
         linea='Escenas y modelos 3D (glb/gltf/obj/stl/escena.json) en una página autocontenida con '
               'three.js, vista explosionada; --png la captura con un navegador sin cabeza.',
         linea_en='3D scenes and models (glb/gltf/obj/stl/escena.json) in a self-contained page with '
                  'three.js, exploded view; --png captures it with a headless browser.',
         toca='sin gancho — uso manual (`imagen.py render` delega aquí); ficheros: el HTML/PNG que se '
              'pida, junto a la entrada salvo que se indique otra ruta (nada en mem/)',
         hooks=[],
         aviso='three.js va EMBEBIDO en abyss/vendor/three.min.js (versión fijada, licencia MIT en '
               'abyss/vendor/LICENSE-three.txt) — la página no toca la red para verse. --png necesita un '
               'navegador sin cabeza en la máquina (msedge.exe/chrome.exe en Windows, google-chrome/'
               'chromium en Linux/macOS) — dependencia OPCIONAL del sistema, no de pip; sin uno, «sin dato: '
               'no hay navegador sin cabeza» y código 2 (la página HTML se escribe de todas formas). Es un '
               'visor y editor de vistas, no un modelador: no repara mallas, no simplifica, no exporta.',
         toca_en="no hook — manual use (`imagen.py render` delegates here); files: whatever HTML/PNG is "
                 "requested, next to the input unless another path is given (nothing in mem/)",
         aviso_en="three.js ships EMBEDDED in abyss/vendor/three.min.js (pinned version, MIT license in "
                  "abyss/vendor/LICENSE-three.txt) — the page never touches the network to display. --png "
                  "needs a headless browser on the machine (msedge.exe/chrome.exe on Windows, "
                  "google-chrome/chromium on Linux/macOS) — an OPTIONAL system dependency, not a pip one; "
                  "without one, \"no data: no headless browser\" and code 2 (the HTML page gets written "
                  "either way). It's a viewer and view editor, not a modeler: it doesn't repair meshes, "
                  "doesn't simplify, doesn't export."),
    dict(id='gestos', script='gestos.py', defecto=True,
         linea='La mano manda en el holograma: MediaPipe + vocabulario PROPIO del paquete (número de '
               'dedos aísla capas del despiece, pellizco desliza la explosión, pose de la palma orbita la '
               'cámara, mano abierta y quieta captura PNG, dos manos escalan).',
         linea_en="The hand drives the hologram: MediaPipe + the package's OWN vocabulary (finger count "
                  'isolates exploded-view layers, pinch slides the explosion, palm pose orbits the '
                  'camera, an open still hand captures a PNG, two hands scale).',
         toca='sin gancho — uso manual (`ojo.py gestos` delega aquí); sirve HTTP SOLO en 127.0.0.1; no '
              'toca mem ni resuelve un proyecto de Claude Code',
         hooks=[],
         aviso='necesita mediapipe (y opencv-python para leer la cámara); sin ellos, dice exactamente qué '
               'instalar y sale con código 2 — nunca instala nada. Se queda corriendo (servidor + bucle de '
               'cámara) hasta que se interrumpe: no es un comando que termina solo.',
         toca_en="no hook — manual use (`ojo.py gestos` delegates here); serves HTTP ONLY on 127.0.0.1; "
                 "doesn't touch mem, and doesn't resolve a Claude Code project",
         aviso_en="needs mediapipe (and opencv-python to read the camera); without them, it says exactly "
                  "what to install and exits with code 2 — it never installs anything itself. It keeps "
                  "running (server + camera loop) until interrupted: it's not a command that finishes on "
                  "its own."),
    dict(id='parentesis', script='parentesis.py', defecto=True,
         linea='Marca un tramo o una sesión entera para que no entre en la memoria futura; puede recortar el '
               'transcript local ya cerrado.',
         linea_en='Marks a stretch or a whole session so it does not enter future memory; can trim the '
                  'local transcript once it is already closed.',
         toca='sin gancho — uso manual (--abrir/--cerrar/--omitir-sesion/--recortar/--recortar-tramo); '
              'ficheros mem/parentesis.json, mem/sesiones/.omitir',
         hooks=[],
         aviso='no puede deshacer lo que ya viajó a la API dentro de un turno: gobierna la memoria LOCAL de '
               'este paquete (lo que el propio asistente vuelve a leer), no los servidores de Anthropic.',
         toca_en="no hook — manual use (--abrir/--cerrar/--omitir-sesion/--recortar/--recortar-tramo); "
                 "files mem/parentesis.json, mem/sesiones/.omitir",
         aviso_en="it can't undo what already went to the API within a turn: it governs this package's "
                  "LOCAL memory (what the assistant itself reads back), not Anthropic's servers."),
    dict(id='huella', script='huella.py', defecto=False,
         linea='Registra lo que un hilo toca fuera de su propia carpeta (ficheros escritos, procesos, puertos) '
               'y ayuda a limpiarlo al cerrar.',
         linea_en='Records what a thread touches outside its own folder (files written, processes, '
                  'ports) and helps clean it up on close.',
         toca='ganchos SessionStart/PostToolUse/Stop → huella.py --arranque/--herramienta/--fin; '
              'ficheros mem/huella/<sesion>.jsonl',
         hooks=[
             ('SessionStart', ['--arranque'], 10),
             ('PostToolUse', ['--herramienta'], 10),
             ('Stop', ['--fin'], 5),
         ],
         aviso='APAGADO por defecto: PostToolUse corre tras CADA herramienta, y la foto de puertos/procesos '
               'tiene coste (remedido el 8-sep-2026 en la máquina de desarrollo: 793 ms de mediana en 5 '
               'llamadas del gancho ENTERO —proceso de Python incluido— tras un comando que parece '
               'persistente, y 96 ms cuando no lo parece y no hay nada que fotografiar) '
               'hasta que el propio guion detecta que ese coste supera 1,5 s de mediana y pasa a fotografiar '
               'solo tras comandos que parecen persistentes (heurística declarada, ver docstring de huella.py).',
         toca_en="hooks SessionStart/PostToolUse/Stop → huella.py --arranque/--herramienta/--fin; files "
                 "mem/huella/<session>.jsonl",
         aviso_en="OFF by default: PostToolUse runs after EVERY tool call, and snapshotting "
                  "ports/processes has a cost (re-measured on 2026-09-08 on the dev machine: 793 ms median over "
                  "5 calls of the WHOLE hook —Python process included— after a command that looks "
                  "persistent, and 96 ms when it doesn't and there is nothing to snapshot) until the "
                  "script itself detects that cost exceeds a 1.5 s "
                  "median and switches to snapshotting only after commands that look persistent (a "
                  "declared heuristic — see huella.py's docstring)."),
    dict(id='cuerpo', script='cuerpo.py', defecto=True,
         linea='El cuerpo de la máquina (cpu, ram, disco, vram, temperatura de GPU, batería) con su propia '
               'normal por cuantiles.',
         linea_en="The machine's body (cpu, ram, disk, vram, GPU temperature, battery) with its own "
                  'quantile-based normal.',
         toca='ganchos SessionStart/UserPromptSubmit → cuerpo.py --arranque/--despertar; ficheros mem/cuerpo.jsonl',
         hooks=[
             ('SessionStart', ['--arranque'], 15),
             ('UserPromptSubmit', ['--despertar'], 15),
         ],
         toca_en="hooks SessionStart/UserPromptSubmit → cuerpo.py --arranque/--despertar; files "
                 "mem/cuerpo.jsonl"),
    dict(id='lector_pdf', script='lector_pdf.py', defecto=True,
         linea='Indexa un PDF por página y sección, busca por TF-IDF y mide cuánto ahorra leer solo lo que toca.',
         linea_en='Indexes a PDF by page and section, searches by TF-IDF, and measures how much is '
                  'saved by reading only what matters.',
         toca='sin gancho — uso manual (--indexar/--secciones/--buscar/--leer/--ahorro <pdf>); '
              'ficheros mem/pdf/<sha1 del fichero>.json',
         hooks=[], aviso='necesita PyMuPDF (fitz) o pypdf; sin ninguna de las dos, «sin dato: pip install pymupdf».',
         toca_en="no hook — manual use (--indexar/--secciones/--buscar/--leer/--ahorro <pdf>); files "
                 "mem/pdf/<file's sha1>.json",
         aviso_en="needs PyMuPDF (fitz) or pypdf; without either, \"no data: pip install pymupdf\"."),
    dict(id='mapa_codigo', script='mapa_codigo.py', defecto=True,
         linea='El índice greppable de un repo Python con `ast`: módulos, clases, funciones e imports con su línea.',
         linea_en='The greppable index of a Python repo with `ast`: modules, classes, functions and '
                  'imports with their line.',
         toca='sin gancho — uso manual (<carpeta> [--salida] [--json], --buscar <nombre>); '
              'ficheros mem/mapas/<carpeta>.txt(.json)',
         hooks=[],
         toca_en="no hook — manual use (<folder> [--salida] [--json], --buscar <name>); files "
                 "mem/mapas/<folder>.txt(.json)"),
    dict(id='auditar', script='auditar.py', defecto=True,
         linea='Las cinco comprobaciones sobre un paquete antes de instalarlo: procedencia, comandos, '
               'permisos, qué sale de la máquina, y dominios para lectura manual.',
         linea_en='The five checks on a package before installing it: provenance, commands, '
                  'permissions, what leaves the machine, and domains for manual reading.',
         toca='sin gancho — uso manual (`python auditar.py <ruta> [--json] [--markdown f.md]`, o vía la '
              'skill esceptico con --paquete); NUNCA ejecuta el código auditado (solo lee texto y, si hay '
              '.git, su historial LOCAL); no toca mem',
         hooks=[],
         toca_en="no hook — manual use (`python auditar.py <path> [--json] [--markdown f.md]`, or via "
                 "the esceptico skill with --paquete); NEVER executes the audited code (only reads text "
                 "and, if there's a .git, its LOCAL history); doesn't touch mem"),
    dict(id='kinetica', script='kinetica.py', defecto=True, especial='skill',
         carpeta_skill='kinetica',
         linea='Despieza UNA foto de un objeto en sus componentes REALES y los deja flotando en 3D '
               'sobre la mano, mirando la cámara.',
         linea_en='Takes ONE photo of an object apart into its REAL components and floats them in 3D '
                  'over your hand, using the camera.',
         toca='copia skills/kinetica/ a <skills-dir>/kinetica/; el visor se sirve SOLO en 127.0.0.1 y la '
              'cámara se enciende a petición explícita, nunca por gancho; no toca settings.json ni mem. '
              'Necesita opencv-python, numpy y Pillow, y las manos piden `--manos`',
         hooks=[],
         toca_en="copies skills/kinetica/ to <skills-dir>/kinetica/; the viewer is served ONLY on "
                 "127.0.0.1 and the camera is turned on by explicit request, never by a hook; doesn't "
                 "touch settings.json or mem. Needs opencv-python, numpy and Pillow, and hands need "
                 "`--manos`"),
    dict(id='kinetico', script='kinetico.py', defecto=True, especial='skill',
         carpeta_skill='kinetico',
         linea='Recorre con la mano un CONJUNTO de cosas —una carpeta del disco, un grafo de módulos— '
               'como un edificio 3D: entra en carpetas y abre ficheros con gestos.',
         linea_en='Walk through a SET of things by hand — a folder on disk, a module graph — as a 3D '
                  'building: step into folders and open files with gestures.',
         toca='copia skills/kinetico/ a <skills-dir>/kinetico/; su servidor expone dos verbos (entrar y '
              'abrir) SOLO sobre lo que esté en la escena montada y sin salir de la carpeta con la que '
              'se abrió; LEE la carpeta que se le diga y no escribe nada en ella; la cámara se enciende '
              'a petición explícita, nunca por gancho; no toca settings.json ni mem',
         hooks=[],
         toca_en="copies skills/kinetico/ to <skills-dir>/kinetico/; its server exposes two verbs (enter "
                 "and open) ONLY over what is in the mounted scene and never outside the folder it was "
                 "opened with; it READS the folder it is given and writes nothing into it; the camera is "
                 "turned on by explicit request, never by a hook; doesn't touch settings.json or mem"),
    dict(id='esceptico', script=None, defecto=True, especial='skill', carpeta_skill='esceptico',
         linea='La ley «ningún plan sin escéptico» como comando: lanza un revisor con model Opus a tumbar un '
               'plan antes de ejecutarlo, o (--paquete) a leer por encima del informe de auditar.py.',
         linea_en='The "no plan without a skeptic" rule as a command: launches an Opus-model reviewer '
                  'to try to shoot down a plan before running it, or (--paquete) to look over '
                  "auditar.py's report.",
         toca='copia skills/esceptico/ a <skills-dir>/esceptico/ (por defecto ~/.claude/skills/esceptico/, '
              'ver --skills-dir); no es Python, no toca settings.json ni mem',
         hooks=[],
         toca_en="copies skills/esceptico/ to <skills-dir>/esceptico/ (by default "
                 "~/.claude/skills/esceptico/, see --skills-dir); not Python, doesn't touch "
                 "settings.json or mem"),
    dict(id='infografia', script='infografia.py', defecto=True,
         linea='De un CSV o JSON a un SVG limpio (barras, barras horizontales, líneas, tabla), biblioteca estándar.',
         linea_en='From a CSV or JSON to a clean SVG (bars, horizontal bars, lines, table), standard '
                  'library only.',
         toca='sin gancho — uso manual; no resuelve proyecto, no toca mem: solo escribe el .svg que se le pida',
         hooks=[],
         toca_en="no hook — manual use; doesn't resolve a project, doesn't touch mem: it only writes the "
                 ".svg you ask for"),
    dict(id='taller', script='taller.py', defecto=False,
         especial='taller',
         linea='Deja lista la configuración de un taller local de texto→imagen para lienzo.py/imagen.py; '
               'no instala nada ni arranca el servidor.',
         linea_en='Sets up the configuration of a local text-to-image workshop for lienzo.py/imagen.py; '
                  'it does not install anything or start the server.',
         toca='sin gancho; ficheros mem/imagen_config.json (siembra/actualiza taller_url, taller_denoise, '
              'taller_pasos)',
         hooks=[], plantilla='imagen_config.json',
         aviso='NO instala diffusers/torch ni arranca ningún proceso: solo escribe la URL por defecto y dice, '
               'por stdout, el comando exacto para arrancarlo tú y qué instalar antes (nunca con pip desde aquí). '
               'El modelo se descarga de Hugging Face al PRIMER uso; en CPU, cada imagen tarda minutos, no segundos.',
         toca_en="no hook; files mem/imagen_config.json (seeds/updates taller_url, taller_denoise, "
                 "taller_pasos)",
         aviso_en="Does NOT install diffusers/torch or start any process: it only writes the default URL "
                  "and prints, on stdout, the exact command to start it yourself and what to install "
                  "first (never with pip from here). The model downloads from Hugging Face on FIRST use; "
                  "on CPU, each image takes minutes, not seconds."),
    dict(id='telegram', script=None, defecto=False, especial='telegram',
         linea='Aviso por Telegram cuando Claude Code necesita permiso o espera respuesta.',
         linea_en='Telegram notice when Claude Code needs permission or is waiting for a reply.',
         toca='gancho Notification → powershell + mem/notify_telegram.ps1 (nunca en el código)',
         hooks=[], aviso='pide token de bot y chat id; los guarda solo en mem/notify_telegram.ps1.',
         toca_en="Notification hook → powershell + mem/notify_telegram.ps1 (never in the code)",
         aviso_en="asks for a bot token and chat id; saves them only in mem/notify_telegram.ps1."),
    dict(id='permisos', script=None, defecto=False, especial='permisos',
         linea='Da permiso de Edit sobre tu settings.json (autoedición). APAGADO por defecto.',
         linea_en='Grants Edit permission over your settings.json (self-editing). OFF by default.',
         toca='clave permissions.allow += "Edit(<settings.json>)"',
         hooks=[], aviso='deja que el propio asistente edite settings.json sin preguntar cada vez.',
         toca_en="key permissions.allow += \"Edit(<settings.json>)\"",
         aviso_en="lets the assistant itself edit settings.json without asking each time."),
    dict(id='preferencias', script=None, defecto=True, especial='preferencias',
         linea='Preferencia showThinkingSummaries (ver los resúmenes de pensamiento).',
         linea_en='Preference showThinkingSummaries (show thinking summaries).',
         toca='clave showThinkingSummaries = true',
         hooks=[], claves={'showThinkingSummaries': True},
         toca_en="key showThinkingSummaries = true"),
]
MODULOS_POR_ID = {m['id']: m for m in MODULOS}


# ---------------------------------------------------------------------------------
# T5.1 · dependencias de terceros por módulo.
#
# Cada entrada: `import_nombre` (lo que se prueba a IMPORTAR de verdad, nunca una
# lista fija de "lo que suele hacer falta"), `pip_nombre` (lo que se instala),
# `para` (para qué sirve, en castellano) y `para_en` (la misma explicación en
# inglés — T5.2: la tabla de `--dependencias` es de las cadenas que el usuario
# ve, así que también lleva su traducción; `_para_localizado()` la elige y cae
# al castellano de `para` si a alguna entrada le faltara `para_en`, mismo
# fail-closed que `_texto()`). Comprobado contra el código real de cada guion, no
# copiado de la lista de ejemplo de la especificación (que avisa de no hacerlo):
#   - `imagen.py` en sí mismo (la cascada "crear") es solo biblioteca estándar;
#     Pillow/numpy los usan `pintor.py` ("imagen.py pintar") y `lienzo.py`;
#     imageio-ffmpeg lo usa `video_pintura.py` ("imagen.py video"); opencv-python
#     es OPCIONAL en `lienzo.py` (ruido/arañazos/relleno/zonas conexas/borrar):
#     sin ella, esos pasos caen a un camino en Python puro o se saltan con aviso.
#   - `ojo.py` necesita opencv-python para "mirar" (webcam) y, delegado, en
#     `lectura_visual.py` (fotocopia/tarjeta/manual: opencv-python+numpy+Pillow)
#     y en `volumen.py` (despiece/prompt3d: opencv-python+numpy). El OCR de
#     "texto"/"fotocopia"/"tarjeta"/"manual" NO usa ningún paquete de pip — usa
#     WinRT en Windows o el binario `tesseract` por PATH con `subprocess`
#     directo (nunca `pytesseract`) — por eso el motor de OCR vive en
#     `NO_INSTALABLES`, no aquí: instalar un paquete de pip no lo pondría.
#   - `lector_pdf.py` necesita `fitz` (PyMuPDF) O `pypdf` (con fitz, mejor
#     heurística de secciones); basta con una de las dos — `grupo_alternativa`
#     las liga, para no pedir instalar ambas cuando con una sobra.
#   - `gestos.py` (módulo propio, APAGADO por defecto) necesita mediapipe +
#     opencv-python + numpy para leer la cámara y calcular los landmarks.
# ---------------------------------------------------------------------------------
DEPENDENCIAS = {
    'imagen': [
        dict(import_nombre='PIL', pip_nombre='Pillow',
             para='pinta el cuadro de pinceladas localmente (pintor.py, "imagen.py pintar") y las '
                  'operaciones de lienzo.py (fundir/collage/restaurar/pintar por números)',
             para_en='renders the brushstroke painting locally (pintor.py, "imagen.py pintar") and '
                     'lienzo.py\'s operations (merge/collage/restore/paint-by-numbers)'),
        dict(import_nombre='numpy', pip_nombre='numpy',
             para='junto con Pillow: pintor.py y lienzo.py lo necesitan para componer localmente',
             para_en='together with Pillow: pintor.py and lienzo.py need it to compose locally'),
        dict(import_nombre='imageio_ffmpeg', pip_nombre='imageio-ffmpeg',
             para='codifica a .mp4 el vídeo acelerado de la pintura (video_pintura.py, "imagen.py '
                  'video"); trae su propio binario de ffmpeg, no hace falta instalarlo aparte',
             para_en='encodes the sped-up painting video to .mp4 (video_pintura.py, "imagen.py video"); '
                     'it bundles its own ffmpeg binary, no need to install one separately'),
        dict(import_nombre='cv2', pip_nombre='opencv-python', opcional=True,
             para='opcional en lienzo.py (ruido/arañazos/relleno/zonas conexas/borrar): sin ella, '
                  'esos pasos caen a un camino en Python puro o se saltan con aviso',
             para_en='optional in lienzo.py (noise/scratches/fill/connected-components/erase): without '
                     'it, those steps fall back to a pure-Python path or are skipped with a warning'),
    ],
    'ojo': [
        dict(import_nombre='cv2', pip_nombre='opencv-python',
             para='"mirar" (webcam) en ojo.py; y, delegado, fotocopia/tarjeta/manual (lectura_visual.py) '
                  'y despiece/prompt3d (volumen.py)',
             para_en='"mirar" (webcam) in ojo.py; and, delegated, fotocopia/tarjeta/manual '
                     '(lectura_visual.py) and despiece/prompt3d (volumen.py)'),
        dict(import_nombre='numpy', pip_nombre='numpy',
             para='junto con opencv-python: fotocopia/tarjeta/manual y despiece/prompt3d',
             para_en='together with opencv-python: fotocopia/tarjeta/manual and despiece/prompt3d'),
        dict(import_nombre='PIL', pip_nombre='Pillow',
             para='compone la tarjeta de visita en PNG y guarda las páginas de manual/fotocopia (lectura_visual.py)',
             para_en='composes the business-card PNG and saves the manual/fotocopia pages (lectura_visual.py)'),
    ],
    'lector_pdf': [
        dict(import_nombre='fitz', pip_nombre='PyMuPDF', grupo_alternativa='lector_pdf_motor',
             para='indexa y extrae texto del PDF con la mejor heurística de secciones (tamaños de letra reales)',
             para_en='indexes and extracts the PDF text with the best section heuristic (real font sizes)'),
        dict(import_nombre='pypdf', pip_nombre='pypdf', grupo_alternativa='lector_pdf_motor',
             para='alternativa a PyMuPDF si esta no está disponible',
             para_en='alternative to PyMuPDF if it is not available'),
    ],
    'gestos': [
        dict(import_nombre='mediapipe', pip_nombre='mediapipe',
             para='vocabulario de manos sobre el vídeo de la cámara (dedos, pellizco, pose de la palma...)',
             para_en='hand vocabulary over the camera video (fingers, pinch, palm pose...)'),
        dict(import_nombre='cv2', pip_nombre='opencv-python', para='lee la cámara para dársela a mediapipe',
             para_en='reads the camera to feed it to mediapipe'),
        dict(import_nombre='numpy', pip_nombre='numpy', para='cálculo geométrico de landmarks, junto con mediapipe',
             para_en='geometric landmark calculations, together with mediapipe'),
    ],
}

# Tamaños aproximados de la RUEDA (wheel) — medidos consultando la API JSON de
# pypi.org el 7-sep-2026 (rueda cp312/cp313 win_amd64 cuando existe; `pypdf` es
# universal, "py3-none-any"). Varían por plataforma/versión de Python y NO son lo
# que ocupará en disco (una dependencia transitiva ya instalada no vuelve a
# contar) — por eso la tabla los marca como "aprox." y nunca como una promesa; si
# algún paquete faltara aquí, la tabla dice «sin dato» en vez de inventar uno.
TAMANOS_APROX_MB = {
    'Pillow': 6.9,
    'numpy': 12.0,
    'imageio-ffmpeg': 29.8,
    'opencv-python': 42.0,
    'PyMuPDF': 18.9,
    'pypdf': 0.4,
    'mediapipe': 19.2,
}


# ---------------------------------------------------------------------------------
# T6 · MediaPipe Tasks Vision vendorizado para el visor cinético (kinetica.html +
# gestos.py) — DISTINTO de la entrada 'gestos' de `DEPENDENCIAS` de arriba: aquella
# es el paquete de PIP `mediapipe` (Python, para el resto de verbos de gestos.py);
# esto es el paquete de NPM `@mediapipe/tasks-vision` (JavaScript + WebAssembly),
# que corre DENTRO DEL NAVEGADOR y nunca se instala con pip. Los seis ficheros y
# tamaños de abajo están MEDIDOS (descargados y comprobados el 8-sep-2026; ver el
# informe de la tarea) — no se afina más de lo que ahí se midió. `destino` es
# siempre con "/" (nunca `os.sep` a pelo): `_ruta_vendor_mp` lo pasa por
# `os.path.join` para que valga en Windows y en POSIX por igual.
# ---------------------------------------------------------------------------------
COMANDO_DESCARGAR_MANOS = 'python instalar.py --manos'

VENDOR_MP = [
    dict(nombre='vision_bundle.mjs', destino='vision_bundle.mjs',
         tam_txt='~137 KB', tam_mb=0.137,
         url='https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/vision_bundle.mjs'),
    dict(nombre='wasm/vision_wasm_internal.js', destino='wasm/vision_wasm_internal.js',
         tam_txt='~210 KB', tam_mb=0.210,
         url='https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm/vision_wasm_internal.js'),
    dict(nombre='wasm/vision_wasm_internal.wasm', destino='wasm/vision_wasm_internal.wasm',
         tam_txt='~9.4 MB', tam_mb=9.4,
         url='https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm/vision_wasm_internal.wasm'),
    dict(nombre='wasm/vision_wasm_nosimd_internal.js', destino='wasm/vision_wasm_nosimd_internal.js',
         tam_txt='~210 KB', tam_mb=0.210,
         url='https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm/vision_wasm_nosimd_internal.js'),
    dict(nombre='wasm/vision_wasm_nosimd_internal.wasm', destino='wasm/vision_wasm_nosimd_internal.wasm',
         tam_txt='~9.3 MB', tam_mb=9.3,
         url='https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm/vision_wasm_nosimd_internal.wasm'),
    dict(nombre='hand_landmarker.task', destino='hand_landmarker.task',
         tam_txt='~7.8 MB', tam_mb=7.8,
         url='https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/'
             'hand_landmarker.task'),
]


def _ruta_vendor_mp(destino):
    """Ruta absoluta de `destino` (relativo, siempre con "/" — ver `VENDOR_MP`)
    dentro de `abyss/vendor/mp/`."""
    return os.path.join(PKG, 'vendor', 'mp', *destino.split('/'))


def _estado_vendor_mp():
    """`[{**entrada_de_VENDOR_MP, 'presente': bool, 'falta': bool}, ...]` —
    'presente' es un `os.path.isfile` REAL sobre `abyss/vendor/mp/<destino>`,
    nunca una lista fija (mismo criterio fail-closed que `_import_disponible`
    con los paquetes de pip: se mira el disco, no se asume nada)."""
    salida = []
    for v in VENDOR_MP:
        presente = os.path.isfile(_ruta_vendor_mp(v['destino']))
        salida.append(dict(v, presente=presente, falta=not presente))
    return salida


def _import_disponible(nombre_import, python_exe=None):
    """True si `import <nombre_import>` funciona de VERDAD bajo `python_exe` (por
    defecto, `sys.executable`). Un `import` real en un proceso aparte con ESE
    intérprete exacto — el que de verdad va a correr los guiones de abyss si se
    usó `--python <exe>` — nunca una lista de paquetes fijada a mano ni un `pip
    show`/`pip list` que pudiera dar por bueno un paquete instalado pero roto
    (o instalado para OTRO intérprete). Cualquier fallo (sin ese `python`, sin
    permiso, timeout) cuenta como "no disponible" — fail-closed, nunca revienta
    el propio instalador."""
    python_exe = python_exe or sys.executable
    try:
        r = subprocess.run([python_exe, '-c', f'import {nombre_import}'],
                            capture_output=True, text=True, timeout=20)
        return r.returncode == 0
    except Exception:
        return False


def _estado_dependencias(modulos=None, python_exe=None):
    """`{modulo_id: [ {**entrada_de_DEPENDENCIAS, 'presente': bool, 'falta': bool}, ... ]}`
    para `modulos` (lista de ids de `DEPENDENCIAS`; `None` = todos). `falta` es
    `False` si la propia entrada está presente O si algún miembro de su mismo
    `grupo_alternativa` lo está (basta una alternativa, p. ej. fitz O pypdf)."""
    modulos = list(DEPENDENCIAS) if modulos is None else [m for m in modulos if m in DEPENDENCIAS]
    salida = {}
    for mid in modulos:
        vistas = [dict(e, presente=_import_disponible(e['import_nombre'], python_exe))
                  for e in DEPENDENCIAS.get(mid, [])]
        grupos_ok = {v['grupo_alternativa'] for v in vistas if v.get('grupo_alternativa') and v['presente']}
        for v in vistas:
            grupo = v.get('grupo_alternativa')
            v['falta'] = (not v['presente']) and (grupo not in grupos_ok if grupo else True)
        salida[mid] = vistas
    return salida


def _paquetes_a_instalar(modulos, python_exe=None):
    """`[(modulo_id, pip_nombre), ...]` solo con lo que de verdad falta para
    `modulos` (ver `_estado_dependencias`). De un `grupo_alternativa` sin
    ninguna presente, instala solo la PRIMERA declarada (la preferida, p. ej.
    PyMuPDF antes que pypdf) — instalar las dos sería instalar de más para
    cubrir lo mismo."""
    estado = _estado_dependencias(modulos, python_exe)
    vistos_grupo = set()
    paquetes = []
    for mid, entradas in estado.items():
        for e in entradas:
            if not e['falta']:
                continue
            grupo = e.get('grupo_alternativa')
            if grupo:
                if grupo in vistos_grupo:
                    continue
                vistos_grupo.add(grupo)
            paquetes.append((mid, e['pip_nombre']))
    return paquetes


def _hay_gpu_nvidia():
    """True si `nvidia-smi` responde (hay driver NVIDIA instalado) — comprobado
    por su cuenta con `subprocess`, SIN necesitar `torch` puesto (a diferencia de
    `taller._tiene_cuda()`, que solo puede preguntar una vez que torch YA está):
    así este instalador puede recomendar el `pip install` correcto ANTES de que
    nada de torch exista en la máquina. Sin `nvidia-smi` en el PATH (no hay
    driver NVIDIA, o no es esa GPU): `False` — nunca revienta por su ausencia."""
    try:
        r = subprocess.run(['nvidia-smi'], capture_output=True, text=True, timeout=5)
        return r.returncode == 0
    except Exception:
        return False


def _comando_taller_torch():
    """El `pip install torch` exacto para esta máquina (T5.1: "detecta si hay GPU
    NVIDIA y escribe el comando de instalación que corresponde"). Con GPU NVIDIA
    detectada, la rueda CUDA; si no, la de CPU (server sin GPU, o AMD/Intel/Apple,
    donde el índice de PyPI ya sirve la rueda correcta por su cuenta)."""
    if _hay_gpu_nvidia():
        return 'pip install torch --index-url https://download.pytorch.org/whl/cu121'
    return 'pip install torch'


def _ultima_linea_no_vacia(texto):
    lineas = [l for l in (texto or '').strip().splitlines() if l.strip()]
    return lineas[-1].strip() if lineas else None


def instalar_dependencias(modulos, *, python_exe=None, idioma='es'):
    """Instala, UNA a una, las dependencias de pip que de verdad faltan para
    `modulos` (lista de ids de `DEPENDENCIAS`; `None`/`[]` = todos). Por cada
    paquete: enseña el comando `sys.executable -m pip install <paquete>` (con el
    `python_exe` pedido) ANTES de correrlo, y el resultado DESPUÉS — nunca en
    silencio. Un fallo (sin pip, sin red, `pip install` con error) se dice con la
    ÚLTIMA línea de su salida y se sigue con el resto — nunca se reintenta solo,
    nunca se instala nada más allá de lo que ya faltaba. Devuelve `(mensajes, ok)`
    con `ok=False` si algún paquete falló (para el código de salida de la CLI).
    Se llama SOLO desde la CLI (`--instalar-dependencias`) o la casilla de la
    ventana — nunca desde un gancho, nunca al arrancar."""
    python_exe = python_exe or sys.executable
    mensajes = []
    paquetes = _paquetes_a_instalar(modulos, python_exe)
    if not paquetes:
        mensajes.append(_texto(idioma, 'dep_nada_que_instalar'))
        return mensajes, True
    ok = True
    for mid, pip_nombre in paquetes:
        comando = [python_exe, '-m', 'pip', 'install', pip_nombre]
        mensajes.append(_texto(idioma, 'dep_comando_antes', comando=' '.join(comando)))
        try:
            r = subprocess.run(comando, capture_output=True, text=True, timeout=600)
        except Exception as e:
            mensajes.append(_texto(idioma, 'dep_error_excepcion', paquete=pip_nombre, error=str(e)))
            ok = False
            continue
        if r.returncode == 0:
            mensajes.append(_texto(idioma, 'dep_ok', paquete=pip_nombre))
        else:
            motivo = _ultima_linea_no_vacia(r.stderr) or _ultima_linea_no_vacia(r.stdout) \
                or _texto(idioma, 'dep_codigo_salida', codigo=r.returncode)
            mensajes.append(_texto(idioma, 'dep_fallo', paquete=pip_nombre, motivo=motivo))
            ok = False
    return mensajes, ok


# ---------------------------------------------------------------------------------
# T6 · descarga de MediaPipe Tasks Vision (`--manos`) — ver `VENDOR_MP` arriba.
# Se llama SOLO desde `--manos` en `__main__` (nunca desde un gancho, nunca al
# arrancar, nunca desde `instalar()`/`desinstalar()`): mismo principio que
# `instalar_dependencias()`, que tampoco corre sola. Regla dura 5 del encargo
# (las pruebas NUNCA bajan nada real): todo lo que toca la red de verdad pasa
# por `_descargar_uno`, el único punto que las pruebas sustituyen por
# monkeypatch.
# ---------------------------------------------------------------------------------
class _SinRedError(Exception):
    """`_descargar_uno` no pudo ni conectar (DNS, conexión rehusada, timeout de
    conexión) — a diferencia de un `HTTPError` (SÍ hay red; el servidor
    respondió con un error) o de un fallo al escribir en disco (tampoco es de
    red). `descargar_vendor_mp()` la usa para parar el lote entero de golpe,
    limpio y sin traza, en vez de repetir el mismo aviso de red con cada
    fichero que quedara."""


def _descargar_uno(url, destino_abs, *, timeout=30):
    """Único punto que toca la red de verdad en `descargar_vendor_mp()` — las
    pruebas lo sustituyen por monkeypatch (regla dura 5 del encargo: ninguna
    prueba baja nada real). Escribe primero a `<destino>.tmp-abyss` y solo hace
    `os.replace` al final (mismo patrón que `_escribir_json`): un corte a
    medias nunca deja un fichero a medio escribir con el nombre bueno. Devuelve
    los bytes escritos, medidos de verdad con `os.path.getsize` (nunca el
    tamaño aproximado de `VENDOR_MP`, que es solo orientativo)."""
    try:
        respuesta = urllib.request.urlopen(url, timeout=timeout)
    except urllib.error.HTTPError as e:
        # sí hay red: el servidor respondió, pero con un error (404, 500...).
        raise RuntimeError(f'HTTP {e.code}') from e
    except (urllib.error.URLError, socket.timeout, ConnectionError) as e:
        raise _SinRedError(str(getattr(e, 'reason', e))) from e
    carpeta = os.path.dirname(destino_abs)
    if carpeta:
        os.makedirs(carpeta, exist_ok=True)
    tmp = destino_abs + '.tmp-abyss'
    try:
        with respuesta, open(tmp, 'wb') as fh:
            shutil.copyfileobj(respuesta, fh)
    except Exception:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise
    os.replace(tmp, destino_abs)
    return os.path.getsize(destino_abs)


# Metadatos + texto COMPLETO de la Apache License 2.0 (fuente:
# https://www.apache.org/licenses/LICENSE-2.0.txt, comprobado 8-sep-2026, 11.358
# bytes, sin modificar). Es la licencia que el propio paquete declara
# ("license": "Apache-2.0" en el package.json de @mediapipe/tasks-vision@0.10.14,
# comprobado ese mismo día) — mismo patrón que `abyss/vendor/LICENSE-three.txt`,
# pero escrito por el instalador (estos ficheros nunca se commitean: no hay un
# `LICENSE-mediapipe.txt` fijo en el repo, se genera cada vez que se corre
# `--manos`, junto a lo que descarga).
_LICENCIA_MEDIAPIPE_TEXTO = """MediaPipe Tasks Vision — vendorizado para abyss/gestos.py y
abyss/plantillas/kinetica.html (T6)

Paquete: @mediapipe/tasks-vision@0.10.14 (npm), servido por jsdelivr
(cdn.jsdelivr.net); el modelo hand_landmarker.task viene de
storage.googleapis.com/mediapipe-models (Google, proyecto MediaPipe). Ficheros
vendorizados en abyss/vendor/mp/: vision_bundle.mjs, wasm/vision_wasm_internal.js,
wasm/vision_wasm_internal.wasm, wasm/vision_wasm_nosimd_internal.js,
wasm/vision_wasm_nosimd_internal.wasm, hand_landmarker.task — origen exacto de
cada uno en VENDOR_MP (instalar.py) o en `python instalar.py --dependencias`.

Licencia: Apache License 2.0 — declarada por el propio paquete ("license":
"Apache-2.0" en su package.json, comprobado 8-sep-2026). Este fichero lo escribe
`instalar.py --manos` cada vez que baja los ficheros de arriba; vive en
abyss/vendor/mp/, que NUNCA se sube al repositorio (son ficheros de terceros
descargados, no código propio de este paquete). Texto completo debajo, tal
cual, sin modificar (fuente: https://www.apache.org/licenses/LICENSE-2.0.txt).

────────────────────────────────────────────────────────────────────────────────

                                 Apache License
                           Version 2.0, January 2004
                        http://www.apache.org/licenses/

   TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION

   1. Definitions.

      "License" shall mean the terms and conditions for use, reproduction,
      and distribution as defined by Sections 1 through 9 of this document.

      "Licensor" shall mean the copyright owner or entity authorized by
      the copyright owner that is granting the License.

      "Legal Entity" shall mean the union of the acting entity and all
      other entities that control, are controlled by, or are under common
      control with that entity. For the purposes of this definition,
      "control" means (i) the power, direct or indirect, to cause the
      direction or management of such entity, whether by contract or
      otherwise, or (ii) ownership of fifty percent (50%) or more of the
      outstanding shares, or (iii) beneficial ownership of such entity.

      "You" (or "Your") shall mean an individual or Legal Entity
      exercising permissions granted by this License.

      "Source" form shall mean the preferred form for making modifications,
      including but not limited to software source code, documentation
      source, and configuration files.

      "Object" form shall mean any form resulting from mechanical
      transformation or translation of a Source form, including but
      not limited to compiled object code, generated documentation,
      and conversions to other media types.

      "Work" shall mean the work of authorship, whether in Source or
      Object form, made available under the License, as indicated by a
      copyright notice that is included in or attached to the work
      (an example is provided in the Appendix below).

      "Derivative Works" shall mean any work, whether in Source or Object
      form, that is based on (or derived from) the Work and for which the
      editorial revisions, annotations, elaborations, or other modifications
      represent, as a whole, an original work of authorship. For the purposes
      of this License, Derivative Works shall not include works that remain
      separable from, or merely link (or bind by name) to the interfaces of,
      the Work and Derivative Works thereof.

      "Contribution" shall mean any work of authorship, including
      the original version of the Work and any modifications or additions
      to that Work or Derivative Works thereof, that is intentionally
      submitted to Licensor for inclusion in the Work by the copyright owner
      or by an individual or Legal Entity authorized to submit on behalf of
      the copyright owner. For the purposes of this definition, "submitted"
      means any form of electronic, verbal, or written communication sent
      to the Licensor or its representatives, including but not limited to
      communication on electronic mailing lists, source code control systems,
      and issue tracking systems that are managed by, or on behalf of, the
      Licensor for the purpose of discussing and improving the Work, but
      excluding communication that is conspicuously marked or otherwise
      designated in writing by the copyright owner as "Not a Contribution."

      "Contributor" shall mean Licensor and any individual or Legal Entity
      on behalf of whom a Contribution has been received by Licensor and
      subsequently incorporated within the Work.

   2. Grant of Copyright License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      copyright license to reproduce, prepare Derivative Works of,
      publicly display, publicly perform, sublicense, and distribute the
      Work and such Derivative Works in Source or Object form.

   3. Grant of Patent License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      (except as stated in this section) patent license to make, have made,
      use, offer to sell, sell, import, and otherwise transfer the Work,
      where such license applies only to those patent claims licensable
      by such Contributor that are necessarily infringed by their
      Contribution(s) alone or by combination of their Contribution(s)
      with the Work to which such Contribution(s) was submitted. If You
      institute patent litigation against any entity (including a
      cross-claim or counterclaim in a lawsuit) alleging that the Work
      or a Contribution incorporated within the Work constitutes direct
      or contributory patent infringement, then any patent licenses
      granted to You under this License for that Work shall terminate
      as of the date such litigation is filed.

   4. Redistribution. You may reproduce and distribute copies of the
      Work or Derivative Works thereof in any medium, with or without
      modifications, and in Source or Object form, provided that You
      meet the following conditions:

      (a) You must give any other recipients of the Work or
          Derivative Works a copy of this License; and

      (b) You must cause any modified files to carry prominent notices
          stating that You changed the files; and

      (c) You must retain, in the Source form of any Derivative Works
          that You distribute, all copyright, patent, trademark, and
          attribution notices from the Source form of the Work,
          excluding those notices that do not pertain to any part of
          the Derivative Works; and

      (d) If the Work includes a "NOTICE" text file as part of its
          distribution, then any Derivative Works that You distribute must
          include a readable copy of the attribution notices contained
          within such NOTICE file, excluding those notices that do not
          pertain to any part of the Derivative Works, in at least one
          of the following places: within a NOTICE text file distributed
          as part of the Derivative Works; within the Source form or
          documentation, if provided along with the Derivative Works; or,
          within a display generated by the Derivative Works, if and
          wherever such third-party notices normally appear. The contents
          of the NOTICE file are for informational purposes only and
          do not modify the License. You may add Your own attribution
          notices within Derivative Works that You distribute, alongside
          or as an addendum to the NOTICE text from the Work, provided
          that such additional attribution notices cannot be construed
          as modifying the License.

      You may add Your own copyright statement to Your modifications and
      may provide additional or different license terms and conditions
      for use, reproduction, or distribution of Your modifications, or
      for any such Derivative Works as a whole, provided Your use,
      reproduction, and distribution of the Work otherwise complies with
      the conditions stated in this License.

   5. Submission of Contributions. Unless You explicitly state otherwise,
      any Contribution intentionally submitted for inclusion in the Work
      by You to the Licensor shall be under the terms and conditions of
      this License, without any additional terms or conditions.
      Notwithstanding the above, nothing herein shall supersede or modify
      the terms of any separate license agreement you may have executed
      with Licensor regarding such Contributions.

   6. Trademarks. This License does not grant permission to use the trade
      names, trademarks, service marks, or product names of the Licensor,
      except as required for reasonable and customary use in describing the
      origin of the Work and reproducing the content of the NOTICE file.

   7. Disclaimer of Warranty. Unless required by applicable law or
      agreed to in writing, Licensor provides the Work (and each
      Contributor provides its Contributions) on an "AS IS" BASIS,
      WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
      implied, including, without limitation, any warranties or conditions
      of TITLE, NON-INFRINGEMENT, MERCHANTABILITY, or FITNESS FOR A
      PARTICULAR PURPOSE. You are solely responsible for determining the
      appropriateness of using or redistributing the Work and assume any
      risks associated with Your exercise of permissions under this License.

   8. Limitation of Liability. In no event and under no legal theory,
      whether in tort (including negligence), contract, or otherwise,
      unless required by applicable law (such as deliberate and grossly
      negligent acts) or agreed to in writing, shall any Contributor be
      liable to You for damages, including any direct, indirect, special,
      incidental, or consequential damages of any character arising as a
      result of this License or out of the use or inability to use the
      Work (including but not limited to damages for loss of goodwill,
      work stoppage, computer failure or malfunction, or any and all
      other commercial damages or losses), even if such Contributor
      has been advised of the possibility of such damages.

   9. Accepting Warranty or Additional Liability. While redistributing
      the Work or Derivative Works thereof, You may choose to offer,
      and charge a fee for, acceptance of support, warranty, indemnity,
      or other liability obligations and/or rights consistent with this
      License. However, in accepting such obligations, You may act only
      on Your own behalf and on Your sole responsibility, not on behalf
      of any other Contributor, and only if You agree to indemnify,
      defend, and hold each Contributor harmless for any liability
      incurred by, or claims asserted against, such Contributor by reason
      of your accepting any such warranty or additional liability.

   END OF TERMS AND CONDITIONS

   APPENDIX: How to apply the Apache License to your work.

      To apply the Apache License to your work, attach the following
      boilerplate notice, with the fields enclosed by brackets "[]"
      replaced with your own identifying information. (Don't include
      the brackets!)  The text should be enclosed in the appropriate
      comment syntax for the file format. We also recommend that a
      file or class name and description of purpose be included on the
      same "printed page" as the copyright notice for easier
      identification within third-party archives.

   Copyright [yyyy] [name of copyright owner]

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
"""


def _escribir_licencia_mediapipe():
    """Escribe `abyss/vendor/mp/LICENSE-mediapipe.txt` (mismo patrón que
    `abyss/vendor/LICENSE-three.txt`, pero GENERADO por el instalador en vez de
    fijo en el repo — ver el comentario junto a `_LICENCIA_MEDIAPIPE_TEXTO`).
    Se llama solo tras terminar `descargar_vendor_mp()` sin fallos; quien la
    llama envuelve esto en su propio `try/except` — un fallo aquí (permiso,
    disco lleno) no debe tirar una descarga que ya terminó bien."""
    ruta = _ruta_vendor_mp('LICENSE-mediapipe.txt')
    carpeta = os.path.dirname(ruta)
    if carpeta:
        os.makedirs(carpeta, exist_ok=True)
    tmp = ruta + '.tmp-abyss'
    with open(tmp, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(_LICENCIA_MEDIAPIPE_TEXTO)
    os.replace(tmp, ruta)


# ---------------------------------------------------------------------------------
# El modelo de recorte de fondo (`--modelo`). Mismo trato que MediaPipe y por la
# misma razón: NUNCA en el repositorio de git. La URL y el destino se leen de
# `abyss/fondo.py` (constantes `URL_MODELO` y `MODELO`) en vez de repetirlas aquí,
# que es como se garantiza que el instalador baja EXACTAMENTE el fichero que el
# módulo va a buscar — dos copias de una URL se desincronizan el día que una cambia.
# La red la toca `_descargar_uno`, el único punto que las pruebas sustituyen.
# ---------------------------------------------------------------------------------
COMANDO_DESCARGAR_MODELO = 'python instalar.py --modelo'


def _millares(n, idioma):
    """El separador de millares es del IDIOMA, no del programa: 4.574.861 en castellano
    y 4,574,861 en inglés. Escribir un número español dentro de una frase inglesa es un
    descuido que se lee como una traducción a medias."""
    return f'{n:,}' if idioma == 'en' else f'{n:,}'.replace(',', '.')


def _datos_del_modelo():
    """`(url, destino_abs)` leídos de `abyss/fondo.py`. Se carga el módulo por ruta y
    no con `import`, para no arrastrar sus dependencias (numpy, Pillow) solo por
    saber una URL: el instalador tiene que poder correr en una máquina pelada."""
    ruta = _script('fondo.py')
    url = destino = None
    with open(ruta, encoding='utf-8') as fh:
        for linea in fh:
            if linea.startswith('URL_MODELO'):
                url = linea.split('=', 1)[1].strip().strip("'" + '"')
            elif linea.startswith('MODELO ='):
                destino = os.path.join(RAIZ, 'abyss', 'vendor', 'modelos', 'u2netp.onnx')
            if url and destino:
                break
    return url, destino


def descargar_vendor_modelo(*, idioma='es', forzar=False, timeout=30):
    """Descarga `abyss/vendor/modelos/u2netp.onnx` (unos 4,4 MB), el modelo que usa
    `abyss/fondo.py` para quitarle el fondo a una foto. Se llama SOLO desde `--modelo`
    en la CLI: nunca desde un gancho, nunca al arrancar, nunca en silencio. Enseña de
    dónde y a dónde ANTES de tocar la red, y los bytes reales DESPUÉS.
    Sin él, `fondo.py` no se queda muerto: usa el recorte del sistema o GrabCut, y
    dice siempre con qué motor recortó. Devuelve `(mensajes, ok)`."""
    url, destino = _datos_del_modelo()
    mensajes = []
    if not url or not destino:
        mensajes.append(_texto(idioma, 'modelo_sin_url'))
        return mensajes, False
    if os.path.isfile(destino) and not forzar:
        mensajes.append(_texto(idioma, 'modelo_ya_esta',
                                bytes=_millares(os.path.getsize(destino), idioma)))
        return mensajes, True
    mensajes.append(_texto(idioma, 'modelo_previa', url=url, destino=destino))
    mensajes.append(_texto(idioma, 'modelo_licencia'))
    try:
        n = _descargar_uno(url, destino, timeout=timeout)
    except _SinRedError as e:
        mensajes.append(_texto(idioma, 'vendor_mp_sin_red', url=url, motivo=str(e)))
        return mensajes, False
    except Exception as e:
        mensajes.append(_texto(idioma, 'vendor_mp_fallo', fichero='u2netp.onnx', motivo=str(e)))
        return mensajes, False
    mensajes.append(_texto(idioma, 'modelo_bajado', bytes=_millares(n, idioma)))
    return mensajes, True


def descargar_vendor_mp(*, idioma='es', forzar=False, timeout=30):
    """Descarga a `abyss/vendor/mp/` lo que le falte al visor cinético
    (MediaPipe Tasks Vision: JS + wasm + el modelo de manos) — ~27 MB en total,
    NUNCA en el repositorio de git. Se llama SOLO desde `--manos` en la CLI:
    nunca desde un gancho, nunca al arrancar, nunca en silencio — enseña la
    lista completa (de dónde, a dónde, cuánto ocupa) ANTES de tocar la red, y
    el resultado de cada fichero DESPUÉS, igual que `instalar_dependencias()`.
    Sin red: UN aviso limpio (nunca una traza de Python) y se PARA ahí — no
    repite el mismo fallo con los ficheros que quedaran. `forzar=True` vuelve a
    bajar también lo que ya estuviera presente (por defecto, se salta lo que ya
    está). Devuelve `(mensajes, ok)`."""
    estado = _estado_vendor_mp()
    pendientes = estado if forzar else [v for v in estado if v['falta']]
    mensajes = []
    if not pendientes:
        mensajes.append(_texto(idioma, 'vendor_mp_nada_que_bajar'))
        return mensajes, True
    total_mb = sum(v['tam_mb'] for v in pendientes)
    mensajes.append(_texto(idioma, 'vendor_mp_previa_cabecera', total=f'{total_mb:.0f}'))
    for v in pendientes:
        mensajes.append(_texto(idioma, 'vendor_mp_previa_fila', url=v['url'], destino=v['destino'],
                                tam=v['tam_txt']))
    mensajes.append(_texto(idioma, 'vendor_mp_licencia_aviso'))
    ok = True
    for v in pendientes:
        destino_abs = _ruta_vendor_mp(v['destino'])
        try:
            n = _descargar_uno(v['url'], destino_abs, timeout=timeout)
        except _SinRedError as e:
            mensajes.append(_texto(idioma, 'vendor_mp_sin_red', url=v['url'], motivo=str(e)))
            return mensajes, False
        except Exception as e:
            mensajes.append(_texto(idioma, 'vendor_mp_fallo', fichero=v['nombre'], motivo=str(e)))
            ok = False
            continue
        mensajes.append(_texto(idioma, 'vendor_mp_ok', fichero=v['nombre'], bytes=n))
    if ok:
        try:
            _escribir_licencia_mediapipe()
            mensajes.append(_texto(idioma, 'vendor_mp_licencia_escrita'))
        except Exception:
            pass  # documentación, no crítico — nunca revienta una descarga ya hecha
    return mensajes, ok


def _para_localizado(idioma, e):
    """El texto de la columna «para qué» en el idioma pedido (T5.2): con
    `idioma != 'es'` usa `e['para_en']` si la entrada la declara; si no (fail-
    closed, mismo criterio que `_texto()`), cae al castellano de `e['para']`
    antes que dejar la fila sin explicación."""
    if idioma != 'es':
        en = e.get('para_en')
        if en:
            return en
    return e['para']


def _fila_dependencia(idioma, mid, e):
    estado = _texto(idioma, 'dep_falta_si') if e['falta'] else _texto(idioma, 'dep_falta_no')
    tam = TAMANOS_APROX_MB.get(e['pip_nombre'])
    tam_txt = f'~{tam} MB' if tam is not None else _texto(idioma, 'sin_dato')
    marca = _texto(idioma, 'marca_opcional') if e.get('opcional') else ''
    if e.get('grupo_alternativa') and e['presente'] is False and not e['falta']:
        marca += _texto(idioma, 'marca_alternativa_cubierta')
    return f'  {mid:12} {estado:8} {e["pip_nombre"]:16}{marca:16} {tam_txt:10} {_para_localizado(idioma, e)}'


def _texto_no_instalables(idioma):
    """T5.1: lo que este instalador NO puede poner porque son binarios del
    sistema (nunca de pip) — el motor de OCR fuera de Windows (el código llama al
    binario `tesseract` por PATH, nunca a `pytesseract`: instalarlo por pip no
    activaría nada) y torch+diffusers para `taller.py` (pesan gigas y dependen de
    la tarjeta). Se dice el comando EXACTO del sistema operativo de ESTA máquina,
    nunca uno genérico fingiendo que vale para cualquiera."""
    lineas = [_texto(idioma, 'no_instalable_cabecera')]
    so = platform.system()
    if so == 'Windows':
        lineas.append(_texto(idioma, 'ocr_windows'))
    elif so == 'Darwin':
        lineas.append(_texto(idioma, 'ocr_macos'))
    else:
        lineas.append(_texto(idioma, 'ocr_linux'))
    lineas.append(_texto(idioma, 'taller_gpu', comando=_comando_taller_torch()))
    return '\n'.join(lineas)


def _tabla_vendor_mp(idioma):
    """T6: la fila de `--dependencias` para MediaPipe Tasks Vision (el vendor de
    `abyss/vendor/mp/`, ver `VENDOR_MP`) — dice, fichero a fichero, si está o
    falta (mismo `os.path.isfile` real de `_estado_vendor_mp`, nunca una
    suposición). No son paquetes de pip: `--instalar-dependencias` no los toca;
    se bajan aparte con `COMANDO_DESCARGAR_MANOS`."""
    estado = _estado_vendor_mp()
    total_mb = sum(v['tam_mb'] for v in estado)
    filas = [_texto(idioma, 'vendor_mp_cabecera')]
    for v in estado:
        est = _texto(idioma, 'dep_falta_si') if v['falta'] else _texto(idioma, 'dep_falta_no')
        filas.append(f'  {v["nombre"]:36} {est:8} {v["tam_txt"]:>8}')
    return '\n'.join(filas) + '\n' + _texto(idioma, 'vendor_mp_pie', total=f'{total_mb:.0f}',
                                             comando=COMANDO_DESCARGAR_MANOS)


def _tabla_dependencias(idioma, modulos=None, python_exe=None):
    estado = _estado_dependencias(modulos, python_exe)
    filas = [_texto(idioma, 'dep_cabecera')]
    for mid, entradas in estado.items():
        for e in entradas:
            filas.append(_fila_dependencia(idioma, mid, e))
    return ('\n'.join(filas) + '\n\n' + _texto_no_instalables(idioma) + '\n\n'
            + _tabla_vendor_mp(idioma))


# ---------------------------------------------------------------------------------
# T5.2 · bilingüe: las cadenas cortas de interfaz
# (ventana, botones, avisos, cabeceras, mensajes de error, resumen final) pasan
# TODAS por aquí — nunca una cadena suelta en medio del código. `_texto()` es el
# ÚNICO punto de lectura de ESTE diccionario; si una clave faltara en el idioma
# pedido, cae al castellano antes que reventar (fail-closed también en esto:
# preferible un mensaje en el idioma "que no toca" a ningún mensaje).
#
# Dos bloques de texto largo NO viven en `TEXTOS` porque son datos por-entrada,
# no vocabulario de interfaz — pero SÍ se traducen, con el mismo fail-closed,
# junto a su dato: `mod['linea']`/`mod['linea_en']` en `MODULOS` (la descripción
# de una frase de cada módulo; ver `_listar()`) y `e['para']`/`e['para_en']` en
# `DEPENDENCIAS` (la columna «para qué»; ver `_para_localizado()`). Antes de que
# existieran `linea_en`/`para_en` (medido 7-sep), `--idioma en --dependencias` y
# `--idioma en --listar` imprimían esos dos bloques enteros en castellano sin
# avisarlo — la mayoría de lo que el usuario veía en pantalla, incumpliendo
# justo la promesa de este párrafo; ahora si a una entrada le faltara la
# traducción, cae a su castellano en vez de dejar la fila muda, igual que
# `_texto()`.
#
# `mod['toca']`/`mod['aviso']` SÍ se quedan sin traducir a propósito: llevan
# vocabulario de control castellano (nombres de gancho, rutas de `mem/`, verbos
# de la CLI) que traducido a medias sería peor que no traducido — `_listar()`
# los OMITE en inglés en vez de imprimirlos así, y `listar_detalle_nota` (abajo)
# lo dice.
# ---------------------------------------------------------------------------------
TEXTOS = {
    'es': {
        'settings_prefix': 'settings: ',
        'no_existe_aun': '  (no existe todavía)',
        'estado_instalado': 'instalado',
        'estado_no_instalado': 'no instalado',
        'estado_sin_gancho': 'sin gancho propio',
        'listar_detalle_nota': '',  # en castellano SÍ se imprime toca/aviso; no hace falta nota
        'apagado_como': 'apagado por defecto; para encenderlo:',
        'toca_label': 'toca:',
        'aviso_label': 'aviso:',
        'falta_valor': 'falta el valor de {bandera}',
        'argumento_no_reconocido': 'argumento no reconocido: {bandera}',
        'modulo_desconocido': '? módulo desconocido: {id}',
        'telegram_faltan_credenciales': 'telegram: faltan credenciales (--telegram-token/--telegram-chat); no se instala',
        'skill_copiada': '{mid}: skill copiada a {destino}',
        'skill_retirada': '{mid}: skill retirada de {destino}',
        'skill_no_tocada': '{mid}: {destino} no lleva la marca de abyss — no se toca',
        'plantilla_sembrada': '{mid}: sembrado mem/{plantilla}',
        'modulo_instalado': '{mid}: instalado',
        'modulo_ya_instalado': '{mid}: ya estaba instalado',
        'modulo_desinstalado': '{mid}: desinstalado',
        'taller_mensaje': (
            '{mid}: NO se instala nada ni se arranca ningún proceso. Para arrancarlo tú: '
            'python "{script}" [--puerto 7860] [--modelo Lykon/dreamshaper-8] [--cache-dir <ruta>] '
            '[--dispositivo auto|cuda|mps|cpu] [--pasos 20] — necesita "pip install diffusers '
            'transformers accelerate" y "{torch_cmd}". El modelo se descarga de Hugging Face al '
            'primer uso; en CPU, cada imagen tarda minutos, no segundos.'),
        'datos_borrados_lista': 'datos generados borrados: {lista}',
        'datos_borrados_nada': '(no había nada)',
        'error_proyecto': 'instalar: no se pudo resolver el proyecto (pasa --proyecto <cwd> o define ABYSS_PROYECTO)',
        'sin_ventana_fallback': 'instalar: sin ventana ({tipo}: {error}); mostrando --listar en su lugar\n',
        'pregunta_borrar_datos': '¿Borrar también sesiones/relojes/etc. generados por abyss? (s/N): ',
        'telegram_pedir_token': 'Abyss · Telegram: token del bot: ',
        'telegram_pedir_chat': 'Abyss · Telegram: chat id: ',
        'dep_cabecera': f'  {"módulo":12} {"falta":8} {"paquete pip":16}{"":16} {"tamaño aprox.":10} para qué',
        'dep_falta_si': 'FALTA',
        'dep_falta_no': 'ok',
        'sin_dato': 'sin dato',
        'marca_opcional': ' (opcional)',
        'marca_alternativa_cubierta': ' (cubierta)',
        'no_instalable_cabecera': 'Lo que este instalador NO puede poner (hace falta el gestor del sistema):',
        'ocr_windows': '  OCR: en Windows el motor de reconocimiento de texto viene con el sistema (WinRT) — no hace falta instalar nada.',
        'ocr_linux': '  OCR: instala el binario de tesseract con tu gestor: sudo apt install tesseract-ocr tesseract-ocr-spa',
        'ocr_macos': '  OCR: instala el binario de tesseract con Homebrew: brew install tesseract tesseract-lang',
        'taller_gpu': '  taller.py (torch + diffusers): pesan gigas y torch depende de la tarjeta — este instalador '
                      'no los instala. Comando detectado para esta máquina: {comando}',
        'dep_nada_que_instalar': 'nada que instalar: ya estaba todo presente',
        'dep_comando_antes': 'comando: {comando}',
        'dep_ok': '{paquete}: instalado',
        'dep_fallo': '{paquete}: FALLÓ ({motivo})',
        'dep_error_excepcion': '{paquete}: no se pudo ejecutar pip ({error})',
        'dep_codigo_salida': 'código de salida {codigo}',
        'dep_modulo_desconocido': 'módulo sin dependencias registradas: {mod}',
        'vendor_mp_cabecera': f'  {"fichero (MediaPipe Tasks Vision)":36} {"falta":8} {"tamaño":>8}',
        'vendor_mp_pie': ('No son paquetes de pip — no van en el repositorio de git (~{total} MB en total si '
                           'faltan todos). Se bajan aparte con: {comando} — licencia Apache License 2.0 '
                           '(proyecto MediaPipe, Google); se escribe una copia en '
                           'abyss/vendor/mp/LICENSE-mediapipe.txt.'),
        'vendor_mp_nada_que_bajar': 'nada que descargar: ya estaban todos los ficheros de MediaPipe Tasks Vision',
        'modelo_sin_url': 'sin dato: no se pudo leer URL_MODELO de abyss/fondo.py',
        'modelo_ya_esta': 'nada que descargar: el modelo ya estaba ({bytes} bytes)',
        'modelo_previa': 'se va a descargar el modelo de recorte de fondo:\n  de:    {url}\n  a:     {destino}\n  pesa:  unos 4,4 MB',
        'modelo_licencia': 'licencias: el fichero .onnx lo distribuye rembg (MIT) y la red que lleva dentro es U^2-Net (Apache-2.0). Las dos, enteras, en abyss/vendor/modelos/LICENSE-u2netp.txt',
        'modelo_bajado': 'modelo descargado: {bytes} bytes (medidos en disco, no estimados)',
        'vendor_mp_previa_cabecera': 'Se va a descargar (MediaPipe Tasks Vision, para el visor 3D — ~{total} MB en total):',
        'vendor_mp_previa_fila': '  {url} -> abyss/vendor/mp/{destino} ({tam})',
        'vendor_mp_licencia_aviso': ('Licencia: Apache License 2.0 (proyecto MediaPipe, Google) — se escribe una '
                                      'copia en abyss/vendor/mp/LICENSE-mediapipe.txt junto con la descarga.'),
        'vendor_mp_ok': '{fichero}: descargado ({bytes} bytes)',
        'vendor_mp_fallo': '{fichero}: FALLÓ ({motivo})',
        'vendor_mp_sin_red': ('sin red: no se pudo conectar con {url} ({motivo}); se para aquí, sin intentar el '
                               'resto — vuelve a intentarlo con conexión'),
        'vendor_mp_licencia_escrita': 'licencia escrita en abyss/vendor/mp/LICENSE-mediapipe.txt',
        'uso': (
            "Uso:\n"
            "  python instalar.py --listar\n"
            "  python instalar.py --instalar mod1,mod2 [--telegram-token T --telegram-chat ID]\n"
            "  python instalar.py --desinstalar mod1[,mod2] [--borrar-datos] [--sin-preguntar]\n"
            "  python instalar.py --dependencias\n"
            "  python instalar.py --instalar-dependencias [mod1,mod2]\n"
            "  python instalar.py --manos                     (baja MediaPipe Tasks Vision para el visor 3D)\n"
            "  python instalar.py --sin-ventana                (equivale a --listar)\n"
            "  python instalar.py                              (ventana Tk; sin entorno gráfico, --listar)\n"
            "Comunes: --settings <ruta>  --python <exe>  --proyecto <cwd>  --skills-dir <ruta>  --idioma es|en\n"
            "  (--skills-dir: dónde copiar una skill como \"esceptico\"; por defecto ~/.claude/skills)\n"
            "  (--idioma: es|en; por defecto, el del sistema — si no empieza por \"es\", inglés)\n"),
        'ventana_titulo': 'Abyss · instalador',
        'ventana_proyecto_label': 'proyecto: {proj}',
        'ventana_proyecto_sin_resolver': '(sin resolver — usa --proyecto <cwd>)',
        'boton_instalar': 'Instalar',
        'boton_desinstalar': 'Desinstalar',
        'boton_dependencias': 'Dependencias...',
        'boton_claves': 'Claves...',
        'claves_titulo': 'Claves opcionales',
        'claves_intro': ('Todo funciona sin ninguna. Lo que necesita clave lo dice y no '
                         'toca la red. Se guardan SOLO en tu carpeta de memoria; nunca '
                         'viajan con el paquete.'),
        'claves_puesta': 'puesta',
        'claves_vacia': 'vacía',
        'claves_dejar': '(déjalo en blanco para no tocarla)',
        'claves_guardar': 'Guardar',
        'claves_cancelar': 'Cancelar',
        'claves_guardadas': 'Guardadas %d clave(s) en %s',
        'claves_sin_cambios': 'No has escrito ninguna: no se ha tocado nada.',
        'claves_sin_proyecto': 'Sin proyecto resuelto: no sé dónde guardarlas.',
        'boton_cerrar': 'Cerrar',
        'titulo_abyss': 'Abyss',
        'titulo_aviso': 'Abyss · aviso',
        'titulo_telegram': 'Abyss · Telegram',
        'msg_sin_modulos': 'No hay módulos marcados.',
        'msg_confirmar_permisos': ('El módulo «permisos» deja que el propio asistente edite settings.json '
                                    'sin preguntar cada vez. ¿Seguro que quieres activarlo?'),
        'dlg_telegram_token': 'Token del bot:',
        'dlg_telegram_chat': 'Chat id:',
        'msg_telegram_incompleto': 'Sin token/chat id no se instala telegram.',
        'msg_sin_proyecto': 'No se pudo resolver el proyecto (mem). Cierra y ejecuta con --proyecto <cwd>.',
        'msg_confirmar_borrar_datos': ('¿Borrar también sesiones/relojes/etc. generados por abyss?\n'
                                        '(recomendado: NO — son memoria tuya)'),
        'msg_confirmar_instalar_dependencias': '¿Instalar ahora los paquetes que faltan? Se instalan UNO a UNO con pip.',
        'msg_nada_que_hacer': 'nada que hacer',
    },
    'en': {
        'settings_prefix': 'settings: ',
        'no_existe_aun': '  (does not exist yet)',
        'estado_instalado': 'installed',
        'estado_no_instalado': 'not installed',
        'estado_sin_gancho': 'no hook of its own',
        'listar_detalle_nota': ('  (details omitted here: they carry untranslated Spanish control '
                                 'vocabulary; run --idioma es --listar, or see README.en.md)'),
        'apagado_como': 'off by default; to turn it on:',
        'toca_label': 'touches:',
        'aviso_label': 'note:',
        'falta_valor': 'missing value for {bandera}',
        'argumento_no_reconocido': 'unrecognized argument: {bandera}',
        'modulo_desconocido': '? unknown module: {id}',
        'telegram_faltan_credenciales': 'telegram: missing credentials (--telegram-token/--telegram-chat); not installed',
        'skill_copiada': '{mid}: skill copied to {destino}',
        'skill_retirada': '{mid}: skill removed from {destino}',
        'skill_no_tocada': '{mid}: {destino} does not carry the abyss mark — left untouched',
        'plantilla_sembrada': '{mid}: seeded mem/{plantilla}',
        'modulo_instalado': '{mid}: installed',
        'modulo_ya_instalado': '{mid}: was already installed',
        'modulo_desinstalado': '{mid}: uninstalled',
        'taller_mensaje': (
            '{mid}: nothing is installed and no process is started. To run it yourself: '
            'python "{script}" [--puerto 7860] [--modelo Lykon/dreamshaper-8] [--cache-dir <path>] '
            '[--dispositivo auto|cuda|mps|cpu] [--pasos 20] — needs "pip install diffusers '
            'transformers accelerate" and "{torch_cmd}". The model downloads from Hugging Face on '
            'first use; on CPU, each image takes minutes, not seconds.'),
        'datos_borrados_lista': 'generated data deleted: {lista}',
        'datos_borrados_nada': '(there was nothing)',
        'error_proyecto': 'instalar: could not resolve the project (pass --proyecto <cwd> or set ABYSS_PROYECTO)',
        'sin_ventana_fallback': 'instalar: no window available ({tipo}: {error}); showing --listar instead\n',
        'pregunta_borrar_datos': 'Also delete sessions/clocks/etc. generated by abyss? (y/N): ',
        'telegram_pedir_token': 'Abyss · Telegram: bot token: ',
        'telegram_pedir_chat': 'Abyss · Telegram: chat id: ',
        'dep_cabecera': f'  {"module":12} {"missing":8} {"pip package":16}{"":16} {"approx. size":10} what for',
        'dep_falta_si': 'MISSING',
        'dep_falta_no': 'ok',
        'sin_dato': 'no data',
        'marca_opcional': ' (optional)',
        'marca_alternativa_cubierta': ' (covered)',
        'no_instalable_cabecera': 'What this installer CANNOT put in place (needs the system package manager):',
        'ocr_windows': '  OCR: on Windows the text-recognition engine ships with the OS (WinRT) — nothing to install.',
        'ocr_linux': '  OCR: install the tesseract binary with your package manager: sudo apt install tesseract-ocr tesseract-ocr-spa',
        'ocr_macos': '  OCR: install the tesseract binary with Homebrew: brew install tesseract tesseract-lang',
        'taller_gpu': '  taller.py (torch + diffusers): they weigh gigabytes and torch depends on the card — this '
                      'installer does not install them. Command detected for this machine: {comando}',
        'dep_nada_que_instalar': 'nothing to install: everything was already present',
        'dep_comando_antes': 'command: {comando}',
        'dep_ok': '{paquete}: installed',
        'dep_fallo': '{paquete}: FAILED ({motivo})',
        'dep_error_excepcion': '{paquete}: could not run pip ({error})',
        'dep_codigo_salida': 'exit code {codigo}',
        'dep_modulo_desconocido': 'module with no registered dependencies: {mod}',
        'vendor_mp_cabecera': f'  {"file (MediaPipe Tasks Vision)":36} {"missing":8} {"size":>8}',
        'vendor_mp_pie': ('Not pip packages — they do not go in the git repository (~{total} MB total if all '
                           'are missing). Fetch them separately with: {comando} — Apache License 2.0 '
                           '(MediaPipe project, Google); a copy is written to '
                           'abyss/vendor/mp/LICENSE-mediapipe.txt.'),
        'vendor_mp_nada_que_bajar': 'nothing to download: every MediaPipe Tasks Vision file was already there',
        'modelo_sin_url': "no data: couldn't read URL_MODELO from abyss/fondo.py",
        'modelo_ya_esta': 'nothing to download: the model was already there ({bytes} bytes)',
        'modelo_previa': 'about to download the background-removal model:\n  from: {url}\n  to:   {destino}\n  size: about 4.4 MB',
        'modelo_licencia': 'licences: the .onnx file is distributed by rembg (MIT) and the network inside it is U^2-Net (Apache-2.0). Both in full in abyss/vendor/modelos/LICENSE-u2netp.txt',
        'modelo_bajado': 'model downloaded: {bytes} bytes (measured on disk, not estimated)',
        'vendor_mp_previa_cabecera': 'About to download (MediaPipe Tasks Vision, for the 3D viewer — ~{total} MB total):',
        'vendor_mp_previa_fila': '  {url} -> abyss/vendor/mp/{destino} ({tam})',
        'vendor_mp_licencia_aviso': ('License: Apache License 2.0 (MediaPipe project, Google) — a copy is '
                                      'written to abyss/vendor/mp/LICENSE-mediapipe.txt together with the '
                                      'download.'),
        'vendor_mp_ok': '{fichero}: downloaded ({bytes} bytes)',
        'vendor_mp_fallo': '{fichero}: FAILED ({motivo})',
        'vendor_mp_sin_red': ('no network: could not connect to {url} ({motivo}); stopping here, the rest was '
                               'not attempted — try again once you have a connection'),
        'vendor_mp_licencia_escrita': 'license written to abyss/vendor/mp/LICENSE-mediapipe.txt',
        'uso': (
            "Usage:\n"
            "  python instalar.py --listar\n"
            "  python instalar.py --instalar mod1,mod2 [--telegram-token T --telegram-chat ID]\n"
            "  python instalar.py --desinstalar mod1[,mod2] [--borrar-datos] [--sin-preguntar]\n"
            "  python instalar.py --dependencias\n"
            "  python instalar.py --instalar-dependencias [mod1,mod2]\n"
            "  python instalar.py --manos                     (downloads MediaPipe Tasks Vision for the 3D viewer)\n"
            "  python instalar.py --sin-ventana                (same as --listar)\n"
            "  python instalar.py                              (Tk window; no display -> --listar)\n"
            "Common: --settings <path>  --python <exe>  --proyecto <cwd>  --skills-dir <path>  --idioma es|en\n"
            "  (--skills-dir: where to copy a skill like \"esceptico\"; default ~/.claude/skills)\n"
            "  (--idioma: es|en; default is the system's — anything not starting with \"es\" becomes English)\n"),
        'ventana_titulo': 'Abyss · installer',
        'ventana_proyecto_label': 'project: {proj}',
        'ventana_proyecto_sin_resolver': '(unresolved — use --proyecto <cwd>)',
        'boton_instalar': 'Install',
        'boton_desinstalar': 'Uninstall',
        'boton_dependencias': 'Dependencies...',
        'boton_claves': 'Keys...',
        'claves_titulo': 'Optional keys',
        'claves_intro': ('Everything works without any of them. What needs a key says so '
                         'and never touches the network. They are stored ONLY in your '
                         'memory folder; they never travel with the package.'),
        'claves_puesta': 'set',
        'claves_vacia': 'empty',
        'claves_dejar': '(leave blank to keep it)',
        'claves_guardar': 'Save',
        'claves_cancelar': 'Cancel',
        'claves_guardadas': 'Saved %d key(s) in %s',
        'claves_sin_cambios': "You didn't type any: nothing was touched.",
        'claves_sin_proyecto': "No project resolved: I don't know where to save them.",
        'boton_cerrar': 'Close',
        'titulo_abyss': 'Abyss',
        'titulo_aviso': 'Abyss · notice',
        'titulo_telegram': 'Abyss · Telegram',
        'msg_sin_modulos': 'No modules are checked.',
        'msg_confirmar_permisos': ('The "permisos" module lets the assistant itself edit settings.json without '
                                    'asking each time. Are you sure you want to enable it?'),
        'dlg_telegram_token': 'Bot token:',
        'dlg_telegram_chat': 'Chat id:',
        'msg_telegram_incompleto': 'Without a token/chat id, telegram is not installed.',
        'msg_sin_proyecto': 'Could not resolve the project (mem). Close and run again with --proyecto <cwd>.',
        'msg_confirmar_borrar_datos': ('Also delete sessions/clocks/etc. generated by abyss?\n'
                                        '(recommended: NO — that is your own memory)'),
        'msg_confirmar_instalar_dependencias': 'Install the missing packages now? They install ONE at a time with pip.',
        'msg_nada_que_hacer': 'nothing to do',
    },
}
_ETIQUETA_ESTADO_CLAVE = {True: 'estado_instalado', False: 'estado_no_instalado', None: 'estado_sin_gancho'}


def _texto(idioma, clave, **fmt):
    """Único punto de lectura de `TEXTOS` (T5.2): `idioma` no reconocido, o clave
    que faltara en él, caen al castellano antes que reventar el instalador por
    un texto — fail-closed también aquí (preferible un idioma "que no toca" a
    ningún mensaje)."""
    tabla = TEXTOS.get(idioma) or TEXTOS['es']
    plantilla = tabla.get(clave, TEXTOS['es'].get(clave, clave))
    return plantilla.format(**fmt) if fmt else plantilla


def _idioma_sistema():
    """`'es'` si el idioma del sistema empieza por "es"; si no, o si no se puede
    determinar, `'en'` (T5.2). `locale.getdefaultlocale()` está deprecado desde
    Python 3.11 (aviso silenciado a propósito: es solo una detección de
    conveniencia, nunca debe imprimir ruido por su cuenta) y podría desaparecer
    en una versión futura de Python; si falla o no da nada, se cae a
    `LC_ALL`/`LANG`/`LC_MESSAGES` del entorno (convención POSIX) antes de asumir
    inglés."""
    codigo = None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            codigo = locale.getdefaultlocale()[0]
    except Exception:
        codigo = None
    if not codigo:
        codigo = os.environ.get('LC_ALL') or os.environ.get('LANG') or os.environ.get('LC_MESSAGES')
    return 'es' if codigo and str(codigo).lower().startswith('es') else 'en'


# ---------------------------------------------------------------------------------
# JSON con backup: leer/escribir settings.json y el manifiesto siempre por aquí.
# ---------------------------------------------------------------------------------
def _leer_json(ruta):
    if not os.path.exists(ruta):
        return {}
    try:
        with open(ruta, encoding='utf-8') as fh:
            return json.loads(fh.read() or '{}')
    except Exception as e:
        sys.exit(f'instalar: {ruta} no es JSON válido ({e}); arréglalo a mano antes de instalar/desinstalar')


def _escribir_json(ruta, datos):
    """Escribe `datos` como JSON con indent=2. `newline='\\n'` a propósito
    (fallo "roza" medido 7-sep): sin esto, `open(..., 'w')` en Windows traduce
    cada `\\n` del texto a `\\r\\n` al escribir, así que un `settings.json` de
    partida en LF (lo que escriben tanto los editores como el propio Claude
    Code) volvía en CRLF tras instalar/desinstalar — mismo CONTENIDO (el JSON
    parseado es idéntico) pero el fichero ENTERO aparecía como modificado en
    cualquier diff o git, aunque nada del usuario hubiera cambiado. Con
    `newline='\\n'` el caso común (LF de entrada) vuelve BYTE A BYTE, y el
    aviso del README pasa a cubrir solo lo que de verdad no se puede
    garantizar (otro indent, otro orden de claves)."""
    carpeta = os.path.dirname(os.path.abspath(ruta))
    if carpeta:
        os.makedirs(carpeta, exist_ok=True)
    texto = json.dumps(datos, ensure_ascii=False, indent=2) + '\n'
    tmp = ruta + '.tmp-abyss'
    with open(tmp, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(texto)
    os.replace(tmp, ruta)


def _copia_fechada(ruta):
    """Copia `ruta` a `ruta.abyss-AAAAMMDD-HHMMSS[-N].bak` si existe. Se hace SIEMPRE
    antes de escribir settings.json, tanto al instalar como al desinstalar.

    Medido 6-sep: instalar→desinstalar seguidos (mismo segundo) dejaba UNA sola
    copia, porque el nombre ya estaba tomado y la segunda llamada se saltaba entera
    — la copia previa al desinstalado (justo la red de seguridad que hace falta si
    el desinstalado sale mal) desaparecía en silencio. Ahora, si el nombre ya existe,
    se añade un sufijo incremental en vez de saltarse la copia."""
    if not os.path.exists(ruta):
        return None
    base = f'{ruta}.abyss-{time.strftime("%Y%m%d-%H%M%S")}'
    destino = base + '.bak'
    n = 1
    while os.path.exists(destino):
        destino = f'{base}-{n}.bak'
        n += 1
    shutil.copy2(ruta, destino)
    return destino


def _ruta_manifiesto(mem):
    return os.path.join(mem, MANIFIESTO_NOMBRE)


def _cargar_manifiesto(mem):
    m = _leer_json(_ruta_manifiesto(mem))
    m.setdefault('modulos_instalados', [])
    m.setdefault('detalle', {})
    return m


def _guardar_manifiesto(mem, datos):
    _escribir_json(_ruta_manifiesto(mem), datos)


def _ruta_config_codigo():
    return os.path.join(PKG, 'config.json')


def _escribir_config_codigo(python_exe):
    """El ÚNICO fichero que el instalador escribe en la carpeta del CÓDIGO (nunca en
    `mem`, nunca en el repo del usuario, §1/§4 de ESPECIFICACION.md): qué `python` se
    usó la última vez que se instaló algo. No hace falta para que los ganchos
    funcionen (cada uno lleva su propia ruta absoluta de `python` en `command`); es
    solo un registro para quien inspeccione esta instalación del código."""
    ruta = _ruta_config_codigo()
    datos = _leer_json(ruta)
    datos['python'] = python_exe
    datos['actualizado'] = time.strftime('%Y-%m-%dT%H:%M:%S')
    _escribir_json(ruta, datos)


# ---------------------------------------------------------------------------------
# Skills copiadas (T2.6, `esceptico`): sin PyYAML (biblioteca estándar solo), así que
# el frontmatter no se parsea de verdad — solo se extrae el BLOQUE entre las dos
# primeras líneas `---` y se busca la marca dentro, literal. Basta para lo que este
# paquete necesita: escribir la marca al copiar, y comprobarla al desinstalar.
# ---------------------------------------------------------------------------------
def _frontmatter_bloque(ruta_skill_md):
    """Texto entre las dos primeras líneas `---` de un `SKILL.md`, o `None` si el
    fichero no existe o no tiene esa forma (primera línea `---`, y otra `---` más
    abajo) — nunca revienta si la skill de destino es rara o no es nuestra."""
    try:
        with open(ruta_skill_md, encoding='utf-8') as fh:
            texto = fh.read()
    except Exception:
        return None
    lineas = texto.splitlines()
    if not lineas or lineas[0].strip() != '---':
        return None
    for i in range(1, len(lineas)):
        if lineas[i].strip() == '---':
            return '\n'.join(lineas[1:i])
    return None


def _skill_es_nuestra(ruta_skill_md):
    """True solo si el `SKILL.md` de destino lleva, en su frontmatter, la línea
    EXACTA `MARCA_SKILL_LINEA` — la misma que escribe `_copiar_skill()` al instalar.
    Una skill con el mismo nombre pero de otro origen (el usuario ya tenía su propio
    `esceptico`) nunca lleva esa línea, y el desinstalador la deja intacta."""
    bloque = _frontmatter_bloque(ruta_skill_md)
    return bool(bloque) and any(l.strip() == MARCA_SKILL_LINEA for l in bloque.splitlines())


def _copiar_skill(carpeta_skill, skills_dir):
    """Copia `skills/<carpeta_skill>/` de este repo (que YA lleva `MARCA_SKILL_LINEA`
    en el frontmatter de su `SKILL.md` — es lo que la distingue de una skill que el
    usuario tuviera puesta por su cuenta con el mismo nombre) a
    `<skills_dir>/<carpeta_skill>/`. Devuelve la ruta de destino. Si el destino ya
    existe (una instalación previa, nuestra o ajena), se sustituye entero — instalar
    dos veces debe dejar la copia buena, no dos mezcladas."""
    origen = os.path.join(RAIZ_SKILLS, carpeta_skill)
    destino = os.path.join(skills_dir, carpeta_skill)
    os.makedirs(skills_dir, exist_ok=True)
    if os.path.isdir(destino):
        shutil.rmtree(destino)
    shutil.copytree(origen, destino)
    return destino


# ---------------------------------------------------------------------------------
# Ganchos: añadir sin perder los ajenos, quitar solo los nuestros por firma exacta
# (ruta del guion + su bandera, o la ruta del .ps1 de telegram).
# ---------------------------------------------------------------------------------
def _entradas(lista_de_grupos):
    for grupo in lista_de_grupos or []:
        for h in (grupo.get('hooks') or []):
            yield h


def _quotar(s):
    """Entrecomilla `s` si lleva un espacio (rutas con espacios: `C:\\Program Files\\...`).
    Sin comillas, esa ruta partiría en dos "palabras" de la línea de comandos."""
    s = str(s)
    return '"' + s.replace('"', '\\"') + '"' if (' ' in s or '\t' in s or s == '') else s


def _construir_command(ejecutable, args):
    """Une `ejecutable` + `args` en UNA sola cadena para la clave `command`.

    Medido 6-sep: el esquema REAL de un gancho de `settings.json` de Claude Code es
    `{type, command, timeout}` con la línea de órdenes ENTERA dentro de `command` —
    no existe un campo `args` aparte (así lo escribe ya `hooks/hooks.json:8`, el
    gancho del propio plugin). La versión anterior de este instalador escribía
    `{"command": "<python.exe>", "args": ["<script>", "--bandera"]}`, que Claude Code
    no sabe interpretar: ejecutaría `python.exe` pelado, sin guion."""
    return ' '.join(_quotar(a) for a in ([ejecutable] + list(args)))


def _partes(entrada):
    """La cadena `command` de esta entrada, normalizada — TODA la línea de órdenes
    vive ahí (§ arriba), así que buscar una ruta o una bandera es buscarlas dentro
    de esta única cadena, no en una lista de `args` que ya no existe."""
    return os.path.normcase(str(entrada.get('command', '')))


def _coincide(entrada, ruta, bandera=None):
    cmd = _partes(entrada)
    if os.path.normcase(str(ruta)) not in cmd:
        return False
    return bandera is None or os.path.normcase(str(bandera)) in cmd


def _hook_presente(settings, evento, ruta, bandera=None):
    bloque = (settings.get('hooks') or {}).get(evento) or []
    return any(_coincide(h, ruta, bandera) for h in _entradas(bloque))


def _anadir_hook(settings, evento, command, timeout, ruta, bandera=None):
    """Añade una entrada de gancho NUEVA al final de la lista de `evento`, sin tocar
    las que ya hubiera. Idempotente: si ya hay una con esta firma (`ruta`+`bandera`),
    no hace nada. Devuelve True si añadió algo. `command` es la línea de órdenes
    ENTERA ya construida (ver `_construir_command`), tal como exige el esquema real
    de settings.json — no hay clave `args` aparte, ni `statusMessage` (no está en el
    esquema documentado de un gancho `command`; ver comentario junto a `MODULOS`)."""
    if _hook_presente(settings, evento, ruta, bandera):
        return False
    bloque = settings.setdefault('hooks', {})
    lista = bloque.setdefault(evento, [])
    lista.append({'hooks': [{'type': 'command', 'command': command, 'timeout': timeout}]})
    return True


def _quitar_hook(settings, evento, ruta, bandera=None):
    """Quita SOLO las entradas de `evento` cuya firma sea `ruta`+`bandera`; conserva
    todo lo demás. Si el evento se queda vacío, se borra la clave; si `hooks` entero
    se queda vacío, también. Devuelve True si quitó algo."""
    bloque = settings.get('hooks')
    if not bloque or evento not in bloque:
        return False
    antes = bloque[evento]
    despues = [g for g in antes if not any(_coincide(h, ruta, bandera) for h in (g.get('hooks') or []))]
    if len(despues) == len(antes):
        return False
    if despues:
        bloque[evento] = despues
    else:
        del bloque[evento]
        if not bloque:
            del settings['hooks']
    return True


def _sembrar_plantilla(nombre_archivo, mem):
    """Copia `plantillas/<nombre_archivo>` a `mem/<nombre_archivo>` SOLO si el
    destino no existe ya (nunca pisa datos del usuario)."""
    origen = os.path.join(PLANTILLAS, nombre_archivo)
    destino = os.path.join(mem, nombre_archivo)
    if os.path.exists(destino) or not os.path.exists(origen):
        return False
    shutil.copy2(origen, destino)
    return True


def _escribir_ps1_telegram(mem, token, chat_id):
    """Lee `abyss/notify_telegram.ps1.plantilla`, sustituye `<TELEGRAM_BOT_TOKEN>`
    y `<CHAT_ID>`, y escribe la copia rellena en `mem/notify_telegram.ps1` — FUERA
    del repo, nunca en el código (§2.5 / ESPECIFICACION.md)."""
    plantilla_ruta = os.path.join(PKG, 'notify_telegram.ps1.plantilla')
    with open(plantilla_ruta, encoding='utf-8') as fh:
        texto = fh.read()
    texto = texto.replace('<TELEGRAM_BOT_TOKEN>', token).replace('<CHAT_ID>', str(chat_id))
    destino = os.path.join(mem, 'notify_telegram.ps1')
    with open(destino, 'w', encoding='utf-8') as fh:
        fh.write(texto)
    return destino


def _powershell():
    return shutil.which('powershell') or shutil.which('pwsh') or 'powershell'


# ---------------------------------------------------------------------------------
# Instalar / desinstalar. La ventana Tk y la CLI llaman exactamente a estas dos
# funciones: no hay una segunda implementación de la lógica en ningún sitio.
# ---------------------------------------------------------------------------------
def instalar(ids, *, settings_ruta, python_exe, mem, telegram=None, skills_dir=None, idioma='es'):
    """Instala los módulos `ids` (lista de str) fusionando en `settings_ruta`.
    `telegram` es `(token, chat_id)` o None/incompleto (entonces ese módulo se
    salta con aviso). `skills_dir` es donde copiar una skill como `esceptico`
    (por defecto `SKILLS_DIR_POR_DEFECTO`, ~/.claude/skills). `idioma` (T5.2,
    por defecto 'es' — NUNCA el del sistema aquí: lo resuelve la CLI/ventana y
    lo pasa ya decidido, para que llamar a esta función directamente sea
    determinista) decide en qué idioma salen los mensajes devueltos. Devuelve la
    lista de mensajes (str) para mostrar al usuario."""
    skills_dir = skills_dir or SKILLS_DIR_POR_DEFECTO
    mensajes = [_texto(idioma, 'modulo_desconocido', id=i) for i in ids if i not in MODULOS_POR_ID]
    ids = [i for i in ids if i in MODULOS_POR_ID]
    if not ids:
        return mensajes

    settings = _leer_json(settings_ruta)
    _copia_fechada(settings_ruta)
    manifiesto = _cargar_manifiesto(mem)
    instalados = set(manifiesto['modulos_instalados'])
    tocado = False

    for mid in ids:
        mod = MODULOS_POR_ID[mid]
        ya = mid in instalados
        cambiado = False

        if mod.get('hooks'):
            hooks_manifest = manifiesto['detalle'].setdefault(mid, {}).setdefault('hooks', [])
        for evento, args, timeout in mod.get('hooks', ()):
            script = _script(mod['script'])
            bandera = args[0] if args else None
            command = _construir_command(python_exe, [script] + list(args))
            if _anadir_hook(settings, evento, command, timeout, script, bandera):
                cambiado = True
            # Firma apuntada SIEMPRE (aunque ya estuviera puesta): es lo que permite
            # a `desinstalar()` encontrar este gancho aunque `abyss/` se mueva o
            # se renombre entre medias — desinstalar no debe depender de dónde esté
            # el código AHORA, sino de dónde estaba cuando se instaló.
            firma = {'evento': evento, 'ruta': script, 'bandera': bandera}
            if firma not in hooks_manifest:
                hooks_manifest.append(firma)

        for clave, valor in (mod.get('claves') or {}).items():
            previas = manifiesto['detalle'].setdefault(mid, {}).setdefault('previas', {})
            if clave not in previas:
                previas[clave] = {'existia': clave in settings, 'valor': settings.get(clave)}
            if settings.get(clave) != valor:
                settings[clave] = valor
                cambiado = True

        if mod.get('especial') == 'permisos':
            regla = f'Edit({os.path.abspath(settings_ruta)})'
            detalle = manifiesto['detalle'].setdefault('permisos', {})
            if 'regla' not in detalle:
                detalle['creamos_bloque'] = 'permissions' not in settings
                detalle['creamos_allow'] = 'allow' not in (settings.get('permissions') or {})
                detalle['regla'] = regla
            bloque_p = settings.setdefault('permissions', {})
            allow = bloque_p.setdefault('allow', [])
            if regla not in allow:
                allow.append(regla)
                cambiado = True

        if mod.get('especial') == 'telegram':
            token, chat = telegram if telegram else (None, None)
            if not (token and chat):
                mensajes.append(_texto(idioma, 'telegram_faltan_credenciales'))
                continue
            ps1 = _escribir_ps1_telegram(mem, token, chat)
            command = _construir_command(_powershell(), ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ps1])
            if _anadir_hook(settings, 'Notification', command, 20, ps1):
                cambiado = True
            manifiesto['detalle'].setdefault('telegram', {})['ps1'] = ps1

        if mod.get('especial') == 'skill':
            destino = _copiar_skill(mod['carpeta_skill'], skills_dir)
            manifiesto['detalle'].setdefault(mid, {})['skill_destino'] = destino
            mensajes.append(_texto(idioma, 'skill_copiada', mid=mid, destino=destino))

        if mod.get('especial') == 'taller':
            ruta_script = _script(mod['script'])
            # T5.1: comando EXACTO detectado (nvidia-smi), no una condicional
            # genérica ("si tienes GPU NVIDIA...") — nunca se instala desde aquí.
            mensajes.append(_texto(idioma, 'taller_mensaje', mid=mid, script=ruta_script,
                                    torch_cmd=_comando_taller_torch()))

        if mod.get('plantilla') and _sembrar_plantilla(mod['plantilla'], mem):
            mensajes.append(_texto(idioma, 'plantilla_sembrada', mid=mid, plantilla=mod['plantilla']))

        instalados.add(mid)
        tocado = tocado or cambiado
        clave_estado = 'modulo_instalado' if (cambiado or not ya) else 'modulo_ya_instalado'
        mensajes.append(_texto(idioma, clave_estado, mid=mid))

    manifiesto['modulos_instalados'] = sorted(instalados)
    manifiesto['python'] = python_exe
    manifiesto['settings_ruta'] = os.path.abspath(settings_ruta)
    manifiesto['actualizado'] = time.strftime('%Y-%m-%dT%H:%M:%S')
    if tocado:
        _escribir_json(settings_ruta, settings)
    _guardar_manifiesto(mem, manifiesto)
    _escribir_config_codigo(python_exe)
    return mensajes


def desinstalar(ids, *, settings_ruta, mem, borrar_datos=False, skills_dir=None, idioma='es'):
    """Desinstala los módulos `ids`: quita solo las entradas cuyo comando apunta a
    nuestro código (o al `.ps1` de telegram que escribimos nosotros), retira una
    skill copiada (`esceptico`) SOLO si lleva nuestra marca, y restaura las claves
    de preferencia/permisos a su valor previo. Si `borrar_datos`, además limpia
    `DATOS_GENERADOS` de `mem` (nunca MEMORY.md ni las fichas). `idioma='es'`
    (T5.2): igual que en `instalar()`, nunca el del sistema aquí — lo decide
    quien llama."""
    skills_dir = skills_dir or SKILLS_DIR_POR_DEFECTO
    mensajes = []
    settings = _leer_json(settings_ruta)
    manifiesto = _cargar_manifiesto(mem)
    instalados = set(manifiesto['modulos_instalados'])
    tocado = False

    for mid in ids:
        mod = MODULOS_POR_ID.get(mid)
        if not mod:
            mensajes.append(_texto(idioma, 'modulo_desconocido', id=mid))
            continue

        detalle_mid = manifiesto['detalle'].get(mid, {})
        hooks_registrados = detalle_mid.get('hooks')
        if hooks_registrados:
            # Firma tal como quedó apuntada AL INSTALAR: sigue siendo correcta aunque
            # `abyss/` se haya movido o renombrado desde entonces.
            objetivos = [(h['evento'], h['ruta'], h.get('bandera')) for h in hooks_registrados]
        else:
            # Manifiesto de antes de que se apuntaran firmas (o módulo sin instalar
            # por esta vía): recalcula desde el código ACTUAL — peor que la firma
            # real si el código se movió entretanto, pero mejor que no quitar nada.
            objetivos = [(evento, _script(mod['script']), (args[0] if args else None))
                         for evento, args, timeout in mod.get('hooks', ())]
        for evento, ruta, bandera in objetivos:
            if _quitar_hook(settings, evento, ruta, bandera):
                tocado = True
        detalle_mid.pop('hooks', None)  # ya desinstalado: la próxima instalación apunta firmas nuevas

        for clave in (mod.get('claves') or {}):
            previas = manifiesto['detalle'].get(mid, {}).get('previas', {})
            prev = previas.get(clave)
            if prev is not None:
                if prev['existia']:
                    settings[clave] = prev['valor']
                else:
                    settings.pop(clave, None)
                tocado = True
                del previas[clave]  # ya restaurado: que la próxima instalación capture el valor REAL de ese momento

        if mod.get('especial') == 'permisos':
            detalle = manifiesto['detalle'].get('permisos') or {}
            regla = detalle.get('regla') or f'Edit({os.path.abspath(settings_ruta)})'
            bloque_p = settings.get('permissions')
            if bloque_p and regla in (bloque_p.get('allow') or []):
                bloque_p['allow'].remove(regla)
                tocado = True
                if not bloque_p['allow'] and detalle.get('creamos_allow'):
                    del bloque_p['allow']
                if not bloque_p and detalle.get('creamos_bloque'):
                    settings.pop('permissions', None)
            manifiesto['detalle'].pop('permisos', None)  # idem: recapturar en la próxima instalación

        if mod.get('especial') == 'telegram':
            ps1 = (manifiesto['detalle'].get('telegram') or {}).get('ps1')
            if ps1 and _quitar_hook(settings, 'Notification', ps1):
                tocado = True
            if ps1 and os.path.exists(ps1):
                os.remove(ps1)  # es un secreto (token) que escribimos nosotros: se va con el módulo
            manifiesto['detalle'].pop('telegram', None)

        if mod.get('especial') == 'skill':
            destino = (manifiesto['detalle'].get(mid) or {}).get('skill_destino') \
                or os.path.join(skills_dir, mod['carpeta_skill'])
            ruta_md = os.path.join(destino, 'SKILL.md')
            if os.path.isdir(destino) and _skill_es_nuestra(ruta_md):
                shutil.rmtree(destino, ignore_errors=True)
                mensajes.append(_texto(idioma, 'skill_retirada', mid=mid, destino=destino))
            elif os.path.isdir(destino):
                mensajes.append(_texto(idioma, 'skill_no_tocada', mid=mid, destino=destino))
            manifiesto['detalle'].pop(mid, None)

        if mod.get('especial') == 'taller':
            manifiesto['detalle'].pop(mid, None)  # nada que restaurar: no tocó settings.json ni claves

        if not mod.get('especial'):  # los especiales ya gestionan su propia entrada arriba
            if detalle_mid:  # `previas` puede seguir ahí (vacío) para módulos con claves: igual que antes
                manifiesto['detalle'][mid] = detalle_mid
            else:
                manifiesto['detalle'].pop(mid, None)

        instalados.discard(mid)
        mensajes.append(_texto(idioma, 'modulo_desinstalado', mid=mid))

    if tocado:
        _copia_fechada(settings_ruta)
        _escribir_json(settings_ruta, settings)
    manifiesto['modulos_instalados'] = sorted(instalados)
    manifiesto['actualizado'] = time.strftime('%Y-%m-%dT%H:%M:%S')
    _guardar_manifiesto(mem, manifiesto)

    if borrar_datos:
        borrados = _borrar_datos_generados(mem)
        lista = ', '.join(borrados) if borrados else _texto(idioma, 'datos_borrados_nada')
        mensajes.append(_texto(idioma, 'datos_borrados_lista', lista=lista))
    return mensajes


def _borrar_datos_generados(mem):
    borrados = []
    for nombre in DATOS_GENERADOS:
        ruta = os.path.join(mem, nombre)
        if os.path.isdir(ruta):
            shutil.rmtree(ruta, ignore_errors=True)
            borrados.append(nombre + '/')
        elif os.path.isfile(ruta):
            os.remove(ruta)
            borrados.append(nombre)
    return borrados


# ---------------------------------------------------------------------------------
# Estado (para --listar y la ventana Tk): ¿tiene este módulo efecto verificable en
# settings.json? True/False si sí; None si no toca settings.json (sin gancho propio).
# ---------------------------------------------------------------------------------
def estado_modulo(settings, mod, settings_ruta=None, skills_dir=None):
    if mod.get('hooks'):
        return all(_hook_presente(settings, ev, _script(mod['script']), (args[0] if args else None))
                   for ev, args, *_ in mod['hooks'])
    if mod.get('claves'):
        return all(settings.get(k) == v for k, v in mod['claves'].items())
    if mod.get('especial') == 'permisos':
        # Comparar contra la regla EXACTA que instala este módulo (no "empieza por
        # Edit( y contiene settings"): si el usuario ya tenía por su cuenta otra
        # regla Edit(...) sobre otro settings.json, no es abyss quien la puso.
        allow = (settings.get('permissions') or {}).get('allow') or []
        if settings_ruta is None:
            return any(str(a).startswith('Edit(') and 'settings' in str(a) for a in allow)
        regla = f'Edit({os.path.abspath(settings_ruta)})'
        return regla in allow
    if mod.get('especial') == 'telegram':
        bloque = (settings.get('hooks') or {}).get('Notification') or []
        return any('notify_telegram.ps1' in os.path.normcase(str(h.get('command', '')))
                   for h in _entradas(bloque))
    if mod.get('especial') == 'skill':
        destino = os.path.join(skills_dir or SKILLS_DIR_POR_DEFECTO, mod['carpeta_skill'])
        return _skill_es_nuestra(os.path.join(destino, 'SKILL.md'))
    return None  # sin gancho propio ni settings.json: exterocepcion, noticias, propiocepcion,
    # ojo, imagen, lector_pdf, mapa_codigo, infografia, parentesis, taller (solo mem/plantilla)


def _campo_localizado(idioma, mod, campo):
    """`mod[campo]` en el idioma pedido, con el mismo criterio que `_linea_localizada`:
    en inglés usa `<campo>_en` si el módulo la declara y, si no, cae al castellano antes
    que dejar el hueco vacío. Antes esto no existía y `--listar --idioma en` ESCONDÍA
    `toca` y `aviso` en vez de traducirlos: quien instalaba en inglés no llegaba a leer
    qué toca cada módulo ni su aviso de coste, que es justo lo que hay que leer antes de
    decidir. Dos pruebas del propio paquete lo cazan (test_instalador_idioma)."""
    if idioma != 'es':
        otro = mod.get(campo + '_en')
        if otro:
            return otro
    return mod.get(campo) or ''


def _linea_localizada(idioma, mod):
    """El texto de una frase de `mod` en el idioma pedido (T5.2), mismo criterio
    que `_para_localizado()`: con `idioma != 'es'` usa `mod['linea_en']` si el
    módulo la declara; si no (fail-closed), cae al castellano de `mod['linea']`
    antes que dejar la fila sin descripción."""
    if idioma != 'es':
        en = mod.get('linea_en')
        if en:
            return en
    return mod['linea']


def _claves(argv, idioma='es'):
    """Qué claves opcionales hay, cuáles tienes puestas y qué desbloquea cada una.

    Las claves NO viajan con el paquete y no van a viajar nunca: distribuir una credencial
    ajena incumple los términos de casi todos estos servicios aunque no cueste dinero, y
    publicarla bajo una licencia abierta es concederle a todo el mundo el derecho a
    redistribuirla — una concesión que ya no se puede retirar. La única que sí viaja es la
    de AI Horde, `0000000000`, porque su propio proyecto la publica para uso anónimo.

    Este comando no pide ni escribe ninguna clave: dice qué hay, qué falta y dónde se saca.
    Rellenarlas es abrir `imagen_config.json` en tu carpeta de memoria.
    """
    import json as _json
    plantilla = os.path.join(RAIZ, 'plantillas', 'imagen_config.json')
    try:
        with open(os.path.abspath(plantilla), encoding='utf-8') as fh:
            base = _json.load(fh)
    except (OSError, ValueError) as e:
        print('sin dato: no puedo leer la plantilla de claves (%s)' % e)
        return
    ayuda = base.get('_ayuda') or {}
    try:
        _proj, mem = _resolver_mem(argv)
    except Exception:
        mem = None
    puesto = {}
    ruta_cfg = os.path.join(mem, 'imagen_config.json') if mem else None
    if ruta_cfg and os.path.isfile(ruta_cfg):
        try:
            with open(ruta_cfg, encoding='utf-8') as fh:
                puesto = _json.load(fh)
        except (OSError, ValueError):
            puesto = {}
    en = idioma != 'es'
    print('claves opcionales' if not en else 'optional keys')
    print(('tu fichero: %s' if not en else 'your file: %s')
          % (ruta_cfg if ruta_cfg else ('sin proyecto' if not en else 'no project')))
    print()
    for campo, info in ayuda.items():
        valor = puesto.get(campo) or base.get(campo) or ''
        # NUNCA se imprime el valor: solo si hay algo o no
        marca = ('puesta' if not en else 'set') if valor else ('vacía' if not en else 'empty')
        print('  %-24s [%s]  %s' % (campo, marca, info.get('desbloquea', '')))
        print('  %-24s     sin ella: %s' % ('', info.get('sin_ella', '')))
        print('  %-24s     dónde: %s' % ('', info.get('donde', '')))
        if info.get('nota'):
            print('  %-24s     ojo: %s' % ('', info['nota']))
        print()
    print('Ninguna clave sale de tu máquina por instalar el paquete, y ninguna viaja dentro de él.'
          if not en else
          'No key leaves your machine by installing the package, and none travels inside it.')


def _listar(settings_ruta, skills_dir=None, idioma='es'):
    """`idioma='es'` (T5.2): con `--idioma en`, la etiqueta de estado, las
    cabeceras y `mod['linea']` (vía `_linea_localizada()`, cayendo al castellano
    si al módulo le faltara `linea_en`) cambian de idioma — y `toca`/`aviso`
    (que sí llevan vocabulario castellano de control, p. ej. «ganchos») se
    OMITEN en inglés en vez de imprimirse a medio traducir; ver el comentario
    junto a `TEXTOS`."""
    settings = _leer_json(settings_ruta)
    existe = os.path.exists(settings_ruta)
    print(_texto(idioma, 'settings_prefix') + str(settings_ruta)
          + ('' if existe else _texto(idioma, 'no_existe_aun')))
    for mod in MODULOS:
        st = estado_modulo(settings, mod, settings_ruta, skills_dir)
        etiqueta = _texto(idioma, _ETIQUETA_ESTADO_CLAVE[st])
        print(f'  {mod["id"]:14} [{etiqueta:16}] {_linea_localizada(idioma, mod)}')
        # El detalle sale en los DOS idiomas. Estaba tras un `if idioma == 'es'`, así que
        # quien instalaba en inglés no llegaba a leer qué toca cada módulo ni su aviso de
        # coste — justo lo que hay que leer antes de decidir. Las dos etiquetas inglesas
        # ya existían sin usarse.
        print(f'  {"":14}   {_texto(idioma, "toca_label")} {_campo_localizado(idioma, mod, "toca")}')
        if mod.get('aviso'):
            print(f'  {"":14}   {_texto(idioma, "aviso_label")} {_campo_localizado(idioma, mod, "aviso")}')
        # Y si viene apagado, el comando literal para encenderlo, ahí mismo.
        if not mod.get('defecto', True):
            print(f'  {"":14}   {_texto(idioma, "apagado_como")} '
                  f'python instalar.py --instalar {mod["id"]}')
    nota = _texto(idioma, 'listar_detalle_nota')
    if nota:
        print(nota)


# ---------------------------------------------------------------------------------
# Resolución de `mem` para el instalador (nunca hay stdin de un gancho aquí: se
# teclea a mano). Si no hay `--proyecto` ni `ABYSS_PROYECTO`, usa el cwd actual.
# ---------------------------------------------------------------------------------
def _resolver_mem(argv):
    argv2 = list(argv)
    if '--proyecto' not in argv2 and not os.environ.get('ABYSS_PROYECTO'):
        argv2 += ['--proyecto', os.getcwd()]
    try:
        return rutas.resolver(argv=argv2, stdin_json={})
    except SystemExit:
        return None, None


def _valor_flag(argv, nombre, defecto=None):
    if nombre in argv:
        i = argv.index(nombre)
        if i + 1 < len(argv):
            return argv[i + 1]
    return defecto


def _lista_flag(argv, nombre):
    v = _valor_flag(argv, nombre)
    return [x.strip() for x in v.split(',') if x.strip()] if v else []


def _lista_flag_opcional(argv, nombre):
    """Como `_lista_flag`, pero para una bandera de `_FLAGS_VALOR_OPCIONAL` (ver
    `_valor_flag_opcional`): `[]` tanto si la bandera no está como si está SIN
    lista detrás (p. ej. `--instalar-dependencias --idioma en` no debe tomar
    "--idioma" como si fuera la lista de módulos)."""
    v = _valor_flag_opcional(argv, nombre)
    return [x.strip() for x in v.split(',') if x.strip()] if v else []


# ---------------------------------------------------------------------------------
# Validación de argv (fallo 6-sep: `--help`, un typo como `--instaler`, o cualquier
# invocación no interactiva con una bandera que __main__ no reconocía, caían de
# largo hasta `_abrir_ventana()` + `mainloop()` — el proceso se quedaba colgado sin
# salida (MEDIDO: `--help` no volvió en 120 s) y encima abría una ventana en el
# escritorio del usuario. Se valida ANTES de decidir qué hacer, para salir con un
# mensaje claro (código 2) en vez de caer a la ventana por descarte.
# ---------------------------------------------------------------------------------
_FLAGS_CON_VALOR = ('--settings', '--python', '--proyecto', '--instalar', '--desinstalar',
                    '--telegram-token', '--telegram-chat', '--skills-dir', '--idioma')
_FLAGS_SIN_VALOR = ('--listar', '--claves', '--sin-ventana', '--borrar-datos', '--sin-preguntar', '-h', '--help',
                    '--dependencias', '--manos', '--modelo')
# T5.1: `--instalar-dependencias` lleva un valor OPCIONAL ("[mod1,mod2]" en el uso:
# sin lista, se comprueban/instalan TODOS los módulos de `DEPENDENCIAS`) — a
# diferencia de `_FLAGS_CON_VALOR`, que siempre exige un valor detrás.
_FLAGS_VALOR_OPCIONAL = ('--instalar-dependencias',)


def _es_bandera(tok):
    return isinstance(tok, str) and (tok.startswith('--') or tok == '-h')


def _uso(idioma='es'):
    return _texto(idioma, 'uso')


def _argumento_no_reconocido(argv, idioma='es'):
    """None si `argv` solo trae banderas conocidas (con su valor detrás cuando lo
    necesitan, u opcional para las de `_FLAGS_VALOR_OPCIONAL`); si no, un mensaje
    (en `idioma`) describiendo la primera que no encaja."""
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in _FLAGS_CON_VALOR:
            if i + 1 >= len(argv):
                return _texto(idioma, 'falta_valor', bandera=a)
            i += 2
            continue
        if a in _FLAGS_VALOR_OPCIONAL:
            if i + 1 < len(argv) and not _es_bandera(argv[i + 1]):
                i += 2
            else:
                i += 1
            continue
        if a in _FLAGS_SIN_VALOR:
            i += 1
            continue
        return _texto(idioma, 'argumento_no_reconocido', bandera=a)
    return None


def _valor_flag_opcional(argv, nombre):
    """Como `_valor_flag`, pero para una bandera de `_FLAGS_VALOR_OPCIONAL`: solo
    toma el siguiente token como valor si existe Y no es otra bandera (`--algo`)
    — así `--instalar-dependencias --idioma en` no se traga `--idioma` como si
    fuera la lista de módulos."""
    if nombre in argv:
        i = argv.index(nombre)
        if i + 1 < len(argv) and not _es_bandera(argv[i + 1]):
            return argv[i + 1]
    return None


def _pedir_telegram_cli(argv, idioma='es'):
    """`(token, chat_id)`: por flags si vienen los dos; si no, se piden por consola
    (salvo que no haya terminal, o se corte con Ctrl+C/EOF: entonces se devuelve lo
    que hubiera por flag, aunque esté incompleto — `instalar()` ya avisa si falta)."""
    token = _valor_flag(argv, '--telegram-token')
    chat = _valor_flag(argv, '--telegram-chat')
    if token and chat:
        return token, chat
    if not sys.stdin.isatty():
        return token, chat
    try:
        token = token or input(_texto(idioma, 'telegram_pedir_token')).strip()
        chat = chat or input(_texto(idioma, 'telegram_pedir_chat')).strip()
    except (EOFError, KeyboardInterrupt):
        pass
    return (token or None), (chat or None)


# ---------------------------------------------------------------------------------
# Ventana Tk: la misma lógica que la CLI (llama a instalar()/desinstalar() de arriba).
# ---------------------------------------------------------------------------------

def _ventana_claves(padre, mem, idioma='es'):
    """Pedir las claves opcionales, una a una, con lo que desbloquea cada una delante.

    Tres reglas, y las tres se ven en el código:
      · NUNCA se muestra el valor de una clave que ya está puesta. Solo si está o no está.
        Una ventana que enseña un secreto es una ventana que lo filtra a la primera captura.
      · Solo se escribe lo que el usuario haya TECLEADO. Un campo en blanco no borra nada:
        es «déjala como estaba», que es lo que espera quien abre esto solo a mirar.
      · Se escribe en la carpeta de memoria del proyecto, jamás en el repositorio.
    """
    import json as _json
    import tkinter as tk
    from tkinter import messagebox
    if not mem:
        messagebox.showinfo(_texto(idioma, 'claves_titulo'),
                            _texto(idioma, 'claves_sin_proyecto'))
        return
    plantilla = os.path.join(RAIZ, 'plantillas', 'imagen_config.json')
    try:
        with open(plantilla, encoding='utf-8') as fh:
            base = _json.load(fh)
    except (OSError, ValueError) as e:
        messagebox.showinfo(_texto(idioma, 'claves_titulo'), 'sin dato: %s' % e)
        return
    ayuda = base.get('_ayuda') or {}
    ruta = os.path.join(mem, 'imagen_config.json')
    actual = {}
    if os.path.isfile(ruta):
        try:
            with open(ruta, encoding='utf-8') as fh:
                actual = _json.load(fh)
        except (OSError, ValueError):
            actual = {}

    v = tk.Toplevel(padre)
    v.title(_texto(idioma, 'claves_titulo'))
    v.configure(bg=C_FONDO)
    v.transient(padre)
    tk.Label(v, text=_texto(idioma, 'claves_intro'), bg=C_FONDO, fg=C_TINTA,
             justify='left', anchor='w').pack(fill='x', padx=12, pady=(12, 4))
    tk.Label(v, text=ruta, bg=C_FONDO, fg=C_ACENTO, anchor='w',
             justify='left').pack(fill='x', padx=12, pady=(0, 8))
    tk.Frame(v, bg=C_BORDE, height=1).pack(fill='x', padx=12)

    barra_v = tk.Frame(v, bg=C_FONDO)
    barra_v.pack(side='bottom', fill='x', padx=12, pady=12)
    cuerpo = tk.Frame(v, bg=C_FONDO)
    cuerpo.pack(side='top', fill='both', expand=True)
    lienzo = tk.Canvas(cuerpo, bg=C_FONDO, highlightthickness=0, bd=0)
    barra = tk.Scrollbar(cuerpo, orient='vertical', command=lienzo.yview,
                         bg=C_PANEL, troughcolor=C_FONDO, activebackground=C_ACENTO,
                         highlightthickness=0, bd=0)
    lienzo.configure(yscrollcommand=barra.set)
    barra.pack(side='right', fill='y')
    lienzo.pack(side='left', fill='both', expand=True, padx=(12, 0), pady=8)
    dentro = tk.Frame(lienzo, bg=C_FONDO)
    ventana_i = lienzo.create_window((0, 0), window=dentro, anchor='nw')
    dentro.bind('<Configure>', lambda e: lienzo.configure(scrollregion=lienzo.bbox('all')))
    lienzo.bind('<Configure>', lambda e: lienzo.itemconfigure(ventana_i, width=e.width))

    campos = {}
    for fila, (campo, info) in enumerate(ayuda.items()):
        caja = tk.Frame(dentro, bg=C_FONDO)
        caja.pack(fill='x', pady=(0, 10))
        puesta = bool(actual.get(campo) or base.get(campo))
        tk.Label(caja, text=campo, bg=C_FONDO, fg=C_TINTA_VIVA, anchor='w',
                 width=24).grid(row=0, column=0, sticky='w')
        tk.Label(caja, text='[%s]' % _texto(idioma, 'claves_puesta' if puesta else 'claves_vacia'),
                 bg=C_FONDO, fg=(C_OK if puesta else C_ACENTO),
                 anchor='w', width=10).grid(row=0, column=1, sticky='w')
        e = tk.Entry(caja, bg=C_PANEL, fg=C_TINTA_VIVA, insertbackground=C_ACENTO,
                     relief='flat', highlightthickness=1, highlightbackground=C_BORDE,
                     highlightcolor=C_ACENTO, show='•', width=34)
        e.grid(row=0, column=2, sticky='we', padx=(8, 0))
        caja.columnconfigure(2, weight=1)
        campos[campo] = e
        tk.Label(caja, text=info.get('desbloquea', ''), bg=C_FONDO, fg=C_TINTA,
                 anchor='w', justify='left', wraplength=620).grid(row=1, column=0, columnspan=3, sticky='w')
        detalle = info.get('donde', '')
        if info.get('nota'):
            detalle += '   ⚠ ' + info['nota']
        tk.Label(caja, text=detalle, bg=C_FONDO, fg=C_ACENTO, anchor='w',
                 justify='left', wraplength=620).grid(row=2, column=0, columnspan=3, sticky='w')

    def guardar():
        nuevos = {c: e.get().strip() for c, e in campos.items() if e.get().strip()}
        if not nuevos:
            messagebox.showinfo(_texto(idioma, 'claves_titulo'),
                                _texto(idioma, 'claves_sin_cambios'))
            v.destroy()
            return
        datos = dict(base)
        datos.update(actual)
        datos.update(nuevos)
        datos.pop('_ayuda', None)          # la ayuda vive en la plantilla, no en tu fichero
        os.makedirs(mem, exist_ok=True)
        with open(ruta, 'w', encoding='utf-8') as fh:
            _json.dump(datos, fh, ensure_ascii=False, indent=2)
        # se dice CUÁNTAS, nunca cuáles ni su valor
        messagebox.showinfo(_texto(idioma, 'claves_titulo'),
                            _texto(idioma, 'claves_guardadas') % (len(nuevos), ruta))
        v.destroy()

    tk.Button(barra_v, text=_texto(idioma, 'claves_guardar'), command=guardar,
              bg=C_PANEL, fg=C_TINTA_VIVA, activebackground=C_ACENTO, activeforeground=C_FONDO,
              relief='flat', bd=0, highlightthickness=1, highlightbackground=C_BORDE,
              padx=14, pady=6, cursor='hand2').pack(side='left')
    tk.Button(barra_v, text=_texto(idioma, 'claves_cancelar'), command=v.destroy,
              bg=C_PANEL, fg=C_TINTA_VIVA, activebackground=C_ACENTO, activeforeground=C_FONDO,
              relief='flat', bd=0, highlightthickness=1, highlightbackground=C_BORDE,
              padx=14, pady=6, cursor='hand2').pack(side='right')

    v.update_idletasks()
    lienzo.configure(height=min(dentro.winfo_reqheight(), int(v.winfo_screenheight() * 0.55)),
                     width=dentro.winfo_reqwidth())
    v.update_idletasks()
    v.geometry('%dx%d' % (v.winfo_reqwidth(), min(v.winfo_reqheight(),
                                                  int(v.winfo_screenheight() * 0.84))))
    return v


def _abrir_ventana(settings_ruta, python_exe, mem, proj, skills_dir=None, idioma='es'):
    skills_dir = skills_dir or SKILLS_DIR_POR_DEFECTO
    import tkinter as tk
    from tkinter import messagebox, simpledialog

    root = tk.Tk()
    root.title(_texto(idioma, 'ventana_titulo'))
    root.configure(bg=C_FONDO)

    # ── que quepa, antes que nada ───────────────────────────────────────────
    # MEDIDO el 9-sep-2026: con 22 módulos la ventana pedía 682x1594 px en una pantalla de
    # 1920x1080 y estaba fijada con resizable(False, False). Los cuatro botones quedaban
    # 514 px POR DEBAJO del borde inferior: la ventana no se podía usar y nadie lo había
    # visto porque nada lo medía. La lista va ahora dentro de un lienzo con barra, la
    # ventana crece a lo alto, y el alto de arranque se limita a lo que dé la pantalla.
    root.resizable(False, True)

    # los colores por defecto de TODO widget clásico que se cree a partir de aquí; los
    # `messagebox` son de Windows y no obedecen: eso se queda gris y se dice
    for patron, valor in (('*background', C_FONDO), ('*foreground', C_TINTA),
                          ('*Label.background', C_FONDO), ('*Label.foreground', C_TINTA),
                          ('*Checkbutton.background', C_FONDO),
                          ('*Checkbutton.foreground', C_TINTA),
                          ('*Checkbutton.activeBackground', C_FONDO),
                          ('*Checkbutton.activeForeground', C_ACENTO),
                          ('*Checkbutton.selectColor', C_ACENTO),
                          ('*Button.background', C_PANEL),
                          ('*Button.foreground', C_TINTA_VIVA),
                          ('*Button.activeBackground', C_ACENTO),
                          ('*Button.activeForeground', C_FONDO),
                          ('*Button.highlightBackground', C_BORDE),
                          ('*Frame.background', C_FONDO),
                          ('*Canvas.background', C_FONDO)):
        root.option_add(patron, valor)

    tk.Label(root, text=_texto(idioma, 'settings_prefix') + str(settings_ruta),
             anchor='w', bg=C_FONDO, fg=C_TINTA_VIVA).pack(fill='x', padx=10, pady=(10, 0))
    proyecto_txt = proj or _texto(idioma, 'ventana_proyecto_sin_resolver')
    tk.Label(root, text=_texto(idioma, 'ventana_proyecto_label', proj=proyecto_txt),
             anchor='w', bg=C_FONDO, fg=C_ACENTO).pack(fill='x', padx=10)

    # El cuerpo va en su propio marco. Sin él, el lienzo y su barra se reparten TODO el
    # espacio que queda y la fila de botones acaba flotando arriba a la derecha — que es
    # exactamente lo que pasó al primer intento.
    # En Tk, lo que va abajo se empaqueta ANTES que lo que se expande: si el cuerpo se
    # lleva primero todo el hueco, la fila de botones se queda con 1 px y sus botones ni
    # llegan a mapearse. Medido: `visible=0` en los cuatro. Así que el marco de los botones
    # se crea aquí, vacío, y más abajo se le meten dentro cuando existen sus funciones.
    tk.Frame(root, bg=C_BORDE, height=1).pack(side='bottom', fill='x')
    botones = tk.Frame(root, bg=C_FONDO)
    botones.pack(side='bottom', fill='x', padx=10, pady=10)

    cuerpo = tk.Frame(root, bg=C_FONDO)
    cuerpo.pack(side='top', fill='both', expand=True)
    lienzo = tk.Canvas(cuerpo, bg=C_FONDO, highlightthickness=0, bd=0)
    barra = tk.Scrollbar(cuerpo, orient='vertical', command=lienzo.yview,
                         bg=C_PANEL, troughcolor=C_FONDO, activebackground=C_ACENTO,
                         highlightthickness=0, bd=0)
    lienzo.configure(yscrollcommand=barra.set)
    barra.pack(side='right', fill='y')
    lienzo.pack(side='left', fill='both', expand=True, padx=(10, 0), pady=8)
    marco = tk.Frame(lienzo, bg=C_FONDO)
    _ventana_interior = lienzo.create_window((0, 0), window=marco, anchor='nw')
    marco.bind('<Configure>',
               lambda e: lienzo.configure(scrollregion=lienzo.bbox('all')))
    lienzo.bind('<Configure>',
                lambda e: lienzo.itemconfigure(_ventana_interior, width=e.width))
    # la rueda del ratón, que en Windows llega con delta de 120 por muesca
    lienzo.bind_all('<MouseWheel>',
                    lambda e: lienzo.yview_scroll(int(-e.delta / 120), 'units'))

    variables = {}
    etiquetas_estado = {}
    for fila, mod in enumerate(MODULOS):
        var = tk.BooleanVar(value=mod['defecto'])
        variables[mod['id']] = var
        tk.Checkbutton(marco, variable=var).grid(row=fila, column=0, sticky='w')
        tk.Label(marco, text=mod['id'], width=14, anchor='w').grid(row=fila, column=1, sticky='w')
        etiqueta = tk.Label(marco, text='...', width=15, anchor='w')
        etiqueta.grid(row=fila, column=2, sticky='w')
        etiquetas_estado[mod['id']] = etiqueta
        # `linea`/`aviso` son documentación del código (T5.2): se muestran igual
        # en las dos ventanas, castellano siempre — solo la etiqueta de estado y
        # los botones/avisos propios del instalador cambian de idioma.
        texto = mod['linea'] + (f'  ⚠ {mod["aviso"]}' if mod.get('aviso') else '')
        tk.Label(marco, text=texto, anchor='w', justify='left', wraplength=420).grid(row=fila, column=3, sticky='w')

    def refrescar():
        settings = _leer_json(settings_ruta)
        for mod in MODULOS:
            st = estado_modulo(settings, mod, settings_ruta, skills_dir)
            etiquetas_estado[mod['id']].config(text=_texto(idioma, _ETIQUETA_ESTADO_CLAVE[st]))

    def seleccionados():
        return [mid for mid, v in variables.items() if v.get()]

    def hacer_instalar():
        ids = seleccionados()
        if not ids:
            messagebox.showinfo(_texto(idioma, 'titulo_abyss'), _texto(idioma, 'msg_sin_modulos'))
            return
        if 'permisos' in ids and not messagebox.askyesno(
                _texto(idioma, 'titulo_aviso'), _texto(idioma, 'msg_confirmar_permisos')):
            ids = [i for i in ids if i != 'permisos']
        token = chat = None
        if 'telegram' in ids:
            titulo_tg = _texto(idioma, 'titulo_telegram')
            token = simpledialog.askstring(titulo_tg, _texto(idioma, 'dlg_telegram_token'), parent=root)
            chat = simpledialog.askstring(titulo_tg, _texto(idioma, 'dlg_telegram_chat'), parent=root) if token else None
            if not (token and chat):
                messagebox.showwarning(_texto(idioma, 'titulo_abyss'), _texto(idioma, 'msg_telegram_incompleto'))
                ids = [i for i in ids if i != 'telegram']
        if mem is None:
            messagebox.showerror(_texto(idioma, 'titulo_abyss'), _texto(idioma, 'msg_sin_proyecto'))
            return
        msjs = instalar(ids, settings_ruta=settings_ruta, python_exe=python_exe, mem=mem,
                        telegram=(token, chat), skills_dir=skills_dir, idioma=idioma)
        messagebox.showinfo(_texto(idioma, 'titulo_abyss'), '\n'.join(msjs) or _texto(idioma, 'msg_nada_que_hacer'))
        refrescar()

    def hacer_desinstalar():
        ids = seleccionados()
        if not ids:
            messagebox.showinfo(_texto(idioma, 'titulo_abyss'), _texto(idioma, 'msg_sin_modulos'))
            return
        if mem is None:
            messagebox.showerror(_texto(idioma, 'titulo_abyss'), _texto(idioma, 'msg_sin_proyecto'))
            return
        borrar = messagebox.askyesno(_texto(idioma, 'titulo_abyss'), _texto(idioma, 'msg_confirmar_borrar_datos'),
                                       default=messagebox.NO)
        msjs = desinstalar(ids, settings_ruta=settings_ruta, mem=mem, borrar_datos=borrar,
                            skills_dir=skills_dir, idioma=idioma)
        messagebox.showinfo(_texto(idioma, 'titulo_abyss'), '\n'.join(msjs) or _texto(idioma, 'msg_nada_que_hacer'))
        refrescar()

    def hacer_dependencias():
        # T5.1: la casilla/botón de la ventana llama a las MISMAS funciones que
        # la CLI (`_tabla_dependencias`/`instalar_dependencias`) — nunca una
        # segunda implementación. Solo actúa sobre los módulos MARCADOS que
        # tengan dependencias registradas; si ninguno lo está, sobre todos.
        ids = [i for i in seleccionados() if i in DEPENDENCIAS] or list(DEPENDENCIAS)
        tabla = _tabla_dependencias(idioma, ids, python_exe)
        if not messagebox.askyesno(_texto(idioma, 'titulo_aviso'),
                                    tabla + '\n\n' + _texto(idioma, 'msg_confirmar_instalar_dependencias')):
            return
        msjs, _ok = instalar_dependencias(ids, python_exe=python_exe, idioma=idioma)
        messagebox.showinfo(_texto(idioma, 'titulo_abyss'), '\n'.join(msjs) or _texto(idioma, 'msg_nada_que_hacer'))

    def _boton(padre, texto, orden_):
        """El color de un botón no llega por `option_add` en Windows: hay que dárselo.
        Medido: con solo option_add salían grises de sistema sobre el fondo oscuro."""
        return tk.Button(padre, text=texto, command=orden_,
                         bg=C_PANEL, fg=C_TINTA_VIVA,
                         activebackground=C_ACENTO, activeforeground=C_FONDO,
                         relief='flat', bd=0, highlightthickness=1,
                         highlightbackground=C_BORDE, highlightcolor=C_ACENTO,
                         padx=14, pady=6, cursor='hand2')

    _boton(botones, _texto(idioma, 'boton_instalar'), hacer_instalar).pack(side='left')
    _boton(botones, _texto(idioma, 'boton_desinstalar'), hacer_desinstalar).pack(side='left', padx=6)
    _boton(botones, _texto(idioma, 'boton_dependencias'), hacer_dependencias).pack(side='left', padx=6)
    _boton(botones, _texto(idioma, 'boton_claves'),
           lambda: _ventana_claves(root, mem, idioma)).pack(side='left', padx=6)
    _boton(botones, _texto(idioma, 'boton_cerrar'), root.destroy).pack(side='right')

    refrescar()

    # El alto de arranque: lo que pida, pero nunca más de lo que hay de pantalla. Se calcula
    # DESPUÉS de montar todo y se comprueba contra la pantalla de verdad; nunca se escribe un
    # geometry() con números a mano, que se rompe en cuanto cambie una fuente o el idioma.
    root.update_idletasks()
    # Un lienzo no pide el alto de lo que lleva dentro: hay que decírselo. Se le da el alto
    # de la lista entera, y luego la ventana se topa a lo que dé la pantalla; lo que no
    # quepa se alcanza con la barra o con la rueda.
    alto_lista = marco.winfo_reqheight()
    alto_util = int(root.winfo_screenheight() * 0.84)
    lienzo.configure(height=alto_lista, width=marco.winfo_reqwidth())
    root.update_idletasks()
    ancho = root.winfo_reqwidth()
    alto = min(root.winfo_reqheight(), alto_util)
    # y COLOCADA donde quepa: con el tamaño arreglado pero puesta en +239, su borde inferior
    # caía en 1146 de una pantalla de 1080. Centrada horizontal, y arriba con un margen.
    x = max(0, (root.winfo_screenwidth() - ancho) // 2)
    y = max(0, min(60, root.winfo_screenheight() - alto - 40))
    root.geometry('%dx%d+%d+%d' % (ancho, alto, x, y))
    root.minsize(min(ancho, 560), 360)
    return root


# ---------------------------------------------------------------------------------
if __name__ == '__main__':
    argv = sys.argv[1:]

    # T5.2: el idioma se resuelve ANTES que nada más (incluso antes de `--help`),
    # para que `--help --idioma en` salga en inglés. Un valor inválido (ni "es" ni
    # "en") es un error de bandera propio — fail-closed, nunca se adivina o se
    # ignora en silencio — dicho en los DOS idiomas a la vez, porque aquí todavía
    # no hay NINGÚN idioma decidido con el que elegir uno solo para el mensaje.
    _idioma_pedido = _valor_flag(argv, '--idioma')
    if _idioma_pedido and _idioma_pedido.strip().lower() not in ('es', 'en'):
        # bilingue-a-proposito: única excepción a "todo pasa por TEXTOS" (T5.2) —
        # antes de esta línea no hay idioma resuelto con el que elegir uno solo.
        sys.stderr.write(f'instalar: --idioma debe ser "es" o "en" (must be "es" or "en"), no "{_idioma_pedido}"\n')
        sys.exit(2)
    idioma = (_idioma_pedido.strip().lower() if _idioma_pedido else None) or _idioma_sistema()

    if '-h' in argv or '--help' in argv:
        print(_uso(idioma))
        sys.exit(0)

    _error_argv = _argumento_no_reconocido(argv, idioma)
    if _error_argv:
        sys.stderr.write(f'instalar: {_error_argv}\n\n{_uso(idioma)}')
        sys.exit(2)

    settings_ruta = _valor_flag(argv, '--settings', SETTINGS_POR_DEFECTO)
    python_exe = _valor_flag(argv, '--python', sys.executable)
    skills_dir = _valor_flag(argv, '--skills-dir', SKILLS_DIR_POR_DEFECTO)

    if '--listar' in argv:
        _listar(settings_ruta, skills_dir=skills_dir, idioma=idioma)
        sys.exit(0)

    if '--claves' in argv:
        _claves(argv, idioma)
        sys.exit(0)

    if '--dependencias' in argv:
        print(_tabla_dependencias(idioma, python_exe=python_exe))
        sys.exit(0)

    if '--instalar-dependencias' in argv:
        modulos_dep = _lista_flag_opcional(argv, '--instalar-dependencias') or None
        desconocidos = [m for m in (modulos_dep or []) if m not in DEPENDENCIAS]
        if desconocidos:
            for m in desconocidos:
                sys.stderr.write(_texto(idioma, 'dep_modulo_desconocido', mod=m) + '\n')
            sys.exit(2)
        mensajes, ok = instalar_dependencias(modulos_dep, python_exe=python_exe, idioma=idioma)
        for msj in mensajes:
            print(msj)
        sys.exit(0 if ok else 1)

    if '--modelo' in argv:
        mensajes, ok = descargar_vendor_modelo(idioma=idioma)
        for msj in mensajes:
            print(msj)
        sys.exit(0 if ok else 1)

    if '--manos' in argv:
        mensajes, ok = descargar_vendor_mp(idioma=idioma)
        for msj in mensajes:
            print(msj)
        sys.exit(0 if ok else 1)

    ids_instalar = _lista_flag(argv, '--instalar')
    ids_desinstalar = _lista_flag(argv, '--desinstalar')

    if ids_instalar:
        proj, mem = _resolver_mem(argv)
        if mem is None:
            sys.exit(_texto(idioma, 'error_proyecto'))
        telegram = _pedir_telegram_cli(argv, idioma) if 'telegram' in ids_instalar else None
        for msj in instalar(ids_instalar, settings_ruta=settings_ruta, python_exe=python_exe, mem=mem,
                             telegram=telegram, skills_dir=skills_dir, idioma=idioma):
            print(msj)
        sys.exit(0)

    if ids_desinstalar:
        proj, mem = _resolver_mem(argv)
        if mem is None:
            sys.exit(_texto(idioma, 'error_proyecto'))
        borrar = '--borrar-datos' in argv
        if not borrar and '--sin-preguntar' not in argv and sys.stdin.isatty():
            try:
                respuesta = input(_texto(idioma, 'pregunta_borrar_datos')).strip().lower()
                borrar = respuesta.startswith('s' if idioma == 'es' else 'y')
            except (EOFError, KeyboardInterrupt):
                borrar = False
        for msj in desinstalar(ids_desinstalar, settings_ruta=settings_ruta, mem=mem, borrar_datos=borrar,
                                skills_dir=skills_dir, idioma=idioma):
            print(msj)
        sys.exit(0)

    if '--sin-ventana' in argv:
        _listar(settings_ruta, skills_dir=skills_dir, idioma=idioma)
        sys.exit(0)

    proj, mem = _resolver_mem(argv)
    try:
        ventana = _abrir_ventana(settings_ruta, python_exe, mem, proj, skills_dir=skills_dir, idioma=idioma)
    except Exception as e:
        # sin entorno gráfico (Tk no puede abrir una ventana: sesión sin escritorio,
        # CI, SSH sin X forwarding…) no hay con qué mostrar la ventana — la misma
        # protección que ya tiene `_pedir_telegram_cli` con `isatty`, aquí para Tk.
        print(_texto(idioma, 'sin_ventana_fallback', tipo=type(e).__name__, error=e))
        _listar(settings_ruta, skills_dir=skills_dir, idioma=idioma)
        sys.exit(0)
    ventana.mainloop()
