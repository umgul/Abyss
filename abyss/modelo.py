"""Modelo: detectar el downgrade Fable→Opus, avisar para volver, y al volver REVISAR.

LÍMITE HONESTO (docs de Anthropic): no hay forma de que un gancho devuelva la sesión a
Fable por sí solo, y ningún gancho observa un cambio de modelo desde dentro de la
sesión: los eventos reales de Claude Code son PreToolUse, PostToolUse, Stop,
SubagentStop, SessionStart, SessionEnd, UserPromptSubmit, PreCompact y Notification —
no existen `PostModelSwitch` ni `PreModelSwitch`. El único retorno al modelo preferido
lo teclea el usuario con `/model`; este módulo vive como LIBRERÍA de
`continuidad.py --despertar`, que llama a `texto(tp)` en cada prompt (ahí se detecta el
downgrade, no en un gancho propio). Regla: NO pausar — el plan de la conversación se
suele trazar en mensajes anteriores con el modelo preferido, así que volver a él permite
revisar lo dicho mientras tanto con el otro modelo.

- preferido(): el último modelo que el usuario fijó con `/model` → cache.
- actual(tp): el último modelo que realmente respondió (campo `model` del transcript).
- texto(tp): aviso `[modelo]` con el comando para volver si responde fuera de
  Fable/Mythos; `[modelo · revisión]` UNA vez si acaba de volver y hay turnos
  respondidos por otro modelo aún no revisados, para que los repase.

`recorrer()` respeta el tramo marcado por `parentesis.py` — igual que
`continuidad.frases_usuario()`, `vigia.leer_turno()` y `propiocepcion.medir()` — para no
reinyectar en `[modelo · revisión]` (que `continuidad.py --despertar` mete en
`additionalContext` y por tanto vuelve a viajar a la API en el prompt siguiente) texto
dicho dentro de un paréntesis.

Carpeta de datos: NUNCA `dirname(__file__)`; se resuelve con `rutas.resolver()` (§1 de
ESPECIFICACION.md). `texto(tp)`/`actual(tp)`/`recorrer(tp)` ya reciben el `transcript_path`
de quien los llama (típicamente `continuidad.py`) y con eso basta para resolver sin tocar
stdin. Si nada resuelve: como librería, no revienta a quien importa el módulo; a mano
(`--estado`, CLI suelta) si falla se avisa claro, como hace `rutas.resolver()`.
"""
import sys
try:                       # la consola de Windows y la salida tienen que hablar
    from . import consola  # el mismo idioma: ver abyss/consola.py
except ImportError:
    import consola
consola.preparar()
import os, re, json, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rutas  # noqa: E402

RE_CMD = re.compile(r'<command-name>/model</command-name>.*?<command-args>\s*([\w.\-]+)', re.S)
FAMILIA_OK = ('fable', 'mythos')

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


def preferido(tp=None):
    ruta = _ruta('modelo_preferido.json', tp)
    try:
        with open(ruta, encoding='utf-8') as fh:
            return json.load(fh).get('modelo')
    except Exception:
        return 'claude-fable-5-1'


def fijar_preferido(m, tp=None):
    ruta = _ruta('modelo_preferido.json', tp)
    if not ruta:
        return  # sin proyecto resoluble no se fija nada; se reintenta la próxima llamada
    with open(ruta, 'w', encoding='utf-8') as fh:
        json.dump({'modelo': m, 'ts': time.time()}, fh, ensure_ascii=False)


def _iter(tp):
    if not tp or not os.path.exists(tp):
        return
    with open(tp, encoding='utf-8', errors='ignore') as fh:
        for line in fh:
            try:
                yield json.loads(line)
            except Exception:
                continue


def es_preferido(modelo):
    return bool(modelo) and any(f in modelo for f in FAMILIA_OK)


