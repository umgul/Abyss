"""TAREA D · integración: los verbos `render` y `mundo`
de `imagen.py`, que delegan en `render3d.renderizar()` y en `mundo._cli()` — mismo patrón que
ya usan `pintar`→`pintor._cli()` y `video`→`video_pintura._cli()`.

`imagen.py` no llama a `rutas.resolver()` a nivel de módulo (solo dentro de `_cli()`, y aquí
NUNCA se ejecuta al importar): seguro importarlo en el propio proceso de la prueba, igual que
`test_render3d.py` ya hace con `render3d` y `test_mundo.py` con `mundo` (ver sus docstrings).

`render3d` y `pintor` NO se ejecutan de verdad aquí (nada de navegador sin cabeza real ni de
Pillow/numpy real): se sustituyen en `sys.modules` por módulos de mentira ANTES de que
`imagen._cli()` haga su `import render3d` / `import pintor` — como Python cachea los módulos
ya importados por nombre, ese `import` de dentro recoge la mentira sin tocar disco ni depender
de qué haya instalado la máquina que corre la suite. Así se puede comprobar el ENCADENADO
(qué argumentos exactos llegan a cada función, en qué orden, qué se escribe en el log) sin
volver a probar `render3d.renderizar()` ni `pintor.pintar()` por dentro — eso ya lo cubren
`test_render3d.py` y `test_pintor_estilos.py`/`test_imagen_pintar.py`.

`mundo._cli` se sustituye igual, para comprobar que el verbo `mundo` reenvía `argv`/`mem` tal
cual (sin repetir aquí el parseo de banderas de `mundo.py`, que ya prueba `test_mundo.py`) y
devuelve su código de salida sin tocarlo.
"""
import contextlib
import io
import json
import os
import sys
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ayudas as ay  # noqa: E402

sys.path.insert(0, str(ay.PKG))
import imagen  # noqa: E402  (sin rutas.resolver() al importar: seguro en proceso, ver docstring)


def _modulo_falso(nombre, **atributos):
    mod = types.ModuleType(nombre)
    for clave, valor in atributos.items():
        setattr(mod, clave, valor)
    return mod


def _correr(argv, proj):
    """Llama a `imagen._cli(argv)` con `ABYSS_PROYECTO=proj` (orden 4 de `rutas.resolver()`,
    sin tocar stdin) y devuelve `(codigo, stdout)`."""
    buf = io.StringIO()
    with mock.patch.dict(os.environ, {"ABYSS_PROYECTO": str(proj)}):
        with contextlib.redirect_stdout(buf):
            codigo = imagen._cli(argv)
    return codigo, buf.getvalue()


def _ultima_linea_json(stdout):
    return json.loads([l for l in stdout.splitlines() if l.strip()][-1])


