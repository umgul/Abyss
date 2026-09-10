"""Dos fallos señalados el 8-sep sobre `abyss/plantillas/kinetica.html` (leída y ARREGLADA
aquí — es la única excepción a "no tocar la plantilla" que pidió el propio revisor; el
resto del paquete la trata como solo lectura, ver `test_kinetica.py`).

Ninguna prueba de aquí abre un navegador (no hay motor JS en esta máquina de pruebas, ver
`requirements.txt`/`instalar.py`: no se instala nada con pip para esto): son falsadores de
TEXTO FUENTE, mismo patrón que `test_documentos_espejo.py` para ficheros que esta suite no
puede ejecutar. La verificación de comportamiento real —servir una carpeta montada por
`kinetica.montar()` en 127.0.0.1 y leer el DOM con un navegador de verdad— se hizo a mano
al escribir este arreglo (medido en ambos modos, automático y manual) y se describe en el
informe de la tarea, no aquí.

(a) `#aviso` — LA PANTALLA afirmaba SIEMPRE "region puesta a mano" y "se reconstruye por
    inpainting", texto fijo en el HTML, aunque el modo automático (sin --regiones) no hace
    ninguna de las dos cosas (`piezas.json` trae `relleno_px: 0` y `procedencia.modo:
    "automatico"`). Arreglo: el aviso sale de `ficha.procedencia` (regiones/recorte/
    relleno), redactada por `kinetica.py` para CADA modo — nunca un texto fijo.

(b) leyenda de la izquierda — nombraba SIEMPRE los tres componentes de la foto de demo
    ("telefono", "empunadura", "teleobjetivo", "las tres piezas"), aunque la carpeta
    montada trajera otro número de piezas con otros nombres (o ninguno, en automático).
    Arreglo: la línea se construye en JS a partir de `piezas` ya cargadas
    (`q.dato.orden`/`q.dato.titulo`), en un `<div id="leyenda_piezas">` que antes era
    texto fijo.
"""
import re
import unittest
from pathlib import Path

RUTA_HTML = Path(__file__).resolve().parent.parent / 'abyss' / 'plantillas' / 'kinetica.html'

# las frases fijas exactas del fallo (a), tal cual estaban antes del arreglo — deben
# desaparecer del todo, no solo de la línea que las asignaba a `#aviso`
FRASES_FIJAS_FALSAS = (
    'region puesta a mano',
    'se reconstruye por inpainting',
    'pixel inventado, no fotografiado',
)

# los nombres de la foto de demo del fallo (b) — no deben aparecer en ningún sitio de la
# plantilla: se copia tal cual como index.html para CUALQUIER foto (kinetica.py:483)
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
        # las tres claves que kinetica.py redacta para CADA modo (kinetica.py:427-460):
        # deben usarse juntas, en la misma expresión que llena `#aviso`, para que la
        # pantalla diga lo que de verdad pasó en ESTA carpeta y no una mezcla fija.
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
        # debe iterar sobre `piezas` (las cargadas desde piezas.json) y usar el orden y el
        # título de CADA una, no un número ni un nombre fijo. Se toma una ventana de texto
        # tras la asignación (no hasta el primer ';': la propia leyenda mete `&middot;`,
        # una entidad HTML con su propio ';' en medio del texto) en vez de recortar por la
        # sintaxis exacta de la sentencia, para no depender de cómo se parta en líneas.
        m = re.search(r"leyenda_piezas['\"]\s*\)\.innerHTML\s*=", self.html)
        self.assertIsNotNone(m, "no se encuentra la asignación a $('#leyenda_piezas').innerHTML")
        ventana = self.html[m.end(): m.end() + 300]
        self.assertIn('piezas.map', ventana, 'la leyenda no se construye recorriendo `piezas`')
        self.assertIn('.dato.orden', ventana, 'la leyenda no usa el orden real de cada pieza')
        self.assertIn('.dato.titulo', ventana, 'la leyenda no usa el título real de cada pieza')


if __name__ == '__main__':
    unittest.main()
