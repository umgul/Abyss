"""Modelo: avisar cuando el sistema cambia de modelo sin que lo elija el usuario, y al salir de ahí, revisar.

Solo avisa con prueba de un cambio automático en el transcript; un cambio hecho por el usuario se permite:
- **safeguard**: la primera respuesta del modelo de reserva trae un bloque `content[].type == "fallback"` con
  `from`/`to`. La línea `system`/`model_refusal_fallback` (`originalModel` → `fallbackModel`) llega unas líneas
  después con el mismo `requestId`, y solo cuenta cuando no hubo bloque (versiones que no lo escribían).
- **inicio**: tras una marca `SessionStart:startup`/`SessionStart:resume` (la deja cualquier gancho de SessionStart),
  la primera respuesta llega de un modelo por debajo del que llevaba el hilo, sin `/model` entre medias. Rango:
  familia (mythos > fable > opus > sonnet > haiku) y después generación (claude-opus-5 > claude-opus-4-8).
Un `/model` con hora igual o posterior al suceso lo da por decidido por el usuario, elija el modelo que elija. Cuenta
la hora y no la posición porque un `/model` hecho a mitad de turno se escribe al acabar el turno, con su hora. Una
respuesta de un modelo distinto del de reserva cierra la bajada.

No avisa, y es un límite: un cambio sin ningún rastro (sin `/model`, sin fallback, sin marca de sesión; los hay en
2.1.219–2.1.237), porque nada dice si fue a mano; una sesión nueva, que no sabe con qué modelo iba otro hilo; una
reanudación sin gancho SessionStart instalado. Si la app escribiera un `/model` por su cuenta al reanudar, contaría
como elección del usuario. El aviso de inicio llega en el prompt siguiente a la primera respuesta: al enviar el
primero aún no ha respondido nadie. `<synthetic>` (errores de la API, límites) no es un modelo y se ignora.

Claude Code tiene un evento `PostModelSwitch` (visto en transcripts de 2.1.255 a 2.1.260, siempre junto a un
`/model`), pero no hay medida de si salta con el selector, con un fallback o al reanudar: este módulo no lo usa ni
lleva gancho propio. Vive como LIBRERÍA de `continuidad.py --despertar`, que llama a `texto(tp)` en cada prompt.
Ningún gancho puede devolver la sesión a otro modelo: el regreso lo teclea el usuario con `/model`.

- texto(tp): `[modelo]` mientras dura una bajada automática, con el comando para volver y el de quedarse;
  `[modelo · revisión]` UNA vez cuando ya responde otro modelo que el de la bajada, con los turnos respondidos
  durante ella (quedarse con el de reserva no la dispara; `--estado` la enseña sin gastarla).
- actual(tp): el último modelo que respondió.
- recorrer(tp): el estado del hilo tras la última línea (ver `_estado_vacio()`).

Paréntesis (`parentesis.py`): los sucesos cuentan también dentro de un tramo, porque no llevan texto del usuario; el
texto de un turno dicho dentro no se guarda, así que no vuelve en `[modelo · revisión]` (que `continuidad.py
--despertar` mete en `additionalContext` y viaja a la API en el prompt siguiente).

Marcapáginas (`marcapaginas.py`): el estado se guarda en `mem/.marcapaginas/<sid>/modelo.json` y en cada prompt solo
se leen las líneas nuevas. Sin marcapáginas, la lectura entera de siempre.

Carpeta de datos: NUNCA `dirname(__file__)`; se resuelve con `rutas.resolver()` (§1 de ESPECIFICACION.md).
`texto(tp)`/`actual(tp)`/`recorrer(tp)` ya reciben el `transcript_path` de quien los llama (típicamente
`continuidad.py`) y con eso basta para resolver sin tocar stdin. Si nada resuelve: como librería, no revienta a quien
importa el módulo; a mano (`--estado`, CLI suelta) si falla se avisa claro, como hace `rutas.resolver()`.
"""
import sys
try:                       # la consola de Windows y la salida tienen que hablar
    from . import consola  # el mismo idioma: ver abyss/consola.py
except ImportError:
    import consola
consola.preparar()
import os, re, json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rutas  # noqa: E402
import marcapaginas as MP  # noqa: E402

