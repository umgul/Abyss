# -*- coding: utf-8 -*-
"""`ojo.py` (ESPECIFICACION_TANDA4.md, T4.6): ocho verbos, un solo punto de entrada.
`mirar` es "lo de hoy" (sin cambios); los otros siete DELEGAN enteros en
`lectura_visual._cli()`, `volumen._cli()` o `gestos._cli()` — nunca repiten su lógica
de visión.

Esta prueba nunca ejerce una cámara, un escáner ni un servidor HTTP real: monkeypatch
sobre las PIEZAS delegadas (no sobre `ojo.py`), para comprobar SOLO el cableado — qué
verbo llama a qué módulo con qué argv exacto — sin arrastrar sus propias dependencias
(numpy/cv2 de `volumen.py`, `mediapipe` de `gestos.py`) ni su comportamiento real, que
ya prueban `test_lectura_visual.py`/`test_volumen.py`/`test_gestos.py` cada uno el
suyo. Para `mirar` (que no delega en nada), se inyecta un `cv2` FALSO en
`sys.modules` — nunca el real ni ninguna cámara — así el resultado no depende de si
esta máquina tiene OpenCV instalado ni de qué cámaras tenga conectadas.

`ojo.py` no llama a `rutas.resolver()` fuera de `main()` (guardado tras
`if __name__ == '__main__':`, igual que `lectura_visual.py`/`volumen.py`/
`gestos.py`): se puede importar DIRECTAMENTE en el proceso de la prueba y llamar a
`ojo._cli(argv, proj, mem)` con un `proj`/`mem` de mentira, sin tocar stdin real."""
import io
import os
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ayudas as ay  # noqa: E402

sys.path.insert(0, str(ay.PKG))
import ojo  # noqa: E402  (sin rutas.resolver() fuera de main(): seguro importarlo aquí)
import lectura_visual  # noqa: E402
import volumen  # noqa: E402
import gestos  # noqa: E402


def _cv2_falso():
    """Un `cv2` de mentira: `VideoCapture(...)` nunca se abre, nunca toca hardware
    real. Se inyecta en `sys.modules['cv2']` justo antes de la llamada y se
    restaura siempre después (`addCleanup`), para no dejarlo puesto para el resto
    de la suite si esta prueba corre junto a otras en el mismo proceso."""
    class _CapFalsa:
        def __init__(self, *a, **k):
            pass

        def isOpened(self):
            return False

        def release(self):
            pass

    m = types.ModuleType('cv2')
    m.CAP_DSHOW = 700  # valor real de cv2.CAP_DSHOW; aquí solo hace falta que exista
    m.VideoCapture = lambda *a, **k: _CapFalsa()
    return m


class LosOchoVerbosExisten(unittest.TestCase):
    def test_son_exactamente_estos_ocho_en_este_orden(self):
        self.assertEqual(
            ojo.VERBOS,
            ('mirar', 'texto', 'fotocopia', 'tarjeta', 'manual', 'despiece', 'prompt3d', 'gestos'))

    def test_verbo_desconocido_no_revienta_y_lista_los_ocho(self):
        salida = io.StringIO()
        with redirect_stdout(salida):
            codigo = ojo._cli(['inventado'], proj='/x', mem='/x/memory')
        self.assertEqual(codigo, 1)
        texto = salida.getvalue()
        self.assertIn('verbo desconocido', texto)
        for verbo in ojo.VERBOS:
            self.assertIn(verbo, texto)

    def test_sin_argumentos_imprime_la_ayuda_con_los_ocho_usos(self):
        salida = io.StringIO()
        with redirect_stdout(salida):
            codigo = ojo._cli([], proj='/x', mem='/x/memory')
        self.assertEqual(codigo, 1)
        texto = salida.getvalue()
        for verbo in ojo.VERBOS:
            self.assertIn(f'ojo.py {verbo}', texto)

    def test_ayuda_explicita_con_h_y_con_help(self):
        for bandera in ('-h', '--help'):
            salida = io.StringIO()
            with redirect_stdout(salida):
                codigo = ojo._cli([bandera], proj='/x', mem='/x/memory')
            self.assertEqual(codigo, 1)
            self.assertIn('mirar', salida.getvalue())


class VerbosDeLecturaVisualDelegan(unittest.TestCase):
    """`texto`/`fotocopia`/`tarjeta`/`manual` delegan ENTERO en
    `lectura_visual._cli()`, con el propio verbo antepuesto al resto del argv —
    ni un carácter menos, ni transformado."""

    def test_texto_delega_con_su_argv_exacto(self):
        with mock.patch.object(lectura_visual, '_cli', return_value=0) as falso:
            codigo = ojo._cli(['texto', 'foto.png', '--portapapeles'], proj='/x', mem='/x/memory')
        self.assertEqual(codigo, 0)
        falso.assert_called_once_with(['texto', 'foto.png', '--portapapeles'])

    def test_fotocopia_delega_y_propaga_el_codigo_de_salida(self):
        with mock.patch.object(lectura_visual, '_cli', return_value=2) as falso:
            codigo = ojo._cli(['fotocopia', '--camara', '0', '--umbral'], proj='/x', mem='/x/memory')
        self.assertEqual(codigo, 2, 'el código de salida del módulo delegado debe propagarse tal cual')
        falso.assert_called_once_with(['fotocopia', '--camara', '0', '--umbral'])

    def test_tarjeta_delega(self):
        with mock.patch.object(lectura_visual, '_cli', return_value=0) as falso:
            ojo._cli(['tarjeta', 'foto.png', '--salida', 'base'], proj='/x', mem='/x/memory')
        falso.assert_called_once_with(['tarjeta', 'foto.png', '--salida', 'base'])

    def test_manual_delega_con_varias_imagenes(self):
        with mock.patch.object(lectura_visual, '_cli', return_value=0) as falso:
            ojo._cli(['manual', 'p1.png', 'p2.png', 'p3.png'], proj='/x', mem='/x/memory')
        falso.assert_called_once_with(['manual', 'p1.png', 'p2.png', 'p3.png'])

    def test_ninguno_de_los_cuatro_toca_volumen_ni_gestos(self):
        with mock.patch.object(lectura_visual, '_cli', return_value=0), \
             mock.patch.object(volumen, '_cli') as vo, \
             mock.patch.object(gestos, '_cli') as ge:
            ojo._cli(['texto', 'foto.png'], proj='/x', mem='/x/memory')
        vo.assert_not_called()
        ge.assert_not_called()


