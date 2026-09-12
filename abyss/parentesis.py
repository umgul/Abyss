"""Paréntesis: lo que el usuario pide que no entre en memoria (§8 de `ESPECIFICACION.md`).

Cuando dice «esto no lo metas en tu memoria», «esto es un paréntesis» o «elimina todo el
rato que hemos hablado de X», hace falta una herramienta honesta para cumplirlo — no un
«vale, lo olvido» de boquilla mientras `continuidad.py` sigue copiando la sesión entera.

Tres mecanismos, distintos y no confundibles:

  1. Un TRAMO por sesión (`--abrir`/`--cerrar`, en `mem/parentesis.json`). No borra nada
     del transcript: lo de dentro del tramo (por `timestamp` de cada línea) deja de
     ENTRAR en lo que este paquete vuelve a leer — `continuidad.guardar()`,
     `frases_usuario()` (bolsas y relojes) y `vigia.leer_turno()` saltan esas líneas con
     el mismo criterio.
  2. Un CORTE del `.jsonl` LOCAL (`--recortar`/`--recortar-tramo`): reescribe el fichero
     que usa la app de Claude Code para reconstruir el hilo (deja `.antes` con el
     original). Solo tiene sentido con el hilo YA cerrado.
  3. `--omitir-sesion`, más bruto: reutiliza `mem/sesiones/.omitir` de `continuidad.py`
     — la sesión entera nunca se copia.

Límite declarado (aquí y en el README): lo que ya se mandó a la API de Anthropic dentro
del propio turno YA VIAJÓ; ninguna herramienta local lo deshace. Esto solo gobierna la
memoria LOCAL (sesiones/, bolsas, relojes) y lo que se vuelve a leer en hilos futuros; lo
ya enviado es un asunto de retención de datos con Anthropic, no de este fichero.

Uso (sin gancho: se invoca por Bash cuando el usuario lo pide, nunca dispara solo):

    python parentesis.py --abrir [motivo] [--sesion <id>]
    python parentesis.py --cerrar [--sesion <id>]
    python parentesis.py --omitir-sesion [id]
    python parentesis.py --recortar <transcript.jsonl> "<último mensaje del usuario que se conserva>"
    python parentesis.py --recortar-tramo <transcript.jsonl> <inicio_iso> <fin_iso>

Sin `--sesion` explícito ni `session_id` por stdin, se usa una HEURÍSTICA: el hilo con el
latido más reciente en `mem/.vivo/` (lo escribe `continuidad.latir()` en cada
`UserPromptSubmit`); `--sesion` explícito siempre gana si se da, y sin ningún latido vivo
se rehúsa (código 1) en vez de adivinar. `--recortar`/`--recortar-tramo` se niegan (código
1) si el hilo sigue vivo (`mem/.vivo/<id>.json` con latido de menos de 2 minutos: la app
podría estar a punto de escribir sobre ese mismo `.jsonl`); `--recortar` exige que el
mensaje coincida EXACTO (tras normalizar espacios) con uno real del usuario en ese
transcript.

El código vive donde lo instale `rutas.CODE`; los datos (`parentesis.json`, el `.omitir`
de `mem/sesiones/`) viven en `mem`, resuelto por `rutas.resolver()` — nunca
`dirname(__file__)` (§1 de ESPECIFICACION.md).
"""
import sys
try:                       # la consola de Windows y la salida tienen que hablar
    from . import consola  # el mismo idioma: ver abyss/consola.py
except ImportError:
    import consola
consola.preparar()
import os, re, json, glob, time, shutil
from datetime import datetime, timezone

try:
    from . import rutas
except ImportError:
    import rutas

CODE = rutas.CODE
# leer_stdin_si_hace_falta: esta pieza no necesita del JSON de un gancho más que, como
# mucho, `session_id` — y solo como último recurso antes de la heurística del latido.
# Invocado a mano con `--proyecto`/`ABYSS_PROYECTO` (el caso normal, sin gancho), no hace
# falta tocar stdin en absoluto.
_STDIN = rutas.leer_stdin_si_hace_falta(sys.argv[1:])
proj, mem = rutas.resolver(sys.argv[1:], _STDIN)
os.environ['ABYSS_PROYECTO'] = proj

RUTA = os.path.join(mem, 'parentesis.json')
SES = os.path.join(mem, 'sesiones')
VIVO = os.path.join(mem, '.vivo')
TOPE_VIVO_S = 120  # 2 minutos: por debajo de esto, --recortar/--recortar-tramo se niegan


# ---------- mem/parentesis.json ----------

def _leer():
    try:
        with open(RUTA, encoding='utf-8') as fh:
            return json.load(fh)
    except Exception:
        return {}


