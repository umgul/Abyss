"""`kinetica.py`: despiece por COMPONENTES REALES de una foto (no capas de nitidez, ver
`volumen.py`), montado para el visor 3D de `abyss/plantillas/kinetica.html` (leída, no
tocada por estas pruebas). No llama a `rutas.resolver()` ni lee stdin (guion de fichero a
fichero, como `volumen.py`/`render3d.py`): se importa DIRECTAMENTE en el proceso de la
prueba, mismo patrón que `test_volumen.py`.

La imagen es sintética y GEOMÉTRICA a propósito (dos rectángulos de color plano, bien
separados, sobre un fondo liso de otro color, dibujados con `cv2`): así se sabe de
antemano que GrabCut debe separarlos del fondo y que, sin regiones, deben salir como DOS
componentes conexos distintos (no se tocan entre sí).

`opencv-python`/`numpy`/`Pillow` SÍ están instalados en la máquina de desarrollo (medido):
no hay aquí una prueba de "sin dependencia" — ese patrón ya lo cubren
`test_imagen_dependencias_opcionales.py`/`test_volumen.py` para el resto del paquete.

NINGUNA prueba de aquí abre una cámara ni un navegador: `montar()` nunca los toca, y las
pruebas que ejercitan la CLI (`kinetica._cli`) usan siempre `--solo-montar`, que por
diseño de `_cli` (ver su código) vuelve ANTES de llamar a `servir()` — reforzado abajo
parcheando `kinetica.servir` para comprobar que, en efecto, nunca se invoca.

`ContratoConLaPlantillaDeVerdad`, al final: las clases de arriba solo comprueban que
`kinetica.py` es coherente CONSIGO MISMO (abren la ruta que el propio módulo eligió y el
nombre que el propio módulo escribió) — nunca abren `abyss/plantillas/kinetica.html` ni
contrastan una sola clave contra lo que ELLA pide. Esa clase sí lee la plantilla de
verdad, extrae con regex sobre su `<script>` lo que exige (`fetch('...')`,
`carg.load('...')` literales y el uso de `p.png` por pieza) y lo contrasta contra una
carpeta montada de verdad, para que cambiar la plantilla o el módulo sin el otro rompa
esta prueba en vez de romper la pantalla."""
import importlib.util
import io
import json
import os
import re
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ayudas as ay  # noqa: E402

sys.path.insert(0, str(ay.PKG))

try:
    import cv2
    import numpy as np
    from PIL import Image
    import kinetica
except ImportError:
    cv2 = None
    np = None
    Image = None
    kinetica = None


def _nueva_carpeta_temporal():
    """Directorio temporal cualquiera (no una memoria de proyecto: `kinetica.py` no llama
    a `rutas.resolver()`, ver su docstring), borrado al final de cada prueba."""
    return Path(tempfile.mkdtemp(prefix='abyss_kinetica_'))


# ───────────────────────────────── imagen sintética ─────────────────────────────────

# Dos rectángulos de color plano, bien separados entre sí y muy distintos del fondo: así
# GrabCut (rectángulo con margen) los separa del fondo de una, y connectedComponents los
# deja como DOS piezas (no se tocan). Tamaños generosos (>=90 px de lado) para que el
# núcleo erosionado de `_mascara_cruda_de_region` (18% del lado corto) no se quede vacío.
ANCHO_IMG, ALTO_IMG = 420, 260
RECT_A = (30, 40, 150, 200)     # x0,y0,x1,y1 — pieza "a"
RECT_B = (250, 60, 390, 220)    # pieza "b"


def _imagen_dos_piezas(ruta):
    img = np.full((ALTO_IMG, ANCHO_IMG, 3), (25, 25, 25), np.uint8)   # fondo oscuro liso
    cv2.rectangle(img, RECT_A[:2], RECT_A[2:], (60, 170, 60), -1)     # verde
    cv2.rectangle(img, RECT_B[:2], RECT_B[2:], (170, 60, 60), -1)     # azul
    cv2.imwrite(str(ruta), img)
    return ruta


