"""Propiocepción de sesión: lo que se puede medir de cada hilo, desde el transcript.
No es un cuerpo. Es el registro de cuánto se hizo, cuánto se pensó, cuántas
correcciones hubo. Cada sesión se compara con la distribución propia (percentil entre
las sesiones registradas), no con un umbral fijo: normales que rotan.

Arranque en frío (§2.2 ESPECIFICACION.md): con menos de UMBRAL_FRIO sesiones medidas
no hay distribución que valga — `percentiles()` devuelve None en vez de inventar un
percentil sobre un puñado de puntos. Fail-closed, nunca a ojo.

El código vive donde lo instale `rutas.CODE`; los datos (sesiones/, propiocepcion.json)
viven en `mem`, resuelto por `rutas.resolver()` — nunca `dirname(__file__)` (§1).

Uso: python propiocepcion.py [id-de-sesión]  → escribe mem/propiocepcion.json
     y muestra la sesión pedida (o la más reciente) contra las demás."""
import sys
try:                       # la consola de Windows y la salida tienen que hablar
    from . import consola  # el mismo idioma: ver abyss/consola.py
except ImportError:
    import consola
consola.preparar()
import os, re, glob, json, gzip
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


def medir(path):
    """Paréntesis: cualquier línea cuya `timestamp` cae dentro de un tramo abierto de
    esta sesión (`parentesis.en_parentesis()`) se salta ENTERA — igual que
    `continuidad.frases_usuario()` — así ni sus turnos, ni sus palabras, ni las fichas
    o sondas que mencione entran en la medida."""
    base = os.path.basename(path)
    if base.endswith('.jsonl.gz'):
        sid = base[:-9]
    elif base.endswith('.jsonl'):
        sid = base[:-6]
    else:
        sid = base
    ts = []; turnos = 0; turnos_limpios = 0; corr = 0; palabras_j = 0; req = {}; tools = 0; fichas = set(); web = 0; sondas = {}
    with abrir_texto(path) as fh:
        for line in fh:
            try:
                d = json.loads(line)
            except Exception:
                continue
            if d.get('isSidechain'):
                continue
            if PZ.en_parentesis(sid, d.get('timestamp')):
                continue
            t = d.get('type'); m = d.get('message') or {}
            if d.get('timestamp'):
                ts.append(d['timestamp'])
            if t == 'user' and not d.get('isMeta'):
                c = m.get('content')
                if isinstance(c, str) and c.strip():
                    # resúmenes de compactación y comandos / entran como `user` pero no son del usuario
                    if c.lstrip().startswith('This session is being continued') or c.lstrip().startswith('<command-name>'):
                        continue
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
                u = m.get('usage') or {}
                if u:
                    req[d.get('requestId') or d.get('uuid')] = u
                for b in (m.get('content') or []):
                    if not (isinstance(b, dict) and b.get('type') == 'tool_use'):
                        continue
                    tools += 1; name = b.get('name'); inp = b.get('input') or {}
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
    out = sum(u.get('output_tokens', 0) for u in req.values())
    think = sum((u.get('output_tokens_details') or {}).get('thinking_tokens', 0) for u in req.values())
    cache = sum(u.get('cache_read_input_tokens', 0) for u in req.values())
    horas = 0.0
    if len(ts) > 1:
        p = lambda s: datetime.fromisoformat(s.replace('Z', '+00:00'))
        horas = (p(max(ts)) - p(min(ts))).total_seconds() / 3600
    return sid, {'inicio': min(ts)[:16] if ts else None, 'horas': round(horas, 1), 'turnos_usuario': turnos,
                 'turnos_usuario_limpios': turnos_limpios,
                 'palabras_usuario': palabras_j, 'respuestas': len(req), 'herramientas': tools, 'tokens_salida': out,
                 'tokens_pensados': think, 'cache_leida': cache, 'web': web, 'correcciones_proxy': corr,
                 'fichas_escritas': sorted(fichas), 'sondas': sondas}


CLAVES = ('horas', 'turnos_usuario', 'turnos_usuario_limpios', 'palabras_usuario', 'respuestas', 'herramientas', 'tokens_salida',
          'tokens_pensados', 'cache_leida', 'web', 'correcciones_proxy')


def medir_todas(extra_dirs=()):
    """Mide todos los transcripts vivos del proyecto + los guardados en mem/sesiones/
    (.jsonl y .jsonl.gz por igual, §2.4)."""
    data = {}
    for d in (proj,) + tuple(extra_dirs):
        for sid, p in archivos_sesion(d):
            _, m = medir(p)
            if m['turnos_usuario'] > 0 and sid not in data:
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
