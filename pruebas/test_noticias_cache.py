"""noticias.recoger(): una caché de hoy solo cuenta si trae algo (portada o temas); una
recogida vacía (sin red, presupuesto agotado) no se escribe, para no machacar una caché
buena ya escrita y para que el siguiente arranque vuelva a intentarlo."""
import sys
import os
import json
import time
from pathlib import Path
from unittest import mock
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'abyss'))
import unittest
import ayudas as ay

import noticias


class RecogerCacheDelDiaSoloSiTraeAlgo(unittest.TestCase):
    def setUp(self):
        self.proj = ay.nuevo_proyecto()
        (self.proj / 'memory').mkdir(parents=True, exist_ok=True)
        self.ruta_cache = self.proj / 'memory' / 'noticias.json'
        self._proyecto_previo = os.environ.get('ABYSS_PROYECTO')
        os.environ['ABYSS_PROYECTO'] = str(self.proj)
        noticias._CACHE.clear()

    def tearDown(self):
        noticias._CACHE.clear()
        if self._proyecto_previo is None:
            os.environ.pop('ABYSS_PROYECTO', None)
        else:
            os.environ['ABYSS_PROYECTO'] = self._proyecto_previo

    def test_rss_fallando_sin_cache_previa_no_escribe_fichero(self):
        def rss_falla_siempre(url, n, timeout=3, presupuesto=None):
            raise RuntimeError('red caída (simulada)')

        with mock.patch.object(noticias, 'autoactualizar_temas', return_value=({}, [])), \
             mock.patch.object(noticias, 'rss', side_effect=rss_falla_siempre):
            out = noticias.recoger(tp=None)

        self.assertEqual(out['portada'], [])
        self.assertEqual(out['temas'], {})
        self.assertFalse(self.ruta_cache.exists(), 'una recogida vacía no debe dejar noticias.json')

    def test_sin_portada_no_recalcula_los_temas_automaticos(self):
        def rss_falla_siempre(url, n, timeout=3, presupuesto=None):
            raise RuntimeError('red caída (simulada)')

        with mock.patch.object(noticias, 'autoactualizar_temas',
                               side_effect=AssertionError('no debía recalcular temas sin portada')), \
             mock.patch.object(noticias, 'rss', side_effect=rss_falla_siempre):
            noticias.recoger(tp=None)

    def test_rss_fallando_con_cache_buena_previa_la_deja_intacta(self):
        hoy = time.strftime('%Y-%m-%d')
        buena = {'dia': hoy, 'portada': [['titular viejo', 'fuente vieja']], 'temas': {}}
        self.ruta_cache.write_text(json.dumps(buena), encoding='utf-8')

        def rss_falla_siempre(url, n, timeout=3, presupuesto=None):
            raise RuntimeError('red caída (simulada)')

        with mock.patch.object(noticias, 'autoactualizar_temas', return_value=({}, [])), \
             mock.patch.object(noticias, 'rss', side_effect=rss_falla_siempre):
            noticias.recoger(refrescar=True, tp=None)  # fuerza el intento aunque la caché de hoy ya sea buena

        self.assertEqual(json.loads(self.ruta_cache.read_text(encoding='utf-8')), buena,
                          'una recogida vacía no debe machacar una caché buena de hoy')

    def test_cache_vacia_de_hoy_no_bloquea_vuelve_a_pedir(self):
        hoy = time.strftime('%Y-%m-%d')
        self.ruta_cache.write_text(json.dumps({'dia': hoy, 'portada': [], 'temas': {}}), encoding='utf-8')
        llamadas = []

        def rss_ok(url, n, timeout=3, presupuesto=None):
            llamadas.append(url)
            if 'search?q=' not in url:
                return [('titular nuevo', 'fuente nueva')]
            return []  # ningún tema llega a 2 titulares; no importa para esta prueba

        with mock.patch.object(noticias, 'autoactualizar_temas', return_value=({}, [])), \
             mock.patch.object(noticias, 'rss', side_effect=rss_ok):
            out = noticias.recoger(tp=None)

        self.assertTrue(llamadas, 'una caché de hoy vacía no debe impedir que se vuelva a intentar')
        self.assertEqual(out['portada'], [('titular nuevo', 'fuente nueva')])
        guardado = json.loads(self.ruta_cache.read_text(encoding='utf-8'))
        self.assertEqual(guardado['portada'], [['titular nuevo', 'fuente nueva']])

    def test_cache_buena_de_hoy_no_vuelve_a_pedir(self):
        hoy = time.strftime('%Y-%m-%d')
        buena = {'dia': hoy, 'portada': [['titular', 'fuente']], 'temas': {}}
        self.ruta_cache.write_text(json.dumps(buena), encoding='utf-8')

        def rss_no_debe_llamarse(url, n, timeout=3, presupuesto=None):
            raise AssertionError('rss no debía llamarse: la caché de hoy ya era buena')

        with mock.patch.object(noticias, 'autoactualizar_temas', return_value=({}, [])), \
             mock.patch.object(noticias, 'rss', side_effect=rss_no_debe_llamarse):
            out = noticias.recoger(tp=None)

        self.assertEqual(out, buena)


if __name__ == '__main__':
    unittest.main()
