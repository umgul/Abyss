# -*- coding: utf-8 -*-
"""`puerta_local.rechazo()`: unitarias con un manejador de mentira, y de verdad
contra `kinetico_servidor.sirve()` y el `_Manejador` de `instalador_web.py`
levantados en un puerto libre — nunca contra el `~/.claude/settings.json` real."""
import http.client
import importlib.util
import json
import os
import shutil
import socket
import sys
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ayudas as ay  # noqa: E402

sys.path.insert(0, str(ay.PKG))
import kinetico_servidor  # noqa: E402
import puerta_local  # noqa: E402


def _falso(puerto=8877, headers=None):
    """Manejador de mentira: solo lo que `rechazo()` mira de verdad."""
    return SimpleNamespace(server=SimpleNamespace(server_address=('127.0.0.1', puerto)),
                            headers=dict(headers or {}))


def _puerto_libre():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def _esperar_puerto(puerto, plazo=5.0):
    """`sirve()` liga y escucha DENTRO del hilo que se lanza: sin esto, la
    primera petición podría llegar antes de que el socket exista."""
    fin = time.time() + plazo
    while time.time() < fin:
        try:
            with socket.create_connection(('127.0.0.1', puerto), timeout=0.2):
                return
        except OSError:
            time.sleep(0.02)
    raise AssertionError('el servidor no llegó a escuchar en el puerto %d' % puerto)


def _cargar_instalador_web():
    ruta = ay.PKG / 'instalador_web.py'
    spec = importlib.util.spec_from_file_location('abyss_instalador_web_bajo_prueba', str(ruta))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ───────────────────────────── rechazo(): unitarias ─────────────────────────────

class RechazoConHost(unittest.TestCase):
    def test_host_127_exacto_pasa(self):
        self.assertIsNone(puerta_local.rechazo(_falso(8877, {'Host': '127.0.0.1:8877'})))

    def test_host_localhost_pasa(self):
        self.assertIsNone(puerta_local.rechazo(_falso(8877, {'Host': 'localhost:8877'})))

    def test_host_en_mayusculas_pasa(self):
        self.assertIsNone(puerta_local.rechazo(_falso(8877, {'Host': 'LOCALHOST:8877'})))

    def test_host_ausente_rechaza(self):
        self.assertIsNotNone(puerta_local.rechazo(_falso(8877, {})))

    def test_host_con_otro_puerto_rechaza(self):
        self.assertIsNotNone(puerta_local.rechazo(_falso(8877, {'Host': '127.0.0.1:9999'})))

    def test_host_ajeno_rechaza(self):
        self.assertIsNotNone(puerta_local.rechazo(_falso(8877, {'Host': 'evil.example:8877'})))


class RechazoConOrigin(unittest.TestCase):
    def test_origin_ausente_pasa(self):
        h = {'Host': '127.0.0.1:8877'}
        self.assertIsNone(puerta_local.rechazo(_falso(8877, h)))

    def test_origin_127_pasa(self):
        h = {'Host': '127.0.0.1:8877', 'Origin': 'http://127.0.0.1:8877'}
        self.assertIsNone(puerta_local.rechazo(_falso(8877, h)))

    def test_origin_localhost_pasa(self):
        h = {'Host': '127.0.0.1:8877', 'Origin': 'http://localhost:8877'}
        self.assertIsNone(puerta_local.rechazo(_falso(8877, h)))

    def test_origin_en_mayusculas_pasa(self):
        h = {'Host': '127.0.0.1:8877', 'Origin': 'HTTP://127.0.0.1:8877'}
        self.assertIsNone(puerta_local.rechazo(_falso(8877, h)))

    def test_origin_ajeno_rechaza(self):
        h = {'Host': '127.0.0.1:8877', 'Origin': 'https://evil.example'}
        self.assertIsNotNone(puerta_local.rechazo(_falso(8877, h)))

    def test_origin_con_otro_puerto_rechaza(self):
        h = {'Host': '127.0.0.1:8877', 'Origin': 'http://127.0.0.1:1234'}
        self.assertIsNotNone(puerta_local.rechazo(_falso(8877, h)))


