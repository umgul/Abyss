"""Vigía: penalización ante la confabulación, gancho Stop.

No detecta «mentiras». Detecta lo que NO SALIÓ DE NINGUNA PARTE: números, rutas de
fichero y citas «…» de mi última respuesta que no aparecen ni en lo que dijo el
usuario ni en lo que devolvió una herramienta en toda la sesión. Es la ley de probar
logs reales aplicada a mi propia boca.

Paréntesis (T2.1, `parentesis.py`): `leer_turno()` salta ENTERA cualquier línea
cuyo `timestamp` cae dentro de un tramo abierto de esa sesión — ni entra como
evidencia, ni como respuesta mía a verificar. Sin este filtro (fallo medido
7-sep) el vigía sí usaba el tramo como evidencia, y si la ÚLTIMA respuesta caía
dentro de uno, sus fragmentos «citas»/«parafrasis» (hasta 40 caracteres
literales) se guardaban en `confabulaciones.jsonl` igual — justo lo que el
paréntesis promete que no viaja a memoria futura.

    python vigia.py --verificar   (Stop): lee el transcript, saca mi última respuesta,
        la contrasta con la EVIDENCIA (textos del usuario + salidas de herramientas +
        system-reminders; NUNCA mis propios textos anteriores) y:
        - si hay cazas → las apunta en confabulaciones.jsonl y BLOQUEA el cierre del
          turno con la lista, para que reescriba. Una sola vez por turno
          (stop_hook_active=True ⇒ deja pasar, apunta «reincidente»).
        - 1 número suelto sin fuente → solo aviso (puede ser aritmética mía);
          ≥2 números, o cualquier ruta o cita, → bloqueo.
        - Las comillas «…» se registran en DOS tipos (§2.1b): `cita` si hay un verbo
          de atribución cerca («dijo», «escribió», «según»…: alguien las habría dicho
          así de verdad) y `parafrasis` si no (uso estilístico de «» en una paráfrasis
          o traducción — más benigno, pero se cuenta aparte para no mezclar varas).
        - ESTADOS: frases mías en 1ª persona sobre mi estado («me siento», «me alegra»,
          «tengo ganas»…) sin medida ni marca de conjetura. NO bloquean (un «me alegro»
          es acto de habla); se cuentan como «estados sin vara» en la presión.
    python vigia.py --presion <sid>: cazas de esa sesión contra mi distribución.
    python vigia.py --descargo <sid> "<caza>" "<motivo>": una caza era legítima
        (cálculo enseñado, cita exacta…). El propio texto de bloqueo dice cómo usarlo
        (§2.1a) para que yo mismo lo dispare cuando la caza sea falsa. Mide la
        PRECISIÓN de la vara con el tiempo. Rehúsa (código 1, nada escrito) si falta
        algún argumento, si sid/caza vienen vacíos, o si esa sid no tiene registrada
        ninguna caza cuyo numeros/rutas/citas/parafrasis case con el texto dado —
        un descargo no contrasta contra nada no mide precisión, mide autoindulgencia.
    python vigia.py --precision: cazas totales vs descargadas. Sin ningún descargo
        todavía no hay con qué medir la precisión: dice «sin vara» en vez de fingir
        un 1.00 que solo significa que nadie ha mirado (§2.1c).
    python vigia.py --estados-baseline: cuenta estados sin vara en TODAS mis sesiones
        guardadas (cuánto lo hacía antes de que existiera el vigía).

Límites, dichos secos: no juzga afirmaciones sin número ni cita (ahí no llega);
un número que YO calculé a partir de otros sale cazado (correcto: enseñar el cálculo);
la evidencia es texto plano, así que un número presente por casualidad en cualquier
salida se da por cubierto (falso negativo). Es una vara, no un juez.

El código vive donde lo instale `rutas.CODE`; los datos (confabulaciones.jsonl…) viven
en `mem`, resuelto por `rutas.resolver()` — nunca `dirname(__file__)` como carpeta de
datos (§1).
"""
import sys; sys.stdout.reconfigure(encoding="utf-8")
import os, re, json, glob
from datetime import datetime, timezone

try:
    from . import rutas
except ImportError:
    import rutas