def _poligono_de_caja(caja):
    x0, y0, x1, y1 = caja
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


def _regiones_json(ruta):
    regiones = [
        {'clave': 'pieza_a', 'titulo': 'Pieza A', 'poligono': _poligono_de_caja(RECT_A),
         'rumbo': [-1.0, 0.0, 0.2], 'orden': 0, 'prioridad': 0},
        {'clave': 'pieza_b', 'titulo': 'Pieza B', 'poligono': _poligono_de_caja(RECT_B),
         'rumbo': [1.0, 0.0, 0.2], 'orden': 1, 'prioridad': 0},
    ]
    with open(ruta, 'w', encoding='utf-8') as fh:
        json.dump(regiones, fh)
    return ruta


@unittest.skipIf(kinetica is None, 'opencv-python/numpy/Pillow no disponibles en esta máquina')
class ConRegionesSalenLasDosPiezas(unittest.TestCase):
    def setUp(self):
        self.tmp = _nueva_carpeta_temporal()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.imagen = _imagen_dos_piezas(self.tmp / 'foto.png')
        self.regiones = _regiones_json(self.tmp / 'regiones.json')
        self.salida = self.tmp / 'montado'

    def test_dos_png_con_alfa_y_piezas_json_coherente(self):
        avisos = []
        r = kinetica.montar(str(self.imagen), regiones_json=str(self.regiones),
                             salida=str(self.salida), avisar=avisos.append)

        self.assertEqual(r['modo'], 'manual')
        self.assertEqual(sorted(r['piezas']), ['pieza_a', 'pieza_b'])

        for clave in ('pieza_a', 'pieza_b'):
            ruta_png = self.salida / 'piezas' / f'{clave}.png'
            self.assertTrue(ruta_png.is_file(), f'falta {ruta_png}')
            with Image.open(ruta_png) as im:
                self.assertEqual(im.mode, 'RGBA', f'{clave}.png debería llevar canal alfa')
                self.assertGreater(im.size[0] * im.size[1], 0)

        # piezas.json vive DENTRO de piezas/ (kinetica.html: fetch('piezas/piezas.json')),
        # nunca en la raíz de la carpeta servida.
        ruta_json = self.salida / 'piezas' / 'piezas.json'
        self.assertTrue(ruta_json.is_file())
        self.assertFalse((self.salida / 'piezas.json').is_file(),
                          'piezas.json NO debe quedar también en la raíz')
        ficha = json.loads(ruta_json.read_text(encoding='utf-8'))
        self.assertEqual(ficha['ancho'], ANCHO_IMG)
        self.assertEqual(ficha['alto'], ALTO_IMG)
        self.assertEqual(ficha['procedencia']['modo'], 'manual')
        self.assertEqual(ficha['original'], 'original.jpg')
        self.assertTrue((self.salida / ficha['original']).is_file())

        self.assertEqual(len(ficha['piezas']), 2)
        claves = {p['clave'] for p in ficha['piezas']}
        self.assertEqual(claves, {'pieza_a', 'pieza_b'})
        campos = {'clave', 'titulo', 'orden', 'caja_px', 'centro', 'tam_frac', 'rumbo',
                  'png', 'area_px', 'relleno_px'}
        for p in ficha['piezas']:
            self.assertEqual(set(p.keys()), campos, p)
            self.assertEqual(len(p['centro']), 2)
            self.assertTrue(all(0.0 <= v <= 1.0 for v in p['centro']), p['centro'])
            self.assertEqual(len(p['tam_frac']), 2)
            self.assertTrue(all(0.0 < v <= 1.0 for v in p['tam_frac']), p['tam_frac'])
            self.assertEqual(len(p['rumbo']), 3)
            self.assertGreater(p['area_px'], 0)
            self.assertEqual(p['relleno_px'], 0)  # sin --rellenar: nada inventado
            # 'png' es la ruta (URL, con "/") que kinetica.html usa en carg.load(p.png, ...)
            self.assertEqual(p['png'], f'piezas/{p["clave"]}.png')
            self.assertTrue((self.salida / 'piezas' / f'{p["clave"]}.png').is_file())

        # la carpeta de trabajo trae lo que la plantilla espera, además de piezas/piezas.json
        self.assertTrue((self.salida / 'three.min.js').is_file())
        self.assertTrue((self.salida / 'index.html').is_file())
        self.assertTrue((self.salida / 'mp' / 'vision_bundle.mjs').is_file())


