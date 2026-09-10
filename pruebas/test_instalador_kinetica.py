# -*- coding: utf-8 -*-
"""Tarea C (visor cinético, T6): `instalar.py` sabe bajar el vendor de MediaPipe
Tasks Vision (JS + wasm + el modelo de manos) que necesita
`abyss/plantillas/kinetica.html` — sin eso, NO va en el repositorio de git
(pesa ~27 MB) y el visor no puede correr.

Regla dura 5 del encargo (NADA de esto baja algo real): cada prueba que
ejercita `descargar_vendor_mp()` monkeypatchea `instalar._descargar_uno` (el
ÚNICO punto de la función que toca la red de verdad) — nunca sale a la red,
nunca escribe un fichero de más de unos bytes de mentira. Las pruebas que
ejercitan `_descargar_uno` en sí mismo monkeypatchean, más abajo,
`urllib.request.urlopen` con una respuesta en memoria (`io.BytesIO`) — jamás
un socket real.

Igual que `test_instalador_dependencias.py`: se importa `instalar.py`
DIRECTAMENTE por ruta de fichero, con su PROPIO nombre de módulo (para no
chocar con otro test que también cargue `instalar.py` en el mismo proceso de
`unittest`)."""
import sys
import os
import io
import socket
import tempfile
import inspect
import shutil
import urllib.error
import importlib.util
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import unittest
import ayudas as ay


def _cargar_instalador():
    ruta = ay.RAIZ / 'instalar.py'
    spec = importlib.util.spec_from_file_location('abyss_instalador_bajo_prueba_kinetica', str(ruta))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# Las seis URL que dio el encargo (medidas: se bajaron y funcionan) — si
# `VENDOR_MP` cambiara alguna sin querer, esta prueba lo caza. También son,
# literalmente, la respuesta a "qué comando exacto hay que dar para bajarlas"
# que pedía el encargo para el mensaje de error de otro módulo.
URLS_MEDIDAS = (
    'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/vision_bundle.mjs',
    'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm/vision_wasm_internal.js',
    'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm/vision_wasm_internal.wasm',
    'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm/vision_wasm_nosimd_internal.js',
    'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm/vision_wasm_nosimd_internal.wasm',
    'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/'
    'hand_landmarker.task',
)