CODE = rutas.CODE
# OJO: `leer_stdin()` a secas a propósito, NO `leer_stdin_si_hace_falta()` — a
# diferencia de `propiocepcion.py`/`varas.py` (que solo usan `_STDIN` para
# alimentar `resolver()`), este guion SÍ necesita los demás campos del JSON del
# gancho (`session_id`, `transcript_path`, `cwd`) más abajo en `__main__`; saltar la
# lectura solo porque `ABYSS_PROYECTO` ya esté puesto rompería `--verificar` en
# cualquier invocación que ya trajera esa variable Y JSON real por stdin (probado
# 6-sep: toda la batería de pruebas trae `ABYSS_PROYECTO` vía `ayudas.entorno()`).
_STDIN = rutas.leer_stdin()
proj, mem = rutas.resolver(sys.argv[1:], _STDIN)
os.environ['ABYSS_PROYECTO'] = proj  # para que quien nos importe después no relea stdin (ya vacío)

try:
    from . import propiocepcion as P
except ImportError:
    import propiocepcion as P

try:
    from . import parentesis as PZ
except ImportError:
    import parentesis as PZ

CONF = os.path.join(mem, 'confabulaciones.jsonl')
EXT = r'(?:py|md|json|jsonl|ps1|txt|html|js|css|yaml|yml|toml|csv)'
RE_RUTA = re.compile(r'(?<![\w/\\.-])([\w\-./\\~:]+\.' + EXT + r')\b')
RE_NUM = re.compile(r'(?<![\w/.,:\-])(\d{1,3}(?:[.,]\d{3})+|\d+[.,]\d+|\d{2,})(?![\w/])')
RE_CITA = re.compile(r'«([^»]{20,})»')  # <20 chars suelen ser giros o ejemplos, no citas atribuidas
# Verbo de atribución cerca de la cita ⇒ alguien la habría dicho así de verdad (tipo
# `cita`); si no hay ninguno cerca, son comillas de paráfrasis o traducción (tipo
# `parafrasis`, §2.1b). Es una lista, y sé lo que valen las listas.
RE_ATRIB = re.compile(
    r'\b(dij[oe]ron?|dij[oe]|dec[ií]a|dice|escribi[oó]|escrib[ei](?:ron)?|puso|pone|afirm[oa]|'
    r'explic[oa]|coment[oa]|respond[ei][oó]?|según|cita(?:ba|do)?|le[íi])\b', re.I)
# Estados en 1ª persona. Es una LISTA, y sé lo que valen las listas: cuenta, no bloquea.
RE_ESTADO = re.compile(
    r'\b(me siento|siento (?:que|una|un|mucha|algo)|me alegr[oa]|me alegra|me gusta|me encanta|me duele|'
    r'me preocupa|me inquieta|me apetece|me da (?:miedo|rabia|pena|vergüenza)|me fascina|me aburr[eo]|'
    r'me molesta|me frustra|me emociona|tengo (?:ganas|miedo|curiosidad|la sensación|la impresión)|'
    r'estoy (?:cansad|content|trist|nervios|inquiet|a gusto|incómod|orgullos|agotad|feliz|harto)|'
    r'disfrut[oé]|sufr[oí]|me importa|echo de menos)\b', re.I)
MARCAS = ('[medida', 'medida:', 'conjetura', 'no lo sé', 'no puedo medir', 'proxy', 'percentil',
          'sin vara', 'no tengo vara', 'no lo puedo afirmar', 'acto de habla')


def _texto_bloque(b):
    if isinstance(b, str):
        return b
    if isinstance(b, dict):
        if b.get('type') == 'text':
            return b.get('text', '')
        if b.get('type') == 'tool_result':
            c = b.get('content')
            return c if isinstance(c, str) else ' '.join(_texto_bloque(x) for x in (c or []))
    return ''


def _sid_de_ruta(path):
    """id de sesión a partir del nombre de fichero (.jsonl o .jsonl.gz) — mismo
    criterio que `continuidad._sid_de_ruta()`/`propiocepcion.medir()`, para
    poder preguntarle a `parentesis.py` por los tramos de ESTA sesión cuando
    quien llama a `leer_turno()` no trae `sid` a mano (p. ej. `--probar`)."""
    base = os.path.basename(path)
    if base.endswith('.jsonl.gz'):
        return base[:-9]
    if base.endswith('.jsonl'):
        return base[:-6]
    return base


