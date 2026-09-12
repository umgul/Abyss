"""Varas para la memoria: mide en vez de decretar.
Dos varas en el índice, separadas:
  ★  estrella-diario  = decreto de quien escribe (importancia asignada ese día)
  ◆  peso-uso medido  = citas [[..]] desde otras fichas + sesiones que la leyeron
     (cortes por CUANTILES de la distribución actual, no umbrales fijos:
      normales que rotan; ◆◆◆ decil alto, ◆◆ siguiente 20 %, ◆ siguiente 30 %)
Uso:  python varas.py                       → informe
      python varas.py --index               → reescribe los ◆ en MEMORY.md (idempotente)
      python varas.py --index --recortar    → además recorta si supera 24 KB (con copia fechada)

Arranque en frío (§2.2): con menos de `propiocepcion.UMBRAL_FRIO` sesiones
archivadas no hay distribución que valga — no se pone NINGÚN ◆ (se avisa por
stdout «sin vara todavía»), aunque el uso medido sea >0: con tan poco corpus el
ranking por cuantiles no significa nada.

Índice grande (§2.3): si MEMORY.md supera 24 KB tras reescribir los ◆, se avisa por
stdout que hace falta recortar — pero NO se recorta solo: el pase automático (el que
dispara `continuidad.cerrar()` tras cada cierre de sesión) nunca toca líneas, porque
el aviso sale por stdout de un gancho y nadie lo lee ahí. Con `--index --recortar`
explícito sí se recorta, siempre con una copia fechada de MEMORY.md al lado antes de
escribir: las líneas de más de 200 caracteres se cortan en su ÚLTIMO separador ' · '
dentro de ese límite (nunca a medias de un enlace markdown). Nunca se borra una línea
entera.

El código vive donde lo instale `rutas.CODE`; los datos (MEMORY.md, fichas,
sesiones/) viven en `mem`, resuelto por `rutas.resolver()` — nunca
`dirname(__file__)` como carpeta de datos (§1).

Límite conocido: «leída» solo ve Read/cat explícitos; lo que el harness inyecta
como recuerdo no deja huella → subestima.

Paréntesis: una lectura de ficha hecha DENTRO de un tramo marcado por `parentesis.py`
no cuenta como uso — no le sube el ◆ a esa ficha, para que MEMORY.md (lo primero que
se lee al empezar cada hilo) no delate qué ficha se consultó en ese rato, aunque el
contenido nunca se copiara a ningún sitio."""
import sys
try:                       # la consola de Windows y la salida tienen que hablar
    from . import consola  # el mismo idioma: ver abyss/consola.py
except ImportError:
    import consola
consola.preparar()
import os, re, json, glob, time, shutil, unicodedata
N = unicodedata.normalize

try:
    from . import rutas
except ImportError:
    import rutas

CODE = rutas.CODE
# leer_stdin_si_hace_falta: si ya hay --proyecto/ABYSS_PROYECTO (p. ej. porque
# continuidad.py ya resolvió proj y lo dejó puesto antes de lanzar este módulo como
# subprocess) no hace falta tocar stdin: ahorra el peaje de `leer_stdin()` y evita el
# hilo lector sin usar que puede trabar el siguiente import que toque hilos.
_STDIN = rutas.leer_stdin_si_hace_falta(sys.argv[1:])
proj, mem = rutas.resolver(sys.argv[1:], _STDIN)
os.environ['ABYSS_PROYECTO'] = proj  # para que quien importe este módulo después no relea stdin (ya vacío)

try:
    from . import propiocepcion as P
except ImportError:
    import propiocepcion as P

# Importado DESPUÉS de fijar ABYSS_PROYECTO (igual que hace `continuidad.py` con
# este mismo módulo) para que la propia resolución de `parentesis.py` no vuelva a
# tocar stdin.
try:
    from . import parentesis as PZ
except ImportError:
    import parentesis as PZ

IDX = os.path.join(mem, 'MEMORY.md')
SES = os.path.join(mem, 'sesiones')
LIMITE_LINEA = 200
LIMITE_ARCHIVO = 24 * 1024
SEP = ' · '

idx = ''
if os.path.exists(IDX):
    # newline='': preserva los finales de línea TAL CUAL estaban (LF o CRLF), sin la
    # traducción universal de Python — sin esto, un MEMORY.md con LF se reescribiría
    # entero en CRLF en cada cierre de sesión, solo por pasar por aquí.
    with open(IDX, encoding='utf-8', newline='') as _fh:
        idx = _fh.read()
