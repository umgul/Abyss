"""`gestos.py`: la regla del 1,7 para dedos extendidos, el
pellizco/escala normalizados por percentiles 10/90 de la sesión, el servidor HTTP local, y
el VOCABULARIO PROPIO (corrección del autor, 7-sep-2026): los dedos aíslan capas del
despiece, el pellizco es el deslizador de explosión, la pose de la palma orbita la cámara,
mano abierta y quieta captura PNG, dos manos escalan — nada del vocabulario del post citado
(un dedo una flor, dos un aguacate, tres una calavera).

`gestos.py` no llama a `rutas.resolver()` (vive/sirve mientras corre, como `taller.py`: sin
mem, sin proyecto de Claude Code) — se puede importar DIRECTAMENTE en el proceso de la
prueba. El caso "sin mediapipe" se prueba por subprocess, igual que `test_taller.py`
prueba "sin diffusers" — pero SIN depender del inventario real de la máquina que ejecute
la batería (MEDIDO el 7-sep-2026, tanda 5: `mediapipe` 1.0.1 puede estar instalado ahí y
la prueba que asumía su ausencia fallaba, y peor, dejaba `gestos.py` llegar a abrir la
cámara y levantar el servidor antes de reventar). Un `sitecustomize.py` propio antepuesto
a `PYTHONPATH` bloquea `import mediapipe` en el PROCESO HIJO sin tocar el Python real
(mismo método que `_entorno_con_modulos_bloqueados()` en
`test_imagen_dependencias_opcionales.py`), y otro fabrica un `mediapipe` que importa pero
sin `.solutions` (así mide el `mediapipe` 1.0.1 real en esta máquina) para probar que ESE
camino también corta antes de tocar hardware. El caso "con mediapipe" (para las funciones
que sí lo usan) inyecta un módulo `mediapipe` FALSO en `sys.modules` (con 21 puntos
sintéticos por mano, una o dos) y recarga `gestos` para que su `import mediapipe as mp` lo
recoja — se limpia siempre en `tearDown` para no dejar el módulo falso puesto para las
demás pruebas de la suite completa.
"""
import importlib
import json
import os
import sys
import tempfile
import textwrap
import threading
import time
import types
import unittest
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ayudas as ay

sys.path.insert(0, str(ay.PKG))
import gestos  # noqa: E402  (sin rutas.resolver(): seguro importarlo aquí, ver docstring del módulo)

_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # nunca por un proxy (es 127.0.0.1 de verdad)


def _get_json(url, tope=10):
    limite = time.time() + tope
    ultimo = None
    while time.time() < limite:
        try:
            with _OPENER.open(url, timeout=2) as r:
                return r.status, json.loads(r.read())
        except Exception as e:
            ultimo = e
            time.sleep(0.1)
    raise RuntimeError(f'sin respuesta de {url} tras {tope}s: {ultimo}')


# 21 puntos sintéticos (x, y, z) en el orden de MediaPipe Hands (0=muñeca; pulgar 1-4;
# índice 5-8; corazón 9-12; anular 13-16; meñique 17-20). Diseñados para que la regla del
# 1,7 dé un resultado EXACTO y conocido: pulgar/corazón/meñique extendidos (ratio 2,5/3,0/2,0,
# los tres > 1,7), índice/anular no (ratio 1,2/1,3, los dos < 1,7).
PUNTOS_21 = [(0.0, 0.0, 0.0)] * 21
PUNTOS_21[0] = (0.0, 0.0, 0.0)
PUNTOS_21[2] = (0.1, 0.0, 0.0); PUNTOS_21[4] = (0.25, 0.0, 0.0)      # pulgar: 0.25/0.1 = 2.5
PUNTOS_21[5] = (0.0, 0.1, 0.0); PUNTOS_21[8] = (0.0, 0.12, 0.0)      # índice: 0.12/0.1 = 1.2
PUNTOS_21[9] = (0.0, -0.1, 0.0); PUNTOS_21[12] = (0.0, -0.3, 0.0)    # corazón: 0.3/0.1 = 3.0
PUNTOS_21[13] = (-0.1, 0.0, 0.0); PUNTOS_21[16] = (-0.13, 0.0, 0.0)  # anular: 0.13/0.1 = 1.3
PUNTOS_21[17] = (0.05, -0.1, 0.0); PUNTOS_21[20] = (0.10, -0.2, 0.0)  # meñique: ratio 2.0
EXTENDIDOS_ESPERADOS = {'pulgar': True, 'indice': False, 'corazon': True, 'anular': False, 'menique': True}