class RechazoConSecFetchSite(unittest.TestCase):
    def test_cross_site_rechaza(self):
        h = {'Host': '127.0.0.1:8877', 'Sec-Fetch-Site': 'cross-site'}
        self.assertIsNotNone(puerta_local.rechazo(_falso(8877, h)))

    def test_same_site_rechaza(self):
        h = {'Host': '127.0.0.1:8877', 'Sec-Fetch-Site': 'same-site'}
        self.assertIsNotNone(puerta_local.rechazo(_falso(8877, h)))

    def test_same_origin_pasa(self):
        h = {'Host': '127.0.0.1:8877', 'Sec-Fetch-Site': 'same-origin'}
        self.assertIsNone(puerta_local.rechazo(_falso(8877, h)))

    def test_none_pasa(self):
        h = {'Host': '127.0.0.1:8877', 'Sec-Fetch-Site': 'none'}
        self.assertIsNone(puerta_local.rechazo(_falso(8877, h)))

    def test_ausente_pasa(self):
        h = {'Host': '127.0.0.1:8877'}
        self.assertIsNone(puerta_local.rechazo(_falso(8877, h)))


# ───────────────────────── kinetico_servidor.sirve(): de verdad ─────────────────────────

class KineticoServidorDeVerdad(unittest.TestCase):
    """`sirve()` no expone el `TCPServer` que crea por dentro (a diferencia de construirlo
    a mano, como hace `test_kinetica.py` con `_elegir_manejador`): se lanza en un hilo
    daemon sobre un puerto libre elegido antes de arrancar, y se deja correr — sin ese
    objeto no hay forma de pararlo desde fuera."""

    @classmethod
    def setUpClass(cls):
        cls.carpeta = Path(tempfile.mkdtemp(prefix='abyss_puerta_local_kinetico_'))
        # sin "raiz": _destino() corta antes de resolver nada, así que ningún
        # destino (exista o no) llega a abrir ni a montar de verdad.
        (cls.carpeta / 'nodos.json').write_text('{}', encoding='utf-8')
        cls.puerto = _puerto_libre()
        cls.hilo = threading.Thread(
            target=kinetico_servidor.sirve,
            args=(str(cls.carpeta),),
            kwargs=dict(puerto=cls.puerto, abrir=False, avisar=lambda *a: None),
            daemon=True)
        cls.hilo.start()
        _esperar_puerto(cls.puerto)

    def _conexion(self):
        return http.client.HTTPConnection('127.0.0.1', self.puerto, timeout=5)

    def test_post_con_origin_ajeno_rechaza_y_no_ejecuta_el_verbo(self):
        c = self._conexion()
        cuerpo = b'{"destino": "no-existe"}'
        c.request('POST', '/entrar', body=cuerpo,
                  headers={'Content-Length': str(len(cuerpo)),
                           'Origin': 'https://evil.example'})
        r = c.getresponse()
        self.assertEqual(r.status, 403)
        r.read()
        c.close()

    def test_get_con_host_ajeno_rechaza(self):
        c = self._conexion()
        c.request('GET', '/index.html', headers={'Host': 'evil.example:%d' % self.puerto})
        r = c.getresponse()
        self.assertEqual(r.status, 403)
        r.read()
        c.close()

    def test_post_con_origin_local_llega_al_verbo(self):
        c = self._conexion()
        cuerpo = b'{"destino": "no-existe"}'
        c.request('POST', '/entrar', body=cuerpo,
                  headers={'Content-Length': str(len(cuerpo)),
                           'Origin': 'http://127.0.0.1:%d' % self.puerto})
        r = c.getresponse()
        self.assertEqual(r.status, 200)
        r.read()
        c.close()

    def test_post_sin_origin_llega_al_verbo(self):
        c = self._conexion()
        cuerpo = b'{"destino": "no-existe"}'
        c.request('POST', '/entrar', body=cuerpo, headers={'Content-Length': str(len(cuerpo))})
        r = c.getresponse()
        self.assertEqual(r.status, 200)
        r.read()
        c.close()

    def test_get_con_host_correcto_sirve_el_fichero(self):
        (self.carpeta / 'index.html').write_text('hola', encoding='utf-8')
        c = self._conexion()
        c.request('GET', '/index.html')
        r = c.getresponse()
        self.assertEqual(r.status, 200)
        r.read()
        c.close()


