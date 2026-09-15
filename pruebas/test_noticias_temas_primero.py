"""noticias.recoger(): dentro del presupuesto de red se piden PRIMERO los temas
efectivos y los candidatos automáticos solo con lo que sobra; y una caché de hoy con
portada pero sin temas, habiendo temas efectivos, es una recogida a medias que se
reintenta (solo los temas, reutilizando la portada) hasta `REINTENTOS_TEMAS` veces al día.

Falsa el fallo medido el 15-sep-2026: con los candidatos por delante y 4 s de
presupuesto, `temas` llegaba vacío y la caché se daba por buena hasta el día siguiente."""
import sys
import os
import re
import json
import time
from pathlib import Path
from unittest import mock
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'abyss'))
import unittest
import ayudas as ay

import noticias

PORTADA = 'https://news.google.com/rss?hl=es&gl=ES&ceid=ES:es'


class _PresupuestoContado:
    """Como `rutas.Presupuesto`, pero se agota tras `n` llamadas de red en vez de por
    reloj: determinista, sin dormir."""

    def __init__(self, n):
        self.n = n
        self.usadas = 0

    def agotado(self):
        return self.usadas >= self.n

    def restante(self, tope=None):
        if self.agotado():
            raise TimeoutError('presupuesto de red agotado')
        self.usadas += 1
        return tope if tope is not None else 3


def _rss_falso(llamadas, portada_ok=True, titulares_tema=2):
    def rss(url, n, timeout=3, presupuesto=None):
        if presupuesto is not None:
            presupuesto.restante(timeout)  # como el rss real: agotado, ni lo intenta
        llamadas.append(url)
        if 'search?q=' not in url:
            if not portada_ok:
                raise RuntimeError('portada caída (simulada)')
            return [('titular', 'fuente')]
        return [(f't{i}', f'f{i}') for i in range(titulares_tema)]
    return rss


class _Base(unittest.TestCase):
    def setUp(self):
        self.proj = ay.nuevo_proyecto()
        self.mem = self.proj / 'memory'
        self.mem.mkdir(parents=True, exist_ok=True)
        self.ruta_cache = self.mem / 'noticias.json'
        (self.mem / 'temas_noticias.json').write_text('["tema uno", "tema dos"]', encoding='utf-8')
        self._proyecto_previo = os.environ.get('ABYSS_PROYECTO')
        os.environ['ABYSS_PROYECTO'] = str(self.proj)
        noticias._CACHE.clear()

    def tearDown(self):
        noticias._CACHE.clear()
        if self._proyecto_previo is None:
            os.environ.pop('ABYSS_PROYECTO', None)
        else:
            os.environ['ABYSS_PROYECTO'] = self._proyecto_previo

    def _cache(self, **campos):
        c = {'dia': time.strftime('%Y-%m-%d'), 'portada': [['titular viejo', 'fuente vieja']], 'temas': {}}
        c.update(campos)
        self.ruta_cache.write_text(json.dumps(c), encoding='utf-8')
        return c

    def _guardado(self):
        return json.loads(self.ruta_cache.read_text(encoding='utf-8'))


class LosTemasEfectivosVanPrimero(_Base):
    def test_los_temas_se_piden_antes_que_los_candidatos(self):
        llamadas = []

        def auto_falso(tp=None, presupuesto=None):
            llamadas.append('AUTOACTUALIZAR')
            return {}, []

        with mock.patch.object(noticias, 'autoactualizar_temas', side_effect=auto_falso), \
             mock.patch.object(noticias, 'rss', side_effect=_rss_falso(llamadas)):
            out = noticias.recoger(tp=None)

        self.assertEqual(llamadas[0], PORTADA)
        temas = [u for u in llamadas if 'search?q=' in u]
        self.assertEqual(len(temas), 2, llamadas)
        i_auto = llamadas.index('AUTOACTUALIZAR')
        self.assertTrue(all(llamadas.index(u) < i_auto for u in temas),
                        f'los temas efectivos deben pedirse ANTES que los candidatos: {llamadas}')
        self.assertEqual(set(out['temas']), {'tema uno', 'tema dos'})

    def test_con_presupuesto_justo_entran_los_temas_y_no_los_candidatos(self):
        llamadas = []
        presupuesto = _PresupuestoContado(3)  # portada + 2 temas: justo lo que el usuario ve

        def auto_no_debe(tp=None, presupuesto=None):
            raise AssertionError('agotado el presupuesto tras los temas, los candidatos no se validan')

        with mock.patch.object(noticias, 'autoactualizar_temas', side_effect=auto_no_debe), \
             mock.patch.object(noticias, 'rss', side_effect=_rss_falso(llamadas)):
            out = noticias.recoger(tp=None, presupuesto=presupuesto)

        self.assertEqual(set(out['temas']), {'tema uno', 'tema dos'})
        self.assertEqual(set(self._guardado()['temas']), {'tema uno', 'tema dos'})

    def test_un_tema_recien_admitido_recibe_titulares_hoy_y_uno_retirado_sale(self):
        (self.mem / 'temas_auto.json').write_text(json.dumps({'Viejo Tema': {'ultimo_ok': 0}}), encoding='utf-8')
        llamadas = []

        def auto_falso(tp=None, presupuesto=None):
            return ({'Nuevo Tema': {'ultimo_ok': time.time()}},
                    [('añadido', 'Nuevo Tema', 'parecido 0.100'), ('retirado', 'Viejo Tema', 'caducado o vetado')])

        with mock.patch.object(noticias, 'autoactualizar_temas', side_effect=auto_falso), \
             mock.patch.object(noticias, 'rss', side_effect=_rss_falso(llamadas)):
            out = noticias.recoger(tp=None)

        self.assertEqual(set(out['temas']), {'tema uno', 'tema dos', 'Nuevo Tema'})
        self.assertNotIn('Viejo Tema', out['temas'])