fichas = [f for f in os.listdir(mem) if f.endswith('.md') and f != 'MEMORY.md']
stars = {N('NFC', m.group(2)): len(m.group(1)) for m in re.finditer(r'\[(★*)[^\]]*\]\(([^)]+\.md)\)', idx)}

n_sesiones = len(P.archivos_sesion(SES))
SIN_VARA = n_sesiones < P.UMBRAL_FRIO  # arranque en frío, §2.2: no hay corpus para cuantiles


def tipo(f):
    with open(os.path.join(mem, f), encoding='utf-8', errors='ignore') as fh:
        cabecera = fh.read(600)
    m = re.search(r'^\s*type:\s*(\w+)', cabecera, re.M)
    return m.group(1) if m else 'sin_tipo'


indeg = {f: 0 for f in fichas}
for f in fichas:
    with open(os.path.join(mem, f), encoding='utf-8', errors='ignore') as _fh:
        body = _fh.read()
    for m in re.finditer(r'\[\[([^\]|]+)', body):
        t = N('NFC', m.group(1).strip()) + '.md'
        if t in indeg and t != f:
            indeg[t] += 1
def _ts_de_linea(line):
    """`timestamp` de una línea de transcript ya candidata, o `None` si no se puede leer
    como JSON — mismo criterio fail-open que `parentesis.en_parentesis()`: una línea
    sin marca de tiempo no se oculta, se cuenta igual que siempre."""
    try:
        return json.loads(line).get('timestamp')
    except Exception:
        return None


reads = {f: set() for f in fichas}
for sp in glob.glob(os.path.join(proj, '*.jsonl')):
    sid = os.path.basename(sp)[:-6]
    with open(sp, encoding='utf-8', errors='ignore') as fh:
        for line in fh:
            if 'memory' not in line or ('"name":"Read"' not in line and 'cat ' not in line):
                continue
            # Paréntesis (ver docstring del módulo): una lectura DENTRO de un tramo
            # marcado no debe subirle el ◆ a esa ficha en MEMORY.md.
            if PZ.en_parentesis(sid, _ts_de_linea(line)):
                continue
            line = N('NFC', line)
            for f in fichas:
                if f in line:
                    reads[f].add(sid)
now = time.time()
use = {f: indeg[f] + len(reads[f]) for f in fichas}
age = {f: (now - os.path.getmtime(os.path.join(mem, f))) / 86400 for f in fichas}
ranked = sorted(fichas, key=lambda f: -use[f]); n = len(ranked)


def glyph(f):
    if SIN_VARA or use[f] == 0:
        return ''
    r = ranked.index(f) / n
    return '◆◆◆' if r < 0.10 else '◆◆' if r < 0.30 else '◆' if r < 0.60 else ''


def _copia_fechada(ruta):
    """Copia `ruta` a `ruta.abyss-AAAAMMDD-HHMMSS.bak` antes de recortarla —
    igual que `instalar._copia_fechada`. Se llama SOLO cuando de verdad se van a
    recortar líneas (nunca en cada `--index`): el recorte es irreversible y el
    aviso, si nadie lo lee por stdout de un gancho, no basta para deshacerlo."""
    if not os.path.exists(ruta):
        return None
    destino = f'{ruta}.abyss-{time.strftime("%Y%m%d-%H%M%S")}.bak'
    if not os.path.exists(destino):
        shutil.copy2(ruta, destino)
    return destino


def _recortar_lineas_largas(texto):
    """Si una línea supera LIMITE_LINEA caracteres, la recorta en el ÚLTIMO ' · ' que
    quede dentro de ese límite — nunca a medias de un enlace markdown. Si no hay
    separador dentro del límite, no la toca (mejor una línea larga que un enlace
    roto). Nunca borra líneas enteras. Devuelve (texto, [(nº_línea, chars_quitados)])."""
    lineas = texto.split('\n'); recortes = []
    for i, ln in enumerate(lineas):
        if len(ln) <= LIMITE_LINEA:
            continue
        corte = ln.rfind(SEP, 0, LIMITE_LINEA)
        if corte == -1:
            continue
        recortes.append((i + 1, len(ln) - corte))
        lineas[i] = ln[:corte]
    return '\n'.join(lineas), recortes