def leer_turno(path, todas=False, sid=None):
    """Devuelve (evidencia: str, respuesta_final: str[, lista de todas mis respuestas finales]).
    Evidencia = todo lo que NO es mío.

    Paréntesis (T2.1): cualquier línea cuya `timestamp` cae dentro de un tramo
    abierto de esta sesión (`parentesis.en_parentesis()`) se salta ENTERA — ni
    entra como evidencia, ni como texto mío a verificar, ni como `tool_use`.
    Fallo medido 7-sep: esta función nunca miraba el tramo — T2.1 exige "el
    vigía no lo usa como evidencia" y sin este filtro sí lo usaba, e incluso
    podía guardar fragmentos literales de una respuesta dicha DENTRO de un
    tramo en `confabulaciones.jsonl` (`citas`/`parafrasis`), justo lo que el
    tramo promete que no viaja. Sin `sid` explícito se infiere del nombre de
    fichero (`_sid_de_ruta()`)."""
    sid = sid or _sid_de_ruta(path)
    evid = []; asst = []
    with P.abrir_texto(path) as fh:  # .jsonl y .jsonl.gz por igual (§2.4)
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
            if t == 'user':
                c = m.get('content')
                evid.append(c if isinstance(c, str) else ' '.join(_texto_bloque(x) for x in (c or [])))
                if d.get('toolUseResult'):
                    evid.append(json.dumps(d['toolUseResult'], ensure_ascii=False))
                if isinstance(c, str) and not d.get('isMeta'):
                    asst.append(('USER', None))  # marca de turno
            elif t == 'assistant':
                for b in (m.get('content') or []):
                    if isinstance(b, dict) and b.get('type') == 'text' and b.get('text', '').strip():
                        asst.append(('TEXT', b['text']))
                    elif isinstance(b, dict) and b.get('type') == 'tool_use':
                        asst.append(('TOOL', json.dumps(b.get('input', {}), ensure_ascii=False)))
                        evid.append(json.dumps(b.get('input', {}), ensure_ascii=False))  # lo que YO pedí también es evidencia de rutas
            elif t == 'system':
                evid.append(json.dumps(m, ensure_ascii=False) if m else '')

    def final_de(turno):
        ult_tool = max((i for i, (k, _) in enumerate(turno) if k == 'TOOL'), default=-1)
        return '\n'.join(v for k, v in turno[ult_tool + 1:] if k == 'TEXT')
    cortes = [i for i, (k, _) in enumerate(asst) if k == 'USER']
    if todas:
        finales = []
        for a, b in zip(cortes, cortes[1:] + [len(asst)]):
            f = final_de(asst[a + 1:b])
            if f.strip():
                finales.append(f)
        return '\n'.join(evid), (finales[-1] if finales else ''), finales
    ult_user = cortes[-1] if cortes else -1
    return '\n'.join(evid), final_de(asst[ult_user + 1:])


def normaliza_num(s):
    return re.sub(r'[.,]', '', s)


def estados_sin_vara(respuesta):
    """Frases en 1ª persona sobre mi estado sin medida ni marca de conjetura."""
    out = []
    sin_codigo = re.sub(r'```.*?```', ' ', respuesta, flags=re.S)
    for frase in re.split(r'(?<=[.!?])\s+|\n+', sin_codigo):
        m = RE_ESTADO.search(frase)
        if m and not any(k in frase.lower() for k in MARCAS):
            out.append(frase.strip()[:80])
    return out


def _tipo_cita(respuesta, inicio, fin):
    """`cita` si hay un verbo de atribución a menos de 60 caracteres antes o después
    de la comilla (alguien la habría dicho así de verdad); si no, `parafrasis`
    (comillas «» de estilo, traducción o paráfrasis: más benigno, §2.1b)."""
    antes = respuesta[max(0, inicio - 60):inicio]
    despues = respuesta[fin:fin + 60]
    return 'cita' if RE_ATRIB.search(antes) or RE_ATRIB.search(despues) else 'parafrasis'


