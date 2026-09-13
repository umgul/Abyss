"""La suite no deja rastro en la máquina: nada en el `~/.claude/projects/` real, y todo lo
temporal (suyo y de los subprocesos que lanza) en una carpeta propia que se borra al acabar."""
import os
import shutil
import tempfile
import time
from pathlib import Path

import pytest

_PROYECTOS = Path.home() / '.claude' / 'projects'

# Antes de que ninguna prueba importe nada: `tempfile` y los subprocesos (que heredan TEMP/TMP)
# crean sus carpetas aquí dentro, y no en el temporal del sistema.
_TEMPORAL = tempfile.mkdtemp(prefix='abyss_suite_')
os.environ['TEMP'] = os.environ['TMP'] = os.environ['TMPDIR'] = _TEMPORAL
tempfile.tempdir = _TEMPORAL


def _entradas():
    try:
        return set(os.listdir(_PROYECTOS))
    except OSError:
        return set()


@pytest.fixture(scope='session', autouse=True)
def _proyectos_reales_intactos():
    antes = _entradas()
    yield
    nuevas = sorted(_entradas() - antes)
    assert not nuevas, f'la suite creó carpetas en {_PROYECTOS}: {nuevas}'


@pytest.fixture(scope='session', autouse=True)
def _temporal_de_la_suite():
    yield
    for _ in range(20):  # en Windows un proceso que acaba de salir puede tardar en soltar sus ficheros
        shutil.rmtree(_TEMPORAL, ignore_errors=True)
        if not os.path.isdir(_TEMPORAL):
            break
        time.sleep(0.25)