# Los 5 dedos extendidos (para el gesto "mano abierta" de la captura por quietud): todas
# las puntas bien lejos de la muñeca, todos los ratios > 1,7 a propósito.
PUNTOS_MANO_ABIERTA = [(0.0, 0.0, 0.0)] * 21
PUNTOS_MANO_ABIERTA[2] = (0.1, 0.0, 0.0); PUNTOS_MANO_ABIERTA[4] = (0.25, 0.0, 0.0)
PUNTOS_MANO_ABIERTA[5] = (0.0, 0.1, 0.0); PUNTOS_MANO_ABIERTA[8] = (0.0, 0.25, 0.0)
PUNTOS_MANO_ABIERTA[9] = (0.0, -0.1, 0.0); PUNTOS_MANO_ABIERTA[12] = (0.0, -0.3, 0.0)
PUNTOS_MANO_ABIERTA[13] = (-0.1, 0.0, 0.0); PUNTOS_MANO_ABIERTA[16] = (-0.25, 0.0, 0.0)
PUNTOS_MANO_ABIERTA[17] = (0.05, -0.1, 0.0); PUNTOS_MANO_ABIERTA[20] = (0.10, -0.2, 0.0)


class ReglaDelUnoSiete(unittest.TestCase):
    def test_cuenta_exactamente_los_dedos_que_tocan(self):
        self.assertEqual(gestos.dedos_extendidos(PUNTOS_21), EXTENDIDOS_ESPERADOS)
        self.assertEqual(sum(EXTENDIDOS_ESPERADOS.values()), 3)

    def test_umbral_justo_en_1_7_no_cuenta_como_extendido(self):
        # ratio EXACTAMENTE 1.7 no es "> 1.7": no debe contar como extendido (límite estricto)
        puntos = list(PUNTOS_21)
        puntos[5] = (0.0, 1.0, 0.0); puntos[8] = (0.0, 1.7, 0.0)
        self.assertFalse(gestos.dedos_extendidos(puntos)['indice'])
        puntos[8] = (0.0, 1.7001, 0.0)
        self.assertTrue(gestos.dedos_extendidos(puntos)['indice'])

    def test_ratio_es_cambiable_por_vocabulario(self):
        # un ratio distinto (vocabulario propio) cambia qué cuenta como extendido, sin
        # tocar la geometría: pulgar a 2.5 dejaría de contar con un listón de 3.0
        self.assertTrue(gestos.dedos_extendidos(PUNTOS_21, ratio=1.7)['pulgar'])
        self.assertFalse(gestos.dedos_extendidos(PUNTOS_21, ratio=3.0)['pulgar'])

    def test_apertura_pellizco_bruta_es_la_distancia_pulgar_indice(self):
        import math
        px, py, _ = PUNTOS_21[4]
        ix, iy, _ = PUNTOS_21[8]
        esperado = math.hypot(px - ix, py - iy)
        self.assertAlmostEqual(gestos.apertura_pellizco_bruta(PUNTOS_21), esperado, places=9)


class PellizcoPorPercentiles(unittest.TestCase):
    def test_extremos_dan_0_y_1(self):
        n = gestos.NormalizadorPercentil(minimo=5)
        for v in range(0, 101):
            n.actualizar(v)
        self.assertEqual(n.normalizar(0), 0.0)
        self.assertEqual(n.normalizar(100), 1.0)
        self.assertAlmostEqual(n.normalizar(50), 0.5, delta=0.05)

    def test_se_recorta_fuera_del_rango_visto(self):
        n = gestos.NormalizadorPercentil(minimo=5)
        for v in range(0, 101):
            n.actualizar(v)
        self.assertEqual(n.normalizar(-50), 0.0)   # nunca negativo
        self.assertEqual(n.normalizar(500), 1.0)   # nunca por encima de 1

    def test_arranque_en_frio_da_0_5_no_finge_un_corte(self):
        n = gestos.NormalizadorPercentil(minimo=5)
        for v in (0.1, 0.2, 0.3):  # menos de 5 muestras
            n.actualizar(v)
        self.assertEqual(n.normalizar(0.1), 0.5)
        self.assertEqual(n.normalizar(999), 0.5)

    def test_minimo_por_defecto_es_30_como_pide_T4_5(self):
        self.assertEqual(gestos.MUESTRAS_PARA_VARA, 30)
        n = gestos.NormalizadorPercentil()
        self.assertEqual(n.minimo, 30)

    def test_descripcion_dice_sin_vara_todavia_con_n_hasta_llegar_al_minimo(self):
        n = gestos.NormalizadorPercentil(minimo=30)
        for i in range(29):
            n.actualizar(i)
            self.assertEqual(n.descripcion(), f'sin vara todavía (n={i + 1})')
        n.actualizar(29)
        self.assertIsNone(n.descripcion())  # ya hay 30: vara lista


