"""Ayudas comunes para las pruebas de Abyss (ESPECIFICACION.md §6).

Los guiones de `abyss/` resuelven datos con `rutas.resolver()`, por eso aquí se
invocan siempre por subprocess, nunca importados directamente en el proceso."""
import sys
import os
import json
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime, timedelta, timezone

RAIZ = Path(__file__).resolve().parent.parent   # raíz del repo (junto a abyss/ e instalar.py)
PKG = RAIZ / 'abyss'


def script(nombre):
    """Ruta absoluta a `nombre` dentro de `abyss/` (p. ej. 'continuidad.py')."""
    return PKG / nombre


def nuevo_proyecto():
    """Directorio temporal que hace de `proj`: los `.jsonl` van directamente dentro
    (como en `~/.claude/projects/<proyecto>/`), y `memory/` es una subcarpeta suya."""
    return Path(tempfile.mkdtemp(prefix='abyss_proj_'))


def entorno(proj, **extra):
    """Copia de `os.environ` con `ABYSS_PROYECTO` apuntando a `proj` (orden 4 de
    `rutas.resolver()`): así cualquier guion resuelve su `mem` sin depender de
    stdin ni de `--proyecto`. `extra` añade o sobreescribe otras variables."""
    env = dict(os.environ)
    env['ABYSS_PROYECTO'] = str(proj)
    env.update(extra)
    return env


def ejecutar(ruta_script, args, env, entrada='', cwd=None, timeout=30):
    """Lanza `python <ruta_script> <args...>` con `entrada` como stdin (siempre algo,
    por defecto '', para que `rutas.leer_stdin()` no bloquee). `errors='replace'`
    evita un `UnicodeDecodeError` si el stderr trae un carácter no-ASCII (`§`) sobre la cp1252 de Windows."""
    return subprocess.run(
        [sys.executable, str(ruta_script)] + [str(a) for a in args],
        input=entrada, capture_output=True, text=True, encoding='utf-8', errors='replace',
        env=env, cwd=cwd, timeout=timeout,
    )


# ---------- líneas de transcript sintéticas ----------

def usuario(texto, ts=None):
    d = {'type': 'user', 'message': {'content': texto}, 'isMeta': False}
    if ts:
        d['timestamp'] = ts
    return d


def usuario_tool_result(contenido, ts=None):
    """Una línea `user` que en realidad es el RESULTADO de una herramienta (bloque
    `tool_result` en el content), tal como las lee `vigia.leer_turno()`."""
    d = {'type': 'user', 'message': {'content': [{'type': 'tool_result', 'content': contenido}]}}
    if ts:
        d['timestamp'] = ts
    return d


def asistente_texto(texto, ts=None, modelo=None):
    msg = {'content': [{'type': 'text', 'text': texto}]}
    if modelo:
        msg['model'] = modelo
    d = {'type': 'assistant', 'message': msg}
    if ts:
        d['timestamp'] = ts
    return d


def asistente_tool_use(nombre, entrada_dict, ts=None):
    d = {'type': 'assistant', 'message': {'content': [{'type': 'tool_use', 'name': nombre, 'input': entrada_dict}]}}
    if ts:
        d['timestamp'] = ts
    return d


def escribir_jsonl(ruta, lineas):
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, 'w', encoding='utf-8') as fh:
        for d in lineas:
            fh.write(json.dumps(d, ensure_ascii=False) + '\n')
    return ruta


def sesion_simple(ruta, frases, inicio=None):
    """Sesión sintética mínima: una línea `user` por frase, separadas un minuto —
    basta para que `propiocepcion.medir()` cuente `turnos_usuario > 0`."""
    inicio = inicio or datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    lineas = [usuario(f, (inicio + timedelta(minutes=i)).strftime('%Y-%m-%dT%H:%M:%SZ'))
              for i, f in enumerate(frases)]
    return escribir_jsonl(ruta, lineas)
