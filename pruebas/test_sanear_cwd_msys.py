"""`rutas._sanear_cwd` (fallo 6-sep, "engaña"): todas las `skills/*/SKILL.md` mandan
`--proyecto "$(pwd)"`. MEDIDO con HOME falso: en la Bash que trae la herramienta Bash
en Windows, `pwd` devuelve `/c/Proyectos/Mi App` (no `C:\\Proyectos\\Mi App`), y sin
traducir esa forma antes de sanear, `--proyecto "C:\\Proyectos\\Mi App"` resolvía
`~/.claude/projects/C--Proyectos-Mi-App` mientras que `--proyecto "/c/Proyectos/Mi
App"` resolvía `~/.claude/projects/-c-Proyectos-Mi-App` — DOS carpetas de memoria
distintas para el MISMO proyecto: la orden documentada leía y escribía en una
memoria fantasma vacía.

`rutas.py` no hace `rutas.resolver()` a nivel de módulo (solo dentro de funciones),
así que se importa DIRECTAMENTE aquí (ver docstring de `ayudas.py`).

SEGUNDA VUELTA (6-sep, revisor Opus, "roza"): la traducción de arriba se aplicaba
en CUALQUIER sistema, sin comprobar que tuviera sentido — en una máquina Unix con
un punto de montaje real de una sola letra bajo `/` (`/n`, `/e`, `/d`: habituales
en granjas y NFS) trasladaba el MISMO fallo que se quería cerrar, en la otra
dirección: Claude Code sanearía `/n/repo` como `-n-repo` (real, sin traducir) pero
`rutas._sanear_cwd()` lo saneaba como `N--repo` (traducido) — dos carpetas de
memoria para el mismo proyecto. `SanearCwdSoloTraduceEnWindows` de abajo mide la
función tal como es, PURA: no hace falta estar en Linux de verdad, basta con
simular `os.name` (`unittest.mock.patch.object`), ya que la función solo mira esa
variable para decidir si traduce."""
import sys
import os
from pathlib import Path
from unittest import mock
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'abyss'))
import unittest

import rutas


class SanearCwdEntiendeMsysYCygwin(unittest.TestCase):
    def test_msys_git_bash_resuelve_igual_que_windows(self):
        windows = rutas._sanear_cwd(r'C:\Proyectos\Mi App')
        msys = rutas._sanear_cwd('/c/Proyectos/Mi App')
        self.assertEqual(windows, msys,
                          f'"$(pwd)" en Git Bash (/c/...) debe sanear IGUAL que la ruta Windows: '
                          f'{windows!r} != {msys!r}')

    def test_cygwin_resuelve_igual_que_windows(self):
        windows = rutas._sanear_cwd(r'C:\Proyectos\Mi App')
        cygwin = rutas._sanear_cwd('/cygdrive/c/Proyectos/Mi App')
        self.assertEqual(windows, cygwin)

    def test_raiz_de_unidad_sin_resto(self):
        # /c solo (sin subcarpeta): no debe reventar ni dejar un resto sin traducir
        self.assertEqual(rutas._sanear_cwd('/c'), rutas._sanear_cwd('C:'))

    def test_ruta_posix_normal_no_se_toca(self):
        # una ruta POSIX real (no de una unidad Windows) no debe alterarse por esta
        # traducción: /home/alguien/proyecto no empieza por una sola letra de unidad
        original = '/home/alguien/proyecto'
        self.assertEqual(rutas._normalizar_estilo_posix_de_windows(original), original)


class SanearCwdSoloTraduceEnWindows(unittest.TestCase):
    def test_en_windows_sigue_traduciendo_una_letra_de_unidad(self):
        with mock.patch.object(rutas.os, 'name', 'nt'):
            self.assertEqual(rutas._normalizar_estilo_posix_de_windows('/n/repo'), 'N:\\repo')
            self.assertEqual(rutas._sanear_cwd('/n/repo'), rutas._sanear_cwd(r'N:\repo'))

    def test_en_unix_no_traduce_un_punto_de_montaje_de_una_letra(self):
        # con el fallo: esto daba 'N--repo' (traducido) en vez de '-n-repo' (real),
        # que es como Claude Code sanearía de verdad ese cwd en una máquina Unix con
        # un montaje /n/... — dos carpetas de memoria para el mismo proyecto.
        with mock.patch.object(rutas.os, 'name', 'posix'):
            self.assertEqual(rutas._normalizar_estilo_posix_de_windows('/n/repo'), '/n/repo')
            self.assertEqual(rutas._sanear_cwd('/n/repo'), '-n-repo')
            self.assertEqual(rutas._sanear_cwd('/opt/app'), '-opt-app')


if __name__ == '__main__':
    unittest.main()
