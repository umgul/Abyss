"""`render3d.py` no usa `rutas.resolver()` (guion de fichero a fichero): se importa
directamente para las pruebas de formato, y por `subprocess` para las que cubren la CLI
completa. `--png` con navegador real solo corre si lo encuentra `_buscar_navegador()`; sin él, se fuerza con `ABYSS_RENDER3D_NAVEGADOR=''`."""
import sys
import os
import re
import json
import struct
import base64
import inspect
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ayudas as ay

sys.path.insert(0, str(ay.PKG))
import render3d  # noqa: E402  (sin rutas.resolver(): seguro importarlo en proceso, ver docstring)

ESCENA_PRUEBA = ay.RAIZ / "pruebas" / "datos" / "escena_prueba.json"


def _ultima_linea_json(stdout):
    return json.loads([l for l in stdout.splitlines() if l.strip()][-1])


def _dimensiones_png(ruta):
    """Ancho/alto de un PNG leyendo su cabecera IHDR a pelo (sin Pillow: `render3d.py` no
    depende de ella, y esta prueba tampoco debería)."""
    with open(ruta, "rb") as fh:
        datos = fh.read(33)
    assert datos[:8] == b"\x89PNG\r\n\x1a\n", "no es un PNG válido"
    ancho, alto = struct.unpack(">II", datos[16:24])
    return ancho, alto


def _perfiles_cdp():
    """Nombres `abyss_cdp_*` que hay ahora mismo en el temporal de la suite. `conftest.py`
    redirige TEMP/TMP y `tempfile.tempdir` a una carpeta propia antes de que nada se
    importe, y el subproceso de `render3d.py` la hereda por variables de entorno: por
    eso este mismo `tempfile.gettempdir()`, en el proceso de la prueba, es donde
    `navegador_cdp.captura()` crea (y debe borrar) el perfil temporal del subproceso."""
    return {n for n in os.listdir(tempfile.gettempdir()) if n.startswith("abyss_cdp_")}


def _sin_url_externa(html):
    """Ningún `http(s)://` fuera del ÚNICO caso legítimo: el espacio de nombres XHTML que usa
    `document.createElementNS(...)` dentro del propio three.js embebido (un identificador,
    nunca una URL que se llegue a pedir por red — ver `_texto_three_embebido()`)."""
    import re
    restante = html.replace("http://www.w3.org/1999/xhtml", "")
    return not re.search(r"https?://", restante)


