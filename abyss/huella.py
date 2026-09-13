"""Huella: todo lo que un hilo toca FUERA de su propia carpeta de código — para poder
decir, al cerrar, QUÉ tocó, y limpiarlo él mismo si hace falta, sin adivinar.

Tres ganchos, cada uno con el JSON de stdin que espera Claude Code:

    --arranque    (SessionStart)   foto inicial de puertos en escucha y procesos con su
                                    hora de arranque, guardada como snapshot base (nada
                                    se imprime).
    --herramienta (PostToolUse)    Write/Edit/NotebookEdit: registra la ruta escrita.
                                    Bash/PowerShell: registra el comando (recortado a 200
                                    caracteres) y la DIFERENCIA de puertos/procesos contra
                                    la última foto — puertos nuevos y procesos nuevos (pid
                                    que no estaba, o con otra hora de arranque). Nada se
                                    imprime: es instrumentación silenciosa.
    --fin         (Stop)           texto PLANO (no JSON), solo si algo registrado en esta
                                    sesión sigue vivo AHORA MISMO (foto fresca, no el
                                    snapshot guardado); sin nada vivo, silencio total.
                                    Solo cuentan los procesos que cuelgan del de esta
                                    sesión; los de atribución incierta (su padre ya no
                                    existe) salen en `--informe` y `--limpiar` nunca los
                                    mata. Un proceso que cuelga de otro vivo ajeno no se
                                    registra.

Registro: `mem/huella/<session_id>.jsonl`, una línea JSON por evento (`ts` ISO UTC, `tipo`
`inicio`|`escrito`|`comando`|`puerto_nuevo`|`proceso_nuevo`, y según el tipo
`ruta`/`comando`/`puerto`/`pid`/`nombre`/`inicio`); nunca sale de `mem` ni por red. El tipo
`comando` guarda el TEXTO LITERAL (recortado a 200 caracteres): un token, una cabecera
`Authorization` o una URL firmada pasada por línea de comandos quedan ahí en local.

Diagnóstico manual (sin gancho): `python huella.py --informe [id]` lista ficheros escritos,
procesos y puertos que este hilo vio nacer/abrirse y que SIGUEN vivos ahora. `python
huella.py --limpiar [id] [--si]`: sin `--si` solo dice qué HARÍA; con `--si` mata SOLO los
procesos cuyo pid Y hora de arranque coinciden con lo registrado AHORA MISMO (reconsultado
al limpiar, no fiado de un `--informe` viejo) y borra SOLO los ficheros bajo el directorio
temporal o bajo `mem/huella|mapas|pdf` — cualquier otra ruta registrada (incluida cualquier
cosa suelta en la raíz de `mem`, como `MEMORY.md`) se LISTA y no se toca. `[id]`: sin él, se
usa `session_id` del stdin, o si no, el hilo con el latido más reciente en `mem/.vivo/`
(heurística); sin ninguna de las dos cosas, se rehúsa (código 1).

Coste declarado, no escondido: `mem/huella/_costes.json` guarda las últimas 30 medidas (ms)
de la foto (siempre la llamada COMBINADA a `powershell.exe`, más rápida que dos separadas).
Con menos de 3 medidas, `--herramienta` fotografía siempre; con 3 o más, si la MEDIANA
supera 1500 ms —por encima de eso solo se fotografía tras comandos que parecen persistentes
(contienen `start`/`python`/`node`/`serve`/`nohup`/`&`); la foto mide ~1 s en la máquina de
desarrollo— se activa esa heurística declarada como tal. El comando en sí SIEMPRE se
registra, se tome o no la foto.

Windows: `Get-NetTCPConnection`/`Get-CimInstance Win32_Process` en una sola invocación de
`powershell.exe` (timeout 8 s). Linux/macOS: `ss`/`lsof` y `ps`, escrito contra la
especificación pero SIN EJECUTAR en esta máquina (es Windows): sin medida propia de esa
rama. `--limpiar`/`--informe` nunca inventan un proceso o puerto "vivo": sin dato, lo dice.

Diseño para las pruebas (igual que `cuerpo.py`): ninguna función toca `rutas.resolver()` ni
stdin al importarse — todas reciben `mem` como argumento; solo `__main__` resuelve
`proj`/`mem` y lee stdin.
"""
import sys
try:                       # la consola de Windows y la salida tienen que hablar
    from . import consola  # el mismo idioma: ver abyss/consola.py
