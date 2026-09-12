"""`rutas.leer_stdin()` no debe colgarse para siempre si stdin es una tubería abierta que
nunca manda EOF: lee en un hilo daemon con `join(ABYSS_TOPE_STDIN)` y devuelve `{}` al
agotar el tope. Usa `subprocess.Popen` a mano, no `ayudas.ejecutar` (cierra stdin de inmediato)."""
import sys
import os
import time
import subprocess
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import unittest
import ayudas as ay

try:
    import cv2  # solo para decidir si este proceso de pruebas puede medir el caso real
except ImportError:
    cv2 = None


class LeerStdinNoSeQuedaColgado(unittest.TestCase):
    def test_ojo_no_cuelga_con_tuberia_de_stdin_abierta(self):
        env = dict(os.environ)
        env.pop('ABYSS_PROYECTO', None)  # sin proyecto resoluble: debe fallar claro, no colgarse
        env['ABYSS_TOPE_STDIN'] = '0.4'  # tope bajo solo para que la prueba sea rápida

        with subprocess.Popen(
            [sys.executable, str(ay.script('ojo.py'))],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding='utf-8', errors='replace', env=env,
        ) as proc:
            try:
                t0 = time.monotonic()
                # A PROPÓSITO: no se escribe nada en proc.stdin ni se cierra aquí (una
                # tubería abierta que nunca manda EOF).
                rc = proc.wait(timeout=5)
                elapsed = time.monotonic() - t0
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
                self.fail('ojo.py se quedó colgado más de 5 s con una tubería de stdin abierta '
                          '(el fallo original se colgaba sin límite)')

            out = proc.stdout.read()
            err = proc.stderr.read()

        self.assertEqual(rc, 1, f'stdout={out!r} stderr={err!r}')
        self.assertIn('sin proyecto', err)
        self.assertLess(elapsed, 3.0,
                         f'debía volver en torno al tope de stdin (0.4s), tardó {elapsed:.1f}s')


@unittest.skipUnless(cv2 is not None, 'OpenCV no instalado: dependencia opcional de ojo.py, '
                                       'sin él este caso no puede llegar a medir el import que se atascaba')
class OjoNoSeCuelgaConAbyssProyectoPuesto(unittest.TestCase):
    """`ABYSS_PROYECTO` se conserva aquí (a diferencia de `LeerStdinNoSeQuedaColgado`),
    así que `rutas.resolver()` no aborta y `ojo.py` llega hasta `import cv2` con la
    misma tubería de stdin abierta que nunca manda EOF."""

    def test_ojo_con_proyecto_resoluble_llega_a_import_cv2_sin_colgarse(self):
        proj = ay.nuevo_proyecto()
        env = ay.entorno(proj)  # ABYSS_PROYECTO puesto y CONSERVADO — a propósito, no se hace pop
        env['ABYSS_TOPE_STDIN'] = '0.4'  # si por lo que sea SÍ se llegara a leer, que sea rápido
        salida = proj / 'foto.jpg'

        with subprocess.Popen(
            # cámara 99 no existe en ninguna máquina de pruebas: ojo.py falla al abrir
            # la "cámara" sin tocar hardware real. Despacha por verbos; "mirar" la abre.
            [sys.executable, str(ay.script('ojo.py')), 'mirar', str(salida), '99'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding='utf-8', errors='replace', env=env,
        ) as proc:
            try:
                t0 = time.monotonic()
                rc = proc.wait(timeout=20)
                elapsed = time.monotonic() - t0
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
                self.fail('ojo.py se quedó colgado más de 20 s con ABYSS_PROYECTO puesto '
                          'y stdin abierto: el hilo de leer_stdin() seguía trabando el '
                          'import de cv2 (el fallo real que el otro caso no medía)')

            out = proc.stdout.read()
            err = proc.stderr.read()

        # cámara 99 no existe: ojo.py sale por "cámara no disponible" (código 2)
        self.assertEqual(rc, 2, f'stdout={out!r} stderr={err!r}')
        self.assertIn('no disponible', out)
        self.assertLess(elapsed, 15.0,
                         f'sin el fallo, import cv2 no debería tardar tanto: {elapsed:.1f}s')


class ContinuidadNoHeredaStdinHaciaVaras(unittest.TestCase):
    """`continuidad.cerrar()` lanza `varas.py --index` con `subprocess.run`: sin
    `stdin=DEVNULL` el hijo heredaría el stdin del gancho. La cadena de herencia de 3
    niveles no es fiable de reproducir en vivo, así que se comprueba por el código fuente."""

    def test_subprocess_run_de_varas_pasa_stdin_devnull(self):
        ruta = ay.script('continuidad.py')
        texto = Path(ruta).read_text(encoding='utf-8')
        i = texto.index("'varas.py'")
        # la llamada subprocess.run(...) completa: desde 'varas.py' hasta el próximo ')'
        fragmento = texto[i:i + 400]
        self.assertIn('stdin=subprocess.DEVNULL', fragmento,
                      'subprocess.run([sys.executable, ..., "varas.py", "--index"], ...) '
                      'debe pasar stdin=subprocess.DEVNULL para no heredar el del gancho')


if __name__ == '__main__':
    unittest.main()
