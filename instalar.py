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
"""
import sys; sys.stdout.reconfigure(encoding="utf-8")
import os
import json
import time
import shutil
import subprocess
import locale
import platform
import warnings

RAIZ = os.path.dirname(os.path.abspath(__file__))     # raíz del repo: aquí vive este fichero
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
         ]),
    dict(id='vigia', script='vigia.py', defecto=True,
         linea='Penaliza la confabulación: caza números, rutas y citas que no salieron de ninguna parte.',
         linea_en='Penalizes confabulation: catches numbers, paths and quotes that came from nowhere.',
         toca='gancho Stop → vigia.py --verificar; ficheros mem/confabulaciones.jsonl',
         hooks=[('Stop', ['--verificar'], 30)]),
    dict(id='exterocepcion', script='exterocepcion.py', defecto=True,
         linea='Lugar, meteo y canal en cada prompt (ipinfo.io, open-meteo.com, nominatim); sin red, «sin dato».',
         linea_en='Place, weather and channel on every prompt (ipinfo.io, open-meteo.com, nominatim); '
                  'without network, "no data".',
         toca='sin gancho propio (lo usa continuidad --despertar); ficheros mem/lugar.json, mem/meteo.json',
         hooks=[]),
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
         plantilla='modelo_preferido.json'),
    dict(id='noticias', script='noticias.py', defecto=True,
         linea='El día y lo reciente nuestro visto desde fuera (Google News RSS), al arrancar.',
         linea_en='The day and our recent activity seen from outside (Google News RSS), on startup.',
         toca='sin gancho propio (lo usa continuidad --arranque); ficheros mem/noticias.json, mem/temas_*.json',
         hooks=[], plantilla='temas_noticias.json'),
    dict(id='propiocepcion', script='propiocepcion.py', defecto=True,
         linea='Mide cada sesión contra mi propia distribución; varas.py pone los ◆ del índice (MEMORY.md).',
         linea_en='Measures each session against its own distribution; varas.py sets the ◆ marks in the '
                  'index (MEMORY.md).',
         toca='sin gancho propio (varas.py --index lo invoca continuidad --cierre); ficheros mem/propiocepcion.json',
         hooks=[]),
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
                          'falta y sale con código 2; nunca se instala nada desde aquí.'),
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
               'arañazos/relleno/zonas conexas — sin ella, más lento o con menos pasos, nunca falla del todo).'),
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
               'visor y editor de vistas, no un modelador: no repara mallas, no simplifica, no exporta.'),
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
               'cámara) hasta que se interrumpe: no es un comando que termina solo.'),
    dict(id='parentesis', script='parentesis.py', defecto=True,
         linea='Marca un tramo o una sesión entera para que no entre en la memoria futura; puede recortar el '
               'transcript local ya cerrado.',
         linea_en='Marks a stretch or a whole session so it does not enter future memory; can trim the '
                  'local transcript once it is already closed.',
         toca='sin gancho — uso manual (--abrir/--cerrar/--omitir-sesion/--recortar/--recortar-tramo); '
              'ficheros mem/parentesis.json, mem/sesiones/.omitir',
         hooks=[],
         aviso='no puede deshacer lo que ya viajó a la API dentro de un turno: gobierna la memoria LOCAL de '
               'este paquete (lo que el propio asistente vuelve a leer), no los servidores de Anthropic.'),
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
               'tiene coste (medido en la máquina de desarrollo: ~950 ms por PowerShell combinado en Windows) '
               'hasta que el propio guion detecta que ese coste supera 1,5 s de mediana y pasa a fotografiar '
               'solo tras comandos que parecen persistentes (heurística declarada, ver docstring de huella.py).'),
    dict(id='cuerpo', script='cuerpo.py', defecto=True,
         linea='El cuerpo de la máquina (cpu, ram, disco, vram, temperatura de GPU, batería) con su propia '
               'normal por cuantiles.',
         linea_en="The machine's body (cpu, ram, disk, vram, GPU temperature, battery) with its own "
                  'quantile-based normal.',
         toca='ganchos SessionStart/UserPromptSubmit → cuerpo.py --arranque/--despertar; ficheros mem/cuerpo.jsonl',
         hooks=[
             ('SessionStart', ['--arranque'], 15),
             ('UserPromptSubmit', ['--despertar'], 15),
         ]),
    dict(id='lector_pdf', script='lector_pdf.py', defecto=True,
         linea='Indexa un PDF por página y sección, busca por TF-IDF y mide cuánto ahorra leer solo lo que toca.',
         linea_en='Indexes a PDF by page and section, searches by TF-IDF, and measures how much is '
                  'saved by reading only what matters.',
         toca='sin gancho — uso manual (--indexar/--secciones/--buscar/--leer/--ahorro <pdf>); '
              'ficheros mem/pdf/<sha1 del fichero>.json',
         hooks=[], aviso='necesita PyMuPDF (fitz) o pypdf; sin ninguna de las dos, «sin dato: pip install pymupdf».'),
    dict(id='mapa_codigo', script='mapa_codigo.py', defecto=True,
         linea='El índice greppable de un repo Python con `ast`: módulos, clases, funciones e imports con su línea.',
         linea_en='The greppable index of a Python repo with `ast`: modules, classes, functions and '
                  'imports with their line.',
         toca='sin gancho — uso manual (<carpeta> [--salida] [--json], --buscar <nombre>); '
              'ficheros mem/mapas/<carpeta>.txt(.json)',
         hooks=[]),
    dict(id='auditar', script='auditar.py', defecto=True,
         linea='Las cinco comprobaciones sobre un paquete antes de instalarlo: procedencia, comandos, '
               'permisos, qué sale de la máquina, y dominios para lectura manual.',
         linea_en='The five checks on a package before installing it: provenance, commands, '
                  'permissions, what leaves the machine, and domains for manual reading.',
         toca='sin gancho — uso manual (`python auditar.py <ruta> [--json] [--markdown f.md]`, o vía la '
              'skill esceptico con --paquete); NUNCA ejecuta el código auditado (solo lee texto y, si hay '
              '.git, su historial LOCAL); no toca mem',
         hooks=[]),
    dict(id='esceptico', script=None, defecto=True, especial='skill', carpeta_skill='esceptico',
         linea='La ley «ningún plan sin escéptico» como comando: lanza un revisor con model Opus a tumbar un '
               'plan antes de ejecutarlo, o (--paquete) a leer por encima del informe de auditar.py.',
         linea_en='The "no plan without a skeptic" rule as a command: launches an Opus-model reviewer '
                  'to try to shoot down a plan before running it, or (--paquete) to look over '
                  "auditar.py's report.",
         toca='copia skills/esceptico/ a <skills-dir>/esceptico/ (por defecto ~/.claude/skills/esceptico/, '
              'ver --skills-dir); no es Python, no toca settings.json ni mem',
         hooks=[]),
    dict(id='infografia', script='infografia.py', defecto=True,
         linea='De un CSV o JSON a un SVG limpio (barras, barras horizontales, líneas, tabla), biblioteca estándar.',
         linea_en='From a CSV or JSON to a clean SVG (bars, horizontal bars, lines, table), standard '
                  'library only.',
         toca='sin gancho — uso manual; no resuelve proyecto, no toca mem: solo escribe el .svg que se le pida',
         hooks=[]),
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
               'El modelo se descarga de Hugging Face al PRIMER uso; en CPU, cada imagen tarda minutos, no segundos.'),
    dict(id='telegram', script=None, defecto=False, especial='telegram',
         linea='Aviso por Telegram cuando Claude Code necesita permiso o espera respuesta.',
         linea_en='Telegram notice when Claude Code needs permission or is waiting for a reply.',
         toca='gancho Notification → powershell + mem/notify_telegram.ps1 (nunca en el código)',
         hooks=[], aviso='pide token de bot y chat id; los guarda solo en mem/notify_telegram.ps1.'),
    dict(id='permisos', script=None, defecto=False, especial='permisos',
         linea='Da permiso de Edit sobre tu settings.json (autoedición). APAGADO por defecto.',
         linea_en='Grants Edit permission over your settings.json (self-editing). OFF by default.',
         toca='clave permissions.allow += "Edit(<settings.json>)"',
         hooks=[], aviso='deja que el propio asistente edite settings.json sin preguntar cada vez.'),
    dict(id='preferencias', script=None, defecto=True, especial='preferencias',
         linea='Preferencia showThinkingSummaries (ver los resúmenes de pensamiento).',
         linea_en='Preference showThinkingSummaries (show thinking summaries).',
         toca='clave showThinkingSummaries = true',
         hooks=[], claves={'showThinkingSummaries': True}),
]
MODULOS_POR_ID = {m['id']: m for m in MODULOS}


# ---------------------------------------------------------------------------------
# T5.1 · dependencias de terceros por módulo (ESPECIFICACION_TANDA5.md §T5.1).
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


def _tabla_dependencias(idioma, modulos=None, python_exe=None):
    estado = _estado_dependencias(modulos, python_exe)
    filas = [_texto(idioma, 'dep_cabecera')]
    for mid, entradas in estado.items():
        for e in entradas:
            filas.append(_fila_dependencia(idioma, mid, e))
    return '\n'.join(filas) + '\n\n' + _texto_no_instalables(idioma)


# ---------------------------------------------------------------------------------
# T5.2 · bilingüe (ESPECIFICACION_TANDA5.md §T5.2): las cadenas cortas de interfaz
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
        'uso': (
            "Uso:\n"
            "  python instalar.py --listar\n"
            "  python instalar.py --instalar mod1,mod2 [--telegram-token T --telegram-chat ID]\n"
            "  python instalar.py --desinstalar mod1[,mod2] [--borrar-datos] [--sin-preguntar]\n"
            "  python instalar.py --dependencias\n"
            "  python instalar.py --instalar-dependencias [mod1,mod2]\n"
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
        'toca_label': 'touches:',  # not shown today (English --listar omits the detail lines); kept for completeness
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
        'uso': (
            "Usage:\n"
            "  python instalar.py --listar\n"
            "  python instalar.py --instalar mod1,mod2 [--telegram-token T --telegram-chat ID]\n"
            "  python instalar.py --desinstalar mod1[,mod2] [--borrar-datos] [--sin-preguntar]\n"
            "  python instalar.py --dependencias\n"
            "  python instalar.py --instalar-dependencias [mod1,mod2]\n"
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
        if idioma == 'es':
            print(f'  {"":14}   {_texto(idioma, "toca_label")} {mod["toca"]}')
            if mod.get('aviso'):
                print(f'  {"":14}   {_texto(idioma, "aviso_label")} {mod["aviso"]}')
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
_FLAGS_SIN_VALOR = ('--listar', '--sin-ventana', '--borrar-datos', '--sin-preguntar', '-h', '--help',
                    '--dependencias')
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
def _abrir_ventana(settings_ruta, python_exe, mem, proj, skills_dir=None, idioma='es'):
    skills_dir = skills_dir or SKILLS_DIR_POR_DEFECTO
    import tkinter as tk
    from tkinter import messagebox, simpledialog

    root = tk.Tk()
    root.title(_texto(idioma, 'ventana_titulo'))
    root.resizable(False, False)

    tk.Label(root, text=_texto(idioma, 'settings_prefix') + str(settings_ruta),
             anchor='w').pack(fill='x', padx=8, pady=(8, 0))
    proyecto_txt = proj or _texto(idioma, 'ventana_proyecto_sin_resolver')
    tk.Label(root, text=_texto(idioma, 'ventana_proyecto_label', proj=proyecto_txt),
             anchor='w', fg='gray').pack(fill='x', padx=8)

    marco = tk.Frame(root)
    marco.pack(fill='both', expand=True, padx=8, pady=8)

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

    botones = tk.Frame(root)
    botones.pack(fill='x', padx=8, pady=(0, 8))
    tk.Button(botones, text=_texto(idioma, 'boton_instalar'), command=hacer_instalar).pack(side='left')
    tk.Button(botones, text=_texto(idioma, 'boton_desinstalar'), command=hacer_desinstalar).pack(side='left', padx=6)
    tk.Button(botones, text=_texto(idioma, 'boton_dependencias'), command=hacer_dependencias).pack(side='left', padx=6)
    tk.Button(botones, text=_texto(idioma, 'boton_cerrar'), command=root.destroy).pack(side='right')

    refrescar()
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