class VocabularioPropio(unittest.TestCase):
    """El vocabulario se puede sustituir por fichero — `cargar_vocabulario()`
    mezcla un JSON propio SOLO en las claves que declare, sobre `VOCABULARIO_POR_DEFECTO`,
    y nunca copia el vocabulario del post (nada de "flor"/"aguacate"/"calavera" en ningún
    sitio de este módulo)."""

    def test_sin_fichero_da_los_valores_por_defecto(self):
        v = gestos.cargar_vocabulario(None)
        self.assertEqual(v, gestos.VOCABULARIO_POR_DEFECTO)
        self.assertEqual(v['ratio_dedo_extendido'], 1.7)
        self.assertEqual(v['muestras_para_vara'], 30)

    def test_fichero_propio_sustituye_solo_lo_que_declara(self):
        tmp = Path(tempfile.mkdtemp(prefix='abyss_vocab_')) / 'vocab.json'
        tmp.write_text(json.dumps({'ratio_dedo_extendido': 2.0, 'muestras_para_vara': 10}), encoding='utf-8')
        v = gestos.cargar_vocabulario(str(tmp))
        self.assertEqual(v['ratio_dedo_extendido'], 2.0)
        self.assertEqual(v['muestras_para_vara'], 10)
        # lo que el fichero no toca se queda con el valor por defecto
        self.assertEqual(v['segundos_captura_quieta'], gestos.VOCABULARIO_POR_DEFECTO['segundos_captura_quieta'])

    def test_fichero_inexistente_da_valueerror(self):
        with self.assertRaises(ValueError):
            gestos.cargar_vocabulario(str(Path(tempfile.mkdtemp()) / 'no_existe.json'))

    def test_fichero_que_no_es_un_objeto_json_da_valueerror(self):
        tmp = Path(tempfile.mkdtemp(prefix='abyss_vocab_')) / 'lista.json'
        tmp.write_text('[1, 2, 3]', encoding='utf-8')
        with self.assertRaises(ValueError):
            gestos.cargar_vocabulario(str(tmp))

    def test_ningun_rastro_del_vocabulario_ajeno_en_lo_que_se_sirve(self):
        # El docstring SÍ nombra "flor/aguacate/calavera" una vez, para declarar por qué
        # están prohibidas — lo que de verdad importa
        # es que esas palabras no aparezcan como claves/valores de lo que este módulo
        # produce: ni el vocabulario configurable ni los campos del estado servido.
        superficie = json.dumps(list(gestos.VOCABULARIO_POR_DEFECTO.keys())
                                 + list(gestos.ESTADO_INICIAL.keys()), ensure_ascii=False).lower()
        for palabra in ('flor', 'aguacate', 'calavera'):
            self.assertNotIn(palabra, superficie, f'"{palabra}" es del vocabulario ajeno, prohibido (ver corrección del autor)')

    def test_cli_reconoce_la_bandera_vocabulario(self):
        opts, error = gestos._parsear_argv(['--vocabulario', 'mem/gestos_vocabulario.json'])
        self.assertIsNone(error)
        self.assertEqual(opts['vocabulario'], 'mem/gestos_vocabulario.json')

    def test_cli_sin_vocabulario_lo_deja_en_none(self):
        opts, error = gestos._parsear_argv(['--puerto', '9000'])
        self.assertIsNone(error)
        self.assertIsNone(opts['vocabulario'])


