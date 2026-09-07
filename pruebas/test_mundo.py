"""`mundo.py` (ESPECIFICACION_TANDA3.md, T3.3): motivos del mundo real para `imagen.py
mundo` — met/artic/commons (sin clave) más streetview/mapillary/webcam (con clave) y
`contexto()` (Wikidata + Wikipedia, sin clave). Sin red en toda la suite: cada fuente
se prueba con un `pedir_fn` de pega que sirve las respuestas JSON reales capturadas
UNA vez el 7-sep en `pruebas/datos/mundo_*.json` (recortadas; ver
`hacer_fixtures.py` — no forma parte del paquete, solo del proceso de captura) — o,
para las tres fuentes con clave (que no se pueden capturar sin pagar/registrar), con
una respuesta sintética de la forma DOCUMENTADA de cada API, igual que
`test_imagen_crear_vias.py` hace con el servidor A1111 falso.

Cualquier URL que una prueba no espere hace fallar esa prueba con un mensaje claro
(`AssertionError`), nunca toca la red de verdad — así una fuente mal probada no
puede colarse como «verde» por accidente.
"""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.parse
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ayudas as ay  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'abyss'))
import mundo  # noqa: E402

DATOS = Path(__file__).resolve().parent / 'datos'


def _cargar(nombre):
    return (DATOS / nombre).read_text(encoding='utf-8').encode('utf-8')


def _pedir_por_ruta(mapa, prohibidas=()):
    """`pedir_fn` de pega: `mapa` es una lista de `(subcadena_de_la_url, fixture_o_funcion)`.
    Se usa la primera entrada cuya subcadena aparezca en la URL pedida; si `fixture_o_funcion`
    es una función se le pasa la URL entera y debe devolver `(cod, cuerpo, content_type)`, si
    es una cadena se lee como fixture JSON de `pruebas/datos/` con `cod=200`.

    Cualquier URL que contenga algo de `prohibidas`, o que no encaje ninguna entrada de
    `mapa`, hace fallar la prueba (nunca se cuela una llamada no esperada)."""
    def _fn(url, datos=None, cabeceras=None, timeout=None, metodo=None):
        for llave in prohibidas:
            if llave in url:
                raise AssertionError(f'esta prueba no debía llamar a una URL con "{llave}": {url}')
        for sub, valor in mapa:
            if sub in url:
                if callable(valor):
                    return valor(url)
                return 200, _cargar(valor), 'application/json'
        raise AssertionError(f'URL no esperada en esta prueba: {url}')
    return _fn


def _pedir_nunca(*a, **k):
    raise AssertionError('esta prueba no debía tocar la red en absoluto')


def _objeto_met_437394_o_vacio(url):
    """Para las pruebas de `_buscar_met`/`buscar`: el objeto 437394 (real, con
    imagen) si la URL lo pide; cualquier otro objectID, el fixture SIN imagen (los
    demás IDs de `mundo_met_search.json` no se capturaron de verdad — no hace
    falta: lo que prueba `_buscar_met` es precisamente que los descarta)."""
    if url.endswith('/objects/437394'):
        return 200, _cargar('mundo_met_objeto_437394.json'), 'application/json'
    return 200, _cargar('mundo_met_objeto_sin_imagen.json'), 'application/json'


MET_ABIERTO = [
    ('metmuseum.org/public/collection/v1/search', 'mundo_met_search.json'),
    ('metmuseum.org/public/collection/v1/objects/', _objeto_met_437394_o_vacio),
]


# ── fuentes abiertas: met / artic / commons ──────────────────────────────────