class VerbosDeVolumenDelegan(unittest.TestCase):
    """`despiece`/`prompt3d` delegan ENTERO en `volumen._cli()`, mismo patrón."""

    def test_despiece_delega_con_su_argv_exacto(self):
        with mock.patch.object(volumen, '_cli', return_value=0) as falso:
            codigo = ojo._cli(['despiece', 'foto.png', '--capas', '3', '--html'], proj='/x', mem='/x/memory')
        self.assertEqual(codigo, 0)
        falso.assert_called_once_with(['despiece', 'foto.png', '--capas', '3', '--html'])

    def test_prompt3d_delega_y_propaga_el_codigo_de_salida(self):
        with mock.patch.object(volumen, '_cli', return_value=2) as falso:
            codigo = ojo._cli(['prompt3d', 'foto.png', '--escena', 'e.json'], proj='/x', mem='/x/memory')
        self.assertEqual(codigo, 2)
        falso.assert_called_once_with(['prompt3d', 'foto.png', '--escena', 'e.json'])

    def test_ninguno_de_los_dos_toca_lectura_visual_ni_gestos(self):
        with mock.patch.object(volumen, '_cli', return_value=0), \
             mock.patch.object(lectura_visual, '_cli') as lv, \
             mock.patch.object(gestos, '_cli') as ge:
            ojo._cli(['prompt3d', 'foto.png'], proj='/x', mem='/x/memory')
        lv.assert_not_called()
        ge.assert_not_called()


class VerboGestosDelega(unittest.TestCase):
    def test_gestos_delega_sin_anteponer_el_nombre_del_verbo(self):
        # gestos._cli() NO lleva un verbo como primer argumento (solo banderas de
        # cámara/puerto/escena/holograma/vocabulario) — a diferencia de los otros
        # seis, aquí NO se antepone "gestos" al argv que recibe.
        with mock.patch.object(gestos, '_cli', return_value=0) as falso:
            codigo = ojo._cli(['gestos', '--camara', '1', '--holograma'], proj='/x', mem='/x/memory')
        self.assertEqual(codigo, 0)
        falso.assert_called_once_with(['--camara', '1', '--holograma'])

    def test_gestos_sin_banderas_delega_con_argv_vacio(self):
        with mock.patch.object(gestos, '_cli', return_value=0) as falso:
            ojo._cli(['gestos'], proj='/x', mem='/x/memory')
        falso.assert_called_once_with([])

    def test_gestos_no_toca_lectura_visual_ni_volumen(self):
        with mock.patch.object(gestos, '_cli', return_value=0), \
             mock.patch.object(lectura_visual, '_cli') as lv, \
             mock.patch.object(volumen, '_cli') as vo:
            ojo._cli(['gestos'], proj='/x', mem='/x/memory')
        lv.assert_not_called()
        vo.assert_not_called()


class VerboMirarNoDelegaEnNada(unittest.TestCase):
    """`mirar` es la única pieza que NO delega (ver docstring de `ojo.py`): se
    comprueba con un `cv2` FALSO inyectado en `sys.modules` — nunca la cámara
    real — que ninguno de los tres módulos delegados se llama, y que el código
    de salida/mensaje son los mismos que "lo de hoy" daba con una cámara que
    nunca llega a abrirse."""

    def setUp(self):
        self._cv2_previo = sys.modules.get('cv2')
        sys.modules['cv2'] = _cv2_falso()
        self.addCleanup(self._restaurar_cv2)
        self.mem = Path(tempfile.mkdtemp(prefix='abyss_ojo_verbos_'))

    def _restaurar_cv2(self):
        if self._cv2_previo is not None:
            sys.modules['cv2'] = self._cv2_previo
        else:
            sys.modules.pop('cv2', None)

    def test_mirar_con_camara_falsa_nunca_abierta_no_delega_en_nada(self):
        with mock.patch.object(lectura_visual, '_cli') as lv, \
             mock.patch.object(volumen, '_cli') as vo, \
             mock.patch.object(gestos, '_cli') as ge:
            salida = io.StringIO()
            with redirect_stdout(salida):
                codigo = ojo._cli(['mirar', 'salida.jpg', '5'], proj='/x', mem=str(self.mem))
        lv.assert_not_called()
        vo.assert_not_called()
        ge.assert_not_called()
        self.assertEqual(codigo, 2)
        self.assertIn('no disponible', salida.getvalue())

    def test_mirar_indice_no_numerico_es_error_de_uso(self):
        salida = io.StringIO()
        with redirect_stdout(salida):
            codigo = ojo._cli(['mirar', 'salida.jpg', 'no-es-un-numero'], proj='/x', mem=str(self.mem))
        self.assertEqual(codigo, 1)
        self.assertIn('índice de cámara', salida.getvalue())


if __name__ == '__main__':
    unittest.main()
