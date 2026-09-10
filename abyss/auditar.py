# -*- coding: utf-8 -*-
"""Auditar: las cinco comprobaciones de Cohen sobre un paquete, con evidencia.

    python auditar.py <ruta_de_paquete> [--json] [--markdown salida.md]

Motivo: el incidente que cuenta Yonathan Cohen es
que a alguien lo comprometieron con un comando que le dio su propia IA, apuntando a
un dominio copia. Esto es la misma pregunta aplicada a un paquete ENTERO antes de
instalarlo: ¿de dónde viene, qué ejecuta y cuándo, qué toca fuera de su carpeta,
adónde manda datos, y qué dominios hay que leer con lupa? Cinco comprobaciones,
cada una con FICHERO y LÍNEA como evidencia — nunca una promesa ni una nota de
confianza.

NUNCA ejecuta el código del paquete auditado (ni lo importa, ni lo corre): todo
sale de leer texto y, para el historial, de `git log` LOCAL sobre el propio
`.git` del paquete (`git log` no toca ningún remoto — sigue siendo "sin red").
Auditar un paquete malicioso con este guion no lo dispara: solo se lee.

Las cinco comprobaciones (§comprobación N — cada una devuelve su propio dict
con `evidencia` y, si procede, `hallazgos`):

  1. **Procedencia**: `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
     `package.json`, `pyproject.toml` (los que existan) — ¿hay un autor con nombre
     real (no un hueco de plantilla: `<tu nombre>`, `TODO`, vacío...), un
     repositorio/homepage, una licencia? Con `.git`: número de commits y fecha del
     primero (`git log`, LOCAL, ver arriba). Un paquete sin autor NI historia de
     commits es de nadie — verificado sobre la máquina de desarrollo el 7-sep:
     `pyproject.toml` usa `tomllib` (biblioteca estándar, Python 3.11+); sin él, un
     lector de respaldo por regex, más pobre, declarado como tal en el propio
     resultado (`_regex_fallback`).
  2. **Comandos**: qué corre y cuándo. Lee `hooks/hooks.json`, `settings.json` y
     `.claude/settings.json` (los que haya, formato de plugin CON clave `hooks` o
     el más plano de `docs/ganchos_settings_ejemplo.json`) y lista cada evento con
     su comando y línea; marca los que disparan en CADA mensaje
     (`UserPromptSubmit`) o tras CADA herramienta (`PreToolUse`/`PostToolUse` SIN
     `matcher` que los restrinja) — si ese gancho no aparece nombrado (ni su
     fichero) en ningún `README*` del paquete, es un hallazgo `rompe` (corre
     siempre y en silencio). Además busca en el código llamadas a `subprocess`,
     `os.system`, `eval`, `exec`, y líneas de descarga-con-tubería-a-un-intérprete
     (`curl/wget/iwr/irm | bash/sh/iex`) — como EVIDENCIA (no todo uso de
     `subprocess` es malo), para que quien lea las vea todas juntas.
  3. **Permisos**: qué escribe FUERA de su propia carpeta — rutas bajo `~/.claude`,
     `settings.json`, el registro de Windows (`HKCU`/`HKLM`/`winreg`/`reg add`), o
     una ruta absoluta pasada a una llamada de escritura — y si el paquete declara
     en algún `README*` cómo deshacerlo (palabras como "desinstalar", "revertir",
     "manifiesto", "backup"...). Escribir fuera Y no declarar cómo deshacerlo es
     `rompe`; escribir fuera con un README que sí lo explica no genera hallazgo
     (es evidencia igualmente, para poder leerla).
  4. **Qué sale de la máquina** (la comprobación que importa de verdad): TODOS
     los hosts de red del paquete — no solo el CÓDIGO: `EXT_RED` (arreglo posterior
     al primer informe) es `EXT_CODIGO` MÁS los ficheros de datos y configuración
     (`.json`, `.yaml`/`.yml`, `.toml`, `.ini`, `.cfg`, `.env`, `.txt`, `.bat`/`.cmd`),
     porque un host puesto en `config/ajustes.json` y leído por el código con
     `cfg['endpoint']` es tan "qué sale de la máquina" como uno escrito a mano en un
     `.py`, y antes de este arreglo pasaba entero sin verse (medido: caso real
     reportado, ver `pruebas/test_auditar.py`). Quedan FUERA los propios
     `RUTAS_MANIFIESTO` (`package.json`, `pyproject.toml`...): su
     `repository`/`homepage` ya lo lee la comprobación 1, y sus dominios entran
     en la comprobación 5 tal cual — meterlos también aquí convertiría
     cualquier `repository` de GitHub legítimo en un "host oculto". Se busca
     una URL completa en cualquier parte del fichero, o el primer argumento de
     una llamada reconocida
     (`urlopen`/`requests.*`/`fetch`/`axios.*`/sockets) sin esquema — agrupados por
     host, y CONTRASTADOS contra el texto de `README*`: un host que el código usa y
     ningún README nombra es un hallazgo `rompe`, con fichero y línea de cada
     aparición. Esta es la comprobación que ningún antivirus hace. `vendor/dist/build`
     se leen APARTE (`extraer_hosts_terceros_embebidos`, `hosts_terceros_embebidos`
     en el resultado): terceros embebidos no son "el código de este paquete" y por
     eso nunca cuentan como hallazgo contra el README, pero antes de este arreglo se
     saltaban EN SILENCIO — ahora se declaran, con sus hosts, para que un informe
     "sin hallazgos" no sea indistinguible de "no miré ahí".
  5. **Dominio**: reúne los dominios que aparecen en `README*` y en los manifiestos
     (de instalación, de proveedor...) para que una persona los compare CARÁCTER A
     CARÁCTER. Nunca genera un hallazgo: el propio límite es el resultado —
     `pollinations.ai` y `pollinations.ai` se leen igual de rápido y el guion no
     sabe distinguirlos.

Veredicto en tres niveles (como `/esceptico`, con otro vocabulario para
paquetes): **rompe** (hace algo que no declara: comprobaciones 2-4), **engaña**
(declara algo que no cumple — no se infiere aquí de forma automática: hace falta
saber qué afirma el README para saber que miente, y eso lo lee una persona o el
Opus de `/esceptico --paquete`, no un regex; queda declarado como límite, no
fingido con una heurística frágil) y **roza** (procedencia floja pero con algo de
rastro: falta un campo, o falta autor pero hay `.git` con commits reales). El
veredicto global es el peor hallazgo de las comprobaciones 1-4; sin ninguno,
`"sin hallazgos"` — nunca un "roza" de relleno cuando no hay nada que decir.

Límite declarado de TODO este guion, secamente: es texto y regex, no un parser ni
un sandbox — un comentario que solo MENCIONA una URL de ejemplo (para explicarla,
o para demostrar que se ha quitado antes de escribirla en otro sitio, como hace
`render3d.py` con la URL de `three.js`) cuenta igual que una llamada real, y una
URL construida por concatenación en dos líneas no se ve. Se prefiere un candidato
de más para que lo descarte quien lee, a un host real que se cuele sin que nadie
lo mire — la misma filosofía que `vigia.py` declara para sus propias cazas.

Y el límite simétrico, el que motivó el arreglo posterior al primer informe: un
"sin hallazgos" NUNCA debe leerse como "no hay nada" cuando en realidad es "esta
vara no mira ahí". Por eso `a_texto()`/`a_markdown()` nunca imprimen "sin
hallazgos" a secas — dicen "sin hallazgos EN LO QUE ESTA VARA MIRA" y listan
debajo, siempre, qué extensiones quedan fuera de `EXT_RED`, qué carpetas no se
leen ni siquiera como terceros (`EXCLUIR_DIRS_SIEMPRE`) y que una URL partida por
concatenación no se reconoce — la misma disciplina que `vigia.py` aplica a sus
propios falsos negativos.

Diseño para las pruebas (igual que `mapa_codigo.py`/`huella.py`): todas las
funciones son puras y reciben `ruta` como argumento; nada se resuelve con
`rutas.resolver()` ni se lee de stdin — este guion no guarda nada en `mem` (no
mide el propio hilo, audita un paquete de terceros) y por eso no necesita
proyecto. Solo `if __name__ == '__main__':` toca argv/stdout/ficheros de salida.
"""
import sys
try:                       # la consola de Windows y la salida tienen que hablar
    from . import consola  # el mismo idioma: ver abyss/consola.py