# Con `match`: la línea del comando EMPIEZA por la etiqueta (153 de 153 en los transcripts medidos); un prompt que pega
# un `/model` en medio de su texto no es una elección.
RE_CMD = re.compile(r'\s*<command-name>/model</command-name>.*?<command-args>\s*([\w.\-]+)', re.S)
FAMILIAS = ('haiku', 'sonnet', 'opus', 'fable', 'mythos')  # de menos a más
MAX_REQUESTS = 16  # requestId de los últimos bloques fallback: su línea system llega pocas líneas después
HUELLA = MP.huella('modelo.py', 'parentesis.py', 'marcapaginas.py')

_CACHE = {}  # 'proj'/'mem' una vez resueltos en este proceso


def _mem(tp=None, stdin_json=None):
    """Como en exterocepcion.py: cacheada por proceso, con `tp` como pista si la hay,
    fail-closed (None) si no hay forma de resolver — no revienta a quien importa este
    módulo.

    Fija `ABYSS_PROYECTO` en el entorno (si no lo estaba ya) igual que
    `propiocepcion.py`/`vigia.py`/`varas.py` tras resolver: así, si `recorrer()` importa
    `parentesis` DESPUÉS de esta llamada, el `rutas.resolver()` propio de
    `parentesis.py` (que lee `sys.argv` de este mismo proceso) encuentra la variable de
    entorno en vez de adivinar."""
    if _CACHE.get('mem'):
        return _CACHE['mem']
    if stdin_json is None:
        stdin_json = {'transcript_path': tp} if tp else {}
    try:
        proj, mem = rutas.resolver(stdin_json=stdin_json)
    except SystemExit:
        return None
    _CACHE['proj'], _CACHE['mem'] = proj, mem
    os.environ.setdefault('ABYSS_PROYECTO', proj)
    return mem


def _ruta(nombre, tp=None):
    m = _mem(tp)
    return os.path.join(m, nombre) if m else None


def _iter(tp):
    with open(tp, encoding='utf-8', errors='ignore') as fh:
        for line in fh:
            try:
                yield json.loads(line)
            except Exception:
                continue


def _sid_de_ruta(tp):
    """id de sesión a partir del nombre del transcript — mismo criterio que
    `vigia._sid_de_ruta()`/`propiocepcion._sid_de()`,
    para poder preguntarle a `parentesis.py` por los tramos de ESTA sesión.
    `None` si `tp` no trae nada de donde sacar un id."""
    if not tp:
        return None
    base = os.path.basename(tp)
    if base.endswith('.jsonl.gz'):
        return base[:-9]
    if base.endswith('.jsonl'):
        return base[:-6]
    return base or None


def _tramos_de(sid, tp):
    """(módulo `parentesis`, tramos de esta sesión como listas), o (None, None) si no se pueden consultar (sin sid,
    sin proyecto, o el propio módulo no se deja importar) — fail-open: entonces no se oculta ningún texto, en vez de
    reventar la librería de `continuidad.py --despertar` que lo llama en cada prompt. `_mem(tp)` se llama ANTES de
    importar `parentesis` para que su `rutas.resolver()` (que lee el `sys.argv` de ESTE proceso) encuentre
    `ABYSS_PROYECTO` ya fijado, en vez de adivinar.

    Los tramos se leen FUERA de ese fail-open: si `parentesis.json` existe pero no se deja leer como tramos,
    `recorrer()` falla y `--despertar` calla el aviso de ese prompt, antes que reinyectar en `[modelo · revisión]`
    algo dicho dentro de un paréntesis."""
    if not sid or _mem(tp) is None:
        return None, None
    try:
        try:
            from . import parentesis as PZ
        except ImportError:
            import parentesis as PZ
    except Exception:
        return None, None
    return PZ, [list(t) for t in PZ.tramos(sid)]


def _epoch(ts):
    try:
        return datetime.fromisoformat(ts.replace('Z', '+00:00')).timestamp()
    except Exception:
        return None


def _no_antes(ts, suceso):
    """¿`ts` es igual o posterior a `suceso`? Sin hora legible en alguno de los dos manda la posición en el fichero:
    lo leído después cuenta como posterior."""
    a, b = _epoch(ts), _epoch(suceso)
    return a is None or b is None or a >= b


