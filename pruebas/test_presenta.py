"""`presenta.py`: el vídeo de un minuto que genera el
propio paquete.

`presenta.py` no llama a `rutas.resolver()` ni lee stdin al importarse (construye su
propio proyecto de ejemplo en un directorio temporal y solo invoca `varas.py`/
`vigia.py` por `subprocess` DENTRO de `generar()`, ver su docstring) — a diferencia de
`varas.py`/`vigia.py`, es seguro importarlo directo en el proceso de la prueba (mismo
criterio que `test_render3d.py` con `render3d`, o `test_auditar.py` con `auditar`):
más rápido que un subproceso por prueba. Solo el análisis de argumentos de la CLI
(`_cli`) se ejercita por subprocess, para probar el argv real (mensajes, código de
salida) sin depender de que el proceso de la prueba no haya tocado ya `sys.argv`.

Piezas naturalmente opcionales, forzadas ausentes con las banderas que YA declaran sus
propios módulos (nunca se depende de qué tenga instalado la máquina que corre la
suite, ni se toca la red — reglas de esta suite):
`ABYSS_SIN_RED` (mundo.py, vía la propia comprobación de `presenta.py` — `mundo.py` no
mira esa variable por su cuenta), `ABYSS_RENDER3D_NAVEGADOR=''` (render3d.py: sin
navegador sin cabeza), `ABYSS_LECTURA_VISUAL_SIN_WINRT`/`SIN_TESSERACT` (lectura_visual.py:
sin motor OCR — el sub-verbo `fotocopia` de "el ojo" sigue vivo mientras haya OpenCV,
así que para dejar ese bloque REALMENTE sin nada que enseñar hace falta además la
variable de abajo). Los bloques que no dependen de nada opcional (memoria/honestidad/
auditoría/sentidos/pintor/estilos: son el propio paquete, no una integración externa)
se fuerzan ausentes, cuando una prueba lo necesita, con `ABYSS_PRESENTA_FORZAR_AUSENTE`
— variable de prueba propia de `presenta.py`, documentada en su propio código, mismo
patrón que las de arriba (lista de ids separados por comas: `memoria,honestidad,...`).

No se genera aquí el vídeo largo de verdad (60 s con todo disponible): eso lo hace el
integrador una vez. Todas las pruebas de generación completa usan un `--segundos`
corto, y las piezas más lentas (red, navegador sin cabeza) van forzadas ausentes para
que la suite no dependa de ellas ni las toque.
"""
import sys
import os
import re
import json
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ayudas as ay

sys.path.insert(0, str(ay.PKG))
import presenta  # noqa: E402  (sin rutas.resolver() al importar, ver docstring de este fichero)

try:
    import imageio_ffmpeg
    _FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()
    FFMPEG_DISPONIBLE = bool(_FFMPEG_EXE)
    _MOTIVO_SIN_FFMPEG = ''
except Exception as e:
    FFMPEG_DISPONIBLE = False
    _MOTIVO_SIN_FFMPEG = f'falta imageio_ffmpeg — {type(e).__name__}: {e}'

# Piezas que dependen de algo fuera del propio paquete: siempre forzadas ausentes en la
# suite (sin red, sin navegador sin cabeza, sin motor OCR) — nunca se depende de la
# máquina que corre las pruebas ni se toca la red (reglas de esta suite).
ENV_SIN_OPCIONALES = {
    "ABYSS_SIN_RED": "1",
    "ABYSS_RENDER3D_NAVEGADOR": "",
    "ABYSS_LECTURA_VISUAL_SIN_WINRT": "1",
    "ABYSS_LECTURA_VISUAL_SIN_TESSERACT": "1",
}
# "el ojo" sigue vivo con solo OpenCV (fotocopia no necesita motor OCR): para dejarlo
# TAMBIÉN ausente (la prueba de "todas las piezas ausentes") hace falta forzarlo aparte.
IDS_PROPIOS_DEL_PAQUETE = ("memoria", "honestidad", "auditoria", "sentidos", "pintor", "estilos")