class FuenteMet(unittest.TestCase):
    def test_descarta_objetos_sin_imagen_o_sin_dominio_publico(self):
        pedir = _pedir_por_ruta(MET_ABIERTO)
        candidatos = mundo._buscar_met('Rembrandt self-portrait', 5, {}, pedir)
        self.assertEqual(len(candidatos), 1, 'de los 6 objectIDs del fixture, solo 437394 trae imagen')
        c = candidatos[0]
        self.assertEqual(c['fuente'], 'met')
        self.assertEqual(c['titulo'], 'Aristotle with a Bust of Homer')
        self.assertIn('Rembrandt', c['autor'])
        self.assertEqual(c['licencia'], 'dominio público')
        self.assertTrue(c['url'].endswith('DP-30758-001.jpg'))
        self.assertIn('437394', c['pagina'])

    def test_http_error_en_la_busqueda_se_convierte_en_runtimeerror(self):
        pedir = _pedir_por_ruta([('metmuseum.org', lambda url: (503, b'', 'text/plain'))])
        with self.assertRaises(RuntimeError):
            mundo._buscar_met('x', 5, {}, pedir)


class FuenteArtic(unittest.TestCase):
    def test_arma_la_url_iiif_desde_el_config_de_la_respuesta(self):
        pedir = _pedir_por_ruta([('api.artic.edu/api/v1/artworks/search', 'mundo_artic_search.json')])
        candidatos = mundo._buscar_artic('Monet water lilies', 2, {}, pedir)
        self.assertEqual(len(candidatos), 2)
        self.assertEqual(candidatos[0]['fuente'], 'artic')
        self.assertEqual(candidatos[0]['titulo'], 'Water Lilies')
        self.assertEqual(candidatos[0]['licencia'], 'dominio público')
        self.assertEqual(candidatos[0]['url'],
                          'https://www.artic.edu/iiif/2/3c27b499-af56-f0d5-93b5-a7f2f1ad5813/full/843,/0/default.jpg')
        self.assertIn('/artworks/16568', candidatos[0]['pagina'])


class FuenteCommons(unittest.TestCase):
    def test_limpia_html_del_autor_y_saca_tamano_en_pixeles(self):
        pedir = _pedir_por_ruta([('commons.wikimedia.org/w/api.php', 'mundo_commons.json')])
        candidatos = mundo._buscar_commons('Last Supper Leonardo', 5, {}, pedir)
        self.assertEqual(len(candidatos), 2)
        autores = {c['autor'] for c in candidatos}
        self.assertIn('Alberto Fernandez Fernandez', autores)
        self.assertIn('Leonardo da Vinci', autores, 'el <bdi><a><span> anidado debe quedar en texto plano')
        tamanos = {c['tamano'] for c in candidatos}
        self.assertEqual(tamanos, {'3314x1971', '5076x2645'})
        licencias = {c['licencia'] for c in candidatos}
        self.assertEqual(licencias, {'CC BY 2.5', 'Public domain'})


# ── contexto: Wikidata + Wikipedia ───────────────────────────────────────────

class Contexto(unittest.TestCase):
    def test_trae_lat_lon_de_un_lugar(self):
        pedir = _pedir_por_ruta([
            ('wikidata.org/w/api.php', 'mundo_wikidata_torre_eiffel.json'),
            ('es.wikipedia.org/api/rest_v1/page/summary/', 'mundo_wikipedia_torre_eiffel.json'),
        ])
        ctx = mundo.contexto('torre Eiffel', {}, pedir_fn=pedir)
        self.assertEqual(ctx['wikidata_id'], 'Q243')
        self.assertEqual(ctx['titulo'], 'torre Eiffel')
        self.assertAlmostEqual(ctx['lat'], 48.858296)
        self.assertAlmostEqual(ctx['lon'], 2.294479)
        self.assertTrue(ctx['url_wikipedia'].endswith('Torre_Eiffel'))
        self.assertIn('monumento', ctx['descripcion'])

    def test_sin_coordenadas_para_una_persona(self):
        pedir = _pedir_por_ruta([
            ('wikidata.org/w/api.php', 'mundo_wikidata_rembrandt.json'),
            ('es.wikipedia.org/api/rest_v1/page/summary/', 'mundo_wikipedia_rembrandt.json'),
        ])
        ctx = mundo.contexto('Rembrandt', {}, pedir_fn=pedir)
        self.assertIsNone(ctx['lat'])
        self.assertIsNone(ctx['lon'])
        self.assertIn('grabador', ctx['descripcion'])

    def test_wikidata_sin_resultado_devuelve_vacio_sin_llamar_a_wikipedia(self):
        pedir = _pedir_por_ruta([('wikidata.org/w/api.php', 'mundo_wikidata_vacio.json')],
                                 prohibidas=('wikipedia.org',))
        self.assertEqual(mundo.contexto('xyzzy_motivo_inexistente_9x7', {}, pedir_fn=pedir), {})

    def test_sin_red_nunca_lanza(self):
        def _pedir_caido(*a, **k):
            raise OSError('red caída')
        self.assertEqual(mundo.contexto('x', {}, pedir_fn=_pedir_caido), {})