class CapasAisladasPorDedos(unittest.TestCase):
    """Número de dedos = qué capa del despiece se aísla — 0 todas, 1 la primera,
    2 las dos primeras… NUNCA el vocabulario del post (esto maneja capas de una escena
    real de `render3d.py`, no invoca figuritas)."""

    def test_cero_dedos_da_todas_las_capas(self):
        self.assertEqual(gestos.capas_visibles_por_dedos(['a', 'b', 'c'], 0), ['a', 'b', 'c'])

    def test_un_dedo_da_solo_la_primera(self):
        self.assertEqual(gestos.capas_visibles_por_dedos(['a', 'b', 'c'], 1), ['a'])

    def test_dos_dedos_da_las_dos_primeras(self):
        self.assertEqual(gestos.capas_visibles_por_dedos(['a', 'b', 'c'], 2), ['a', 'b'])

    def test_mas_dedos_que_capas_satura_al_total_sin_inventar(self):
        self.assertEqual(gestos.capas_visibles_por_dedos(['a', 'b'], 5), ['a', 'b'])

    def test_sin_escena_cargada_da_none(self):
        self.assertIsNone(gestos.capas_visibles_por_dedos(None, 2))


class OrbitaDeLaPalma(unittest.TestCase):
    """Pose de la palma = órbita de la cámara — mismo dato, vocabulario propio."""

    def test_alias_giro_e_inclinacion_de_yaw_y_pitch(self):
        pose = {'roll': 1.0, 'pitch': 12.5, 'yaw': -30.0}
        self.assertEqual(gestos.orbita_de_pose(pose), {'giro': -30.0, 'inclinacion': 12.5})

    def test_sin_pose_da_none(self):
        self.assertIsNone(gestos.orbita_de_pose(None))


class CapturaPorQuietud(unittest.TestCase):
    """Mano abierta y quieta un segundo = capturar PNG."""

    def test_quieta_un_segundo_dispara_captura_una_sola_vez(self):
        d = gestos.DetectorCapturaPorQuietud(segundos=1.0, umbral_movimiento=0.04)
        pos = (0.5, 0.5)
        self.assertIsNone(d.actualizar(5, pos, t=0.0))
        self.assertIsNone(d.actualizar(5, pos, t=0.5))
        self.assertEqual(d.actualizar(5, pos, t=1.0), 'captura')
        # sigue abierta y quieta: no se repite en el fotograma siguiente
        self.assertIsNone(d.actualizar(5, pos, t=1.2))

    def test_menos_de_5_dedos_nunca_dispara_y_reinicia_la_cuenta(self):
        d = gestos.DetectorCapturaPorQuietud(segundos=1.0, umbral_movimiento=0.04)
        pos = (0.5, 0.5)
        self.assertIsNone(d.actualizar(4, pos, t=0.0))
        self.assertIsNone(d.actualizar(4, pos, t=2.0))
        self.assertIsNone(d.actualizar(5, pos, t=2.1))  # recién llega a 5: vuelve a contar desde aquí
        self.assertIsNone(d.actualizar(5, pos, t=2.5))

    def test_moverse_reinicia_la_cuenta_de_quietud(self):
        d = gestos.DetectorCapturaPorQuietud(segundos=1.0, umbral_movimiento=0.04)
        self.assertIsNone(d.actualizar(5, (0.5, 0.5), t=0.0))
        self.assertIsNone(d.actualizar(5, (0.5, 0.9), t=0.9))  # se movió: reinicia
        self.assertIsNone(d.actualizar(5, (0.5, 0.9), t=1.5))  # solo 0.6s quieta desde el movimiento
        self.assertEqual(d.actualizar(5, (0.5, 0.9), t=1.95), 'captura')  # ya 1.05s quieta


