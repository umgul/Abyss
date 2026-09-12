"""`ABYSS_PROYECTO` con un nombre sin separadores se resuelve bajo
`~/.claude/projects/`, nunca como carpeta relativa al cwd."""
import os
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ayudas as ay


class NombrePeladoVaBajoClaudeProjects(unittest.TestCase):
    def test_nombre_sin_separadores_no_crea_carpeta_en_el_cwd(self):
        home = ay.nuevo_proyecto()
        cwd = ay.nuevo_proyecto()
        env = ay.entorno('nombre-pelado', HOME=str(home), USERPROFILE=str(home))
        codigo = (f'import sys; sys.path.insert(0, {str(ay.PKG)!r}); import rutas; '
                  'print(rutas.resolver([], {})[0])')
        r = subprocess.run([sys.executable, '-c', codigo], env=env, cwd=str(cwd),
                           capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        esperado = home / '.claude' / 'projects' / 'nombre-pelado'
        self.assertEqual(Path(r.stdout.strip()).resolve(), esperado.resolve())
        self.assertTrue((esperado / 'memory').is_dir())
        self.assertFalse((cwd / 'nombre-pelado').exists(), 'un nombre pelado no debe crear nada en el cwd')

    def test_una_ruta_con_separadores_se_usa_tal_cual(self):
        proj = ay.nuevo_proyecto()
        env = ay.entorno(proj)
        codigo = (f'import sys; sys.path.insert(0, {str(ay.PKG)!r}); import rutas; '
                  'print(rutas.resolver([], {})[0])')
        r = subprocess.run([sys.executable, '-c', codigo], env=env,
                           capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(Path(r.stdout.strip()).resolve(), proj.resolve())


if __name__ == '__main__':
    unittest.main()