if '--index' in sys.argv:
    if not os.path.exists(IDX) and not fichas:
        # Proyecto virgen: ni índice ni ninguna ficha .md en mem/. El gancho SessionEnd
        # (continuidad.cerrar() → varas.py --index) dispara en TODOS los proyectos que
        # se abran (settings.json es global); sin este aviso, crearía de la nada un
        # MEMORY.md con solo la leyenda — el fichero de memoria automática que Claude
        # Code inyecta en contexto, con una leyenda que no explica nada de ESE
        # proyecto. No se escribe nada.
        print('sin índice ni fichas todavía: no se crea MEMORY.md de la nada')
        sys.exit()
    if SIN_VARA:
        print(f'sin vara todavía (n={n_sesiones} sesiones archivadas; hacen falta {P.UMBRAL_FRIO}): '
              f'no se pone ningún ◆ en este índice.')

    def sub(m):
        if SIN_VARA:
            return m.group(0)  # sin corpus: no tocar lo que ya había, ni para borrarlo
        name = N('NFC', m.group(1)); g = glyph(name) if name in use else ''
        return f']({m.group(1)})' + (' ' + g if g else '')
    new = re.sub(r'\]\(([^)]+\.md)\)(?: ◆+)?', sub, idx)
    legend = '> Varas: **★** = estrella-diario (decreto mío al escribir) · **◆** = peso-uso MEDIDO (citas+lecturas, cuantiles, `python varas.py --index`)\n'
    if '> Varas:' in new:
        new = re.sub(r'> Varas:.*\n', legend, new, count=1)
    else:
        # Tras la PRIMERA línea que empiece por '# ' (el título del índice, sea cual
        # sea su texto — no una cadena fija de un MEMORY.md concreto); si no hay
        # ninguna, al principio del fichero.
        m = re.search(r'^# .*\n', new, re.M)
        new = new[:m.end()] + legend + new[m.end():] if m else legend + new

    if len(new.encode('utf-8')) > LIMITE_ARCHIVO:
        if '--recortar' in sys.argv:
            recortado, recortes = _recortar_lineas_largas(new)
            if recortes:
                _copia_fechada(IDX)  # irreversible: copia del índice ANTES de pisarlo
                new = recortado
                print(f'MEMORY.md supera {LIMITE_ARCHIVO // 1024} KB: recortadas {len(recortes)} líneas '
                      f'largas en su último separador (nunca se borra una línea entera; '
                      f'copia previa en {os.path.basename(IDX)}.abyss-*.bak):')
                for ln, quitados in recortes:
                    print(f'  línea {ln}: -{quitados} caracteres')
        else:
            print(f'MEMORY.md supera {LIMITE_ARCHIVO // 1024} KB: hace falta recortar líneas largas. '
                  f'No se recorta en el pase automático (tras --cierre) — hazlo tú con '
                  f'`python varas.py --index --recortar` cuando quieras.')

    tmp = IDX + '.tmp-abyss'  # escritura atómica: varios hilos pueden cerrar sesión a la vez (§ README)
    with open(tmp, 'w', encoding='utf-8', newline='') as fh:  # preserva los finales de línea originales
        fh.write(new)
    os.replace(tmp, IDX)
    print('índice reescrito', len(new), 'bytes'); sys.exit()

if SIN_VARA:
    print(f'sin vara todavía (n={n_sesiones} sesiones archivadas; hacen falta {P.UMBRAL_FRIO} para medir ◆)')
S = [f for f in fichas if f in stars]
print(f'fichas {n} | en índice {len(S)} | huérfanas {n - len(S)}')
for k in (3, 2, 1, 0):
    g = [f for f in S if stars[f] == k]
    if g:
        print(f'{"★" * k or "sin ★":6} n={len(g):3}  citada {sum(indeg[f] for f in g) / len(g):.2f}  leída {sum(len(reads[f]) for f in g) / len(g):.2f}  alguna vez leída {sum(1 for f in g if reads[f])}/{len(g)}')
# Solo las de tipo project (obra fechada) envejecen por desuso. reference / user /
# feedback son ley o perfil: se leen por el gancho del índice sin dejar huella → nunca
# candidatas por desuso. Lo que no tiene type se lista aparte, no se propone.
print('\ncandidatas al desván (type=project, sin ★, uso 0, >45 días):')
for f in sorted(S, key=lambda f: -age[f]):
    if tipo(f) == 'project' and stars[f] == 0 and use[f] == 0 and age[f] > 45:
        print('  ', f, f'({age[f]:.0f}d)')
st = [f for f in fichas if tipo(f) == 'sin_tipo']
if st:
    print('sin type en frontmatter (revisar a mano, no se proponen):', st)
print('huérfanas:', [f for f in fichas if f not in stars])
