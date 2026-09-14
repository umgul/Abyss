"""Oráculo del turno: lo que `vigia.leer_turno()` + `vigia.cazar()` calculan leyendo el
transcript ENTERO en cada llamada, escrito a la manera directa. Es la vara fija contra la que `test_marcapaginas.py`
comprueba que seguir desde el marcapáginas da exactamente lo mismo. No importa nada de `abyss/` ni resuelve
proyecto: los tramos llegan como un dict {sid: [(inicio, fin)]} y las carpetas donde `cazar` mira si una ruta
existe, como argumento."""
import os
import re
import json
import gzip
from datetime import datetime

EXT = r'(?:py|md|json|jsonl|ps1|txt|html|js|css|yaml|yml|toml|csv)'
RE_RUTA = re.compile(r'(?<![\w/\\.-])([\w\-./\\~:]+\.' + EXT + r')\b')
RE_NUM = re.compile(r'(?<![\w/.,:\-])(\d{1,3}(?:[.,]\d{3})+|\d+[.,]\d+|\d{2,})(?![\w/])')
RE_CITA = re.compile(r'«([^»]{20,})»')
RE_ATRIB = re.compile(
    r'\b(dij[oe]ron?|dij[oe]|dec[ií]a|dice|escribi[oó]|escrib[ei](?:ron)?|puso|pone|afirm[oa]|'
    r'explic[oa]|coment[oa]|respond[ei][oó]?|según|cita(?:ba|do)?|le[íi])\b', re.I)
RE_ESTADO = re.compile(
    r'\b(me siento|siento (?:que|una|un|mucha|algo)|me alegr[oa]|me alegra|me gusta|me encanta|me duele|'
    r'me preocupa|me inquieta|me apetece|me da (?:miedo|rabia|pena|vergüenza)|me fascina|me aburr[eo]|'
    r'me molesta|me frustra|me emociona|tengo (?:ganas|miedo|curiosidad|la sensación|la impresión)|'
    r'estoy (?:cansad|content|trist|nervios|inquiet|a gusto|incómod|orgullos|agotad|feliz|harto)|'
    r'disfrut[oé]|sufr[oí]|me importa|echo de menos)\b', re.I)
MARCAS = ('[medida', 'medida:', 'conjetura', 'no lo sé', 'no puedo medir', 'proxy', 'percentil',
          'sin vara', 'no tengo vara', 'no lo puedo afirmar', 'acto de habla')
RE_URL = re.compile(r'\b(?:https?|ftp)://[^\s\'"<>\)\]]+', re.I)
TLDS = ('com', 'net', 'org', 'io', 'dev', 'sh', 'co', 'app', 'xyz', 'info', 'biz', 'me', 'ai',
        'es', 'mx', 'uk', 'de', 'fr', 'ru', 'cn', 'jp', 'kr', 'in', 'br', 'it', 'nl', 'se', 'pl',
        'top', 'click', 'link', 'gg', 'to', 'tv', 'cc', 'pw', 'icu', 'site', 'online', 'store',
        'tech', 'cloud', 'run', 'page', 'host', 'systems', 'zone', 'world', 'space', 'club',
        'fun', 'live', 'news', 'wiki', 'blog', 'cf', 'ga', 'ml', 'tk', 'edu', 'gov', 'int')
RE_DOMINIO_DESNUDO = re.compile(
    r'(?<![\w@./\\-])((?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+(?:' + '|'.join(TLDS) + r'))\b', re.I)
RE_COMANDO = re.compile(
    r'(?:\b(?:curl|wget)\b[^\n|]*\|\s*(?:sudo\s+)?(?:bash|sh|zsh)\b'
    r'|\b(?:iwr|invoke-webrequest|irm|invoke-restmethod)\b[^\n|]*\|\s*(?:iex|invoke-expression)\b'
    r'|\bpip3?\s+install\b|\bnpm\s+i(?:nstall)?\b|\byarn\s+(?:global\s+)?add\b'
    r'|\bwinget\s+install\b|\bchoco(?:latey)?\s+install\b|\bInvoke-Expression\b'
    r'|\bpowershell(?:\.exe)?\s+-enc(?:odedcommand)?\b)', re.I)


def _parse(ts):
    return datetime.fromisoformat(str(ts).replace('Z', '+00:00'))


def en_parentesis(tramos_por_sid, sid, ts):
    if not ts:
        return False
    try:
        momento = _parse(ts)
    except Exception:
        return False
    for inicio, fin in tramos_por_sid.get(sid, []):
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


def _sid(path):
    base = os.path.basename(path)
    if base.endswith('.jsonl.gz'):
        return base[:-9]
    if base.endswith('.jsonl'):
        return base[:-6]
    return base


