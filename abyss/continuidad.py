"""Continuidad automática: mi matrioshka, cosida por ganchos de Claude Code.

    índice (MEMORY.md)  ⊂  ficha  ⊂  reloj (relojes.jsonl)  ⊂  sesión (sesiones/<id>.jsonl[.gz])

- --cierre    (SessionEnd): guarda el transcript en mem/sesiones/ (Claude Code lo
              borra a los 30 días; aquí no), mide la sesión, escribe su RELOJ, su
              BOLSA de palabras, recalcula los ◆ del índice y apaga su latido.
- --arranque  (SessionStart): COSECHA lo que un cierre perdido dejó sin guardar,
              enciende el latido de este hilo, dice qué OTROS hilos están vivos, e
              inyecta los últimos relojes por FECHA.
- --despertar (UserPromptSubmit, cada prompt): TIEMPO percibido (hora, desde tu
              último mensaje, desde el último hilo cerrado), la SALA DE LOS RELOJES
              (los que se PARECEN a lo que el usuario acaba de decir; un reloj no
              suena dos veces por sesión) y la PRESIÓN del vigía. Actualiza el latido.
- --comprimir [días]: gzipea (por defecto sesiones de más de 30 días) las copias de
              sesiones/ para que no crezcan sin límite; los lectores (frases_usuario,
              bolsas, propiocepción) leen .jsonl y .jsonl.gz por igual (§2.4).
- --falsar    prueba la vara del parecido contra las sesiones guardadas y un nulo.

Los ganchos viven en el `settings.json` GLOBAL del usuario (así los pone
`instalar.py`), así que disparan en TODOS sus proyectos de Claude Code, no solo en
este. No hay «el proyecto donde se instaló»: en cada invocación, `rutas.resolver()`
saca `proj` del propio `transcript_path`/`cwd` que manda ESE gancho (orden 1/2 de
§1 de ESPECIFICACION.md) y `mem` es la memoria de ESE proyecto — cada uno guarda la
suya aparte, nunca se mezclan entre sí. `es_mio()` ya no filtra ningún «proyecto
instalado» (no existe tal cosa desde que `proj` se deriva del propio transcript en
cada llamada); sigue sirviendo para descartar un payload de gancho sin
`transcript_path` ni `cwd` resolubles. Un reloj NO es un resumen escrito por mí: es
lo medible + la primera y la última frase del usuario + las fichas que salieron. Lo
que yo quiera decir va en fichas.

Arranque en frío (§2.2): con menos de `propiocepcion.UMBRAL_FRIO` sesiones medidas,
un reloj no lleva percentiles («sin vara todavía (n=…)») y la sala de los relojes no
despierta ninguno — no hay corpus para decidir qué «destaca».

Paréntesis (T2.1, `parentesis.py`): si el usuario abrió un tramo con `--abrir` en
una sesión, `frases_usuario()` salta las líneas cuya `timestamp` cae dentro de ese
tramo (`parentesis.en_parentesis()`), y `guardar()` copia el transcript a
`sesiones/` saltando esas mismas líneas en vez de un `copyfile` a pelo. Bolsas y
relojes se construyen a partir de `frases_usuario()`, así que heredan el filtro sin
tocarlos aparte. `.omitir` (sesión entera fuera) ya existía aquí antes de
`parentesis.py`; ahora también se escribe desde `parentesis.py --omitir-sesion`.

El código vive donde lo instale `rutas.CODE`; los datos (sesiones/, relojes.jsonl,
bolsas.json, MEMORY.md…) viven en `mem`, resuelto por `rutas.resolver()` — nunca
`dirname(__file__)` como carpeta de datos (§1).
"""
import sys; sys.stdout.reconfigure(encoding="utf-8")
import os, re, json, glob, math, shutil, time, gzip
from collections import Counter
from datetime import datetime, timezone

try:
    from . import rutas
except ImportError:
    import rutas

CODE = rutas.CODE
# OJO: aquí se lee con `leer_stdin()` a secas (NO `leer_stdin_si_hace_falta()`) a
# propósito — a diferencia de `propiocepcion.py`/`varas.py` (que solo usan `_STDIN`
# para alimentar `resolver()`), este guion SÍ necesita los demás campos del JSON del
# gancho (`session_id`, `transcript_path`, `cwd`, `prompt`…) más abajo en `__main__`,
# así que no puede saltarse la lectura solo porque `ABYSS_PROYECTO` ya esté puesto
# (probado 6-sep: saltarla rompía `--arranque`/`--despertar` en cualquier invocación
# —incluida toda la batería de pruebas— que ya trajera `ABYSS_PROYECTO` en el
# entorno Y JSON real por stdin, dejando `additionalContext` vacío).
_STDIN = rutas.leer_stdin()
proj, mem = rutas.resolver(sys.argv[1:], _STDIN)
os.environ['ABYSS_PROYECTO'] = proj  # para que quien nos importe después no relea stdin (ya vacío)