except ImportError:
    import consola
consola.preparar()
import os
import re
import json
import subprocess
import urllib.parse

# Carpetas que NUNCA se leen, ni siquiera como terceros embebidos (VCS, entornos
# instalados, caché): a diferencia de vendor/dist/build, no son contenido del
# paquete en sí, así que no hay nada que declarar sobre ellas más allá de esto.
EXCLUIR_DIRS_SIEMPRE = {'.git', 'venv', '.venv', 'node_modules', '__pycache__',
                        'site-packages', '.hg', '.svn'}
# vendor/dist/build SÍ son contenido del paquete (terceros embebidos): se excluyen
# de "código propio" (comprobaciones 2, 3 y la parte "propia" de la 4) pero la
# comprobación 4 los recorre APARTE (`_listar_ficheros_terceros_embebidos`) en vez
# de callarlos — ver docstring del módulo.
DIRS_TERCEROS_EMBEBIDOS = {'vendor', 'dist', 'build'}
# Las pruebas son contenido del paquete, pero sus hosts son ATREZO, no llamadas: un
# fichero que prueba a un auditor tiene que inventarse dominios para que los cace. Antes
# se contaban como hallazgos reales — medido el 8-sep-2026 auditando este mismo paquete:
# `api.declarado.com`, `api.oculto.net`, `api.sinesquema.io` y `cdn.de-terceros.example`
# salían acusando al paquete de llamar a sitios que no existen. Se leen APARTE y se
# declaran, con el mismo criterio que vendor/dist/build: nunca callarlas, nunca acusarlas.
DIRS_PRUEBAS = {'pruebas', 'tests', 'test'}
EXCLUIR_DIRS = EXCLUIR_DIRS_SIEMPRE | DIRS_TERCEROS_EMBEBIDOS | DIRS_PRUEBAS
EXT_CODIGO = {'.py', '.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs', '.ps1', '.sh', '.rb', '.go'}
# Ficheros de datos/configuración: la comprobación 4 también los
# lee, porque un host puesto aquí y leído por el código (`cfg['endpoint']`) sale
# de la máquina igual que uno escrito a mano en un `.py` — antes pasaba sin verse.
EXT_DATOS = {'.json', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.env', '.txt', '.bat', '.cmd'}
EXT_RED = EXT_CODIGO | EXT_DATOS

RUTAS_MANIFIESTO = ('.claude-plugin/plugin.json', '.claude-plugin/marketplace.json',
                     'package.json', 'pyproject.toml')
# Los propios manifiestos quedan FUERA de la comprobación 4 aunque su extensión
# (.json/.toml) esté en EXT_RED: su `repository`/`homepage` ya se lee en la
# comprobación 1, y sus dominios entran tal cual en la comprobación 5 para
# lectura carácter a carácter — contarlos también aquí convertiría cualquier
# `repository` legítimo de GitHub en un "host oculto", que no es lo que esta
# comprobación busca (config/datos propios que el código consulta para saber
# adónde mandar algo, como `config/ajustes.json` en el caso real reportado).
RUTAS_MANIFIESTO_NORM = {os.path.normpath(r) for r in RUTAS_MANIFIESTO}
FICHEROS_GANCHOS = ('hooks/hooks.json', 'settings.json', '.claude/settings.json')
EVENTOS_CADA_MENSAJE = {'UserPromptSubmit'}
EVENTOS_CADA_HERRAMIENTA = {'PreToolUse', 'PostToolUse'}

PLACEHOLDERS_AUTOR = {
    'tu nombre', 'your name', 'todo', 'tbd', 'n/a', 'na', 'unknown', 'anonymous', 'anónimo',
    'anonimo', 'el usuario', 'change me', 'changeme', 'first last', 'nombre apellido',
    'example', 'ejemplo', 'foo bar', 'test', '-',
}
PALABRAS_DESHACER = ('desinstalar', 'desinstalación', 'desinstalacion', 'deshacer', 'revertir',
                      'rollback', 'uninstall', 'undo', 'manifiesto', 'copia de seguridad', 'backup', '.bak')

RE_URL = re.compile(r'https?://[^\s\'"`)>\]}\\]+')
RE_LLAMADA_HOST = re.compile(
    r'(?:requests\.\w+|urlopen|fetch|axios\.\w+|http\.client\.HTTPS?Connection|'
    r'socket\.create_connection)\(\s*\(?\s*[\'"]([^\'"]+)[\'"]', re.I)
RE_PELIGROSO = re.compile(
    r'(subprocess\.\w+|os\.system\(|[^.\w]eval\(|[^.\w]exec\(|Invoke-Expression|(?<!\w)iex\s|powershell\s+-enc)', re.I)
RE_DESCARGA_EJECUTABLE = re.compile(
    r'(curl|wget|iwr|invoke-webrequest|irm|invoke-restmethod)\b[^\n|]*\|\s*(bash|sh|iex|powershell)', re.I)
RE_ESCRITURA = re.compile(
    r'(open\([^)]*[\'"]w|write_text|writetext|os\.remove\(|os\.unlink\(|shutil\.(move|copy\w*)\(|'
    r'Set-Content|Out-File|New-Item|Remove-Item|reg\s+add|New-ItemProperty|Set-ItemProperty|'
    r'WriteAllText|writeFileSync|fs\.writeFile)', re.I)
RE_FUERA_DE_CARPETA = re.compile(
    r'(~[\\/]\.claude\b|\.claude[\\/](?!plugin)|\bsettings\.json\b|\bHKCU\b|\bHKLM\b|\bHKEY_[A-Z_]+\b|'
    r'\bwinreg\b|%APPDATA%|expanduser\([\'"]~)', re.I)

ORDEN_SEVERIDAD = {'rompe': 3, 'engaña': 2, 'roza': 1}
HOSTS_QUE_NO_SALEN = {'localhost', '127.0.0.1', '0.0.0.0', '::1'}  # nunca salen de la máquina: no son "comprobación 4"


# ---------- lectura de ficheros (nunca ejecuta nada) ----------

def _leer_texto(ruta_fichero):
    try:
        with open(ruta_fichero, encoding='utf-8-sig', errors='replace') as fh:
            return fh.read()
    except OSError:
        return ''


def _listar_ficheros(ruta, extensiones, excluir=EXCLUIR_DIRS):
    """Rutas absolutas de todos los ficheros bajo `ruta` cuya extensión está en
    `extensiones`, sin bajar a las carpetas de `excluir` (a cualquier
    profundidad; por defecto `EXCLUIR_DIRS` — código y datos PROPIOS del
    paquete, nunca `vendor/dist/build`)."""
    for raiz, dirs, ficheros in os.walk(ruta):
        dirs[:] = [d for d in dirs if d not in excluir]
        for nombre in sorted(ficheros):
            if os.path.splitext(nombre)[1].lower() in extensiones:
                yield os.path.join(raiz, nombre)


def _listar_ficheros_terceros_embebidos(ruta, extensiones):
    """Como `_listar_ficheros`, pero SOLO lo que cae bajo alguna carpeta
    `vendor/`, `dist/` o `build/` de `ruta` (a cualquier profundidad) — usada
    por la comprobación 4 para declarar esos hosts APARTE en vez
    de saltárselos en silencio como hacían las comprobaciones 2 y 3. Sigue sin
    bajar a `EXCLUIR_DIRS_SIEMPRE` (un `.git` o `node_modules` anidado dentro de
    `vendor/` tampoco es contenido legible del paquete)."""
    for raiz, dirs, ficheros in os.walk(ruta):
        dirs[:] = [d for d in dirs if d not in EXCLUIR_DIRS_SIEMPRE]
        partes = set(os.path.relpath(raiz, ruta).replace(os.sep, '/').split('/'))
        if not (partes & DIRS_TERCEROS_EMBEBIDOS):
            continue
        for nombre in sorted(ficheros):
            if os.path.splitext(nombre)[1].lower() in extensiones:
                yield os.path.join(raiz, nombre)


def _listar_ficheros_de_pruebas(ruta, extensiones):
    """Hermano de `_listar_ficheros_terceros_embebidos`, pero para `DIRS_PRUEBAS`.
    Mismo trato y por la misma razón: son contenido del paquete, pero sus hosts son
    atrezo. Se leen para declararlos, nunca para acusar."""
    for raiz, dirs, ficheros in os.walk(ruta):
        dirs[:] = [d for d in dirs if d not in EXCLUIR_DIRS_SIEMPRE]
        partes = set(os.path.relpath(raiz, ruta).replace(os.sep, '/').split('/'))
        if not (partes & DIRS_PRUEBAS):
            continue
        for nombre in sorted(ficheros):
            if os.path.splitext(nombre)[1].lower() in extensiones:
                yield os.path.join(raiz, nombre)


def _texto_readmes(ruta):
    """Concatena el texto de todo `README*` en la RAÍZ de `ruta` (no de
    subcarpetas: un README de una carpeta ajena dentro del paquete no cuenta como
    documentación del paquete completo). Se usa siempre en minúsculas para
    comparar sin distinguir mayúsculas."""
    textos = []
    try:
        nombres = os.listdir(ruta)
    except OSError:
        return ''
    for nombre in sorted(nombres):
        if nombre.upper().startswith('README'):
            p = os.path.join(ruta, nombre)
            if os.path.isfile(p):
                textos.append(_leer_texto(p))
    return '\n'.join(textos)


def _texto_docs_deshacer(ruta):
    """README* más cualquier fichero de la raíz que empiece por
    MANIFEST/UNINSTALL/INSTALL/CHANGELOG — donde un paquete honesto suele decir
    cómo deshacer lo que instala, si lo dice en algún sitio."""
    textos = [_texto_readmes(ruta)]
    try:
        nombres = os.listdir(ruta)
    except OSError:
        nombres = []
    for nombre in sorted(nombres):
        if nombre.upper().startswith(('MANIFEST', 'UNINSTALL', 'INSTALL', 'CHANGELOG')):
            p = os.path.join(ruta, nombre)
            if os.path.isfile(p):
                textos.append(_leer_texto(p))
    return '\n'.join(textos)


def _linea_de_comando_json(texto_json, comando):
    """Línea del `command` de un gancho DENTRO del JSON crudo del fichero. El
    `comando` que entrega `json.loads()` ya no lleva las comillas escapadas
    (`\\"`) que sí tiene el fichero en disco (los ganchos reales casi siempre
    envuelven la ruta entre comillas, `python \"...\" --flag`) — medido: buscar
    el comando tal cual contra `hooks/hooks.json` de este mismo repo no
    encontraba NINGUNA línea. Se re-escapa con `json.dumps` (la misma regla de
    escape que usa cualquier JSON válido) antes de buscarlo."""
    if not comando:
        return None
    return _linea_de_texto(texto_json, json.dumps(comando)[1:-1][:80])


def _linea_de_texto(texto, patron):
    """Línea (1-based) de la primera aparición literal de `patron` en `texto`, o
    `None` si no aparece o `texto` está vacío. Subcadena literal, no regex."""
    if not texto or not patron:
        return None
    idx = texto.find(patron)
    if idx == -1:
        return None
    return texto.count('\n', 0, idx) + 1


# ---------- comprobación 1: procedencia ----------

def _parsear_pyproject_regex(texto):
    """Lector de respaldo SIN `tomllib` (Python < 3.11): no interpreta TOML de
    verdad, solo busca como texto plano las claves que esta comprobación mira.
    Declarado como degradado (`_regex_fallback`): falla con TOML anidado o con
    comillas o comentarios en medio del valor."""
    def _valor(clave):
        m = re.search(r'(?m)^\s*' + re.escape(clave) + r'\s*=\s*(.+)$', texto)
        return m.group(1).strip() if m else None
    return {
        '_regex_fallback': True,
        'project': {'authors': _valor('authors'), 'license': _valor('license')},
        'tool': {'poetry': {'authors': _valor('authors'), 'license': _valor('license'),
                             'repository': _valor('repository'), 'homepage': _valor('homepage')}},
    }


def _parsear_pyproject(texto):
    try:
        import tomllib
    except ImportError:
        return _parsear_pyproject_regex(texto), None
    try:
        return tomllib.loads(texto), None
    except Exception as e:
        return None, f'{type(e).__name__}: {e}'


def leer_manifiestos(ruta):
    """{ruta_relativa: {'ruta_abs','texto','datos','error'}} SOLO de los
    manifiestos de `RUTAS_MANIFIESTO` que existen bajo `ruta`. `datos` es `None`
    si el fichero no se pudo parsear (JSON roto; TOML solo si además falla el
    respaldo por regex, que no suele fallar del todo)."""
    out = {}
    for rel in RUTAS_MANIFIESTO:
        p = os.path.join(ruta, *rel.split('/'))
        if not os.path.isfile(p):
            continue
        texto = _leer_texto(p)
        if rel.endswith('.toml'):
            datos, error = _parsear_pyproject(texto)
        else:
            try:
                datos, error = json.loads(texto), None
            except Exception as e:
                datos, error = None, f'{type(e).__name__}: {e}'
        out[rel] = {'ruta_abs': p, 'texto': texto, 'datos': datos, 'error': error}
    return out


def _nombre_de(valor):
    """Aplana `author`/`owner`/`authors` (str, {'name':...}, o lista de esas dos
    formas — los tres formatos reales de `package.json`/`plugin.json`/pyproject
    con PEP 621 o Poetry) al primer nombre no vacío que encuentre, o `None`."""
    if valor is None:
        return None
    if isinstance(valor, str):
        m = re.match(r'^\s*([^<]+?)\s*(?:<.*>)?\s*$', valor)  # "Nombre <correo>" (npm) → "Nombre"
        nombre = (m.group(1) if m else valor).strip()
        return nombre or None
    if isinstance(valor, dict):
        return _nombre_de(valor.get('name'))
    if isinstance(valor, list):
        for v in valor:
            n = _nombre_de(v)
            if n:
                return n
    return None


def _autor_es_placeholder(nombre):
    """Comparación EXACTA contra `PLACEHOLDERS_AUTOR` (nunca subcadena: un nombre
    real puede contener por casualidad una de esas palabras — p. ej. "Ana
    Ejemplos" no es un hueco de plantilla solo porque contenga "ejemplo").
    Los huecos entre `<...>` sí se reconocen por forma, no por lista."""
    n = (nombre or '').strip().lower()
    if not n:
        return True
    if n.startswith('<') and n.endswith('>'):
        return True
    return n in PLACEHOLDERS_AUTOR


def _extraer_autor(rel, datos):
    rel = rel.replace('\\', '/')
    if rel.endswith('marketplace.json'):
        return datos.get('owner')
    if rel.endswith('plugin.json') or rel.endswith('package.json'):
        return datos.get('author')
    if rel.endswith('pyproject.toml'):
        proyecto = datos.get('project') or {}
        if proyecto.get('authors'):
            return proyecto['authors']
        poetry = ((datos.get('tool') or {}).get('poetry')) or {}
        return poetry.get('authors')
    return None


def _extraer_licencia(rel, datos):
    rel = rel.replace('\\', '/')
    if rel.endswith('plugin.json') or rel.endswith('package.json'):
        lic = datos.get('license')
        if isinstance(lic, dict):
            return lic.get('type')
        return lic
    if rel.endswith('pyproject.toml'):
        proyecto = datos.get('project') or {}
        lic = proyecto.get('license')
        if isinstance(lic, dict):
            return lic.get('text') or lic.get('file')
        if lic:
            return lic
        poetry = ((datos.get('tool') or {}).get('poetry')) or {}
        return poetry.get('license')
    return None


def _extraer_repo(rel, datos):
    rel = rel.replace('\\', '/')
    if rel.endswith('plugin.json'):
        return datos.get('repository') or datos.get('homepage')
    if rel.endswith('marketplace.json'):
        for p in (datos.get('plugins') or []):
            if isinstance(p, dict) and p.get('homepage'):
                return p['homepage']
        return None
    if rel.endswith('package.json'):
        repo = datos.get('repository')
        if isinstance(repo, dict):
            repo = repo.get('url')
        return repo or datos.get('homepage')
    if rel.endswith('pyproject.toml'):
        proyecto = datos.get('project') or {}
        urls = proyecto.get('urls') or {}
        for clave in ('Repository', 'repository', 'Homepage', 'homepage', 'Source', 'source'):
            if urls.get(clave):
                return urls[clave]
        poetry = ((datos.get('tool') or {}).get('poetry')) or {}
        return poetry.get('repository') or poetry.get('homepage')
    return None


def leer_git(ruta):
    """Historial de `.git` bajo `ruta`: número de commits y fecha ISO del primero,
    con `git log --format=%cI` — LOCAL sobre el repo ya presente en disco (`git
    log` no consulta ningún remoto: sigue siendo "sin red"). Sin `.git`:
    `hay_git=False`. Con `.git` pero sin `git` en PATH, con el comando fallando, o
    agotado el tiempo (10 s): `sin_dato` con el motivo — nunca se inventa un
    número de commits."""
    if not os.path.isdir(os.path.join(ruta, '.git')):
        return {'hay_git': False, 'commits': None, 'primer_commit': None, 'sin_dato': None}
    try:
        r = subprocess.run(['git', '-C', ruta, 'log', '--format=%cI'],
                            capture_output=True, text=True, timeout=10)
    except FileNotFoundError:
        return {'hay_git': True, 'commits': None, 'primer_commit': None,
                'sin_dato': 'sin dato: git no está en PATH'}
    except subprocess.TimeoutExpired:
        return {'hay_git': True, 'commits': None, 'primer_commit': None,
                'sin_dato': 'sin dato: git log no respondió a tiempo (10 s)'}
    if r.returncode != 0:
        return {'hay_git': True, 'commits': None, 'primer_commit': None,
                'sin_dato': f'sin dato: git log devolvió el código {r.returncode}'}
    fechas = [l for l in r.stdout.splitlines() if l.strip()]
    return {'hay_git': True, 'commits': len(fechas),
            'primer_commit': fechas[-1] if fechas else None, 'sin_dato': None}


def comprobar_procedencia(ruta, manifiestos, git_info):
    autores, licencias, repos, evidencia = [], [], [], []
    for rel, m in manifiestos.items():
        rel_norm = rel.replace('\\', '/')
        if m['datos'] is None:
            evidencia.append({'fichero': rel_norm, 'linea': 1, 'nota': f"no se pudo leer: {m['error']}"})
            continue
        clave_autor = 'owner' if rel_norm.endswith('marketplace.json') else 'author'
        autor = _nombre_de(_extraer_autor(rel, m['datos']))
        autores.append({'fichero': rel_norm, 'linea': _linea_de_texto(m['texto'], f'"{clave_autor}"'),
                         'valor': autor, 'placeholder': _autor_es_placeholder(autor)})
        licencias.append({'fichero': rel_norm, 'valor': _extraer_licencia(rel, m['datos'])})
        repos.append({'fichero': rel_norm, 'valor': _extraer_repo(rel, m['datos'])})

    hay_autor_real = any(a['valor'] and not a['placeholder'] for a in autores)
    hay_licencia = any(l['valor'] for l in licencias)
    hay_repo = any(r['valor'] for r in repos)
    sin_historia = not git_info['hay_git'] or not git_info['commits']

    hallazgos = []
    if not hay_autor_real:
        if autores:
            resumen = 'ningún manifiesto declara un autor con nombre real (vacío o placeholder de plantilla)'
            fichero, linea = autores[0]['fichero'], autores[0]['linea']
        elif manifiestos:
            resumen = 'el manifiesto encontrado no se pudo leer (ver evidencia) y no hay otro que declare autor'
            primero = next(iter(manifiestos)).replace('\\', '/')
            fichero, linea = primero, 1
        else:
            resumen = ('no hay ningún manifiesto de procedencia bajo el paquete '
                       '(.claude-plugin/plugin.json, package.json, pyproject.toml)')
            fichero, linea = None, None
        resumen += ' y sin historial de commits' if sin_historia else \
            f" (sí hay {git_info['commits']} commit(s) de git, desde {git_info['primer_commit']}: hay trazabilidad)"
        hallazgos.append({'comprobacion': 'procedencia', 'severidad': 'rompe' if sin_historia else 'roza',
                           'resumen': resumen, 'fichero': fichero, 'linea': linea})
    if manifiestos and not hay_licencia:
        hallazgos.append({'comprobacion': 'procedencia', 'severidad': 'roza',
                           'resumen': 'ningún manifiesto declara licencia',
                           'fichero': next(iter(manifiestos)).replace('\\', '/'), 'linea': None})
    if manifiestos and not hay_repo:
        hallazgos.append({'comprobacion': 'procedencia', 'severidad': 'roza',
                           'resumen': 'ningún manifiesto declara repositorio ni homepage',
                           'fichero': next(iter(manifiestos)).replace('\\', '/'), 'linea': None})

    return {'manifiestos_encontrados': [r.replace('\\', '/') for r in manifiestos],
            'autores': autores, 'licencias': licencias, 'repos': repos, 'git': git_info,
            'evidencia': evidencia, 'hallazgos': hallazgos}


# ---------- comprobación 2: comandos ----------

def _nombre_script(comando):
    m = re.search(r'([^\s"\']+\.(?:py|ps1|sh|js|mjs|cjs))\b', comando or '', re.I)
    return os.path.basename(m.group(1)) if m else None


def _grupos_de_eventos(datos):
    """{evento: [grupo, ...]} de un fichero de ganchos ya parseado — formato de
    plugin (clave `hooks` con los eventos dentro, igual en `hooks/hooks.json` y en
    el `settings.json` real que escribe `instalar.py`) o el más plano donde los
    eventos están en el nivel superior (visto en `docs/ganchos_settings_ejemplo.json`
    y en paquetes de terceros). Un elemento de la lista con `command` pero sin
    `hooks` se trata como un grupo de un solo hook sin `matcher`."""
    base = datos.get('hooks') if isinstance(datos.get('hooks'), dict) else datos
    out = {}
    if not isinstance(base, dict):
        return out
    for evento, grupos in base.items():
        if not isinstance(grupos, list):
            continue
        out[evento] = []
        for g in grupos:
            if not isinstance(g, dict):
                continue
            if isinstance(g.get('hooks'), list):
                out[evento].append(g)
            elif 'command' in g:
                out[evento].append({'hooks': [g]})
    return out


def _buscar_llamadas_peligrosas(ruta):
    out = []
    for p in _listar_ficheros(ruta, EXT_CODIGO):
        rel = os.path.relpath(p, ruta).replace(os.sep, '/')
        texto = _leer_texto(p)
        if not texto:
            continue
        for i, linea in enumerate(texto.splitlines(), 1):
            if RE_PELIGROSO.search(linea):
                out.append({'fichero': rel, 'linea': i, 'nota': 'llamada a subprocess/os.system/eval/exec',
                             'texto': linea.strip()[:160]})
            if RE_DESCARGA_EJECUTABLE.search(linea):
                out.append({'fichero': rel, 'linea': i,
                             'nota': 'descarga con tubería a un intérprete (curl/wget/iwr/irm | bash/sh/iex)',
                             'texto': linea.strip()[:160]})
    return out


def comprobar_comandos(ruta):
    evidencia, hallazgos = [], []
    texto_readmes = _texto_readmes(ruta).lower()
    for rel in FICHEROS_GANCHOS:
        p = os.path.join(ruta, *rel.split('/'))
        if not os.path.isfile(p):
            continue
        texto = _leer_texto(p)
        try:
            datos = json.loads(texto)
        except Exception as e:
            evidencia.append({'fichero': rel, 'linea': 1, 'nota': f'no es JSON válido: {e}'})
            continue
        for evento, grupos in _grupos_de_eventos(datos).items():
            cada_mensaje = evento in EVENTOS_CADA_MENSAJE
            for grupo in grupos:
                sin_matcher = not grupo.get('matcher') or grupo.get('matcher') == '*'
                cada_herramienta = evento in EVENTOS_CADA_HERRAMIENTA and sin_matcher
                for h in grupo.get('hooks', []):
                    if not isinstance(h, dict):
                        continue
                    comando = h.get('command') or ''
                    linea = _linea_de_comando_json(texto, comando)
                    evidencia.append({'fichero': rel, 'linea': linea, 'evento': evento, 'comando': comando,
                                       'cada_mensaje': cada_mensaje, 'cada_herramienta': cada_herramienta})
                    if not (cada_mensaje or cada_herramienta):
                        continue
                    base_nombre = _nombre_script(comando)
                    declarado = bool(base_nombre) and base_nombre.lower() in texto_readmes
                    if not declarado:
                        cuando = 'en cada mensaje' if cada_mensaje else 'tras cada herramienta'
                        hallazgos.append({
                            'comprobacion': 'comandos', 'severidad': 'rompe',
                            'resumen': f'gancho de {evento} ({base_nombre or comando[:60] or "sin comando"}) '
                                       f'corre {cuando} y no aparece nombrado en ningún README del paquete',
                            'fichero': rel, 'linea': linea,
                        })
    evidencia.extend(_buscar_llamadas_peligrosas(ruta))
    return {'evidencia': evidencia, 'hallazgos': hallazgos}


# ---------- comprobación 3: permisos ----------

def comprobar_permisos(ruta):
    """Evidencia de escritura fuera de la carpeta del paquete. Dos pasos, no uno
    solo: primero, ¿este FICHERO escribe algo en absoluto en algún sitio
    (`RE_ESCRITURA`, en cualquier línea)? Si no, se salta entero (más rápido, y
    una ruta sin más contexto en un fichero que nunca escribe nada no es una
    escritura). Si sí, cada línea que además nombre una ruta fuera de la carpeta
    (`RE_FUERA_DE_CARPETA`) es evidencia — AUNQUE la propia llamada de escritura
    esté unas líneas más abajo (medido: la ruta y el `open(..., 'w')` casi
    siempre caen en líneas distintas — `p = os.path.expanduser(...)` y luego
    `open(p, 'w')` — exigir las dos cosas en la MISMA línea no encontraba nada de
    esto). Sigue siendo una heurística declarada: puede colar un fichero que solo
    MENCIONA esa ruta sin escribir ahí (falso positivo) o perderse una ruta
    construida por partes (falso negativo)."""
    evidencia = []
    for p in _listar_ficheros(ruta, EXT_CODIGO):
        rel = os.path.relpath(p, ruta).replace(os.sep, '/')
        texto = _leer_texto(p)
        if not texto or not RE_ESCRITURA.search(texto):
            continue
        for i, linea in enumerate(texto.splitlines(), 1):
            if RE_FUERA_DE_CARPETA.search(linea):
                evidencia.append({'fichero': rel, 'linea': i, 'texto': linea.strip()[:160]})
    declara_deshacer = any(p in _texto_docs_deshacer(ruta).lower() for p in PALABRAS_DESHACER)
    hallazgos = []
    if evidencia and not declara_deshacer:
        primero = evidencia[0]
        hallazgos.append({
            'comprobacion': 'permisos', 'severidad': 'rompe',
            'resumen': f'escribe fuera de su propia carpeta ({len(evidencia)} sitio(s) detectado(s)) '
                       'sin declarar en ningún README cómo deshacerlo',
            'fichero': primero['fichero'], 'linea': primero['linea'],
        })
    return {'evidencia': evidencia[:20], 'total_evidencia': len(evidencia),
            'declara_deshacer': declara_deshacer, 'hallazgos': hallazgos}


# ---------- comprobación 4: qué sale de la máquina ----------

def normalizar_host(host_o_url):
    """Host en minúsculas, sin `www.`, sin usuario/puerto/ruta — para comparar
    hosts entre sí sin que un puerto o una barra final cuenten como distinto."""
    valor = host_o_url if '://' in host_o_url else 'http://' + host_o_url
    try:
        neto = urllib.parse.urlsplit(valor).netloc or host_o_url
    except Exception:
        neto = host_o_url
    neto = neto.split('@')[-1].split(':')[0].strip().lower()
    return neto[4:] if neto.startswith('www.') else neto


def _hosts_en_ficheros(ficheros, ruta):
    """{host: [(fichero_relativo, línea), ...]} de los `ficheros` dados (rutas
    absolutas bajo `ruta`), excepto `HOSTS_QUE_NO_SALEN` (loopback: nunca salen
    de la máquina). Compartida por `extraer_hosts_codigo` y
    `extraer_hosts_terceros_embebidos` — misma lectura, distinto barrido de
    carpetas. Ver el límite declarado en el docstring del módulo: es un regex
    sobre texto, cuenta tanto una llamada real como una URL solo mencionada en
    un comentario, y no ve una URL partida por concatenación."""
    out = {}
    for p in ficheros:
        rel = os.path.relpath(p, ruta).replace(os.sep, '/')
        texto = _leer_texto(p)
        if not texto:
            continue
        for i, linea in enumerate(texto.splitlines(), 1):
            hosts_linea = set()
            for m in RE_URL.finditer(linea):
                hosts_linea.add(normalizar_host(m.group(0)))
            for m in RE_LLAMADA_HOST.finditer(linea):
                candidato = m.group(1)
                if '://' in candidato or re.match(r'^[\w.\-]+\.[a-zA-Z]{2,}', candidato):
                    hosts_linea.add(normalizar_host(candidato))
            for host in hosts_linea:
                if host and '.' in host and host not in HOSTS_QUE_NO_SALEN:
                    out.setdefault(host, []).append((rel, i))
    return out


def extraer_hosts_codigo(ruta):
    """{host: [(fichero_relativo, línea), ...]} del código Y de los ficheros de
    datos/configuración PROPIOS de `ruta` (`EXT_RED` = `EXT_CODIGO` más
    `.json`/`.yaml`/`.yml`/`.toml`/`.ini`/`.cfg`/`.env`/`.txt`/`.bat`/`.cmd` —
    Arreglo: antes solo se leía `EXT_CODIGO` y un host puesto en un
    `.json` de configuración pasaba entero sin verse), nunca `vendor/dist/build`
    (leídos aparte por `extraer_hosts_terceros_embebidos`, nunca como código
    propio) NI los propios `RUTAS_MANIFIESTO` (ver la constante: su
    `repository`/`homepage` ya tiene comprobación propia, en la 1 y la 5)."""
    ficheros = (p for p in _listar_ficheros(ruta, EXT_RED)
                if os.path.relpath(p, ruta) not in RUTAS_MANIFIESTO_NORM)
    return _hosts_en_ficheros(ficheros, ruta)


def extraer_hosts_pruebas(ruta):
    """Los hosts que viven en las carpetas de pruebas. Se declaran, no se acusan: ver
    el comentario de `DIRS_PRUEBAS`."""
    return _hosts_en_ficheros(_listar_ficheros_de_pruebas(ruta, EXT_RED), ruta)


def extraer_hosts_terceros_embebidos(ruta):
    """Igual que `extraer_hosts_codigo`, pero solo de lo que cae bajo
    `vendor/`, `dist/` o `build/`: antes esas carpetas se
    saltaban EN SILENCIO en la comprobación 4 y un "sin hallazgos" no
    distinguía "no hay nada" de "no miré ahí". Se declaran aparte a propósito:
    nunca cuentan como código de ESTE paquete, así que nunca generan hallazgo
    contra su README (ver `comprobar_red`)."""
    return _hosts_en_ficheros(_listar_ficheros_terceros_embebidos(ruta, EXT_RED), ruta)


def comprobar_red(ruta):
    hosts = extraer_hosts_codigo(ruta)
    hosts_terceros = extraer_hosts_terceros_embebidos(ruta)
    hosts_pruebas = extraer_hosts_pruebas(ruta)
    texto_readmes = _texto_readmes(ruta).lower()
    hallazgos, sin_declarar = [], []
    for host, apariciones in sorted(hosts.items()):
        if host in texto_readmes:
            continue
        sin_declarar.append(host)
        fichero, linea = apariciones[0]
        hallazgos.append({
            'comprobacion': 'red', 'severidad': 'rompe',
            'resumen': f'el código usa el host "{host}" y ningún README del paquete lo nombra',
            'fichero': fichero, 'linea': linea,
            'apariciones': [f'{f}:{n}' for f, n in apariciones[:8]],
        })
    return {'hosts_en_codigo': {h: [f'{f}:{n}' for f, n in aps] for h, aps in sorted(hosts.items())},
            'hosts_sin_declarar': sin_declarar,
            'hosts_terceros_embebidos': {h: [f'{f}:{n}' for f, n in aps]
                                          for h, aps in sorted(hosts_terceros.items())},
            'hosts_en_pruebas': {h: [f'{f}:{n}' for f, n in aps]
                                 for h, aps in sorted(hosts_pruebas.items())},
            'hallazgos': hallazgos}


# ---------- comprobación 5: dominio (sin veredicto, a propósito) ----------

def comprobar_dominio(ruta, manifiestos):
    """Dominios de README* y manifiestos, para lectura carácter a carácter. Nunca
    genera un hallazgo: el guion no sabe si un dominio es legítimo, y ese límite
    es el propio resultado de esta comprobación, no un hueco pendiente."""
    textos = [_texto_readmes(ruta)] + [m['texto'] for m in manifiestos.values() if m['texto']]
    dominios = {normalizar_host(m.group(0)) for t in textos for m in RE_URL.finditer(t)}
    return {
        'dominios_declarados': sorted(d for d in dominios if d),
        'limite': 'este guion NO dice si un dominio es legítimo; solo los reúne para lectura '
                  'carácter a carácter — contra eso solo vale leer, no un regex.',
    }


# ---------- veredicto y ensamblado ----------

def veredicto_de(hallazgos):
    if not hallazgos:
        return 'sin hallazgos'
    return max(hallazgos, key=lambda h: ORDEN_SEVERIDAD.get(h['severidad'], 0))['severidad']


def auditar(ruta):
    """Punto de entrada único: `auditar(ruta) -> dict` con las cinco
    comprobaciones, la lista combinada de `hallazgos` (1-4; la 5 nunca aporta) y
    el `veredicto` global (el peor hallazgo, o `"sin hallazgos"`)."""
    ruta = os.path.abspath(ruta)
    if not os.path.isdir(ruta):
        raise NotADirectoryError(f'no existe la carpeta: {ruta}')
    manifiestos = leer_manifiestos(ruta)
    git_info = leer_git(ruta)
    procedencia = comprobar_procedencia(ruta, manifiestos, git_info)
    comandos = comprobar_comandos(ruta)
    permisos = comprobar_permisos(ruta)
    red = comprobar_red(ruta)
    dominio = comprobar_dominio(ruta, manifiestos)
    hallazgos = procedencia['hallazgos'] + comandos['hallazgos'] + permisos['hallazgos'] + red['hallazgos']
    return {'ruta': ruta, 'procedencia': procedencia, 'comandos': comandos, 'permisos': permisos,
            'red': red, 'dominio': dominio, 'hallazgos': hallazgos, 'veredicto': veredicto_de(hallazgos)}


# ---------- informes en texto y markdown ----------

def _texto_historia_git(g):
    if not g['hay_git']:
        return 'sin .git'
    if g['sin_dato']:
        return g['sin_dato']
    return f"{g['commits']} commit(s), primero {g['primer_commit']}"


def _que_no_leyo(r):
    """Lista de lo que ESTA pasada no leyó, declarado en vez de callado (arreglo,
    misma disciplina que `vigia.py` aplica a sus falsos negativos): un
    "sin hallazgos" sin esta lista no distingue "no hay nada" de "no miré ahí".
    Se usa igual con o sin hallazgos — el límite no depende del resultado."""
    terceros = r['red']['hosts_terceros_embebidos']
    if terceros:
        linea_terceros = (f"vendor/dist/build: {len(terceros)} host(s) ahí dentro, leídos APARTE como "
                           f"terceros embebidos (nunca contra el README de este paquete): "
                           + ', '.join(sorted(terceros)))
    else:
        linea_terceros = ('vendor/dist/build: sin hosts detectados ahí dentro (o esas carpetas no '
                           'existen en este paquete) — se leen aparte, nunca en silencio')
    return [
        f"solo estas extensiones, en código y datos: {', '.join(sorted(EXT_RED))} — cualquier otra "
        "(compilados, binarios, formatos propios de otra herramienta...) no se lee",
        f"carpetas nunca leídas, ni siquiera como terceros: {', '.join(sorted(EXCLUIR_DIRS_SIEMPRE))}",
        linea_terceros,
        'una URL partida en dos líneas por concatenación de cadenas no se reconoce: es un regex '
        'sobre texto, no un parser',
    ]


def a_texto(r):
    L = [f"auditoría de {r['ruta']}", f"veredicto: {r['veredicto']}", '']
    if not r['hallazgos']:
        L.append('sin hallazgos EN LO QUE ESTA VARA MIRA, en las cuatro comprobaciones con veredicto '
                  '(procedencia, comandos, permisos, red) — no es "no hay nada", es "hasta donde mira '
                  'esta vara, no lo vio" (punto 6 dice qué no leyó).')
    else:
        for h in r['hallazgos']:
            donde = f"{h['fichero']}:{h['linea']}" if h.get('fichero') and h.get('linea') else \
                (h.get('fichero') or 'sin fichero concreto')
            L.append(f"[{h['severidad']}] ({h['comprobacion']}) {h['resumen']} — {donde}")
    historia = _texto_historia_git(r['procedencia']['git'])
    L += ['',
          f"1. procedencia — manifiestos: {r['procedencia']['manifiestos_encontrados']} · historial: {historia}",
          f"2. comandos — {len(r['comandos']['evidencia'])} entradas de evidencia (ganchos + llamadas de código)",
          f"3. permisos — {r['permisos']['total_evidencia']} escritura(s) fuera de la carpeta · declara cómo deshacer: {r['permisos']['declara_deshacer']}",
          f"4. red — {len(r['red']['hosts_en_codigo'])} host(s) en el código · "
          f"{len(r['red']['hosts_sin_declarar'])} sin nombrar en ningún README · "
          f"{len(r['red']['hosts_terceros_embebidos'])} host(s) más bajo vendor/dist/build (terceros embebidos)",
          f"5. dominio — {len(r['dominio']['dominios_declarados'])} dominio(s) para lectura manual: {r['dominio']['limite']}",
          '', '6. qué no leyó esta vara (declarado, no medido):']
    L += [f"   - {linea}" for linea in _que_no_leyo(r)]
    return '\n'.join(L)


def a_markdown(r):
    # En el informe MARKDOWN va el NOMBRE del paquete, no su ruta absoluta: este fichero
    # se publica, y la ruta de la máquina donde se auditó no es del paquete — puede llevar
    # el nombre de una persona dentro. (Medido el 8-sep-2026: el informe regenerado con la
    # ruta entera hacía saltar la prueba de datos personales del propio repositorio.)
    # Por pantalla y en el JSON sí sale la ruta entera: ahí no se publica nada.
    L = [f"# Auditoría de `{os.path.basename(os.path.abspath(r['ruta']))}`", '',
         f"**Veredicto**: {r['veredicto']}", '']
    L.append('## Hallazgos')
    if not r['hallazgos']:
        L.append('')
        L.append('Sin hallazgos **en lo que esta vara mira**, en las cuatro comprobaciones con '
                  'veredicto (procedencia, comandos, permisos, red) — no es "no hay nada": es "hasta '
                  'donde mira esta vara, no lo vio". Ver la sección 6 para qué no leyó.')
    else:
        L.append('')
        L.append('| severidad | comprobación | fichero:línea | qué dice |')
        L.append('|---|---|---|---|')
        for h in r['hallazgos']:
            donde = f"{h['fichero']}:{h['linea']}" if h.get('fichero') and h.get('linea') else (h.get('fichero') or '—')
            L.append(f"| {h['severidad']} | {h['comprobacion']} | `{donde}` | {h['resumen']} |")

    L += ['', '## 1 · Procedencia',
          f"- Manifiestos encontrados: {r['procedencia']['manifiestos_encontrados'] or 'ninguno'}"]
    for a in r['procedencia']['autores']:
        L.append(f"  - `{a['fichero']}`: autor = {a['valor'] or '(vacío)'}"
                  f"{' — placeholder/sin nombre real' if a['placeholder'] else ''}")
    L.append(f"- Historial: {_texto_historia_git(r['procedencia']['git'])}")

    L += ['', '## 2 · Comandos']
    for e in r['comandos']['evidencia']:
        if 'evento' in e:
            marca = ' **(cada mensaje)**' if e.get('cada_mensaje') else (' **(tras cada herramienta)**' if e.get('cada_herramienta') else '')
            L.append(f"- `{e['fichero']}:{e['linea']}` {e['evento']}{marca}: `{e['comando']}`")
        else:
            L.append(f"- `{e['fichero']}:{e['linea']}` {e['nota']}: `{e.get('texto', '')}`")

    L += ['', '## 3 · Permisos', f"- Declara cómo deshacerlo en algún README: {r['permisos']['declara_deshacer']}"]
    for e in r['permisos']['evidencia']:
        L.append(f"- `{e['fichero']}:{e['linea']}`: `{e['texto']}`")

    L += ['', '## 4 · Qué sale de la máquina']
    if r['red']['hosts_en_codigo']:
        for host, apariciones in r['red']['hosts_en_codigo'].items():
            marca = ' — **sin nombrar en el README**' if host in r['red']['hosts_sin_declarar'] else ' — nombrado en el README'
            L.append(f"- `{host}`{marca}: {', '.join(apariciones[:8])}")
    else:
        L.append('- ningún host propio detectado (ver punto 6: eso no es lo mismo que "no hay ninguno")')
    L.append('')
    if r['red']['hosts_terceros_embebidos']:
        L.append('Terceros embebidos bajo `vendor/`, `dist/` o `build/` — leídos APARTE, nunca contra '
                  'el README de este paquete (no son código propio):')
        for host, apariciones in r['red']['hosts_terceros_embebidos'].items():
            L.append(f"- `{host}`: {', '.join(apariciones[:8])}")
    else:
        L.append('Sin `vendor/`, `dist/` ni `build/` con hosts en este paquete (o esas carpetas no existen aquí).')

    L += ['', '## 5 · Dominio (lectura manual)', f"- {r['dominio']['limite']}", '']
    L.append(', '.join(f'`{d}`' for d in r['dominio']['dominios_declarados']) or '(ninguno encontrado)')

    L += ['', '## 6 · Qué no leyó esta vara (declarado, no medido)']
    for linea in _que_no_leyo(r):
        L.append(f'- {linea}')
    return '\n'.join(L) + '\n'


if __name__ == '__main__':
    _argv = sys.argv[1:]
    _con_json = '--json' in _argv
    if _con_json:
        _argv.remove('--json')
    _salida_md = None
    if '--markdown' in _argv:
        i = _argv.index('--markdown')
        if i + 1 >= len(_argv):
            print('--markdown necesita un fichero detrás'); sys.exit(1)
        _salida_md = _argv[i + 1]
        del _argv[i:i + 2]
    for _a in _argv:
        if _a.startswith('--'):
            print(f'argumento no reconocido: {_a} (usa --json/--markdown)'); sys.exit(1)
    if len(_argv) != 1:
        print('uso: auditar.py <ruta_de_paquete> [--json] [--markdown salida.md]'); sys.exit(1)
    if not os.path.isdir(_argv[0]):
        print(f'no existe la carpeta: {_argv[0]}'); sys.exit(1)

    _r = auditar(_argv[0])
    if _salida_md:
        _dir_md = os.path.dirname(os.path.abspath(_salida_md))
        if _dir_md:
            os.makedirs(_dir_md, exist_ok=True)
        with open(_salida_md, 'w', encoding='utf-8') as _fh:
            _fh.write(a_markdown(_r))
        print(f'markdown: {_salida_md}')
    print(json.dumps(_r, ensure_ascii=False, indent=1) if _con_json else a_texto(_r))
    sys.exit(0)