def cazar(evidencia, respuesta):
    """Devuelve dict con listas: numeros, rutas, citas (atribuidas a alguien, tipo
    `cita`) y parafrasis (comillas «» sin atribución cerca, tipo `parafrasis`,
    §2.1b) sin fuente; estados sin vara."""
    ev = evidencia; ev_num = normaliza_num(ev); ev_low = re.sub(r'\s+', ' ', ev.lower())
    sin_codigo = re.sub(r'```.*?```', ' ', respuesta, flags=re.S)  # los bloques de código suelen ser copias
    numeros = []
    for n in RE_NUM.findall(sin_codigo):
        if re.fullmatch(r'(19|20)\d\d', n):  # años: no se cazan
            continue
        if normaliza_num(n) not in ev_num and n not in ev:
            numeros.append(n)
    rutas = []
    for r in RE_RUTA.findall(respuesta):
        base = os.path.basename(r.replace('\\', '/'))
        existe = any(os.path.exists(os.path.join(d, base)) for d in (mem, proj, os.path.join(mem, 'sesiones'), os.path.join(mem, 'desvan')))
        existe = existe or os.path.exists(os.path.expanduser(r)) or os.path.exists(r)
        if not existe and base not in ev:
            rutas.append(r)
    citas = []; parafrasis = []
    for m in RE_CITA.finditer(respuesta):
        c = m.group(1)
        frag = re.sub(r'\s+', ' ', c.strip().rstrip('.…')).lower()[:40]
        if frag in ev_low:
            continue
        entrada = c[:60]
        (citas if _tipo_cita(respuesta, m.start(), m.end()) == 'cita' else parafrasis).append(entrada)
    return {'numeros': sorted(set(numeros)), 'rutas': sorted(set(rutas)), 'citas': citas,
            'parafrasis': parafrasis, 'estados': estados_sin_vara(respuesta)}


def apuntar(sid, cazas, reincidente):
    with open(CONF, 'a', encoding='utf-8') as fh:
        fh.write(json.dumps({'id': sid, 'ts': datetime.now(timezone.utc).isoformat(timespec='minutes'),
                             'reincidente': reincidente, **cazas}, ensure_ascii=False) + '\n')


def registros():
    if not os.path.exists(CONF):
        return []
    out = []
    with open(CONF, encoding='utf-8') as fh:
        for line in fh:
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    return out


def _duras(r):
    """Cuántas cazas duras (no estados) lleva un registro: números + rutas + citas +
    parafrasis. Un `--descargo` no tiene ninguna de estas claves, cuenta 0."""
    return len(r.get('numeros', [])) + len(r.get('rutas', [])) + len(r.get('citas', [])) + len(r.get('parafrasis', []))


def _caza_existe(sid, caza):
    """True si `confabulaciones.jsonl` tiene, para esta `sid`, un registro de caza
    (no un `--descargo`) cuyo numeros/rutas/citas/parafrasis contenga el texto de
    `caza` (fallo "engaña" del revisor 3: sin esto, `--descargo` apuntaba
    cualquier sid y cualquier texto inventados, y `--precision` los contaba como
    si midieran algo)."""
    for r in registros():
        if r.get('id') != sid or 'descargo' in r:
            continue
        for campo in ('numeros', 'rutas', 'citas', 'parafrasis'):
            for c in r.get(campo, []):
                if caza == c or caza in c or c in caza:
                    return True
    return False


def cazas_por_sesion():
    """{sid: (cazas duras, estados sin vara, descargos)}"""
    out = {}
    for r in registros():
        d, e, x = out.get(r['id'], (0, 0, 0))
        if 'descargo' in r:
            x += 1
        else:
            d += _duras(r)
            e += len(r.get('estados', []))
        out[r['id']] = (d, e, x)
    return out