class LaPortadaSolaNoEsUnaCacheBuena(_Base):
    def test_cache_de_hoy_con_portada_y_sin_temas_reintenta_solo_los_temas(self):
        self._cache()
        llamadas = []

        with mock.patch.object(noticias, 'autoactualizar_temas',
                               side_effect=AssertionError('en un reintento de temas no se recalculan candidatos')), \
             mock.patch.object(noticias, 'rss', side_effect=_rss_falso(llamadas, portada_ok=False)):
            out = noticias.recoger(tp=None)

        self.assertNotIn(PORTADA, llamadas, 'la portada de hoy se reutiliza, no se vuelve a pedir')
        self.assertEqual(set(out['temas']), {'tema uno', 'tema dos'})
        self.assertEqual(out['portada'], [['titular viejo', 'fuente vieja']])
        guardado = self._guardado()
        self.assertEqual(set(guardado['temas']), {'tema uno', 'tema dos'})
        self.assertEqual(guardado['portada'], [['titular viejo', 'fuente vieja']])
        self.assertEqual(guardado['intentos_temas'], 1)

    def test_cada_reintento_sin_titulares_cuenta(self):
        self._cache(intentos_temas=1)
        llamadas = []

        with mock.patch.object(noticias, 'autoactualizar_temas', return_value=({}, [])), \
             mock.patch.object(noticias, 'rss', side_effect=_rss_falso(llamadas, titulares_tema=0)):
            out = noticias.recoger(tp=None)

        self.assertEqual(out['temas'], {})
        self.assertEqual(self._guardado()['intentos_temas'], 2)
        self.assertEqual(self._guardado()['portada'], [['titular viejo', 'fuente vieja']])

    def test_los_reintentos_de_temas_se_acotan_por_dia(self):
        c = self._cache(intentos_temas=noticias.REINTENTOS_TEMAS)

        with mock.patch.object(noticias, 'autoactualizar_temas', return_value=({}, [])), \
             mock.patch.object(noticias, 'rss', side_effect=AssertionError('rss no debía llamarse: reintentos del día agotados')):
            out = noticias.recoger(tp=None)

        self.assertEqual(out, c)

    def test_con_el_presupuesto_ya_agotado_no_se_gasta_un_reintento(self):
        c = self._cache()

        with mock.patch.object(noticias, 'autoactualizar_temas', return_value=({}, [])), \
             mock.patch.object(noticias, 'rss', side_effect=AssertionError('rss no debía llamarse: presupuesto agotado')):
            out = noticias.recoger(tp=None, presupuesto=_PresupuestoContado(0))

        self.assertEqual(out, c)
        self.assertEqual(self._guardado(), c, 'sin intento de red, la caché no cambia ni cuenta el reintento')

    def test_sin_temas_efectivos_la_portada_sola_es_completa(self):
        (self.mem / 'temas_noticias.json').write_text('[]', encoding='utf-8')
        c = self._cache()

        with mock.patch.object(noticias, 'autoactualizar_temas', return_value=({}, [])), \
             mock.patch.object(noticias, 'rss', side_effect=AssertionError('rss no debía llamarse: no hay temas que pedir')):
            out = noticias.recoger(tp=None)

        self.assertEqual(out, c)

    def test_cache_de_hoy_con_temas_no_vuelve_a_pedir(self):
        c = self._cache(temas={'tema uno': [['t', 'f'], ['t2', 'f2']]})

        with mock.patch.object(noticias, 'autoactualizar_temas', return_value=({}, [])), \
             mock.patch.object(noticias, 'rss', side_effect=AssertionError('rss no debía llamarse: la caché de hoy ya trae temas')):
            out = noticias.recoger(tp=None)

        self.assertEqual(out, c)


class ElPresupuestoDelArranqueEstaDocumentado(unittest.TestCase):
    """El valor por defecto de `PRESUPUESTO_ARRANQUE_S` en `continuidad.py` es el que
    dicen los dos README (12 s desde el 15-sep-2026: con 4 s los temas no cabían)."""

    def _defecto(self):
        src = (ay.PKG / 'continuidad.py').read_text(encoding='utf-8')
        m = re.search(r"ABYSS_PRESUPUESTO_ARRANQUE',\s*([\d.]+)\)", src)
        self.assertIsNotNone(m, 'no encuentro el valor por defecto de ABYSS_PRESUPUESTO_ARRANQUE')
        return float(m.group(1))

    def test_no_vuelve_a_los_4_segundos_que_dejaban_los_temas_fuera(self):
        self.assertGreaterEqual(self._defecto(), 12.0)

    def test_los_dos_readme_dicen_el_mismo_valor(self):
        v = self._defecto()
        self.assertIn(f'{v:g} s y 2,5 s', (ay.RAIZ / 'README.md').read_text(encoding='utf-8'))
        self.assertIn(f'{v:g} s and 2.5 s', (ay.RAIZ / 'README.en.md').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
