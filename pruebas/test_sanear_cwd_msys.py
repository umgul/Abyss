"""`rutas._sanear_cwd()` debe traducir rutas MSYS/Cygwin (`/c/...`,
`/cygdrive/c/...`) igual que las rutas Windows, pero SOLO en Windows (`os.name ==
'nt'`) — `rutas.py` se importa aquí directamente, sin subprocess."""
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
        # ruta POSIX real (no de una unidad Windows): no empieza por una sola letra,
        # así que no debe alterarse.
        original = '/home/alguien/proyecto'
        self.assertEqual(rutas._normalizar_estilo_posix_de_windows(original), original)


class SanearCwdSoloTraduceEnWindows(unittest.TestCase):
    def test_en_windows_sigue_traduciendo_una_letra_de_unidad(self):
        with mock.patch.object(rutas.os, 'name', 'nt'):
            self.assertEqual(rutas._normalizar_estilo_posix_de_windows('/n/repo'), 'N:\\repo')
            self.assertEqual(rutas._sanear_cwd('/n/repo'), rutas._sanear_cwd(r'N:\repo'))

    def test_en_unix_no_traduce_un_punto_de_montaje_de_una_letra(self):
        # en una máquina Unix con un montaje real de una letra (/n/...), Claude Code
        # sanea ese cwd como '-n-repo' sin traducir: traducirlo aquí daría dos
        # carpetas de memoria para el mismo proyecto.
        with mock.patch.object(rutas.os, 'name', 'posix'):
            self.assertEqual(rutas._normalizar_estilo_posix_de_windows('/n/repo'), '/n/repo')
            self.assertEqual(rutas._sanear_cwd('/n/repo'), '-n-repo')
            self.assertEqual(rutas._sanear_cwd('/opt/app'), '-opt-app')


if __name__ == '__main__':
    unittest.main()