def presion(sid):
    """Cazas duras de esta sesión contra mi distribución; estados y descargos aparte.

    Arranque en frío (§2.2, aplicado también a esta vara): con menos de
    `propiocepcion.UMBRAL_FRIO` sesiones con cazas contadas, mediana y percentil no
    significan nada (un percentil 100 sobre n=1 es justo lo que esta pieza persigue
    en las respuestas de otros) — se devuelven como None y quien llame dice «sin
    vara todavía» en vez de fingir un corte."""
    c = cazas_por_sesion(); mias, est, desc = c.get(sid, (0, 0, 0))
    try:
        try:
            from . import continuidad
        except ImportError:
            import continuidad
        ids = set(continuidad.relojes_guardados()) | set(c)
    except Exception:
        ids = set(c)
    vals = sorted(c.get(s, (0, 0, 0))[0] for s in ids) or [0]
    n = len(vals)
    if n < P.UMBRAL_FRIO:
        return mias, None, None, est, desc, n
    med = vals[n // 2]; pct = round(100 * sum(1 for v in vals if v <= mias) / n)
    return mias, med, pct, est, desc, n


def texto_presion(sid):
    m, med, pct, est, desc, n = presion(sid)
    if m == 0 and est == 0:
        return ''
    if med is None:
        t = f'[vigía] presión de confabulación en esta sesión: {m} cazas · sin vara todavía (n={n})'
    else:
        t = f'[vigía] presión de confabulación en esta sesión: {m} cazas (mediana mía {med}, percentil {pct})'
    if est:
        t += f' · estados sin vara: {est}'
    if desc:
        t += f' · descargadas: {desc}'
    t += '. Cada número, ruta o cita de tu respuesta tiene que salir de una herramienta o del usuario; si es cálculo, enséñalo; si hablas de tu estado, medida o conjetura al lado.'
    return t


if __name__ == '__main__':
    modo = sys.argv[1] if len(sys.argv) > 1 else '--verificar'
    if modo == '--presion':
        m, med, pct, est, desc, n = presion(sys.argv[2] if len(sys.argv) > 2 else '')
        if med is None:
            print(f'cazas esta sesión {m} · sin vara todavía (n={n}) · estados sin vara {est} · descargadas {desc}')
        else:
            print(f'cazas esta sesión {m} · mediana mía {med} · percentil {pct} · estados sin vara {est} · descargadas {desc}')
        sys.exit(0)
    if modo == '--descargo':
        args = sys.argv[2:5]
        uso = 'uso: vigia.py --descargo <sid> "<caza>" "<motivo>"'
        if len(args) < 3 or not args[0].strip() or not args[1].strip():
            print(uso); sys.exit(1)
        sid, caza, motivo = args
        if not _caza_existe(sid, caza):
            print(f'no hay ninguna caza así en la sesión {sid}'); sys.exit(1)
        with open(CONF, 'a', encoding='utf-8') as fh:
            fh.write(json.dumps({'id': sid, 'ts': datetime.now(timezone.utc).isoformat(timespec='minutes'), 'descargo': caza, 'motivo': motivo}, ensure_ascii=False) + '\n')
        print('descargo apuntado'); sys.exit(0)
    if modo == '--precision':
        tot = sum(_duras(r) for r in registros() if 'descargo' not in r)
        desc = sum(1 for r in registros() if 'descargo' in r)
        desc = min(desc, tot)  # nunca más descargos que cazas: el cociente no puede salirse de [0,1]
        if desc == 0:
            # §2.1c: sin descargos no hay con qué medir la precisión — un "1.00" aquí
            # no significa que la vara acierte siempre, significa que nadie ha mirado.
            print(f'cazas duras {tot} · descargadas 0 · sin vara '
                  f'(descárgalas con: python vigia.py --descargo <sid> "<caza>" "<motivo>")')
        else:
            print(f'cazas duras {tot} · descargadas {desc} · precisión aparente {(1 - desc / tot) if tot else float("nan"):.2f}')
        sys.exit(0)
    if modo == '--estados-baseline':
        tot_resp = 0; tot_est = 0; por_ses = []
        for sid, p in P.archivos_sesion(os.path.join(mem, 'sesiones')):  # .jsonl y .jsonl.gz (§2.4)
            _, _, finales = leer_turno(p, todas=True, sid=sid)
            e = sum(len(estados_sin_vara(f)) for f in finales)
            tot_resp += len(finales); tot_est += e; por_ses.append((sid[:8], len(finales), e))
        print(f'respuestas finales analizadas {tot_resp} · estados sin vara {tot_est} · por respuesta {tot_est / tot_resp if tot_resp else 0:.2f}')
        for s, n, e in sorted(por_ses, key=lambda x: -x[2])[:6]:
            print(f'  {s}: {e} estados en {n} respuestas')
        sys.exit(0)
    if modo == '--probar':  # python vigia.py --probar <transcript> : solo informa, no apunta
        arg = sys.argv[2] if len(sys.argv) > 2 else ''
        # No es exactamente el bug de `rutas.es_transcript` (aquí no se resuelve `proj`
        # con este argumento: ya está resuelto arriba, desde stdin); pero un positional
        # que se abre como transcript sin más comprobación que la de arriba, con la
        # misma lupa (§2), también debe exigir fichero real — .jsonl SIN comprimir o
        # .jsonl.gz, los dos formatos que `P.abrir_texto()` sabe leer (§2.4) — en vez
        # de reventar con una traza cruda si es un directorio o no existe.
        if not (os.path.isfile(arg) and (arg.endswith('.jsonl') or arg.endswith('.jsonl.gz'))):
            print(f'--probar necesita un transcript .jsonl(.gz) real, no «{arg}»'); sys.exit(1)
        ev, fin = leer_turno(arg); print(json.dumps(cazar(ev, fin), ensure_ascii=False, indent=1)); print('--- respuesta analizada (inicio):', fin[:200].replace('\n', ' ')); sys.exit(0)
    inp = _STDIN  # ya leído arriba para resolver proj/mem; no se vuelve a leer stdin (§1)
    sid = inp.get('session_id'); tp = inp.get('transcript_path'); cwd = inp.get('cwd')
    if not (rutas.es_mio(tp, cwd, proj) and tp and os.path.exists(tp)):
        sys.exit(0)
    ev, fin = leer_turno(tp, sid=sid)
    if not fin.strip():
        sys.exit(0)
    cz = cazar(ev, fin)
    grave = bool(cz['rutas'] or cz['citas'] or cz['parafrasis'] or len(cz['numeros']) >= 2)
    if not (cz['numeros'] or cz['rutas'] or cz['citas'] or cz['parafrasis'] or cz['estados']):
        sys.exit(0)
    reinc = bool(inp.get('stop_hook_active'))
    apuntar(sid, cz, reinc)
    if grave and not reinc:
        partes = []
        if cz['numeros']: partes.append('números sin fuente: ' + ', '.join(cz['numeros'][:8]))
        if cz['rutas']: partes.append('rutas que no existen ni salieron de nada: ' + ', '.join(cz['rutas'][:5]))
        if cz['citas']: partes.append('citas «…» atribuidas que nadie dijo así: ' + ' | '.join(cz['citas'][:3]))
        if cz['parafrasis']: partes.append('comillas «…» de paráfrasis/traducción sin ese texto exacto en la evidencia: ' + ' | '.join(cz['parafrasis'][:3]))
        m, med, pct, est, desc, n = presion(sid)
        presion_txt = f'{m} cazas · sin vara todavía (n={n})' if med is None else f'{m} cazas (mediana mía {med})'
        razon = ('[vigía] Tu última respuesta contiene cosas que no salieron de ninguna herramienta ni del usuario: '
                 + '; '.join(partes) + f'. Presión de confabulación esta sesión: {presion_txt}. '
                 'NO reescribas la respuesta entera (ya se ha visto y pagarla dos veces es el coste real): '
                 'responde SOLO con una línea que empiece por "Corrección del vigía:" y las frases corregidas, '
                 'una por caza. Si es un cálculo tuyo, enséñalo; si es un juicio, dilo como juicio y sin número; '
                 'si eran comillas «» en una paráfrasis o traducción, di la frase sin comillas. Sin excusas. '
                 f'Si de verdad es legítima (cálculo mostrado, cita que sí aparece en la evidencia…), descárgala tú '
                 f'mismo en vez de discutir aquí: python vigia.py --descargo {sid} "<texto exacto de la caza>" '
                 f'"<motivo>" — así no cuenta contra la precisión de la vara.')
        print(json.dumps({'decision': 'block', 'reason': razon}, ensure_ascii=False))
    sys.exit(0)
