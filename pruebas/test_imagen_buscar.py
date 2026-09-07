"""`imagen.py buscar` (ESPECIFICACION_TANDA2.md, T2.8): Openverse y Wikimedia Commons, sin
clave, solo busca y trae con atribución (no monta nada). Probado contra las respuestas JSON
guardadas en `pruebas/datos/openverse_ejemplo.json` y `pruebas/datos/commons_ejemplo.json`
(copias fieles de la forma real de cada API, con URLs de imagen sustituidas por rutas de un
servidor local): un servidor HTTP falso en 127.0.0.1 las sirve, sin tocar la red de verdad,
igual que `test_imagen_crear_vias.py` hace para la vía `local` de `crear`.

`ABYSS_OPENVERSE_URL`/`ABYSS_COMMONS_URL` (ver docstring de `imagen.py`) apuntan la búsqueda
a ese servidor falso en vez de a los hosts reales.
"""
import base64
import io
import json
import os
import re
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ayudas as ay

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'abyss'))
import imagen

DATOS = Path(__file__).resolve().parent / 'datos'

try:
    from PIL import Image
except ImportError:
    Image = None


def _png_falso():
    import random
    img = Image.new('RGB', (48, 48))
    px = img.load()
    rnd = random.Random(2)
    for y in range(48):
        for x in range(48):
            px[x, y] = (rnd.randrange(256), rnd.randrange(256), rnd.randrange(256))
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


class _ServidorBancosFalso:
    """Sirve las dos fixtures (con el placeholder `127.0.0.1:0` sustituido por su propio
    puerto, para que las URLs de imagen que trae cada resultado apunten de vuelta a este
    mismo servidor) y, para cualquier otra ruta, una imagen sintética — así `--descargar`
    también se prueba sin red."""

    def __enter__(self):
        openverse = (DATOS / 'openverse_ejemplo.json').read_text(encoding='utf-8')
        commons = (DATOS / 'commons_ejemplo.json').read_text(encoding='utf-8')
        png = _png_falso()
        estado = {}

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path.startswith('/v1/images/'):
                    cuerpo = re.sub(r'127\.0\.0\.1:0', f'127.0.0.1:{estado["puerto"]}', openverse).encode('utf-8')
                    self._json(cuerpo)
                elif self.path.startswith('/w/api.php'):
                    cuerpo = re.sub(r'127\.0\.0\.1:0', f'127.0.0.1:{estado["puerto"]}', commons).encode('utf-8')
                    self._json(cuerpo)
                else:
                    self.send_response(200)
                    self.send_header('Content-Type', 'image/jpeg')
                    self.send_header('Content-Length', str(len(png)))
                    self.end_headers()
                    self.wfile.write(png)

            def _json(self, cuerpo):
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(cuerpo)))
                self.end_headers()
                self.wfile.write(cuerpo)

            def log_message(self, *a):
                pass

        self.httpd = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.puerto = self.httpd.server_address[1]
        estado['puerto'] = self.puerto
        self.hilo = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.hilo.start()
        return self

    def __exit__(self, *exc):
        self.httpd.shutdown()
        self.httpd.server_close()


def _sin_proxy(env):
    for k in ('http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY'):
        env.pop(k, None)
    return env


def _env_bancos_falsos(proj, srv):
    env = _sin_proxy(ay.entorno(proj))
    env['ABYSS_OPENVERSE_URL'] = f'http://127.0.0.1:{srv.puerto}/v1/images/'
    env['ABYSS_COMMONS_URL'] = f'http://127.0.0.1:{srv.puerto}/w/api.php'
    return env