# ---------------------------------------------------------------------------------
# El registro VENDOR_MP: los datos que la plantilla kinetica.html necesita tener
# en abyss/vendor/mp/ para poder servirse (ver su docstring: vision_bundle.mjs,
# mp/wasm/*, hand_landmarker.task).
# ---------------------------------------------------------------------------------
class RegistroVendorMP(unittest.TestCase):
    def test_las_seis_url_son_exactamente_las_medidas(self):
        inst = _cargar_instalador()
        urls = tuple(v['url'] for v in inst.VENDOR_MP)
        self.assertEqual(urls, URLS_MEDIDAS)

    def test_comando_descargar_manos_es_el_que_otro_modulo_necesita_citar(self):
        inst = _cargar_instalador()
        self.assertEqual(inst.COMANDO_DESCARGAR_MANOS, 'python instalar.py --manos')

    def test_cada_entrada_declara_los_campos_que_usa_la_tabla_y_la_descarga(self):
        inst = _cargar_instalador()
        self.assertEqual(len(inst.VENDOR_MP), 6)
        for v in inst.VENDOR_MP:
            for campo in ('nombre', 'destino', 'url', 'tam_txt', 'tam_mb'):
                self.assertIn(campo, v, f'falta "{campo}" en {v}')
            self.assertTrue(str(v['nombre']).strip())
            self.assertTrue(str(v['tam_txt']).strip())
            self.assertGreater(v['tam_mb'], 0)
            self.assertTrue(v['url'].startswith('https://'), 'nunca http:// sin cifrar')

    def test_destinos_son_relativos_con_barra_y_unicos(self):
        """`destino` es siempre "/" (nunca `os.sep` a pelo, para que
        `_ruta_vendor_mp` valga en Windows y POSIX por igual) y nunca empieza
        por "/" ni contiene "..": nunca debe poder escapar de
        abyss/vendor/mp/."""
        inst = _cargar_instalador()
        destinos = [v['destino'] for v in inst.VENDOR_MP]
        self.assertEqual(len(destinos), len(set(destinos)), 'destinos repetidos')
        for d in destinos:
            self.assertNotIn('\\', d)
            self.assertFalse(d.startswith('/'))
            self.assertNotIn('..', d)

    def test_wasm_va_en_su_propia_subcarpeta_como_espera_kinetica_html(self):
        """`kinetica.html` pide `FilesetResolver.forVisionTasks('./mp/wasm')`:
        los cuatro ficheros wasm/js del bundle deben vivir bajo "wasm/"."""
        inst = _cargar_instalador()
        por_nombre = {v['nombre']: v['destino'] for v in inst.VENDOR_MP}
        for nombre in ('wasm/vision_wasm_internal.js', 'wasm/vision_wasm_internal.wasm',
                       'wasm/vision_wasm_nosimd_internal.js', 'wasm/vision_wasm_nosimd_internal.wasm'):
            self.assertTrue(por_nombre[nombre].startswith('wasm/'), nombre)
        self.assertEqual(por_nombre['vision_bundle.mjs'], 'vision_bundle.mjs')
        self.assertEqual(por_nombre['hand_landmarker.task'], 'hand_landmarker.task')

    def test_total_aproximado_es_unos_27_mb_sin_afinar_mas(self):
        """El encargo mide "unos 27 MB" — ni más fino. Sumar los seis tamaños
        aproximados y redondear al entero no inventa una cifra más precisa que
        la medida; solo la agrega."""
        inst = _cargar_instalador()
        total = sum(v['tam_mb'] for v in inst.VENDOR_MP)
        self.assertEqual(round(total), 27)

    def test_tamanos_no_mas_finos_que_los_medidos(self):
        """El encargo dio 137 KB, 210 KB, 9,4 MB, 210 KB, 9,3 MB y 7,8 MB — como
        mucho un decimal en los MB, sin más cifras inventadas."""
        inst = _cargar_instalador()
        for v in inst.VENDOR_MP:
            if v['tam_txt'].endswith('MB'):
                numero = v['tam_txt'].lstrip('~').rstrip(' MB')
                self.assertLessEqual(len(numero.split('.')[-1]), 1, v['tam_txt'])


# ---------------------------------------------------------------------------------
# `_ruta_vendor_mp` / `_estado_vendor_mp`: comprobación REAL contra el disco
# (nunca una lista fija), igual que `_import_disponible` con los paquetes de pip.
# ---------------------------------------------------------------------------------
class RutaYEstadoVendorMP(unittest.TestCase):
    def test_ruta_vendor_mp_usa_os_path_join_no_concatenacion(self):
        inst = _cargar_instalador()
        esperado = os.path.join(inst.PKG, 'vendor', 'mp', 'wasm', 'vision_wasm_internal.js')
        self.assertEqual(inst._ruta_vendor_mp('wasm/vision_wasm_internal.js'), esperado)

    def test_estado_dice_falta_si_no_esta_el_fichero(self):
        inst = _cargar_instalador()
        tmp = tempfile.mkdtemp(prefix='abyss_vendor_mp_')
        try:
            with mock.patch.object(inst, 'PKG', tmp):
                estado = inst._estado_vendor_mp()
                self.assertTrue(all(v['falta'] for v in estado), 'carpeta vacía: todo debe faltar')
                self.assertTrue(all(not v['presente'] for v in estado))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_estado_dice_ok_solo_para_lo_que_de_verdad_esta_escrito(self):
        inst = _cargar_instalador()
        tmp = tempfile.mkdtemp(prefix='abyss_vendor_mp_')
        try:
            with mock.patch.object(inst, 'PKG', tmp):
                ruta = inst._ruta_vendor_mp('vision_bundle.mjs')
                os.makedirs(os.path.dirname(ruta), exist_ok=True)
                with open(ruta, 'w', encoding='utf-8') as fh:
                    fh.write('// contenido de mentira, para la prueba')
                estado = {v['nombre']: v for v in inst._estado_vendor_mp()}
                self.assertFalse(estado['vision_bundle.mjs']['falta'])
                self.assertTrue(estado['hand_landmarker.task']['falta'])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------------