except ImportError:
    import consola
consola.preparar()
import os, re, json, glob, time, subprocess, tempfile
from pathlib import Path
from datetime import datetime, timezone

try:
    from . import rutas
except ImportError:
    import rutas

DIRNOMBRE = 'huella'
TOPE_MEDIANA_MS = 1500     # por encima de esto, fotografiar solo tras comandos "persistentes"
MIN_MEDIDAS_COSTE = 3      # con menos medidas de coste, no hay mediana fiable: se fotografía siempre
VENTANA_COSTES = 30        # cuántas medidas de coste recientes se conservan
HEURISTICA_PERSISTENTE = ('start', 'python', 'node', 'serve', 'nohup')  # + el carácter '&' aparte


# ---------- rutas de datos (siempre mem/huella/...) ----------

def _dir(mem):
    return os.path.join(mem, DIRNOMBRE)


def _ruta_log(mem, sid):
    return os.path.join(_dir(mem), sid + '.jsonl')


def _ruta_snapshot(mem, sid):
    return os.path.join(_dir(mem), sid + '.snapshot.json')


def _ruta_costes(mem):
    return os.path.join(_dir(mem), '_costes.json')


def _ahora():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def registrar(mem, sid, evento):
    os.makedirs(_dir(mem), exist_ok=True)
    with open(_ruta_log(mem, sid), 'a', encoding='utf-8') as fh:
        fh.write(json.dumps(evento, ensure_ascii=False) + '\n')


def eventos(mem, sid):
    """Todos los eventos registrados de esta sesión, en orden. [] si nunca se
    registró nada (el módulo no corrió, o no tocó nada fuera de su carpeta)."""
    out = []
    try:
        with open(_ruta_log(mem, sid), encoding='utf-8') as fh:
            for linea in fh:
                linea = linea.strip()
                if not linea:
                    continue
                try:
                    out.append(json.loads(linea))
                except Exception:
                    continue
    except FileNotFoundError:
        pass
    return out


def snapshot_leer(mem, sid):
    try:
        with open(_ruta_snapshot(mem, sid), encoding='utf-8') as fh:
            return json.load(fh)
    except Exception:
        return None


def snapshot_escribir(mem, sid, foto_dict):
    os.makedirs(_dir(mem), exist_ok=True)
    with open(_ruta_snapshot(mem, sid), 'w', encoding='utf-8') as fh:
        json.dump(foto_dict, fh, ensure_ascii=False)


def costes_leer(mem):
    try:
        with open(_ruta_costes(mem), encoding='utf-8') as fh:
            return json.load(fh)
    except Exception:
        return []


def costes_apuntar(mem, ms):
    datos = costes_leer(mem)
    datos.append(ms)
    datos = datos[-VENTANA_COSTES:]
    os.makedirs(_dir(mem), exist_ok=True)
    with open(_ruta_costes(mem), 'w', encoding='utf-8') as fh:
        json.dump(datos, fh)
    return datos


# ---------- instrumentos: puertos en escucha + procesos con hora de arranque ----------

