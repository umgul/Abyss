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
aviso) y tres botones, Instalar / Desinstalar / Cerrar, que llaman a las mismas
`instalar()`/`desinstalar()` de aquí abajo — no hay una segunda implementación.

Sin rutas de usuario en el código: todo lo que toca a un usuario concreto (dónde
está `~/.claude`, qué proyecto, qué `python`) se resuelve en tiempo de ejecución.
"""
import sys; sys.stdout.reconfigure(encoding="utf-8")
import os
import json
import time
import shutil

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
         toca='ganchos SessionStart/SessionEnd/UserPromptSubmit → continuidad.py --arranque/--cierre/--despertar',
         hooks=[
             ('SessionStart', ['--arranque'], 60),
             ('SessionEnd', ['--cierre'], 60),
             ('UserPromptSubmit', ['--despertar'], 30),
         ]),
    dict(id='vigia', script='vigia.py', defecto=True,
         linea='Penaliza la confabulación: caza números, rutas y citas que no salieron de ninguna parte.',
         toca='gancho Stop → vigia.py --verificar; ficheros mem/confabulaciones.jsonl',
         hooks=[('Stop', ['--verificar'], 30)]),
    dict(id='exterocepcion', script='exterocepcion.py', defecto=True,
         linea='Lugar, meteo y canal en cada prompt (ipinfo.io, open-meteo.com, nominatim); sin red, «sin dato».',
         toca='sin gancho propio (lo usa continuidad --despertar); ficheros mem/lugar.json, mem/meteo.json',
         hooks=[]),
    dict(id='modelo', script='modelo.py', defecto=True,
         linea='Avisa si Fable bajó a Opus y qué revisar cuando se vuelve.',
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
         toca='sin gancho propio (lo usa continuidad --arranque); ficheros mem/noticias.json, mem/temas_*.json',
         hooks=[], plantilla='temas_noticias.json'),
    dict(id='propiocepcion', script='propiocepcion.py', defecto=True,
         linea='Mide cada sesión contra mi propia distribución; varas.py pone los ◆ del índice (MEMORY.md).',
         toca='sin gancho propio (varas.py --index lo invoca continuidad --cierre); ficheros mem/propiocepcion.json',
         hooks=[]),
    dict(id='ojo', script='ojo.py', defecto=True,
         linea='Un fotograma de la webcam, solo cuando se pide (OpenCV opcional).',
         toca='sin gancho — nunca se dispara solo; uso manual; ficheros mem/ojo.log',
         hooks=[], aviso='necesita OpenCV (cv2); sin él, «sin cv2: no hay ojo».'),
    dict(id='imagen', script='imagen.py', defecto=True,
         linea='Crear una imagen por cascada de proveedores, pintarla localmente por pinceladas (varios '
               'estilos), animarla en vídeo, renderizar una escena 3D, o buscar una imagen ya hecha o un '
               'motivo del mundo real — solo a petición.',
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
         toca='sin gancho — uso manual (`imagen.py render` delega aquí); ficheros: el HTML/PNG que se '
              'pida, junto a la entrada salvo que se indique otra ruta (nada en mem/)',
         hooks=[],
         aviso='three.js va EMBEBIDO en abyss/vendor/three.min.js (versión fijada, licencia MIT en '
               'abyss/vendor/LICENSE-three.txt) — la página no toca la red para verse. --png necesita un '
               'navegador sin cabeza en la máquina (msedge.exe/chrome.exe en Windows, google-chrome/'
               'chromium en Linux/macOS) — dependencia OPCIONAL del sistema, no de pip; sin uno, «sin dato: '
               'no hay navegador sin cabeza» y código 2 (la página HTML se escribe de todas formas). Es un '
               'visor y editor de vistas, no un modelador: no repara mallas, no simplifica, no exporta.'),
    dict(id='parentesis', script='parentesis.py', defecto=True,
         linea='Marca un tramo o una sesión entera para que no entre en la memoria futura; puede recortar el '
               'transcript local ya cerrado.',
         toca='sin gancho — uso manual (--abrir/--cerrar/--omitir-sesion/--recortar/--recortar-tramo); '
              'ficheros mem/parentesis.json, mem/sesiones/.omitir',
         hooks=[],
         aviso='no puede deshacer lo que ya viajó a la API dentro de un turno: gobierna la memoria LOCAL de '
               'este paquete (lo que el propio asistente vuelve a leer), no los servidores de Anthropic.'),
    dict(id='huella', script='huella.py', defecto=False,
         linea='Registra lo que un hilo toca fuera de su propia carpeta (ficheros escritos, procesos, puertos) '
               'y ayuda a limpiarlo al cerrar.',
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
         toca='ganchos SessionStart/UserPromptSubmit → cuerpo.py --arranque/--despertar; ficheros mem/cuerpo.jsonl',
         hooks=[
             ('SessionStart', ['--arranque'], 15),
             ('UserPromptSubmit', ['--despertar'], 15),
         ]),
    dict(id='lector_pdf', script='lector_pdf.py', defecto=True,
         linea='Indexa un PDF por página y sección, busca por TF-IDF y mide cuánto ahorra leer solo lo que toca.',
         toca='sin gancho — uso manual (--indexar/--secciones/--buscar/--leer/--ahorro <pdf>); '
              'ficheros mem/pdf/<sha1 del fichero>.json',
         hooks=[], aviso='necesita PyMuPDF (fitz) o pypdf; sin ninguna de las dos, «sin dato: pip install pymupdf».'),
    dict(id='mapa_codigo', script='mapa_codigo.py', defecto=True,
         linea='El índice greppable de un repo Python con `ast`: módulos, clases, funciones e imports con su línea.',
         toca='sin gancho — uso manual (<carpeta> [--salida] [--json], --buscar <nombre>); '
              'ficheros mem/mapas/<carpeta>.txt(.json)',
         hooks=[]),
    dict(id='esceptico', script=None, defecto=True, especial='skill', carpeta_skill='esceptico',
         linea='La ley «ningún plan sin escéptico» como comando: lanza un revisor con model Opus a tumbar un '
               'plan antes de ejecutarlo.',
         toca='copia skills/esceptico/ a <skills-dir>/esceptico/ (por defecto ~/.claude/skills/esceptico/, '
              'ver --skills-dir); no es Python, no toca settings.json ni mem',
         hooks=[]),
    dict(id='infografia', script='infografia.py', defecto=True,
         linea='De un CSV o JSON a un SVG limpio (barras, barras horizontales, líneas, tabla), biblioteca estándar.',
         toca='sin gancho — uso manual; no resuelve proyecto, no toca mem: solo escribe el .svg que se le pida',
         hooks=[]),
    dict(id='taller', script='taller.py', defecto=False,
         especial='taller',
         linea='Deja lista la configuración de un taller local de texto→imagen para lienzo.py/imagen.py; '
               'no instala nada ni arranca el servidor.',
         toca='sin gancho; ficheros mem/imagen_config.json (siembra/actualiza taller_url, taller_denoise, '
              'taller_pasos)',
         hooks=[], plantilla='imagen_config.json',
         aviso='NO instala diffusers/torch ni arranca ningún proceso: solo escribe la URL por defecto y dice, '
               'por stdout, el comando exacto para arrancarlo tú y qué instalar antes (nunca con pip desde aquí). '
               'El modelo se descarga de Hugging Face al PRIMER uso; en CPU, cada imagen tarda minutos, no segundos.'),
    dict(id='telegram', script=None, defecto=False, especial='telegram',
         linea='Aviso por Telegram cuando Claude Code necesita permiso o espera respuesta.',
         toca='gancho Notification → powershell + mem/notify_telegram.ps1 (nunca en el código)',
         hooks=[], aviso='pide token de bot y chat id; los guarda solo en mem/notify_telegram.ps1.'),
    dict(id='permisos', script=None, defecto=False, especial='permisos',
         linea='Da permiso de Edit sobre tu settings.json (autoedición). APAGADO por defecto.',
         toca='clave permissions.allow += "Edit(<settings.json>)"',
         hooks=[], aviso='deja que el propio asistente edite settings.json sin preguntar cada vez.'),
    dict(id='preferencias', script=None, defecto=True, especial='preferencias',
         linea='Preferencia showThinkingSummaries (ver los resúmenes de pensamiento).',
         toca='clave showThinkingSummaries = true',
         hooks=[], claves={'showThinkingSummaries': True}),
]
MODULOS_POR_ID = {m['id']: m for m in MODULOS}


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
def instalar(ids, *, settings_ruta, python_exe, mem, telegram=None, skills_dir=None):
    """Instala los módulos `ids` (lista de str) fusionando en `settings_ruta`.
    `telegram` es `(token, chat_id)` o None/incompleto (entonces ese módulo se
    salta con aviso). `skills_dir` es donde copiar una skill como `esceptico`
    (por defecto `SKILLS_DIR_POR_DEFECTO`, ~/.claude/skills). Devuelve la lista de
    mensajes (str) para mostrar al usuario."""
    skills_dir = skills_dir or SKILLS_DIR_POR_DEFECTO
    mensajes = [f'? módulo desconocido: {i}' for i in ids if i not in MODULOS_POR_ID]
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
                mensajes.append('telegram: faltan credenciales (--telegram-token/--telegram-chat); no se instala')
                continue
            ps1 = _escribir_ps1_telegram(mem, token, chat)
            command = _construir_command(_powershell(), ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ps1])
            if _anadir_hook(settings, 'Notification', command, 20, ps1):
                cambiado = True
            manifiesto['detalle'].setdefault('telegram', {})['ps1'] = ps1

        if mod.get('especial') == 'skill':
            destino = _copiar_skill(mod['carpeta_skill'], skills_dir)
            manifiesto['detalle'].setdefault(mid, {})['skill_destino'] = destino
            mensajes.append(f'{mid}: skill copiada a {destino}')

        if mod.get('especial') == 'taller':
            ruta_script = _script(mod['script'])
            mensajes.append(
                f'{mid}: NO se instala nada ni se arranca ningún proceso. Para arrancarlo tú: '
                f'python "{ruta_script}" [--puerto 7860] [--modelo Lykon/dreamshaper-8] '
                f'[--cache-dir <ruta>] [--dispositivo auto|cuda|mps|cpu] [--pasos 20] — necesita '
                f'"pip install diffusers" y torch (con CUDA si tienes GPU NVIDIA: sigue '
                f'pytorch.org/get-started/locally/; si no, la versión CPU — cada imagen tardará '
                f'minutos, no segundos). El modelo se descarga de Hugging Face al primer uso.')

        if mod.get('plantilla') and _sembrar_plantilla(mod['plantilla'], mem):
            mensajes.append(f'{mid}: sembrado mem/{mod["plantilla"]}')

        instalados.add(mid)
        tocado = tocado or cambiado
        mensajes.append(f'{mid}: {"instalado" if cambiado or not ya else "ya estaba instalado"}')

    manifiesto['modulos_instalados'] = sorted(instalados)
    manifiesto['python'] = python_exe
    manifiesto['settings_ruta'] = os.path.abspath(settings_ruta)
    manifiesto['actualizado'] = time.strftime('%Y-%m-%dT%H:%M:%S')
    if tocado:
        _escribir_json(settings_ruta, settings)
    _guardar_manifiesto(mem, manifiesto)
    _escribir_config_codigo(python_exe)
    return mensajes


def desinstalar(ids, *, settings_ruta, mem, borrar_datos=False, skills_dir=None):
    """Desinstala los módulos `ids`: quita solo las entradas cuyo comando apunta a
    nuestro código (o al `.ps1` de telegram que escribimos nosotros), retira una
    skill copiada (`esceptico`) SOLO si lleva nuestra marca, y restaura las claves
    de preferencia/permisos a su valor previo. Si `borrar_datos`, además limpia
    `DATOS_GENERADOS` de `mem` (nunca MEMORY.md ni las fichas)."""
    skills_dir = skills_dir or SKILLS_DIR_POR_DEFECTO
    mensajes = []
    settings = _leer_json(settings_ruta)
    manifiesto = _cargar_manifiesto(mem)
    instalados = set(manifiesto['modulos_instalados'])
    tocado = False

    for mid in ids:
        mod = MODULOS_POR_ID.get(mid)
        if not mod:
            mensajes.append(f'? módulo desconocido: {mid}')
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
                mensajes.append(f'{mid}: skill retirada de {destino}')
            elif os.path.isdir(destino):
                mensajes.append(f'{mid}: {destino} no lleva la marca de abyss — no se toca')
            manifiesto['detalle'].pop(mid, None)

        if mod.get('especial') == 'taller':
            manifiesto['detalle'].pop(mid, None)  # nada que restaurar: no tocó settings.json ni claves

        if not mod.get('especial'):  # los especiales ya gestionan su propia entrada arriba
            if detalle_mid:  # `previas` puede seguir ahí (vacío) para módulos con claves: igual que antes
                manifiesto['detalle'][mid] = detalle_mid
            else:
                manifiesto['detalle'].pop(mid, None)

        instalados.discard(mid)
        mensajes.append(f'{mid}: desinstalado')

    if tocado:
        _copia_fechada(settings_ruta)
        _escribir_json(settings_ruta, settings)
    manifiesto['modulos_instalados'] = sorted(instalados)
    manifiesto['actualizado'] = time.strftime('%Y-%m-%dT%H:%M:%S')
    _guardar_manifiesto(mem, manifiesto)

    if borrar_datos:
        borrados = _borrar_datos_generados(mem)
        mensajes.append('datos generados borrados: ' + (', '.join(borrados) if borrados else '(no había nada)'))
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


_ETIQUETA_ESTADO = {True: 'instalado', False: 'no instalado', None: 'sin gancho propio'}


def _listar(settings_ruta, skills_dir=None):
    settings = _leer_json(settings_ruta)
    existe = os.path.exists(settings_ruta)
    print(f'settings: {settings_ruta}' + ('' if existe else '  (no existe todavía)'))
    for mod in MODULOS:
        st = estado_modulo(settings, mod, settings_ruta, skills_dir)
        print(f'  {mod["id"]:14} [{_ETIQUETA_ESTADO[st]:16}] {mod["linea"]}')
        print(f'  {"":14}   toca: {mod["toca"]}')
        if mod.get('aviso'):
            print(f'  {"":14}   aviso: {mod["aviso"]}')


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


# ---------------------------------------------------------------------------------
# Validación de argv (fallo 6-sep: `--help`, un typo como `--instaler`, o cualquier
# invocación no interactiva con una bandera que __main__ no reconocía, caían de
# largo hasta `_abrir_ventana()` + `mainloop()` — el proceso se quedaba colgado sin
# salida (MEDIDO: `--help` no volvió en 120 s) y encima abría una ventana en el
# escritorio del usuario. Se valida ANTES de decidir qué hacer, para salir con un
# mensaje claro (código 2) en vez de caer a la ventana por descarte.
# ---------------------------------------------------------------------------------
_FLAGS_CON_VALOR = ('--settings', '--python', '--proyecto', '--instalar', '--desinstalar',
                    '--telegram-token', '--telegram-chat', '--skills-dir')
_FLAGS_SIN_VALOR = ('--listar', '--sin-ventana', '--borrar-datos', '--sin-preguntar', '-h', '--help')

_USO = """Uso:
  python instalar.py --listar
  python instalar.py --instalar mod1,mod2 [--telegram-token T --telegram-chat ID]
  python instalar.py --desinstalar mod1[,mod2] [--borrar-datos] [--sin-preguntar]
  python instalar.py --sin-ventana                (equivale a --listar)
  python instalar.py                              (ventana Tk; sin entorno gráfico, --listar)
