"""Propiocepción de sesión: lo que se puede medir de cada hilo, desde el transcript.
No es un cuerpo. Es el registro de cuánto se hizo, cuánto se pensó, cuántas
correcciones hubo. Cada sesión se compara con la distribución propia (percentil entre
las sesiones registradas), no con un umbral fijo: normales que rotan.

Arranque en frío (§2.2 ESPECIFICACION.md): con menos de UMBRAL_FRIO sesiones medidas
no hay distribución que valga — `percentiles()` devuelve None en vez de inventar un
percentil sobre un puñado de puntos. Fail-closed, nunca a ojo.

Una sola lectura por fichero (`extraer()`): de cada transcript salen a la vez su medida,
las frases del usuario que usan bolsas y relojes (`continuidad.frases_usuario()`) y los
trozos de línea con los que `varas.py` sabe qué fichas se leyeron. Lo sacado se recuerda
en `mem/.matrioshka/<sid>.json` con la firma del fichero; mientras la firma no cambie,
`extraer()` no vuelve a abrir el transcript. De una sesión en `sesiones/.omitir` no se
recuerda nada, así que esa se lee entera cada vez. La muñeca es memoria de una lectura,
nunca la fuente: borrarla entera solo obliga a releer.

El código vive donde lo instale `rutas.CODE`; los datos (sesiones/, propiocepcion.json,
.matrioshka/) viven en `mem`, resuelto por `rutas.resolver()` — nunca
`dirname(__file__)` (§1).

Uso: python propiocepcion.py [id-de-sesión]  → escribe mem/propiocepcion.json
     y muestra la sesión pedida (o la más reciente) contra las demás."""
import sys
try:                       # la consola de Windows y la salida tienen que hablar
    from . import consola  # el mismo idioma: ver abyss/consola.py
except ImportError:
    import consola
consola.preparar()
import os, re, glob, json, gzip, hashlib, time, unicodedata
from datetime import datetime

try:
    from . import rutas
except ImportError:
    import rutas

CODE = rutas.CODE
# leer_stdin_si_hace_falta: cuando este módulo lo importan continuidad.py/vigia.py,
# ABYSS_PROYECTO YA está puesto (lo dejaron ellos antes del import); sin mirar el
# entorno antes de leer stdin, se pagaría un peaje de segundos de más en cada
# --cosecha/--arranque.
_STDIN = rutas.leer_stdin_si_hace_falta(sys.argv[1:])
proj, mem = rutas.resolver(sys.argv[1:], _STDIN)
os.environ['ABYSS_PROYECTO'] = proj  # para que quien importe este módulo después no tenga que releer stdin

# Paréntesis: se importa DESPUÉS de fijar ABYSS_PROYECTO (igual que hace
# continuidad.py con este mismo módulo) para que la propia resolución de
# `parentesis.py` no vuelva a tocar stdin.
try:
    from . import parentesis as PZ
except ImportError:
    import parentesis as PZ

OUT = os.path.join(mem, 'propiocepcion.json')
UMBRAL_FRIO = 8  # sesiones medidas mínimas para fiarse de un percentil (§2.2)
# proxy TOSCO de corrección: arranque de un mensaje del usuario que niega o corrige.
# Lista cerrada: un proxy tosco, no un juicio.
CORR = re.compile(r'^\s*(no\b|nop\b|mal\b|mentira|falso|te equivocas|eso no|no es (así|cierto|verdad)|error\b|te has equivocado|no me refer)', re.I)
FICHA = re.compile(r'([\w\-.%áéíóúñ]+\.md)')

SES = os.path.join(mem, 'sesiones')
MUNECAS = os.path.join(mem, rutas.MATRIOSHKA)
# De una línea que lee memoria se guardan, por cada `.md`, los VENTANA_LECTURA caracteres
# de antes: un nombre de fichero no pasa de 255, así que la ficha entera cae dentro.
VENTANA_LECTURA = 512
SEP_LECTURAS = '\x00'  # une los trozos: ningún nombre de fichero lleva NUL en ningún sistema
MAX_ENTRADAS = 4       # por sesión: transcript, copia, y lo mismo sacado por otra copia del código


def abrir_texto(path):
    """Abre un .jsonl o un .jsonl.gz igual, como texto UTF-8 tolerante (§2.4: las
    sesiones viejas se gzipean con `continuidad.py --comprimir` y hay que poder
    seguir leyéndolas)."""
    if path.endswith('.gz'):
        return gzip.open(path, 'rt', encoding='utf-8', errors='ignore')
    return open(path, encoding='utf-8', errors='ignore')