class ServidorSoloEnLoopback(unittest.TestCase):
    """Tercera prueba declarada: "el servidor local responde JSON y no
    escucha fuera de 127.0.0.1". Se llama directamente a `construir_servidor()` (no
    necesita `mediapipe`/`cv2`, `estado`/`cerrojo` son los únicos que usan los manejadores)."""

    def test_liga_a_127_0_0_1_y_responde_estado_y_health(self):
        estado = dict(gestos.ESTADO_INICIAL)
        cerrojo = threading.Lock()
        srv = gestos.construir_servidor(0, estado, cerrojo)
        try:
            self.assertEqual(srv.server_address[0], '127.0.0.1')
            hilo = threading.Thread(target=srv.serve_forever, daemon=True)
            hilo.start()
            puerto = srv.server_address[1]

            cod, cuerpo = _get_json(f'http://127.0.0.1:{puerto}/estado')
            self.assertEqual(cod, 200)
            self.assertEqual(cuerpo, gestos.ESTADO_INICIAL)  # nada se muestra hasta que hay un gesto completo

            cod, salud = _get_json(f'http://127.0.0.1:{puerto}/health')
            self.assertEqual(cod, 200)
            self.assertTrue(salud['ok'])

            with self.assertRaises(urllib.error.HTTPError) as ctx:
                _OPENER.open(f'http://127.0.0.1:{puerto}/no-existe', timeout=5)
            self.assertEqual(ctx.exception.code, 404)
        finally:
            srv.shutdown()
            srv.server_close()

    def test_estado_refleja_lo_que_escribe_el_bucle_bajo_el_cerrojo(self):
        estado = dict(gestos.ESTADO_INICIAL)
        cerrojo = threading.Lock()
        srv = gestos.construir_servidor(0, estado, cerrojo)
        try:
            hilo = threading.Thread(target=srv.serve_forever, daemon=True)
            hilo.start()
            puerto = srv.server_address[1]
            with cerrojo:
                estado.update({'dedos_extendidos': 3, 'pellizco': 0.42, 'capas_visibles': ['a', 'b']})
            cod, cuerpo = _get_json(f'http://127.0.0.1:{puerto}/estado')
            self.assertEqual(cod, 200)
            self.assertEqual(cuerpo['dedos_extendidos'], 3)
            self.assertEqual(cuerpo['pellizco'], 0.42)
            self.assertEqual(cuerpo['capas_visibles'], ['a', 'b'])
        finally:
            srv.shutdown()
            srv.server_close()


def _entorno_sin_mediapipe(env_base):
    """`sitecustomize.py` propio antepuesto a `PYTHONPATH` que bloquea `import mediapipe`
    SIEMPRE en el proceso hijo, sin importar si esta máquina lo tiene instalado o no
    (mismo método que `_entorno_con_modulos_bloqueados()` en
    `test_imagen_dependencias_opcionales.py` — el Python real no se toca)."""
    bloqueo_dir = Path(tempfile.mkdtemp(prefix='abyss_sin_mediapipe_'))
    (bloqueo_dir / 'sitecustomize.py').write_text(textwrap.dedent('''
        import sys
        import importlib.abc

        class _Bloqueador(importlib.abc.MetaPathFinder):
            def find_spec(self, name, path, target=None):
                if name.split(".")[0] == "mediapipe":
                    raise ModuleNotFoundError(
                        "mediapipe bloqueado por la prueba (sitecustomize)", name="mediapipe")
                return None

        sys.meta_path.insert(0, _Bloqueador())
    '''), encoding='utf-8')
    env = dict(env_base)
    env['PYTHONPATH'] = str(bloqueo_dir) + os.pathsep + env.get('PYTHONPATH', '')
    return env


def _entorno_con_mediapipe_roto(env_base):
    """`sitecustomize.py` propio que deja en `sys.modules` un `mediapipe` que IMPORTA sin
    error pero sin atributo `solutions` — así mide esta tanda (7-sep-2026) el `mediapipe`
    1.0.1 real instalado en la máquina (`AttributeError: module 'mediapipe' has no
    attribute 'solutions'` dentro de `crear_detector()`). El Python real no se toca: solo
    el proceso hijo ve este módulo falso."""
    bloqueo_dir = Path(tempfile.mkdtemp(prefix='abyss_mediapipe_roto_'))
    (bloqueo_dir / 'sitecustomize.py').write_text(textwrap.dedent('''
        import sys
        import types

        _falso = types.ModuleType("mediapipe")
        # A propósito SIN "solutions": así mide esta máquina el mediapipe 1.0.1 real.
        sys.modules["mediapipe"] = _falso
    '''), encoding='utf-8')
    env = dict(env_base)
    env['PYTHONPATH'] = str(bloqueo_dir) + os.pathsep + env.get('PYTHONPATH', '')
    return env


