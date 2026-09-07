"""Fallo medido 6-sep ("rompe"): `continuidad.py --arranque` hace red (ipinfo.io vía
`exterocepcion.py`, portada + hasta 8 temas vía `noticias.py`) SIN presupuesto: con
la red en agujero negro (paquetes descartados — wifi caída, portal cautivo,
cortafuegos) cada llamada consumía su timeout entero (6-8 s) y el total crecía con
el NÚMERO de llamadas — medido 38-78 s, por encima del timeout de 60 s del propio
gancho SessionStart, perdiendo el JSON entero de `additionalContext`.

Arreglo: `rutas.Presupuesto`, compartido entre todas las llamadas de red de una
misma invocación — agotado, las llamadas siguientes fallan al instante (sin tocar
la red), y `noticias.recoger()` ya no intenta los temas si la portada falló (antes
repetía el mismo fallo hasta 8 veces más).

Estas pruebas importan `exterocepcion.py`/`noticias.py` DIRECTAMENTE (no por
subprocess): a diferencia de `continuidad.py`/`vigia.py`/`varas.py`/`propiocepcion.py`,
ninguno de los dos hace `rutas.resolver()` a nivel de módulo (solo dentro de
funciones), así que importarlos aquí no aborta el proceso de `unittest` (ver
docstring de `ayudas.py`). SIEMPRE se sustituye `urllib.request.urlopen` por un
doble de prueba: en ningún caso debe salir una petición real (regla dura 2 del
encargo: "sin red en la suite")."""
import sys
import os
from pathlib import Path
from unittest import mock
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'abyss'))
import unittest
import ayudas as ay

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
        """`ABYSS_SIN_RED=1` (fallo 6-sep, "la suite no es independiente de la red"):
        corta la red al instante, INCLUSO sin ningún presupuesto de por medio."""
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
    """Antes: si la portada fallaba (sin red), `recoger()` intentaba IGUAL hasta 8
    temas más — cada uno repetía el mismo fallo, multiplicando por 9 el tiempo total
    en agujero negro (el núcleo medible del fallo 6-sep). Ahora se salta el resto en
    cuanto la portada falla."""

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

        # autoactualizar_temas no se mide aquí (tiene su propio candado de red vía
        # `nombres_propios_recurrentes`, que importa `continuidad.py` — módulo que
        # SÍ resuelve `rutas.resolver()` al importarse; se sustituye por un no-op
        # para no arrastrar ese import al proceso de esta prueba).
        with mock.patch.object(noticias, 'autoactualizar_temas', return_value=({}, [])), \
             mock.patch.object(noticias, 'rss', side_effect=rss_falla_siempre):
            out = noticias.recoger(tp=None)

        self.assertEqual(len(llamadas), 1,
                          'con la portada caída, NO debe intentarse ningún tema más '
                          f'(se intentaron {len(llamadas)}: {llamadas})')
        self.assertEqual(out['portada'], [])
        self.assertEqual(out['temas'], {})

    def test_intenta_los_temas_si_la_portada_sale_bien(self):
        """Contraprueba: si la portada SÍ responde, los temas se siguen intentando
        con normalidad (el salto es solo cuando la portada falla, no siempre)."""
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