# ── fuentes con clave: nunca tocan la red sin ella ───────────────────────────

class FuentesConClave(unittest.TestCase):
    def test_streetview_sin_clave_no_toca_la_red(self):
        with self.assertRaises(RuntimeError) as cm:
            mundo._buscar_streetview('x', 5, {}, _pedir_nunca, {'lugar': (1.0, 2.0)})
        self.assertTrue(str(cm.exception).startswith('sin clave:'))

    def test_mapillary_sin_clave_no_toca_la_red(self):
        with self.assertRaises(RuntimeError) as cm:
            mundo._buscar_mapillary('x', 5, {}, _pedir_nunca, {'lugar': (1.0, 2.0)})
        self.assertTrue(str(cm.exception).startswith('sin clave:'))

    def test_webcam_sin_clave_no_toca_la_red(self):
        with self.assertRaises(RuntimeError) as cm:
            mundo._buscar_webcam('x', 5, {}, _pedir_nunca, {'lugar': (1.0, 2.0)})
        self.assertTrue(str(cm.exception).startswith('sin clave:'))

    def test_streetview_con_clave_pero_sin_lugar_no_toca_la_red(self):
        with self.assertRaises(RuntimeError) as cm:
            mundo._buscar_streetview('x', 5, {'google_maps_key': 'ABC'}, _pedir_nunca, {'lugar': None})
        self.assertTrue(str(cm.exception).startswith('sin lugar:'))

    def test_streetview_con_clave_y_lugar_pide_metadata_y_arma_la_url(self):
        meta = json.dumps({'status': 'OK', 'pano_id': 'PANO123'}).encode('utf-8')

        def _pedir(url, datos=None, cabeceras=None, timeout=None, metodo=None):
            self.assertIn('streetview/metadata', url)
            self.assertIn('key=ABC', url)
            self.assertIn('heading=270', url)
            return 200, meta, 'application/json'

        candidatos = mundo._buscar_streetview(
            'x', 5, {'google_maps_key': 'ABC'}, _pedir,
            {'lugar': (48.85, 2.29), 'rumbo': 270, 'inclinacion': 10, 'campo': 80})
        self.assertEqual(len(candidatos), 1)
        c = candidatos[0]
        self.assertEqual(c['fuente'], 'streetview')
        self.assertIn('heading=270', c['url'])
        self.assertIn('key=ABC', c['url'])
        self.assertIn('PANO123', c['pagina'])

    def test_streetview_status_no_ok_lanza_sin_key_expuesta(self):
        meta = json.dumps({'status': 'ZERO_RESULTS'}).encode('utf-8')
        pedir = lambda *a, **k: (200, meta, 'application/json')  # noqa: E731
        with self.assertRaises(RuntimeError) as cm:
            mundo._buscar_streetview('x', 5, {'google_maps_key': 'SECRETA'}, pedir, {'lugar': (1.0, 2.0)})
        self.assertNotIn('SECRETA', str(cm.exception))

    def test_mapillary_con_clave_y_lugar(self):
        cuerpo = json.dumps({'data': [{'id': '999', 'thumb_2048_url': 'https://x/img.jpg',
                                        'creator': {'username': 'alguien'}}]}).encode('utf-8')

        def _pedir(url, datos=None, cabeceras=None, timeout=None, metodo=None):
            self.assertIn(urllib.parse.urlencode({'closeto': '2.29,48.85'}), url)
            return 200, cuerpo, 'application/json'

        candidatos = mundo._buscar_mapillary('x', 5, {'mapillary_token': 'T1'}, _pedir, {'lugar': (48.85, 2.29)})
        self.assertEqual(len(candidatos), 1)
        self.assertEqual(candidatos[0]['fuente'], 'mapillary')
        self.assertEqual(candidatos[0]['licencia'], 'CC BY-SA 4.0')
        self.assertEqual(candidatos[0]['autor'], 'alguien')

    def test_webcam_con_clave_y_lugar(self):
        cuerpo = json.dumps({'webcams': [{'id': '42', 'title': 'Plaza Mayor',
                                           'images': {'current': {'preview': 'https://x/cam.jpg'}},
                                           'location': {'city': 'Madrid', 'country': 'ES'}}]}).encode('utf-8')

        def _pedir(url, datos=None, cabeceras=None, timeout=None, metodo=None):
            self.assertEqual(cabeceras.get('x-windy-api-key'), 'W1')
            return 200, cuerpo, 'application/json'

        candidatos = mundo._buscar_webcam('x', 5, {'windy_key': 'W1'}, _pedir, {'lugar': (40.4, -3.7)})
        self.assertEqual(len(candidatos), 1)
        self.assertEqual(candidatos[0]['titulo'], 'Plaza Mayor')
        self.assertIn('Madrid', candidatos[0]['autor'])