class GestosSinMediapipeCLI(unittest.TestCase):
    def test_sale_con_2_y_el_mensaje_nombra_mediapipe(self):
        env = _entorno_sin_mediapipe(dict(os.environ))
        r = ay.ejecutar(ay.script('gestos.py'), ['--puerto', '0'], env)
        self.assertEqual(r.returncode, 2, f'stdout={r.stdout!r} stderr={r.stderr!r}')
        self.assertIn('mediapipe', r.stdout)
        self.assertIn('pip install', r.stdout)
        self.assertNotIn('Traceback', r.stdout)
        self.assertNotIn('Traceback', r.stderr)
        # falsador: sin mediapipe, la CLI corta ANTES de tocar cámara o servidor (regla
        # dura de esta tanda: nada de encender webcam/levantar HTTP sin la dependencia).
        self.assertNotIn('escuchando en http', r.stdout)
        self.assertNotIn('calibrando', r.stdout)

    def test_argumento_desconocido_sale_con_1_sin_tocar_la_dependencia(self):
        r = ay.ejecutar(ay.script('gestos.py'), ['--no-existe', 'x'], dict(os.environ))
        self.assertEqual(r.returncode, 1)


class GestosMediapipeRotoCLI(unittest.TestCase):
    """Falsador del hallazgo de la tanda 5 (7-sep-2026): `mediapipe` 1.0.1 en la máquina
    real IMPORTA pero no trae `.solutions`. Antes del arreglo, `main()` solo comprobaba
    `mp is None` (verdadero solo si el import falla) y seguía adelante hasta abrir la
    cámara y levantar el servidor con un mediapipe inservible, reventando recién entonces
    en `crear_detector()` — justo lo que la regla dura de esta tanda prohíbe. Aquí se
    inyecta ESE mediapipe roto por subprocess y se comprueba que la CLI corta antes."""

    def test_sale_con_2_sin_abrir_camara_ni_servidor(self):
        env = _entorno_con_mediapipe_roto(dict(os.environ))
        r = ay.ejecutar(ay.script('gestos.py'), ['--puerto', '0'], env)
        self.assertEqual(r.returncode, 2, f'stdout={r.stdout!r} stderr={r.stderr!r}')
        self.assertIn('mediapipe', r.stdout)
        self.assertNotIn('Traceback', r.stdout)
        self.assertNotIn('Traceback', r.stderr)
        self.assertNotIn('escuchando en http', r.stdout)
        self.assertNotIn('calibrando', r.stdout)


def _grupos_de(datos):
    grupos = []
    for p in datos.get('piezas') or []:
        g = p.get('grupo') or p.get('nombre')
        if g not in grupos:
            grupos.append(g)
    return grupos


class LecturaDeEscena(unittest.TestCase):
    def test_grupos_de_una_escena_json_normal(self):
        ruta = ay.RAIZ / 'pruebas' / 'datos' / 'escena_prueba.json'
        grupos = gestos._grupos_de_escena(str(ruta))
        self.assertEqual(grupos, ['cuerpo', 'remate'])  # 2 piezas en "cuerpo", 1 en "remate" (ver el fichero)


# ───────────────────────────────── módulo `mediapipe` falso (21 puntos sintéticos, 1 o 2 manos) ─────────────────────────────────

class _PuntoFalso:
    def __init__(self, x, y, z=0.0):
        self.x, self.y, self.z = x, y, z


class _ManoFalsa:
    def __init__(self, landmark):
        self.landmark = landmark


class _ResultadoFalso:
    def __init__(self, manos):
        self.multi_hand_landmarks = manos


def _fabricar_hands_falso(lista_de_manos):
    """`lista_de_manos`: lista de manos, cada una una lista de puntos (x,y[,z])."""
    def _mano(puntos):
        return _ManoFalsa([_PuntoFalso(*p) for p in puntos])

    class _HandsFalso:
        def __init__(self, **kw):
            pass

        def process(self, _frame_rgb):
            return _ResultadoFalso([_mano(p) for p in lista_de_manos])

        def close(self):
            pass

    return _HandsFalso