def _escribir(datos):
    os.makedirs(mem, exist_ok=True)
    with open(RUTA, 'w', encoding='utf-8') as fh:
        json.dump(datos, fh, ensure_ascii=False, indent=1)


def tramos(sid):
    """[(inicio_iso, fin_iso_o_None)] de esta sesión, tal cual están guardados.
    [] si nunca se abrió ningún paréntesis en ella."""
    return [(t.get('inicio'), t.get('fin')) for t in _leer().get(sid, [])]


def _parse(ts):
    return datetime.fromisoformat(str(ts).replace('Z', '+00:00'))


def en_parentesis(sid, ts):
    """¿Cae `ts` dentro de algún tramo de paréntesis de `sid`? Un tramo sin `--cerrar`
    (`fin` es `None`) se trata como abierto hasta ahora: nada posterior al `--abrir` se
    escapa aunque la sesión se cierre a mitad. Fail-open ante datos ilegibles: una línea
    sin `timestamp` o un `inicio` corrupto no se oculta (ocultar por defecto escondería
    mensajes ajenos al paréntesis); un `fin` corrupto sí oculta (ahí ya se sabe que el
    tramo existe)."""
    if not ts:
        return False
    try:
        momento = _parse(ts)
    except Exception:
        return False
    for inicio, fin in tramos(sid):
        try:
            ini = _parse(inicio)
        except Exception:
            continue
        if momento < ini:
            continue
        if fin is None:
            return True
        try:
            f = _parse(fin)
        except Exception:
            return True
        if momento <= f:
            return True
    return False


def abrir(sid, motivo=None):
    datos = _leer()
    lst = datos.setdefault(sid, [])
    for t in lst:
        if t.get('fin') is None:
            extra = f' ({t["motivo"]})' if t.get('motivo') else ''
            return f'ya había un paréntesis abierto en {sid[:8]} desde {t["inicio"]}{extra}; sigue abierto, no se abre otro'
    ahora = datetime.now(timezone.utc).isoformat(timespec='seconds')
    lst.append({'inicio': ahora, 'fin': None, 'motivo': motivo})
    _escribir(datos)
    extra = f' — motivo: {motivo}' if motivo else ''
    return (f'paréntesis abierto en {sid[:8]} desde {ahora}{extra}. Nada de lo que se hable hasta '
            f'--cerrar entra en mem/sesiones/, bolsas ni relojes de este proyecto.')


def cerrar(sid):
    datos = _leer()
    lst = datos.get(sid, [])
    abierto = next((t for t in lst if t.get('fin') is None), None)
    if abierto is None:
        return f'no hay ningún paréntesis abierto en la sesión {sid[:8]}'
    ahora = datetime.now(timezone.utc).isoformat(timespec='seconds')
    abierto['fin'] = ahora
    _escribir(datos)
    extra = f' — motivo: {abierto["motivo"]}' if abierto.get('motivo') else ''
    return f'paréntesis cerrado en {sid[:8]}: de {abierto["inicio"]} a {ahora}{extra}'


# ---------- --omitir-sesion (reusa mem/sesiones/.omitir de continuidad.py) ----------

def omitir_sesion(sid):
    os.makedirs(SES, exist_ok=True)
    ruta = os.path.join(SES, '.omitir')
    try:
        with open(ruta, encoding='utf-8') as fh:
            existentes = {l.strip() for l in fh if l.strip()}
    except Exception:
        existentes = set()
    if sid in existentes:
        return f'{sid[:8]} ya estaba en sesiones/.omitir'
    with open(ruta, 'a', encoding='utf-8') as fh:
        fh.write(sid + '\n')
    return f'{sid[:8]} añadida a sesiones/.omitir: ningún hilo (este u otro haciendo la cosecha) la copiará a mem/sesiones/'


# ---------- heurística de sesión actual (sin gancho, sin session_id) ----------

def _sesion_actual():
    """El id de sesión con el latido más reciente en `mem/.vivo/` (lo mantiene
    `continuidad.latir()`), o `None` si no hay ninguno. Heurística, no ley — ver
    docstring del módulo."""
    mejor = None
    for p in glob.glob(os.path.join(VIVO, '*.json')):
        try:
            with open(p, encoding='utf-8') as fh:
                v = json.load(fh)
        except Exception:
            continue
        ts = v.get('ts', 0)
        if mejor is None or ts > mejor[1]:
            mejor = (v.get('id') or os.path.basename(p)[:-5], ts)
    return mejor[0] if mejor else None


