"""`pintor.pintar(..., estilo=...)`: motor
único, un dict de parámetros por estilo. Importa `pintor` directamente en el proceso de la
prueba, como `test_pintor_acabado_suave.py` (no toca `rutas.resolver()` ni conoce `mem`).

Cada valor de este fichero (pinceladas, fracción blanca, desviación entre canales) es una MEDIDA
tomada en el propio desarrollo de esta tarea sobre las fotos sintéticas de aquí — no un umbral
inventado; ver el margen con el que pasa cada aserción antes de tocar los estilos.
"""
import sys
import os
import gzip
import json
import tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import unittest
import ayudas as ay

sys.path.insert(0, str(ay.PKG))

try:
    from PIL import Image, ImageDraw
    import numpy as np
    import pintor
except ImportError:
    Image = ImageDraw = np = pintor = None


def _foto_sintetica(ruta, ancho=150, alto=100):
    """La misma fórmula de degradado que usan `test_imagen_pintar.py` y
    `test_pintor_acabado_suave.py`: reproducible, con las tres bandas de color distintas."""
    img = Image.new('RGB', (ancho, alto))
    px = img.load()
    for y in range(alto):
        for x in range(ancho):
            px[x, y] = ((x * 3) % 256, (y * 5) % 256, ((x + y * 2) * 7) % 256)
    img.save(ruta)
    return ruta


def _foto_clara(ruta, ancho=150, alto=100):
    """Una imagen «clara»: casi toda cerca del blanco, con una figura más oscura en el centro
    (para `tinta`: sin una zona genuinamente próxima al papel blanco, nada se queda sin pintar)."""
    img = Image.new('RGB', (ancho, alto))
    px = img.load()
    for y in range(alto):
        for x in range(ancho):
            if ancho * 0.2 < x < ancho * 0.75 and alto * 0.25 < y < alto * 0.8:
                px[x, y] = (60 + (x % 30), 50 + (y % 30), 70 + ((x + y) % 20))
            else:
                px[x, y] = (246 + (x % 8), 248 + (y % 6), 250 + ((x + y) % 5))
    img.save(ruta)
    return ruta


def _mascara_cubierta(trazos_gz, margen=2):
    """Repinta la huella (línea + dos círculos) de cada trazo en una máscara aparte — igual que
    `pintor.pintar()` dibuja cada pincelada — para saber, píxel a píxel, qué zona del lienzo
    tocó de verdad alguna pincelada (de cualquier capa) y cuál no. `margen` engorda cada trazo
    un poco al repintarlo: sin él, un par de píxeles justo en el BORDE de un trazo (donde
    `ImageDraw` redondea) pueden colar como "sin pincelada" por una diferencia de redondeo entre
    esta reconstrucción y el trazo original — medido, no hipotético — y el "sin pincelada" debe
    ser el interior de verdad, no el borde."""
    with gzip.open(trazos_gz, 'rt', encoding='utf-8') as fh:
        datos = json.load(fh)
    W, H = datos['W'], datos['H']
    mascara = Image.new('L', (W, H), 0)
    dm = ImageDraw.Draw(mascara)
    for radio, _color, pts in datos['trazos']:
        radio = radio + margen
        linea = [(pts[k], pts[k + 1]) for k in range(0, len(pts), 2)]
        dm.line(linea, fill=255, width=2 * radio, joint='curve')
        for q in (linea[0], linea[-1]):
            dm.ellipse([q[0] - radio, q[1] - radio, q[0] + radio, q[1] + radio], fill=255)
    return np.asarray(mascara), datos


def _desviacion_entre_canales(png):
    """max(R,G,B) - min(R,G,B) por píxel, promediado: 0 en un gris perfecto."""
    arr = np.asarray(Image.open(png)).astype(np.float32)
    return float((arr.max(axis=2) - arr.min(axis=2)).mean())