# `--dependencias` (`_tabla_dependencias`/`_tabla_vendor_mp`): dice si están o
# faltan, en los dos idiomas, y NUNCA toca la red por su cuenta.
# ---------------------------------------------------------------------------------
class TablaDependenciasDiceVendorMP(unittest.TestCase):
    def test_dependencias_nunca_descarga_nada_por_su_cuenta(self):
        """Mirar la tabla no debe bajar ni un byte: si `_descargar_uno` se
        llamara desde aquí, esta prueba lo cazaría."""
        inst = _cargar_instalador()
        with mock.patch.object(inst, '_descargar_uno', side_effect=AssertionError(
                '--dependencias no debe tocar la red')):
            texto = inst._tabla_dependencias('es')
        self.assertIn('MediaPipe Tasks Vision', texto)

    def test_dice_falta_en_es_y_missing_en_en(self):
        inst = _cargar_instalador()
        tmp = tempfile.mkdtemp(prefix='abyss_vendor_mp_')
        try:
            with mock.patch.object(inst, 'PKG', tmp):
                texto_es = inst._tabla_vendor_mp('es')
                texto_en = inst._tabla_vendor_mp('en')
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        self.assertIn('FALTA', texto_es)
        self.assertNotIn('MISSING', texto_es)
        self.assertIn('MISSING', texto_en)
        self.assertNotIn('FALTA', texto_en)

    def test_dice_ok_cuando_los_seis_ficheros_estan(self):
        inst = _cargar_instalador()
        tmp = tempfile.mkdtemp(prefix='abyss_vendor_mp_')
        try:
            with mock.patch.object(inst, 'PKG', tmp):
                for v in inst.VENDOR_MP:
                    ruta = inst._ruta_vendor_mp(v['destino'])
                    os.makedirs(os.path.dirname(ruta), exist_ok=True)
                    open(ruta, 'wb').write(b'x')
                texto = inst._tabla_vendor_mp('es')
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        self.assertNotIn('FALTA', texto)

    def test_menciona_la_licencia_apache_y_el_comando_de_descarga(self):
        inst = _cargar_instalador()
        texto = inst._tabla_vendor_mp('es')
        self.assertIn('Apache License 2.0', texto)
        self.assertIn(inst.COMANDO_DESCARGAR_MANOS, texto)
        self.assertIn('LICENSE-mediapipe.txt', texto)

    def test_no_se_instalan_con_instalar_dependencias(self):
        """No son paquetes de pip: no deben figurar en `DEPENDENCIAS`, ni
        `_paquetes_a_instalar` debe intentar meterlos con pip."""
        inst = _cargar_instalador()
        nombres_pip = {e['pip_nombre'] for entradas in inst.DEPENDENCIAS.values() for e in entradas}
        self.assertNotIn('@mediapipe/tasks-vision', nombres_pip)
        for v in inst.VENDOR_MP:
            self.assertNotIn(v['nombre'], nombres_pip)


# ---------------------------------------------------------------------------------
# `--manos` es una bandera SIN valor, reconocida por el validador de argv.
# ---------------------------------------------------------------------------------
class BanderaManosReconocida(unittest.TestCase):
    def test_manos_esta_en_flags_sin_valor(self):
        inst = _cargar_instalador()
        self.assertIn('--manos', inst._FLAGS_SIN_VALOR)

    def test_argumento_no_reconocido_acepta_manos_sola_y_con_idioma(self):
        inst = _cargar_instalador()
        self.assertIsNone(inst._argumento_no_reconocido(['--manos']))
        self.assertIsNone(inst._argumento_no_reconocido(['--manos', '--idioma', 'en']))

    def test_uso_menciona_manos_en_los_dos_idiomas(self):
        inst = _cargar_instalador()
        self.assertIn('--manos', inst._uso('es'))
        self.assertIn('--manos', inst._uso('en'))

    def test_manos_nunca_aparece_en_hooks_json(self):
        """Mismo criterio que `--dependencias`/`--instalar-dependencias`
        (`test_instalador_dependencias.py`): esto es un verbo de la CLI a
        petición explícita, nunca algo que un gancho dispare solo."""
        texto = (ay.RAIZ / 'hooks' / 'hooks.json').read_text(encoding='utf-8')
        self.assertNotIn('--manos', texto)

    def test_descargar_vendor_mp_nunca_se_llama_desde_instalar_o_desinstalar(self):
        inst = _cargar_instalador()
        for nombre_fn in ('instalar', 'desinstalar'):
            fuente = inspect.getsource(getattr(inst, nombre_fn))
            self.assertNotIn('descargar_vendor_mp(', fuente, f'{nombre_fn}() no debe llamar a descargar_vendor_mp')