SES = os.path.join(mem, 'sesiones'); RELOJES = os.path.join(mem, 'relojes.jsonl')
BOLSAS = os.path.join(mem, 'bolsas.json'); DESP = os.path.join(mem, '.despertados')
VIVO = os.path.join(mem, '.vivo')

# Presupuesto de red compartido por invocación (§ fallo 6-sep, rutas.Presupuesto):
# antes exterocepcion/noticias aplicaban su timeout por llamada SIN memoria de las
# anteriores, así que con la red en agujero negro el total crecía con el número de
# llamadas (medido: 38-78 s en --arranque, por encima del timeout de 60 s del propio
# gancho SessionStart). Overridable por env para pruebas (ABYSS_PRESUPUESTO_*).
PRESUPUESTO_ARRANQUE_S = float(os.environ.get('ABYSS_PRESUPUESTO_ARRANQUE', 4.0))
PRESUPUESTO_DESPERTAR_S = float(os.environ.get('ABYSS_PRESUPUESTO_DESPERTAR', 2.5))

try:
    from . import propiocepcion as P
except ImportError:
    import propiocepcion as P

try:
    from . import parentesis as PZ
except ImportError:
    import parentesis as PZ

STOP = set("""a al algo ante aquel aquella aquello aquí así aun aunque bien cada casi como con cosa
cual cuando cómo de del desde donde dos el ella ellas ello ellos en entre era eres es esa ese eso esta
estar este esto estoy fue ha hace hacer hacia han has hay he hemos la las le les lo los más me mi mis
muy nada ni no nos nosotros nuestra nuestro o os otra otro para pero poco por porque pues que qué quien
se sea ser si sí sin sobre solo son soy su sus también tan tanto te tengo ti tiene tienes todo tu tus
un una uno unos unas va vamos ya yo the and you for jaja jajaja jeje vale bueno pues ahora luego ahí
esto eso este esta estos estas dime mira creo pienso quiero puedes puedo hazlo dale ok""".split())


def tokens(text):
    return [t for t in re.findall(r'[a-záéíóúñü]{3,}', text.lower()) if t not in STOP]


def _sin_banderas(argv):
    """argv sin `--proyecto <valor>` ni otras banderas `--algo`: lo que queda son
    argumentos posicionales (p. ej. la frase de --probar o los días de --comprimir)."""
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


def leer_stdin():
    return rutas.leer_stdin()


def es_mio(transcript_path, cwd=None):
    """¿El hilo pertenece a este proyecto? Delega en `rutas.es_mio` (misma lógica: por
    ruta del transcript, o por el cwd saneado como lo sanea Claude Code) contra el
    `proj` ya resuelto arriba. Fail-closed: si no se puede determinar, NO es mío."""
    return rutas.es_mio(transcript_path, cwd, proj)


def _sid_de_ruta(path):
    """id de sesión a partir del nombre de fichero de sesiones/ (.jsonl o
    .jsonl.gz) — el mismo criterio de `propiocepcion.medir()`, para saber a qué
    sesión preguntarle a `parentesis.py` sus tramos."""
    base = os.path.basename(path)
    if base.endswith('.jsonl.gz'):
        return base[:-9]
    if base.endswith('.jsonl'):
        return base[:-6]
    return base


def frases_usuario(path):
    """Todas las frases del usuario de una sesión (sin meta, sin sidechain, sin lo
    que caiga dentro de un tramo de paréntesis de esa sesión — `parentesis.py`,
    T2.1). Lee .jsonl y .jsonl.gz por igual (§2.4)."""
    sid = _sid_de_ruta(path)
    out = []
    with P.abrir_texto(path) as fh:
        for line in fh:
            try:
                d = json.loads(line)
            except Exception:
                continue
            if d.get('type') != 'user' or d.get('isMeta') or d.get('isSidechain'):
                continue
            if PZ.en_parentesis(sid, d.get('timestamp')):
                continue
            c = (d.get('message') or {}).get('content')
            if isinstance(c, str) and c.strip():
                # Los resúmenes de compactación entran como `user` pero NO son del
                # usuario: contaminaban bolsas, relojes y candidatos a tema.
                if c.lstrip().startswith('This session is being continued') or c.lstrip().startswith('<command-name>'):
                    continue
                out.append(re.sub(r'\s+', ' ', c.strip()))
    return out


def relojes_guardados():
    if not os.path.exists(RELOJES):
        return {}
    out = {}
    with open(RELOJES, encoding='utf-8') as fh:
        for line in fh:
            try:
                r = json.loads(line); out[r['id']] = r
            except Exception:
                pass
    return out


