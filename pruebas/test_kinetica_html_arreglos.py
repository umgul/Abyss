"""Falsadores de TEXTO FUENTE sobre `abyss/plantillas/kinetica.html` (no hay
motor JS en esta máquina de pruebas): comprueban que el aviso y la leyenda
salen de datos reales (`ficha.procedencia`, `piezas`), no de texto fijo."""
import re
import unittest
from pathlib import Path

RUTA_HTML = Path(__file__).resolve().parent.parent / 'abyss' / 'plantillas' / 'kinetica.html'

# frases fijas que no deben aparecer en ningún sitio de la plantilla (no solo
# en la asignación a `#aviso`)
FRASES_FIJAS_FALSAS = (
    'region puesta a mano',
    'se reconstruye por inpainting',
    'pixel inventado, no fotografiado',
)

# nombres de la foto de demo: no deben aparecer en la plantilla, que se copia
# tal cual como index.html para cualquier foto (kinetica.py:483)
NOMBRES_DE_DEMO = ('telefono', 'empunadura', 'teleobjetivo')


class ElAvisoSaleDeLaFichaNoDeTextoFijo(unittest.TestCase):
    def setUp(self):
        self.html = RUTA_HTML.read_text(encoding='utf-8')

    def test_no_queda_ninguna_frase_fija_falsa_del_modo_manual(self):
        bajo = self.html.lower()
        for frase in FRASES_FIJAS_FALSAS:
            self.assertNotIn(frase, bajo,
                f'sigue el texto fijo "{frase}": en modo automático (sin --regiones) es '
                'falso — no hubo región puesta a mano ni se llamó a cv2.inpaint')

    def test_aviso_se_construye_con_los_tres_campos_de_procedencia(self):
        # las tres claves que kinetica.py redacta para cada modo (kinetica.py:427-460)
        # deben usarse juntas en la expresión que llena `#aviso`.
        m = re.search(
            r"\$\(\s*['\"]#aviso['\"]\s*\)\.textContent\s*=(?P<expr>.*?);",
            self.html, re.DOTALL)
        self.assertIsNotNone(m, 'no se encuentra la asignación a $(\'#aviso\').textContent')
        expr = m.group('expr')
        for campo in ('regiones', 'recorte', 'relleno'):
            self.assertIn(f'ficha.procedencia.{campo}', expr,
                f'la asignación de #aviso no lee ficha.procedencia.{campo}')


class LaLeyendaNombraLasPiezasQueHay(unittest.TestCase):
    def setUp(self):
        self.html = RUTA_HTML.read_text(encoding='utf-8')

    def test_ningun_nombre_de_la_foto_de_demo_queda_en_la_plantilla(self):
        bajo = self.html.lower()
        for nombre in NOMBRES_DE_DEMO:
            self.assertNotIn(nombre, bajo,
                f'sigue "{nombre}" (nombre de la foto de demo) en una plantilla que se '
                'copia tal cual para cualquier foto (kinetica.py:483)')
        self.assertNotIn('las tres piezas', bajo,
            'sigue afirmando un número fijo de piezas en la leyenda')

    def test_hay_un_hueco_para_la_leyenda_que_el_js_rellena_desde_piezas(self):
        self.assertIn('id="leyenda_piezas"', self.html,
            'falta el contenedor que el JS debe rellenar con las piezas reales')
        # itera sobre `piezas` y usa el orden/título de cada una, no un número o
        # nombre fijo. Se toma una ventana de 300 caracteres en vez de cortar en
        # el primer ';': la leyenda mete `&middot;`, que ya trae un ';' propio.
        m = re.search(r"leyenda_piezas['\"]\s*\)\.innerHTML\s*=", self.html)
        self.assertIsNotNone(m, "no se encuentra la asignación a $('#leyenda_piezas').innerHTML")
        ventana = self.html[m.end(): m.end() + 300]
        self.assertIn('piezas.map', ventana, 'la leyenda no se construye recorriendo `piezas`')
        self.assertIn('.dato.orden', ventana, 'la leyenda no usa el orden real de cada pieza')
        self.assertIn('.dato.titulo', ventana, 'la leyenda no usa el título real de cada pieza')


if __name__ == '__main__':
    unittest.main()