def archivos_sesion(directorio):
    """[(sid, ruta)] de las sesiones .jsonl y .jsonl.gz de un directorio, sin duplicar:
    si existen las dos formas para el mismo id, gana la sin comprimir (es la más nueva;
    --comprimir borra el .jsonl en cuanto escribe el .gz, así que solo coexisten un
    instante)."""
    out = {}
    for p in glob.glob(os.path.join(directorio, '*.jsonl.gz')):
        out[os.path.basename(p)[:-9]] = p
    for p in glob.glob(os.path.join(directorio, '*.jsonl')):
        out[os.path.basename(p)[:-6]] = p
    return sorted(out.items())


def _sid_de(path):
    base = os.path.basename(path)
    if base.endswith('.jsonl.gz'):
        return base[:-9]
    if base.endswith('.jsonl'):
        return base[:-6]
    return base


def _huella_codigo():
    """Qué código y qué Python sacan lo que se recuerda: los bytes de este fichero y de
    `parentesis.py` (lo que decide qué entra y qué se salta), la versión de Python y la de
    su tabla Unicode (la NFC de las lecturas). Se calcula al importar, así un proceso que
    cargó el código viejo nunca firma con la huella del nuevo. Si no se pueden leer, None:
    sin huella no se recuerda nada."""
    h = hashlib.sha1()
    try:
        for nombre in ('propiocepcion.py', 'parentesis.py'):
            with open(os.path.join(CODE, nombre), 'rb') as fh:
                h.update(fh.read())
    except OSError:
        return None
    h.update(f'{sys.version_info[0]}.{sys.version_info[1]} {unicodedata.unidata_version}'.encode('ascii'))
    return h.hexdigest()


HUELLA = _huella_codigo()
_CLAVES_MEDIDA = ('inicio', 'horas', 'turnos_usuario', 'turnos_usuario_limpios', 'palabras_usuario', 'respuestas',
                  'herramientas', 'tokens_salida', 'tokens_pensados', 'cache_leida', 'web', 'correcciones_proxy',
                  'fichas_escritas', 'sondas')
_MEMO = {}  # (sid, firma) -> entrada: dentro de un proceso nadie relee el mismo fichero ni la misma muñeca


def sesiones_omitidas():
    """Ids de `sesiones/.omitir`: las sesiones que el usuario pidió no guardar
    (`parentesis.py --omitir-sesion`). `continuidad.guardar()` no las copia, y de ellas no
    se recuerda nada en `.matrioshka/`."""
    try:
        with open(os.path.join(SES, '.omitir'), encoding='utf-8') as fh:
            return {l.strip() for l in fh if l.strip()}
    except Exception:
        return set()


def _es_lectura_de_memoria(line):
    """El filtro de `varas.py` sobre la línea CRUDA: nombra `memory` y trae un `Read` (JSON
    compacto, como lo escribe el harness) o un `cat `. Sin parsear, así que vale igual para
    las líneas de sidechain y para las que no son JSON."""
    return 'memory' in line and ('"name":"Read"' in line or 'cat ' in line)


def _trozos_con_md(linea, trozos):
    """Añade a `trozos` los segmentos de `linea` (ya en NFC) que acaban en cada `.md` y
    empiezan VENTANA_LECTURA caracteres antes, fundiendo los que se solapan. Como toda
    ficha termina en `.md`, una ficha está en la línea si y solo si está en un segmento."""
    i = linea.find('.md'); ini_seg = fin_seg = None
    while i != -1:
        ini, fin = max(0, i - VENTANA_LECTURA), i + 3
        if fin_seg is not None and ini <= fin_seg:
            fin_seg = fin
        else:
            if fin_seg is not None:
                trozos.add(linea[ini_seg:fin_seg])
            ini_seg, fin_seg = ini, fin
        i = linea.find('.md', fin)
    if fin_seg is not None:
        trozos.add(linea[ini_seg:fin_seg])


def _objeto(x):
    """`x` si es un objeto JSON (dict); si no, uno vacío. Lo que venía vacío sigue vacío."""
    return x if isinstance(x, dict) else {}


def _numero(x):
    """`x` si es un número; si no (un texto, una lista), 0: no suma lo que no se entiende."""
    return x if isinstance(x, (int, float)) else 0