def _inyectar_mediapipe_falso(lista_de_manos):
    hands_falso = _fabricar_hands_falso(lista_de_manos)
    fake_mp = types.ModuleType('mediapipe')
    fake_sol = types.ModuleType('mediapipe.solutions')
    fake_hands_mod = types.ModuleType('mediapipe.solutions.hands')
    fake_hands_mod.Hands = hands_falso
    fake_sol.hands = fake_hands_mod
    fake_mp.solutions = fake_sol
    sys.modules['mediapipe'] = fake_mp
    sys.modules['mediapipe.solutions'] = fake_sol
    sys.modules['mediapipe.solutions.hands'] = fake_hands_mod


def _quitar_mediapipe_falso():
    for nombre in ('mediapipe.solutions.hands', 'mediapipe.solutions', 'mediapipe'):
        sys.modules.pop(nombre, None)


class ModuloFalsoIntegracion(unittest.TestCase):
    """Segunda prueba declarada, literal: "un módulo falso inyectado en
    sys.modules con 21 puntos sintéticos" ejercitando la regla del 1,7 y el pellizco por
    percentiles 10/90 a través del camino REAL (`crear_detector().process(...)` ->
    `manos_de_resultado()` -> `dedos_extendidos()`/`apertura_pellizco_bruta()`), no solo
    las funciones puras sueltas (esas están en `ReglaDelUnoSiete`/`PellizcoPorPercentiles`,
    sin necesitar ningún mediapipe, falso o real)."""

    def tearDown(self):
        # Nunca dejar el `mediapipe` falso puesto para el resto de la suite: se quita y se
        # recarga `gestos` para que vuelva a ver el `mediapipe` real (aquí: ausente).
        _quitar_mediapipe_falso()
        importlib.reload(gestos)

    def test_pipeline_completo_regla_1_7_y_pellizco_0_y_1(self):
        _inyectar_mediapipe_falso([PUNTOS_21])
        importlib.reload(gestos)
        self.assertIsNotNone(gestos.mp, 'el mediapipe falso debe quedar activo tras recargar')

        detector = gestos.crear_detector()
        resultado = detector.process(None)  # el frame no importa: el falso ignora su contenido
        manos = gestos.manos_de_resultado(resultado)
        self.assertEqual(len(manos), 1)
        puntos = manos[0]
        self.assertEqual(len(puntos), 21)

        dedos = gestos.dedos_extendidos(puntos)
        self.assertEqual(dedos, EXTENDIDOS_ESPERADOS)

        normalizador = gestos.NormalizadorPercentil(minimo=5)
        # Una sesión sintética de aperturas de pellizco alrededor de la que da PUNTOS_21,
        # para tener con qué calcular percentiles 10/90 de verdad.
        bruto = gestos.apertura_pellizco_bruta(puntos)
        for v in [bruto * f for f in (0.2, 0.4, 0.6, 0.8, 1.0, 1.2, 1.4, 1.6, 1.8, 2.0)]:
            normalizador.actualizar(v)
        self.assertEqual(normalizador.normalizar(bruto * 0.2), 0.0)   # el mínimo visto
        self.assertEqual(normalizador.normalizar(bruto * 2.0), 1.0)   # el máximo visto

        info = gestos.procesar_puntos(puntos, 640, 480, normalizador)
        self.assertEqual(info['dedos'], EXTENDIDOS_ESPERADOS)
        self.assertEqual(info['dedos_extendidos'], 3)
        self.assertIsInstance(info['pellizco'], float)
        self.assertEqual(info['explosion'], info['pellizco'])  # alias, vocabulario propio

    def test_puntos_de_resultado_sin_mano_da_none(self):
        _inyectar_mediapipe_falso([])
        importlib.reload(gestos)
        self.assertIsNone(gestos.puntos_de_resultado(_ResultadoFalso([])))

    def test_puntos_de_resultado_incompleto_da_none_no_extrapola(self):
        _inyectar_mediapipe_falso([PUNTOS_21])
        importlib.reload(gestos)
        mano_incompleta = _ManoFalsa([_PuntoFalso(*p) for p in PUNTOS_21[:15]])  # solo 15, no 21
        resultado = _ResultadoFalso([mano_incompleta])
        self.assertIsNone(gestos.puntos_de_resultado(resultado))

    def test_dos_manos_dan_escala_por_distancia_entre_munecas(self):
        mano_b = [(x + 1.0, y, z) for (x, y, z) in PUNTOS_21]  # misma forma, desplazada en X
        _inyectar_mediapipe_falso([PUNTOS_21, mano_b])
        importlib.reload(gestos)
        detector = gestos.crear_detector(max_manos=2)
        resultado = detector.process(None)
        manos = gestos.manos_de_resultado(resultado)
        self.assertEqual(len(manos), 2)

        dist = gestos.distancia_entre_manos(manos)
        self.assertAlmostEqual(dist, 1.0, places=6)  # muñecas en (0,0,0) y (1,0,0)

        norm_pellizco = gestos.NormalizadorPercentil(minimo=100)  # nunca llega: sin vara a propósito
        norm_escala = gestos.NormalizadorPercentil(minimo=3)
        for d in (0.5, 1.0, 1.5):
            norm_escala.actualizar(d)
        info = gestos.procesar_fotograma(manos, 640, 480, norm_pellizco, norm_escala)
        self.assertEqual(info['manos'], 2)
        self.assertIsInstance(info['escala'], float)
        self.assertIn('sin vara todavía', info['vara_pellizco'])  # con minimo=100 nunca hay vara

    def test_una_mano_da_escala_none_y_vara_escala_none(self):
        _inyectar_mediapipe_falso([PUNTOS_21])
        importlib.reload(gestos)
        detector = gestos.crear_detector(max_manos=2)
        resultado = detector.process(None)
        manos = gestos.manos_de_resultado(resultado)
        self.assertEqual(len(manos), 1)
        info = gestos.procesar_fotograma(manos, 640, 480, gestos.NormalizadorPercentil(), gestos.NormalizadorPercentil())
        self.assertEqual(info['manos'], 1)
        self.assertIsNone(info['escala'])
        self.assertIsNone(info['vara_escala'])