def _resolver_sid(explicito):
    if explicito:
        return explicito
    if _STDIN.get('session_id'):
        return _STDIN['session_id']
    s = _sesion_actual()
    if s:
        return s
    # Sin acentos a propósito: stderr, a diferencia de stdout, NO se reconfigura a
    # utf-8 (mismo criterio que rutas.py/vigia.py) — en la consola cp1252 de
    # Windows una tilde aquí sale como byte suelto que un lector en utf-8 (como
    # `ayudas.ejecutar` en las pruebas) no puede decodificar limpio.
    sys.stderr.write('parentesis: no se sabe de que sesion se habla - pasa --sesion <id> '
                      '(no hay session_id por stdin ni ningun latido vivo en mem/.vivo/)\n')
    sys.exit(1)


# ---------- --recortar / --recortar-tramo: el transcript LOCAL de verdad ----------

def _esta_vivo(sid):
    """¿Hay un latido de este hilo (`mem/.vivo/<sid>.json`, de `continuidad.latir()`) de
    menos de `TOPE_VIVO_S`? Sin fichero de latido se considera MUERTO — fail-open a
    propósito: negar un recorte legítimo porque el gancho de continuidad nunca escribió
    el latido sería peor que el riesgo contrario."""
    p = os.path.join(VIVO, sid + '.json')
    try:
        with open(p, encoding='utf-8') as fh:
            v = json.load(fh)
        return (time.time() - v.get('ts', 0)) < TOPE_VIVO_S
    except Exception:
        return False


def _sid_de_jsonl(ruta):
    base = os.path.basename(ruta)
    return base[:-6] if base.endswith('.jsonl') else base


def _contenido_real_usuario(d):
    """`message.content` si esta línea es un turno REAL del usuario (string, no la
    lista de bloques de un `tool_result`) y no es meta — mismo criterio que usa
    `vigia.leer_turno()` para no confundir el resultado de una herramienta con algo
    que el usuario tecleó."""
    if d.get('type') != 'user' or d.get('isMeta'):
        return None
    c = (d.get('message') or {}).get('content')
    return c if isinstance(c, str) else None


def recortar(ruta_jsonl, ultimo_mensaje):
    """Conserva de `ruta_jsonl` todo hasta la ÚLTIMA vez que el usuario escribió
    `ultimo_mensaje` exacto, incluida la respuesta completa a ese mensaje. Fail-closed:
    si el hilo sigue vivo, o si ese mensaje no aparece tal cual, no toca nada.
    `<ruta_jsonl>.antes` guarda el original, solo en la primera llamada. Devuelve
    (ok: bool, mensaje: str)."""
    if not (os.path.isfile(ruta_jsonl) and ruta_jsonl.endswith('.jsonl')):
        return False, f'--recortar necesita un transcript .jsonl real (no comprimido), no «{ruta_jsonl}»'
    sid = _sid_de_jsonl(ruta_jsonl)
    if _esta_vivo(sid):
        return False, f'el hilo {sid[:8]} tiene latido de menos de {TOPE_VIVO_S // 60} min: se niega a recortar un transcript vivo'
    with open(ruta_jsonl, encoding='utf-8', errors='ignore') as fh:
        lineas = fh.readlines()
    objetivo = re.sub(r'\s+', ' ', ultimo_mensaje.strip())
    idx_objetivo = None
    for i, linea in enumerate(lineas):
        try:
            d = json.loads(linea)
        except Exception:
            continue
        c = _contenido_real_usuario(d)
        if c is not None and re.sub(r'\s+', ' ', c.strip()) == objetivo:
            idx_objetivo = i  # se queda con la ÚLTIMA coincidencia, no la primera
    if idx_objetivo is None:
        return False, f'no se encontró ese mensaje del usuario tal cual en {os.path.basename(ruta_jsonl)}: no se toca nada'
    idx_corte = len(lineas)
    for i in range(idx_objetivo + 1, len(lineas)):
        try:
            d = json.loads(lineas[i])
        except Exception:
            continue
        if _contenido_real_usuario(d) is not None:
            idx_corte = i
            break
    if idx_corte == len(lineas):
        return True, (f'«{ultimo_mensaje[:60]}» (o su respuesta) ya llega hasta el final de '
                       f'{os.path.basename(ruta_jsonl)}: nada que recortar')
    antes = ruta_jsonl + '.antes'
    if not os.path.exists(antes):
        shutil.copyfile(ruta_jsonl, antes)
    with open(ruta_jsonl, 'w', encoding='utf-8') as fh:
        fh.writelines(lineas[:idx_corte])
    return True, (f'{os.path.basename(ruta_jsonl)} recortado a {idx_corte}/{len(lineas)} líneas '
                   f'(conservado hasta la respuesta a «{ultimo_mensaje[:60]}»); original en {os.path.basename(antes)}')


