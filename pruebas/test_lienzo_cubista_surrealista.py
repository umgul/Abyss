"""`lienzo.py cubista`/`surrealista` (encargo 9-sep: "dos estilos pictóricos NUEVOS" para
rehacer el vídeo del David). Import directo de `lienzo` en proceso, como hace
`test_lienzo.py` (ningún verbo de aquí toca `mem` ni resuelve un proyecto de Claude Code).

Por qué un fichero aparte de `test_lienzo.py` y no más clases dentro de él: son dos verbos
grandes (triangulación, campo de deformación) con su propia batería de casos — separarlos
deja `test_lienzo.py` centrado en los verbos "clásicos" y este en los dos nuevos.

Casos mínimos de la tarea:
  - `cubista` produce PNG + facetas > 0; con desplazamiento=giro=0 las facetas cubren el
    100% del lienzo EXACTO (Delaunay de un conjunto de puntos que cubre el rectángulo
    entero no deja huecos); con desplazamiento > 0 la cobertura BAJA de forma medible (los
    huecos entre facetas movidas dejan ver el fondo) — así se falsa que el desplazamiento
    de verdad mueve algo, no solo que la función no revienta.
  - `surrealista` con fuerza=0 y viraje=0 devuelve la foto EXACTA (sin desplazamiento ni
    viraje, remuestrear con el campo idéntico a la rejilla original no debe tocar ni un
    píxel); con fuerza>0 el desplazamiento medido sube con la fuerza pedida, y el viraje
    de tono se nota en la media del canal H.
  - los dos, sin OpenCV, no revientan (caen a su fallback declarado) — igual que
    `Numeros`/`Restaurar` en `test_lienzo.py`.
  - `--pasos N --pasos-dir DIR`: el ÚLTIMO paso es idéntico al PNG final, en los dos verbos.
"""
import json
import math
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'abyss'))

import numpy as np
from PIL import Image

import ayudas as ay
import lienzo


def _tmp():
    return Path(tempfile.mkdtemp(prefix='abyss_lienzo_cs_'))


def _foto_sintetica(ruta, ancho=180, alto=130):
    """Misma fórmula de degradado que usan `test_pintor_estilos.py`/`test_imagen_pintar.py`:
    reproducible, con gradiente real (para que Canny encuentre bordes de verdad) y las tres
    bandas de color distintas (para que un viraje de tono se note)."""
    img = Image.new('RGB', (ancho, alto))
    px = img.load()
    for y in range(alto):
        for x in range(ancho):
            px[x, y] = ((x * 3) % 256, (y * 5) % 256, ((x + y * 2) * 7) % 256)
    img.save(ruta)
    return ruta