def _horas(ts):
    """Horas de la primera a la última marca de tiempo (texto ISO). Con todas legibles, la
    resta de siempre; si alguna no se entiende, cuentan solo las que sí, y si mezclan hora con
    zona y sin zona no hay resta que valga: 0."""
    if len(ts) < 2:
        return 0.0
    p = lambda s: datetime.fromisoformat(s.replace('Z', '+00:00'))
    try:
        return (p(max(ts)) - p(min(ts))).total_seconds() / 3600
    except (ValueError, TypeError):
        pass
    fechas = []
    for s in ts:
        try:
            fechas.append(p(s))
        except ValueError:
            continue
    try:
        return (max(fechas) - min(fechas)).total_seconds() / 3600 if len(fechas) > 1 else 0.0
    except TypeError:
        return 0.0


def _leer_sesion(path, lista):
    """UNA lectura del fichero. Devuelve (entrada, acaba_en_salto); la entrada lleva:
      - 'medida': lo que siempre midió este módulo;
      - 'frases': las de `continuidad.frases_usuario()` (usuario, no meta, no sidechain,
        sin compactación ni `<command-name>`, espacios colapsados);
      - 'lecturas': los trozos que mira `varas.py`, sacados de la línea CRUDA como siempre
        los sacó `varas` (también de sidechain y de líneas que no son JSON), unidos por
        SEP_LECTURAS.
    Una línea JSON que no es un objeto solo puede contar para las lecturas. De una línea con
    campos de otra forma —un `message`, un `usage` o un `input` que no son objetos, un número
    escrito como texto, una marca de tiempo que no es ISO— lo que no se entiende no cuenta,
    y el resto de la sesión se mide igual.

    Paréntesis: cualquier línea cuya `timestamp` cae dentro de un tramo de esta sesión
    (`lista`, leída una vez por quien llama) se salta ENTERA — ni sus turnos, ni sus
    palabras, ni sus frases, ni las fichas, sondas o lecturas que mencione."""
    ts = []; turnos = 0; turnos_limpios = 0; corr = 0; palabras_j = 0; req = {}; tools = 0; fichas = set(); web = 0; sondas = {}
    frases = []; trozos = set(); acaba_en_salto = True
    with abrir_texto(path) as fh:
        for line in fh:
            acaba_en_salto = line.endswith('\n')
            try:
                d = json.loads(line)
            except Exception:
                d = None
            if _es_lectura_de_memoria(line) and \
                    not PZ.en_tramos(lista, d.get('timestamp') if isinstance(d, dict) else None):
                _trozos_con_md(unicodedata.normalize('NFC', line), trozos)
            if not isinstance(d, dict) or d.get('isSidechain'):
                continue
            if PZ.en_tramos(lista, d.get('timestamp')):
                continue
            t = d.get('type'); m = _objeto(d.get('message'))
            if d.get('timestamp') and isinstance(d['timestamp'], str):
                ts.append(d['timestamp'])
            if t == 'user' and not d.get('isMeta'):
                c = m.get('content')
                if isinstance(c, str) and c.strip():
                    # resúmenes de compactación y comandos / entran como `user` pero no son del usuario
                    if c.lstrip().startswith('This session is being continued') or c.lstrip().startswith('<command-name>'):
                        continue
                    frases.append(re.sub(r'\s+', ' ', c.strip()))
                    turnos += 1; palabras_j += len(c.split())
                    # Hay mucho más que tampoco escribió nadie: avisos de tareas en segundo
                    # plano, recordatorios del sistema, resultados que vuelven — todo llega
                    # como `user` y empieza por '<'; contarlo infla el denominador y hace
                    # parecer rarísima cualquier corrección.
                    # `turnos_usuario` no cambia: relojes.jsonl es de solo añadir y
                    # `continuidad.py` compara ese número para saber si una sesión ya está
                    # apuntada; cambiarlo mezclaría dos varas en el mismo fichero.
                    if not c.lstrip().startswith('<'):
                        turnos_limpios += 1
                    if CORR.match(c):
                        corr += 1
            elif t == 'assistant':
                u = _objeto(m.get('usage'))
                if u:
                    try:
                        req[d.get('requestId') or d.get('uuid')] = u
                    except TypeError:  # un id que no puede ser clave
                        pass
                contenido = m.get('content')
                for b in (contenido if isinstance(contenido, list) else []):
                    if not (isinstance(b, dict) and b.get('type') == 'tool_use'):
                        continue
                    tools += 1; name = b.get('name'); inp = _objeto(b.get('input'))
                    if name in ('WebSearch', 'WebFetch'):
                        web += 1
                    if name == 'Agent':  # cuenta qué modelo se usó para cada sub-tarea delegada
                        sondas[str(inp.get('model') or 'por-defecto')] = sondas.get(str(inp.get('model') or 'por-defecto'), 0) + 1
                    if name == 'Write' and 'memory' in str(inp.get('file_path', '')):
                        fichas.add(os.path.basename(str(inp['file_path']).replace('\\', '/')))
                    elif name in ('Bash', 'PowerShell'):
                        cmd = str(inp.get('command', ''))
                        if 'memory' in cmd:
                            for seg in re.findall(r'cat\s*>>?\s*(\S+)', cmd):
                                mm = FICHA.search(seg.replace('\\', '/').split('/')[-1])
                                if mm:
                                    fichas.add(mm.group(1))
    out = sum(_numero(u.get('output_tokens', 0)) for u in req.values())
    think = sum(_numero(_objeto(u.get('output_tokens_details')).get('thinking_tokens', 0)) for u in req.values())
    cache = sum(_numero(u.get('cache_read_input_tokens', 0)) for u in req.values())
    horas = _horas(ts)
    medida = {'inicio': min(ts)[:16] if ts else None, 'horas': round(horas, 1), 'turnos_usuario': turnos,
              'turnos_usuario_limpios': turnos_limpios,
              'palabras_usuario': palabras_j, 'respuestas': len(req), 'herramientas': tools, 'tokens_salida': out,
              'tokens_pensados': think, 'cache_leida': cache, 'web': web, 'correcciones_proxy': corr,
              'fichas_escritas': sorted(fichas), 'sondas': sondas}
    return {'medida': medida, 'frases': frases, 'lecturas': SEP_LECTURAS.join(sorted(trozos))}, acaba_en_salto


