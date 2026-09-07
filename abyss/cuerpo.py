# -*- coding: utf-8 -*-
"""Cuerpo: el hardware de la máquina donde corro, con normal propia.

Seis canales, cada uno en SU PROPIA función de lectura (para poder simular cada
instrumento por separado en las pruebas, con `unittest.mock.patch`, sin tocar los
demás):

    leer_cpu()          % de uso de CPU ahora mismo.
    leer_ram_libre()     RAM libre, en MB.
    leer_disco_libre(mem) GB libres en el disco que contiene `mem` (`shutil.disk_usage`,
                          biblioteca estándar: no hace falta comando externo).
    leer_gpu()           (vram_libre_MiB, temperatura_gpu) de UNA sola llamada a
                          `nvidia-smi --query-gpu=memory.used,memory.total,temperature.gpu
                          --format=csv,noheader,nounits` — vram y temperatura salen del
                          mismo comando, así que comparten función. Sin `nvidia-smi`
                          instalado (o sin GPU NVIDIA): `(None, None)`.
    leer_bateria()        (porcentaje, cargando) de la batería. Sin batería (equipo de
                          sobremesa) o sin instrumento: `(None, None)`.

Windows: RAM por `ctypes` (`GlobalMemoryStatusEx`); CPU por PowerShell
(`Get-CimInstance Win32_Processor`, media de `LoadPercentage`) con `wmic` de
respaldo si PowerShell falla; batería por PowerShell sobre `Win32_Battery`.
Linux: `/proc/meminfo` (RAM), `os.getloadavg()`/`/proc/loadavg` (CPU),
`/sys/class/power_supply/BAT*` (batería). macOS: `vm_stat` (RAM), `os.getloadavg()`
(CPU), `pmset -g batt` (batería). CUALQUIER instrumento ausente o que falle
devuelve `None` (nunca 0: un 0% de batería medido de verdad y una batería que no
existe no son la misma información) — fail-closed, [[verificar-antes-de-construir]].

Normal propia (arranque en frío, ESPECIFICACION.md §2.2): cada medida se apunta en
`mem/cuerpo.jsonl` (una línea JSON por medida: ts + los seis canales). Con al menos
`UMBRAL_FRIO` (8) medidas PREVIAS con dato en un canal, ese canal se lee contra sus
propios cuantiles (p5, p50, p95); con menos, la línea dice «sin vara todavía
(n=…)» y no se inventa ningún corte. La vara de cada medida se calcula SIEMPRE
contra el historial ANTERIOR a ella (nunca incluyéndose a sí misma).

Ganchos (registrados por `instalar.py`, no por este módulo):
    --arranque  (SessionStart): imprime `{"hookSpecificOutput": {...}}` con una
                línea `[cuerpo] cpu … · ram libre … · disco libre … · vram libre …
                · temp gpu … · batería …`.
    --despertar (UserPromptSubmit): SOLO imprime algo si algún canal de la medida
                de AHORA cae fuera de su p5–p95 propio; si todo está dentro de lo
                suyo, silencio total (no hay JSON que imprimir). Nunca ordena nada
                (no cierra procesos, no baja modelos, no sugiere nada): mide, y
                quien lo lea decide.
Los dos ganchos se callan (sin imprimir nada, código 0) si `rutas.es_mio()` no
reconoce el `transcript_path`/`cwd` del JSON de stdin como de este proyecto.

CLI manual: `python cuerpo.py` (una medida, se guarda, se imprime la línea),
`--historial [n]` (últimas n medidas guardadas, 20 por defecto), `--json` (la
salida como JSON en vez de texto; combinable con `--historial`).

Nada de esto sale de la máquina: no hay ninguna llamada de red en todo el módulo.

Diseño deliberado para las pruebas: a diferencia de otros guiones de `abyss/`
(`continuidad.py`, `vigia.py`…) que resuelven `proj`/`mem` nada más importarse,
ESTE módulo no toca `rutas.resolver()` ni stdin al importarse — todas las
funciones de arriba son puras (reciben `mem`/`hist` como argumento) y se pueden
llamar directamente desde una prueba con instrumentos monkeypatcheados, sin
lanzar un subproceso. Solo el bloque `if __name__ == '__main__':` resuelve
`proj`/`mem` y lee stdin, para el uso real como gancho o CLI.

Carpeta de datos: NUNCA `dirname(__file__)`; la resuelve `rutas.resolver()` (§1 de
ESPECIFICACION.md) — solo dentro de `__main__`, ver arriba.
"""
import sys; sys.stdout.reconfigure(encoding="utf-8")
import os
import re
import json
import time
import shutil
import subprocess