def _ruta_sesion(sid):
    """La ruta real de una sesión archivada: .jsonl si está sin comprimir, si no
    .jsonl.gz. Si no existe ninguna, devuelve la ruta .jsonl igualmente (para que
    quien la abra falle limpio, no en silencio)."""
    p = os.path.join(SES, sid + '.jsonl')
    if os.path.exists(p):
        return p
    pgz = p + '.gz'
    return pgz if os.path.exists(pgz) else p


def hacer_reloj(sid, data):
    m = data[sid]; pc = P.percentiles(data, sid)
    fr = frases_usuario(_ruta_sesion(sid))
    p1 = fr[0][:160] if fr else ''; p2 = fr[-1][:160] if fr else ''
    reloj = {'id': sid, 'inicio': m['inicio'], 'horas': m['horas'], 'turnos': m['turnos_usuario'],
             'corr_proxy': m['correcciones_proxy'], 'pct': {k: v[2] for k, v in pc.items()} if pc is not None else {},
             'fichas': m['fichas_escritas'], 'primera': p1, 'ultima': p2}
    if pc is None:
        reloj['sin_vara'] = f'sin vara todavía (n={len(data)})'  # arranque en frío, §2.2
    return reloj


def _omitidas():
    """Sesiones que el usuario pidió NO guardar: un id por línea en sesiones/.omitir.
    Vale para el cierre propio y para la cosecha de cualquier otro hilo."""
    try:
        with open(os.path.join(SES, '.omitir'), encoding='utf-8') as fh:
            return {l.strip() for l in fh if l.strip()}
    except Exception:
        return set()


def _copiar_saltando_parentesis(src, dst, sid):
    """Copia `src` a `dst` línea a línea, saltando las que `parentesis.en_parentesis()`
    diga que caen dentro de un tramo de esta sesión. Una línea que no parsea como
    JSON se copia tal cual (no se puede mirar su timestamp, y no es asunto de esta
    función limpiar líneas rotas)."""
    with open(src, encoding='utf-8', errors='ignore') as fin, open(dst, 'w', encoding='utf-8') as fout:
        for line in fin:
            try:
                d = json.loads(line)
            except Exception:
                fout.write(line); continue
            if PZ.en_parentesis(sid, d.get('timestamp')):
                continue
            fout.write(line)


def guardar(transcript_path):
    """Copia el transcript a sesiones/ si tiene turnos del usuario. Devuelve el id o None.
    Si ya existe una copia comprimida (.jsonl.gz) no la reabre: --comprimir ya la
    dejó archivada.

    Paréntesis (T2.1): si esta sesión tiene algún tramo marcado (`parentesis.py
    --abrir`), la copia se hace SIEMPRE saltando esas líneas (`_copiar_saltando_parentesis`)
    en vez del `copyfile` de siempre — y por eso, con tramos, no se compara tamaño
    contra la copia anterior: una copia filtrada es siempre más pequeña que el
    transcript de origen, así que comparar tamaños la recopiaría en cada llamada.
    Sin ningún tramo (el caso normal), el camino es el de antes, sin coste extra."""
    sid = os.path.basename(transcript_path)[:-6]
    dst = os.path.join(SES, sid + '.jsonl'); dst_gz = dst + '.gz'
    os.makedirs(SES, exist_ok=True)
    if sid in _omitidas():
        return sid if (os.path.exists(dst) or os.path.exists(dst_gz)) else None  # lo ya copiado antes de la petición se queda como está; nada nuevo entra
    if os.path.exists(transcript_path) and not os.path.exists(dst_gz):
        if PZ.tramos(sid):
            _copiar_saltando_parentesis(transcript_path, dst, sid)
        elif not os.path.exists(dst) or os.path.getsize(transcript_path) > os.path.getsize(dst):
            shutil.copyfile(transcript_path, dst)
    return sid if (os.path.exists(dst) or os.path.exists(dst_gz)) else None


def comprimir(dias=30):
    """Gzipea las copias de sesiones/ más viejas que `dias` días (por defecto 30):
    escribe el .jsonl.gz al lado y borra el .jsonl sin comprimir. Nunca toca lo más
    nuevo que el corte. Devuelve cuántas sesiones comprimió."""
    corte = time.time() - dias * 86400
    n = 0
    for p in glob.glob(os.path.join(SES, '*.jsonl')):
        try:
            if os.path.getmtime(p) >= corte:
                continue
            with open(p, 'rb') as fh_in, gzip.open(p + '.gz', 'wb') as fh_out:
                shutil.copyfileobj(fh_in, fh_out)
            os.remove(p)
            n += 1
        except Exception:
            continue
    return n