class ImagenRenderCLI(unittest.TestCase):
    def test_render_llama_a_renderizar_con_las_banderas_y_registra_en_el_log(self):
        proj = ay.nuevo_proyecto()
        (proj / "memory").mkdir(exist_ok=True)
        llamadas = []

        def renderizar_falso(entrada, **kw):
            llamadas.append((entrada, kw))
            return {"html": "/x/escena_render3d.html", "png": None, "piezas": 3,
                    "grupos": 2, "centro": [0.0, 0.0, 0.0], "radio": 1.0, "unidades": "m"}

        falso = _modulo_falso("render3d", renderizar=renderizar_falso, SinNavegador=RuntimeError)
        with mock.patch.dict(sys.modules, {"render3d": falso}):
            codigo, salida = _correr(["render", "escena.json", "--explosion", "0.5", "--luz", "fria"], proj)

        self.assertEqual(codigo, 0, salida)
        self.assertEqual(len(llamadas), 1)
        entrada, kw = llamadas[0]
        self.assertEqual(entrada, "escena.json")
        self.assertEqual(kw["explosion"], 0.5)
        self.assertEqual(kw["luz"], "fria")
        self.assertIsNone(kw["png"], "sin --pintar ni --png, no debe forzarse la captura")

        datos = _ultima_linea_json(salida)
        self.assertEqual(datos["html"], "/x/escena_render3d.html")

        log = (proj / "memory" / "imagen.log").read_text(encoding="utf-8")
        lineas = [l for l in log.splitlines() if l.strip()]
        self.assertEqual(len(lineas), 1)
        self.assertIn("render", lineas[0])
        self.assertIn("escena.json", lineas[0])
        self.assertIn("escena_render3d.html", lineas[0])

    def test_render_sin_navegador_da_codigo_2_y_no_escribe_en_el_log(self):
        proj = ay.nuevo_proyecto()
        (proj / "memory").mkdir(exist_ok=True)

        def renderizar_falso(entrada, **kw):
            raise falso.SinNavegador("no hay navegador sin cabeza")

        falso = _modulo_falso("render3d", renderizar=renderizar_falso, SinNavegador=RuntimeError)
        with mock.patch.dict(sys.modules, {"render3d": falso}):
            codigo, salida = _correr(["render", "escena.json", "--png"], proj)

        self.assertEqual(codigo, 2)
        self.assertIn("sin dato", salida)
        self.assertFalse((proj / "memory" / "imagen.log").exists(),
                          "un render que falla del todo no debe dejar línea en el log")

    def test_render_error_generico_da_codigo_2_con_sin_render(self):
        proj = ay.nuevo_proyecto()
        (proj / "memory").mkdir(exist_ok=True)

        def renderizar_falso(entrada, **kw):
            raise ValueError("tipo de pieza desconocido: rombo")

        falso = _modulo_falso("render3d", renderizar=renderizar_falso, SinNavegador=RuntimeError)
        with mock.patch.dict(sys.modules, {"render3d": falso}):
            codigo, salida = _correr(["render", "escena.json"], proj)

        self.assertEqual(codigo, 2)
        self.assertIn("sin render", salida)
        self.assertIn("ValueError", salida)

    def test_render_pintar_fuerza_png_y_encadena_con_pintor_pintar(self):
        proj = ay.nuevo_proyecto()
        (proj / "memory").mkdir(exist_ok=True)
        llamadas_render, llamadas_pintar = [], []

        def renderizar_falso(entrada, **kw):
            llamadas_render.append((entrada, kw))
            return {"html": "/x/e_render3d.html", "png": "/x/e_render3d.png", "piezas": 1,
                    "grupos": 1, "centro": [0.0, 0.0, 0.0], "radio": 1.0, "unidades": "m"}

        def pintar_falso(ruta, **kw):
            llamadas_pintar.append((ruta, kw))
            return {"png": "/x/e_render3d_pintada.png", "trazos": "/x/e_render3d_trazos.json.gz",
                    "pinceladas": 321, "error_medio": 4.2, "W": 10, "H": 10,
                    "estilo": kw.get("estilo", "oleo")}

        falso_r3d = _modulo_falso("render3d", renderizar=renderizar_falso, SinNavegador=RuntimeError)
        falso_pintor = _modulo_falso("pintor", pintar=pintar_falso)
        with mock.patch.dict(sys.modules, {"render3d": falso_r3d, "pintor": falso_pintor}):
            codigo, salida = _correr(
                ["render", "escena.json", "--pintar", "--estilo", "acuarela", "--acabado"], proj)

        self.assertEqual(codigo, 0, salida)

        self.assertEqual(len(llamadas_render), 1)
        _, kw_render = llamadas_render[0]
        self.assertIs(kw_render["png"], True, "--pintar debe forzar --png aunque no se pida a mano")

        self.assertEqual(len(llamadas_pintar), 1)
        ruta_pintada, kw_pintar = llamadas_pintar[0]
        self.assertEqual(ruta_pintada, "/x/e_render3d.png", "debe pintar el PNG que dejó el render")
        self.assertEqual(kw_pintar["estilo"], "acuarela")
        self.assertTrue(kw_pintar["acabado"])
        self.assertFalse(kw_pintar["alta"])
        self.assertEqual(kw_pintar["supermuestreo"], 1, "sin --suave, supermuestreo por defecto")

        datos = _ultima_linea_json(salida)
        self.assertEqual(datos["estilo"], "acuarela", "la última línea de salida es el resultado de pintor")

        log = (proj / "memory" / "imagen.log").read_text(encoding="utf-8")
        lineas = [l for l in log.splitlines() if l.strip()]
        self.assertEqual(len(lineas), 2, "las DOS salidas (render y pintar) se apuntan en el log")
        self.assertIn("render", lineas[0])
        self.assertIn("pintar", lineas[1])
        self.assertIn("e_render3d_pintada.png", lineas[1])

    def test_render_pintar_con_suave_pasa_supermuestreo_2(self):
        proj = ay.nuevo_proyecto()
        (proj / "memory").mkdir(exist_ok=True)
        llamadas_pintar = []

        def renderizar_falso(entrada, **kw):
            return {"html": "/x/e.html", "png": "/x/e.png", "piezas": 1, "grupos": 1,
                    "centro": [0.0, 0.0, 0.0], "radio": 1.0, "unidades": "m"}

        def pintar_falso(ruta, **kw):
            llamadas_pintar.append(kw)
            return {"png": "/x/e_pintada.png", "trazos": "/x/e_trazos.json.gz", "pinceladas": 1,
                    "error_medio": 0.0, "W": 1, "H": 1, "estilo": kw.get("estilo", "oleo")}

        falso_r3d = _modulo_falso("render3d", renderizar=renderizar_falso, SinNavegador=RuntimeError)
        falso_pintor = _modulo_falso("pintor", pintar=pintar_falso)
        with mock.patch.dict(sys.modules, {"render3d": falso_r3d, "pintor": falso_pintor}):
            codigo, salida = _correr(["render", "escena.json", "--pintar", "--suave", "3"], proj)

        self.assertEqual(codigo, 0, salida)
        self.assertEqual(llamadas_pintar[0]["supermuestreo"], 3)

    def test_render_pintar_sin_png_del_render_da_codigo_2(self):
        proj = ay.nuevo_proyecto()
        (proj / "memory").mkdir(exist_ok=True)

        def renderizar_falso(entrada, **kw):
            # caso límite: aunque se fuerce png=True, `render3d.renderizar` podría no
            # dejar un PNG de verdad (p. ej. un aviso ya cubierto en su propia prueba);
            # aquí solo se comprueba que `imagen.py` no revienta ni llama a pintor.
            return {"html": "/x/e.html", "png": None, "piezas": 1, "grupos": 1,
                    "centro": [0.0, 0.0, 0.0], "radio": 1.0, "unidades": "m"}

        llamado_pintor = []
        falso_r3d = _modulo_falso("render3d", renderizar=renderizar_falso, SinNavegador=RuntimeError)
        falso_pintor = _modulo_falso("pintor", pintar=lambda *a, **k: llamado_pintor.append(1))
        with mock.patch.dict(sys.modules, {"render3d": falso_r3d, "pintor": falso_pintor}):
            codigo, salida = _correr(["render", "escena.json", "--pintar"], proj)

        self.assertEqual(codigo, 2)
        self.assertIn("sin cuadro", salida)
        self.assertFalse(llamado_pintor, "sin PNG del render, pintor.pintar() no debe llamarse")

    def test_falta_entrada_da_codigo_1(self):
        proj = ay.nuevo_proyecto()
        (proj / "memory").mkdir(exist_ok=True)
        codigo, salida = _correr(["render"], proj)
        self.assertEqual(codigo, 1)
        self.assertIn("falta", salida)

    def test_argumento_no_reconocido_da_codigo_1(self):
        proj = ay.nuevo_proyecto()
        (proj / "memory").mkdir(exist_ok=True)
        codigo, salida = _correr(["render", "escena.json", "--marciano"], proj)
        self.assertEqual(codigo, 1)
        self.assertIn("argumento no reconocido", salida)