try:
    from . import rutas
except ImportError:
    import rutas

UMBRAL_FRIO = 8  # misma vara que propiocepcion.UMBRAL_FRIO (§2.2 ESPECIFICACION.md)

# nombre legible, divisor de escala, unidad, decimales — en el orden en que se muestran
CANAL_INFO = {
    'cpu':            ('cpu',          1,    '%',   0),
    'ram_libre_mb':   ('ram libre',    1024, 'GB',  1),
    'disco_libre_gb': ('disco libre',  1,    'GB',  0),
    'vram_libre_mib': ('vram libre',   1024, 'GiB', 1),
    'temp_gpu':       ('temp gpu',     1,    '°C',  0),
    'bateria_pct':    ('batería',      1,    '%',   0),
}
ORDEN_CANALES = tuple(CANAL_INFO)


# ---------- lectura de instrumentos (una función por instrumento) ----------

def leer_cpu():
    """% de uso de CPU ahora mismo. Windows: PowerShell sobre Win32_Processor
    (media de LoadPercentage entre núcleos/sockets), con `wmic cpu get
    loadpercentage` de respaldo si PowerShell falla. Linux/macOS:
    `os.getloadavg()[0]` (carga a 1 minuto) entre `os.cpu_count()`, como
    aproximación declarada — no es un % de uso instantáneo tal cual, es carga
    media reciente por núcleo. Sin instrumento: None, nunca 0."""
    if os.name == 'nt':
        try:
            r = subprocess.run(
                ['powershell', '-NoProfile', '-Command',
                 '(Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average'],
                capture_output=True, text=True, timeout=5)
            v = r.stdout.strip()
            if v:
                return float(v)
        except Exception:
            pass
        try:
            r = subprocess.run(['wmic', 'cpu', 'get', 'loadpercentage'], capture_output=True, text=True, timeout=5)
            for linea in r.stdout.splitlines():
                linea = linea.strip()
                if linea.isdigit():
                    return float(linea)
        except Exception:
            pass
        return None
    try:
        carga1 = os.getloadavg()[0]
        n = os.cpu_count() or 1
        return round(100 * carga1 / n, 1)
    except Exception:
        return None


class _MemoryStatusEx:
    """Envoltorio perezoso de MEMORYSTATUSEX: importar `ctypes` cuesta poco pero
    definir la estructura a nivel de módulo en un guion que también corre en
    Linux/macOS no aporta nada; se define solo si `leer_ram_libre()` la necesita."""
    _cls = None

    @classmethod
    def estructura(cls):
        if cls._cls is None:
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ('dwLength', ctypes.c_ulong), ('dwMemoryLoad', ctypes.c_ulong),
                    ('ullTotalPhys', ctypes.c_ulonglong), ('ullAvailPhys', ctypes.c_ulonglong),
                    ('ullTotalPageFile', ctypes.c_ulonglong), ('ullAvailPageFile', ctypes.c_ulonglong),
                    ('ullTotalVirtual', ctypes.c_ulonglong), ('ullAvailVirtual', ctypes.c_ulonglong),
                    ('sullAvailExtendedVirtual', ctypes.c_ulonglong),
                ]
            cls._cls = MEMORYSTATUSEX
        return cls._cls