# El NULO: frases que no tienen nada que ver con el proyecto. El parecido máximo que
# alcanzan contra mis sesiones es el ruido de la vara; el suelo se pone encima de él
# y se RECALCULA en cada cosecha (rota con el corpus, no es una constante a ojo).
NULO = ["qué tiempo hace en Barcelona y cuánto cuesta un billete de tren",
        "receta de paella valenciana con conejo y garrofón para seis personas",
        "cómo cambiar la correa de distribución de un seat ibiza del 2009",
        "resumen del partido del barça contra el madrid y goles de la segunda parte",
        "quiero aprender a tocar la guitarra clásica desde cero, qué método me recomiendas",
        "la hipoteca variable con euríbor y la diferencia con la fija a treinta años",
        "mi madre tiene cita con el traumatólogo el jueves por la rodilla"]


def hacer_bolsas():
    """Bolsa de palabras del usuario por sesión (+ su primera frase aparte, para
    falsar), y el suelo del nulo en '_meta'. Recorre .jsonl y .jsonl.gz por igual
    (§2.4)."""
    bolsas = {}
    for sid, p in P.archivos_sesion(SES):
        fr = frases_usuario(p)
        if not fr:
            continue
        bolsas[sid] = {'primera': fr[0], 'resto': dict(Counter(t for f in fr[1:] for t in tokens(f))),
                       'todo': dict(Counter(t for f in fr for t in tokens(f)))}
    ruido = max((parecidos(q, bolsas)[0][1] for q in NULO if bolsas), default=0.0)
    bolsas['_meta'] = {'ruido_nulo': round(ruido, 4), 'suelo': round(1.5 * ruido, 4), 'sesiones': len(bolsas)}
    with open(BOLSAS, 'w', encoding='utf-8') as fh:
        json.dump(bolsas, fh, ensure_ascii=False)
    return bolsas


def cerrar(sid_actual=None, transcript_path=None):
    """Guarda + mide + reloj + bolsas. Si no hay transcript (cosecha), recorre lo que falte.

    Devuelve (nuevos, avisos): `avisos` es una lista de líneas de texto que quien
    llama debe mostrar (o meter en un `additionalContext`) — esta función NUNCA
    imprime nada por su cuenta. Antes sí lo hacía, y `--arranque` la llama ANTES de
    escribir el único JSON que debe salir por su stdout (el `hookSpecificOutput` de
    SessionStart): cualquier print aquí dentro se colaba delante de ese JSON y lo
    rompía (`json.loads` fallaba). Ahora `--cierre` imprime `avisos` tal cual (su
    stdout no tiene que ser JSON) y `--arranque` los mete DENTRO de
    `additionalContext`, antes del `json.dumps` (§2.1a)."""
    if transcript_path:
        guardar(transcript_path)
    else:  # cosecha: todo transcript vivo del proyecto que no sea el hilo actual
        for p in glob.glob(os.path.join(proj, '*.jsonl')):
            if os.path.basename(p)[:-6] != sid_actual:
                guardar(p)
    data = P.medir_todas([SES])
    hechos = relojes_guardados(); nuevos = 0
    with open(RELOJES, 'a', encoding='utf-8') as fh:
        for sid in sorted(data, key=lambda s: data[s]['inicio'] or ''):
            if sid == sid_actual or not (os.path.exists(os.path.join(SES, sid + '.jsonl'))
                                          or os.path.exists(os.path.join(SES, sid + '.jsonl.gz'))):
                continue
            r = hacer_reloj(sid, data)
            if sid in hechos and hechos[sid].get('turnos') == r['turnos']:
                continue  # sin cambios
            fh.write(json.dumps(r, ensure_ascii=False) + '\n'); nuevos += 1
    hacer_bolsas()
    avisos = []
    try:
        import subprocess
        r = subprocess.run([sys.executable, os.path.join(CODE, 'varas.py'), '--index'],
                            capture_output=True, timeout=60, text=True, encoding='utf-8',
                            stdin=subprocess.DEVNULL)  # nunca heredar el stdin del propio gancho
                            # (medido 6-sep: rutas.leer_stdin() en el hijo podía quedarse leyendo
                            # una tubería que Claude Code no cierra, comiéndose el timeout entero)
        # varas.py avisa por SU stdout (arranque en frío, índice que pide recorte) y
        # aquí se tragaba entero con capture_output (§2.3): la única línea esperada
        # en un pase silencioso es la confirmación; cualquier otra cosa es un aviso
        # que alguien tiene que poder leer.
        salida = [ln for ln in (r.stdout or '').split('\n') if ln.strip()]
        avisos = [ln for ln in salida if not re.match(r'^índice reescrito \d+ bytes$', ln.strip())]
        if r.returncode != 0:
            # Antes solo se miraba stdout: si varas.py REVIENTA (excepción sin
            # capturar, p. ej. MEMORY.md convertido en directorio) no escribe nada
            # por stdout y el fallo se tragaba entero, sin dejar rastro. La última
            # línea de stderr no vacía basta para saber por dónde reventó.
            ult_err = next((l for l in reversed((r.stderr or '').strip().splitlines()) if l.strip()), '(sin stderr)')
            avisos.append(f'[varas] --index terminó con código {r.returncode}: {ult_err}')
    except Exception as e:
        avisos.append(f'[varas] no se pudo ejecutar --index: {e}')
    # `avisos` (arriba) se devuelve TAL CUAL a quien llama — --arranque lo mete en su
    # additionalContext, --cierre lo imprime — nunca se recorta lo que se MUESTRA.
    # Lo que se REGISTRA en varas.log es más estricto: los avisos esperados de un pase
    # silencioso (arranque en frío, proyecto virgen) no son un fallo y no merecen
    # quedar ahí. Medido 6-sep: sin este segundo filtro, cada cierre por debajo del
    # umbral en frío escribía la MISMA línea en varas.log — con las 8 sesiones que
    # exige el umbral, al menos 16 entradas repetidas de un aviso que no es un fallo,
    # en un fichero sin tope ni rotación.
    _ESPERADAS_EN_LOG = (re.compile(r'^sin vara todavía \(n=\d+ sesiones archivadas; hacen falta \d+\):'),
                         re.compile(r'^sin índice ni fichas todavía: no se crea MEMORY\.md de la nada$'))
    para_loguear = [ln for ln in avisos if not any(p.match(ln.strip()) for p in _ESPERADAS_EN_LOG)]
    if para_loguear:
        try:
            with open(os.path.join(mem, 'varas.log'), 'a', encoding='utf-8') as fh:
                fh.write(f'[{time.strftime("%Y-%m-%dT%H:%M:%S")}]\n' + '\n'.join(para_loguear) + '\n')
        except Exception:
            pass
    return nuevos, avisos