@unittest.skipIf(kinetica is None, 'opencv-python/numpy/Pillow no disponibles en esta máquina')
class SinRegionesAvisaAutomatico(unittest.TestCase):
    def setUp(self):
        self.tmp = _nueva_carpeta_temporal()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.imagen = _imagen_dos_piezas(self.tmp / 'foto.png')
        self.salida = self.tmp / 'montado_auto'

    def test_avisa_automatico_y_no_finge_nombre_real(self):
        avisos = []
        r = kinetica.montar(str(self.imagen), salida=str(self.salida), avisar=avisos.append)

        self.assertEqual(r['modo'], 'automatico')
        self.assertTrue(any('AUTOMÁTICA' in a or 'automática' in a for a in avisos),
                         f'ningún aviso menciona el modo automático: {avisos}')

        ruta_json = self.salida / 'piezas' / 'piezas.json'
        ficha = json.loads(ruta_json.read_text(encoding='utf-8'))
        self.assertEqual(ficha['procedencia']['modo'], 'automatico')
        self.assertGreaterEqual(len(ficha['piezas']), 1)  # al menos separó algo del fondo
        for p in ficha['piezas']:
            self.assertIn('sin nombre real', p['titulo'])
            self.assertTrue(p['clave'].startswith('auto_'))


@unittest.skipIf(kinetica is None, 'opencv-python/numpy/Pillow no disponibles en esta máquina')
class CliSoloMontarNoSirveNada(unittest.TestCase):
    def setUp(self):
        self.tmp = _nueva_carpeta_temporal()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.imagen = _imagen_dos_piezas(self.tmp / 'foto.png')
        self.regiones = _regiones_json(self.tmp / 'regiones.json')
        self.salida = self.tmp / 'montado_cli'

    def test_solo_montar_nunca_llama_a_servir(self):
        argv = [str(self.imagen), '--regiones', str(self.regiones), '--salida',
                str(self.salida), '--solo-montar']
        with mock.patch.object(kinetica, 'servir') as servir_falso:
            buf = io.StringIO()
            with redirect_stdout(buf):
                codigo = kinetica._cli(argv)
        self.assertEqual(codigo, 0, buf.getvalue())
        servir_falso.assert_not_called()
        self.assertTrue((self.salida / 'piezas' / 'piezas.json').is_file())


@unittest.skipIf(kinetica is None, 'opencv-python/numpy/Pillow no disponibles en esta máquina')
class SinMpAvisaYSigueEnCodigoCero(unittest.TestCase):
    """`MP_VENDOR` se parchea a una ruta que NO existe, sin importar si esta instalación
    ya trae `abyss/vendor/mp/` de verdad (otra tanda) o no: así la prueba comprueba el
    camino "falta mp/" siempre, no solo por casualidad del estado actual del repo."""

    def setUp(self):
        self.tmp = _nueva_carpeta_temporal()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.imagen = _imagen_dos_piezas(self.tmp / 'foto.png')
        self.regiones = _regiones_json(self.tmp / 'regiones.json')
        self.salida = self.tmp / 'montado_sinmp'

    def test_aviso_de_mp_ausente_y_codigo_0(self):
        ruta_mp_inexistente = str(self.tmp / 'no_existe_mp')
        argv = [str(self.imagen), '--regiones', str(self.regiones), '--salida',
                str(self.salida), '--solo-montar']
        with mock.patch.object(kinetica, 'MP_VENDOR', ruta_mp_inexistente):
            buf = io.StringIO()
            with redirect_stdout(buf):
                codigo = kinetica._cli(argv)
        salida_texto = buf.getvalue()
        self.assertEqual(codigo, 0, salida_texto)
        self.assertIn('abyss/vendor/mp/', salida_texto)
        # el visor sigue montado, solo sin manos: el sustituto de vision_bundle.mjs existe
        ruta_stub = self.salida / 'mp' / 'vision_bundle.mjs'
        self.assertTrue(ruta_stub.is_file())
        self.assertIn('MediaPipe', ruta_stub.read_text(encoding='utf-8'))