def _duracion_mp4(ruta):
    """Segundos de un `.mp4`, leyendo el "Duration: HH:MM:SS.ss" que el propio `ffmpeg`
    imprime por stderr al abrirlo — no hace falta `ffprobe` aparte, ya que
    `imageio_ffmpeg` solo trae el binario de `ffmpeg`."""
    r = subprocess.run([_FFMPEG_EXE, "-i", ruta], capture_output=True, text=True, timeout=30)
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", r.stderr)
    assert m, f'no se encontró "Duration:" en la salida de ffmpeg: {r.stderr[-500:]}'
    h, mi, s = m.groups()
    return int(h) * 3600 + int(mi) * 60 + float(s)


class TechoPorBiseccion(unittest.TestCase):
    def test_sin_valores_da_cero(self):
        self.assertEqual(presenta._techo_por_bisección([], 10.0), 0.0)

    def test_techo_reparte_para_sumar_el_objetivo(self):
        # tres bloques largos: el techo debe dejarlos a todos igual de cortos y sumar 6.0
        techo = presenta._techo_por_bisección([4.0, 4.0, 4.0], 6.0)
        self.assertAlmostEqual(sum(min(v, techo) for v in (4.0, 4.0, 4.0)), 6.0, places=2)
        self.assertAlmostEqual(techo, 2.0, places=2)

    def test_techo_no_recorta_lo_que_ya_cabe(self):
        # un valor corto (1.0) y uno largo (10.0), objetivo 5.0: el corto no debe tocarse
        techo = presenta._techo_por_bisección([1.0, 10.0], 5.0)
        self.assertGreaterEqual(techo, 1.0)
        self.assertAlmostEqual(min(1.0, techo) + min(10.0, techo), 5.0, places=2)


class AjustarPresupuesto(unittest.TestCase):
    def test_sin_bloques_no_hay_nada_que_ajustar(self):
        asignadas, recortes = presenta._ajustar_presupuesto([], 10.0)
        self.assertEqual(asignadas, {})
        self.assertEqual(recortes, [])

    def test_si_ya_cabe_no_recorta_nada(self):
        ids = ["honestidad", "auditoria"]  # naturales 4.0 + 4.5 = 8.5
        asignadas, recortes = presenta._ajustar_presupuesto(ids, 100.0)
        self.assertEqual(asignadas, {i: presenta.DURACION_NATURAL[i] for i in ids})
        self.assertEqual(recortes, [])

    def test_recorta_solo_los_mas_largos(self):
        # "pintor" (natural 8.0) es el más largo con diferencia; "honestidad" (4.0) es
        # de las más cortas — con un objetivo ajustado, "pintor" debe recortarse y
        # "honestidad" debe quedar SIN tocar (ver docstring: "recorta los tramos más
        # largos", nunca todo por igual).
        ids = ["honestidad", "pintor"]  # naturales 4.0 + 8.0 = 12.0
        asignadas, recortes = presenta._ajustar_presupuesto(ids, 8.0)
        self.assertEqual(asignadas["honestidad"], presenta.DURACION_NATURAL["honestidad"])
        self.assertLess(asignadas["pintor"], presenta.DURACION_NATURAL["pintor"])
        ids_recortados = {r[0] for r in recortes}
        self.assertEqual(ids_recortados, {"pintor"})

    def test_nunca_baja_del_piso(self):
        ids = list(presenta.ORDEN_BLOQUES)  # los diez, con un objetivo minúsculo
        asignadas, _recortes = presenta._ajustar_presupuesto(ids, 0.5)
        for id_bloque, segundos in asignadas.items():
            self.assertGreaterEqual(segundos, presenta.PISO_BLOQUE, id_bloque)


