"""`lienzo.py`: operar con imágenes reales, sin modelo.
Ningún verbo de este fichero resuelve un proyecto de Claude Code salvo `borrar --metodo
taller` (no probado con red real: ver `test_imagen_buscar.py` para el patrón de servidor
local falso usado en el resto del paquete si algún día se cablea `taller.py` de verdad ahí),
así que aquí se importa `lienzo` directamente y se llama a sus funciones en proceso — más
rápido, sin subprocess, y sin riesgo de que un guion con `rutas.resolver()` a nivel de módulo
aborte el proceso de pruebas (`lienzo.py` no lo hace: se comprobó leyendo el código).

Casos mínimos de la tarea:
  - `fundir` con alfa 0 devuelve la primera imagen y con alfa 1 la segunda, píxel a píxel.
  - `collage` de 4 imágenes -> ancho pedido y 4 zonas no negras.
  - `restaurar` sube el contraste de una imagen "lavada" (medido, no afirmado).
  - `numeros` produce exactamente N entradas de paleta.
  - `borrar` sobre una imagen con textura y un rectángulo negro de 30x30 -> el error medio en
    esa zona baja por debajo de la mitad del error inicial (medido, no afirmado).
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'abyss'))

import numpy as np
from PIL import Image, ImageFilter

import ayudas as ay
import lienzo


def _tmp():
    return Path(tempfile.mkdtemp(prefix='abyss_lienzo_'))


def _img_plana(ruta, color, ancho=64, alto=48):
    Image.new('RGB', (ancho, alto), color).save(ruta)
    return ruta


def _img_ruido(ruta, ancho=64, alto=48, semilla=1):
    rnd = np.random.RandomState(semilla)
    arr = rnd.randint(0, 256, (alto, ancho, 3), dtype=np.uint8)
    Image.fromarray(arr, 'RGB').save(ruta)
    return ruta, arr


class Fundir(unittest.TestCase):
    def test_alfa_0_da_la_primera_y_alfa_1_la_segunda_pixel_a_pixel(self):
        d = _tmp()
        a = _img_ruido(d / 'a.png', semilla=1)[0]
        b = _img_ruido(d / 'b.png', semilla=2)[0]

        salida0 = lienzo.fundir(str(a), str(b), alfa=0.0, salida=str(d / 's0.png'))
        salida1 = lienzo.fundir(str(a), str(b), alfa=1.0, salida=str(d / 's1.png'))

        arr_a = np.asarray(Image.open(a))
        arr_b = np.asarray(Image.open(b))
        arr_s0 = np.asarray(Image.open(salida0))
        arr_s1 = np.asarray(Image.open(salida1))

        np.testing.assert_array_equal(arr_s0, arr_a, 'alfa=0 debe devolver la primera imagen tal cual')
        np.testing.assert_array_equal(arr_s1, arr_b, 'alfa=1 (modo mezcla) debe devolver la segunda tal cual')

    def test_modo_desconocido_da_valueerror(self):
        d = _tmp()
        a = _img_plana(d / 'a.png', (10, 20, 30))
        b = _img_plana(d / 'b.png', (200, 100, 50))
        with self.assertRaises(ValueError):
            lienzo.fundir(str(a), str(b), modo='no_existe')

    def test_mascara_degradado_h_da_valores_distintos_por_columna(self):
        d = _tmp()
        a = _img_plana(d / 'a.png', (0, 0, 0), ancho=100, alto=10)
        b = _img_plana(d / 'b.png', (255, 255, 255), ancho=100, alto=10)
        salida = lienzo.fundir(str(a), str(b), alfa=1.0, mascara='degradado_h', salida=str(d / 's.png'))
        arr = np.asarray(Image.open(salida))
        self.assertLess(arr[5, 0, 0], arr[5, 99, 0], 'a la izquierda debe quedar más oscuro que a la derecha')


class Doble(unittest.TestCase):
    def test_produce_png_del_tamano_de_la_primera(self):
        d = _tmp()
        a = _img_ruido(d / 'a.png', ancho=80, alto=40)[0]
        b = _img_ruido(d / 'b.png', ancho=50, alto=50, semilla=9)[0]
        salida = lienzo.doble(str(a), str(b), salida=str(d / 's.png'))
        with Image.open(salida) as im:
            self.assertEqual(im.size, (80, 40))


class Collage(unittest.TestCase):
    def test_cuatro_imagenes_dan_ancho_pedido_y_cuatro_zonas_no_negras(self):
        d = _tmp()
        colores = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]
        rutas = [str(_img_plana(d / f'{i}.png', c, ancho=100, alto=100)) for i, c in enumerate(colores)]
        salida = lienzo.collage(rutas, columnas=2, ancho=400, margen=10, fondo='#000000',
                                 salida=str(d / 'collage.png'))
        with Image.open(salida) as im:
            self.assertEqual(im.width, 400, 'el ancho del collage debe ser el pedido')
            arr = np.asarray(im)
        cell_w = cell_h = int((400 - 10 * 3) / 2)
        centros = [
            (10 + cell_h // 2, 10 + cell_w // 2),
            (10 + cell_h // 2, 10 + cell_w + 10 + cell_w // 2),
            (10 + cell_h + 10 + cell_h // 2, 10 + cell_w // 2),
            (10 + cell_h + 10 + cell_h // 2, 10 + cell_w + 10 + cell_w // 2),
        ]
        no_negras = [tuple(arr[y, x]) != (0, 0, 0) for y, x in centros]
        self.assertEqual(sum(no_negras), 4, 'las 4 celdas deben llevar color, no el fondo negro')

    def test_mosaico_sin_columnas_tambien_da_el_ancho_pedido(self):
        d = _tmp()
        colores = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
        rutas = [str(_img_plana(d / f'm{i}.png', c, ancho=120, alto=80)) for i, c in enumerate(colores)]
        salida = lienzo.collage(rutas, ancho=600, salida=str(d / 'mosaico.png'))
        with Image.open(salida) as im:
            self.assertEqual(im.width, 600)


class Degradado(unittest.TestCase):
    def test_direccion_abajo_oscurece_hacia_el_borde_inferior(self):
        d = _tmp()
        img = _img_plana(d / 'a.png', (200, 200, 200), ancho=40, alto=100)
        salida = lienzo.degradado(str(img), direccion='abajo', color='#000000', desde=0.5,
                                   salida=str(d / 's.png'))
        arr = np.asarray(Image.open(salida))
        self.assertGreater(arr[5, 20, 0], arr[95, 20, 0], 'arriba debe quedar más claro que abajo')

    def test_direccion_desconocida_da_valueerror(self):
        d = _tmp()
        img = _img_plana(d / 'a.png', (1, 2, 3))
        with self.assertRaises(ValueError):
            lienzo.degradado(str(img), direccion='diagonal')


class Restaurar(unittest.TestCase):
    def test_sube_el_contraste_de_una_imagen_lavada(self):
        d = _tmp()
        rnd = np.random.RandomState(3)
        base = rnd.randint(0, 256, (60, 80, 3), dtype=np.uint8).astype(np.float32)
        lavada = (base * 0.15 + 128).clip(0, 255).astype(np.uint8)  # rango comprimido a ~[128,166]
        ruta = d / 'lavada.png'
        Image.fromarray(lavada, 'RGB').save(ruta)

        r = lienzo.restaurar(str(ruta), salida=str(d / 'restaurada.png'), avisar=lambda *a: None)

        self.assertGreater(r['contraste_despues'], r['contraste_antes'],
                            'los niveles automáticos deben subir el contraste de una imagen lavada')
        self.assertTrue(os.path.exists(r['salida']))

    def test_sin_aranazos_sin_opencv_avisa_y_no_revienta(self):
        d = _tmp()
        img = _img_plana(d / 'a.png', (120, 130, 140), ancho=30, alto=30)
        avisos = []
        cv2_real = lienzo.cv2
        try:
            lienzo.cv2 = None  # simula "sin OpenCV" sin desinstalar nada de verdad
            r = lienzo.restaurar(str(img), salida=str(d / 's.png'),
                                  sin_aranazos=True, avisar=avisos.append)
        finally:
            lienzo.cv2 = cv2_real
        self.assertFalse(r['aranazos_reparados'])
        self.assertTrue(any('arañazos' in a and 'opencv' in a.lower() for a in avisos), avisos)


class RestaurarReduceRuidoDeVerdad(unittest.TestCase):
    """T2.lienzo (7-sep), fallo MEDIDO con una foto real degradada a propósito
    (viraje amarillo, contraste 0.55, ruido gaussiano sigma 9, desenfoque 0.8,
    12 arañazos; fuera de este repo): `restaurar --sin-aranazos` bajaba el
    error frente al original (44.7 -> 25.2) pero SU PROPIA métrica de ruido
    subía de 43.69 a 83.88 — los niveles
    automáticos estiraban el contraste (y con él, el grano) ANTES de que la
    reducción de ruido pudiera compensarlo, y la vara vieja (percentil de
    gradiente) además cambiaba de escala con el contraste, así que ni siquiera
    medía lo mismo antes y después. Aquí, con una foto SINTÉTICA degradada del
    mismo modo (terreno suave con variedad tonal amplia —para que el
    estiramiento de niveles se comporte como en una foto real, no como en un
    bloque de pocos tonos planos— más dos parches REALMENTE planos —para que
    la medida de ruido en bloques de 8 px mida ruido de verdad, no la
    pendiente de un degradado—, viraje + contraste reducido + ruido gaussiano
    + desenfoque): `--nitidez 0` porque afilar amplifica cualquier detalle
    fino que quede, ruido incluido — un efecto distinto y ya declarado del que
    arregla este fallo (el orden ruido-antes-que-niveles); con nitidez
    puesta, el "ruido no reducido" que reporta la propia función en ese caso
    es la salida HONESTA que pide el fallo, no un error. Verificado por
    mutación (deshaciendo el reordenado — ruido después de niveles, como
    antes— este test falla porque el ruido medido sube en vez de bajar;
    restaurado el orden, vuelve a verde)."""

    def _foto_sintetica_y_su_version_vieja(self, d, ancho=220, alto=170, semilla=11):
        yy, xx = np.mgrid[0:alto, 0:ancho].astype(np.float32)
        base = (128 + 60 * np.sin(xx / 25.0) + 50 * np.cos(yy / 19.0)
                 + 40 * np.sin((xx + yy) / 33.0) + 20 * np.sin(xx / 7.0) * np.cos(yy / 11.0))
        base = np.clip(base, 0, 255)
        # dos parches REALMENTE planos (como un trozo de cielo o de pared) para que
        # el percentil 20 de `_ruido_zonas_planas` tenga zonas sin absolutamente
        # ningún detalle de la escena donde medir solo ruido.
        base[10:60, 10:70] = 210.0
        base[100:150, 150:210] = 60.0
        original = np.stack([base, base, base], axis=-1).clip(0, 255).astype(np.uint8)
        ruta_original = d / 'original.png'
        Image.fromarray(original, 'RGB').save(ruta_original)

        arr = original.astype(np.float32)
        arr = (arr - 128) * 0.55 + 128  # contraste reducido, como una foto "lavada" por el tiempo
        arr[..., 0] += 25
        arr[..., 1] += 12  # viraje amarillo: sube rojo y verde, no azul
        rnd = np.random.RandomState(semilla)
        arr = arr + rnd.normal(0, 9, arr.shape).astype(np.float32)
        vieja = (Image.fromarray(arr.clip(0, 255).astype(np.uint8), 'RGB')
                 .filter(ImageFilter.GaussianBlur(radius=0.8)))
        ruta_vieja = d / 'vieja.png'
        vieja.save(ruta_vieja)
        return ruta_original, ruta_vieja

    def test_ruido_baja_y_error_baja_frente_al_original(self):
        d = _tmp()
        ruta_original, ruta_vieja = self._foto_sintetica_y_su_version_vieja(d)

        r = lienzo.restaurar(str(ruta_vieja), salida=str(d / 'restaurada.png'), sin_aranazos=True,
                              nitidez=0.0, avisar=lambda *a: None)

        self.assertLess(r['ruido_despues'], r['ruido_antes'],
                         f"el ruido medido no debe subir: {r['ruido_antes']} -> {r['ruido_despues']}")
        self.assertTrue(r['ruido_reducido'])

        original = np.asarray(Image.open(ruta_original)).astype(np.float32)
        vieja = np.asarray(Image.open(ruta_vieja)).astype(np.float32)
        restaurada = np.asarray(Image.open(r['salida'])).astype(np.float32)
        error_antes = np.abs(vieja - original).mean()
        error_despues = np.abs(restaurada - original).mean()
        self.assertLess(error_despues, error_antes,
                         f'el error frente al original debe bajar: {error_antes:.1f} -> {error_despues:.1f}')


class Numeros(unittest.TestCase):
    def _imagen_de_n_bloques(self, ruta, n, ancho=120, alto=90):
        colores = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0),
                   (255, 0, 255), (0, 255, 255), (128, 0, 0), (0, 128, 0)]
        assert n <= len(colores)
        arr = np.zeros((alto, ancho, 3), dtype=np.uint8)
        cols = math_ceil_sqrt(n)
        filas = math_ceil_div(n, cols)
        cw, ch = ancho // cols, alto // filas
        for i in range(n):
            fy, fx = divmod(i, cols)
            arr[fy * ch:(fy + 1) * ch, fx * cw:(fx + 1) * cw] = colores[i]
        Image.fromarray(arr, 'RGB').save(ruta)
        return ruta

    def test_produce_exactamente_n_entradas_de_paleta(self):
        d = _tmp()
        n = 6
        img = self._imagen_de_n_bloques(d / 'bloques.png', n)
        r = lienzo.numeros(str(img), colores=n, ancho=120, min_zona=10, salida=str(d / 'salida'))
        self.assertEqual(r['colores'], n)
        self.assertTrue(os.path.exists(r['plantilla']))
        self.assertTrue(os.path.exists(r['color']))

    def test_contorno_pinta_pixeles_en_la_frontera_entre_zonas(self):
        """Fallo "roza": los contornos de `numeros` no tenían falsador —
        medido por mutación (convertir `_dibujar_contornos` en un `return`
        inmediato, dejando la plantilla SIN ninguna línea entre zonas, que es
        lo único que la hace pintable), las 19 pruebas anteriores seguían en
        verde. Aquí se cuentan los píxeles del color de contorno
        (`(160, 160, 160)`, el valor por defecto de `_dibujar_contornos`) en el
        cuerpo de la plantilla (sin el pie de paleta) y se exige que haya al
        menos uno — la imagen sintética tiene bloques de color contiguos, así
        que SIEMPRE hay una frontera que dibujar."""
        d = _tmp()
        n = 4
        img = self._imagen_de_n_bloques(d / 'bloques3.png', n, ancho=120, alto=90)
        r = lienzo.numeros(str(img), colores=n, ancho=120, min_zona=10, salida=str(d / 'salida3'))
        plantilla = np.asarray(Image.open(r['plantilla']).convert('RGB'))
        cuerpo = plantilla[:90, :, :]  # sin el pie de paleta (los últimos 40 px)
        contorno = np.all(cuerpo == (160, 160, 160), axis=-1)
        # con el contorno de verdad, las dos fronteras (horizontal y vertical)
        # entre los 4 bloques suman ~210 píxeles en esta imagen; un `return`
        # inmediato deja como mucho el antialiasing incidental de algún número
        # (medido: 1 píxel) — el tope de 20 separa limpiamente ambos casos.
        self.assertGreater(int(contorno.sum()), 20,
                            'debe haber una frontera de verdad entre zonas, no ruido incidental')

    def test_con_salida_los_nombres_no_llevan_numeros_de_mas(self):
        """Fallo "roza" medido 7-sep: el docstring del módulo y `skills/imagen/
        SKILL.md` prometían, con `--salida base`, `<base>_numeros_plantilla.png`
        y `<base>_numeros_color.png` — MEDIDO: `numeros(..., salida='pn')` da
        de verdad `pn_plantilla.png`/`pn_color.png` (SIN el `_numeros` de más);
        `pn_numeros_plantilla.png` no existe. Este test fija el nombre EXACTO,
        no solo que algún fichero exista (lo que ya cubría la prueba de
        arriba)."""
        d = _tmp()
        n = 4
        img = self._imagen_de_n_bloques(d / 'bloques4.png', n, ancho=40, alto=30)
        base = str(d / 'pn')
        r = lienzo.numeros(str(img), colores=n, ancho=40, min_zona=5, salida=base)
        self.assertEqual(r['plantilla'], base + '_plantilla.png')
        self.assertEqual(r['color'], base + '_color.png')
        self.assertTrue(os.path.exists(base + '_plantilla.png'))
        self.assertTrue(os.path.exists(base + '_color.png'))
        self.assertFalse(os.path.exists(base + '_numeros_plantilla.png'),
                          'con --salida explícito, el "_numeros" NO debe añadirse de más')
        self.assertFalse(os.path.exists(base + '_numeros_color.png'))

    def test_sin_salida_los_nombres_si_llevan_numeros(self):
        """Contraprueba: SIN `--salida`, el nombre sí sale de la propia foto
        con `_numeros_plantilla.png`/`_numeros_color.png` — el `_numeros` de
        más solo sobra cuando `--salida` ya trae su propia base."""
        d = _tmp()
        n = 4
        img = self._imagen_de_n_bloques(d / 'bloques5.png', n, ancho=40, alto=30)
        r = lienzo.numeros(str(img), colores=n, ancho=40, min_zona=5)
        base_foto = os.path.splitext(str(img))[0]
        self.assertEqual(r['plantilla'], base_foto + '_numeros_plantilla.png')
        self.assertEqual(r['color'], base_foto + '_numeros_color.png')

    def test_etiquetado_puro_sin_opencv_da_el_mismo_numero_de_zonas(self):
        d = _tmp()
        n = 4
        img = self._imagen_de_n_bloques(d / 'bloques2.png', n, ancho=40, alto=30)
        cv2_real = lienzo.cv2
        try:
            lienzo.cv2 = None
            r = lienzo.numeros(str(img), colores=n, ancho=40, min_zona=5, salida=str(d / 'salida2'))
        finally:
            lienzo.cv2 = cv2_real
        self.assertEqual(r['colores'], n)
        self.assertEqual(r['zonas'], n, 'cada bloque de color es una única zona conexa')


class NumerosFusionaZonasPequenas(unittest.TestCase):
    """T2.lienzo (7-sep), fallo MEDIDO con una foto real de 768×768 (paisaje
    pintado, fuera de este repo): `numeros --colores 12 --ancho 1200` daba
    24157 zonas, y `--colores 8 --ancho 1200 --min-zona 400` daba 16255 — un
    libro de pintar por números de verdad tiene decenas o cientos de zonas,
    no miles: `--min-zona` descartaba el NÚMERO de la zona chica pero la
    dejaba ahí sin fundir, así que el contorno seguía lleno de islas. Aquí,
    sintético (sin la foto real: la suite no toca ficheros externos): 3
    bloques de color más ruido sal-y-pimienta en manchas de 3×3 (no de 1 solo
    píxel: MEDIDO en desarrollo — el filtro de moda por sí solo ya limpia el
    ruido de 1 píxel, así que un falsador con manchas de 1 píxel no distingue
    si lo que las quita es el filtro de moda o la fusión; con manchas de 3×3
    sí hace falta la fusión) deben dar exactamente 3 zonas tras `numeros`, no
    cientos ni docenas. Verificado por mutación: haciendo que
    `_fusionar_zonas_pequenas` devuelva `(etiquetas, num_zonas)` sin fundir
    nada (un `return` inmediato), este test falla (salían 15 zonas con esta
    semilla en vez de 3); restaurada la fusión, vuelve a verde."""

    def _bloques_con_ruido_sal_y_pimienta(self, ruta, ancho=240, alto=180, semilla=7,
                                            fraccion_ruido=0.08, tam_mancha=3):
        colores = [(220, 40, 40), (40, 200, 60), (40, 60, 220)]
        arr = np.zeros((alto, ancho, 3), dtype=np.uint8)
        tercio = ancho // 3
        for i, c in enumerate(colores):
            x0 = i * tercio
            x1 = ancho if i == 2 else (i + 1) * tercio
            arr[:, x0:x1] = c
        rnd = np.random.RandomState(semilla)
        n_ruido = int(ancho * alto * fraccion_ruido / (tam_mancha * tam_mancha))
        ys = rnd.randint(0, alto - tam_mancha, n_ruido)
        xs = rnd.randint(0, ancho - tam_mancha, n_ruido)
        elegido = rnd.randint(0, len(colores), n_ruido)
        for y, x, k in zip(ys.tolist(), xs.tolist(), elegido.tolist()):
            arr[y:y + tam_mancha, x:x + tam_mancha] = colores[k]
        Image.fromarray(arr, 'RGB').save(ruta)
        return ruta

    def test_tres_bloques_con_ruido_dan_tres_zonas_no_cientos(self):
        d = _tmp()
        img = self._bloques_con_ruido_sal_y_pimienta(d / 'ruido.png')
        r = lienzo.numeros(str(img), colores=3, ancho=240, salida=str(d / 'salida'))
        self.assertEqual(r['zonas'], 3,
                          f"deben quedar 3 zonas tras fundir el ruido sal-y-pimienta, salieron {r['zonas']}")


def math_ceil_sqrt(n):
    import math
    return math.ceil(math.sqrt(n))


def math_ceil_div(a, b):
    return -(-a // b)


@unittest.skipUnless(lienzo.cv2 is not None, 'OpenCV no disponible: borrar --metodo telea/ns lo necesita')
class Borrar(unittest.TestCase):
    def _imagen_con_textura_y_agujero(self, ruta, ancho=120, alto=120, semilla=5):
        rnd = np.random.RandomState(semilla)
        base = (rnd.rand(alto, ancho) * 40 + 100).astype(np.float32)  # textura suave de un solo tono
        arr = np.stack([base, base, base], axis=-1).astype(np.uint8)
        original = arr.copy()
        x, y, w, h = 40, 40, 30, 30
        arr[y:y + h, x:x + w] = 0
        Image.fromarray(arr, 'RGB').save(ruta)
        return ruta, original, (x, y, w, h)

    def test_borrar_reduce_el_error_en_la_zona_por_debajo_de_la_mitad(self):
        d = _tmp()
        ruta, original, (x, y, w, h) = self._imagen_con_textura_y_agujero(d / 'con_agujero.png')
        dañada = np.asarray(Image.open(ruta)).astype(np.float32)
        error_inicial = np.abs(dañada[y:y + h, x:x + w] - original[y:y + h, x:x + w]).mean()

        r = lienzo.borrar(str(ruta), caja=f'{x},{y},{w},{h}', metodo='telea', salida=str(d / 'reparada.png'),
                           avisar=lambda *a: None)
        reparada = np.asarray(Image.open(r['salida'])).astype(np.float32)
        error_final = np.abs(reparada[y:y + h, x:x + w] - original[y:y + h, x:x + w]).mean()

        self.assertLess(error_final, error_inicial / 2,
                         f'error inicial {error_inicial:.1f}, final {error_final:.1f}: debe bajar de la mitad')

    def test_ns_tambien_funciona(self):
        d = _tmp()
        ruta, original, (x, y, w, h) = self._imagen_con_textura_y_agujero(d / 'con_agujero2.png', semilla=8)
        r = lienzo.borrar(str(ruta), caja=f'{x},{y},{w},{h}', metodo='ns', salida=str(d / 'reparada2.png'),
                           avisar=lambda *a: None)
        self.assertTrue(os.path.exists(r['salida']))
        self.assertIn(r['metodo_usado'], ('telea', 'ns'))

    def test_mas_de_una_fuente_de_mascara_es_error(self):
        d = _tmp()
        ruta, _, _ = self._imagen_con_textura_y_agujero(d / 'x.png')
        with self.assertRaises(ValueError):
            lienzo.borrar(str(ruta), caja='0,0,5,5', color='#ffffff')

    def test_metodo_taller_sin_configurar_da_sin_dato(self):
        d = _tmp()
        ruta, _, (x, y, w, h) = self._imagen_con_textura_y_agujero(d / 'y.png')
        proj = _tmp()
        (proj / 'memory').mkdir(exist_ok=True)
        with self.assertRaises(RuntimeError) as ctx:
            lienzo.borrar(str(ruta), caja=f'{x},{y},{w},{h}', metodo='taller', mem=str(proj / 'memory'))
        self.assertIn('sin dato', str(ctx.exception))


@unittest.skipUnless(lienzo.cv2 is not None, 'OpenCV no disponible: borrar --metodo telea/ns lo necesita')
class BorrarAvisaBorronProbable(unittest.TestCase):
    """T2.lienzo (7-sep), fallo MEDIDO con fotos reales (fuera de este repo): una
    estación meteorológica de 240×350 px sobre matorral oscuro en una foto de
    2048×1536, y una cosechadora de 960×360 px en un montaje — el relleno
    clásico (`cv2.inpaint`) deja un borrón visible en los dos casos, y ni el
    docstring ni la skill lo avisaban: prometían "objetos pequeños", sin decir
    que un objeto grande o un fondo con textura fallan. Aquí, sintético: una
    imagen con textura fuerte y una caja grande debe llevar 'aviso'; una línea
    fina sobre fondo liso NO debe llevar aviso, y el error en la zona debe
    bajar a menos de la mitad (el caso en que el relleno clásico sí funciona,
    declarado en el docstring). Verificado por mutación: forzando que
    `_evaluar_aviso_borron` siempre devuelva `(None, {})`, el primer test de
    aquí abajo falla porque no hay 'aviso' donde tenía que haberlo; restaurada
    la medida, vuelve a verde."""

    def test_textura_fuerte_y_caja_grande_lleva_aviso(self):
        d = _tmp()
        rnd = np.random.RandomState(4)
        ancho, alto = 150, 150
        base = (rnd.rand(alto, ancho) * 255).astype(np.uint8)  # textura fuerte, sin estructura suave
        arr = np.stack([base, base, base], axis=-1)
        ruta = d / 'textura.png'
        Image.fromarray(arr, 'RGB').save(ruta)

        r = lienzo.borrar(str(ruta), caja='40,40,60,60', metodo='telea',
                           salida=str(d / 'borrada.png'), avisar=lambda *a: None)
        self.assertIsNotNone(r.get('aviso'), 'una caja grande sobre textura fuerte debe avisar de borrón probable')

    def test_linea_fina_sobre_fondo_liso_no_avisa_y_baja_el_error(self):
        d = _tmp()
        ancho, alto = 300, 300
        base = np.full((alto, ancho), 140, dtype=np.uint8)
        original = np.stack([base, base, base], axis=-1)
        arr = original.copy()
        fila0, grosor = 150, 2
        arr[fila0:fila0 + grosor, :] = 20  # una línea fina oscura (un cable), fondo liso alrededor
        ruta = d / 'linea.png'
        Image.fromarray(arr, 'RGB').save(ruta)

        r = lienzo.borrar(str(ruta), caja=f'0,{fila0},{ancho},{grosor}', metodo='telea',
                           salida=str(d / 'sin_linea.png'), avisar=lambda *a: None)
        self.assertIsNone(r.get('aviso'), f"una línea fina sobre fondo liso no debe avisar: {r.get('aviso')}")

        zona_original = original[fila0:fila0 + grosor, :].astype(np.float32)
        zona_dañada = arr[fila0:fila0 + grosor, :].astype(np.float32)
        reparada = np.asarray(Image.open(r['salida'])).astype(np.float32)
        zona_reparada = reparada[fila0:fila0 + grosor, :]
        error_inicial = np.abs(zona_dañada - zona_original).mean()
        error_final = np.abs(zona_reparada - zona_original).mean()
        self.assertLess(error_final, error_inicial / 2,
                         f'error inicial {error_inicial:.1f}, final {error_final:.1f}: debe bajar de la mitad')


class CLI(unittest.TestCase):
    """La CLI en sí (`_cli`, invocada por subprocess como la usaría un usuario) para las
    rutas que no necesitan proyecto ni red: parsing de argumentos y verbo desconocido."""

    def test_verbo_desconocido_sale_con_1(self):
        r = ay.ejecutar(ay.script('lienzo.py'), ['pastel', 'x'], dict(os.environ))
        self.assertEqual(r.returncode, 1)
        self.assertIn('verbo desconocido', r.stdout)

    def test_fundir_por_cli_escribe_el_fichero_pedido(self):
        d = _tmp()
        a = _img_plana(d / 'a.png', (10, 20, 30), ancho=20, alto=20)
        b = _img_plana(d / 'b.png', (200, 100, 50), ancho=20, alto=20)
        salida = d / 's.png'
        r = ay.ejecutar(ay.script('lienzo.py'),
                         ['fundir', str(a), str(b), '--alfa', '1', '--salida', str(salida)],
                         dict(os.environ))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(salida.exists())

    def test_borrar_sin_ninguna_mascara_sale_con_1(self):
        d = _tmp()
        img = _img_plana(d / 'a.png', (1, 2, 3))
        r = ay.ejecutar(ay.script('lienzo.py'), ['borrar', str(img)], dict(os.environ))
        self.assertEqual(r.returncode, 1)
        self.assertIn('--caja', r.stdout)

    @unittest.skipUnless(lienzo.cv2 is not None, 'OpenCV no disponible: borrar --metodo telea/ns lo necesita')
    def test_borrar_por_cli_imprime_json_con_salida_y_aviso(self):
        d = _tmp()
        img = _img_plana(d / 'a.png', (120, 130, 140), ancho=40, alto=40)
        salida = d / 's.png'
        r = ay.ejecutar(ay.script('lienzo.py'),
                         ['borrar', str(img), '--caja', '5,5,5,5', '--salida', str(salida)],
                         dict(os.environ))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        # `borrar` avisa por `print` (como `restaurar`) y LUEGO imprime el JSON: la
        # última línea de stdout es la que hay que parsear (mismo patrón que usan
        # otras pruebas de este paquete, p. ej. test_infografia.py).
        cuerpo = json.loads(r.stdout.strip().splitlines()[-1])
        self.assertEqual(cuerpo['salida'], str(salida))
        self.assertIn('aviso', cuerpo)


class DocstringNoSobreafirmaElTaller(unittest.TestCase):
    """Fallo "roza" medido 7-sep: la cabecera del docstring del módulo decía que
    `borrar --metodo taller` habla con un servidor "que TÚ tienes en tu propia
    máquina (nunca sale de casa)" — nada en el código garantiza eso:
    `_inpaint_taller()` manda la imagen a la URL tal cual venga de `taller_url`
    en `imagen_config.json`, sin comprobar que sea loopback ni red local. El
    propio módulo se corrige más abajo ("eso solo llega a la máquina que TÚ
    configures en `taller_url`") — es la cabecera la que debía decir lo mismo."""

    def test_cabecera_no_promete_nunca_sale_de_casa_sin_matiz(self):
        doc = lienzo.__doc__ or ''
        self.assertNotIn('nunca sale de casa)', doc)

    def test_cabecera_dice_que_depende_de_taller_url(self):
        doc = lienzo.__doc__ or ''
        self.assertIn('taller_url', doc)


if __name__ == '__main__':
    unittest.main()