def _rango(modelo):
    """(familia, generación) para comparar modelos: mythos > fable > opus > sonnet > haiku y, dentro de la familia,
    la generación (`claude-opus-5` > `claude-opus-4-8`, `claude-fable-5-1` > `claude-fable-5`); una fecha de 8 cifras
    no es generación. None si no es de ninguna familia conocida: entonces no se compara."""
    s = str(modelo or '').lower().split('[')[0]
    familia = next((i for i, f in enumerate(FAMILIAS) if f in s), None)
    if familia is None:
        return None
    return familia, tuple(int(x) for x in re.findall(r'\d+', s) if len(x) < 8)


def _por_debajo(modelo, referencia):
    a, b = _rango(modelo), _rango(referencia)
    return a is not None and b is not None and a < b


def _casa(elegido, modelo):
    """`elegido` (argumento de `/model`: alias como 'opus' o id completo) y `modelo` (el id que respondió) son el
    mismo si uno contiene al otro."""
    return bool(elegido) and bool(modelo) and (elegido.lower() in modelo.lower() or modelo.lower() in elegido.lower())


def _estado_vacio():
    """Lo que `recorrer()` sabe del hilo tras la última línea leída (se guarda tal cual en el marcapáginas):
    - ultimo: el último modelo que respondió.
    - bajada: {'de', 'a', 'motivo': 'safeguard'|'inicio', 'ts'} mientras dura una bajada automática; si no, None.
    - inicio: {'de', 'ts'} desde una marca de arranque o reanudación hasta la primera respuesta; si no, None.
    - fij / fij_tras_ultima: el argumento del último `/model` y si llegó después de la última respuesta.
    - requests: `requestId` de los últimos bloques fallback, para no contar dos veces su línea system.
    - turnos: los turnos ya cerrados respondidos durante una bajada, dichos fuera de paréntesis.
    - cur: el turno en curso; entra en `turnos` cuando llega el prompt siguiente, si le toca. De cada turno se guarda
      el último modelo que respondió (`modelo`), el que respondió durante la bajada (`modelo_bajada`) y el primer
      texto de cada modelo (`textos`): un turno puede empezar en la bajada y acabar en el modelo de origen."""
    return {'ultimo': None, 'bajada': None, 'inicio': None, 'fij': None, 'fij_tras_ultima': False,
            'requests': [], 'turnos': [], 'cur': None}


def _estado_valido(e):
    return (isinstance(e, dict) and set(e) == set(_estado_vacio()) and isinstance(e['requests'], list)
            and isinstance(e['turnos'], list) and (e['cur'] is None or isinstance(e['cur'], dict)))


def _plano(texto, n):
    return re.sub(r'\s+', ' ', texto.strip())[:n]


def _caer(e, de, a, motivo, ts):
    e['bajada'] = {'de': de, 'a': a, 'motivo': motivo, 'ts': ts}
    cur = e['cur']
    if cur is not None and cur['modelo'] == a:
        cur['bajada'] = True; cur['modelo_bajada'] = a