Comunes: --settings <ruta>  --python <exe>  --proyecto <cwd>  --skills-dir <ruta>
  (--skills-dir: dónde copiar una skill como "esceptico"; por defecto ~/.claude/skills)
"""


def _argumento_no_reconocido(argv):
    """None si `argv` solo trae banderas conocidas (con su valor detrás cuando lo
    necesitan); si no, un mensaje describiendo la primera que no encaja."""
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in _FLAGS_CON_VALOR:
            if i + 1 >= len(argv):
                return f'falta el valor de {a}'
            i += 2
            continue
        if a in _FLAGS_SIN_VALOR:
            i += 1
            continue
        return f'argumento no reconocido: {a}'
    return None


def _pedir_telegram_cli(argv):
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
        token = token or input('Abyss · Telegram: token del bot: ').strip()
        chat = chat or input('Abyss · Telegram: chat id: ').strip()
    except (EOFError, KeyboardInterrupt):
        pass
    return (token or None), (chat or None)


# ---------------------------------------------------------------------------------
# Ventana Tk: la misma lógica que la CLI (llama a instalar()/desinstalar() de arriba).
# ---------------------------------------------------------------------------------
def _abrir_ventana(settings_ruta, python_exe, mem, proj, skills_dir=None):
    skills_dir = skills_dir or SKILLS_DIR_POR_DEFECTO
    import tkinter as tk
    from tkinter import messagebox, simpledialog

    root = tk.Tk()
    root.title('Abyss · instalador')
    root.resizable(False, False)

    tk.Label(root, text=f'settings: {settings_ruta}', anchor='w').pack(fill='x', padx=8, pady=(8, 0))
    tk.Label(root, text=f'proyecto: {proj or "(sin resolver — usa --proyecto <cwd>)"}',
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
        texto = mod['linea'] + (f'  ⚠ {mod["aviso"]}' if mod.get('aviso') else '')
        tk.Label(marco, text=texto, anchor='w', justify='left', wraplength=420).grid(row=fila, column=3, sticky='w')

    def refrescar():
        settings = _leer_json(settings_ruta)
        for mod in MODULOS:
            st = estado_modulo(settings, mod, settings_ruta, skills_dir)
            etiquetas_estado[mod['id']].config(text=_ETIQUETA_ESTADO[st])

    def seleccionados():
        return [mid for mid, v in variables.items() if v.get()]

    def hacer_instalar():
        ids = seleccionados()
        if not ids:
            messagebox.showinfo('Abyss', 'No hay módulos marcados.')
            return
        if 'permisos' in ids and not messagebox.askyesno(
                'Abyss · aviso',
                'El módulo «permisos» deja que el propio asistente edite settings.json '
                'sin preguntar cada vez. ¿Seguro que quieres activarlo?'):
            ids = [i for i in ids if i != 'permisos']
        token = chat = None
        if 'telegram' in ids:
            token = simpledialog.askstring('Abyss · Telegram', 'Token del bot:', parent=root)
            chat = simpledialog.askstring('Abyss · Telegram', 'Chat id:', parent=root) if token else None
            if not (token and chat):
                messagebox.showwarning('Abyss', 'Sin token/chat id no se instala telegram.')
                ids = [i for i in ids if i != 'telegram']
        if mem is None:
            messagebox.showerror('Abyss', 'No se pudo resolver el proyecto (mem). '
                                             'Cierra y ejecuta con --proyecto <cwd>.')
            return
        msjs = instalar(ids, settings_ruta=settings_ruta, python_exe=python_exe, mem=mem,
                        telegram=(token, chat), skills_dir=skills_dir)
        messagebox.showinfo('Abyss', '\n'.join(msjs) or 'nada que hacer')
        refrescar()

    def hacer_desinstalar():
        ids = seleccionados()
        if not ids:
            messagebox.showinfo('Abyss', 'No hay módulos marcados.')
            return
        if mem is None:
            messagebox.showerror('Abyss', 'No se pudo resolver el proyecto (mem). '
                                             'Cierra y ejecuta con --proyecto <cwd>.')
            return
        borrar = messagebox.askyesno('Abyss', '¿Borrar también sesiones/relojes/etc. generados por abyss?\n'
                                                 '(recomendado: NO — son memoria tuya)', default=messagebox.NO)
        msjs = desinstalar(ids, settings_ruta=settings_ruta, mem=mem, borrar_datos=borrar, skills_dir=skills_dir)
        messagebox.showinfo('Abyss', '\n'.join(msjs) or 'nada que hacer')
        refrescar()

    botones = tk.Frame(root)
    botones.pack(fill='x', padx=8, pady=(0, 8))
    tk.Button(botones, text='Instalar', command=hacer_instalar).pack(side='left')
    tk.Button(botones, text='Desinstalar', command=hacer_desinstalar).pack(side='left', padx=6)
    tk.Button(botones, text='Cerrar', command=root.destroy).pack(side='right')

    refrescar()
    return root


# ---------------------------------------------------------------------------------
if __name__ == '__main__':
    argv = sys.argv[1:]

    if '-h' in argv or '--help' in argv:
        print(_USO)
        sys.exit(0)

    _error_argv = _argumento_no_reconocido(argv)
    if _error_argv:
        sys.stderr.write(f'instalar: {_error_argv}\n\n{_USO}')
        sys.exit(2)

    settings_ruta = _valor_flag(argv, '--settings', SETTINGS_POR_DEFECTO)
    python_exe = _valor_flag(argv, '--python', sys.executable)
    skills_dir = _valor_flag(argv, '--skills-dir', SKILLS_DIR_POR_DEFECTO)

    if '--listar' in argv:
        _listar(settings_ruta, skills_dir=skills_dir)
        sys.exit(0)

    ids_instalar = _lista_flag(argv, '--instalar')
    ids_desinstalar = _lista_flag(argv, '--desinstalar')

    if ids_instalar:
        proj, mem = _resolver_mem(argv)
        if mem is None:
            sys.exit('instalar: no se pudo resolver el proyecto (pasa --proyecto <cwd> o define ABYSS_PROYECTO)')
        telegram = _pedir_telegram_cli(argv) if 'telegram' in ids_instalar else None
        for msj in instalar(ids_instalar, settings_ruta=settings_ruta, python_exe=python_exe, mem=mem,
                             telegram=telegram, skills_dir=skills_dir):
            print(msj)
        sys.exit(0)

    if ids_desinstalar:
        proj, mem = _resolver_mem(argv)
        if mem is None:
            sys.exit('instalar: no se pudo resolver el proyecto (pasa --proyecto <cwd> o define ABYSS_PROYECTO)')
        borrar = '--borrar-datos' in argv
        if not borrar and '--sin-preguntar' not in argv and sys.stdin.isatty():
            try:
                borrar = input('¿Borrar también sesiones/relojes/etc. generados por abyss? (s/N): ') \
                    .strip().lower().startswith('s')
            except (EOFError, KeyboardInterrupt):
                borrar = False
        for msj in desinstalar(ids_desinstalar, settings_ruta=settings_ruta, mem=mem, borrar_datos=borrar,
                                skills_dir=skills_dir):
            print(msj)
        sys.exit(0)

    if '--sin-ventana' in argv:
        _listar(settings_ruta, skills_dir=skills_dir)
        sys.exit(0)

    proj, mem = _resolver_mem(argv)
    try:
        ventana = _abrir_ventana(settings_ruta, python_exe, mem, proj, skills_dir=skills_dir)
    except Exception as e:
        # sin entorno gráfico (Tk no puede abrir una ventana: sesión sin escritorio,
        # CI, SSH sin X forwarding…) no hay con qué mostrar la ventana — la misma
        # protección que ya tiene `_pedir_telegram_cli` con `isatty`, aquí para Tk.
        print(f'instalar: sin ventana ({type(e).__name__}: {e}); mostrando --listar en su lugar\n')
        _listar(settings_ruta, skills_dir=skills_dir)
        sys.exit(0)
    ventana.mainloop()