class ProyectoDeEjemplo(unittest.TestCase):
    """`_construir_proyecto_ejemplo()` + `varas.py --index` (subprocess, como lo invoca
    `_bloque_memoria`): comprueba que el proyecto sintético de este guion cruza de
    verdad `propiocepcion.UMBRAL_FRIO` y que los pesos ◆ se RECALCULAN (no "sin vara
    todavía") — la ficha citada Y leída debe acabar con más ◆ que la que nadie usa."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='abyss_test_presenta_')
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_indice_recalcula_pesos_de_verdad(self):
        proyecto = presenta._construir_proyecto_ejemplo(self.tmp)
        idx = os.path.join(proyecto, 'memory', 'MEMORY.md')
        with open(idx, encoding='utf-8') as fh:
            antes = fh.read()
        self.assertNotIn('◆', antes, 'antes de --index no debería haber ningún peso todavía')

        r = presenta._ejecutar_pieza('varas.py', ['--index'], proyecto, avisar=lambda *a, **k: None)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('índice reescrito', r.stdout)

        with open(idx, encoding='utf-8') as fh:
            despues = fh.read()
        self.assertIn('la_vara.md) ◆◆◆', despues, despues)
        self.assertIn('el_andamiaje.md) ◆', despues, despues)
        # la_confeccion.md no la cita ni la lee nadie: sin uso, sin glifo (glyph() en varas.py)
        self.assertNotIn('la_confeccion.md) ◆', despues, despues)


class BloquesOptativosSinPieza(unittest.TestCase):
    """Cada bloque que depende de algo FUERA del propio paquete debe saltarse con
    `PiezaNoDisponible` (nunca reventar) cuando esa pieza no está — probado llamando al
    generador directamente, sin pasar por todo `generar()`."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='abyss_test_presenta_')
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.ctx = {
            "ancho": 320, "alto": 180, "idioma": "es", "T": presenta.TEXTOS["es"],
            "tmp": self.tmp, "avisar": lambda *a, **k: None, "duracion": 1.0,
        }

    def test_mundo_sin_red(self):
        with mock.patch.dict(os.environ, {"ABYSS_SIN_RED": "1"}):
            with self.assertRaises(presenta.PiezaNoDisponible):
                presenta._bloque_mundo(self.ctx)

    def test_threed_sin_navegador(self):
        with mock.patch.dict(os.environ, {"ABYSS_RENDER3D_NAVEGADOR": ""}):
            with self.assertRaises(presenta.PiezaNoDisponible):
                presenta._bloque_threed(self.ctx)

    def test_holograma_sin_navegador(self):
        with mock.patch.dict(os.environ, {"ABYSS_RENDER3D_NAVEGADOR": ""}):
            with self.assertRaises(presenta.PiezaNoDisponible):
                presenta._bloque_holograma(self.ctx)

    def test_ojo_sin_motor_ni_opencv(self):
        env = {"ABYSS_LECTURA_VISUAL_SIN_WINRT": "1", "ABYSS_LECTURA_VISUAL_SIN_TESSERACT": "1"}
        with mock.patch.dict(os.environ, env), \
             mock.patch.object(presenta.lectura_visual, "_CV2_OK", False):
            with self.assertRaises(presenta.PiezaNoDisponible):
                presenta._bloque_ojo(self.ctx)

    def test_ojo_sigue_vivo_solo_con_opencv(self):
        # fotocopia no necesita motor OCR: sin él, pero CON OpenCV, el bloque debe
        # seguir dando algo que enseñar (no debe lanzar).
        env = {"ABYSS_LECTURA_VISUAL_SIN_WINRT": "1", "ABYSS_LECTURA_VISUAL_SIN_TESSERACT": "1"}
        if not getattr(presenta.lectura_visual, "_CV2_OK", False):
            self.skipTest('OpenCV no está instalado en esta máquina')
        with mock.patch.dict(os.environ, env):
            frames = presenta._bloque_ojo(self.ctx)
        self.assertTrue(frames)


class CliArgumentos(unittest.TestCase):
    """Solo el análisis de argumentos: subprocess, para probar el argv real (nunca
    llega a `generar()`, así que estas pruebas son rápidas)."""

    def _cli(self, args, timeout=15):
        return ay.ejecutar(ay.script('presenta.py'), args, dict(os.environ), timeout=timeout)

    def test_bandera_desconocida(self):
        r = self._cli(['--no-existe', 'x'])
        self.assertEqual(r.returncode, 1)
        self.assertIn('no reconocido', r.stdout)

    def test_segundos_no_numerico(self):
        r = self._cli(['--segundos', 'pronto'])
        self.assertEqual(r.returncode, 1)
        self.assertIn('--segundos', r.stdout)

    def test_ancho_no_numerico(self):
        r = self._cli(['--ancho', 'grande'])
        self.assertEqual(r.returncode, 1)
        self.assertIn('--ancho', r.stdout)

    def test_idioma_invalido(self):
        r = self._cli(['--idioma', 'fr'])
        self.assertEqual(r.returncode, 1)
        self.assertIn('--idioma', r.stdout)

    def test_ayuda_imprime_docstring_y_sale_1(self):
        r = self._cli(['--help'])
        self.assertEqual(r.returncode, 1)
        self.assertIn('presenta.py', r.stdout)


