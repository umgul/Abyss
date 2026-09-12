"""rutas.py — el único sitio donde se decide dónde vive el CÓDIGO y dónde viven los DATOS.

El código se instala UNA VEZ (aquí, en `CODE`); los datos viven por proyecto, dentro de la
memoria automática de Claude Code para ese proyecto
(`~/.claude/projects/<proyecto-saneado>/memory/`). Todo guion que necesite datos debe
llamar a `resolver()` y nunca calcular `proj`/`mem` por su cuenta.

Orden de resolución de `proj` (se prueba en este orden; el primero que responde gana,
nunca se combinan ni se adivina uno por defecto):

  1. `dirname(transcript_path)` del JSON de stdin que manda el gancho de Claude Code.
     Es la fuente más de fiar: Claude Code ya escribió ese transcript bajo
     `~/.claude/projects/<proyecto-saneado>/`, así que su carpeta contenedora ES el
     proyecto, sin sanear nada más.
  2. `cwd` del mismo JSON de stdin, SANEADO exactamente como lo sanea Claude Code para
     nombrar la carpeta de un proyecto: `re.sub(r"[^A-Za-z0-9]", "-", cwd)` (todo lo que
     no sea letra o dígito se vuelve un guion — así `C:\\Program Files\\Git\\cmd` se
     convierte en `C--Program-Files-Git-cmd`), buscado bajo `~/.claude/projects/`.
  3. `--proyecto <cwd>` en la línea de comandos: incluye el mismo `<cwd>` que mandaría
     el gancho, así que recibe el MISMO saneado que (2) y se busca en el mismo sitio.
     Sirve para invocar un guion a mano con el cwd que habría llegado por stdin.
  4. Variable de entorno `ABYSS_PROYECTO`: a diferencia de (2) y (3), aquí se espera
     la ruta YA RESUELTA a la carpeta del proyecto (no un cwd, no se sanea) — para
     pruebas automatizadas o para que el instalador la fije sin pasar por stdin. Un
     nombre sin separadores se toma como carpeta bajo `~/.claude/projects/`, nunca
     relativo al cwd.

Si ninguna de las cuatro fuentes resuelve un proyecto, `resolver()` aborta (mensaje claro
por stderr y `sys.exit(1)`): sin proyecto no hay datos, nunca se inventa uno ni se cae a
un directorio por defecto (fail-closed).

`mem = proj/memory` se crea si no existe (es memoria de DATOS, no de código: nada del
paquete instalado escribe ahí salvo lo que cada pieza declare).

`CODE = dirname(__file__)` es la carpeta de este paquete tal como se instaló: solo
código: nada se escribe ahí salvo `config.json` (lo hace el instalador).
"""
import os
import re
import sys
import json
import time
import threading

CODE = os.path.dirname(os.path.abspath(__file__))
CLAUDE_PROJECTS = os.path.join(os.path.expanduser('~'), '.claude', 'projects')


def leer_stdin(tope_s=None):
    """JSON de stdin (lo que manda el gancho de Claude Code), tolerante: si stdin está
    vacío, cerrado o no trae JSON válido, devuelve {} en vez de reventar el gancho.

    Fail-closed también con un terminal interactivo: si stdin es (o parece) una tty,
    NO se lee (`.read()` se quedaría colgado esperando un EOF que nunca llega cuando
    alguien ejecuta un guion a mano) — se devuelve {} igual que con stdin vacío; quien
    llame usará --proyecto o ABYSS_PROYECTO (§1 de ESPECIFICACION.md).

    Con una TUBERÍA ABIERTA que nunca manda EOF, un `.read()` directo no vuelve jamás
    (p. ej. `subprocess.run` heredando el stdin del propio gancho si Claude Code no lo
    cierra). Se lee en un hilo aparte (daemon: no bloquea la salida del proceso aunque
    nunca termine) con `join(tope)`: si no ha acabado a tiempo, se abandona esa lectura
    y se devuelve {} igual que con stdin vacío — nunca se espera más de `tope` segundos
    (por defecto `ABYSS_TOPE_STDIN`, 3 s).

    LÍMITE: agotado el tope, el hilo daemon SIGUE vivo, bloqueado para siempre en
    `sys.stdin.read()` (no se puede matar un hilo desde fuera en Python) — el
    siguiente `import` que toque hilos (`import cv2`, en `ojo.py`) puede trabarse
    contra ese lector colgado y dejar el proceso entero sin avanzar; el tope evita el
    bloqueo EN `leer_stdin()`, pero no borra el hilo colgado que deja detrás. Por eso
    no se debe llamar a esta función cuando ya hay una pista directa de proyecto sin
    tocar stdin (`--proyecto` en argv o `ABYSS_PROYECTO` en el entorno): usa
    `leer_stdin_si_hace_falta()` en vez de esta, salvo que de verdad quieras forzar la
    lectura."""
    try:
        if sys.stdin is None or sys.stdin.isatty():
            return {}
        tope = tope_s if tope_s is not None else float(os.environ.get('ABYSS_TOPE_STDIN', 3.0))
        leido = {}

        def _leer():
            try:
                leido['texto'] = sys.stdin.read()
            except Exception:
                leido['texto'] = ''

        hilo = threading.Thread(target=_leer, daemon=True)
        hilo.start()
        hilo.join(tope)
        if hilo.is_alive():
            return {}  # tubería abierta que no manda EOF a tiempo: como si no hubiera JSON de gancho
        return json.loads(leido.get('texto') or '{}')
    except Exception:
        return {}