class ImagenMundoCLI(unittest.TestCase):
    def test_mundo_delega_en_mundo_cli_con_el_mismo_argv_y_mem(self):
        proj = ay.nuevo_proyecto()
        (proj / "memory").mkdir(exist_ok=True)
        llamadas = []

        def cli_falso(argv, mem, pedir_fn=None):
            llamadas.append((list(argv), mem, pedir_fn))
            return 0

        falso = _modulo_falso("mundo", _cli=cli_falso)
        with mock.patch.dict(sys.modules, {"mundo": falso}):
            codigo, salida = _correr(
                ["mundo", "La última cena", "--fuente", "commons", "--n", "3"], proj)

        self.assertEqual(codigo, 0, salida)
        self.assertEqual(len(llamadas), 1)
        argv, mem_recibido, pedir_fn = llamadas[0]
        self.assertEqual(argv, ["La última cena", "--fuente", "commons", "--n", "3"],
                          "debe reenviar el argv del verbo tal cual, sin --proyecto")
        self.assertEqual(os.path.normcase(mem_recibido),
                          os.path.normcase(os.path.join(os.path.abspath(str(proj)), "memory")))
        self.assertIsNone(pedir_fn, "imagen.py no debe inyectar su propio pedir_fn: usa el real")

    def test_mundo_propaga_el_codigo_de_salida_de_mundo_cli(self):
        proj = ay.nuevo_proyecto()
        (proj / "memory").mkdir(exist_ok=True)
        falso = _modulo_falso("mundo", _cli=lambda argv, mem, pedir_fn=None: 2)
        with mock.patch.dict(sys.modules, {"mundo": falso}):
            codigo, _ = _correr(["mundo", "motivo cualquiera"], proj)
        self.assertEqual(codigo, 2)


if __name__ == "__main__":
    unittest.main()
