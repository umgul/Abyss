"""`pintor.pintar()` con `--acabado` y `--suave` (ESPECIFICACION.md §6). A diferencia
de los guiones con gancho, `pintor.py` no llama a `rutas.resolver()` ni conoce `mem`,
así que aquí es seguro importarlo directamente, sin subprocess."""
import sys
import os
import tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import unittest
import ayudas as ay

sys.path.insert(0, str(ay.PKG))

try:
    from PIL import Image
    import pintor
except ImportError:
    Image = None
    pintor = None


def _foto_sintetica(ruta, ancho=200, alto=150):
    img = Image.new('RGB', (ancho, alto))
    px = img.load()
    for y in range(alto):
        for x in range(ancho):
            px[x, y] = ((x * 3) % 256, (y * 5) % 256, ((x + y * 2) * 7) % 256)
    img.save(ruta)
    return ruta


@unittest.skipUnless(pintor is not None, 'Pillow/numpy no disponibles (requirements.txt): opcionales de pintor.py')
class PintorAcabadoYSuave(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix='abyss_pintor_')
        self.foto = _foto_sintetica(os.path.join(self.d, 'foto.png'))

    def test_acabado_anhade_pinceladas_sin_subir_el_error(self):
        sin = pintor.pintar(self.foto, salida=os.path.join(self.d, 'sin'), ancho=200,
                             acabado=False, semilla=7, avisar=lambda *a: None)
        con = pintor.pintar(self.foto, salida=os.path.join(self.d, 'con'), ancho=200,
                             acabado=True, semilla=7, avisar=lambda *a: None)
        self.assertGreater(con['pinceladas'], sin['pinceladas'],
                            '--acabado añade una capa extra: debe haber más pinceladas')
        self.assertLessEqual(con['error_medio'], sin['error_medio'],
                              '--acabado repasa lo que faltaba: el error medio no debe subir')

    def test_suave_mantiene_el_tamano_del_png(self):
        normal = pintor.pintar(self.foto, salida=os.path.join(self.d, 'n1'), ancho=200,
                                supermuestreo=1, semilla=7, avisar=lambda *a: None)
        suave = pintor.pintar(self.foto, salida=os.path.join(self.d, 'n2'), ancho=200,
                               supermuestreo=2, semilla=7, avisar=lambda *a: None)
        self.assertEqual((normal['W'], normal['H']), (suave['W'], suave['H']))
        with Image.open(normal['png']) as im1, Image.open(suave['png']) as im2:
            self.assertEqual(im1.size, im2.size,
                              '--suave pinta más grande y reduce al final: el PNG de salida '
                              'debe medir lo mismo que sin él (el tamaño de FICHERO puede variar)')


if __name__ == '__main__':
    unittest.main()