# ───────────────── contrato con la plantilla real (no con lo que el módulo CREE) ─────────────────

_RUTA_PLANTILLA = Path(ay.PKG) / 'plantillas' / 'kinetica.html'
_RE_FETCH = re.compile(r"""fetch\(\s*['"]([^'"]+)['"]""")
_RE_CARGA_LITERAL = re.compile(r"""carg\.load\(\s*['"]([^'"]+)['"]""")
_RE_CARGA_POR_PIEZA = re.compile(r"""carg\.load\(\s*p\.png\b""")
# un fetch con method:'POST' en la MISMA llamada: eso es un verbo, no un fichero
_RE_VERBO = re.compile(r"""fetch\(\s*['"]([^'"]+)['"]\s*,\s*\{[^}]*method\s*:\s*['"]POST['"]""")


def _fetches_de_la_plantilla(texto):
    """`{ruta_literal: opcional}`, leído línea a línea del `<script>`. `opcional` es
    `True` cuando el propio `fetch(...)` va envuelto en un `try { ... }` en esa misma
    línea (así declara la plantilla `fichas.json`: lo intenta y sigue con `{}` si
    falta — `kinetica.py` documenta ese fichero como opcional). Cualquier otro
    `fetch(...)` de la plantilla es, por tanto, obligatorio.

    Los VERBOS quedan fuera: ver `_verbos_de_la_plantilla`."""
    verbos = set(_verbos_de_la_plantilla(texto))
    vistos = {}
    for linea in texto.splitlines():
        for m in _RE_FETCH.finditer(linea):
            if m.group(1) in verbos:
                continue
            vistos[m.group(1)] = 'try' in linea[:m.start()]
    return vistos


def _verbos_de_la_plantilla(texto):
    """Las rutas que la plantilla pide por POST. NO son ficheros y por eso no se les
    puede exigir que existan en la carpeta montada: son órdenes que atiende el servidor
    (hoy `/abrir-enlace`, que abre el sitio oficial FUERA de la ventana para no llevarse
    la escena por delante). Se les exige otra cosa, más fuerte, en su propia prueba: que
    el servidor de `kinetica.py` las conteste de verdad."""
    return sorted({m.group(1) for m in _RE_VERBO.finditer(texto)})


def _cargas_literales_de_la_plantilla(texto):
    return sorted({m.group(1) for m in _RE_CARGA_LITERAL.finditer(texto)})


