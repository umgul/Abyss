"""`instalar.py` (fallo 6-sep, "roza"): cualquier bandera desconocida caía de largo
hasta `_abrir_ventana()` + `mainloop()`, sin salida — MEDIDO: `python instalar.py
--help` no volvió en 120 s (hubo que localizar el proceso y matarlo), abriendo de
paso una ventana Tk en el escritorio. `__main__` solo miraba `--listar`,
`--instalar`, `--desinstalar` y `--sin-ventana`; cualquier otra cosa (`--help`, un
typo como `--instaler`, o cualquier invocación no interactiva sin banderas) se
tragaba hasta la ventana.

Ahora `argv` se valida ANTES de decidir qué hacer: `-h`/`--help` imprime el uso y
sale con 0; cualquier bandera que no encaje sale con 2 y un mensaje que la nombra
— nunca llega a `_abrir_ventana()`. Las pruebas de subprocess usan un timeout corto
(10 s, muy por debajo de los 120 s medidos) para que un cuelgue real falle rápido
en vez de colgar la propia suite.
"""
import sys
import os
import json
import tempfile
import subprocess
import importlib.util
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import unittest
import ayudas as ay


def _cargar_instalador():
    ruta = ay.RAIZ / 'instalar.py'
    spec = importlib.util.spec_from_file_location('abyss_instalador_bajo_prueba_no_cuelga', str(ruta))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class ValidacionDeArgvDirecta(unittest.TestCase):
    """`_argumento_no_reconocido()` a pelo, sin subprocess: rápido y prueba la
    lógica exacta que decide si se cae a la ventana."""

    def setUp(self):
        self.inst = _cargar_instalador()

    def test_banderas_conocidas_con_su_valor_no_dan_error(self):
        ok = ['--instalar', 'continuidad,vigia', '--settings', 'x.json',
              '--python', 'python3', '--proyecto', '/tmp/x', '--sin-preguntar']
        self.assertIsNone(self.inst._argumento_no_reconocido(ok))

    def test_bandera_desconocida_se_detecta(self):
        err = self.inst._argumento_no_reconocido(['--instaler', 'continuidad'])
        self.assertIsNotNone(err)
        self.assertIn('--instaler', err)

    def test_bandera_con_valor_sin_valor_detras_se_detecta(self):
        err = self.inst._argumento_no_reconocido(['--settings'])
        self.assertIsNotNone(err)
        self.assertIn('--settings', err)

    def test_listar_solo_no_da_error(self):
        self.assertIsNone(self.inst._argumento_no_reconocido(['--listar']))


class InstaladorCliNoSeCuelga(unittest.TestCase):
    """Subprocess de verdad contra `instalar.py`, tal como lo teclearía alguien:
    el fallo real era que el PROCESO no volvía. `--settings` apunta a un fichero
    temporal para no tocar nunca el `~/.claude/settings.json` real de quien corra
    la prueba (regla dura 1 del encargo)."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='abyss_instalador_cli_'))
        self.settings_ruta = self.tmp / 'settings.json'

    def _correr(self, args, timeout=10):
        return subprocess.run(
            [sys.executable, str(ay.RAIZ / 'instalar.py')] + args,
            input='', capture_output=True, text=True, encoding='utf-8', errors='replace',
            timeout=timeout,
        )

    def test_help_sale_rapido_sin_abrir_ventana(self):
        # con el fallo: TimeoutExpired (medido: no volvía ni a los 120 s)
        try:
            r = self._correr(['--help'])
        except subprocess.TimeoutExpired:
            self.fail('instalar.py --help se quedó colgado (el fallo real: caía a '
                      'la ventana Tk sin salida)')
        self.assertEqual(r.returncode, 0, f'stdout={r.stdout!r} stderr={r.stderr!r}')
        self.assertIn('Uso', r.stdout)

    def test_bandera_desconocida_sale_con_2_sin_abrir_ventana(self):
        try:
            r = self._correr(['--instaler', 'continuidad', '--settings', str(self.settings_ruta)])
        except subprocess.TimeoutExpired:
            self.fail('instalar.py con una bandera desconocida se quedó colgado '
                      '(el fallo real: caía a la ventana Tk sin salida)')
        self.assertEqual(r.returncode, 2, f'stdout={r.stdout!r} stderr={r.stderr!r}')
        self.assertIn('--instaler', r.stderr)
        self.assertFalse(self.settings_ruta.exists(), 'no debe haber tocado settings.json')

    def test_h_corto_tambien_sale_con_0(self):
        try:
            r = self._correr(['-h'])
        except subprocess.TimeoutExpired:
            self.fail('instalar.py -h se quedó colgado')
        self.assertEqual(r.returncode, 0, f'stdout={r.stdout!r} stderr={r.stderr!r}')


if __name__ == '__main__':
    unittest.main()