def recortar_tramo(ruta_jsonl, inicio_iso, fin_iso):
    """Como `recortar()` pero por tramo de tiempo: quita las líneas cuya
    `timestamp` cae entre `inicio_iso` y `fin_iso` (los dos incluidos), conserva el
    resto tal cual. Mismo candado de hilo vivo, mismo `.antes` que no se pisa."""
    if not (os.path.isfile(ruta_jsonl) and ruta_jsonl.endswith('.jsonl')):
        return False, f'--recortar-tramo necesita un transcript .jsonl real (no comprimido), no «{ruta_jsonl}»'
    sid = _sid_de_jsonl(ruta_jsonl)
    if _esta_vivo(sid):
        return False, f'el hilo {sid[:8]} tiene latido de menos de {TOPE_VIVO_S // 60} min: se niega a recortar un transcript vivo'
    try:
        ini = _parse(inicio_iso); fin = _parse(fin_iso)
    except Exception as e:
        return False, f'--recortar-tramo necesita fechas ISO válidas (inicio, fin): {e}'
    with open(ruta_jsonl, encoding='utf-8', errors='ignore') as fh:
        lineas = fh.readlines()
    conservadas = []; quitadas = 0
    for linea in lineas:
        ts = None
        try:
            ts = json.loads(linea).get('timestamp')
        except Exception:
            pass
        if ts:
            try:
                momento = _parse(ts)
                if ini <= momento <= fin:
                    quitadas += 1
                    continue
            except Exception:
                pass
        conservadas.append(linea)
    if quitadas == 0:
        return True, f'ninguna línea de {os.path.basename(ruta_jsonl)} cae entre {inicio_iso} y {fin_iso}: nada que recortar'
    antes = ruta_jsonl + '.antes'
    if not os.path.exists(antes):
        shutil.copyfile(ruta_jsonl, antes)
    with open(ruta_jsonl, 'w', encoding='utf-8') as fh:
        fh.writelines(conservadas)
    return True, (f'{os.path.basename(ruta_jsonl)}: {quitadas} línea(s) del tramo {inicio_iso}–{fin_iso} '
                   f'eliminadas ({len(conservadas)} quedan); original en {os.path.basename(antes)}')


# ---------- CLI ----------

def _parse_argv(argv):
    """Separa `--proyecto <valor>`/`--sesion <valor>` (las dos únicas banderas de
    valor de esta pieza) de los argumentos posicionales; cualquier otra `--algo`
    suelta se ignora en vez de colarse como si fuera un positional."""
    banderas = {}; pos = []; i = 0
    while i < len(argv):
        a = argv[i]
        if a in ('--proyecto', '--sesion') and i + 1 < len(argv):
            banderas[a[2:]] = argv[i + 1]; i += 2; continue
        if a.startswith('--'):
            i += 1; continue
        pos.append(a); i += 1
    return banderas, pos


if __name__ == '__main__':
    _argv = sys.argv[1:]
    _modo = _argv[0] if _argv else ''
    _banderas, _pos = _parse_argv(_argv[1:])

    if _modo == '--abrir':
        _motivo = ' '.join(_pos).strip() or None
        print(abrir(_resolver_sid(_banderas.get('sesion')), _motivo))
        sys.exit(0)

    if _modo == '--cerrar':
        print(cerrar(_resolver_sid(_banderas.get('sesion'))))
        sys.exit(0)

    if _modo == '--omitir-sesion':
        _sid = _pos[0] if _pos else _resolver_sid(_banderas.get('sesion'))
        print(omitir_sesion(_sid))
        sys.exit(0)

    if _modo == '--recortar':
        if len(_pos) < 2:
            sys.stderr.write('uso: parentesis.py --recortar <transcript.jsonl> "<último mensaje del usuario que se conserva>"\n')
            sys.exit(1)
        _ok, _msg = recortar(_pos[0], ' '.join(_pos[1:]))
        print(_msg); sys.exit(0 if _ok else 1)

    if _modo == '--recortar-tramo':
        if len(_pos) < 3:
            sys.stderr.write('uso: parentesis.py --recortar-tramo <transcript.jsonl> <inicio_iso> <fin_iso>\n')
            sys.exit(1)
        _ok, _msg = recortar_tramo(_pos[0], _pos[1], _pos[2])
        print(_msg); sys.exit(0 if _ok else 1)

    sys.stderr.write('uso: parentesis.py --abrir [motivo] | --cerrar | --omitir-sesion [id] | '
                      '--recortar <jsonl> "<msg>" | --recortar-tramo <jsonl> <inicio> <fin>\n')
    sys.exit(1)