# ---------- la muñeca: lo que dijo una lectura, con la firma de lo que se leyó ----------

def _firma(path, sid):
    """(firma, tramos) de un fichero ANTES de leerlo: tamaño, mtime en ns, los tramos de
    paréntesis de su sesión (como listas, igual que vuelven del JSON) y la huella del código."""
    lista = [list(t) for t in PZ.tramos(sid)]
    st = os.stat(path)
    return [st.st_size, st.st_mtime_ns, lista, HUELLA], lista


def _variantes(sid):
    """Los ficheros que puede tener una sesión: su transcript vivo y sus copias."""
    return (os.path.join(proj, sid + '.jsonl'), os.path.join(SES, sid + '.jsonl'),
            os.path.join(SES, sid + '.jsonl.gz'))


def _ruta_muneca(sid):
    return os.path.join(MUNECAS, sid + '.json')


def _leer_muneca(sid, firma):
    """La entrada de `.matrioshka/<sid>.json` con esta firma exacta, o None. Cualquier fallo
    (no existe, JSON roto, bytes que no son UTF-8, otra forma) es None: la muñeca ahorra
    una lectura, nunca decide un resultado."""
    try:
        with open(_ruta_muneca(sid), encoding='utf-8') as fh:
            entradas = json.load(fh)['entradas']
        for e in entradas:
            if e['firma'] != firma:
                continue
            medida, frases, lecturas_ = e['medida'], e['frases'], e['lecturas']
            if (isinstance(medida, dict) and all(k in medida for k in _CLAVES_MEDIDA)
                    and isinstance(frases, list) and all(isinstance(x, str) for x in frases)
                    and isinstance(lecturas_, str)):
                return {'medida': medida, 'frases': frases, 'lecturas': lecturas_}
    except Exception:
        pass
    return None