# ── buscar(): combina fuentes, recorta a n, nunca lanza ──────────────────────

class Buscar(unittest.TestCase):
    def test_por_defecto_solo_pide_las_fuentes_abiertas(self):
        pedir = _pedir_por_ruta(
            MET_ABIERTO + [('api.artic.edu', 'mundo_artic_search.json'), ('commons.wikimedia.org', 'mundo_commons.json')],
            prohibidas=('wikidata.org', 'googleapis.com', 'mapillary.com', 'windy.com'))
        candidatos = mundo.buscar('motivo', n=3, cfg={}, pedir_fn=pedir)
        self.assertLessEqual(len(candidatos), 3)
        self.assertTrue(candidatos)
        self.assertNotIn('streetview', {c['fuente'] for c in candidatos})

    def test_recorta_al_total_n_no_por_fuente(self):
        pedir = _pedir_por_ruta(
            MET_ABIERTO + [('api.artic.edu', 'mundo_artic_search.json'), ('commons.wikimedia.org', 'mundo_commons.json')])
        candidatos = mundo.buscar('motivo', fuentes=('met', 'artic', 'commons'), n=2, cfg={}, pedir_fn=pedir)
        self.assertEqual(len(candidatos), 2)

    def test_fuente_desconocida_se_avisa_y_no_revienta(self):
        avisos = []
        candidatos = mundo.buscar('x', fuentes='flickr', cfg={}, avisar=avisos.append, pedir_fn=_pedir_nunca)
        self.assertEqual(candidatos, [])
        self.assertEqual(avisos, ['flickr: fuente desconocida'])

    def test_una_fuente_que_falla_no_tumba_a_las_demas(self):
        avisos = []
        pedir = _pedir_por_ruta(MET_ABIERTO + [('commons.wikimedia.org', 'mundo_commons.json'),
                                                ('api.artic.edu', lambda url: (503, b'', 'text/plain'))])
        candidatos = mundo.buscar('motivo', fuentes=('met', 'artic', 'commons'), n=5, cfg={},
                                   avisar=avisos.append, pedir_fn=pedir)
        self.assertTrue(candidatos, 'met y commons sí respondieron')
        self.assertTrue(any('artic' in a for a in avisos))

    def test_deriva_lugar_del_contexto_para_streetview_sin_lugar_explicito(self):
        meta = json.dumps({'status': 'OK', 'pano_id': 'P1'}).encode('utf-8')
        pedir = _pedir_por_ruta([
            ('wikidata.org/w/api.php', 'mundo_wikidata_torre_eiffel.json'),
            ('es.wikipedia.org/api/rest_v1/page/summary/', 'mundo_wikipedia_torre_eiffel.json'),
            ('streetview/metadata', lambda url: (200, meta, 'application/json')),
        ])
        candidatos = mundo.buscar('torre Eiffel', fuentes='streetview',
                                   cfg={'google_maps_key': 'ABC'}, pedir_fn=pedir)
        self.assertEqual(len(candidatos), 1)
        self.assertIn('48.858', candidatos[0]['titulo'])
        self.assertIn('P1', candidatos[0]['pagina'])

    def test_streetview_sin_clave_avisa_sin_llamar_a_contexto_ni_a_la_red(self):
        # con la clave ausente, ni siquiera hace falta derivar el lugar: se falla
        # por la clave antes de necesitarlo (nunca se llama a Wikidata/Wikipedia).
        avisos = []
        candidatos = mundo.buscar('torre Eiffel', fuentes='streetview', cfg={},
                                   avisar=avisos.append, pedir_fn=_pedir_nunca)
        self.assertEqual(candidatos, [])
        self.assertEqual(len(avisos), 1)
        self.assertIn('sin clave:', avisos[0])