def _foto_con_figura(ruta, ancho=220, alto=160):
    """Un rectángulo claro sobre fondo oscuro, con un borde NÍTIDO real (no un
    degradado) — para que `cv2.Canny`/el fallback de Sobel tengan un contorno de
    verdad que sembrar, como una figura recortada sobre su fondo."""
    arr = np.full((alto, ancho, 3), (30, 25, 40), dtype=np.uint8)
    arr[alto // 5:alto * 4 // 5, ancho // 4:ancho * 3 // 4] = (210, 190, 160)
    Image.fromarray(arr, 'RGB').save(ruta)
    return ruta


class Cubista(unittest.TestCase):
    def setUp(self):
        self.d = _tmp()
        self.foto = _foto_sintetica(self.d / 'foto.png')

    def test_produce_png_y_facetas(self):
        r = lienzo.cubista(str(self.foto), facetas=100, semilla=3, salida=str(self.d / 'c.png'))
        self.assertGreater(r['facetas'], 0)
        with open(r['salida'], 'rb') as fh:
            self.assertEqual(fh.read(8), b'\x89PNG\r\n\x1a\n')
        with Image.open(r['salida']) as im:
            self.assertEqual(im.size, Image.open(self.foto).size)

    def test_sin_desplazamiento_ni_giro_las_facetas_cubren_el_lienzo_entero(self):
        # medido en desarrollo con esta misma foto sintética: 0.0/0.0 -> cobertura 1.0
        # exacta (una Delaunay de puntos que ya cubren el rectángulo entero no deja
        # huecos); es el caso de referencia para el siguiente test.
        r = lienzo.cubista(str(self.foto), facetas=120, desplazamiento=0.0, giro=0.0,
                            semilla=5, salida=str(self.d / 'c_quieto.png'))
        self.assertEqual(r['cobertura_facetas'], 1.0,
                          'sin mover ni girar nada, la triangulación debe cubrir el 100% del lienzo')

    def test_mas_desplazamiento_baja_la_cobertura_de_forma_medible(self):
        # falsador de que "desplazamiento" mueve algo de verdad: si `cubista()` ignorase
        # el parámetro (p. ej. un `dx = dy = 0` fijo por error), las tres cifras saldrían
        # iguales a 1.0 y este test fallaría. Medido con esta foto: 0.0->1.0,
        # 0.07->0.9689, 0.25->0.845 (semilla 5, 120 facetas).
        quieto = lienzo.cubista(str(self.foto), facetas=120, desplazamiento=0.0, giro=0.0,
                                 semilla=5, salida=str(self.d / 'c0.png'))
        poco = lienzo.cubista(str(self.foto), facetas=120, desplazamiento=0.07, giro=7.0,
                               semilla=5, salida=str(self.d / 'c1.png'))
        mucho = lienzo.cubista(str(self.foto), facetas=120, desplazamiento=0.25, giro=20.0,
                                semilla=5, salida=str(self.d / 'c2.png'))
        self.assertGreater(quieto['cobertura_facetas'], poco['cobertura_facetas'])
        self.assertGreater(poco['cobertura_facetas'], mucho['cobertura_facetas'])

    def test_contorno_cambia_la_imagen_frente_a_sin_contorno(self):
        con = lienzo.cubista(str(self.foto), facetas=90, semilla=9, contorno=True,
                              salida=str(self.d / 'con.png'))
        sin = lienzo.cubista(str(self.foto), facetas=90, semilla=9, contorno=False,
                              salida=str(self.d / 'sin.png'))
        arr_con = np.asarray(Image.open(con['salida'])).astype(np.int16)
        arr_sin = np.asarray(Image.open(sin['salida'])).astype(np.int16)
        self.assertFalse(np.array_equal(arr_con, arr_sin),
                          '--sin-contorno debe cambiar de verdad el PNG (quita la línea de junta)')

    def test_bordes_reales_siembran_mas_facetas_donde_hay_un_contorno_nitido(self):
        # con una figura de bordes nítidos, los puntos semilla de _puntos_de_bordes
        # deben caer sobre el contorno del rectángulo (no en cualquier sitio): se
        # comprueba indirectamente pidiendo pocas facetas y viendo que salen puntos
        # de borde de verdad (más de la mitad de los pedidos, con esta figura de
        # bordes limpios) en vez de quedarse vacíos por falta de bordes que Canny
        # pueda encontrar.
        foto = _foto_con_figura(self.d / 'figura.png')
        gris = np.asarray(Image.open(foto).convert('L'))
        rnd = np.random.RandomState(1)
        pts = lienzo._puntos_de_bordes(gris, 40, rnd)
        self.assertGreater(len(pts), 20, 'una figura con un borde nítido de verdad debe dar bastantes puntos de borde')

    def test_facetas_pedidas_de_mas_en_una_foto_minuscula_no_revienta(self):
        # una foto de 12x10 con 500 facetas pedidas: MEDIDO — salen 0 facetas válidas
        # (los triángulos que caben en un lienzo tan pequeño quedan todos por debajo
        # del umbral de área de 3 px² que descarta esquirlas degeneradas), no un
        # error. "No revienta" es el caso a probar aquí, no un mínimo de facetas: con
        # un lienzo de 120 px² no hay sitio material para 500 triángulos de verdad.
        chica = self.d / 'chica.png'
        Image.new('RGB', (12, 10), (80, 90, 100)).save(chica)
        r = lienzo.cubista(str(chica), facetas=500, salida=str(self.d / 'c_chica.png'))
        self.assertEqual(r['facetas'], 0)
        self.assertTrue(os.path.exists(r['salida']), 'debe escribir un PNG (el fondo) aunque no haya facetas')
        with Image.open(r['salida']) as im:
            self.assertEqual(im.size, (12, 10))

    def test_sin_opencv_cae_a_la_rejilla_y_no_revienta(self):
        cv2_real = lienzo.cv2
        try:
            lienzo.cv2 = None
            r = lienzo.cubista(str(self.foto), facetas=80, semilla=2, salida=str(self.d / 'c_sin_cv2.png'))
        finally:
            lienzo.cv2 = cv2_real
        self.assertGreater(r['facetas'], 0)
        with Image.open(r['salida']) as im:
            self.assertEqual(im.size, Image.open(self.foto).size)

    def test_pasos_el_ultimo_es_identico_al_png_final(self):
        r = lienzo.cubista(str(self.foto), facetas=70, semilla=4, salida=str(self.d / 'c_pasos.png'),
                            pasos=5, pasos_dir=str(self.d / 'pasos'))
        self.assertEqual(len(r['pasos']), 5)
        final = np.asarray(Image.open(r['salida']))
        ultimo = np.asarray(Image.open(r['pasos'][-1]))
        np.testing.assert_array_equal(final, ultimo, 'el último paso debe ser exactamente el cuadro acabado')
        # y el PRIMER paso NO debe ser una copia del último: si `_dibujar` ignorase
        # `hasta` (p. ej. por el fallo de reproducibilidad del jitter que describe el
        # comentario de `cubista()`), pasos[0] y pasos[-1] saldrían iguales.
        primero = np.asarray(Image.open(r['pasos'][0]))
        self.assertFalse(np.array_equal(primero, final),
                          'el primer paso (pocas facetas) no debe coincidir con el cuadro acabado')


class Surrealista(unittest.TestCase):
    def setUp(self):
        self.d = _tmp()
        self.foto = _foto_sintetica(self.d / 'foto.png')

    def test_produce_png_del_mismo_tamano(self):
        r = lienzo.surrealista(str(self.foto), fuerza=20, salida=str(self.d / 's.png'))
        with Image.open(r['salida']) as im, Image.open(self.foto) as orig:
            self.assertEqual(im.size, orig.size)

    def test_fuerza_y_viraje_cero_devuelve_la_foto_exacta(self):
        # falsador de que el campo/viraje de verdad son los que mueven la imagen: sin
        # fuerza ni viraje, remuestrear con un campo (0,0) y girar el tono 0 grados no
        # debe tocar ni un píxel.
        r = lienzo.surrealista(str(self.foto), fuerza=0.0, viraje=0.0, salida=str(self.d / 's0.png'))
        arr_orig = np.asarray(Image.open(self.foto))
        arr_out = np.asarray(Image.open(r['salida']))
        np.testing.assert_array_equal(arr_orig, arr_out, 'fuerza=0, viraje=0 debe devolver la foto tal cual')
        self.assertEqual(r['desplazamiento_medido'], 0.0)

    def test_mas_fuerza_sube_el_desplazamiento_medido(self):
        poca = lienzo.surrealista(str(self.foto), fuerza=10, escala=40, semilla=1, salida=str(self.d / 'sp.png'))
        mucha = lienzo.surrealista(str(self.foto), fuerza=40, escala=40, semilla=1, salida=str(self.d / 'sm.png'))
        self.assertLess(poca['desplazamiento_medido'], mucha['desplazamiento_medido'])

    def test_viraje_desplaza_el_tono_medio(self):
        # fuerza=0 para aislar el efecto de color del efecto de deformación: solo debe
        # cambiar el tono (canal H de HSV), no la posición de ningún píxel.
        sin_virar = lienzo.surrealista(str(self.foto), fuerza=0.0, viraje=0.0, salida=str(self.d / 'sv0.png'))
        con_virar = lienzo.surrealista(str(self.foto), fuerza=0.0, viraje=60.0, salida=str(self.d / 'sv1.png'))
        h0 = np.asarray(Image.open(sin_virar['salida']).convert('HSV'))[..., 0].astype(np.float32)
        h1 = np.asarray(Image.open(con_virar['salida']).convert('HSV'))[..., 0].astype(np.float32)
        esperado = 60.0 / 360.0 * 255  # lo que `_virar_tono` desplaza el canal H de Pillow (0-255)
        diferencia_circular = np.minimum(np.abs(h1 - h0), 256 - np.abs(h1 - h0))
        self.assertLess(abs(float(diferencia_circular.mean()) - esperado), 2.0,
                         f'el tono medio debe moverse ~{esperado:.1f} (0-255), salió {diferencia_circular.mean():.1f}')

    def test_sin_opencv_cae_al_bilineal_propio_y_no_revienta(self):
        cv2_real = lienzo.cv2
        try:
            lienzo.cv2 = None
            r = lienzo.surrealista(str(self.foto), fuerza=15, escala=25, salida=str(self.d / 's_sin_cv2.png'))
        finally:
            lienzo.cv2 = cv2_real
        self.assertGreater(r['desplazamiento_medido'], 0.0)
        with Image.open(r['salida']) as im:
            self.assertEqual(im.size, Image.open(self.foto).size)

    def test_pasos_el_ultimo_es_identico_al_png_final(self):
        r = lienzo.surrealista(str(self.foto), fuerza=18, escala=35, viraje=30, salida=str(self.d / 's_pasos.png'),
                                pasos=5, pasos_dir=str(self.d / 'pasos'))
        self.assertEqual(len(r['pasos']), 5)
        final = np.asarray(Image.open(r['salida']))
        ultimo = np.asarray(Image.open(r['pasos'][-1]))
        np.testing.assert_array_equal(final, ultimo)
        primero = np.asarray(Image.open(r['pasos'][0])).astype(np.float32)
        original = np.asarray(Image.open(self.foto)).astype(np.float32)
        # el primer paso (t = 1/pasos) debe estar MÁS CERCA del original que el final
        # (t = 1): la progresión de verdad empieza casi intacta.
        err_primero = np.abs(primero - original).mean()
        err_final = np.abs(final.astype(np.float32) - original).mean()
        self.assertLess(err_primero, err_final)


class CLI(unittest.TestCase):
    def setUp(self):
        self.d = _tmp()
        self.foto = _foto_sintetica(self.d / 'foto.png', ancho=100, alto=80)

    def test_verbos_nuevos_aparecen_en_el_mensaje_de_verbo_desconocido(self):
        r = ay.ejecutar(ay.script('lienzo.py'), ['no_existe', 'x'], dict(os.environ))
        self.assertEqual(r.returncode, 1)
        self.assertIn('cubista', r.stdout)
        self.assertIn('surrealista', r.stdout)

    def test_cubista_por_cli_escribe_el_fichero_pedido(self):
        salida = self.d / 'c_cli.png'
        r = ay.ejecutar(ay.script('lienzo.py'),
                         ['cubista', str(self.foto), '--facetas', '60', '--salida', str(salida)],
                         dict(os.environ))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(salida.exists())
        cuerpo = json.loads(r.stdout.strip().splitlines()[-1])
        self.assertGreater(cuerpo['facetas'], 0)

    def test_surrealista_por_cli_escribe_el_fichero_pedido(self):
        salida = self.d / 's_cli.png'
        r = ay.ejecutar(ay.script('lienzo.py'),
                         ['surrealista', str(self.foto), '--fuerza', '15', '--salida', str(salida)],
                         dict(os.environ))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(salida.exists())

    def test_cubista_necesita_una_foto(self):
        r = ay.ejecutar(ay.script('lienzo.py'), ['cubista'], dict(os.environ))
        self.assertEqual(r.returncode, 1)
        self.assertIn('cubista necesita una foto', r.stdout)

    def test_surrealista_necesita_una_foto(self):
        r = ay.ejecutar(ay.script('lienzo.py'), ['surrealista'], dict(os.environ))
        self.assertEqual(r.returncode, 1)
        self.assertIn('surrealista necesita una foto', r.stdout)


if __name__ == '__main__':
    unittest.main()