class EscenaJsonCLI(unittest.TestCase):
    def test_tres_piezas_por_nombre_y_deslizador(self):
        tmp = tempfile.mkdtemp(prefix="abyss_render3d_")
        r = ay.ejecutar(ay.script("render3d.py"), [str(ESCENA_PRUEBA), "--html", os.path.join(tmp, "salida.html")],
                        dict(os.environ), timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        datos = _ultima_linea_json(r.stdout)
        self.assertEqual(datos["piezas"], 3)
        self.assertEqual(datos["grupos"], 2)  # "base"+"columna" comparten grupo "cuerpo"; "remate" va solo
        with open(datos["html"], encoding="utf-8") as fh:
            html = fh.read()
        for nombre in ("base", "columna", "remate"):
            self.assertIn(f'"{nombre}"', html)
        self.assertIn("sldExplosion", html)
        self.assertIn("OrbitaMinima", html)

    def test_html_no_referencia_url_externa(self):
        tmp = tempfile.mkdtemp(prefix="abyss_render3d_")
        ruta_html = os.path.join(tmp, "salida.html")
        r = ay.ejecutar(ay.script("render3d.py"), [str(ESCENA_PRUEBA), "--html", ruta_html], dict(os.environ), timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(ruta_html, encoding="utf-8") as fh:
            html = fh.read()
        self.assertTrue(_sin_url_externa(html), "la página no debe referenciar ninguna URL externa")

    def test_html_se_escribe_siempre_aunque_no_se_pida_bandera(self):
        """El HTML es el propio resultado (a diferencia de `pintor.py`, donde
        `--html` es un extra opcional): se escribe exista o no la bandera `--html`."""
        tmp = tempfile.mkdtemp(prefix="abyss_render3d_")
        entrada = os.path.join(tmp, "escena_prueba.json")
        with open(ESCENA_PRUEBA, encoding="utf-8") as fh:
            contenido = fh.read()
        with open(entrada, "w", encoding="utf-8") as fh:
            fh.write(contenido)
        r = ay.ejecutar(ay.script("render3d.py"), [entrada], dict(os.environ), timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(os.path.exists(os.path.join(tmp, "escena_prueba_render3d.html")))

    def test_pieza_tipo_desconocido_no_revienta(self):
        tmp = tempfile.mkdtemp(prefix="abyss_render3d_")
        entrada = os.path.join(tmp, "mala.json")
        with open(entrada, "w", encoding="utf-8") as fh:
            json.dump({"piezas": [{"nombre": "x", "tipo": "pentagono", "pos": [0, 0, 0]}]}, fh)
        r = ay.ejecutar(ay.script("render3d.py"), [entrada], dict(os.environ), timeout=30)
        self.assertEqual(r.returncode, 2)
        self.assertIn("sin render", r.stdout)

    def test_entrada_inexistente_no_revienta(self):
        tmp = tempfile.mkdtemp(prefix="abyss_render3d_")
        r = ay.ejecutar(ay.script("render3d.py"), [os.path.join(tmp, "no_existe.json")], dict(os.environ), timeout=30)
        self.assertEqual(r.returncode, 2)
        self.assertIn("sin render", r.stdout)

    def test_extension_no_soportada(self):
        tmp = tempfile.mkdtemp(prefix="abyss_render3d_")
        entrada = os.path.join(tmp, "modelo.fbx")
        with open(entrada, "w", encoding="utf-8") as fh:
            fh.write("lo que sea")
        r = ay.ejecutar(ay.script("render3d.py"), [entrada], dict(os.environ), timeout=30)
        self.assertEqual(r.returncode, 2)
        self.assertIn("sin render", r.stdout)


class AcabadoEstudioCLI(unittest.TestCase):
    """`--acabado estudio|mate`: `mate` es el valor por defecto; `estudio` sigue la receta
    de `pintor_demo/tornillo/tornillo.html`. El JS es el mismo para los dos modos (decide en
    tiempo de ejecución), así que aquí solo se comprueba lo que cambia en el HTML escrito."""

    def test_mate_por_defecto_y_rejilla_marcada(self):
        tmp = tempfile.mkdtemp(prefix="abyss_render3d_acabado_")
        ruta_html = os.path.join(tmp, "s.html")
        r = ay.ejecutar(ay.script("render3d.py"), [str(ESCENA_PRUEBA), "--html", ruta_html],
                        dict(os.environ), timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(ruta_html, encoding="utf-8") as fh:
            html = fh.read()
        self.assertIn('"acabado": "mate"', html)
        self.assertIn('id="chkRejilla" type="checkbox" checked', html, "mate: la rejilla sigue marcada por defecto, como siempre")

    def test_estudio_acabado_embebido_y_sin_rejilla_marcada(self):
        tmp = tempfile.mkdtemp(prefix="abyss_render3d_acabado_")
        ruta_html = os.path.join(tmp, "s.html")
        r = ay.ejecutar(ay.script("render3d.py"), [str(ESCENA_PRUEBA), "--html", ruta_html, "--acabado", "estudio"],
                        dict(os.environ), timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(ruta_html, encoding="utf-8") as fh:
            html = fh.read()
        self.assertIn('"acabado": "estudio"', html)
        self.assertIn('id="chkRejilla" type="checkbox" >', html, "estudio: SIN rejilla al arrancar (pide el encargo)")
        # sigue sin haber ninguna URL externa: el entorno es 100% procedural (dos <canvas> 2D)
        self.assertTrue(_sin_url_externa(html), "el acabado estudio no debe traer ninguna URL externa")

    def test_acabado_invalido_error_y_no_revienta(self):
        tmp = tempfile.mkdtemp(prefix="abyss_render3d_acabado_")
        r = ay.ejecutar(ay.script("render3d.py"),
                        [str(ESCENA_PRUEBA), "--html", os.path.join(tmp, "s.html"), "--acabado", "brillante"],
                        dict(os.environ), timeout=30)
        self.assertEqual(r.returncode, 1)
        self.assertIn("--acabado debe ser mate/estudio", r.stdout)


class AcabadoEstudioFuente(unittest.TestCase):
    """`_MAIN_JS` es compartido por "mate" y "estudio" (`ESCENA.acabado` decide en el
    navegador, no `_construir_html()` en Python): la prueba real de que la receta de
    estudio está ahí es leer `_MAIN_JS` directamente."""

    def test_receta_de_estudio_presente_y_guardada_tras_el_if(self):
        js = render3d._MAIN_JS
        for pieza in ("ACESFilmicToneMapping", "PCFSoftShadowMap", "CubeReflectionMapping",
                      "metalness: 1.0", "shadowMap.enabled", "receiveShadow = true"):
            self.assertIn(pieza, js, f"falta {pieza!r} en _MAIN_JS: la receta de estudio no está")
        # las cinco piezas de la receta cuelgan del mismo guardián -- si alguna se escapara
        # fuera del `if`, "mate" heredaría metal/sombras/tono ACES sin pedirlo.
        self.assertEqual(js.count("ESCENA.acabado === 'estudio'"), 5,
                          "material/renderer/entorno/luces/suelo: cinco guardianes, ni uno menos")
        # la rejilla se sigue creando siempre (el control de la página la puede reencender);
        # lo que cambia con el acabado es solo su visibilidad inicial.
        self.assertIn("grid.visible = (ESCENA.acabado !== 'estudio')", js)


class SinNavegadorCLI(unittest.TestCase):
    def test_sin_navegador_codigo_2_y_mensaje(self):
        """`ABYSS_RENDER3D_NAVEGADOR=''` fuerza la rama "no encontrado" sin depender de qué
        navegadores tenga instalados la máquina que corre la suite (ver docstring de
        `render3d._buscar_navegador()`)."""
        tmp = tempfile.mkdtemp(prefix="abyss_render3d_")
        env = dict(os.environ)
        env["ABYSS_RENDER3D_NAVEGADOR"] = ""
        r = ay.ejecutar(ay.script("render3d.py"), [str(ESCENA_PRUEBA), "--html", os.path.join(tmp, "s.html"), "--png"],
                        env, timeout=30)
        self.assertEqual(r.returncode, 2)
        self.assertIn("sin dato: no hay navegador sin cabeza", r.stdout)
        # el HTML no depende del navegador: ya se ha escrito antes de intentar la captura
        self.assertTrue(os.path.exists(os.path.join(tmp, "s.html")))


@unittest.skipUnless(render3d._buscar_navegador(), "sin navegador sin cabeza en esta máquina")
class PngConNavegador(unittest.TestCase):
    def test_png_al_menos_10kb_con_las_dimensiones_pedidas(self):
        tmp = tempfile.mkdtemp(prefix="abyss_render3d_")
        ruta_html = os.path.join(tmp, "s.html")
        ruta_png = os.path.join(tmp, "s.png")
        antes = _perfiles_cdp()
        r = ay.ejecutar(ay.script("render3d.py"),
                        [str(ESCENA_PRUEBA), "--html", ruta_html, "--png", ruta_png, "--ancho", "800", "--alto", "500"],
                        dict(os.environ), timeout=60)
        nuevas = _perfiles_cdp() - antes
        self.assertFalse(nuevas, f"quedó un perfil temporal de navegador_cdp sin borrar: {nuevas}")
        self.assertEqual(r.returncode, 0, r.stderr)
        datos = _ultima_linea_json(r.stdout)
        self.assertEqual(datos["png"].replace("/", "\\"), os.path.abspath(ruta_png).replace("/", "\\"))
        tam = os.path.getsize(ruta_png)
        self.assertGreaterEqual(tam, 10_000, f"PNG de solo {tam} bytes: puede estar en blanco")
        self.assertEqual(_dimensiones_png(ruta_png), (800, 500))

    def test_vista_explosionada_separa_los_grupos(self):
        """Comprobado indirectamente por tamaño de PNG: si `--explosion` no cambiara el
        encuadre, el PNG comprimiría a un tamaño similar. Prueba de humo, no un examen
        de píxeles."""
        tmp = tempfile.mkdtemp(prefix="abyss_render3d_")
        pngs = {}
        antes = _perfiles_cdp()
        for explosion in ("0", "1.5"):
            ruta_png = os.path.join(tmp, f"e{explosion}.png")
            r = ay.ejecutar(ay.script("render3d.py"),
                            [str(ESCENA_PRUEBA), "--html", os.path.join(tmp, f"e{explosion}.html"),
                             "--png", ruta_png, "--explosion", explosion, "--ancho", "400", "--alto", "300"],
                            dict(os.environ), timeout=60)
            nuevas = _perfiles_cdp() - antes
            self.assertFalse(nuevas,
                              f"quedó un perfil temporal de navegador_cdp sin borrar tras --explosion {explosion}: {nuevas}")
            self.assertEqual(r.returncode, 0, r.stderr)
            pngs[explosion] = os.path.getsize(ruta_png)
        self.assertNotEqual(pngs["0"], pngs["1.5"], "la vista explosionada debería cambiar el fotograma capturado")


class FormatosDirectos(unittest.TestCase):
    """`cargar_entrada()`/`renderizar()` en proceso (sin `rutas`, seguro — ver docstring del
    módulo): un fixture sintético mínimo por formato."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="abyss_render3d_fmt_")

    def _ruta(self, nombre):
        return os.path.join(self.tmp, nombre)

    def test_stl_binario_una_sola_pieza_no_explosiona(self):
        ruta = self._ruta("una_malla.stl")
        tris = [((0, 0, 1), (0, 0, 0), (1, 0, 0), (0, 1, 0)),
                ((0, 0, 1), (1, 0, 0), (1, 1, 0), (0, 1, 0))]
        with open(ruta, "wb") as fh:
            fh.write(b" " * 80)
            fh.write(struct.pack("<I", len(tris)))
            for (n, v0, v1, v2) in tris:
                fh.write(struct.pack("<12fH", *n, *v0, *v1, *v2, 0))
        piezas, camara, unidades = render3d.cargar_entrada(ruta)
        self.assertEqual(len(piezas), 1, "un STL binario sin más metadatos es UNA sola malla")
        self.assertEqual(piezas[0]["tipo"], "malla")
        self.assertEqual(len(piezas[0]["vertices"]), 6)
        # el límite documentado ("un STL de una sola malla no se explosiona") sale solo de
        # que solo hay un grupo posible: nada de qué separarla.
        piezas[0].setdefault("grupo", piezas[0]["nombre"])
        self.assertEqual(len({p.get("grupo") or p["nombre"] for p in piezas}), 1)

    def test_stl_ascii_multisolid_una_pieza_por_solido(self):
        ruta = self._ruta("multi.stl")
        contenido = (
            "solid pieza_a\n"
            "facet normal 0 0 1\nouter loop\nvertex 0 0 0\nvertex 1 0 0\nvertex 0 1 0\nendloop\nendfacet\n"
            "endsolid pieza_a\n"
            "solid pieza_b\n"
            "facet normal 0 0 1\nouter loop\nvertex 2 0 0\nvertex 3 0 0\nvertex 2 1 0\nendloop\nendfacet\n"
            "endsolid pieza_b\n"
        )
        with open(ruta, "w", encoding="utf-8") as fh:
            fh.write(contenido)
        piezas, _, _ = render3d.cargar_entrada(ruta)
        self.assertEqual([p["nombre"] for p in piezas], ["pieza_a", "pieza_b"])
        self.assertEqual(len(piezas[0]["vertices"]), 3)

    def test_obj_grupos_y_triangulacion_en_abanico(self):
        ruta = self._ruta("cubos.obj")
        with open(ruta, "w", encoding="utf-8") as fh:
            fh.write(
                "o cuadrado\n"
                "v 0 0 0\nv 1 0 0\nv 1 1 0\nv 0 1 0\n"
                "f 1 2 3 4\n"  # cuadrilátero: 2 triángulos = 6 vértices no indexados
                "o triangulo\n"
                "v 2 0 0\nv 3 0 0\nv 3 1 0\n"
                "f 5 6 7\n"
            )
        piezas, _, _ = render3d.cargar_entrada(ruta)
        por_nombre = {p["nombre"]: p for p in piezas}
        self.assertEqual(len(por_nombre["cuadrado"]["vertices"]), 6)
        self.assertEqual(len(por_nombre["triangulo"]["vertices"]), 3)

    def test_obj_color_desde_mtl(self):
        ruta_mtl = self._ruta("mat.mtl")
        with open(ruta_mtl, "w", encoding="utf-8") as fh:
            fh.write("newmtl rojo\nKd 1.0 0.0 0.0\n")
        ruta_obj = self._ruta("con_color.obj")
        with open(ruta_obj, "w", encoding="utf-8") as fh:
            fh.write("mtllib mat.mtl\no pieza\nusemtl rojo\nv 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n")
        piezas, _, _ = render3d.cargar_entrada(ruta_obj)
        self.assertEqual(piezas[0]["color"], "#ff0000")

    def _fixture_gltf_glb(self):
        """(gltf_dict, glb_bytes) — un triángulo en un nodo trasladado [1,2,3], material
        rojo — usados por las dos pruebas de abajo (mismo contenido, dos envases)."""
        pos = struct.pack("<9f", 0, 0, 0, 1, 0, 0, 0, 1, 0)
        idx = struct.pack("<3H", 0, 1, 2)
        buf = pos + idx
        if len(buf) % 4:
            buf += b"\x00" * (4 - len(buf) % 4)
        gltf = {
            "asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": [0]}],
            "nodes": [{"name": "pieza1", "mesh": 0, "translation": [1, 2, 3]}],
            "meshes": [{"primitives": [{"attributes": {"POSITION": 0}, "indices": 1, "material": 0}]}],
            "materials": [{"pbrMetallicRoughness": {"baseColorFactor": [1, 0, 0, 1]}}],
            "accessors": [
                {"bufferView": 0, "componentType": 5126, "count": 3, "type": "VEC3"},
                {"bufferView": 1, "componentType": 5123, "count": 3, "type": "SCALAR"},
            ],
            "bufferViews": [
                {"buffer": 0, "byteOffset": 0, "byteLength": 36},
                {"buffer": 0, "byteOffset": 36, "byteLength": 6},
            ],
        }
        gltf_con_uri = dict(gltf, buffers=[{"byteLength": len(buf),
                            "uri": "data:application/octet-stream;base64," + base64.b64encode(buf).decode("ascii")}])
        gltf_sin_uri = dict(gltf, buffers=[{"byteLength": len(buf)}])
        j = json.dumps(gltf_sin_uri).encode("utf-8")
        if len(j) % 4:
            j += b" " * (4 - len(j) % 4)

        def chunk(ctype, data):
            return struct.pack("<II", len(data), ctype) + data

        cuerpo = chunk(0x4E4F534A, j) + chunk(0x004E4942, buf)
        glb = struct.pack("<III", 0x46546C67, 2, 12 + len(cuerpo)) + cuerpo
        return gltf_con_uri, glb

    def test_gltf_con_data_uri_transforma_por_el_nodo(self):
        gltf, _glb = self._fixture_gltf_glb()
        ruta = self._ruta("prueba.gltf")
        with open(ruta, "w", encoding="utf-8") as fh:
            json.dump(gltf, fh)
        piezas, _, _ = render3d.cargar_entrada(ruta)
        self.assertEqual(len(piezas), 1)
        self.assertEqual(piezas[0]["nombre"], "pieza1")
        self.assertEqual(piezas[0]["color"], "#ff0000")
        # posición local (0,0,0) trasladada [1,2,3] -> (1,2,3) en coordenadas del mundo
        self.assertEqual(piezas[0]["vertices"][0], (1.0, 2.0, 3.0))

    def test_glb_binario_mismo_resultado_que_gltf(self):
        _gltf, glb = self._fixture_gltf_glb()
        ruta = self._ruta("prueba.glb")
        with open(ruta, "wb") as fh:
            fh.write(glb)
        piezas, _, _ = render3d.cargar_entrada(ruta)
        self.assertEqual(piezas[0]["vertices"][0], (1.0, 2.0, 3.0))
        self.assertEqual(piezas[0]["color"], "#ff0000")

    def test_bbox_escena_cubre_primitivas_y_mallas(self):
        piezas = [
            {"tipo": "esfera", "pos": [0, 0, 0], "tam": [1.0], "nombre": "a"},
            {"tipo": "malla", "vertices": [(5.0, 0.0, 0.0)], "nombre": "b"},
        ]
        centro, radio = render3d._bbox_escena(piezas)
        self.assertGreaterEqual(radio, 2.5)  # de -1 (esfera) a 5 (vértice de malla): radio >= 3

    def test_renderizar_en_proceso_escribe_html_por_defecto_junto_a_la_entrada(self):
        ruta = self._ruta("directo.json")
        with open(ESCENA_PRUEBA, encoding="utf-8") as fh:
            contenido = fh.read()
        with open(ruta, "w", encoding="utf-8") as fh:
            fh.write(contenido)
        avisos = []
        r = render3d.renderizar(ruta, avisar=avisos.append)
        self.assertEqual(r["html"], self._ruta("directo_render3d.html"))
        self.assertTrue(os.path.exists(r["html"]))
        self.assertTrue(any("html:" in a for a in avisos))


class DocumentacionFrenteACodigo(unittest.TestCase):
    """Dos claims del docstring/LICENSE que no coincidían con el código: (1) el aviso de
    obsolescencia de three.js no se borra, solo pierde el esquema de sus URLs; (2)
    `document.title` no es señal de nada — la captura decide por peso, y el primer fotograma se pinta antes de animar."""

    def test_aviso_three_no_se_borra_solo_pierde_esquema_de_sus_urls(self):
        crudo = render3d._leer_vendor("three.min.js")
        # las 3 cadenas http distintas que trae el vendor tal cual se descargó:
        # threejs.org (aviso de obsolescencia), discourse.threejs.org (aviso de color,
        # repetido dos veces) y el namespace XHTML.
        self.assertIn("https://threejs.org", crudo)
        self.assertIn("https://discourse.threejs.org", crudo)
        self.assertIn("http://www.w3.org/1999/xhtml", crudo)
        self.assertIn("are deprecated", crudo, "el aviso de obsolescencia debe seguir en el vendor")

        incrustado = render3d._texto_three_embebido()
        # el aviso NO se borra: sigue el texto del console.warn, solo sin el esquema de sus URLs.
        self.assertIn("are deprecated", incrustado, "_texto_three_embebido() no debe borrar líneas")
        self.assertNotIn("https://threejs.org", incrustado)
        self.assertNotIn("https://discourse.threejs.org", incrustado)
        self.assertIn("threejs.org", incrustado)
        self.assertIn("discourse.threejs.org", incrustado)
        # la única http:// que debe sobrevivir es el namespace XHTML (no se toca: es un
        # identificador de createElementNS, nunca una URL que se descargue).
        self.assertIn("http://www.w3.org/1999/xhtml", incrustado)
        restantes = re.findall(r"https?://[^\s\"'\\]*", incrustado)
        self.assertEqual(set(restantes), {"http://www.w3.org/1999/xhtml"},
                          "no debe quedar ninguna URL con esquema salvo el namespace XHTML")

    def test_captura_no_depende_de_una_senal_sin_lector(self):
        fuente_main = render3d._MAIN_JS
        self.assertNotIn("document.title", fuente_main,
                          "no debe quedar una señal declarada que ningún camino del código lee")
        # el primer fotograma se pinta antes de arrancar el bucle rAF (síncrono de verdad).
        pos_primer_render = fuente_main.index("renderer.render(escena3d, camera);")
        pos_animar = fuente_main.index("function animar()")
        self.assertLess(pos_primer_render, pos_animar)
        # _capturar_png decide solo por el peso del PNG (UMBRAL_PNG_OK), nunca por título.
        fuente_captura = inspect.getsource(render3d._capturar_png)
        self.assertIn("UMBRAL_PNG_OK", fuente_captura)
        self.assertNotIn("title", fuente_captura)


if __name__ == "__main__":
    unittest.main()
