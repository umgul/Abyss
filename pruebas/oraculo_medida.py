"""Oráculo de la medida: la semántica de referencia de `propiocepcion.extraer()` escrita a
la manera directa — una lectura por pieza (medida, frases, lecturas de fichas) y el
paréntesis consultado línea a línea. Es la vara fija contra la que `test_matrioshka.py`
comprueba que la pasada única y su muñeca dan exactamente lo mismo. No importa nada de
`abyss/` ni resuelve proyecto: los tramos llegan como un dict {sid: [(inicio, fin)]}.
Una línea JSON que no es un objeto hace fallar `medir` y `frases_usuario` de aquí: el
corpus que las compara no debe llevarla."""
import os
import re
import json
import gzip
import glob
import unicodedata
from datetime import datetime

CORR = re.compile(r'^\s*(no\b|nop\b|mal\b|mentira|falso|te equivocas|eso no|no es (así|cierto|verdad)|error\b|te has equivocado|no me refer)', re.I)
FICHA = re.compile(r'([\w\-.%áéíóúñ]+\.md)')


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


def abrir_texto(path):
    if path.endswith('.gz'):
        return gzip.open(path, 'rt', encoding='utf-8', errors='ignore')
    return open(path, encoding='utf-8', errors='ignore')


def _sid(path):
    base = os.path.basename(path)
    if base.endswith('.jsonl.gz'):
        return base[:-9]
    if base.endswith('.jsonl'):
        return base[:-6]
    return base


def medir(path, tramos):
    sid = _sid(path)
    ts = []; turnos = 0; turnos_limpios = 0; corr = 0; palabras_j = 0; req = {}; tools = 0; fichas = set(); web = 0; sondas = {}
    with abrir_texto(path) as fh:
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
            if d.get('timestamp'):
                ts.append(d['timestamp'])
            if t == 'user' and not d.get('isMeta'):
                c = m.get('content')
                if isinstance(c, str) and c.strip():
                    if c.lstrip().startswith('This session is being continued') or c.lstrip().startswith('<command-name>'):
                        continue
                    turnos += 1; palabras_j += len(c.split())
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
                    if name == 'Agent':
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


def frases_usuario(path, tramos):
    sid = _sid(path)
    out = []
    with abrir_texto(path) as fh:
        for line in fh:
            try:
                d = json.loads(line)
            except Exception:
                continue
            if d.get('type') != 'user' or d.get('isMeta') or d.get('isSidechain'):
                continue
            if en_parentesis(tramos, sid, d.get('timestamp')):
                continue
            c = (d.get('message') or {}).get('content')
            if isinstance(c, str) and c.strip():
                if c.lstrip().startswith('This session is being continued') or c.lstrip().startswith('<command-name>'):
                    continue
                out.append(re.sub(r'\s+', ' ', c.strip()))
    return out


def _ts_de_linea(line):
    try:
        return json.loads(line).get('timestamp')
    except Exception:
        return None


def lecturas(proj, fichas, tramos):
    """{ficha: set(sid)}: qué sesiones de `proj/*.jsonl` leyeron cada ficha, línea a línea."""
    reads = {f: set() for f in fichas}
    for sp in glob.glob(os.path.join(proj, '*.jsonl')):
        sid = os.path.basename(sp)[:-6]
        with open(sp, encoding='utf-8', errors='ignore') as fh:
            for line in fh:
                if 'memory' not in line or ('"name":"Read"' not in line and 'cat ' not in line):
                    continue
                if en_parentesis(tramos, sid, _ts_de_linea(line)):
                    continue
                line = unicodedata.normalize('NFC', line)
                for f in fichas:
                    if f in line:
                        reads[f].add(sid)
    return reads