def _paso(e, d, oculto):
    """Aplica una línea del transcript (ya parseada) al estado `e`. `oculto`: la línea cae dentro de un tramo de
    paréntesis; su texto no se guarda, sus sucesos sí cuentan."""
    t = d.get('type')
    m = d.get('message') if isinstance(d.get('message'), dict) else {}
    ts = d.get('timestamp') if isinstance(d.get('timestamp'), str) else None
    if t == 'user':
        c = m.get('content')
        if not isinstance(c, str):
            return
        mm = RE_CMD.match(c)
        if mm:
            e['fij'] = mm.group(1); e['fij_tras_ultima'] = True
            for clave in ('bajada', 'inicio'):
                if e[clave] is not None and _no_antes(ts, e[clave]['ts']):
                    e[clave] = None
            return
        if d.get('isMeta') or c.lstrip().startswith('This session is being continued') or c.lstrip().startswith('<command-name>'):
            return
        cur = e['cur']
        if cur is not None and cur['bajada'] and not cur['oculto']:
            e['turnos'].append(cur)
        e['cur'] = {'prompt': '' if oculto else _plano(c, 70), 'ts': (ts or '')[11:16], 'iso': ts or '',
                    'modelo': None, 'modelo_bajada': None, 'textos': {}, 'bajada': False, 'oculto': oculto}
    elif t == 'assistant':
        mo = m.get('model')
        if not isinstance(mo, str) or not mo or mo.startswith('<'):
            return
        contenido = m.get('content') if isinstance(m.get('content'), list) else []
        cur = e['cur']
        if cur is not None:
            cur['modelo'] = mo
            if mo not in cur['textos'] and not oculto:
                for b in contenido:
                    if isinstance(b, dict) and b.get('type') == 'text' and isinstance(b.get('text'), str) and b['text'].strip():
                        cur['textos'][mo] = _plano(b['text'], 90); break
        if e['bajada'] is not None and mo != e['bajada']['a']:
            e['bajada'] = None
        fallback = next((b for b in contenido if isinstance(b, dict) and b.get('type') == 'fallback'), None)
        de = fallback.get('from') if fallback is not None else None
        de = de.get('model') if isinstance(de, dict) else None
        if isinstance(de, str) and de:
            rid = d.get('requestId')
            if isinstance(rid, str) and rid:
                e['requests'] = (e['requests'] + [rid])[-MAX_REQUESTS:]
            _caer(e, de, mo, 'safeguard', ts)
        inicio = e['inicio']
        if inicio is not None:
            e['inicio'] = None
            if e['bajada'] is None and _por_debajo(mo, inicio['de']):
                _caer(e, inicio['de'], mo, 'inicio', inicio['ts'])
        if cur is not None and e['bajada'] is not None and mo == e['bajada']['a']:
            cur['bajada'] = True; cur['modelo_bajada'] = mo
        e['ultimo'] = mo; e['fij_tras_ultima'] = False
    elif t == 'system':
        if d.get('subtype') != 'model_refusal_fallback' or d.get('requestId') in e['requests']:
            return
        de, a = d.get('originalModel'), d.get('fallbackModel')
        if isinstance(de, str) and de and isinstance(a, str) and a:
            _caer(e, de, a, 'safeguard', ts)
    elif t == 'attachment':
        at = d.get('attachment')
        if not isinstance(at, dict) or at.get('hookEvent') != 'SessionStart':
            return
        if str(at.get('hookName') or '').rsplit(':', 1)[-1] not in ('startup', 'resume') or e['inicio'] is not None:
            return
        de = e['bajada']['de'] if e['bajada'] is not None else e['ultimo']
        if de:
            e['inicio'] = {'de': de, 'ts': ts}


def _aplicar(e, d, PZ, tramos):
    if isinstance(d, dict):
        _paso(e, d, PZ is not None and PZ.en_tramos(tramos, d.get('timestamp')))


def _leer_entero(tp, PZ, tramos):
    e = _estado_vacio()
    for d in _iter(tp):
        _aplicar(e, d, PZ, tramos)
    return e


def recorrer(tp):
    """El estado del hilo (`_estado_vacio()`) tras la última línea completa del transcript, siguiendo desde el
    marcapáginas de la sesión; sin marcapáginas, leyendo entero."""
    if not tp or not os.path.isfile(tp):
        return _estado_vacio()
    sid = _sid_de_ruta(tp)
    PZ, tramos = _tramos_de(sid, tp)
    l = MP.Lectura.abrir(_CACHE.get('mem'), _CACHE.get('proj'), tp, sid, 'modelo', HUELLA, tramos or [])
    if l is None:
        return _leer_entero(tp, PZ, tramos)
    e = None
    try:
        guardado = l.estado if l.estado is not None else (None if l.offset else _estado_vacio())
        if not _estado_valido(guardado):
            # la firma casa pero el estado no se deja usar: se quita para que la próxima lectura empiece de cero
            MP.apuntar_fallo(l.mem, 'modelo', sid, ValueError('estado del marcapáginas ilegible'))
            try:
                os.remove(os.path.join(l.carpeta, 'modelo.json'))
            except OSError:
                pass
        else:
            for linea in l.lineas_nuevas():
                try:
                    d = json.loads(linea)
                except Exception:
                    continue
                _aplicar(guardado, d, PZ, tramos)
            l.confirmar(guardado)
            e = guardado
    except Exception as fallo:  # un fallo de lectura o de disco no decide nada: se apunta y se lee entero
        MP.apuntar_fallo(l.mem, 'modelo', sid, fallo)
        e = None
    finally:
        l.soltar()
    return e if e is not None else _leer_entero(tp, PZ, tramos)


def actual(tp):
    return recorrer(tp)['ultimo']


def _revisado_hasta(marca):
    """Hora ISO del último turno ya listado en `[modelo · revisión]`; '' sin marca o si la marca es un número (un
    recuento de turnos, que no dice cuáles)."""
    try:
        with open(marca, encoding='utf-8') as fh:
            hasta = fh.read().strip()
    except Exception:
        return ''
    return '' if hasta.isdigit() else hasta