@unittest.skipIf(kinetica is None, 'opencv-python/numpy/Pillow no disponibles en esta máquina')
class ContratoConLaPlantillaDeVerdad(unittest.TestCase):
    """Monta una carpeta de verdad con `kinetica.montar()` y la contrasta con lo que
    `abyss/plantillas/kinetica.html` DE VERDAD pide (leída y parseada aquí, nunca
    tocada) — no con lo que `kinetica.py` cree haber escrito. Ver docstring del
    módulo."""

    def setUp(self):
        self.assertTrue(_RUTA_PLANTILLA.is_file(), f'no existe {_RUTA_PLANTILLA}')
        self.texto = _RUTA_PLANTILLA.read_text(encoding='utf-8')
        self.tmp = _nueva_carpeta_temporal()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        imagen = _imagen_dos_piezas(self.tmp / 'foto.png')
        regiones = _regiones_json(self.tmp / 'regiones.json')
        self.salida = self.tmp / 'montado_contrato'
        kinetica.montar(str(imagen), regiones_json=str(regiones), salida=str(self.salida),
                         avisar=lambda *_: None)

    def test_cada_fetch_obligatorio_de_la_plantilla_existe_en_lo_montado(self):
        fetches = _fetches_de_la_plantilla(self.texto)
        self.assertTrue(fetches, 'no se encontró ningún fetch(...) en el <script> de la '
                                  'plantilla: ¿cambió el patrón que busca esta prueba?')
        for ruta, opcional in fetches.items():
            if opcional:
                continue
            with self.subTest(ruta=ruta):
                self.assertTrue(
                    (self.salida / ruta).is_file(),
                    f'la plantilla pide fetch({ruta!r}) sin try/catch (recurso obligatorio) '
                    f'y no está en {self.salida}')

    def test_cada_verbo_de_la_plantilla_lo_atiende_el_servidor(self):
        """Un POST de la plantilla no es un fichero: es una orden. Aquí no basta con que
        no exista en la carpeta — se levanta el servidor DE VERDAD sobre lo montado y se
        comprueba que contesta a ese verbo y solo a ese. Sin esto, la plantilla podría
        pedir un verbo que nadie implementa y todas las demás pruebas seguirían verdes."""
        import http.client
        import threading
        from http.server import ThreadingHTTPServer
        verbos = _verbos_de_la_plantilla(self.texto)
        self.assertTrue(verbos, 'la plantilla no pide ningún verbo por POST: ¿cambió el '
                                'patrón que busca esta prueba?')
        srv = ThreadingHTTPServer(('127.0.0.1', 0),
                                  kinetica._elegir_manejador(str(self.salida)))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.shutdown)
        puerto = srv.server_address[1]
        try:
            for ruta in verbos:
                with self.subTest(verbo=ruta):
                    self.assertFalse((self.salida / ruta.lstrip('/')).exists(),
                                     f'{ruta} es un verbo, no debería existir como fichero')
                    c = http.client.HTTPConnection('127.0.0.1', puerto, timeout=5)
                    c.request('POST', ruta, body=b'', headers={'Content-Length': '0'})
                    self.assertEqual(c.getresponse().status, 200,
                                     f'el servidor no atiende POST {ruta}')
                    c.close()
            # y NO atiende cualquier otra cosa: la lista es blanca, no un cajón abierto
            c = http.client.HTTPConnection('127.0.0.1', puerto, timeout=5)
            c.request('POST', '/lo-que-sea', body=b'', headers={'Content-Length': '0'})
            self.assertEqual(c.getresponse().status, 404,
                             'el servidor acepta POST a rutas que nadie declaró')
            c.close()
        finally:
            srv.server_close()

    def test_cada_textura_literal_de_la_plantilla_existe_en_lo_montado(self):
        literales = _cargas_literales_de_la_plantilla(self.texto)
        self.assertTrue(literales, "no se encontró ningún carg.load('...') literal en la "
                                    "plantilla: ¿cambió el patrón que busca esta prueba?")
        for ruta in literales:
            with self.subTest(ruta=ruta):
                self.assertTrue((self.salida / ruta).is_file(),
                                 f"la plantilla pide carg.load({ruta!r}) y no está en {self.salida}")

    def test_plantilla_usa_p_png_y_piezas_json_lo_declara_por_pieza(self):
        """La plantilla carga la textura de CADA pieza con `carg.load(p.png, ...)` (no
        un literal): eso exige que cada objeto de `piezas.json` traiga un campo `png`
        con una ruta que exista de verdad — nadie más lo garantiza."""
        self.assertRegex(
            self.texto, _RE_CARGA_POR_PIEZA,
            'la plantilla ya no carga la textura de cada pieza con "p.png": revisar qué '
            'campo espera ahora y actualizar esta prueba (no asumirlo)')

        fetches = _fetches_de_la_plantilla(self.texto)
        rutas_piezas_json = [r for r in fetches if r.endswith('piezas.json')]
        self.assertEqual(len(rutas_piezas_json), 1,
                          f'se esperaba un único fetch(...) a *piezas.json en la plantilla, '
                          f'hay {rutas_piezas_json}')
        ruta_piezas_json = self.salida / rutas_piezas_json[0]
        self.assertTrue(ruta_piezas_json.is_file(),
                         f'piezas.json no está donde la plantilla lo pide: {ruta_piezas_json}')

        ficha = json.loads(ruta_piezas_json.read_text(encoding='utf-8'))
        self.assertTrue(ficha.get('piezas'), 'piezas.json sin piezas: no se puede comprobar "png"')
        for p in ficha['piezas']:
            with self.subTest(clave=p.get('clave')):
                self.assertIn('png', p, f'la pieza {p.get("clave")!r} no trae el campo "png" '
                                        'que pide carg.load(p.png, ...) en la plantilla')
                self.assertTrue(
                    (self.salida / p['png']).is_file(),
                    f'{p.get("clave")!r}: png={p.get("png")!r} no existe en {self.salida}')


