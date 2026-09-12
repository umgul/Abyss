"""`rutas.Presupuesto` acota el tiempo total de red de una misma invocación de
`continuidad.py --arranque`: agotado, las llamadas siguientes fallan al instante
sin tocar la red, y `noticias.recoger()` deja de intentar temas si la portada ya falló."""
import sys
import os
from pathlib import Path
from unittest import mock
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'abyss'))
import unittest
import ayudas as ay

# exterocepcion.py y noticias.py, a diferencia de continuidad.py/vigia.py/varas.py/
# propiocepcion.py, no llaman a rutas.resolver() al importarse (solo dentro de
# funciones): por eso aquí se importan directamente, sin subprocess.
import rutas
import exterocepcion
import noticias


class _UrlopenNuncaLlamado:
    def __call__(self, *a, **kw):
        raise AssertionError('urlopen no debía llamarse: el presupuesto ya estaba agotado')


class PresupuestoMecanica(unittest.TestCase):
    """`rutas.Presupuesto` en sí, sin red de por medio."""

    def test_agotado_desde_el_principio(self):
        p = rutas.Presupuesto(0)
        self.assertTrue(p.agotado())
        with self.assertRaises(TimeoutError):
            p.restante()

    def test_no_agotado_con_tiempo_por_delante(self):
        p = rutas.Presupuesto(10)
        self.assertFalse(p.agotado())
        self.assertLessEqual(p.restante(tope=3), 3)
        self.assertGreater(p.restante(), 0)


class PresupuestoCortaLaRedExterocepcion(unittest.TestCase):
    def setUp(self):
        exterocepcion._CACHE.clear()

    def tearDown(self):
        exterocepcion._CACHE.clear()

    def test_get_con_presupuesto_agotado_no_toca_la_red(self):
        presupuesto = rutas.Presupuesto(0)  # agotado desde el instante en que se crea
        with mock.patch('urllib.request.urlopen', _UrlopenNuncaLlamado()):
            with self.assertRaises(TimeoutError):
                exterocepcion._get('https://ipinfo.io/json', presupuesto=presupuesto)

    def test_abyss_sin_red_corta_al_instante_sin_presupuesto(self):
        with mock.patch.dict(os.environ, {'ABYSS_SIN_RED': '1'}):
            with mock.patch('urllib.request.urlopen', _UrlopenNuncaLlamado()):
                with self.assertRaises(Exception):
                    exterocepcion._get('https://ipinfo.io/json')


class PresupuestoCortaLaRedNoticias(unittest.TestCase):
    def setUp(self):
        noticias._CACHE.clear()

    def tearDown(self):
        noticias._CACHE.clear()

    def test_rss_con_presupuesto_agotado_no_toca_la_red(self):
        presupuesto = rutas.Presupuesto(0)
        with mock.patch('urllib.request.urlopen', _UrlopenNuncaLlamado()):
            with self.assertRaises(TimeoutError):
                noticias.rss('https://news.google.com/rss?hl=es&gl=ES&ceid=ES:es', 6, presupuesto=presupuesto)

    def test_abyss_sin_red_corta_al_instante_sin_presupuesto(self):
        with mock.patch.dict(os.environ, {'ABYSS_SIN_RED': '1'}):
            with mock.patch('urllib.request.urlopen', _UrlopenNuncaLlamado()):
                with self.assertRaises(Exception):
                    noticias.rss('https://news.google.com/rss?hl=es&gl=ES&ceid=ES:es', 6)


class RecogerSaltaLosTemasSiLaPortadaFalla(unittest.TestCase):
    def setUp(self):
        self.proj = ay.nuevo_proyecto()
        (self.proj / 'memory').mkdir(parents=True, exist_ok=True)
        (self.proj / 'memory' / 'temas_noticias.json').write_text(
            '["tema uno", "tema dos", "tema tres", "tema cuatro", "tema cinco"]', encoding='utf-8')
        self._proyecto_previo = os.environ.get('ABYSS_PROYECTO')
        os.environ['ABYSS_PROYECTO'] = str(self.proj)
        noticias._CACHE.clear()

    def tearDown(self):
        noticias._CACHE.clear()
        if self._proyecto_previo is None:
            os.environ.pop('ABYSS_PROYECTO', None)
        else:
            os.environ['ABYSS_PROYECTO'] = self._proyecto_previo

    def test_un_solo_intento_de_red_si_la_portada_falla(self):
        llamadas = []

        def rss_falla_siempre(url, n, timeout=3, presupuesto=None):
            llamadas.append(url)
            raise RuntimeError('red caída (simulada)')

        # autoactualizar_temas importa continuidad.py (SÍ resuelve rutas.resolver()
        # al importarse); se sustituye por un no-op para no arrastrar ese import aquí.
        with mock.patch.object(noticias, 'autoactualizar_temas', return_value=({}, [])), \
             mock.patch.object(noticias, 'rss', side_effect=rss_falla_siempre):
            out = noticias.recoger(tp=None)

        self.assertEqual(len(llamadas), 1,
                          'con la portada caída, NO debe intentarse ningún tema más '
                          f'(se intentaron {len(llamadas)}: {llamadas})')
        self.assertEqual(out['portada'], [])
        self.assertEqual(out['temas'], {})

    def test_intenta_los_temas_si_la_portada_sale_bien(self):
        llamadas = []

        def rss_falso(url, n, timeout=3, presupuesto=None):
            llamadas.append(url)
            if 'search?q=' not in url:  # portada
                return [('titular', 'fuente')]
            return []  # cada tema, sin titulares suficientes (no llega a guardarse)

        with mock.patch.object(noticias, 'autoactualizar_temas', return_value=({}, [])), \
             mock.patch.object(noticias, 'rss', side_effect=rss_falso):
            noticias.recoger(tp=None)

        # 1 portada + 5 temas de temas_noticias.json (temas_efectivos()[:8])
        self.assertEqual(len(llamadas), 6, f'se esperaban 6 intentos, hubo {len(llamadas)}: {llamadas}')


if __name__ == '__main__':
    unittest.main()