def _posterior(iso, hasta):
    if not hasta:
        return True
    a, b = _epoch(iso), _epoch(hasta)
    return (iso > hasta) if a is None or b is None else a > b


def texto(tp, marcar=True):
    """El aviso de este prompt. `marcar=False` (lo usa `--estado`) enseña la revisión pendiente sin darla por hecha:
    la única vez que sale tiene que ser la que `continuidad.py --despertar` inyecta."""
    e = recorrer(tp)
    b = e['bajada']
    if b is not None:
        if b['motivo'] == 'safeguard':
            causa = f"un safeguard pasó la sesión de {b['de']} a {b['a']}"
            extra = ' Si el mensaje que lo disparó sigue en el hilo, edítalo antes de reintentar o volverá a bajar.'
        else:
            causa = f"la sesión arrancó con {b['a']} y el hilo venía de {b['de']}"
            extra = ''
        return (f"[modelo] downgrade automático: estás respondiendo como {b['a']} porque {causa}. "
                f"No puedo volver solo: teclea `/model {b['de']}` para regresar.{extra} "
                f"Si prefieres seguir con {b['a']}, teclea `/model {b['a']}` y dejo de avisar.")
    # Sin hora no se puede recordar qué turnos se listaron: esos no entran (en un transcript real no pasa).
    lista = [t for t in e['turnos'] if t['iso']]
    cur = e['cur']
    if cur is not None and cur['bajada'] and not cur['oculto'] and cur['iso']:
        lista.append(cur)
    ahora = e['fij'] if e['fij_tras_ultima'] else e['ultimo']
    if not lista or not ahora or _casa(ahora, lista[-1]['modelo_bajada']):
        return ''
    rev = _ruta('.modelo_revisado', tp)
    marca = os.path.join(rev, _sid_de_ruta(tp)) if rev else None
    hasta = _revisado_hasta(marca) if marca else ''
    nuevos = [t for t in lista if _posterior(t['iso'], hasta)]
    if not nuevos:
        return ''
    if marca and marcar:
        os.makedirs(rev, exist_ok=True)
        with open(marca, 'w', encoding='utf-8') as fh:
            fh.write(nuevos[-1]['iso'])
    modelos = ', '.join(sorted({t['modelo_bajada'] for t in nuevos}))
    L = [f'[modelo · revisión] Terminó el downgrade automático: ahora responde {ahora}. Durante la bajada respondió '
         f'{modelos} en {len(nuevos)} turno(s); repásalos antes de seguir:']
    for t in nuevos[:8]:
        L.append(f"  - {t['ts']} {t['modelo_bajada']} · usuario: «{t['prompt']}» → «{t['textos'].get(t['modelo_bajada'], '')}»")
    if len(nuevos) > 8:
        L.append(f'  … y {len(nuevos) - 8} más (grep en el transcript por el modelo)')
    return '\n'.join(L)


if __name__ == '__main__':
    a = sys.argv[1:]
    # uso manual (--estado o CLI suelta): a mano conviene el error claro si no hay proyecto.
    # `rutas.es_transcript` exige fichero real + `.jsonl`: ni la propia bandera `--proyecto`
    # ni un directorio cuelan como transcript_path (si colara, resolvería `proj` como el
    # cwd, pisando tanto `--proyecto <valor>` como `ABYSS_PROYECTO`). Se valida igual el
    # argumento de `--estado`.
    es_estado = bool(a) and a[0] == '--estado'
    candidato = a[1] if es_estado and len(a) > 1 else (a[0] if a and not es_estado else None)
    tp_arg = candidato if rutas.es_transcript(candidato) else None
    sj = {'transcript_path': tp_arg} if tp_arg else None
    _CACHE['proj'], _CACHE['mem'] = rutas.resolver(argv=a, stdin_json=sj)
    if es_estado:
        e = recorrer(tp_arg)
        b = e['bajada']
        print('actual:', e['ultimo'] or '—', '· downgrade automático:',
              f"{b['de']} → {b['a']} ({b['motivo']})" if b else 'ninguno')
        print(texto(tp_arg, marcar=False) or '(sin aviso)')
        sys.exit(0)
    print(texto(tp_arg))