@unittest.skipUnless(pintor is not None, 'Pillow/numpy no disponibles (requirements.txt): opcionales de pintor.py')
class EstilosDelPintor(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix='abyss_pintor_estilos_')
        self.foto = _foto_sintetica(os.path.join(self.d, 'foto.png'))

    def test_cada_estilo_produce_png_y_trazos(self):
        for estilo in ('oleo', 'impresionista', 'acuarela', 'pastel', 'carbon', 'tinta'):
            r = pintor.pintar(self.foto, salida=os.path.join(self.d, estilo), ancho=150,
                               semilla=7, estilo=estilo, avisar=lambda *a: None)
            self.assertEqual(r['estilo'], estilo)
            self.assertGreater(r['pinceladas'], 0, f'{estilo}: debe pintar al menos una pincelada')
            with open(r['png'], 'rb') as fh:
                self.assertEqual(fh.read(8), b'\x89PNG\r\n\x1a\n', f'{estilo}: PNG válido')
            with gzip.open(r['trazos'], 'rt', encoding='utf-8') as fh:
                datos = json.load(fh)
            # las otras tres claves no cambian de forma (test_imagen_pintar.py las exige así);
            # estilo/papel/alfa viajan DENTRO de "radios" (ver docstring de pintor.py)
            self.assertEqual(set(datos.keys()), {'W', 'H', 'radios', 'trazos'})
            self.assertEqual(set(datos['radios'].keys()), {'lista', 'estilo', 'papel', 'alfa'})
            self.assertEqual(datos['radios']['estilo'], estilo)
            self.assertRegex(datos['radios']['papel'], r'^#[0-9a-f]{6}$')
            self.assertGreater(len(datos['trazos']), 0)

    def test_estilo_desconocido_falla_claro(self):
        with self.assertRaises(ValueError):
            pintor.pintar(self.foto, estilo='acrilico')

    def test_ajuste_desconocido_falla_claro(self):
        with self.assertRaises(TypeError):
            pintor.pintar(self.foto, radio_gordo=99)  # nombre inventado, no es de ningún estilo

    def test_acuarela_tiene_menos_pinceladas_que_oleo(self):
        oleo = pintor.pintar(self.foto, salida=os.path.join(self.d, 'oleo'), ancho=150,
                              semilla=7, estilo='oleo', avisar=lambda *a: None)
        acuarela = pintor.pintar(self.foto, salida=os.path.join(self.d, 'acuarela'), ancho=150,
                                  semilla=7, estilo='acuarela', avisar=lambda *a: None)
        self.assertLess(acuarela['pinceladas'], oleo['pinceladas'],
                         'acuarela: radios más gordos y menos capas que óleo — debe salir con menos pinceladas')

    def test_acuarela_deja_el_papel_donde_no_llega_ninguna_pincelada(self):
        # radios pequeños a propósito (frente a los 40,22,12,7 por defecto): con el pincel
        # grande de serie, un puñado de trazos ya cubre el lienzo entero y la prueba sería
        # vacía (medido: 0 px sin trazo con los parámetros por defecto en este lienzo).
        r = pintor.pintar(self.foto, salida=os.path.join(self.d, 'acuarela_chica'), ancho=150,
                           semilla=7, estilo='acuarela', radios=[10, 5], umbral=[130, 110],
                           longitud=[3, 3], avisar=lambda *a: None)
        mascara, datos = _mascara_cubierta(r['trazos'])
        sin_pincelada = mascara == 0
        self.assertGreater(int(sin_pincelada.sum()), 0,
                            'la prueba necesita que quede AL MENOS un píxel sin ninguna pincelada')
        arr = np.asarray(Image.open(r['png']))
        papel = np.array(pintor._a_rgb(datos['radios']['papel']))
        self.assertTrue(np.all(arr[sin_pincelada] == papel),
                         'sin pincelada encima, el lienzo debe enseñar el papel tal cual, no otra cosa')

    def test_saturacion_cero_da_un_cuadro_en_grises(self):
        r = pintor.pintar(self.foto, salida=os.path.join(self.d, 'grises'), ancho=150, semilla=7,
                           estilo='oleo', saturacion=0.0, acabado=True, avisar=lambda *a: None)
        self.assertLess(_desviacion_entre_canales(r['png']), 2.0)

    def test_carbon_y_tinta_dan_gris_de_verdad(self):
        for estilo in ('carbon', 'tinta'):
            r = pintor.pintar(self.foto, salida=os.path.join(self.d, estilo), ancho=150,
                               semilla=7, estilo=estilo, avisar=lambda *a: None)
            self.assertLess(_desviacion_entre_canales(r['png']), 2.0,
                             f'{estilo}: satura a 0 — debe salir gris de verdad (R=G=B), no solo apagado')

    def test_carbon_tramado_no_rompe_el_motor_y_admite_acabado_y_suave(self):
        # --acabado/--suave valen para cualquier estilo (T3.2): una capa de más, o el doble de
        # tamaño con reducción al final — nunca crashean con el tramado a 45° de carbon.
        sin = pintor.pintar(self.foto, salida=os.path.join(self.d, 'carbon_sin'), ancho=150,
                             semilla=5, estilo='carbon', acabado=False, avisar=lambda *a: None)
        con = pintor.pintar(self.foto, salida=os.path.join(self.d, 'carbon_con'), ancho=150,
                             semilla=5, estilo='carbon', acabado=True, avisar=lambda *a: None)
        self.assertGreater(con['pinceladas'], sin['pinceladas'])
        suave = pintor.pintar(self.foto, salida=os.path.join(self.d, 'carbon_suave'), ancho=150,
                               semilla=5, estilo='carbon', supermuestreo=2, avisar=lambda *a: None)
        with Image.open(sin['png']) as im1, Image.open(suave['png']) as im2:
            self.assertEqual(im1.size, im2.size)

    def test_tinta_deja_mas_de_la_mitad_del_lienzo_como_el_papel_en_foto_clara(self):
        clara = _foto_clara(os.path.join(self.d, 'foto_clara.png'))
        r = pintor.pintar(clara, salida=os.path.join(self.d, 'tinta'), ancho=150, semilla=7,
                           estilo='tinta', avisar=lambda *a: None)
        arr = np.asarray(Image.open(r['png']))
        blanco = np.all(arr == 255, axis=2).mean()
        self.assertGreater(blanco, 0.5,
                            'tinta + foto clara: el umbral alto sobre papel blanco debe dejar sin '
                            'pintar más de la mitad del lienzo (medido: ~56%% con esta foto)')


if __name__ == '__main__':
    unittest.main()
