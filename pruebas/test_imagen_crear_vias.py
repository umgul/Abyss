"""`imagen.py crear`/`vias` (ESPECIFICACION.md §3 y §6, tarea B item 1c/1d): la cascada
de proveedores. Un servidor HTTP falso en 127.0.0.1 hace de servidor local estilo
A1111/Forge para la vía `local` (la única que no manda el prompt fuera, ver docstring
de imagen.py); para el resto se corta la red (proxy a un puerto muerto, 127.0.0.1:9,
donde no escucha nadie) y se mide que falla rápido, nombrando la vía, sin imprimir
ninguna clave configurada.

Todo con ABYSS_PROYECTO/--proyecto sobre un proyecto temporal (ayudas.py); nunca
sale una petición real a internet: la vía `local` habla con el servidor de este mismo
proceso, y las demás encuentran el proxy muerto antes de llegar a ninguna parte.
"""
import sys
import os
import io
import json
import time
import base64
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ayudas as ay

try:
    from PIL import Image
except ImportError:
    Image = None

ORDEN_ESPERADO = ['local', 'pollinations', 'cloudflare', 'together', 'huggingface', 'horde']


def _png_falso_64x64():
    """Un PNG de 64x64 con ruido: por encima de los 2000 bytes que `imagen.crear()`
    exige para no descartar la respuesta como «demasiado corta» (imagen.py)."""
    import random
    img = Image.new('RGB', (64, 64))
    px = img.load()
    rnd = random.Random(1)
    for y in range(64):
        for x in range(64):
            px[x, y] = (rnd.randrange(256), rnd.randrange(256), rnd.randrange(256))
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    datos = buf.getvalue()
    assert len(datos) > 2000, f'PNG de prueba demasiado pequeño ({len(datos)}B): sube el ruido'
    return datos


class _ServidorA1111Falso:
    """`with _ServidorA1111Falso() as srv:` levanta en un hilo, en 127.0.0.1 y puerto
    efímero, un servidor que responde a POST /sdapi/v1/txt2img como A1111/Forge
    (`{"images": [<png en base64>]}`, ver docstring de imagen.py)."""

    def __enter__(self):
        b64 = base64.b64encode(_png_falso_64x64()).decode('ascii')

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                largo = int(self.headers.get('Content-Length', 0))
                self.rfile.read(largo)  # se descarta: no hace falta mirar el prompt
                cuerpo = json.dumps({'images': [b64]}).encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(cuerpo)))
                self.end_headers()
                self.wfile.write(cuerpo)

            def log_message(self, *a):
                pass  # silencio: no ensuciar la salida de la prueba

        self.httpd = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.puerto = self.httpd.server_address[1]
        self.hilo = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.hilo.start()
        return self

    def __exit__(self, *exc):
        self.httpd.shutdown()
        self.httpd.server_close()


def _sin_proxy(env):
    """Quita cualquier proxy heredado del entorno real: la vía `local` habla con
    127.0.0.1 y un proxy ajeno lo estropearía (urllib respeta http_proxy/https_proxy
    incluso para loopback si no se dice lo contrario)."""
    for k in ('http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY'):
        env.pop(k, None)
    return env


def _red_cortada(env):
    """Ningún proveedor externo responde: el proxy apunta a 127.0.0.1:9, un puerto
    donde no escucha nadie (regla de la tarea: 'sin red en la suite')."""
    env['http_proxy'] = env['HTTP_PROXY'] = 'http://127.0.0.1:9'
    env['https_proxy'] = env['HTTPS_PROXY'] = 'http://127.0.0.1:9'
    return env