def _tiene_pista_directa(argv):
    """¿Ya hay de dónde sacar `proj` SIN tocar stdin? (orden 3 y 4 de `resolver()`:
    `--proyecto <cwd>` en `argv`, o `ABYSS_PROYECTO` ya puesto en el entorno). No
    mira los órdenes 1/2 (`transcript_path`/`cwd` del propio JSON de stdin) porque
    esos SÍ necesitan leer stdin — es la comprobación que hace innecesario leerlo."""
    return '--proyecto' in argv or bool(os.environ.get('ABYSS_PROYECTO'))


def leer_stdin_si_hace_falta(argv=None, tope_s=None):
    """Como `leer_stdin()`, pero se ahorra la lectura ENTERA cuando `argv`/el entorno ya
    traen una pista directa de proyecto (`_tiene_pista_directa`): los órdenes 1/2 de
    `resolver()` no hacen falta, así que no hay motivo para tocar stdin ni para
    arriesgarse al hilo lector colgado que puede dejar `leer_stdin()` (ver su
    docstring). Devuelve {} sin leer en ese caso; si no hay pista directa, delega en
    `leer_stdin()` como siempre.

    La llama `resolver()` cuando no le pasan `stdin_json`, y los guiones con gancho que
    necesitan leer el JSON de stdin ellos mismos para otros campos además de
    `proj`/`mem` (`session_id`, `cwd`…: `continuidad.py`, `vigia.py`)."""
    if argv is None:
        argv = sys.argv[1:]
    if _tiene_pista_directa(argv):
        return {}
    return leer_stdin(tope_s)


class Presupuesto:
    """Reloj de cuenta atrás COMPARTIDO entre varias llamadas de red de una misma
    invocación de un gancho (--arranque, --despertar): con la red en agujero negro
    (wifi caída, portal cautivo, cortafuegos) cada conexión puede consumir su timeout
    entero, y sin presupuesto compartido el total crece con el NÚMERO de llamadas
    (ipinfo + portada + hasta 8 temas), no con un tope fijo — puede superar el timeout
    de 60 s del propio gancho SessionStart y perder el JSON de `additionalContext`.

    `restante(tope)`: segundos que quedan, capados por `tope`; si ya no queda nada,
    lanza `TimeoutError` SIN que quien llama intente la red — así, agotado el
    presupuesto, las llamadas siguientes fallan al instante, no cada una con su
    propio timeout completo."""

    def __init__(self, segundos):
        self.limite = time.monotonic() + max(0.0, segundos)

    def restante(self, tope=None):
        r = self.limite - time.monotonic()
        if r <= 0:
            raise TimeoutError('presupuesto de red agotado')
        return min(r, tope) if tope is not None else r

    def agotado(self):
        return time.monotonic() >= self.limite


def _normalizar_estilo_posix_de_windows(cwd):
    """Un `cwd` en estilo MSYS/Git-Bash (`/c/Proyectos/Mi App`) o Cygwin
    (`/cygdrive/c/Proyectos/Mi App`) nombra la MISMA carpeta que su forma Windows
    (`C:\\Proyectos\\Mi App`) — pero saneado TAL CUAL da una carpeta de proyecto
    DISTINTA de la que usa el propio gancho de Claude Code (que manda `cwd` en forma
    Windows): la Bash que trae la herramienta Bash en Windows hace que `pwd` devuelva
    `/c/Users/...`, no `C:\\Users\\...`, y con las dos formas creando carpetas
    distintas, una orden con `--proyecto "$(pwd)"` lee y escribe en una memoria
    fantasma vacía. Se traduce ANTES de sanear para que las dos formas resuelvan la
    MISMA carpeta.

    SOLO en Windows (`os.name == 'nt'`): aplicar esta traducción en cualquier sistema
    trasladaría el mismo fallo a Linux/macOS al revés — una máquina Unix con un punto
    de montaje real de una sola letra bajo `/` (`/n`, `/e`, `/d`, habituales en NFS)
    sanearía distinto según pasara por aquí o no (`/n/repo` daría `N--repo` en vez de
    `-n-repo`), dos carpetas de memoria para el mismo proyecto. En Windows nadie tiene
    un directorio raíz `/n` de verdad; en Unix sí puede tenerlo, así que ahí esta
    traducción no debe tocar nada."""
    if os.name != 'nt':
        return cwd
    m = re.match(r'^/cygdrive/([A-Za-z])(/.*)?$', cwd)  # Cygwin: /cygdrive/c/resto
    if not m:
        m = re.match(r'^/([A-Za-z])(/.*)?$', cwd)  # MSYS/Git-Bash: /c o /c/resto
    if not m:
        return cwd
    resto = (m.group(2) or '').replace('/', '\\')
    return f'{m.group(1).upper()}:{resto}'


