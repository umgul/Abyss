"""Todo enlace markdown `[texto](ruta)` en la documentación publicada, que no sea
externo (`http://`/`https://`) ni un ancla (`#...`), debe resolver a un fichero
real, relativo a la carpeta del propio .md."""
import re
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
FICHEROS_MD = [RAIZ / 'README.md', RAIZ / 'README.en.md', RAIZ / 'docs' / 'leyes.md']
RE_ENLACE = re.compile(r'\[[^\]]*\]\(([^)]+)\)')


def _rutas_de(md_path):
    texto = md_path.read_text(encoding='utf-8')
    for destino in RE_ENLACE.findall(texto):
        destino = destino.strip()
        if destino.startswith(('http://', 'https://', '#', 'mailto:')):
            continue
        yield destino.split('#', 1)[0]  # quita un ancla `#seccion` al final, si la hay


class EnlacesInternosResuelven(unittest.TestCase):
    def test_todos_los_enlaces_relativos_existen(self):
        rotos = []
        for md in FICHEROS_MD:
            if not md.exists():
                continue
            for destino in _rutas_de(md):
                if not (md.parent / destino).exists():
                    rotos.append(f'{md.relative_to(RAIZ)} -> {destino}')
        self.assertEqual(rotos, [], 'enlaces markdown rotos:\n' + '\n'.join(rotos))


if __name__ == '__main__':
    unittest.main()