def leer_ram_libre():
    """RAM libre en MB. Windows: `ctypes.windll.kernel32.GlobalMemoryStatusEx`
    (`ullAvailPhys`). Linux: `/proc/meminfo` (`MemAvailable`, o `MemFree` si el
    kernel no trae `MemAvailable`). macOS: `vm_stat` (páginas libres + inactivas
    por el tamaño de página que el propio `vm_stat` declara). Sin instrumento:
    None."""
    if os.name == 'nt':
        try:
            import ctypes
            Cls = _MemoryStatusEx.estructura()
            m = Cls()
            m.dwLength = ctypes.sizeof(Cls)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
                return m.ullAvailPhys / (1024 * 1024)
        except Exception:
            pass
        return None
    try:
        info = {}
        with open('/proc/meminfo', encoding='utf-8') as fh:
            for linea in fh:
                clave, _, valor = linea.partition(':')
                info[clave.strip()] = valor.strip()
        if 'MemAvailable' in info:
            return float(info['MemAvailable'].split()[0]) / 1024
        if 'MemFree' in info:
            return float(info['MemFree'].split()[0]) / 1024
    except Exception:
        pass
    try:
        r = subprocess.run(['vm_stat'], capture_output=True, text=True, timeout=5)
        tam = 4096
        m = re.search(r'page size of (\d+) bytes', r.stdout)
        if m:
            tam = int(m.group(1))
        libres = 0
        for campo in ('Pages free', 'Pages inactive'):
            mm = re.search(re.escape(campo) + r':\s+(\d+)\.', r.stdout)
            if mm:
                libres += int(mm.group(1))
        if libres:
            return libres * tam / (1024 * 1024)
    except Exception:
        pass
    return None


def leer_disco_libre(mem):
    """GB libres en el disco que contiene el directorio `mem` (`shutil.disk_usage`,
    biblioteca estándar — no hace falta comando externo en ningún sistema). None
    si `mem` no existe o no se puede consultar."""
    try:
        return shutil.disk_usage(mem).free / (1024 ** 3)
    except Exception:
        return None


def leer_gpu():
    """(vram_libre_MiB, temperatura_gpu) de UNA llamada a `nvidia-smi
    --query-gpu=memory.used,memory.total,temperature.gpu --format=csv,noheader,nounits`
    (primera GPU si hay varias). Sin `nvidia-smi` en el PATH (no está instalado o
    no hay GPU NVIDIA): `(None, None)` — nunca 0, que sería indistinguible de una
    GPU llena de verdad."""
    try:
        r = subprocess.run(
            ['nvidia-smi', '--query-gpu=memory.used,memory.total,temperature.gpu',
             '--format=csv,noheader,nounits'],
            capture_output=True, text=True, timeout=5)
        if r.returncode != 0 or not r.stdout.strip():
            return None, None
        primera = r.stdout.strip().splitlines()[0]
        usada, total, temp = (float(x.strip()) for x in primera.split(','))
        return total - usada, temp
    except Exception:
        return None, None


def leer_bateria():
    """(porcentaje, cargando) de la batería. Windows: PowerShell sobre
    `Win32_Battery` (`EstimatedChargeRemaining`, `BatteryStatus` — 6/7/8/9 son los
    cuatro estados de "cargando" de WMI). Linux:
    `/sys/class/power_supply/BAT*/{capacity,status}`. macOS: `pmset -g batt`. Sin
    batería (equipo de sobremesa) o sin instrumento: `(None, None)`."""
    if os.name == 'nt':
        try:
            r = subprocess.run(
                ['powershell', '-NoProfile', '-Command',
                 'Get-CimInstance Win32_Battery | Select-Object -First 1 '
                 'EstimatedChargeRemaining,BatteryStatus | ConvertTo-Json -Compress'],
                capture_output=True, text=True, timeout=5)
            txt = r.stdout.strip()
            if not txt:
                return None, None
            d = json.loads(txt)
            pct = d.get('EstimatedChargeRemaining')
            if pct is None:
                return None, None
            return float(pct), d.get('BatteryStatus') in (6, 7, 8, 9)
        except Exception:
            return None, None
    try:
        base = '/sys/class/power_supply'
        for nombre in sorted(os.listdir(base)):
            if not nombre.startswith('BAT'):
                continue
            d = os.path.join(base, nombre)
            with open(os.path.join(d, 'capacity'), encoding='utf-8') as fh:
                pct = float(fh.read().strip())
            cargando = False
            try:
                with open(os.path.join(d, 'status'), encoding='utf-8') as fh:
                    cargando = fh.read().strip().lower() == 'charging'
            except Exception:
                pass
            return pct, cargando
    except Exception:
        pass
    try:
        r = subprocess.run(['pmset', '-g', 'batt'], capture_output=True, text=True, timeout=5)
        m = re.search(r'(\d+)%', r.stdout)
        if m:
            return float(m.group(1)), ('discharging' not in r.stdout.lower())
    except Exception:
        pass
    return None, None