class BuscarEnProceso(unittest.TestCase):
    """Las funciones `buscar_openverse`/`buscar_commons` en proceso, con `pedir_fn` de
    pega leyendo directamente las fixtures — sin ni siquiera un servidor HTTP de por
    medio. Cubre el parseo del JSON de cada API tal como viene documentado."""

    def _pedir_falso(self, nombre_fixture):
        cuerpo = (DATOS / nombre_fixture).read_text(encoding='utf-8').encode('utf-8')

        def _pedir(url, datos=None, cabeceras=None, timeout=None, metodo=None):
            return 200, cuerpo, 'application/json'
        return _pedir

    def test_openverse_parsea_titulo_autor_licencia_url(self):
        resultados = imagen.buscar_openverse('bicicleta', n=5, pedir_fn=self._pedir_falso('openverse_ejemplo.json'))
        self.assertEqual(len(resultados), 2)
        r0 = resultados[0]
        self.assertEqual(r0['fuente'], 'openverse')
        self.assertEqual(r0['titulo'], 'Bicicleta roja apoyada en un muro')
        self.assertEqual(r0['autor'], 'Persona de Ejemplo')
        self.assertEqual(r0['licencia'], 'CC0 1.0')
        self.assertTrue(r0['url'].endswith('bicicleta.jpg'))

    def test_openverse_respeta_el_limite_n(self):
        resultados = imagen.buscar_openverse('bicicleta', n=1, pedir_fn=self._pedir_falso('openverse_ejemplo.json'))
        self.assertEqual(len(resultados), 1)

    def test_commons_parsea_y_quita_html_del_autor(self):
        resultados = imagen.buscar_commons('puente', n=5, pedir_fn=self._pedir_falso('commons_ejemplo.json'))
        self.assertEqual(len(resultados), 2)
        r0 = resultados[0]
        self.assertEqual(r0['fuente'], 'commons')
        self.assertEqual(r0['autor'], 'Alguien', 'el <a href=...> debe quedar limpio')
        self.assertEqual(r0['licencia'], 'CC BY-SA 4.0')
        r1 = resultados[1]
        self.assertEqual(r1['licencia'], 'public domain', 'sin LicenseShortName, cae a License')

    def test_openverse_http_error_se_convierte_en_runtimeerror(self):
        def _pedir(url, datos=None, cabeceras=None, timeout=None, metodo=None):
            return 503, b'', 'text/plain'
        with self.assertRaises(RuntimeError):
            imagen.buscar_openverse('x', pedir_fn=_pedir)

    def test_buscar_combinado_recorta_a_n_y_no_revienta_si_una_fuente_falla(self):
        # `buscar()` en sí siempre usa `_pedir` real de cada buscador (sin `pedir_fn`
        # inyectable a ese nivel): se sustituye aquí el propio diccionario `BUSCADORES`
        # por dos fuentes falsas (una con datos, otra que falla) para no tocar la red.
        original = dict(imagen.BUSCADORES)
        try:
            imagen.BUSCADORES['openverse'] = lambda q, n: imagen.buscar_openverse(q, n, pedir_fn=self._pedir_falso('openverse_ejemplo.json'))
            imagen.BUSCADORES['commons'] = lambda q, n: (_ for _ in ()).throw(RuntimeError('commons caído'))
            resultados, errores = imagen.buscar('x', n=1, fuente='ambas')
        finally:
            imagen.BUSCADORES.clear()
            imagen.BUSCADORES.update(original)
        self.assertEqual(len(resultados), 1, 'n=1 debe recortar el total, aunque openverse trajera más')
        self.assertEqual(len(errores), 1)
        self.assertIn('commons', errores[0])


@unittest.skipUnless(Image is not None, 'Pillow no disponible: solo hace falta para fabricar la imagen falsa del servidor')
class BuscarPorCLI(unittest.TestCase):
    def test_buscar_imprime_resultados_de_ambas_fuentes(self):
        with _ServidorBancosFalso() as srv:
            proj = ay.nuevo_proyecto()
            env = _env_bancos_falsos(proj, srv)
            r = ay.ejecutar(ay.script('imagen.py'), ['buscar', 'bicicleta'], env, timeout=30)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn('[openverse]', r.stdout)
            self.assertIn('[commons]', r.stdout)
            self.assertIn('Bicicleta roja apoyada en un muro', r.stdout)

    def test_buscar_fuente_unica_solo_trae_esa_fuente(self):
        with _ServidorBancosFalso() as srv:
            proj = ay.nuevo_proyecto()
            r = ay.ejecutar(ay.script('imagen.py'), ['buscar', 'x', '--fuente', 'commons'],
                             _env_bancos_falsos(proj, srv), timeout=30)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertNotIn('[openverse]', r.stdout)
            self.assertIn('[commons]', r.stdout)

    def test_buscar_descargar_guarda_imagen_y_atribucion(self):
        with _ServidorBancosFalso() as srv:
            proj = ay.nuevo_proyecto()
            (proj / 'memory').mkdir(exist_ok=True)
            r = ay.ejecutar(ay.script('imagen.py'),
                             ['buscar', 'bicicleta', '--fuente', 'openverse', '--descargar'],
                             _env_bancos_falsos(proj, srv), timeout=30)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn('descargada:', r.stdout)

            imagenes = list((proj / 'memory' / 'imagenes').glob('buscar_openverse_*'))
            txts = [p for p in imagenes if p.suffix == '.txt']
            imgs = [p for p in imagenes if p.suffix != '.txt']
            self.assertEqual(len(imgs), 1)
            self.assertEqual(len(txts), 1)
            atribucion = txts[0].read_text(encoding='utf-8')
            self.assertIn('Bicicleta roja apoyada en un muro', atribucion)
            self.assertIn('Persona de Ejemplo', atribucion)
            self.assertIn('CC0', atribucion)

    def test_fuente_desconocida_sale_con_1(self):
        proj = ay.nuevo_proyecto()
        r = ay.ejecutar(ay.script('imagen.py'), ['buscar', 'x', '--fuente', 'flickr'], ay.entorno(proj))
        self.assertEqual(r.returncode, 1)

    def test_sin_texto_sale_con_1(self):
        proj = ay.nuevo_proyecto()
        r = ay.ejecutar(ay.script('imagen.py'), ['buscar'], ay.entorno(proj))
        self.assertEqual(r.returncode, 1)


if __name__ == '__main__':
    unittest.main()
