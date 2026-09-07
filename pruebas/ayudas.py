"""Ayudas comunes para las pruebas de Abyss (ESPECIFICACION.md §6).

No es un fichero de pruebas (no empieza por `test_`): `unittest discover` no lo
recoge como caso, pero cada `test_*.py` lo importa para no repetir lo mismo:

- `nuevo_proyecto()`: un directorio temporal que hace de `proj` — los transcripts
  `.jsonl` van DIRECTAMENTE dentro (como hace Claude Code de verdad), y `memory/`
  es una subcarpeta suya. Así `dirname(transcript_path) == proj` sin trucos, y
  `rutas.es_mio()` acierta solo.
- `entorno(proj)`: copia de `os.environ` con `ABYSS_PROYECTO=proj` (orden 4 de
  `rutas.resolver()`), para los guiones que no reciben `transcript_path` por stdin.
- `ejecutar(...)`: lanza `python <guion> <args>` como lo haría un gancho de Claude
  Code, con `entrada` como stdin — SIEMPRE se pasa algo (por defecto `''`) para
  que el proceso no se quede esperando un stdin real que nunca llega.
- constructores de líneas de transcript sintéticas (`usuario`, `asistente_texto`,
  `asistente_tool_use`, `usuario_tool_result`) y `sesion_simple()` para una sesión
  mínima medible por `propiocepcion.medir()`.

Los guiones de `abyss/` resuelven su carpeta de datos con `rutas.resolver()`
(nunca `dirname(__file__)`, ESPECIFICACION.md §1); por eso aquí NUNCA se importan
esos guiones directamente en el proceso de las pruebas (varios hacen
`rutas.leer_stdin()`/`rutas.resolver()` nada más importarse y podrían abortar el
proceso entero de `unittest`), siempre por subprocess, igual que los invocaría un
gancho real.
"""
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
    """Directorio temporal que hace de `proj`: los transcripts `.jsonl` sintéticos
    van directamente dentro (igual que Claude Code los deja bajo
    `~/.claude/projects/<proyecto>/`), y `memory/` es una subcarpeta suya."""
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
    """Lanza `python <ruta_script> <args...>`. `entrada` es el stdin (JSON en texto
    del gancho, o '' si el guion no lo necesita) — se pasa siempre algo para que
    `rutas.leer_stdin()` no se quede bloqueado esperando un terminal real.

    `errors='replace'` en la decodificación: cada guion reconfigura SU stdout a
    utf-8, pero no su stderr — un traceback sin capturar (justo lo que una prueba
    de fallo quiere poder inspeccionar) puede salir en el `cp1252` de la consola
    de Windows si lleva algún carácter no-ASCII en el código fuente (p. ej. `§`).
    Sin `errors='replace'` eso revienta el propio `subprocess.run` con un
    `UnicodeDecodeError` ANTES de devolver el `CompletedProcess`, y la prueba que
    quería comprobar el mensaje de error se queda sin poder mirarlo."""
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