# ---------- medida, historial, cuantiles (puro: nada de esto toca stdin) ----------

def medir(mem):
    """Una foto del cuerpo AHORA MISMO. Cada canal es independiente: sin su
    instrumento vale `None` (nunca 0)."""
    vram, temp = leer_gpu()
    pct, cargando = leer_bateria()
    return {
        'ts': time.time(),
        'cpu': leer_cpu(),
        'ram_libre_mb': leer_ram_libre(),
        'disco_libre_gb': leer_disco_libre(mem),
        'vram_libre_mib': vram,
        'temp_gpu': temp,
        'bateria_pct': pct,
        'bateria_cargando': cargando,
    }


def _ruta_historial(mem):
    return os.path.join(mem, 'cuerpo.jsonl')


def historial(mem):
    """Todas las medidas guardadas en `mem/cuerpo.jsonl`, en orden. `[]` si el
    fichero no existe todavía (primera vez que corre esta pieza en el proyecto)."""
    out = []
    try:
        with open(_ruta_historial(mem), encoding='utf-8') as fh:
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


def guardar(mem, medida):
    """Añade `medida` a `mem/cuerpo.jsonl` (una línea JSON más; nunca se reescribe
    el historial anterior)."""
    os.makedirs(mem, exist_ok=True)
    with open(_ruta_historial(mem), 'a', encoding='utf-8') as fh:
        fh.write(json.dumps(medida, ensure_ascii=False) + '\n')


def cuantiles(canal, hist):
    """(p5, p50, p95, n) de `canal` sobre las medidas de `hist` que traen dato en
    ese canal (`None` no cuenta ni como medida ni como cero). `None` si hay menos
    de `UMBRAL_FRIO` medidas con dato — arranque en frío, §2.2: sin vara todavía,
    no se inventa un corte sobre un puñado de puntos."""
    vals = sorted(m[canal] for m in hist if m.get(canal) is not None)
    n = len(vals)
    if n < UMBRAL_FRIO:
        return None

    def _p(q):
        i = min(n - 1, max(0, round(q * (n - 1))))
        return vals[i]

    return _p(0.05), _p(0.50), _p(0.95), n


def _valor_fmt(canal, v, con_unidad=True):
    """Texto del valor de `canal`, con COMA decimal (castellano — T2.3 lo pide
    con el ejemplo literal «ram libre 9,8 GB»; `infografia.py` ya trae `--es`/
    `--no-es` para esto mismo en otra pieza de la misma tanda). Sin
    agrupación de miles: ningún canal de `cuerpo.py` llega a esa magnitud, así
    que un `.` -> `,` directo sobre el número ya formateado basta y no hace
    falta tirar de `infografia.formatear_numero()` (que sí agrupa miles) para
    no acoplar un módulo con el otro."""
    if v is None:
        return 'sin dato'
    _, div, unidad, dec = CANAL_INFO[canal]
    txt = f'{v / div:.{dec}f}'.replace('.', ',')
    if not con_unidad:
        return txt
    return f'{txt}{unidad}' if unidad == '%' else f'{txt} {unidad}'