# ───────────────────────────────── orden: ordena, no numera ─────────────────────────────────

def _regiones_json_con_ordenes(ruta, orden_a, orden_b):
    """Mismas dos piezas de `_regiones_json`, pero con los `orden` crudos que se pidan —
    para probar que `kinetica.py` los usa solo para ORDENAR, nunca los copia tal cual al
    `piezas.json` de salida."""
    regiones = [
        {'clave': 'pieza_a', 'titulo': 'Pieza A', 'poligono': _poligono_de_caja(RECT_A),
         'rumbo': [-1.0, 0.0, 0.2], 'orden': orden_a, 'prioridad': 0},
        {'clave': 'pieza_b', 'titulo': 'Pieza B', 'poligono': _poligono_de_caja(RECT_B),
         'rumbo': [1.0, 0.0, 0.2], 'orden': orden_b, 'prioridad': 0},
    ]
    with open(ruta, 'w', encoding='utf-8') as fh:
        json.dump(regiones, fh)
    return ruta


@unittest.skipIf(kinetica is None, 'opencv-python/numpy/Pillow no disponibles en esta máquina')
class OrdenSeReindexaAlSalir(unittest.TestCase):
    """El `orden` del fichero de regiones solo ORDENA: puede numerar 1,2,3 o dejar huecos,
    pero `kinetica.html` lo usa como índice DENSO 0..N-1 (`piezas.find(q => q.dato.orden
    === objetivo.aislada-1)` al aislar por dedos extendidos) — con un `orden` no denso ese
    `find` no encuentra nada, devuelve `undefined` y el `.dato.titulo` siguiente revienta
    con TypeError en cada fotograma. Aquí se piden 5 y 2 (invertido y con huecos): la
    salida debe quedar 0/1, en el orden relativo pedido, nunca 5/2 tal cual."""

    def setUp(self):
        self.tmp = _nueva_carpeta_temporal()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.imagen = _imagen_dos_piezas(self.tmp / 'foto.png')
        # pieza_a pide orden 5, pieza_b pide orden 2: pieza_b va ANTES pese a ir segunda
        # en la lista, y ninguno de los dos valores crudos (5, 2) debe sobrevivir.
        self.regiones = _regiones_json_con_ordenes(self.tmp / 'regiones.json', 5, 2)
        self.salida = self.tmp / 'montado_orden'

    def test_orden_final_es_0_n_menos_1_conservando_el_orden_relativo(self):
        r = kinetica.montar(str(self.imagen), regiones_json=str(self.regiones),
                             salida=str(self.salida), avisar=lambda *_: None)
        self.assertEqual(sorted(r['piezas']), ['pieza_a', 'pieza_b'])

        ruta_json = self.salida / 'piezas' / 'piezas.json'
        ficha = json.loads(ruta_json.read_text(encoding='utf-8'))
        por_clave = {p['clave']: p['orden'] for p in ficha['piezas']}
        self.assertEqual(set(por_clave.values()), {0, 1},
                          f'"orden" debe quedar denso 0..N-1, salió {por_clave}')
        # pieza_b pidió el orden crudo MENOR (2 < 5): debe quedar primera (0)
        self.assertEqual(por_clave['pieza_b'], 0, por_clave)
        self.assertEqual(por_clave['pieza_a'], 1, por_clave)


