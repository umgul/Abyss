"""Paréntesis: lo que el usuario pide que no entre en memoria.

Petición del usuario (6-sep 18:26): cuando dice «esto no lo metas en tu memoria»,
«esto es un paréntesis» o «elimina todo el rato que hemos hablado de X», el
asistente necesita una herramienta honesta para cumplirlo — no un «vale, lo
olvido» de boquilla mientras `continuidad.py` sigue copiando la sesión entera.
Es el §8 de `ESPECIFICACION.md` y la T2.1 de `ESPECIFICACION_TANDA2.md`.

Dos mecanismos, DISTINTOS y no confundibles:

  1. Un TRAMO por sesión, marcado con `--abrir`/`--cerrar`, que vive en
     `mem/parentesis.json`. No borra nada del transcript: hace que lo de dentro
     del tramo (por marca de tiempo `timestamp` de cada línea) deje de ENTRAR en
     lo que este paquete vuelve a leer — `continuidad.guardar()` copia la sesión
     a `mem/sesiones/` saltando esas líneas, y `frases_usuario()` (de donde salen
     las bolsas de palabras y los relojes) hace lo mismo. La sala de los relojes
     y las bolsas heredan el filtro sin tocarlas, porque las dos se construyen a
     partir de `frases_usuario()`. El vigía (`vigia.py`, `leer_turno()`) también
     salta las líneas de un tramo, con el mismo criterio (fallo "engaña" del
     revisor 7-sep: no lo hacía, y podía guardar fragmentos literales de una
     respuesta dicha dentro de un tramo en `confabulaciones.jsonl`).
  2. Un CORTE del fichero de verdad, con `--recortar`/`--recortar-tramo`: reescribe
     el `.jsonl` LOCAL que usa la propia app de Claude Code para reconstruir el
     hilo (deja `.antes` con el original). Solo tiene sentido con el hilo YA
     cerrado (si sigue vivo, la app puede volver a escribir encima).
  Y un tercero, más bruto: `--omitir-sesion` reutiliza el `.omitir` que ya tenía
  `continuidad.py` (`mem/sesiones/.omitir`): la sesión entera nunca se copia, ni
  aunque la cierre otro hilo distinto haciendo la cosecha.

Lo que esto NO puede prometer (dicho aquí y en el README, no solo en la cabeza):
lo que ya se mandó a la API de Anthropic dentro del propio turno YA VIAJÓ — esto
no lo puede deshacer, ninguna herramienta local puede. Lo que gobierna es la
memoria LOCAL de este paquete y lo que el propio asistente vuelve a leer en
hilos futuros (sesiones/, bolsas, relojes, sala de relojes). Si el usuario quiere
borrar lo ya enviado, eso es un asunto de retención de datos con Anthropic, no
de este fichero.

Uso (SIN gancho — el asistente lo llama él mismo por Bash cuando el usuario lo
pide, nunca dispara solo):

    python parentesis.py --abrir [motivo] [--sesion <id>]
    python parentesis.py --cerrar [--sesion <id>]
    python parentesis.py --omitir-sesion [id]
    python parentesis.py --recortar <transcript.jsonl> "<último mensaje del usuario que se conserva>"
    python parentesis.py --recortar-tramo <transcript.jsonl> <inicio_iso> <fin_iso>

`--sesion <id>` es una bandera QUE NO PIDE la especificación tal cual pero hace
falta para saber de qué sesión se habla: `--abrir`/`--cerrar` no llegan por un
gancho (ahí sí vendría `session_id` en el JSON de stdin), así que sin `--sesion`
explícito ni `session_id` por stdin (por si alguna vez SÍ llega así) se recurre a
una HEURÍSTICA, dicha como tal: el hilo con el latido más reciente en
`mem/.vivo/` (lo escribe `continuidad.latir()` en cada `UserPromptSubmit`) — justo
antes de que el asistente llame aquí, ESE prompt ya disparó el latido de este
mismo hilo, así que su marca de tiempo es la más fresca. Con varios hilos
mandando prompts a la vez de verdad (no el caso normal) podría acertar el hilo
equivocado; por eso `--sesion` explícito siempre gana si se da. Sin ningún latido
vivo y sin `--sesion`, se rehúsa (código 1) en vez de adivinar.

`--recortar`/`--recortar-tramo` se niegan (código 1, no tocan nada) si el hilo
sigue vivo: `mem/.vivo/<id>.json` con latido de menos de 2 minutos — la app puede
estar a punto de volver a escribir sobre ese mismo `.jsonl`, y un recorte a mitad
de escritura deja el fichero roto. `--recortar` exige que el mensaje dado
coincida EXACTO (tras normalizar espacios) con algún mensaje real del usuario en
ese transcript (no un fragmento): si no lo encuentra, no toca nada y lo dice.

El código vive donde lo instale `rutas.CODE`; los datos (`parentesis.json`, y el
`.omitir` que ya vivía en `mem/sesiones/`) viven en `mem`, resuelto por
`rutas.resolver()` — nunca `dirname(__file__)` (§1 de ESPECIFICACION.md).
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
# leer_stdin_si_hace_falta: esta pieza no necesita ningún otro campo del JSON de
# un gancho más que, como mucho, `session_id` (§ heurística de arriba) — y eso solo
# como ÚLTIMO recurso antes de la heurística del latido. Invocado a mano con
# `--proyecto`/`ABYSS_PROYECTO` (el caso normal, "sin gancho"), no hace falta tocar
# stdin en absoluto.
_STDIN = rutas.leer_stdin_si_hace_falta(sys.argv[1:])
proj, mem = rutas.resolver(sys.argv[1:], _STDIN)
os.environ['ABYSS_PROYECTO'] = proj

RUTA = os.path.join(mem, 'parentesis.json')
SES = os.path.join(mem, 'sesiones')
VIVO = os.path.join(mem, '.vivo')
TOPE_VIVO_S = 120  # 2 minutos (T2.1): por debajo de esto, --recortar/--recortar-tramo se niegan


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
    """¿Cae la marca de tiempo `ts` (de una línea del transcript) dentro de algún
    tramo de paréntesis de `sid`? Un tramo sin cerrar (`--abrir` sin `--cerrar`
    todavía: `fin` es `None`) se trata como abierto hasta AHORA MISMO — así, si la
    sesión se cierra a mitad de un paréntesis que el usuario nunca llegó a
    cerrar explícitamente, nada de lo posterior al `--abrir` se escapa igual.

    Fail-open declarado (no fail-closed) ante datos que no se pueden interpretar:
    una línea SIN `timestamp`, o un `inicio` de tramo corrupto, no se oculta —
    ocultar por defecto cualquier línea sin marca de tiempo escondería mensajes
    que no tienen nada que ver con ningún paréntesis real. Un `fin` corrupto sí
    oculta (mejor de más que de menos, ahí ya sabemos que el tramo existe)."""
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
    """¿Hay un latido de este hilo (`mem/.vivo/<sid>.json`, lo escribe
    `continuidad.latir()`) de menos de `TOPE_VIVO_S`? Sin fichero de latido se
    considera MUERTO — fail-open aquí a propósito: negar un recorte legítimo
    porque el gancho de continuidad nunca llegó a escribir el latido (proyecto sin
    ese módulo instalado, por ejemplo) sería peor que el riesgo contrario."""
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
    (tras normalizar espacios) exactamente `ultimo_mensaje`, INCLUIDA la respuesta
    completa a ese mensaje (todo lo que hay hasta el siguiente turno real del
    usuario, o el final del fichero si no hay ninguno detrás). Dos negativas
    fail-closed: si el hilo sigue vivo, o si ese mensaje no aparece tal cual, no se
    toca nada. `<ruta_jsonl>.antes` guarda el original — solo se crea la PRIMERA
    vez (una segunda llamada no pisa el original con un recorte intermedio).
    Devuelve (ok: bool, mensaje: str)."""
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
