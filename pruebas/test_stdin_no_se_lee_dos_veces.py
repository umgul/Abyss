"""
Comprueba que `propiocepcion.py` y `varas.py` leen stdin de forma perezosa
(evitan el tope de `rutas.leer_stdin()` si `ABYSS_PROYECTO` ya está puesto),
mientras `continuidad.py` y `vigia.py` siguen leyendo stdin a secas a propósito.
"""
import sys
import os
import time
import subprocess
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import unittest
import ayudas as ay


class PropiocepcionNoReleeStdinConAbyssProyectoPuesto(unittest.TestCase):
    def test_propiocepcion_no_espera_el_tope_con_abyss_proyecto_puesto(self):
        proj = ay.nuevo_proyecto()
        (proj / 'memory').mkdir(parents=True, exist_ok=True)
        env = ay.entorno(proj)  # ABYSS_PROYECTO puesto y CONSERVADO
        env['ABYSS_TOPE_STDIN'] = '5'  # si por lo que sea SÍ leyera, tardaría ~5s: de sobra para notarlo

        with subprocess.Popen(
            [sys.executable, str(ay.script('propiocepcion.py'))],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding='utf-8', errors='replace', env=env,
        ) as proc:
            t0 = time.monotonic()
            try:
                # A PROPÓSITO: no se escribe nada en proc.stdin ni se cierra — una
                # tubería abierta que nunca manda EOF, igual que en
                # test_leer_stdin_no_bloquea.py.
                rc = proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
                self.fail('propiocepcion.py tardó más de 8s con ABYSS_PROYECTO puesto: '
                          'seguía leyendo stdin (y pagando su tope) aunque ya no hacía falta')
            elapsed = time.monotonic() - t0
            out = proc.stdout.read()
            err = proc.stderr.read()

        self.assertEqual(rc, 0, f'stdout={out!r} stderr={err!r}')
        self.assertLess(elapsed, 2.0,
                         f'con el fallo tardaría en torno al tope (5s aquí); tardó {elapsed:.1f}s')


class VarasTampocoReleeStdinConAbyssProyectoPuesto(unittest.TestCase):
    def test_varas_index_no_espera_el_tope_con_abyss_proyecto_puesto(self):
        proj = ay.nuevo_proyecto()
        (proj / 'memory').mkdir(parents=True, exist_ok=True)
        env = ay.entorno(proj)
        env['ABYSS_TOPE_STDIN'] = '5'

        with subprocess.Popen(
            [sys.executable, str(ay.script('varas.py')), '--index'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding='utf-8', errors='replace', env=env,
        ) as proc:
            t0 = time.monotonic()
            try:
                rc = proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
                self.fail('varas.py --index se quedó colgado más de 8s con ABYSS_PROYECTO puesto')
            elapsed = time.monotonic() - t0
            out = proc.stdout.read()
            err = proc.stderr.read()

        self.assertEqual(rc, 0, f'stdout={out!r} stderr={err!r}')
        self.assertLess(elapsed, 2.0,
                         f'con el fallo tardaría en torno al tope (5s aquí); tardó {elapsed:.1f}s')


class LosDosQueSoloAlimentanResolverUsanElAtajoPerezoso(unittest.TestCase):
    """Comprueba por código fuente (no por timing, más frágil) que
    `propiocepcion.py` y `varas.py` llaman a la variante perezosa de lectura
    de stdin."""

    def test_propiocepcion_y_varas_llaman_a_la_variante_perezosa(self):
        raiz_abyss = Path(ay.PKG)
        for nombre in ('propiocepcion.py', 'varas.py'):
            texto = (raiz_abyss / nombre).read_text(encoding='utf-8')
            self.assertIn('rutas.leer_stdin_si_hace_falta(', texto,
                          f'{nombre} debe leer stdin con leer_stdin_si_hace_falta(), '
                          f'no con leer_stdin() a secas (fallo 6-sep)')
            self.assertNotIn('_STDIN = rutas.leer_stdin()', texto)


class LosDosConLogicaPropiaSiguenLeyendoASecas(unittest.TestCase):
    """`continuidad.py` y `vigia.py` deben seguir leyendo stdin a secas: usan
    `session_id`/`transcript_path`/`cwd`/`prompt` de `_STDIN`, no solo para
    resolver `proj`/`mem`."""

    def test_continuidad_y_vigia_siguen_con_leer_stdin_a_secas(self):
        raiz_abyss = Path(ay.PKG)
        for nombre in ('continuidad.py', 'vigia.py'):
            texto = (raiz_abyss / nombre).read_text(encoding='utf-8')
            self.assertIn('_STDIN = rutas.leer_stdin()', texto,
                          f'{nombre} debe seguir leyendo con leer_stdin() a secas '
                          f'(usa otros campos de _STDIN además de para resolver())')


if __name__ == '__main__':
    unittest.main()
