"""`kinetico.py`: sin `--salida`, la escena se monta en el temporal del sistema, nunca
en el directorio desde el que se lanza (que puede ser el repo del usuario)."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ayudas as ay


class MontarSinSalidaNoEnsuciaElCwd(unittest.TestCase):
    def test_solo_montar_sin_salida_no_escribe_en_el_cwd(self):
        carpeta = Path(tempfile.mkdtemp(prefix='abyss_kinetico_arbol_'))
        (carpeta / 'nota.txt').write_text('hola', encoding='utf-8')
        cwd = Path(tempfile.mkdtemp(prefix='abyss_kinetico_cwd_'))
        r = ay.ejecutar(ay.script('kinetico.py'), ['arbol', str(carpeta), '--hondura', '1', '--solo-montar', '--sin-manos'],
                        dict(os.environ), cwd=str(cwd), timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(list(cwd.iterdir()), [], 'no debe dejar nada en el directorio de lanzamiento')
        self.assertTrue((Path(tempfile.gettempdir()) / 'abyss' / 'kinetico_montado' / 'nodos.json').is_file())


if __name__ == '__main__':
    unittest.main()