def _guardar_muneca(sid, firma, entrada):
    """Escribe la entrada en `.matrioshka/<sid>.json` de forma atómica (temporal de este
    proceso + `os.replace`). Se quedan las entradas de otras firmas cuyo tamaño, mtime y
    tramos siguen casando con un fichero vivo de la sesión —la del transcript, la de su
    copia, o la misma sacada por otra copia del código—, hasta MAX_ENTRADAS. Si algo falla
    (otro proceso la tiene abierta, disco lleno, un carácter que no se puede volcar) no se
    guarda y ya está.

    Si la sesión entró en `.omitir` mientras se leía, lo recién guardado se borra en el
    acto: `parentesis.py --omitir-sesion` apunta la sesión antes de borrar su muñeca, así
    que en cualquier orden una de las dos partes la quita."""
    ruta = _ruta_muneca(sid)
    tmp = f'{ruta}.{os.getpid()}.tmp'
    try:
        vivas = []
        for p in _variantes(sid):
            try:
                st = os.stat(p)
            except OSError:
                continue
            vivas.append([st.st_size, st.st_mtime_ns, firma[2]])
        try:
            with open(ruta, encoding='utf-8') as fh:
                previas = [e for e in json.load(fh)['entradas']
                           if isinstance(e, dict) and isinstance(e.get('firma'), list) and len(e['firma']) == 4
                           and e['firma'] != firma and e['firma'][:3] in vivas]
        except Exception:
            previas = []
        os.makedirs(MUNECAS, exist_ok=True)
        with open(tmp, 'w', encoding='utf-8') as fh:
            json.dump({'entradas': (previas + [dict(entrada, firma=firma)])[-MAX_ENTRADAS:]}, fh, ensure_ascii=True)
        os.replace(tmp, ruta)
        if sid in sesiones_omitidas():
            os.remove(ruta)
    except Exception:
        try:
            os.remove(tmp)
        except OSError:
            pass


def extraer(path):
    """Lo que UNA lectura de `path` dice de su sesión: {'medida', 'frases', 'lecturas'} (ver
    `_leer_sesion`), recordado en `.matrioshka/<sid>.json` con la firma del fichero.

    La matrioshka: la línea está dentro de la sesión, la sesión dentro de su muñeca, y las
    muñecas dentro de lo que se mide del proyecto (propiocepcion.json, relojes, bolsas, los ◆
    del índice). Si la firma no cambió —mismo tamaño, mismo mtime, mismos tramos, mismo
    código—, se devuelve lo recordado sin abrir el fichero; si cambió algo, se relee.

    No se recuerda nada de una sesión en `.omitir`, ni lo leído mientras el fichero cambiaba:
    el stat de después tiene que coincidir con el de antes, y la última línea tiene que
    estar completa. Límite de la firma: un fichero reescrito con el mismo tamaño dentro del
    mismo tick de mtime pasaría por el mismo; quienes escriben estos ficheros (Claude Code
    añadiendo líneas, `parentesis.py` recortando, la copia filtrada de `continuidad.py`)
    siempre cambian el tamaño o los tramos."""
    sid = _sid_de(path)
    firma, lista = _firma(path, sid)
    clave = (sid, json.dumps(firma))
    if clave in _MEMO:
        return _MEMO[clave]
    recordable = HUELLA is not None and sid not in sesiones_omitidas()
    entrada = _leer_muneca(sid, firma) if recordable else None
    if entrada is None:
        entrada, completa = _leer_sesion(path, lista)
        if recordable and completa:
            try:
                st = os.stat(path)
                if [st.st_size, st.st_mtime_ns] == firma[:2]:
                    _guardar_muneca(sid, firma, entrada)
            except OSError:
                pass
    _MEMO[clave] = entrada
    return entrada


def lecturas(path):
    """Los trozos de `path` que `varas.py` mira para saber qué fichas leyó su sesión. De la
    muñeca si hay una con su firma; si no, el recorrido barato de siempre —solo se parsean
    las líneas candidatas— y NO se guarda nada: `varas.py` nunca escribe en `.matrioshka/`."""
    sid = _sid_de(path)
    firma, lista = _firma(path, sid)
    clave = (sid, json.dumps(firma))
    if clave in _MEMO:
        return _MEMO[clave]['lecturas']
    if HUELLA is not None and sid not in sesiones_omitidas():
        entrada = _leer_muneca(sid, firma)
        if entrada is not None:
            _MEMO[clave] = entrada
            return entrada['lecturas']
    trozos = set()
    with abrir_texto(path) as fh:
        for line in fh:
            if not _es_lectura_de_memoria(line):
                continue
            try:
                d = json.loads(line)
            except Exception:
                d = None
            if PZ.en_tramos(lista, d.get('timestamp') if isinstance(d, dict) else None):
                continue
            _trozos_con_md(unicodedata.normalize('NFC', line), trozos)
    return SEP_LECTURAS.join(sorted(trozos))