# ── descargar(): imagen + atribución ──────────────────────────────────────────

class Descargar(unittest.TestCase):
    def test_descarga_escribe_imagen_y_atribucion(self):
        candidato = {'fuente': 'commons', 'titulo': 'Un motivo', 'autor': 'Alguien',
                     'licencia': 'CC BY 2.5', 'tamano': '800x600',
                     'url': 'https://ejemplo.org/foto.jpg', 'pagina': 'https://ejemplo.org/pagina'}
        cuerpo = b'\xff\xd8\xff' + b'0' * 500  # cabecera JPEG + relleno

        def _pedir(url, datos=None, cabeceras=None, timeout=None, metodo=None):
            self.assertEqual(url, candidato['url'])
            return 200, cuerpo, 'image/jpeg'

        with tempfile.TemporaryDirectory() as d:
            ruta_img, ruta_txt = mundo.descargar(candidato, d, pedir_fn=_pedir)
            self.assertTrue(os.path.exists(ruta_img))
            self.assertTrue(ruta_img.endswith('.jpg'))
            self.assertTrue(os.path.exists(ruta_txt))
            with open(ruta_img, 'rb') as fh:
                self.assertEqual(fh.read(), cuerpo)
            with open(ruta_txt, encoding='utf-8') as fh:
                atribucion = fh.read()
            self.assertIn('Un motivo', atribucion)
            self.assertIn('Alguien', atribucion)
            self.assertIn('CC BY 2.5', atribucion)
            self.assertIn('commons', atribucion)
            self.assertIn('800x600', atribucion)

    def test_sin_url_lanza_sin_tocar_la_red(self):
        with self.assertRaises(RuntimeError):
            mundo.descargar({'fuente': 'x'}, tempfile.mkdtemp(), pedir_fn=_pedir_nunca)

    def test_http_no_200_lanza(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(RuntimeError):
                mundo.descargar({'fuente': 'x', 'url': 'https://e.org/f.jpg'}, d,
                                 pedir_fn=lambda *a, **k: (404, b'', 'text/plain'))


# ── CLI: `mundo._cli(argv, mem, pedir_fn=...)`, en proceso (sin subprocess) ──

class CLI(unittest.TestCase):
    def setUp(self):
        self.proj = ay.nuevo_proyecto()
        self.mem = self.proj / 'memory'
        self.mem.mkdir(exist_ok=True)

    def _correr(self, argv, pedir_fn=_pedir_nunca):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            codigo = mundo._cli(argv, str(self.mem), pedir_fn=pedir_fn)
        return codigo, buf.getvalue()

    def test_sin_motivo_devuelve_1(self):
        codigo, salida = self._correr([])
        self.assertEqual(codigo, 1)

    def test_fuente_desconocida_devuelve_1(self):
        codigo, salida = self._correr(['x', '--fuente', 'flickr'])
        self.assertEqual(codigo, 1)

    def test_lugar_malformado_devuelve_1(self):
        codigo, salida = self._correr(['x', '--lugar', 'nosecuantos'])
        self.assertEqual(codigo, 1)

    def test_n_no_numerico_devuelve_1(self):
        codigo, salida = self._correr(['x', '--n', 'tres'])
        self.assertEqual(codigo, 1)

    def test_argumento_desconocido_devuelve_1(self):
        codigo, salida = self._correr(['x', '--que-se-yo'])
        self.assertEqual(codigo, 1)

    def test_streetview_sin_clave_devuelve_1_y_avisa_sin_traza(self):
        codigo, salida = self._correr(['x', '--fuente', 'streetview', '--lugar', '1,2'])
        self.assertEqual(codigo, 1, salida)
        self.assertIn('sin clave', salida)
        self.assertNotIn('Traceback', salida)

    def test_busqueda_met_devuelve_0_imprime_candidatos_y_no_llama_a_wikidata(self):
        pedir = _pedir_por_ruta(MET_ABIERTO, prohibidas=('wikidata.org',))
        codigo, salida = self._correr(['Rembrandt', '--fuente', 'met', '--n', '1'], pedir_fn=pedir)
        self.assertEqual(codigo, 0, salida)
        self.assertIn('[met]', salida)
        self.assertNotIn('contexto (', salida, 'met no necesita lugar: no debe pedir contexto')

    def test_lee_la_clave_del_imagen_config_json_y_deriva_lugar_una_sola_vez(self):
        (self.mem / 'imagen_config.json').write_text(json.dumps({'google_maps_key': 'ABC'}), encoding='utf-8')
        llamadas_wikidata = []

        def _wikidata(url):
            llamadas_wikidata.append(url)
            return 200, _cargar('mundo_wikidata_vacio.json'), 'application/json'

        pedir = _pedir_por_ruta([('wikidata.org/w/api.php', _wikidata)], prohibidas=('googleapis.com',))
        codigo, salida = self._correr(['x', '--fuente', 'streetview'], pedir_fn=pedir)
        self.assertEqual(codigo, 2, salida)  # sin clave YA no es el problema: ahora es "sin lugar"
        self.assertIn('sin lugar', salida)
        self.assertEqual(len(llamadas_wikidata), 1, 'el contexto ya calculado por la CLI no debe volver a pedirse')

    def test_descargar_guarda_fichero_bajo_mem_imagenes(self):
        cuerpo = b'\xff\xd8\xff' + b'0' * 500

        def _pedir(url, datos=None, cabeceras=None, timeout=None, metodo=None):
            if 'metmuseum.org/public/collection/v1/search' in url:
                return 200, _cargar('mundo_met_search.json'), 'application/json'
            if 'metmuseum.org/public/collection/v1/objects/' in url:
                return _objeto_met_437394_o_vacio(url)
            if url.startswith('https://images.metmuseum.org'):
                return 200, cuerpo, 'image/jpeg'
            raise AssertionError(f'URL no esperada: {url}')

        codigo, salida = self._correr(['Rembrandt', '--fuente', 'met', '--n', '1', '--descargar'], pedir_fn=_pedir)
        self.assertEqual(codigo, 0, salida)
        self.assertIn('descargado:', salida)
        imagenes = list((self.mem / 'imagenes').glob('mundo_met_*'))
        self.assertTrue(any(p.suffix != '.txt' for p in imagenes))
        self.assertTrue(any(p.suffix == '.txt' for p in imagenes))


if __name__ == '__main__':
    unittest.main()