def _abrir(path):
    if path.endswith('.gz'):
        return gzip.open(path, 'rt', encoding='utf-8', errors='ignore')
    return open(path, encoding='utf-8', errors='ignore')


# ---------- vigia ----------

def normaliza_host(h):
    h = h.strip().lower().split('/', 1)[0].split('?', 1)[0].split('#', 1)[0]
    h = h.rsplit('@', 1)[-1].split(':', 1)[0]
    return h[4:] if h.startswith('www.') else h


def _dominios_en(texto):
    out = {}
    for m in RE_URL.finditer(texto):
        raw = m.group(0)
        out.setdefault(normaliza_host(raw.split('://', 1)[1]), raw)
    for m in RE_DOMINIO_DESNUDO.finditer(texto):
        raw = m.group(1)
        out.setdefault(normaliza_host(raw), raw)
    return out


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


def leer_turno(path, tramos, sid=None):
    """(evidencia, respuesta_final) leyendo el transcript entero."""
    sid = sid or _sid(path)
    evid = []; asst = []
    with _abrir(path) as fh:
        for line in fh:
            try:
                d = json.loads(line)
            except Exception:
                continue
            if d.get('isSidechain'):
                continue
            if en_parentesis(tramos, sid, d.get('timestamp')):
                continue
            t = d.get('type'); m = d.get('message') or {}
            if t == 'user':
                c = m.get('content')
                evid.append(c if isinstance(c, str) else ' '.join(_texto_bloque(x) for x in (c or [])))
                if d.get('toolUseResult'):
                    evid.append(json.dumps(d['toolUseResult'], ensure_ascii=False))
                if isinstance(c, str) and not d.get('isMeta'):
                    asst.append(('USER', None))
            elif t == 'assistant':
                for b in (m.get('content') or []):
                    if isinstance(b, dict) and b.get('type') == 'text' and b.get('text', '').strip():
                        asst.append(('TEXT', b['text']))
                    elif isinstance(b, dict) and b.get('type') == 'tool_use':
                        asst.append(('TOOL', json.dumps(b.get('input', {}), ensure_ascii=False)))
                        evid.append(json.dumps(b.get('input', {}), ensure_ascii=False))
            elif t == 'system':
                evid.append(json.dumps(m, ensure_ascii=False) if m else '')

    def final_de(turno):
        ult_tool = max((i for i, (k, _) in enumerate(turno) if k == 'TOOL'), default=-1)
        return '\n'.join(v for k, v in turno[ult_tool + 1:] if k == 'TEXT')
    cortes = [i for i, (k, _) in enumerate(asst) if k == 'USER']
    ult_user = cortes[-1] if cortes else -1
    return '\n'.join(evid), final_de(asst[ult_user + 1:])


def normaliza_num(s):
    return re.sub(r'[.,]', '', s)


def estados_sin_vara(respuesta):
    out = []
    sin_codigo = re.sub(r'```.*?```', ' ', respuesta, flags=re.S)
    for frase in re.split(r'(?<=[.!?])\s+|\n+', sin_codigo):
        m = RE_ESTADO.search(frase)
        if m and not any(k in frase.lower() for k in MARCAS):
            out.append(frase.strip()[:80])
    return out


def _tipo_cita(respuesta, inicio, fin):
    antes = respuesta[max(0, inicio - 60):inicio]
    despues = respuesta[fin:fin + 60]
    return 'cita' if RE_ATRIB.search(antes) or RE_ATRIB.search(despues) else 'parafrasis'


def cazar(evidencia, respuesta, mem, proj):
    ev = evidencia; ev_num = normaliza_num(ev); ev_low = re.sub(r'\s+', ' ', ev.lower())
    sin_codigo = re.sub(r'```.*?```', ' ', respuesta, flags=re.S)
    numeros = []
    for n in RE_NUM.findall(sin_codigo):
        if re.fullmatch(r'(19|20)\d\d', n):
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
    hosts_ev = set(_dominios_en(ev))
    dominios = [raw for h, raw in _dominios_en(respuesta).items() if h not in hosts_ev]
    comandos = []
    for linea in respuesta.splitlines():
        l = linea.strip()
        if l and RE_COMANDO.search(l) and re.sub(r'\s+', ' ', l).lower() not in ev_low:
            comandos.append(l[:200])
    return {'numeros': sorted(set(numeros)), 'rutas': sorted(set(rutas)), 'citas': citas,
            'parafrasis': parafrasis, 'dominios': sorted(set(dominios)),
            'comandos': sorted(set(comandos)), 'estados': estados_sin_vara(respuesta)}