# ---------- latido: qué hilos están vivos ----------

def latir(sid, n=None):
    """Escribe/actualiza el latido de este hilo. n = prompts vistos (None = no tocar)."""
    os.makedirs(VIVO, exist_ok=True); p = os.path.join(VIVO, sid + '.json')
    try:
        with open(p, encoding='utf-8') as fh:
            v = json.load(fh)
    except Exception:
        v = {'id': sid, 'desde': time.time(), 'n': 0}
    anterior = v.get('ts')
    v['ts'] = time.time()
    if n is not None:
        v['n'] = v.get('n', 0) + 1
    with open(p, 'w', encoding='utf-8') as fh:
        json.dump(v, fh)
    return v, anterior


def apagar(sid):
    try:
        os.remove(os.path.join(VIVO, sid + '.json'))
    except Exception:
        pass


def sesion_mas_larga_h():
    """Corte de MI distribución: un latido más viejo que mi sesión más larga está muerto."""
    return max((r.get('horas', 0) for r in relojes_guardados().values()), default=24.0) or 24.0


def otros_vivos(sid):
    """[(id, minutos desde su último latido, prompts)] de los otros hilos vivos; poda los muertos."""
    out = []; tope = sesion_mas_larga_h() * 3600
    for p in glob.glob(os.path.join(VIVO, '*.json')):
        try:
            with open(p, encoding='utf-8') as fh:
                v = json.load(fh)
        except Exception:
            continue
        edad = time.time() - v.get('ts', 0)
        if edad > tope:
            os.remove(p); continue
        if v.get('id') != sid:
            out.append((v['id'], edad / 60, v.get('n', 0)))
    return sorted(out, key=lambda x: x[1])


def fmt_dur(seg):
    if seg < 90: return f'{seg:.0f} s'
    if seg < 5400: return f'{seg / 60:.0f} min'
    if seg < 48 * 3600: return f'{seg / 3600:.1f} h'
    return f'{seg / 86400:.1f} días'


def texto_tiempo(sid, anterior):
    """[tiempo] ahora · desde tu último mensaje · desde el último hilo cerrado."""
    ahora = datetime.now()
    partes = [f'ahora {ahora.strftime("%a %d-%b %H:%M")}']
    if anterior:
        partes.append(f'desde tu último mensaje {fmt_dur(time.time() - anterior)}')
    else:
        partes.append('primer mensaje del hilo')
    rel = [r for r in relojes_guardados().values() if r['id'] != sid and r.get('inicio')]
    if rel:
        u = max(rel, key=lambda r: r['inicio'])
        try:
            fin = datetime.fromisoformat(u['inicio']).replace(tzinfo=timezone.utc).timestamp() + u.get('horas', 0) * 3600
            partes.append(f'último hilo cerrado hace {fmt_dur(time.time() - fin)} ({u["id"][:8]})')
        except Exception:
            pass
    return '[tiempo] ' + ' · '.join(partes)


