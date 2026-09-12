"""La suite no debe dejar nada en el `~/.claude/projects/` real: lo que resuelva
`rutas.resolver()` durante las pruebas va a directorios temporales o a un HOME desechable."""
import os
from pathlib import Path

import pytest

_PROYECTOS = Path.home() / '.claude' / 'projects'


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
