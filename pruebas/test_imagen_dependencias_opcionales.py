"""`imagen.py pintar`/`video` con Pillow/numpy bloqueados (fallo 6-sep, "engaña"):
MEDIDO que `import pintor`/`import video_pintura` sin `try/except` dejaban salir la
traza cruda de `ModuleNotFoundError` (`imagen.py pintar ...` -> Traceback ... File
"abyss/pintor.py", line 38, in <module> / import numpy as np / ModuleNotFoundError;
`imagen.py video ...` -> Traceback ... File "abyss/video_pintura.py", line 24 / from
PIL import Image, ImageDraw / ModuleNotFoundError), mientras el README prometía
"nunca con una traza cruda".

Se bloquea el import de `numpy`/`PIL` con un `sitecustomize.py` propio en un
directorio temporal antepuesto a `PYTHONPATH` (mismo método que usó el revisor):
Pillow y numpy SIGUEN instalados en la máquina real, solo este proceso hijo no los
ve — nunca se toca el Python real ni sale ninguna petición de red.
"""
import sys
import os
import textwrap
import tempfile
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import unittest
import ayudas as ay


def _entorno_con_modulos_bloqueados(proj, nombres):
    bloqueo_dir = Path(tempfile.mkdtemp(prefix='abyss_bloqueo_'))
    lista_py = ', '.join(repr(n) for n in nombres)
    (bloqueo_dir / 'sitecustomize.py').write_text(textwrap.dedent(f'''
        import sys
        import importlib.abc

        class _Bloqueador(importlib.abc.MetaPathFinder):
            BLOQUEADOS = {{{lista_py}}}

            def find_spec(self, name, path, target=None):
                raiz = name.split(".")[0]
                if raiz in self.BLOQUEADOS:
                    raise ModuleNotFoundError(
                        "{{}} bloqueado por la prueba (sitecustomize)".format(raiz), name=raiz)
                return None

        sys.meta_path.insert(0, _Bloqueador())
    '''), encoding='utf-8')
    env = ay.entorno(proj)
    env['PYTHONPATH'] = str(bloqueo_dir) + os.pathsep + env.get('PYTHONPATH', '')
    return env


class ImagenPintarSinNumpyFallaClaro(unittest.TestCase):
    def test_mensaje_claro_sin_traceback_ni_codigo_0(self):
        proj = ay.nuevo_proyecto()
        (proj / 'memory').mkdir(exist_ok=True)
        foto = proj / 'foto.png'
        foto.write_bytes(b'no hace falta que sea un PNG real: numpy revienta antes de leerla')
        env = _entorno_con_modulos_bloqueados(proj, ['numpy'])

        r = ay.ejecutar(ay.script('imagen.py'), ['pintar', str(foto)], env)

        self.assertEqual(r.returncode, 2, f'stdout={r.stdout!r} stderr={r.stderr!r}')
        self.assertNotIn('Traceback', r.stdout)
        self.assertNotIn('Traceback', r.stderr)
        self.assertIn('sin cuadro', r.stdout)


class ImagenVideoSinPillowFallaClaro(unittest.TestCase):
    def test_mensaje_claro_sin_traceback_ni_codigo_0(self):
        proj = ay.nuevo_proyecto()
        (proj / 'memory').mkdir(exist_ok=True)
        trazos = proj / 'trazos.json.gz'
        trazos.write_bytes(b'')  # no hace falta que sea válido: PIL revienta antes de leerlo
        env = _entorno_con_modulos_bloqueados(proj, ['PIL'])

        r = ay.ejecutar(ay.script('imagen.py'),
                         ['video', str(trazos), str(proj / 'salida.mp4')], env)

        self.assertEqual(r.returncode, 2, f'stdout={r.stdout!r} stderr={r.stderr!r}')
        self.assertNotIn('Traceback', r.stdout)
        self.assertNotIn('Traceback', r.stderr)
        self.assertIn('sin video', r.stdout)


if __name__ == '__main__':
    unittest.main()