# ───────────────────────────────── original.jpg siempre, recodificado si hace falta ─────────────────────────────────

@unittest.skipIf(kinetica is None, 'opencv-python/numpy/Pillow no disponibles en esta máquina')
class OriginalSiempreEsJpgYLoDeclaraSiRecodifica(unittest.TestCase):
    """La plantilla carga SIEMPRE 'original.jpg' de forma literal
    (`carg.load('original.jpg', ...)`, kinetica.html) — con una entrada .png (como la de
    estas pruebas) el módulo debe recodificar a JPEG, nunca dejar un 'original.png' que
    la plantilla no sabe pedir (y que solo "funcionaba" por casualidad cuando la entrada
    ya era .jpg)."""

    def setUp(self):
        self.tmp = _nueva_carpeta_temporal()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.imagen = _imagen_dos_piezas(self.tmp / 'foto.png')   # entrada .png a propósito
        self.regiones = _regiones_json(self.tmp / 'regiones.json')
        self.salida = self.tmp / 'montado_original'

    def test_entrada_png_sale_como_original_jpg_recodificada(self):
        kinetica.montar(str(self.imagen), regiones_json=str(self.regiones),
                         salida=str(self.salida), avisar=lambda *_: None)

        self.assertTrue((self.salida / 'original.jpg').is_file(),
                         'la plantilla pide literalmente original.jpg')
        self.assertFalse((self.salida / 'original.png').is_file(),
                          'no debe quedar un original.png que nadie pide')
        with Image.open(self.salida / 'original.jpg') as im:
            self.assertEqual(im.format, 'JPEG')

        ficha = json.loads((self.salida / 'piezas' / 'piezas.json').read_text(encoding='utf-8'))
        self.assertEqual(ficha['original'], 'original.jpg')
        self.assertIn('recodific', ficha['procedencia']['original'].lower(),
                       f'procedencia.original no declara la recodificación: {ficha["procedencia"]}')


# ───────────────────────────────── aviso de mp/ ausente: cita el comando real ─────────────────────────────────

@unittest.skipIf(kinetica is None, 'opencv-python/numpy/Pillow no disponibles en esta máquina')
class MensajeMediapipeCitaElComandoDelInstalador(unittest.TestCase):
    """El aviso de "falta mp/" debe mandar al comando de UNA línea que el propio paquete
    ya trae (`python instalar.py --manos`, ver `instalar.COMANDO_DESCARGAR_MANOS`), no a
    un procedimiento manual con npm/tar/Node.js — `instalar.py --manos` ya baja los seis
    ficheros él mismo, con `urllib`, sin Node.js. Se carga `instalar.py` DIRECTAMENTE por
    ruta de fichero, con su propio nombre de módulo (mismo patrón que
    `test_instalador_kinetica.py`, para no chocar si otra prueba lo carga en el mismo
    proceso de `unittest`)."""

    def test_mensaje_cita_el_comando_real_y_no_manda_a_npm_ni_node(self):
        ruta = ay.RAIZ / 'instalar.py'
        spec = importlib.util.spec_from_file_location(
            'abyss_instalador_bajo_prueba_kinetica_mensaje', str(ruta))
        inst = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(inst)

        self.assertIn(inst.COMANDO_DESCARGAR_MANOS, kinetica.MENSAJE_MEDIAPIPE,
                      'MENSAJE_MEDIAPIPE no cita instalar.COMANDO_DESCARGAR_MANOS: se '
                      'pueden separar con el tiempo si uno cambia sin el otro')
        self.assertNotIn('npm', kinetica.MENSAJE_MEDIAPIPE.lower())
        self.assertNotIn('node.js', kinetica.MENSAJE_MEDIAPIPE.lower())


if __name__ == '__main__':
    unittest.main()