def _sanear_cwd(cwd):
    """Reproduce el saneado que hace Claude Code para nombrar la carpeta de un proyecto
    bajo ~/.claude/projects/: cualquier carácter que no sea A-Za-z0-9 se vuelve '-'."""
    cwd = _normalizar_estilo_posix_de_windows(cwd)
    return re.sub(r'[^A-Za-z0-9]', '-', cwd)


def resolver(argv=None, stdin_json=None):
    """Resuelve `(proj, mem)` por el orden fijado arriba y en ESPECIFICACION.md §1.

    `argv` por defecto es `sys.argv[1:]`. `stdin_json` por defecto es
    `leer_stdin_si_hace_falta(argv)` — que NO toca stdin en absoluto si `argv`/el
    entorno ya traen `--proyecto`/`ABYSS_PROYECTO` (pásalo tú mismo si ya lo leíste
    antes, para no consumir stdin dos veces).

    Comprueba, en orden, hasta que uno responda:
      1. `stdin_json['transcript_path']` → `proj = dirname(abspath(transcript_path))`.
      2. `stdin_json['cwd']` saneado → `proj = CLAUDE_PROJECTS/<saneado>`.
      3. `--proyecto <cwd>` en `argv` → mismo saneado que (2).
      4. `os.environ['ABYSS_PROYECTO']` → es `proj` (una ruta); un nombre sin
         separadores se toma como `CLAUDE_PROJECTS/<nombre>`, nunca relativo al cwd.

    Crea `mem = proj/memory` si no existe y devuelve `(proj, mem)`.

    Si nada resuelve, escribe el motivo por stderr y hace `sys.exit(1)`: sin proyecto
    no hay datos, no hay valor por defecto que inventar.
    """
    if argv is None:
        argv = sys.argv[1:]
    if stdin_json is None:
        stdin_json = leer_stdin_si_hace_falta(argv)
    stdin_json = stdin_json or {}

    proj = None

    tp = stdin_json.get('transcript_path')
    if tp:
        proj = os.path.dirname(os.path.abspath(tp))

    if not proj:
        cwd = stdin_json.get('cwd')
        if cwd:
            proj = os.path.join(CLAUDE_PROJECTS, _sanear_cwd(cwd))

    if not proj and '--proyecto' in argv:
        i = argv.index('--proyecto')
        if i + 1 < len(argv):
            proj = os.path.join(CLAUDE_PROJECTS, _sanear_cwd(argv[i + 1]))

    if not proj:
        var = os.environ.get('ABYSS_PROYECTO')
        if var:
            proj = var if ('/' in var or os.sep in var) else os.path.join(CLAUDE_PROJECTS, var)

    if not proj:
        sys.stderr.write(
            'abyss: sin proyecto no hay datos '
            '(ni transcript_path, ni cwd, ni --proyecto, ni ABYSS_PROYECTO)\n'
        )
        sys.exit(1)

    proj = os.path.abspath(proj)
    mem = os.path.join(proj, 'memory')
    os.makedirs(mem, exist_ok=True)
    return proj, mem


def es_transcript(x):
    """¿Es `x` un argumento posicional válido como transcript_path? Ni una bandera
    (empieza por '--'), ni un directorio, ni una cadena cualquiera cuelan: tiene que
    EXISTIR COMO FICHERO y terminar en `.jsonl`. Lo usan `exterocepcion.py`,
    `modelo.py` y `noticias.py` en su `__main__` antes de meter un positional en
    `stdin_json['transcript_path']` para `resolver()` — sin esta comprobación, una
    bandera como `--proyecto` o un directorio como `.` colarían como transcript_path
    y crearían `memory/` en el sitio equivocado en vez de caer a `--proyecto <valor>`
    o `ABYSS_PROYECTO` como toca."""
    return bool(x) and isinstance(x, str) and not x.startswith('--') and os.path.isfile(x) and x.endswith('.jsonl')


def es_mio(transcript_path, cwd, proj):
    """¿Pertenece este hilo (transcript_path/cwd tal como los manda un gancho) a `proj`?

    Sin adivinar: por la ruta del transcript, o por el `cwd` saneado como lo sanea
    Claude Code. Si no se puede determinar ninguna de las dos, NO es mío (fail-closed:
    en cualquier otro proyecto, silencio)."""
    if transcript_path and os.path.normcase(os.path.dirname(os.path.abspath(transcript_path))) == \
            os.path.normcase(os.path.abspath(proj)):
        return True
    if cwd and _sanear_cwd(cwd) == os.path.basename(os.path.abspath(proj)):
        return True
    return False