def evaluar(medida, hist_previo):
    """[(canal, valor, 'p5'|'p95', límite)] de los canales de `medida` que caen
    FUERA de su p5–p95 medido sobre `hist_previo` (el historial ANTERIOR a esta
    medida, nunca incluyéndola). Un canal sin dato, o sin vara todavía (menos de
    `UMBRAL_FRIO` medidas previas con dato en ESE canal), no puede violar nada:
    no entra en la lista. Lista vacía = silencio del gancho de prompt."""
    salidas = []
    for canal in ORDEN_CANALES:
        v = medida.get(canal)
        if v is None or canal == 'bateria_pct':
            # la batería fluctúa por diseño entre "cargando" y "descargando": un
            # p5-p95 de su propio historial no dice nada útil de su estado normal
            # (bajaría de p5 cada vez que se desconecta el cargador, algo normal,
            # no una anomalía). Se muestra en el arranque, no se vigila aquí.
            continue
        c = cuantiles(canal, hist_previo)
        if not c:
            continue
        p5, p50, p95, _n = c
        if v < p5:
            salidas.append((canal, v, 'p5', p5))
        elif v > p95:
            salidas.append((canal, v, 'p95', p95))
    return salidas


def texto_arranque(medida, hist_previo):
    """Línea `[cuerpo] …` para el gancho SessionStart: un valor por canal, con
    `(p50 tuyo …)` cuando ese canal ya tiene vara propia. Si el historial entero
    tiene menos de `UMBRAL_FRIO` medidas, ningún canal lleva cuantil y la línea
    termina en «sin vara todavía (n=…)» — una sola vez, no por canal."""
    n = len(hist_previo)
    con_vara_global = n >= UMBRAL_FRIO
    partes = []
    for canal in ORDEN_CANALES:
        v = medida.get(canal)
        nombre = CANAL_INFO[canal][0]
        txt = _valor_fmt(canal, v)
        if canal == 'bateria_pct' and v is not None:
            txt += ' cargando' if medida.get('bateria_cargando') else ' sin cargar'
        if con_vara_global and v is not None:
            c = cuantiles(canal, hist_previo)
            if c:
                _p5, p50, _p95, _n = c
                txt += f' (p50 tuyo {_valor_fmt(canal, p50, con_unidad=False)})'
        partes.append(f'{nombre} {txt}')
    linea = '[cuerpo] ' + ' · '.join(partes)
    if not con_vara_global:
        linea += f' · sin vara todavía (n={n})'
    return linea


def texto_despertar(medida, hist_previo):
    """Línea `[cuerpo] …` para el gancho UserPromptSubmit: SOLO si `evaluar()`
    encuentra algo fuera de rango; cadena vacía (silencio) si no."""
    salidas = evaluar(medida, hist_previo)
    if not salidas:
        return ''
    partes = []
    for canal, v, extremo, limite in salidas:
        nombre = CANAL_INFO[canal][0]
        etiqueta = 'por debajo de tu p5' if extremo == 'p5' else 'por encima de tu p95'
        partes.append(f'{nombre} {_valor_fmt(canal, v)}: {etiqueta} ({_valor_fmt(canal, limite, con_unidad=False)})')
    return '[cuerpo] ' + ' · '.join(partes)


_BANDERAS_VALIDAS = ('--arranque', '--despertar', '--historial', '--json', '--proyecto')
_USO_BANDERAS = 'usa --arranque/--despertar/--historial/--json/--proyecto'