# ---------------------------------------------------------------------------------
# `descargar_vendor_mp()` con un descargador SIMULADO (regla dura 5: nunca baja
# nada real). Se monkeypatchea `_descargar_uno` — el único punto de la función
# que toca la red de verdad.
# ---------------------------------------------------------------------------------
class DescargarVendorMPConDescargadorSimulado(unittest.TestCase):
    def _con_pkg_temporal(self):
        tmp = tempfile.mkdtemp(prefix='abyss_vendor_mp_')
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        return tmp

    def test_avisa_antes_de_bajar_nada_de_donde_y_cuanto_ocupa(self):
        """T6: "se ensena que se va a bajar, de donde y cuanto ocupa antes de
        empezar" — las URL y tamaños deben estar YA en `mensajes` antes de que
        se llame a `_descargar_uno` la primera vez."""
        inst = _cargar_instalador()
        tmp = self._con_pkg_temporal()

        def falso(url, destino_abs, timeout=30):
            os.makedirs(os.path.dirname(destino_abs), exist_ok=True)
            open(destino_abs, 'wb').write(b'x')
            return 1

        with mock.patch.object(inst, 'PKG', tmp), \
             mock.patch.object(inst, '_escribir_licencia_mediapipe'), \
             mock.patch.object(inst, '_descargar_uno', side_effect=falso):
            # `mensajes` es la lista COMPLETA que ve el usuario, en orden: se
            # comprueba que las 6 URL/tamaños ya están ahí ANTES de la primera
            # línea "descargado" (nunca se anuncia después de empezar).
            mensajes, ok = inst.descargar_vendor_mp(idioma='es')
        self.assertTrue(ok)
        primera_linea_descargado = next(i for i, m in enumerate(mensajes) if 'descargado' in m)
        for v in inst.VENDOR_MP:
            indice_url = next(i for i, m in enumerate(mensajes) if v['url'] in m)
            self.assertLess(indice_url, primera_linea_descargado,
                             f'{v["url"]} debe anunciarse antes de la primera descarga')
            self.assertIn(v['tam_txt'], mensajes[indice_url])

    def test_si_no_falta_nada_no_llama_al_descargador(self):
        inst = _cargar_instalador()
        tmp = self._con_pkg_temporal()
        with mock.patch.object(inst, 'PKG', tmp):
            for v in inst.VENDOR_MP:
                ruta = inst._ruta_vendor_mp(v['destino'])
                os.makedirs(os.path.dirname(ruta), exist_ok=True)
                open(ruta, 'wb').write(b'x')
            with mock.patch.object(inst, '_descargar_uno') as descargar:
                mensajes, ok = inst.descargar_vendor_mp(idioma='es')
            descargar.assert_not_called()
        self.assertTrue(ok)
        self.assertTrue(any('nada que descargar' in m for m in mensajes))

    def test_solo_baja_lo_que_falta_salta_lo_que_ya_esta(self):
        inst = _cargar_instalador()
        tmp = self._con_pkg_temporal()
        with mock.patch.object(inst, 'PKG', tmp):
            ya_esta = inst.VENDOR_MP[0]
            ruta = inst._ruta_vendor_mp(ya_esta['destino'])
            os.makedirs(os.path.dirname(ruta), exist_ok=True)
            open(ruta, 'wb').write(b'x')
            llamadas = []

            def falso(url, destino_abs, timeout=30):
                llamadas.append(url)
                os.makedirs(os.path.dirname(destino_abs), exist_ok=True)
                open(destino_abs, 'wb').write(b'y')
                return 1

            with mock.patch.object(inst, '_escribir_licencia_mediapipe'), \
                 mock.patch.object(inst, '_descargar_uno', side_effect=falso):
                mensajes, ok = inst.descargar_vendor_mp(idioma='es')
        self.assertTrue(ok)
        self.assertNotIn(ya_esta['url'], llamadas)
        self.assertEqual(len(llamadas), len(inst.VENDOR_MP) - 1)

    def test_sin_red_para_todo_de_golpe_limpio_y_sin_traza(self):
        """T6: "si no hay red, se dice y se sale limpio, sin traza" — UN solo
        intento (no 6), UN aviso, sin la palabra "Traceback"."""
        inst = _cargar_instalador()
        tmp = self._con_pkg_temporal()
        llamadas = []

        def sin_red(url, destino_abs, timeout=30):
            llamadas.append(url)
            raise inst._SinRedError('[Errno 11001] getaddrinfo failed')

        with mock.patch.object(inst, 'PKG', tmp), \
             mock.patch.object(inst, '_descargar_uno', side_effect=sin_red):
            mensajes, ok = inst.descargar_vendor_mp(idioma='es')
        self.assertFalse(ok)
        self.assertEqual(len(llamadas), 1, 'no debe repetir el intento con el resto de ficheros')
        texto = '\n'.join(mensajes)
        self.assertIn('sin red', texto)
        self.assertNotIn('Traceback', texto)

    def test_sin_red_en_ingles_dice_no_network_sin_traza(self):
        inst = _cargar_instalador()
        tmp = self._con_pkg_temporal()

        def sin_red(url, destino_abs, timeout=30):
            raise inst._SinRedError('timed out')

        with mock.patch.object(inst, 'PKG', tmp), \
             mock.patch.object(inst, '_descargar_uno', side_effect=sin_red):
            mensajes, ok = inst.descargar_vendor_mp(idioma='en')
        self.assertFalse(ok)
        texto = '\n'.join(mensajes)
        self.assertIn('no network', texto)
        self.assertNotIn('Traceback', texto)

    def test_un_fallo_que_no_es_de_red_sigue_con_el_resto(self):
        """Un HTTPError (404, por ejemplo) SÍ hay red — no debe parar el lote
        entero, a diferencia de `_SinRedError`."""
        inst = _cargar_instalador()
        tmp = self._con_pkg_temporal()
        llamadas = []

        def falla_solo_el_modelo(url, destino_abs, timeout=30):
            llamadas.append(url)
            if 'hand_landmarker' in url:
                raise RuntimeError('HTTP 404')
            os.makedirs(os.path.dirname(destino_abs), exist_ok=True)
            open(destino_abs, 'wb').write(b'x')
            return 1

        with mock.patch.object(inst, 'PKG', tmp), \
             mock.patch.object(inst, '_descargar_uno', side_effect=falla_solo_el_modelo):
            mensajes, ok = inst.descargar_vendor_mp(idioma='es')
        self.assertFalse(ok)
        self.assertEqual(len(llamadas), len(inst.VENDOR_MP), 'debe intentar los 6, no pararse en el primer fallo')
        texto = '\n'.join(mensajes)
        self.assertIn('FALLÓ', texto)
        self.assertIn('HTTP 404', texto)

    def test_licencia_se_escribe_solo_si_todo_salio_bien(self):
        inst = _cargar_instalador()
        tmp = self._con_pkg_temporal()

        def ok_siempre(url, destino_abs, timeout=30):
            os.makedirs(os.path.dirname(destino_abs), exist_ok=True)
            open(destino_abs, 'wb').write(b'x')
            return 1

        with mock.patch.object(inst, 'PKG', tmp), \
             mock.patch.object(inst, '_descargar_uno', side_effect=ok_siempre):
            mensajes, ok = inst.descargar_vendor_mp(idioma='es')
            ruta_licencia = inst._ruta_vendor_mp('LICENSE-mediapipe.txt')  # con PKG aún parcheado
        self.assertTrue(ok)
        self.assertTrue(os.path.isfile(ruta_licencia))
        self.assertTrue(any('LICENSE-mediapipe.txt' in m for m in mensajes))

    def test_licencia_no_se_escribe_si_algo_fallo(self):
        inst = _cargar_instalador()
        tmp = self._con_pkg_temporal()

        def falla_uno(url, destino_abs, timeout=30):
            if 'hand_landmarker' in url:
                raise RuntimeError('HTTP 500')
            os.makedirs(os.path.dirname(destino_abs), exist_ok=True)
            open(destino_abs, 'wb').write(b'x')
            return 1

        with mock.patch.object(inst, 'PKG', tmp), \
             mock.patch.object(inst, '_descargar_uno', side_effect=falla_uno):
            mensajes, ok = inst.descargar_vendor_mp(idioma='es')
            ruta_licencia = inst._ruta_vendor_mp('LICENSE-mediapipe.txt')  # con PKG aún parcheado
        self.assertFalse(ok)
        self.assertFalse(os.path.isfile(ruta_licencia))