@unittest.skipUnless(FFMPEG_DISPONIBLE, _MOTIVO_SIN_FFMPEG or 'falta imageio_ffmpeg')
class GeneracionCompleta(unittest.TestCase):
    """Las pruebas de esta clase llaman a `generar()` en proceso (ver docstring
    del módulo) — nunca el vídeo largo de verdad."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='abyss_test_presenta_')
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self._entorno = mock.patch.dict(os.environ, ENV_SIN_OPCIONALES)
        self._entorno.start()
        self.addCleanup(self._entorno.stop)

    def test_segundos_12_produce_video_en_los_10_a_14_segundos(self):
        salida = os.path.join(self.tmp, 'salida.mp4')
        avisos = []
        r = presenta.generar(salida=salida, segundos=12.0, avisar=avisos.append)

        self.assertTrue(os.path.isfile(salida))
        dur_real = _duracion_mp4(salida)
        self.assertGreater(dur_real, 10.0, avisos)
        self.assertLess(dur_real, 14.0, avisos)
        # el propio resumen no debe mentir sobre su duración (dentro de un fotograma)
        self.assertAlmostEqual(r['duracion'], dur_real, delta=1.0 / presenta.FPS + 0.05)

        disponibles = [b for b in r['bloques'] if b['disponible']]
        ausentes = [b for b in r['bloques'] if not b['disponible']]
        self.assertEqual(len(disponibles) + len(ausentes), len(presenta.ORDEN_BLOQUES))
        self.assertGreater(len(disponibles), 0, 'con las piezas propias del paquete debería haber bloques')
        # las tres piezas forzadas ausentes por ENV_SIN_OPCIONALES SIEMPRE deben faltar
        ids_ausentes = {b['id'] for b in ausentes}
        self.assertEqual({'mundo', 'threed', 'holograma'} & ids_ausentes, {'mundo', 'threed', 'holograma'})
        # todo lo que es del propio paquete (sin dependencia externa) debe seguir vivo
        ids_disponibles = {b['id'] for b in disponibles}
        self.assertTrue(set(IDS_PROPIOS_DEL_PAQUETE).issubset(ids_disponibles), r['bloques'])
        # cada bloque disponible debe llevar su duración real medida, ninguno a 0
        for b in disponibles:
            self.assertGreater(b['segundos_reales'], 0, b)
        self.assertTrue(r['recortes'], 'con --segundos 12 debería haber hecho falta recortar algo')

    def test_todas_las_piezas_ausentes_no_revienta(self):
        salida = os.path.join(self.tmp, 'salida.mp4')
        forzar = ','.join(IDS_PROPIOS_DEL_PAQUETE + ('ojo',))
        with mock.patch.dict(os.environ, {'ABYSS_PRESENTA_FORZAR_AUSENTE': forzar}):
            r = presenta.generar(salida=salida, segundos=10.0, avisar=lambda *a, **k: None)

        self.assertTrue(os.path.isfile(salida))
        self.assertGreater(_duracion_mp4(salida), 0.5)
        self.assertEqual([b for b in r['bloques'] if b['disponible']], [])
        self.assertEqual(len(r['omitidos']), len(presenta.ORDEN_BLOQUES))
        self.assertEqual(r['recortes'], [])

    def test_idioma_en_no_deja_texto_de_control_en_castellano(self):
        salida = os.path.join(self.tmp, 'salida.mp4')
        avisos = []
        presenta.generar(salida=salida, idioma='en', segundos=8.0, avisar=avisos.append)
        texto = '\n'.join(avisos)
        # plantillas de log SOLO en castellano (TEXTOS["es"]): no deben colarse con --idioma en
        self.assertNotIn('recorte de presupuesto', texto)
        self.assertNotIn('se salta', texto)


if __name__ == '__main__':
    unittest.main()