class NoSeAbreLoQueSeEjecutaria(unittest.TestCase):
    def test_ejecutables_y_accesos_directos(self):
        for nombre in ('a.exe', 'B.BAT', 'c.lnk', 'd.ps1', 'e.js', 'f.py', 'g.url', 'h.msi'):
            self.assertTrue(puerta_local.se_ejecutaria(nombre), nombre)
        for nombre in ('peli.mkv', 'libro.pdf', 'foto.png', 'nota.txt', 'web.html'):
            self.assertFalse(puerta_local.se_ejecutaria(nombre), nombre)

    def test_un_content_length_absurdo_no_se_lee(self):
        class Rfile:
            def read(self, n):
                raise AssertionError('no debía leer con Content-Length %r' % n)
        for largo in ('-1', 'abc', str(10 ** 9)):
            h = type('H', (), {'headers': {'Content-Length': largo}, 'rfile': Rfile()})()
            puerta_local.descartar_cuerpo(h)

    def test_el_servidor_se_niega_a_abrir_un_ejecutable_de_la_escena(self):
        raiz = Path(tempfile.mkdtemp(prefix='abyss_puerta_local_ejecutable_'))
        (raiz / 'lanzar.bat').write_text('echo hola', encoding='utf-8')
        montaje = Path(tempfile.mkdtemp(prefix='abyss_puerta_local_montaje_'))
        (montaje / 'nodos.json').write_text(json.dumps({'raiz': str(raiz), 'items': [{'id': 'lanzar.bat'}]}),
                                            encoding='utf-8')
        puerto = _puerto_libre()
        threading.Thread(target=kinetico_servidor.sirve, args=(str(montaje),),
                         kwargs=dict(puerto=puerto, abrir=False, avisar=lambda *a: None), daemon=True).start()
        _esperar_puerto(puerto)
        c = http.client.HTTPConnection('127.0.0.1', puerto, timeout=5)
        cuerpo = json.dumps({'destino': 'lanzar.bat'}).encode('utf-8')
        c.request('POST', '/abrir', body=cuerpo, headers={'Content-Length': str(len(cuerpo)),
                                                         'Origin': 'http://127.0.0.1:%d' % puerto})
        r = c.getresponse()
        respuesta = json.loads(r.read().decode('utf-8'))
        c.close()
        self.assertFalse(respuesta['ok'])
        self.assertIn('ejecutaría', respuesta['por_que'])


# ───────────────────────── instalador_web._Manejador: de verdad ─────────────────────────

class InstaladorWebDeVerdad(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _cargar_instalador_web()
        cls.tmp = Path(tempfile.mkdtemp(prefix='abyss_puerta_local_instalador_web_'))
        # settings/skills a un temporal propio: esta prueba NUNCA debe leer ni
        # escribir el settings.json real del usuario.
        cls.mod._CTX.update(settings_ruta=str(cls.tmp / 'settings.json'),
                             skills_dir=str(cls.tmp / 'skills'))
        cls.srv = ThreadingHTTPServer(('127.0.0.1', 0), cls.mod._Manejador)
        cls.puerto = cls.srv.server_address[1]
        cls.hilo = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.hilo.start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def _conexion(self):
        return http.client.HTTPConnection('127.0.0.1', self.puerto, timeout=5)

    def test_get_api_estado_con_host_correcto_funciona(self):
        c = self._conexion()
        c.request('GET', '/api/estado')
        r = c.getresponse()
        self.assertEqual(r.status, 200)
        r.read()
        c.close()

    def test_get_api_estado_con_host_ajeno_rechaza(self):
        c = self._conexion()
        c.request('GET', '/api/estado', headers={'Host': 'evil.example:%d' % self.puerto})
        r = c.getresponse()
        self.assertEqual(r.status, 403)
        r.read()
        c.close()

    def test_post_con_origin_ajeno_rechaza_y_no_ejecuta_el_verbo(self):
        # ruta inexistente a propósito: si el rechazo fallara y el verbo se
        # ejecutara, esto seguiría sin instalar ni desinstalar nada real.
        c = self._conexion()
        c.request('POST', '/api/no-existe-de-verdad', body=b'',
                  headers={'Content-Length': '0', 'Origin': 'https://evil.example'})
        r = c.getresponse()
        self.assertEqual(r.status, 403)
        r.read()
        c.close()

    def test_post_con_origin_local_llega_al_verbo(self):
        c = self._conexion()
        c.request('POST', '/api/no-existe-de-verdad', body=b'',
                  headers={'Content-Length': '0', 'Origin': 'http://127.0.0.1:%d' % self.puerto})
        r = c.getresponse()
        self.assertEqual(r.status, 404)  # llega al verbo: ruta desconocida → 404 real
        r.read()
        c.close()

    def test_post_sin_origin_llega_al_verbo(self):
        c = self._conexion()
        c.request('POST', '/api/no-existe-de-verdad', body=b'', headers={'Content-Length': '0'})
        r = c.getresponse()
        self.assertEqual(r.status, 404)
        r.read()
        c.close()


if __name__ == '__main__':
    unittest.main()