def barrer_munecas():
    """Quita de `.matrioshka/` lo que ya no debe estar: la muñeca de una sesión en
    `.omitir`, la de una sesión sin ningún fichero (ni transcript ni copia), y los
    temporales de más de diez minutos que dejó un proceso interrumpido. Devuelve cuántos
    ficheros quitó."""
    try:
        nombres = os.listdir(MUNECAS)
    except OSError:
        return 0
    omitidas = sesiones_omitidas(); ahora = time.time(); n = 0
    for nombre in nombres:
        ruta = os.path.join(MUNECAS, nombre)
        try:
            if nombre.endswith('.tmp'):
                if ahora - os.path.getmtime(ruta) > 600:
                    os.remove(ruta); n += 1
            elif nombre.endswith('.json'):
                sid = nombre[:-5]
                if sid in omitidas or not any(os.path.exists(p) for p in _variantes(sid)):
                    os.remove(ruta); n += 1
        except OSError:
            continue
    return n


def medir(path):
    """(sid, medida) de un transcript: la medida de `extraer()`."""
    return _sid_de(path), extraer(path)['medida']


CLAVES = ('horas', 'turnos_usuario', 'turnos_usuario_limpios', 'palabras_usuario', 'respuestas', 'herramientas', 'tokens_salida',
          'tokens_pensados', 'cache_leida', 'web', 'correcciones_proxy')


def medir_todas(extra_dirs=()):
    """Mide todos los transcripts vivos del proyecto + los guardados en mem/sesiones/
    (.jsonl y .jsonl.gz por igual, §2.4). Una sesión ya medida en un directorio no se
    vuelve a medir en el siguiente: cuenta la primera medida con turnos, como siempre."""
    data = {}
    for d in (proj,) + tuple(extra_dirs):
        for sid, p in archivos_sesion(d):
            if sid in data:
                continue
            _, m = medir(p)
            if m['turnos_usuario'] > 0:
                data[sid] = m
    with open(OUT, 'w', encoding='utf-8') as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
    return data


def percentiles(data, sid):
    """Una sesión contra la distribución propia: {clave: (valor, mediana, percentil)}.

    Arranque en frío (§2.2): con menos de UMBRAL_FRIO sesiones medidas devuelve None
    — sin vara todavía, no se inventa un percentil sobre una distribución que casi
    no existe."""
    n = len(data)
    if n < UMBRAL_FRIO:
        return None
    me = data[sid]; out = {}
    for k in CLAVES:
        vals = sorted(d[k] for d in data.values()); v = me[k]
        out[k] = (v, vals[n // 2], round(100 * sum(1 for x in vals if x <= v) / n))
    r = me['correcciones_proxy'] / max(1, me['turnos_usuario'])
    rs = sorted(d['correcciones_proxy'] / max(1, d['turnos_usuario']) for d in data.values())
    out['tasa_correccion'] = (round(r, 2), round(rs[n // 2], 2), round(100 * sum(1 for x in rs if x <= r) / n))
    return out


def _posicionales(argv):
    """argv sin `--proyecto <valor>` ni otras banderas: lo que queda es el id de sesión."""
    out = []; saltar = False
    for a in argv:
        if saltar:
            saltar = False; continue
        if a == '--proyecto':
            saltar = True; continue
        if a.startswith('--'):
            continue
        out.append(a)
    return out


if __name__ == '__main__':
    argv_pos = _posicionales(sys.argv[1:])
    data = medir_todas([os.path.join(mem, 'sesiones')])
    if not data:
        print(f'sin datos que medir todavía en {mem}')
        sys.exit(0)
    want = argv_pos[0] if argv_pos else max(data, key=lambda s: data[s]['inicio'] or '')
    if want not in data:
        print(f'{want[:8]} no está entre las {len(data)} sesiones medidas')
        sys.exit(1)
    me = data[want]
    print(f'sesión {want[:8]}  inicio {me["inicio"]}  ({len(data)} sesiones medidas)')
    pc = percentiles(data, want)
    if pc is None:
        print(f'  sin vara todavía (n={len(data)}) — hacen falta {UMBRAL_FRIO} sesiones medidas para comparar')
    else:
        for k, (v, med, pct) in pc.items():
            print(f'  {k:18} {v:>10}   mediana mía {med:>9}   percentil {pct:3}')
    print('  fichas escritas:', len(me['fichas_escritas']), me['fichas_escritas'])
