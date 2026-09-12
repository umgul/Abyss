# -*- coding: utf-8 -*-
"""Cuerpo: el hardware de la máquina donde se ejecuta, con normal propia.

Seis canales, cada uno en su propia función (`leer_cpu`, `leer_ram_libre`,
`leer_disco_libre`, `leer_gpu`, `leer_bateria` — vram y temperatura de la misma llamada a
`nvidia-smi`), por el instrumento nativo de Windows/Linux/macOS. Canal ausente o que
falla: `None`, nunca 0 (un 0% real y "sin instrumento" no son la misma información).

Arranque en frío (ESPECIFICACION.md §2.2): cada medida se apunta en `mem/cuerpo.jsonl`
(línea JSON, ts + los seis canales); con `UMBRAL_FRIO` (8) medidas previas con dato, ese
canal se lee contra sus propios cuantiles p5/p50/p95 — con menos, «sin vara todavía»,
siempre contra el historial ANTERIOR a la medida actual.

Ganchos (los registra `instalar.py`, no este módulo): `--arranque` (SessionStart) imprime
la medida; `--despertar` (UserPromptSubmit) solo si algún canal sale de su p5–p95 propio,
y solo mide, nunca ordena nada. Ambos callan si `rutas.es_mio()` no reconoce el proyecto.
CLI manual: `python cuerpo.py [--historial [n]] [--json]`.

Sin red: ningún canal ni gancho sale de la máquina. No toca `rutas.resolver()` ni stdin
al importarse (funciones puras, sin lanzar subproceso desde una prueba); solo `__main__`
resuelve `proj`/`mem`, siempre por `rutas.resolver()` (§1 ESPECIFICACION.md), nunca
`dirname(__file__)`.
"""
import sys
try:                       # la consola de Windows y la salida tienen que hablar
    from . import consola  # el mismo idioma: ver abyss/consola.py
except ImportError:
    import consola
consola.preparar()
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
    """% de uso de CPU ahora mismo. Windows: PowerShell sobre `Win32_Processor`, con
    `wmic` de respaldo si PowerShell falla. Linux/macOS: `os.getloadavg()[0]` entre
    `os.cpu_count()` — carga media reciente por núcleo, no un % instantáneo. Sin
    instrumento: `None`, nunca 0."""
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
    """Envoltorio perezoso de MEMORYSTATUSEX: se define solo si `leer_ram_libre()` la
    necesita, para no cargar la estructura en un guion que también corre en
    Linux/macOS."""
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
    """RAM libre en MB. Windows: `GlobalMemoryStatusEx`. Linux: `/proc/meminfo`
    (`MemAvailable`, o `MemFree` si el kernel no lo trae). macOS: `vm_stat` (páginas
    libres + inactivas por su propio tamaño de página). Sin instrumento: `None`."""
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
    """(vram_libre_MiB, temperatura_gpu) de una llamada a `nvidia-smi --query-gpu=...`
    (primera GPU si hay varias). Sin `nvidia-smi` en el PATH: `(None, None)` — nunca 0,
    que sería indistinguible de una GPU llena de verdad."""
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
    """(porcentaje, cargando) de la batería. Windows: `Win32_Battery` (`BatteryStatus`
    6/7/8/9 = cargando). Linux: `/sys/class/power_supply/BAT*/{capacity,status}`. macOS:
    `pmset -g batt`. Sin batería o sin instrumento: `(None, None)`."""
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
    """Texto del valor de `canal`, con coma decimal (castellano). Sin agrupación de
    miles: ningún canal de `cuerpo.py` llega a esa magnitud, así que no hace falta
    `infografia.formatear_numero()` (que sí agrupa) y así no se acopla un módulo con el
    otro."""
    if v is None:
        return 'sin dato'
    _, div, unidad, dec = CANAL_INFO[canal]
    txt = f'{v / div:.{dec}f}'.replace('.', ',')
    if not con_unidad:
        return txt
    return f'{txt}{unidad}' if unidad == '%' else f'{txt} {unidad}'


def evaluar(medida, hist_previo):
    """[(canal, valor, 'p5'|'p95', límite)] de los canales de `medida` fuera de su
    p5–p95 sobre `hist_previo` (el historial ANTERIOR, nunca incluyéndola). Un canal
    sin dato o sin vara todavía no entra en la lista. Lista vacía = silencio del
    gancho de prompt."""
    salidas = []
    for canal in ORDEN_CANALES:
        v = medida.get(canal)
        if v is None or canal == 'bateria_pct':
            # la batería fluctúa por diseño entre "cargando" y "descargando": su propio
            # p5-p95 no dice nada útil del estado normal (bajaría cada vez que se
            # desconecta el cargador). Se muestra en el arranque, no se vigila aquí.
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
        # la vara de cada medida se calcula SIEMPRE contra el historial ANTERIOR a ella:
        # se pasa `hist_completo[:offset+i]`, no `[]`, para no perder la vara ya
        # existente del proyecto en cada fila listada.
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