def _powershell(cmd, timeout=8):
    """(stdout, pid) de un script de PowerShell (`-NoProfile -NonInteractive`).
    `stdout` es `None` si falla, se agota el tiempo, o el proceso no arranca.
    `pid` es el del propio `powershell.exe` (por eso `Popen`): `foto()` tiene que
    poder excluirse a sí misma, porque ese proceso se ve vivo mientras consulta."""
    try:
        proc = subprocess.Popen(['powershell', '-NoProfile', '-NonInteractive', '-Command', cmd],
                                 stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    except Exception:
        return None, None
    try:
        salida, _err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        try:
            proc.communicate(timeout=2)
        except Exception:
            pass
        return None, proc.pid
    return (salida if proc.returncode == 0 else None), proc.pid


def _normalizar_lista(x):
    """`ConvertTo-Json` de PowerShell da `null` cuando la colección de origen
    tiene CERO filas (no una lista vacía) y un objeto suelto (no una lista de un
    elemento) cuando tiene EXACTAMENTE una — aquí se normalizan las dos formas.
    Se llama solo cuando ya se sabe que el comando ENTERO funcionó, así que
    `None` aquí significa «cero filas», no «sin dato»."""
    if x is None:
        return []
    if isinstance(x, dict):
        return [x]
    return x


def leer_puertos_y_procesos_windows():
    """(puertos, procesos, pid_powershell) de UNA sola llamada combinada a
    PowerShell — ver docstring del módulo para el coste medido de separarlas.
    `puertos` es {puerto_str: pid_str} (pid "0" si `OwningProcess` viene
    vacío); `procesos` es {pid_str: {'nombre':..., 'inicio': iso, 'padre': pid_str|None}}. Cualquiera
    de los dos es `None` si la llamada entera falló o no dio JSON legible
    ("sin dato": nunca un dict vacío fingiendo que se miró y no había nada).
    `pid_powershell` es el PID del propio `powershell.exe` que hizo la
    consulta (o `None` si ni siquiera se pudo lanzar) — `foto()` lo usa para
    descartarse a sí mismo del resultado."""
    salida, pid_ps = _powershell(
        "$p = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | "
        "Select-Object LocalPort,OwningProcess; "
        "$q = Get-CimInstance Win32_Process | Where-Object {$_.CreationDate} | "
        "Select-Object @{n='Id';e={$_.ProcessId}},@{n='ProcessName';e={$_.Name}},"
        "@{n='Padre';e={$_.ParentProcessId}},@{n='Inicio';e={$_.CreationDate.ToString('o')}}; "
        "@{puertos=$p; procesos=$q} | ConvertTo-Json -Compress -Depth 4"
    )
    if not salida or not salida.strip():
        return None, None, pid_ps
    try:
        d = json.loads(salida)
    except Exception:
        return None, None, pid_ps
    try:
        puertos = {str(int(x['LocalPort'])): str(int(x.get('OwningProcess') or 0))
                   for x in _normalizar_lista(d.get('puertos')) if x.get('LocalPort') is not None}
        procesos = {str(int(x['Id'])): {'nombre': x.get('ProcessName') or '', 'inicio': x.get('Inicio') or '',
                                        'padre': None if x.get('Padre') is None else str(int(x['Padre']))}
                    for x in _normalizar_lista(d.get('procesos')) if x.get('Id') is not None}
    except Exception:
        return None, None, pid_ps
    return puertos, procesos, pid_ps


def _parsear_ss(salida):
    """`ss -ltnp` (Linux): una línea por socket en escucha, con `...:<puerto> ...
    users:(("nombre",pid=<pid>,...))` al final si el proceso es visible (puede
    no serlo sin privilegios: en ese caso el puerto se registra con pid '')."""
    out = {}
    for linea in salida.splitlines()[1:]:
        m = re.search(r':(\d+)\s+\S+\s+\S+.*?pid=(\d+)', linea)
        if m:
            out[m.group(1)] = m.group(2)
            continue
        m2 = re.search(r':(\d+)\s', linea)
        if m2:
            out.setdefault(m2.group(1), '')
    return out


def _parsear_lsof(salida):
    """`lsof -iTCP -sTCP:LISTEN -P -n` (Linux/macOS de respaldo si no hay `ss`):
    columnas separadas por espacios, PID en la 2ª, puerto al final del `NAME`
    (`*:8080` o `1.2.3.4:8080`)."""
    out = {}
    for linea in salida.splitlines()[1:]:
        partes = linea.split()
        if len(partes) < 9:
            continue
        m = re.search(r':(\d+)$', partes[8].split('->')[0])
        if m:
            out[m.group(1)] = partes[1]
    return out


def leer_puertos_posix():
    """{puerto_str: pid_str}|None con `ss -ltnp`, o `lsof -iTCP -sTCP:LISTEN`
    si `ss` no existe. NO probado en esta máquina (es Windows): escrito contra
    el formato documentado de esos comandos, sin ejecutar ni medir aquí."""
    try:
        r = subprocess.run(['ss', '-ltnp'], capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            return _parsear_ss(r.stdout)
    except Exception:
        pass
    try:
        r = subprocess.run(['lsof', '-iTCP', '-sTCP:LISTEN', '-P', '-n'], capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            return _parsear_lsof(r.stdout)
    except Exception:
        pass
    return None


def leer_procesos_posix():
    """{pid_str: {'nombre':..., 'inicio': iso, 'padre': pid_str}}|None con
    `ps -eo pid,ppid,lstart,comm`. Escrito contra el formato documentado de `ps`,
    sin ejecutar ni medir en Windows."""
    try:
        r = subprocess.run(['ps', '-eo', 'pid,ppid,lstart,comm'], capture_output=True, text=True, timeout=5)
        if r.returncode != 0:
            return None
        out = {}
        for linea in r.stdout.splitlines()[1:]:
            partes = linea.split(None, 6)
            if len(partes) < 7:
                continue
            pid, ppid, dow, mon, day, hhmmss_year, resto = partes
            nombre = resto.split()[-1] if resto.split() else ''
            try:
                dt = datetime.strptime(f'{dow} {mon} {day} {hhmmss_year}', '%a %b %d %H:%M:%S %Y')
                inicio = dt.isoformat()
            except Exception:
                inicio = ''
            out[pid] = {'nombre': nombre, 'inicio': inicio, 'padre': ppid}
        return out
    except Exception:
        return None


def _pids_propios(pid_powershell=None):
    """PIDs del árbol del propio gancho, que nunca cuentan como `proceso_nuevo`: este
    intérprete, quien lo lanzó y el `powershell.exe` que acaba de tomar la foto
    (se ve vivo a sí mismo mientras corre)."""
    out = {str(os.getpid()), str(os.getppid())}
    if pid_powershell is not None:
        out.add(str(pid_powershell))
    return out


_SHELLS = {'cmd', 'bash', 'sh', 'zsh', 'dash', 'powershell', 'pwsh', 'conhost', 'mintty'}


def _nombre_base(nombre):
    n = (nombre or '').lower()
    return n[:-4] if n.endswith('.exe') else n


def _raiz_sesion(procesos):
    """El primer antepasado de este gancho que no es un shell: el proceso de Claude
    Code que lanza ganchos y herramientas (o quien lanza las pruebas). None si la
    tabla no permite seguir la cadena."""
    if not procesos:
        return None
    pid, vistos = str(os.getppid()), set()
    while pid in procesos and pid not in vistos:
        vistos.add(pid)
        info = procesos[pid]
        if _nombre_base(info.get('nombre')) not in _SHELLS:
            return {'pid': pid, 'inicio': info.get('inicio')}
        pid = info.get('padre')
    return None


def _desciende_de(procesos, pid, raiz):
    """True si `pid` cuelga de `raiz`, False si cuelga de otro proceso vivo, None si
    la cadena se corta antes (un padre que ya no existe) y no se puede decir."""
    vistos = set()
    while pid and pid not in vistos:
        vistos.add(pid)
        info = procesos.get(pid)
        if pid == raiz['pid']:
            # la raíz puede faltar de la tabla: `foto()` quita al padre del propio gancho, y
            # cuando el gancho lo lanza la raíz misma, la raíz ES ese padre (vivo, verificado)
            return True if info is None else info.get('inicio') == raiz['inicio']
        if info is None:
            return None
        pid = info.get('padre')
    return False if pid else None


def foto():
    """({'puertos': {...}|None, 'procesos': {...}|None, 'raiz': {...}|None}, coste_ms).
    `procesos` nunca incluye el árbol del propio gancho (`_pids_propios()`); `raiz`
    es el proceso de sesión del que cuelga este gancho (`_raiz_sesion()`), para
    atribuir los procesos nuevos. `coste_ms` es solo el tiempo de esta llamada."""
    t0 = time.perf_counter()
    if os.name == 'nt':
        puertos, procesos, pid_ps = leer_puertos_y_procesos_windows()
        propios = _pids_propios(pid_ps)
    else:
        puertos = leer_puertos_posix()
        procesos = leer_procesos_posix()
        propios = _pids_propios()
    raiz = _raiz_sesion(procesos)
    if procesos is not None:
        procesos = {pid: info for pid, info in procesos.items() if pid not in propios}
    coste_ms = round((time.perf_counter() - t0) * 1000)
    return {'puertos': puertos, 'procesos': procesos, 'raiz': raiz}, coste_ms


# ---------- heurística de cuándo fotografiar (coste medido, no ley) ----------

def _mediana(datos):
    if not datos:
        return None
    s = sorted(datos); n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def parece_persistente(comando):
    """¿Este comando PARECE que puede dejar algo corriendo? Heurística declarada,
    no ley — falsos negativos y falsos positivos son ambos posibles y esperados."""
    c = comando or ''
    return any(p in c.lower() for p in HEURISTICA_PERSISTENTE) or '&' in c


def debe_fotografiar(costes_previos, comando):
    """¿Toca tomar la foto tras este comando? Con menos de `MIN_MEDIDAS_COSTE`
    medidas previas no hay mediana fiable: se fotografía siempre, para poder
    medirla. Con mediana por encima de `TOPE_MEDIANA_MS`, solo si el comando
    parece persistente (`parece_persistente`)."""
    if len(costes_previos) < MIN_MEDIDAS_COSTE:
        return True
    med = _mediana(costes_previos)
    if med is None or med <= TOPE_MEDIANA_MS:
        return True
    return parece_persistente(comando)


def diferencias(anterior, actual):
    """[(tipo, datos)] entre dos fotos: `puerto_nuevo` ({'puerto','pid'}) y
    `proceso_nuevo` ({'pid','nombre','inicio'} más, si hay raíz de sesión, `seguro`:
    True si cuelga de ella, False si su cadena de padres se corta antes de poder
    decirlo). Un proceso nuevo que cuelga de otro proceso vivo ajeno no es de este
    hilo y no se registra. Un campo en `None` en cualquiera de los dos lados
    (instrumento sin dato) se salta esa comparación entera."""
    out = []
    ap, an = anterior.get('puertos'), actual.get('puertos')
    if ap is not None and an is not None:
        for puerto in sorted(set(an) - set(ap), key=lambda x: int(x)):
            out.append(('puerto_nuevo', {'puerto': puerto, 'pid': an.get(puerto)}))
    aq, cq = anterior.get('procesos'), actual.get('procesos')
    raiz = anterior.get('raiz') or actual.get('raiz')
    if aq is not None and cq is not None:
        for pid, info in cq.items():
            previo = aq.get(pid)
            if previo is not None and previo.get('inicio') == info.get('inicio'):
                continue
            datos = {'pid': pid, 'nombre': info.get('nombre'), 'inicio': info.get('inicio')}
            if raiz is not None:
                seguro = _desciende_de(cq, pid, raiz)
                if seguro is False:
                    continue
                datos['seguro'] = bool(seguro)
            out.append(('proceso_nuevo', datos))
    return out


# ---------- las tres operaciones de gancho (puras salvo E/S en mem/huella/) ----------

def arrancar(mem, sid):
    """`--arranque` (SessionStart): foto base, guardada como snapshot; un evento
    `inicio` con cuántos puertos/procesos había (o `None` si ese instrumento
    falló) y el coste de esta foto."""
    actual, coste_ms = foto()
    snapshot_escribir(mem, sid, actual)
    costes_apuntar(mem, coste_ms)
    registrar(mem, sid, {
        'ts': _ahora(), 'tipo': 'inicio',
        'puertos_iniciales': None if actual['puertos'] is None else len(actual['puertos']),
        'procesos_iniciales': None if actual['procesos'] is None else len(actual['procesos']),
        'foto_ms': coste_ms,
    })


def registrar_escritura(mem, sid, ruta):
    registrar(mem, sid, {'ts': _ahora(), 'tipo': 'escrito', 'ruta': ruta})


def registrar_comando(mem, sid, comando):
    """`--herramienta` (PostToolUse de Bash/PowerShell): SIEMPRE registra el
    comando (recortado a 200 caracteres); la foto y su diferencia contra el
    último snapshot solo si `debe_fotografiar()` lo dice. Sin ningún snapshot
    previo (p. ej. `--arranque` nunca corrió), no hay contra qué diferenciar:
    se guarda la foto actual como base y no se registra ningún evento nuevo
    (no se puede saber qué había ANTES de esta misma llamada)."""
    comando = (comando or '')[:200]
    registrar(mem, sid, {'ts': _ahora(), 'tipo': 'comando', 'comando': comando})
    if not debe_fotografiar(costes_leer(mem), comando):
        return
    anterior = snapshot_leer(mem, sid)
    actual, coste_ms = foto()
    costes_apuntar(mem, coste_ms)
    if anterior is not None:
        if actual.get('raiz') is None:
            actual['raiz'] = anterior.get('raiz')
        for tipo, datos in diferencias(anterior, actual):
            registrar(mem, sid, {'ts': _ahora(), 'tipo': tipo, 'foto_ms': coste_ms, **datos})
    snapshot_escribir(mem, sid, actual)


# ---------- --informe / --limpiar ----------

def _raiz(ruta):
    """Raíz para agrupar («agrupados por raíz»): unidad + primer directorio
    en Windows (`C:\\Users`), `/` + primer directorio en POSIX (`/tmp`).
    Heurística de agrupación, no una ruta canónica."""
    partes = Path(ruta).parts
    return str(Path(*partes[:2])) if len(partes) >= 2 else str(Path(ruta))


def agrupar_por_raiz(rutas_):
    grupos = {}
    for r in rutas_:
        grupos.setdefault(_raiz(r), []).append(r)
    return grupos


def informe(mem, sid, foto_actual=None):
    """Ficheros escritos (agrupados por raíz), procesos vivos (pid, nombre, hora
    de arranque — solo si la hora registrada SIGUE coincidiendo ahora) y puertos
    vivos (siguen en la foto actual) de esta sesión. `foto_actual` se puede pasar
    ya calculada (la usa `resumen_stop()` con el último snapshot guardado, para
    no pagar una foto fresca en cada Stop); si no, se toma una nueva."""
    evs = eventos(mem, sid)
    escritos = sorted({e['ruta'] for e in evs if e.get('tipo') == 'escrito' and e.get('ruta')})
    procesos_reg = {e['pid']: e for e in evs if e.get('tipo') == 'proceso_nuevo'}
    puertos_reg = {e['puerto']: e for e in evs if e.get('tipo') == 'puerto_nuevo'}
    if foto_actual is None:
        foto_actual, _coste = foto()
    fp = foto_actual.get('puertos'); fq = foto_actual.get('procesos')
    procesos_vivos = []
    for pid, e in procesos_reg.items():
        info = (fq or {}).get(pid)
        if info is not None and info.get('inicio') == e.get('inicio'):
            procesos_vivos.append({'pid': pid, 'nombre': e.get('nombre'), 'inicio': e.get('inicio'),
                                   'seguro': e.get('seguro', True)})
    puertos_vivos = []
    for puerto, e in puertos_reg.items():
        if fp is not None and puerto in fp:
            puertos_vivos.append({'puerto': puerto, 'pid': fp[puerto]})
    return {
        'sesion': sid,
        'ficheros_escritos': agrupar_por_raiz(escritos),
        'procesos_vivos': procesos_vivos,
        'puertos_vivos': puertos_vivos,
        'sin_dato_puertos': fp is None,
        'sin_dato_procesos': fq is None,
    }


def texto_informe(inf):
    L = [f"[huella] sesión {inf['sesion'][:8]}"]
    if not inf['ficheros_escritos']:
        L.append('ficheros escritos: ninguno registrado')
    else:
        L.append('ficheros escritos:')
        for raiz, lst in sorted(inf['ficheros_escritos'].items()):
            L.append(f'  {raiz} ({len(lst)}):')
            for r in lst:
                L.append(f'    {r}')
    if inf['sin_dato_procesos']:
        L.append('procesos vivos: sin dato (no se pudo consultar en esta máquina)')
    elif not inf['procesos_vivos']:
        L.append('procesos vivos: ninguno')
    else:
        for p in inf['procesos_vivos']:
            nota = '' if p.get('seguro', True) else ' (atribución incierta: su padre ya no existe)'
            L.append(f"  proceso vivo: pid {p['pid']} {p['nombre']} desde {p['inicio']}{nota}")
    if inf['sin_dato_puertos']:
        L.append('puertos vivos: sin dato (no se pudo consultar en esta máquina)')
    elif not inf['puertos_vivos']:
        L.append('puertos vivos: ninguno')
    else:
        for p in inf['puertos_vivos']:
            L.append(f"  puerto vivo: {p['puerto']} (pid {p['pid']})")
    return '\n'.join(L)


def resumen_stop(mem, sid):
    """`--fin` (Stop): comprueba con una foto FRESCA (el último snapshot es justo la
    foto en la que se detectó cada novedad; compararlo contra ella sería tautológico).
    Solo fotografía si hay algo registrado que comprobar. Los procesos de atribución
    incierta (su padre ya no existe) no cuentan aquí: en Windows eso incluye servicios del
    sistema cuya cadena de padres está rota, y atribuírselos al hilo sería falso. Se ven en
    `--informe`."""
    evs = eventos(mem, sid)
    if not any(e.get('tipo') in ('proceso_nuevo', 'puerto_nuevo') for e in evs):
        return ''
    inf = informe(mem, sid)  # foto fresca (foto_actual=None por defecto)
    n_p = sum(1 for p in inf['procesos_vivos'] if p.get('seguro', True))
    n_pu = len(inf['puertos_vivos'])
    if n_p == 0 and n_pu == 0:
        return ''
    return f'[huella] {n_p} proceso y {n_pu} puerto abiertos por este hilo siguen vivos: --informe'


def _bajo(ruta, base):
    try:
        return os.path.commonpath([os.path.abspath(ruta), os.path.abspath(base)]) == os.path.abspath(base)
    except Exception:
        return False


# Subcarpetas de `mem` que ESTE paquete genera por su cuenta (mismo criterio que
# `instalar.DATOS_GENERADOS`). Nada suelto en la raíz de `mem` (MEMORY.md, fichas
# *.md, cuerpo.jsonl…) es borrable: eso es memoria o configuración del usuario.
_MEM_SUBCARPETAS_GENERADAS = ('huella', 'mapas', 'pdf')


def _bajo_mem_generado(ruta, mem):
    """¿`ruta` cae bajo una subcarpeta de `mem` que abyss genera por su cuenta
    (`_MEM_SUBCARPETAS_GENERADAS`)? Nunca es `True` para `MEMORY.md`, ninguna
    ficha `*.md` de `mem`, ni ningún fichero suelto directamente en la raíz de
    `mem` (`cuerpo.jsonl`, `imagen_config.json`, `parentesis.json`...): eso es
    memoria o configuración del usuario, no algo que este módulo deba poder
    borrar solo porque un `Write` de la sesión pasó por ahí."""
    try:
        nombre = os.path.basename(os.path.abspath(ruta))
    except Exception:
        return False
    if nombre.lower().endswith('.md'):
        return False
    return any(_bajo(ruta, os.path.join(mem, sub)) for sub in _MEM_SUBCARPETAS_GENERADAS)


def _matar(pid):
    try:
        if os.name == 'nt':
            r = subprocess.run(['taskkill', '/PID', str(pid), '/F'], capture_output=True, text=True, timeout=8)
            return r.returncode == 0
        os.kill(int(pid), 9)
        return True
    except Exception:
        return False


def limpiar(mem, sid, confirmar):
    """Sin `confirmar`: solo dice qué HARÍA (ni mata ni borra nada). Con
    `confirmar=True`: vuelve a pedir `informe()` FRESCO (re-verifica pid + hora
    de arranque en este mismo instante, no se fía de una llamada anterior — un
    pid reciclado entre medias con otra hora de arranque no entra en
    `procesos_vivos` y por tanto no se toca) y mata esos procesos; borra SOLO
    los ficheros registrados que estén bajo el directorio temporal del sistema
    o bajo una subcarpeta de `mem` que este paquete genera por su cuenta
    (`_bajo_mem_generado()`: `mem/huella/`, `mem/mapas/`, `mem/pdf/` — nunca
    `MEMORY.md` ni una ficha `*.md` ni nada suelto en la raíz de `mem`, que es
    memoria o configuración del usuario, no algo generado por este módulo) —
    cualquier otro se lista en `no_tocados` y nunca se toca."""
    inf = informe(mem, sid)
    tmp = tempfile.gettempdir()
    borrables, no_tocados = [], []
    for lst in inf['ficheros_escritos'].values():
        for r in lst:
            (borrables if (_bajo(r, tmp) or _bajo_mem_generado(r, mem)) else no_tocados).append(r)

    L = [f"[huella --limpiar] sesión {sid[:8]}" + ('' if confirmar else ' (simulación, sin --si)')]
    if not inf['procesos_vivos']:
        L.append('procesos: ninguno vivo que matar')
    for p in inf['procesos_vivos']:
        if not p.get('seguro', True):
            # sin padre no se puede afirmar que sea de este hilo: puede ser un servicio del sistema
            L.append(f"  no se toca (atribución incierta): pid {p['pid']} {p['nombre']}")
            continue
        if confirmar:
            ok = _matar(p['pid'])
            L.append(f"  proceso {p['pid']} {p['nombre']}: {'matado' if ok else 'no se pudo matar'}")
        else:
            L.append(f"  mataría: pid {p['pid']} {p['nombre']} (desde {p['inicio']})")
    if not borrables:
        L.append('ficheros: ninguno bajo temp/ ni mem/ que borrar')
    for r in borrables:
        if confirmar:
            try:
                os.remove(r)
                L.append(f'  borrado: {r}')
            except Exception as e:
                L.append(f'  no se pudo borrar {r}: {e}')
        else:
            L.append(f'  borraría: {r}')
    if no_tocados:
        L.append('fuera de temp/ y de lo que este paquete genera en mem/, no se tocan '
                 '(bórralos tú si hace falta):')
        for r in no_tocados:
            L.append(f'  {r}')
    return '\n'.join(L)


# ---------- heurística de sesión actual (mismo mecanismo que parentesis.py) ----------

def _sesion_actual(mem):
    mejor = None
    for p in glob.glob(os.path.join(mem, '.vivo', '*.json')):
        try:
            with open(p, encoding='utf-8') as fh:
                v = json.load(fh)
        except Exception:
            continue
        ts = v.get('ts', 0)
        if mejor is None or ts > mejor[1]:
            mejor = (v.get('id') or os.path.basename(p)[:-5], ts)
    return mejor[0] if mejor else None


# ---------- CLI ----------

def _parse_argv(argv):
    banderas = {}; pos = []; desconocidas = []; i = 0
    while i < len(argv):
        a = argv[i]
        if a == '--si':
            banderas['si'] = True; i += 1; continue
        if a in ('--proyecto', '--sesion') and i + 1 < len(argv):
            banderas[a[2:]] = argv[i + 1]; i += 2; continue
        if a.startswith('--'):
            desconocidas.append(a); i += 1; continue
        pos.append(a); i += 1
    return banderas, pos, desconocidas


if __name__ == '__main__':
    _argv = sys.argv[1:]
    _modo = _argv[0] if _argv else ''
    _banderas, _pos, _desconocidas = _parse_argv(_argv[1:])
    if _desconocidas:
        sys.stderr.write(f'argumento no reconocido: {_desconocidas[0]} (usa --si/--proyecto/--sesion)\n')
        sys.exit(1)

    if _modo in ('--arranque', '--herramienta', '--fin'):
        _STDIN = rutas.leer_stdin()  # estos SÍ necesitan tool_name/tool_input además de proj (§1)
    else:
        _STDIN = rutas.leer_stdin_si_hace_falta(_argv[1:])
    proj, mem = rutas.resolver(_argv[1:], _STDIN)

    def _sid_diagnostico():
        return _pos[0] if _pos else (_banderas.get('sesion') or _STDIN.get('session_id') or _sesion_actual(mem))

    if _modo == '--arranque':
        sid = _STDIN.get('session_id'); tp = _STDIN.get('transcript_path'); cwd = _STDIN.get('cwd')
        if sid and rutas.es_mio(tp, cwd, proj):
            arrancar(mem, sid)
        sys.exit(0)

    if _modo == '--herramienta':
        sid = _STDIN.get('session_id'); tp = _STDIN.get('transcript_path'); cwd = _STDIN.get('cwd')
        if not sid or not rutas.es_mio(tp, cwd, proj):
            sys.exit(0)
        tool_name = _STDIN.get('tool_name') or ''
        tool_input = _STDIN.get('tool_input')
        if not isinstance(tool_input, dict):
            tool_input = {}  # sin dato utilizable (p.ej. una cadena o una lista): no se registra, sale con 0
        if tool_name in ('Write', 'Edit', 'NotebookEdit'):
            ruta = tool_input.get('file_path') or tool_input.get('notebook_path')
            if ruta:
                registrar_escritura(mem, sid, ruta)
        elif tool_name in ('Bash', 'PowerShell'):
            registrar_comando(mem, sid, str(tool_input.get('command') or ''))
        sys.exit(0)

    if _modo == '--fin':
        sid = _STDIN.get('session_id'); tp = _STDIN.get('transcript_path'); cwd = _STDIN.get('cwd')
        if sid and rutas.es_mio(tp, cwd, proj):
            txt = resumen_stop(mem, sid)
            if txt:
                print(txt)
        sys.exit(0)

    if _modo == '--informe':
        sid = _sid_diagnostico()
        if not sid:
            sys.stderr.write('huella: no se sabe de que sesion se habla - pasa el id como argumento\n')
            sys.exit(1)
        print(texto_informe(informe(mem, sid)))
        sys.exit(0)

    if _modo == '--limpiar':
        sid = _sid_diagnostico()
        if not sid:
            sys.stderr.write('huella: no se sabe de que sesion se habla - pasa el id como argumento\n')
            sys.exit(1)
        print(limpiar(mem, sid, confirmar=bool(_banderas.get('si'))))
        sys.exit(0)

    sys.stderr.write('uso: huella.py --arranque | --herramienta | --fin | --informe [id] | --limpiar [id] [--si]\n')
    sys.exit(1)