# ---------------------------------------------------------------------------------
# `--manos` desde la CLI real (subprocess, como un usuario) — con
# `ABYSS_INSTALADOR_TEST_SIN_RED` no existe: se fuerza sin red monkeypatcheando
# en proceso, así que aquí se comprueba solo lo que no toca la red: el flag se
# reconoce y no cuelga con `--help`.
# ---------------------------------------------------------------------------------
class ManosPorCLIEnProceso(unittest.TestCase):
    def test_manos_llama_a_descargar_vendor_mp_y_respeta_su_ok(self):
        """Sin lanzar un subproceso de verdad (que sí golpearía la red): se
        comprueba que el bloque de `--manos` en `__main__` usa el resultado de
        `descargar_vendor_mp` para el código de salida, imprimiendo cada
        mensaje — mismo patrón que `--instalar-dependencias`."""
        inst = _cargar_instalador()
        fuente = inspect.getsource(inst)
        self.assertIn("if '--manos' in argv:", fuente)
        # el bloque debe llamar a descargar_vendor_mp e imprimir sus mensajes,
        # igual que el de --instalar-dependencias con instalar_dependencias.
        i = fuente.index("if '--manos' in argv:")
        bloque = fuente[i:i + 260]
        self.assertIn('descargar_vendor_mp(', bloque)
        self.assertIn('print(msj)', bloque)
        self.assertIn('sys.exit(0 if ok else 1)', bloque)