def _sid_de_ruta(tp):
    """id de sesión a partir del nombre del transcript — mismo criterio que
    `continuidad._sid_de_ruta()`/`vigia._sid_de_ruta()`/`propiocepcion.medir()`,
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


def _parentesis_de(sid, tp):
    """`parentesis.en_parentesis` ya importado, o `None` si no se puede resolver (sin
    sid, sin proyecto, o el propio módulo falla) — fail-open: sin poder consultar el
    tramo, `recorrer()` simplemente no filtra nada, en vez de reventar la librería de
    `continuidad.py --despertar` que lo llama en cada prompt. `_mem(tp)` se llama ANTES
    de importar `parentesis` para que su `rutas.resolver()` (que lee el `sys.argv` de
    ESTE proceso) encuentre `ABYSS_PROYECTO` ya fijado, en vez de adivinar."""
    if not sid or _mem(tp) is None:
        return None
    try:
        try:
            from . import parentesis as PZ
        except ImportError:
            import parentesis as PZ
        return PZ.en_parentesis
    except Exception:
        return None


def recorrer(tp):
    """Lista de turnos: {'prompt', 'ts', 'modelo', 'resp'} por cada mensaje real del
    usuario, con el modelo y el primer texto de la respuesta. También el último
    /model y si fue posterior a la última respuesta.

    Respeta el tramo marcado por `parentesis.py` (`parentesis.en_parentesis()`):
    cualquier línea cuya `timestamp` cae dentro de un tramo abierto de esta sesión se
    salta ENTERA — ni como turno de usuario, ni como respuesta, ni como modelo. Sin
    este filtro, `texto()` podría reinyectar en `[modelo · revisión]` (que vuelve a
    viajar a la API en el siguiente prompt) texto dicho dentro de un paréntesis, justo
    lo que el tramo promete impedir."""
    sid = _sid_de_ruta(tp)
    en_parentesis = _parentesis_de(sid, tp)
    turnos = []; cur = None; fij = None; tras_ultima = False
    for d in _iter(tp):
        if en_parentesis is not None and en_parentesis(sid, d.get('timestamp')):
            continue
        t = d.get('type'); m = d.get('message') or {}
        if t == 'user':
            c = m.get('content')
            if not isinstance(c, str):
                continue
            mm = RE_CMD.search(c)
            if mm:
                fij = mm.group(1); tras_ultima = True; continue
            if d.get('isMeta') or c.lstrip().startswith('This session is being continued') or c.lstrip().startswith('<command-name>'):
                continue
            cur = {'prompt': re.sub(r'\s+', ' ', c.strip())[:70], 'ts': (d.get('timestamp') or '')[11:16], 'modelo': None, 'resp': ''}
            turnos.append(cur)
        elif t == 'assistant':
            mo = m.get('model')
            if mo:
                tras_ultima = False
                if cur is not None:
                    cur['modelo'] = mo
                    if not cur['resp']:
                        for b in (m.get('content') or []):
                            if isinstance(b, dict) and b.get('type') == 'text' and b.get('text', '').strip():
                                cur['resp'] = re.sub(r'\s+', ' ', b['text'].strip())[:90]; break
    return turnos, fij, tras_ultima


def actual(tp):
    turnos, _, _ = recorrer(tp)
    for t in reversed(turnos):
        if t['modelo']:
            return t['modelo']
    return None


def texto(tp):
    turnos, fij, tras_ultima = recorrer(tp)
    # Solo un `/model` de la familia preferida fija el preferido: un `/model opus-5` no
    # debe dejar "respondes como opus-5, no como opus-5".
    if fij and es_preferido(fij):
        fijar_preferido(fij, tp)
    a = next((t['modelo'] for t in reversed(turnos) if t['modelo']), None)
    pref = preferido(tp)
    # (b) si ya volvió (o ya responde como preferido): ¿hay turnos ajenos sin revisar?
    if (tras_ultima and es_preferido(fij)) or es_preferido(a):
        ajenos = [t for t in turnos if t['modelo'] and not es_preferido(t['modelo'])]
        if ajenos:
            rev = _ruta('.modelo_revisado', tp)
            marca = None
            if rev:
                os.makedirs(rev, exist_ok=True)
                marca = os.path.join(rev, os.path.basename(tp)[:-6]) if tp else None
            ya = 0
            try:
                with open(marca, encoding='utf-8') as fh:
                    ya = int(fh.read().strip() or 0)
            except Exception:
                pass
            nuevos = ajenos[ya:]
            if nuevos:
                if marca:
                    with open(marca, 'w', encoding='utf-8') as fh:
                        fh.write(str(len(ajenos)))
                L = [f'[modelo · revisión] Has vuelto a {pref}. Entre medias respondió otro modelo en {len(nuevos)} turno(s); '
                     'repásalos antes de seguir (volver al preferido es la ocasión de revisar lo dicho por el otro):']
                for t in nuevos[:8]:
                    L.append(f"  - {t['ts']} {t['modelo']} · usuario: «{t['prompt']}» → «{t['resp']}»")
                if len(nuevos) > 8:
                    L.append(f'  … y {len(nuevos) - 8} más (grep en el transcript por el modelo)')
                return '\n'.join(L)
        return ''
    # (a) sigue respondiendo fuera de la familia preferida
    if not a:
        return ''
    return (f'[modelo] estás respondiendo como {a}, no como {pref} (downgrade por un safeguard o por el sistema). '
            f'No puedo volver solo: teclea `/model {pref}` para regresar. Si el mensaje que lo disparó sigue en el hilo, '
            'edítalo antes de reintentar o volverá a bajar.')


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
        print('preferido:', preferido(tp_arg), '· actual:', actual(tp_arg)); print(texto(tp_arg) or '(sin aviso)')
        sys.exit(0)
    print(texto(tp_arg))
