"""Falsador del arreglo de `pintor.py` (ESPECIFICACION_TANDA3.md T3.2, arreglo «--html ignora el
papel y el alfa del estilo»): antes de este arreglo, la plantilla `_HTML` de `--html` pintaba
SIEMPRE `borra()` sobre `#080607` (el fondo fijo de "oleo") y con alfa 1, sin mirar el `"papel"`
ni el `"alfa"` que el propio `.json.gz` ya guarda (T3.2) y que `video_pintura.py` sí respeta —
medido con `pintor.py sintetica.png --estilo tinta --html`: papel del cuadro `#ffffff`, página con
`#080607`. Lo mismo vale para carbon, acuarela, pastel e impresionista (papeles claros).

Importa `pintor` directamente en el proceso de la prueba, como `test_pintor_estilos.py` y
`test_pintor_acabado_suave.py` (no toca `rutas.resolver()` ni conoce `mem`).
"""
import sys
import os
import re
import gzip
import json
import tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import unittest
import ayudas as ay

sys.path.insert(0, str(ay.PKG))

try:
    from PIL import Image
    import pintor
except ImportError:
    Image = pintor = None

# estilos cuyo papel NO es el fondo oscuro de oleo (#08 06 07) — los afectados por el fallo
ESTILOS_PAPEL_CLARO = ("impresionista", "acuarela", "pastel", "carbon", "tinta")


def _foto_sintetica(ruta, ancho=60, alto=40):
    img = Image.new('RGB', (ancho, alto))
    px = img.load()
    for y in range(alto):
        for x in range(ancho):
            px[x, y] = ((x * 4) % 256, (y * 6) % 256, ((x + y) * 3) % 256)
    img.save(ruta)
    return ruta


def _leer_papel_alfa_html(ruta_html):
    """Extrae los literales `PAPEL=` y `ALFA=` que la plantilla `_HTML` inyecta en el <script>."""
    with open(ruta_html, encoding='utf-8') as fh:
        texto = fh.read()
    m = re.search(r'PAPEL=(\"#[0-9a-f]{6}\"),ALFA=([0-9.]+)', texto)
    assert m, f'la plantilla _HTML debe declarar PAPEL/ALFA junto a T: {ruta_html}'
    return json.loads(m.group(1)), float(m.group(2)), texto


@unittest.skipUnless(pintor is not None, 'Pillow no disponible (requirements.txt): opcional de pintor.py')
class HtmlUsaElPapelYElAlfaDelEstilo(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix='abyss_pintor_html_')
        self.foto = _foto_sintetica(os.path.join(self.d, 'foto.png'))

    def _pintar(self, estilo):
        return pintor.pintar(self.foto, salida=os.path.join(self.d, estilo), ancho=60,
                              semilla=3, estilo=estilo, html=True, avisar=lambda *a: None)

    def test_html_pinta_sobre_el_papel_del_estilo_no_el_fondo_del_oleo(self):
        for estilo in ESTILOS_PAPEL_CLARO:
            r = self._pintar(estilo)
            with gzip.open(r['trazos'], 'rt', encoding='utf-8') as fh:
                datos = json.load(fh)
            papel_esperado = datos['radios']['papel']  # el mismo dato que ya viaja en el .json.gz
            papel_html, _alfa_html, texto = _leer_papel_alfa_html(r['html'])
            self.assertEqual(papel_html, papel_esperado,
                              f'{estilo}: --html debe pintar sobre su propio papel ({papel_esperado}), '
                              f'no sobre un fondo fijo')
            self.assertNotEqual(papel_esperado, '#080607',
                                 f'{estilo}: la tabla del estilo debe tener un papel distinto del de oleo '
                                 f'para que esta prueba falsara el fallo original')
            # el fondo oscuro fijo de oleo no debe colarse en la página de un estilo de papel claro
            self.assertNotIn('#080607', texto,
                              f'{estilo}: la página no debe seguir usando el fondo fijo de oleo')

    def test_html_usa_el_alfa_del_estilo_para_componer_capas(self):
        r = self._pintar('acuarela')
        with gzip.open(r['trazos'], 'rt', encoding='utf-8') as fh:
            datos = json.load(fh)
        _papel_html, alfa_html, texto = _leer_papel_alfa_html(r['html'])
        self.assertAlmostEqual(alfa_html, datos['radios']['alfa'], places=3,
                                msg='acuarela: --html debe recibir el mismo alfa que el .json.gz')
        self.assertLess(alfa_html, 0.999, 'acuarela: su alfa de capa es < 1 (pinta por capas)')
        # con alfa<1 la plantilla compone cada capa aparte (mismo criterio que video_pintura.py)
        self.assertIn('globalAlpha', texto,
                       'con alfa < 1 la plantilla debe componer la capa con globalAlpha, no dibujar directo')

    def test_html_de_oleo_no_cambia_de_papel_ni_de_alfa(self):
        # oleo es el único estilo cuyo papel YA coincidía con el fondo fijo anterior: el arreglo
        # no debe alterar su resultado.
        r = self._pintar('oleo')
        papel_html, alfa_html, _texto = _leer_papel_alfa_html(r['html'])
        self.assertEqual(papel_html, '#080607')
        self.assertEqual(alfa_html, 1.0)


if __name__ == '__main__':
    unittest.main()