# ---------------------------------------------------------------------------------
# `_descargar_uno`: el único punto que toca la red de verdad — probado con
# `urllib.request.urlopen` sustituido por una respuesta en memoria
# (`io.BytesIO`), JAMÁS un socket real.
# ---------------------------------------------------------------------------------
class DescargarUnoEscribeAtomicoYClasificaLosFallos(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='abyss_descargar_uno_')
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_escribe_el_contenido_y_devuelve_los_bytes_medidos(self):
        inst = _cargar_instalador()
        destino = os.path.join(self.tmp, 'wasm', 'archivo.bin')
        contenido = b'contenido de prueba, nunca se descarga de verdad'
        with mock.patch.object(inst.urllib.request, 'urlopen', return_value=io.BytesIO(contenido)) as fake:
            n = inst._descargar_uno('https://example.invalid/archivo.bin', destino, timeout=7)
        fake.assert_called_once()
        self.assertEqual(fake.call_args.kwargs.get('timeout'), 7)
        self.assertEqual(n, len(contenido))
        with open(destino, 'rb') as fh:
            self.assertEqual(fh.read(), contenido)
        # atómico: no debe sobrevivir el fichero temporal
        self.assertFalse(os.path.exists(destino + '.tmp-abyss'))

    def test_escritura_no_deja_crlf_en_disco(self):
        """El propio proyecto ya tiene un bug conocido de CRLF (ver
        `_escribir_json`); aquí el contenido es binario y `_descargar_uno`
        escribe en modo 'wb', así que no debe traducir NADA."""
        inst = _cargar_instalador()
        destino = os.path.join(self.tmp, 'archivo.bin')
        contenido = b'linea1\nlinea2\n'
        with mock.patch.object(inst.urllib.request, 'urlopen', return_value=io.BytesIO(contenido)):
            inst._descargar_uno('https://example.invalid/archivo.bin', destino)
        self.assertEqual(Path(destino).read_bytes(), contenido)

    def test_http_error_se_convierte_en_runtimeerror_con_el_codigo(self):
        inst = _cargar_instalador()
        err = urllib.error.HTTPError('https://example.invalid', 404, 'not found', {}, None)
        with mock.patch.object(inst.urllib.request, 'urlopen', side_effect=err):
            with self.assertRaises(RuntimeError) as ctx:
                inst._descargar_uno('https://example.invalid/x', os.path.join(self.tmp, 'x.bin'))
        self.assertIn('404', str(ctx.exception))

    def test_url_error_se_convierte_en_sinrederror(self):
        inst = _cargar_instalador()
        with mock.patch.object(inst.urllib.request, 'urlopen',
                                side_effect=urllib.error.URLError('nombre no resuelto')):
            with self.assertRaises(inst._SinRedError):
                inst._descargar_uno('https://example.invalid/x', os.path.join(self.tmp, 'x.bin'))

    def test_timeout_se_convierte_en_sinrederror(self):
        inst = _cargar_instalador()
        with mock.patch.object(inst.urllib.request, 'urlopen', side_effect=socket.timeout('timed out')):
            with self.assertRaises(inst._SinRedError):
                inst._descargar_uno('https://example.invalid/x', os.path.join(self.tmp, 'x.bin'))

    def test_fallo_al_escribir_no_deja_el_tmp_a_medias(self):
        """Si algo revienta A MITAD de escribir (disco lleno, permiso...), no
        debe quedar ni `archivo.bin.tmp-abyss` ni `archivo.bin`."""
        inst = _cargar_instalador()

        class _RespuestaQueRevienta(io.BytesIO):
            def read(self, *a, **kw):
                raise OSError('disco lleno (simulado)')

        destino = os.path.join(self.tmp, 'archivo.bin')
        with mock.patch.object(inst.urllib.request, 'urlopen', return_value=_RespuestaQueRevienta(b'x')):
            with self.assertRaises(OSError):
                inst._descargar_uno('https://example.invalid/x', destino)
        self.assertFalse(os.path.exists(destino))
        self.assertFalse(os.path.exists(destino + '.tmp-abyss'))