class GestoAMediasNoCambiaLaEscena(unittest.TestCase):
    """Cuarta prueba declarada: "un gesto a medias NO cambia la escena".
    `procesar_fotograma([], ...)` (sin ninguna mano completa) da `None`, y el bucle de
    `main()` deja entonces el `estado` servido TAL CUAL — se comprueba aquí simulando ese
    contrato: aplicar un `None` nunca debe machacar el último estado bueno."""

    def test_sin_manos_completas_da_none_y_el_llamador_no_toca_el_estado(self):
        norm_p, norm_e = gestos.NormalizadorPercentil(), gestos.NormalizadorPercentil()
        self.assertIsNone(gestos.procesar_fotograma([], 640, 480, norm_p, norm_e))

    def test_estado_servido_no_cambia_entre_un_gesto_completo_y_uno_a_medias(self):
        estado = dict(gestos.ESTADO_INICIAL)
        estado['grupos'] = ['capa_0', 'capa_1', 'fondo']
        cerrojo = threading.Lock()
        norm_p, norm_e = gestos.NormalizadorPercentil(), gestos.NormalizadorPercentil()

        # fotograma 1: gesto COMPLETO (2 dedos extendidos con estos puntos concretos)
        info1 = gestos.procesar_fotograma([PUNTOS_21], 640, 480, norm_p, norm_e)
        self.assertIsNotNone(info1)
        with cerrojo:
            estado.update(info1)
            estado['capas_visibles'] = gestos.capas_visibles_por_dedos(estado['grupos'], info1['dedos_extendidos'])
        instantanea_buena = dict(estado)

        # fotograma 2: gesto A MEDIAS (ninguna mano con los 21 puntos) — el bucle real de
        # `main()` hace `continue` en vez de llamar a `estado.update(...)`, aquí se
        # comprueba justo esa rama: `procesar_fotograma([])` da `None` y NADA se actualiza.
        info2 = gestos.procesar_fotograma([], 640, 480, norm_p, norm_e)
        self.assertIsNone(info2)
        if info2 is not None:  # nunca se ejecuta; deja explícito el contrato que main() respeta
            with cerrojo:
                estado.update(info2)

        self.assertEqual(estado, instantanea_buena, 'un gesto a medias no debe cambiar el estado servido')


if __name__ == '__main__':
    unittest.main()