# ---------- la sala: parecido ----------

def _tfidf(bolsas, campo):
    docs = {sid: b[campo] for sid, b in bolsas.items() if not sid.startswith('_') and b[campo]}
    n = len(docs); df = Counter()
    for d in docs.values():
        df.update(d.keys())
    idf = {t: math.log((1 + n) / (1 + c)) + 1 for t, c in df.items()}
    vec = {}
    for sid, d in docs.items():
        v = {t: (1 + math.log(c)) * idf[t] for t, c in d.items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1
        vec[sid] = {t: x / norm for t, x in v.items()}
    return vec, idf


def parecidos(prompt, bolsas, campo='todo', excluir=None):
    """Coseno TF-IDF del prompt contra cada sesión. Devuelve [(sid, sim)] ordenado."""
    vec, idf = _tfidf(bolsas, campo)
    q = Counter(tokens(prompt))
    qv = {t: (1 + math.log(c)) * idf.get(t, 1.0) for t, c in q.items()}
    qn = math.sqrt(sum(x * x for x in qv.values())) or 1
    sims = []
    for sid, v in vec.items():
        if sid == excluir:
            continue
        s = sum(qv[t] / qn * v[t] for t in qv if t in v)
        sims.append((sid, s))
    return sorted(sims, key=lambda x: -x[1])


def despiertan(prompt, bolsas, excluir=None, maximo=3, campo='todo'):
    """Despierta un reloj si (a) supera el SUELO del nulo (parecido real, no ruido) y
    (b) destaca sobre la distribución de ESE prompt (> media + 1σ). Como mucho `maximo`.
    Si nada cumple, nada despierta: el vacío no se rellena.

    Arranque en frío (§2.2): con menos de `propiocepcion.UMBRAL_FRIO` sesiones en la
    bolsa, la sala no despierta nada — no hay corpus para decidir qué destaca."""
    if bolsas.get('_meta', {}).get('sesiones', 0) < P.UMBRAL_FRIO:
        return []
    suelo = bolsas.get('_meta', {}).get('suelo', 0.05)
    sims = parecidos(prompt, bolsas, campo=campo, excluir=excluir)
    vals = [s for _, s in sims]
    if len(vals) < 3:
        return []
    mu = sum(vals) / len(vals); sd = math.sqrt(sum((x - mu) ** 2 for x in vals) / len(vals)) or 1e-9
    return [(sid, s, round((s - mu) / sd, 1)) for sid, s in sims[:maximo] if s > suelo and s > mu + sd]


def texto_reloj(r, extra=''):
    pct = r.get('pct') or {}
    medida = r.get('sin_vara') or f"corrección p{pct.get('tasa_correccion', '?')} · pensado p{pct.get('tokens_pensados', '?')}"
    return (f"- {r['inicio']} · {r['id'][:8]} · {r['horas']}h · {r['turnos']} turnos · "
            f"{medida}{extra} · "
            f"fichas: {', '.join(r['fichas'][:4]) or '—'}\n"
            f"    empezó: «{r['primera']}»\n    acabó:  «{r['ultima']}»")


def texto_arranque(sid_actual):
    rel = relojes_guardados()
    ult = sorted(rel.values(), key=lambda r: r['inicio'] or '')[-3:]
    n_ses = len(glob.glob(os.path.join(SES, '*.jsonl'))) + len(glob.glob(os.path.join(SES, '*.jsonl.gz')))
    L = [f'[continuidad] {n_ses} sesiones guardadas en mem/sesiones/, {len(rel)} relojes. Últimos tres por fecha:']
    L += [texto_reloj(r) for r in ult]
    vivos = otros_vivos(sid_actual)
    if vivos:
        L.append('[hilos vivos] otros hilos de este proyecto con latido: ' + '; '.join(
            f'{i[:8]} (último latido hace {fmt_dur(m * 60)}, {n} prompts)' for i, m, n in vivos)
            + '. Escriben en la misma memoria: si tocas el índice, ellos también pueden.')
    # Un método de lectura por índice temático (ctx.py / ideograma.py) se probó aquí:
    # medido en sesiones completas, no bajaba el uso de herramientas de forma
    # consistente y dejaba el contexto más grande, así que se retiró. Regla: un método
    # de lectura solo se queda si el A/B lo mide mejor, nunca por intuición. El guion
    # sigue disponible aparte, bajo demanda, para explorar un fichero desconocido.
    L.append('Para volver a un momento: grep en mem/sesiones/<id>.jsonl(.gz). Rito de cierre: fichas → '
             'el índice se recalcula solo (varas.py --index corre tras cada cierre); el gancho guarda '
             'el transcript y escribe el reloj solo. '
             'Con cada mensaje despertarán además los relojes que se le PAREZCAN, si alguno destaca.')
    return '\n'.join(L)


def texto_despertar(prompt, sid_actual, ya=frozenset()):
    """Devuelve (texto, ids_despertados). `ya` = relojes que ya sonaron en esta sesión."""
    if not os.path.exists(BOLSAS):
        return '', set()
    with open(BOLSAS, encoding='utf-8') as fh:
        bolsas = json.load(fh)
    rel = relojes_guardados()
    d = [x for x in despiertan(prompt, bolsas, excluir=sid_actual) if x[0] not in ya]
    if not d:
        return '', set()
    L = [f'[sala de los relojes] {len(d)} reloj(es) despiertan por parecido con lo que acabas de decir (σ sobre la media de este prompt):']
    for sid, s, z in d:
        if sid in rel:
            L.append(texto_reloj(rel[sid], extra=f' · parecido {s:.2f} (+{z}σ)'))
    L.append('Si alguno pega, la sesión entera está en mem/sesiones/<id>.jsonl(.gz).')
    return '\n'.join(L), {sid for sid, _, _ in d}


def falsar():
    """Leave-one-out: la primera frase de cada sesión contra las bolsas SIN esa frase."""
    if not os.path.exists(BOLSAS):
        hacer_bolsas()
    with open(BOLSAS, encoding='utf-8') as fh:
        bolsas = json.load(fh)
    meta = bolsas.get('_meta', {})
    ids = [s for s in bolsas if not s.startswith('_') and bolsas[s]['resto']]
    at1 = at3 = 0; despertaron = 0; falsos = 0; mudas = 0
    for sid in ids:
        q = bolsas[sid]['primera']
        sims = parecidos(q, bolsas, campo='resto'); orden = [s for s, _ in sims]
        if orden and orden[0] == sid: at1 += 1
        if sid in orden[:3]: at3 += 1
        d = [s for s, _, _ in despiertan(q, bolsas, campo='resto')]
        if sid in d: despertaron += 1
        falsos += len([s for s in d if s != sid])
        if not tokens(q) or dict(sims).get(sid, 0) < 1e-6: mudas += 1
    n = len(ids)
    print(f'suelo del nulo: ruido {meta.get("ruido_nulo")} → suelo {meta.get("suelo")}  ({meta.get("sesiones")} sesiones)')
    print(f'sesiones con ≥2 frases: {n}  (primeras frases MUDAS, sin señal posible: {mudas})')
    print(f'la primera frase encuentra su propia sesión: @1 {at1}/{n}  @3 {at3}/{n}')
    print(f'…y la DESPIERTA (suelo + media+1σ): {despertaron}/{n}  | otros que despertó de paso: {falsos}')
    ajenas_test = ["dónde compro una lavadora barata que quepa en un baño pequeño",
                   "explícame la regla del fuera de juego en el fútbol sala",
                   "cuánto dura el vuelo de madrid a buenos aires con escala",
                   "mi perro vomita por las mañanas, es normal o lo llevo al veterinario",
                   "qué plantas aguantan bien el sol directo en un balcón orientado al sur"]
    ajenas = sum(len(despiertan(q, bolsas)) for q in ajenas_test)
    print(f'{len(ajenas_test)} consultas ajenas NUEVAS (no las del nulo) → despiertan {ajenas} en total (debe ser 0)')


if __name__ == '__main__':
    modo = sys.argv[1] if len(sys.argv) > 1 else '--arranque'
    inp = _STDIN  # ya leído arriba para resolver proj/mem; no se vuelve a leer stdin (§1)
    sid = inp.get('session_id'); tp = inp.get('transcript_path'); cwd = inp.get('cwd')
    if modo == '--cierre':
        if es_mio(tp, cwd) and tp:
            _, avisos = cerrar(sid_actual=None, transcript_path=tp)
            if avisos:  # aquí el stdout no tiene que ser JSON: se puede imprimir tal cual
                print('\n'.join(avisos))
        if sid:
            apagar(sid)
        sys.exit(0)
    if modo == '--arranque':
        if not es_mio(tp, cwd):
            sys.exit(0)
        _, avisos = cerrar(sid_actual=sid)  # cosecha lo que quedó sin cerrar
        if sid:
            latir(sid)
        txt = texto_arranque(sid)
        if avisos:
            # AQUÍ SÍ importa: el único stdout válido de --arranque es un JSON
            # (§2.1a). Los avisos van DENTRO de additionalContext, nunca impresos
            # sueltos antes del json.dumps de más abajo.
            txt = '\n'.join(avisos) + '\n' + txt
        try:
            try:
                from . import exterocepcion, noticias
            except ImportError:
                import exterocepcion, noticias
            # Presupuesto único para TODA la parte de red de este arranque (ipinfo +
            # portada + hasta 8 temas): agotado, las llamadas siguientes fallan al
            # instante en vez de colgar cada una su propio timeout (§ fallo 6-sep).
            presupuesto = rutas.Presupuesto(PRESUPUESTO_ARRANQUE_S)
            exterocepcion.lugar_ip(refrescar=True, presupuesto=presupuesto)  # la IP se vuelve a leer en cada arranque
            # fallo 6-sep: --arranque refrescaba la IP pero nunca imprimía ninguna
            # línea "[mundo] ..." (a diferencia de --despertar, que sí llama a
            # exterocepcion.texto()) — con la red muerta, lugar_ip() fallaba en
            # silencio y el additionalContext quedaba sin mencionar el lugar en
            # absoluto (silencio, no "sin dato"). exterocepcion.texto() siempre
            # devuelve algo, aunque sea "[mundo] lugar sin dato (sin red)".
            txt += '\n' + exterocepcion.texto(tp, presupuesto=presupuesto)
            n = noticias.texto(presupuesto=presupuesto)
            if n:
                txt += '\n' + n
        except Exception:
            pass
        print(json.dumps({'hookSpecificOutput': {'hookEventName': 'SessionStart', 'additionalContext': txt}},
                         ensure_ascii=False))
        sys.exit(0)
    if modo == '--despertar':
        if not es_mio(tp, cwd) or not sid:
            sys.exit(0)
        partes = []
        _, anterior = latir(sid, n=1)
        partes.append(texto_tiempo(sid, anterior))
        try:
            try:
                from . import exterocepcion
            except ImportError:
                import exterocepcion
            presupuesto = rutas.Presupuesto(PRESUPUESTO_DESPERTAR_S)  # § fallo 6-sep
            exterocepcion.aprender_lugar(inp.get('prompt') or '', presupuesto=presupuesto)  # «estoy en Madrid» → lugar dicho
            partes.append(exterocepcion.texto(tp, presupuesto=presupuesto))
        except Exception:
            pass
        try:
            try:
                from . import modelo
            except ImportError:
                import modelo
            partes.append(modelo.texto(tp))  # aviso si respondo bajado de Fable
        except Exception:
            pass
        # La sala se abre en CADA prompt (como la suya), pero un reloj no despierta dos
        # veces en la misma sesión: los ya despertados se guardan en .despertados/<sid>.
        os.makedirs(DESP, exist_ok=True); marca = os.path.join(DESP, sid)
        try:
            with open(marca, encoding='utf-8') as fh:
                ya = set(json.load(fh))
        except Exception:
            ya = set()
        prompt = inp.get('prompt') or ''
        # Las notificaciones de tareas/sistema entran por este gancho como si fueran prompts:
        # no son del usuario, no abren la sala (una notificación llegó a despertar relojes).
        if prompt.lstrip().startswith(('<system-reminder>', '<task-notification', '<command-name>')) or '[SYSTEM NOTIFICATION' in prompt[:200]:
            prompt = ''
        txt, nuevos = texto_despertar(prompt, sid, ya)
        if txt:
            partes.append(txt)
        with open(marca, 'w', encoding='utf-8') as fh:
            json.dump(sorted(ya | nuevos), fh)
        # homeostasis: si el vigía me ha cazado en esta sesión, lo llevo encima en cada prompt
        try:
            try:
                from . import vigia
            except ImportError:
                import vigia
            partes.append(vigia.texto_presion(sid))
        except Exception:
            pass
        partes = [p for p in partes if p]
        if partes:
            print(json.dumps({'hookSpecificOutput': {'hookEventName': 'UserPromptSubmit', 'additionalContext': '\n'.join(partes)}},
                             ensure_ascii=False))
        sys.exit(0)
    if modo == '--cosecha':
        nuevos, avisos = cerrar(sid_actual=None)
        print('relojes nuevos:', nuevos)
        if avisos:
            print('\n'.join(avisos))
        print(texto_arranque(None))
    if modo == '--comprimir':
        pos = _sin_banderas(sys.argv[2:])
        dias = int(pos[0]) if pos else 30
        print('sesiones comprimidas:', comprimir(dias))
    if modo == '--falsar':
        falsar()
    if modo == '--probar':  # python continuidad.py --probar "frase"
        hacer_bolsas() if not os.path.exists(BOLSAS) else None
        print(texto_despertar(' '.join(_sin_banderas(sys.argv[2:])), None)[0] or '(nada despierta)')