def _validar_argv(argv):
    """Rechaza con código 1 (ESPECIFICACION.md §3: nunca tragarse en silencio un
    argumento que no encaja) cualquier `--bandera` fuera de `_BANDERAS_VALIDAS` y
    cualquier posicional que no sea el `n` de `--historial`. Devuelve la lista de
    posicionales (excluyendo el valor que ya consume `--proyecto <valor>`)."""
    valor_de_proyecto = None
    if '--proyecto' in argv:
        i = argv.index('--proyecto')
        if i + 1 < len(argv):
            valor_de_proyecto = i + 1
    for i, a in enumerate(argv):
        if i == valor_de_proyecto:
            continue
        if a.startswith('--') and a not in _BANDERAS_VALIDAS:
            print(f'argumento no reconocido: {a} ({_USO_BANDERAS})')
            sys.exit(1)
    posicionales = [a for i, a in enumerate(argv) if i != valor_de_proyecto and not a.startswith('--')]
    modo = argv[0] if argv and argv[0].startswith('--') and argv[0] not in ('--json',) else None
    if posicionales and modo != '--historial':
        print(f'argumento no reconocido: {posicionales[0]} ({_USO_BANDERAS})')
        sys.exit(1)
    if modo == '--historial' and len(posicionales) > 1:
        print(f'argumento no reconocido: {posicionales[1]} ({_USO_BANDERAS})')
        sys.exit(1)
    return posicionales


if __name__ == '__main__':
    argv = sys.argv[1:]
    _posicionales = _validar_argv(argv)
    modo = argv[0] if argv and argv[0].startswith('--') and argv[0] not in ('--json',) else None

    if modo in ('--arranque', '--despertar'):
        _STDIN = rutas.leer_stdin()
    else:
        _STDIN = rutas.leer_stdin_si_hace_falta(argv)
    proj, mem = rutas.resolver(argv, _STDIN)

    if modo == '--arranque':
        tp = _STDIN.get('transcript_path'); cwd = _STDIN.get('cwd')
        if not rutas.es_mio(tp, cwd, proj):
            sys.exit(0)
        hist_previo = historial(mem)
        medida = medir(mem)
        guardar(mem, medida)
        txt = texto_arranque(medida, hist_previo)
        print(json.dumps({'hookSpecificOutput': {'hookEventName': 'SessionStart', 'additionalContext': txt}},
                          ensure_ascii=False))
        sys.exit(0)

    if modo == '--despertar':
        tp = _STDIN.get('transcript_path'); cwd = _STDIN.get('cwd')
        if not rutas.es_mio(tp, cwd, proj):
            sys.exit(0)
        hist_previo = historial(mem)
        medida = medir(mem)
        guardar(mem, medida)
        txt = texto_despertar(medida, hist_previo)
        if txt:
            print(json.dumps({'hookSpecificOutput': {'hookEventName': 'UserPromptSubmit', 'additionalContext': txt}},
                              ensure_ascii=False))
        sys.exit(0)

    if modo == '--historial':
        if _posicionales:
            try:
                n = int(_posicionales[0])
            except ValueError:
                print(f'--historial necesita un número, no "{_posicionales[0]}"')
                sys.exit(1)
        else:
            n = 20
        hist_completo = historial(mem)
        hist = hist_completo[-n:] if n > 0 else []
        # la vara de cada medida se calcula SIEMPRE contra el historial ANTERIOR a
        # ella (docstring de texto_arranque): pasar [] aquí hacía que TODAS las filas
        # mintieran «sin vara todavía (n=0)» aunque el proyecto sí tuviera vara.
        offset = len(hist_completo) - len(hist)
        if '--json' in argv:
            print(json.dumps(hist, ensure_ascii=False, indent=1))
        elif not hist:
            print(f'sin medidas todavía en {mem}')
        else:
            for i, m in enumerate(hist):
                marca = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(m.get('ts', 0)))
                hist_previo = hist_completo[:offset + i]
                print(f'{marca}  {texto_arranque(m, hist_previo)}')
        sys.exit(0)

    # uso manual sin bandera de gancho: una medida, se guarda, se imprime
    hist_previo = historial(mem)
    medida = medir(mem)
    guardar(mem, medida)
    if '--json' in argv:
        cuantiles_actuales = {c: cuantiles(c, hist_previo) for c in ORDEN_CANALES}
        print(json.dumps({'medida': medida, 'cuantiles': cuantiles_actuales}, ensure_ascii=False, indent=1))
    else:
        print(texto_arranque(medida, hist_previo))