# ---------------------------------------------------------------------------------
# La licencia de MediaPipe: Apache License 2.0, registrada donde el paquete
# guarda las licencias de terceros (mismo patrón que `LICENSE-three.txt`), pero
# ESCRITA por el instalador — nunca commiteada (el vendor entero es descargado).
# ---------------------------------------------------------------------------------
class LicenciaMediaPipe(unittest.TestCase):
    def test_texto_declara_apache_2_0_y_el_paquete_vendorizado(self):
        inst = _cargar_instalador()
        self.assertIn('Apache License', inst._LICENCIA_MEDIAPIPE_TEXTO)
        self.assertIn('Version 2.0', inst._LICENCIA_MEDIAPIPE_TEXTO)
        self.assertIn('@mediapipe/tasks-vision', inst._LICENCIA_MEDIAPIPE_TEXTO)
        self.assertIn('TERMS AND CONDITIONS', inst._LICENCIA_MEDIAPIPE_TEXTO)

    def test_escribir_licencia_mediapipe_crea_el_fichero_sin_crlf(self):
        inst = _cargar_instalador()
        tmp = tempfile.mkdtemp(prefix='abyss_licencia_mp_')
        try:
            with mock.patch.object(inst, 'PKG', tmp):
                inst._escribir_licencia_mediapipe()
                ruta = inst._ruta_vendor_mp('LICENSE-mediapipe.txt')
                self.assertTrue(os.path.isfile(ruta))
                crudo = Path(ruta).read_bytes()
                self.assertNotIn(b'\r\n', crudo)
                self.assertIn(b'Apache License', crudo)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()
