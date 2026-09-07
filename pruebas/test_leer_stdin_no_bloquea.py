"""`rutas.leer_stdin()` (fallo 6-sep, "roza"): solo se protegía contra un terminal
(`isatty`). Si stdin es una TUBERÍA ABIERTA que nunca manda EOF, `sys.stdin.read()`
se colgaba para siempre, sin límite de tiempo — MEDIDO: `( sleep 30 ) | python
abyss/ojo.py` seguía colgado hasta matarlo a los 15 s. Afecta a cualquier guion que
resuelva `rutas.resolver()` sin pista de proyecto (`ojo.py`, y por extensión
`continuidad.py`/`vigia.py`/`varas.py`/`propiocepcion.py` si Claude Code no cierra
el descriptor de stdin del gancho).

Ahora `leer_stdin()` lee en un hilo daemon con `join(tope)` (por defecto
`ABYSS_TOPE_STDIN`, 3 s): agotado el tope, se abandona la lectura y se devuelve {}
— aquí se baja el tope por env para que la prueba sea rápida sin dejar de medir el
mecanismo real (un tope bajo o alto es la MISMA lógica).

Se usa `subprocess.Popen` a mano (no `ayudas.ejecutar`, que usa `subprocess.run`
con `input=` — eso escribe Y CIERRA stdin de inmediato, justo lo que aquí no
queremos): se abre la tubería y NUNCA se escribe ni se cierra, para reproducir de
verdad "una tubería abierta que no manda EOF".

SEGUNDA VUELTA (6-sep, revisor Opus, "engaña"): el caso de arriba
(`LeerStdinNoSeQuedaColgado`) hace `env.pop('ABYSS_PROYECTO')` — SIN proyecto
resoluble, `rutas.resolver()` hace `sys.exit(1)` en cuanto el tope de
`leer_stdin()` expira, ANTES de que `ojo.py` llegue a `import cv2`. Así mide el
camino del ABORTO, no el camino en el que `ojo.py` hace su trabajo — y es
justo AHÍ donde está el fallo real: MEDIDO con un guion mínimo, agotado el tope
de `leer_stdin()` el hilo daemon queda VIVO, bloqueado para siempre en
`sys.stdin.read()` (no se puede matar un hilo desde fuera en Python), y el
siguiente `import` que toque hilos (`import cv2`) se traba contra él — el
proceso entero deja de avanzar sin volver jamás, aunque `leer_stdin()` ya
hubiera devuelto {} a tiempo. `ContinuidadNoSeCuelgaConAbyssProyectoPuesto` de
abajo CONSERVA `ABYSS_PROYECTO` (no lo hace pop) con la MISMA tubería abierta:
`rutas.resolver()` SÍ resuelve, y `ojo.py` SÍ llega a `import cv2` — es el único
de los dos casos que reproduce el cuelgue de verdad.
"""
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
                # A PROPÓSITO: no se escribe nada en proc.stdin ni se cierra aquí — con
                # el fallo, esto se queda esperando un EOF que nunca llega.
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
    """El caso que `LeerStdinNoSeQuedaColgado` NO cazaba: aquí `ABYSS_PROYECTO` se
    CONSERVA (no se hace pop), así que `rutas.resolver()` resuelve sin abortar y
    `ojo.py` llega de verdad hasta `import cv2` con la misma tubería de stdin
    abierta que nunca manda EOF."""

    def test_ojo_con_proyecto_resoluble_llega_a_import_cv2_sin_colgarse(self):
        proj = ay.nuevo_proyecto()
        env = ay.entorno(proj)  # ABYSS_PROYECTO puesto y CONSERVADO — a propósito, no se hace pop
        env['ABYSS_TOPE_STDIN'] = '0.4'  # si por lo que sea SÍ se llegara a leer, que sea rápido
        salida = proj / 'foto.jpg'

        with subprocess.Popen(
            # índice de cámara 99: no existe de verdad en ninguna máquina de pruebas,
            # así ojo.py falla al abrir la "cámara" sin tocar hardware real — lo que
            # se está midiendo es si el PROCESO vuelve, no si hay foto.
            # T4.6: ojo.py despacha por verbos y `mirar` es el que abre la cámara.
            [sys.executable, str(ay.script('ojo.py')), 'mirar', str(salida), '99'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding='utf-8', errors='replace', env=env,
        ) as proc:
            try:
                t0 = time.monotonic()
                # A PROPÓSITO: la misma tubería abierta sin EOF que en el caso de
                # arriba — la diferencia es que aquí SÍ hay proyecto resoluble, así
                # que el proceso no aborta en rutas.resolver() y llega a import cv2.
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
    """Camino real más probable señalado 6-sep: `continuidad.cerrar()` lanza
    `varas.py --index` con `subprocess.run` — si no se le pasa `stdin=DEVNULL`, el
    hijo hereda el descriptor de stdin del propio gancho, y si ese descriptor es una
    tubería que Claude Code no cierra, el cierre de sesión se come el timeout
    entero. Reproducir la cadena de herencia de 3 niveles (Claude Code → gancho →
    varas.py) en una prueba no es fiable; se comprueba directamente, por el código
    fuente, que la llamada lleva `stdin=subprocess.DEVNULL` — con el fallo, esta
    prueba falla porque esa palabra no aparece junto a la llamada."""

    def test_subprocess_run_de_varas_pasa_stdin_devnull(self):
        ruta = ay.script('continuidad.py')
        texto = Path(ruta).read_text(encoding='utf-8')
        i = texto.index("'varas.py'")
        # la llamada a subprocess.run completa: desde 'varas.py' hasta el próximo ')'
        # que cierra subprocess.run(...) — basta con mirar los ~300 caracteres siguientes
        fragmento = texto[i:i + 400]
        self.assertIn('stdin=subprocess.DEVNULL', fragmento,
                      'subprocess.run([sys.executable, ..., "varas.py", "--index"], ...) '
                      'debe pasar stdin=subprocess.DEVNULL para no heredar el del gancho')


if __name__ == '__main__':
    unittest.main()