@unittest.skipUnless(Image is not None, 'Pillow no disponible: solo hace falta aquí para fabricar el PNG falso del servidor')
class ImagenCrearViaLocal(unittest.TestCase):
    def test_crear_via_local_escribe_png_y_log(self):
        with _ServidorA1111Falso() as srv:
            proj = ay.nuevo_proyecto()
            (proj / 'memory').mkdir(exist_ok=True)
            cfg = {'local_url': f'http://127.0.0.1:{srv.puerto}', 'orden': ['local']}
            (proj / 'memory' / 'imagen_config.json').write_text(json.dumps(cfg), encoding='utf-8')
            env = _sin_proxy(ay.entorno(proj))

            r = ay.ejecutar(ay.script('imagen.py'),
                             ['crear', 'un gato dibujado a lápiz', '--via', 'local'], env, timeout=30)

            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn('local', r.stdout)

            imagenes = list((proj / 'memory' / 'imagenes').glob('*.png'))
            self.assertEqual(len(imagenes), 1)
            with open(imagenes[0], 'rb') as fh:
                self.assertEqual(fh.read(8), b'\x89PNG\r\n\x1a\n')

            log = (proj / 'memory' / 'imagen.log').read_text(encoding='utf-8')
            self.assertIn('local', log)

    def test_proyecto_no_acaba_como_fichero_de_salida_en_crear(self):
        """Mismo falsador que en test_imagen_pintar.py (tarea B item 2), para `crear`:
        con `--proyecto <cwd>` Y `--via local`, la salida sigue siendo la que genera
        `crear()` por defecto (mem/imagenes/imagen_AAAAMMDD_HHMMSS.png), nunca algo
        derivado del valor de `--proyecto`."""
        with _ServidorA1111Falso() as srv:
            home_falso = ay.nuevo_proyecto()  # aquí solo hace de HOME desechable, no de "proj"
            marcador = 'marcador-de-proyecto-de-prueba'
            mem_resuelta = home_falso / '.claude' / 'projects' / marcador / 'memory'
            mem_resuelta.mkdir(parents=True, exist_ok=True)
            cfg = {'local_url': f'http://127.0.0.1:{srv.puerto}', 'orden': ['local']}
            (mem_resuelta / 'imagen_config.json').write_text(json.dumps(cfg), encoding='utf-8')

            env = _sin_proxy(dict(os.environ))
            env.pop('ABYSS_PROYECTO', None)  # fuerza la resolución por --proyecto (orden 3)
            env['HOME'] = env['USERPROFILE'] = str(home_falso)

            r = ay.ejecutar(ay.script('imagen.py'),
                             ['crear', 'x', '--via', 'local', '--proyecto', marcador],
                             env, cwd=str(home_falso), timeout=30)

            self.assertEqual(r.returncode, 0, r.stderr)
            imagenes = list((mem_resuelta / 'imagenes').glob('*.png'))
            self.assertEqual(len(imagenes), 1, 'debe escribir bajo memory/imagenes/, con el nombre por defecto')
            self.assertFalse((home_falso / marcador).exists(),
                              '--proyecto no debe acabar convertido en ruta/carpeta de salida')


class ImagenCrearSinRed(unittest.TestCase):
    def test_horde_sin_red_falla_rapido_y_nombra_la_via_sin_imprimir_la_clave(self):
        proj = ay.nuevo_proyecto()
        (proj / 'memory').mkdir(exist_ok=True)
        secreto = 'CLAVE-SECRETA-QUE-NO-DEBE-SALIR-9x7'
        cfg = {'orden': ['pollinations', 'horde'], 'pollinations_key': secreto}
        (proj / 'memory' / 'imagen_config.json').write_text(json.dumps(cfg), encoding='utf-8')
        env = _red_cortada(ay.entorno(proj))

        t0 = time.time()
        r = ay.ejecutar(ay.script('imagen.py'), ['crear', 'x'], env, timeout=45)
        transcurrido = time.time() - t0

        self.assertLess(transcurrido, 30, f'con la red cortada, tardó {transcurrido:.1f}s')
        self.assertEqual(r.returncode, 2)
        self.assertIn('pollinations', r.stdout)
        self.assertIn('horde', r.stdout)
        self.assertNotIn(secreto, r.stdout, 'la clave configurada no debe aparecer en el mensaje de error')
        self.assertNotIn(secreto, r.stderr)


class ImagenVias(unittest.TestCase):
    def test_vias_imprime_una_fila_por_via(self):
        proj = ay.nuevo_proyecto()
        env = _red_cortada(ay.entorno(proj))
        r = ay.ejecutar(ay.script('imagen.py'), ['vias'], env, timeout=45)
        self.assertEqual(r.returncode, 0, r.stderr)
        filas = [l for l in r.stdout.splitlines() if l.strip()]
        self.assertEqual([l.split()[0] for l in filas], ORDEN_ESPERADO)


if __name__ == '__main__':
    unittest.main()
