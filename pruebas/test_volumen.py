"""`volumen.py` (ESPECIFICACION_TANDA4.md, T4.4): despiece por capas (2,5D, GrabCut +
nitidez/luminancia) y `prompt3d` (paleta k-medias, proporciones, horizonte, formas por
circularidad de contorno). `volumen.py` no llama a `rutas.resolver()` (guion de fichero a
fichero, como `render3d.py`/`pintor.py`, ver su propio docstring) — se puede importar
DIRECTAMENTE en el proceso de la prueba, igual que `test_render3d.py` importa `render3d`.

Las imágenes son sintéticas y GEOMÉTRICAS a propósito (formas de color plano dibujadas con
`cv2`): así se sabe de antemano qué debería separar GrabCut y qué círculo/rectángulo/óvalo
debería salir de la clasificación por circularidad — nada de esto se afirma "reconocido",
se afirma "medido de ESTA imagen concreta, construida para dar ese resultado".

`opencv-python`/`numpy` SÍ están instalados en la máquina de desarrollo (medido en
ESPECIFICACION_TANDA4.md): las pruebas de "sin dependencia" bloquean `cv2` con un
`sitecustomize.py` propio por `PYTHONPATH` (mismo método que
`test_imagen_dependencias_opcionales.py`) en vez de desinstalar nada de verdad.
"""
import sys
import os
import json
import tempfile
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ayudas as ay

sys.path.insert(0, str(ay.PKG))

try:
    import cv2
    import numpy as np
    import volumen
    import render3d  # sin rutas.resolver(): seguro importarlo aquí, ver docstring de ambos módulos
except ImportError:
    cv2 = None
    np = None
    volumen = None
    render3d = None


def _tres_formas(ruta):
    """Fondo oscuro plano + un círculo (más luminoso) y un rectángulo (más luminoso aún,
    y más nítido en el borde): pensada para que GrabCut separe las dos formas del fondo y
    para que `formas_dominantes()` las clasifique como "esfera" y "rectangulo"."""
    img = np.full((300, 400, 3), (20, 20, 20), np.uint8)
    cv2.circle(img, (140, 150), 70, (60, 60, 60), -1)
    cv2.rectangle(img, (240, 90), (360, 210), (200, 200, 200), -1)
    cv2.imwrite(str(ruta), img)
    return ruta


def _triangulo(ruta):
    """Un triángulo: ni "esfera" (circularidad baja) ni "rectangulo" (3 vértices, no 4-6)
    ni "cilindro" (razón de aspecto <1,6) — tiene que salir "irregular"."""
    img = np.full((200, 200, 3), (20, 20, 20), np.uint8)
    pts = np.array([[100, 40], [40, 160], [160, 160]], np.int32)
    cv2.fillPoly(img, [pts], (150, 150, 150))
    cv2.imwrite(str(ruta), img)
    return ruta


def _imagen_uniforme(ruta):
    img = np.full((120, 160, 3), (90, 90, 90), np.uint8)
    cv2.imwrite(str(ruta), img)
    return ruta


def _sitecustomize_bloqueando(nombres):
    d = Path(tempfile.mkdtemp(prefix='abyss_bloqueo_volumen_'))
    lista_py = ', '.join(repr(n) for n in nombres)
    (d / 'sitecustomize.py').write_text(textwrap.dedent(f'''
        import sys
        import importlib.abc

        class _Bloqueador(importlib.abc.MetaPathFinder):
            BLOQUEADOS = {{{lista_py}}}

            def find_spec(self, name, path, target=None):
                raiz = name.split(".")[0]
                if raiz in self.BLOQUEADOS:
                    raise ModuleNotFoundError(
                        "{{}} bloqueado por la prueba (sitecustomize)".format(raiz), name=raiz)
                return None

        sys.meta_path.insert(0, _Bloqueador())
    '''), encoding='utf-8')
    return d


def _ultima_linea_json(stdout):
    return json.loads([l for l in stdout.splitlines() if l.strip()][-1])


@unittest.skipUnless(cv2 is not None, 'opencv-python no disponible en esta máquina')
class VolumenSinOpenCV(unittest.TestCase):
    def test_mensaje_claro_codigo_2_sin_traceback(self):
        proj = ay.nuevo_proyecto()
        img = proj / 'foto.png'
        _imagen_uniforme(img)
        bloqueo = _sitecustomize_bloqueando(['cv2'])
        env = ay.entorno(proj)
        env['PYTHONPATH'] = str(bloqueo) + os.pathsep + env.get('PYTHONPATH', '')

        r = ay.ejecutar(ay.script('volumen.py'), ['despiece', str(img)], env)

        self.assertEqual(r.returncode, 2, f'stdout={r.stdout!r} stderr={r.stderr!r}')
        self.assertIn('pip install opencv-python', r.stdout)
        self.assertIn('numpy', r.stdout)
        self.assertNotIn('Traceback', r.stdout)
        self.assertNotIn('Traceback', r.stderr)


@unittest.skipUnless(cv2 is not None, 'opencv-python no disponible en esta máquina')
class MascaraPrimerPlano(unittest.TestCase):
    def test_grabcut_separa_las_dos_formas_del_fondo(self):
        img = cv2.imread(str(_tres_formas(Path(tempfile.mktemp(suffix='.png')))), cv2.IMREAD_COLOR)
        fg = volumen.mascara_primer_plano(img)
        # círculo (pi*70^2≈15394) + rectángulo (120*120=14400) ≈ 29794, con margen por el trazado
        self.assertGreater(int(fg.sum()), 25000)
        self.assertLess(int(fg.sum()), 35000)

    def test_sin_contraste_avisa_y_usa_el_recuadro_central(self):
        img = cv2.imread(str(_imagen_uniforme(Path(tempfile.mktemp(suffix='.png')))), cv2.IMREAD_COLOR)
        avisos = []
        fg = volumen.mascara_primer_plano(img, avisar=avisos.append)
        self.assertTrue(any('GrabCut no separó nada' in a for a in avisos), avisos)
        self.assertGreater(int(fg.sum()), 0, 'el fallback debe dejar ALGO como primer plano')


@unittest.skipUnless(cv2 is not None, 'opencv-python no disponible en esta máquina')
class Despiece(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='abyss_despiece_'))
        self.foto = _tres_formas(self.tmp / 'foto.png')

    def test_escena_valida_y_abrible_por_render3d(self):
        ruta_escena = self.tmp / 'escena.json'
        r = volumen.despiece(str(self.foto), capas=4, salida=str(ruta_escena), avisar=lambda *a: None)

        self.assertEqual(r['escena'], str(ruta_escena))
        self.assertEqual(r['capas_pedidas'], 4)
        self.assertGreaterEqual(r['capas_efectivas'], 2)  # al menos una capa de objeto + el fondo
        self.assertLessEqual(r['capas_efectivas'], 4)
        self.assertEqual(len(r['capas_png']), r['capas_efectivas'])
        for p in r['capas_png']:
            self.assertTrue(os.path.isfile(p), p)
            recorte = cv2.imread(p, cv2.IMREAD_UNCHANGED)
            self.assertEqual(recorte.shape[2], 4, 'cada capa debe llevar canal alfa')
            self.assertGreater(int((recorte[:, :, 3] > 0).sum()), 0, 'alguna parte debe ser opaca')

        datos = json.loads(ruta_escena.read_text(encoding='utf-8'))
        self.assertEqual(datos['despiece']['tipo'], '2.5D')
        self.assertEqual(datos['despiece']['capas_efectivas'], len(datos['piezas']))
        self.assertEqual(len(datos['piezas']), r['capas_efectivas'])
        for p in datos['piezas']:
            self.assertEqual(p['tipo'], 'plano')
            self.assertIn('capa_png', p)
            self.assertEqual(len(p['pos']), 3)
            self.assertEqual(len(p['tam']), 2)

        # capa 0 = más cerca = mayor z; la última capa (fondo) = z 0 (§docstring del módulo)
        piezas_por_grupo = {p['grupo']: p for p in datos['piezas']}
        zetas = [piezas_por_grupo[f'capa_{i}']['pos'][2] for i in sorted(
            int(g.split('_')[1]) for g in piezas_por_grupo)]
        self.assertEqual(zetas, sorted(zetas, reverse=True), 'la profundidad debe ser monótona por índice de capa')
        self.assertAlmostEqual(min(zetas), 0.0, places=5, msg='la capa de fondo debe quedar en z=0')

        # render3d.py YA sabe abrir esta escena.json, con su deslizador de explosión
        piezas_cargadas, camara, unidades = render3d.cargar_entrada(str(ruta_escena))
        self.assertEqual(len(piezas_cargadas), r['capas_efectivas'])
        self.assertEqual(unidades, 'm')

    def test_capa_vacia_no_se_inventa(self):
        # --capas muy alto sobre una imagen de solo 2 formas: alguna capa se queda sin
        # ningún píxel, y el resultado lo dice en vez de escribir una pieza vacía.
        r = volumen.despiece(str(self.foto), capas=8, salida=str(self.tmp / 'e8.json'), avisar=lambda *a: None)
        self.assertLess(r['capas_efectivas'], 8)
        self.assertGreater(r['capas_efectivas'], 0)

    def test_html_lleva_el_aviso_2_5d_y_no_rompe_el_render_normal(self):
        r = volumen.despiece(str(self.foto), capas=3, salida=str(self.tmp / 'e.json'), html=True, avisar=lambda *a: None)
        self.assertIn('html', r)
        html = Path(r['html']).read_text(encoding='utf-8')
        self.assertIn('avisoDespiece', html)
        self.assertIn('2,5D', html)
        self.assertIn('NO es una reconstrucción 3D', html)
        # y sigue siendo una página de render3d.py normal y corriente (three.js embebido)
        self.assertIn('THREE.WebGLRenderer', html)

    def test_cli_capas_y_salida(self):
        ruta_escena = self.tmp / 'cli_escena.json'
        r = ay.ejecutar(ay.script('volumen.py'),
                         ['despiece', str(self.foto), '--capas', '3', '--salida', str(ruta_escena)],
                         ay.entorno(self.tmp))
        self.assertEqual(r.returncode, 0, f'stdout={r.stdout!r} stderr={r.stderr!r}')
        datos = _ultima_linea_json(r.stdout)
        self.assertEqual(datos['capas_pedidas'], 3)
        self.assertTrue(ruta_escena.is_file())

    def test_imagen_inexistente_sin_dato_codigo_2(self):
        r = ay.ejecutar(ay.script('volumen.py'), ['despiece', str(self.tmp / 'no_existe.png')], ay.entorno(self.tmp))
        self.assertEqual(r.returncode, 2)
        self.assertIn('sin dato', r.stdout)
        self.assertNotIn('Traceback', r.stdout)


@unittest.skipUnless(cv2 is not None, 'opencv-python no disponible en esta máquina')
class PaletaDominante(unittest.TestCase):
    def test_tres_colores_planos_sin_duplicados(self):
        img = cv2.imread(str(_tres_formas(Path(tempfile.mktemp(suffix='.png')))), cv2.IMREAD_COLOR)
        paleta = volumen.paleta_dominante(img, k=5)
        self.assertEqual(len(paleta), 3, paleta)  # 3 colores reales, aunque se pidan 5 grupos
        self.assertAlmostEqual(sum(p['proporcion'] for p in paleta), 1.0, places=2)
        # el fondo (más grande con diferencia) debe ser el primero, de mayor a menor
        self.assertGreater(paleta[0]['proporcion'], paleta[1]['proporcion'])
        self.assertGreater(paleta[1]['proporcion'], paleta[2]['proporcion'])


@unittest.skipUnless(cv2 is not None, 'opencv-python no disponible en esta máquina')
class FormasDominantes(unittest.TestCase):
    def test_circulo_y_rectangulo_clasificados_por_circularidad(self):
        img = cv2.imread(str(_tres_formas(Path(tempfile.mktemp(suffix='.png')))), cv2.IMREAD_COLOR)
        formas = volumen.formas_dominantes(img)
        self.assertEqual({f['forma'] for f in formas}, {'esfera', 'rectangulo'})
        esfera = next(f for f in formas if f['forma'] == 'esfera')
        rect = next(f for f in formas if f['forma'] == 'rectangulo')
        self.assertGreaterEqual(esfera['circularidad'], 0.85)
        self.assertLess(rect['circularidad'], 0.85)
        self.assertTrue(4 <= rect['vertices'] <= 6, rect)

    def test_triangulo_no_se_fuerza_a_encajar(self):
        img = cv2.imread(str(_triangulo(Path(tempfile.mktemp(suffix='.png')))), cv2.IMREAD_COLOR)
        formas = volumen.formas_dominantes(img)
        self.assertEqual(len(formas), 1)
        self.assertEqual(formas[0]['forma'], 'irregular')

    def test_sin_contorno_grande_lista_vacia(self):
        # Con un primer plano vacío A PROPÓSITO (bypass del fallback de `mascara_primer_plano`,
        # que sobre una imagen uniforme SÍ marca el recuadro central entero como objeto — eso
        # se prueba aparte en `MascaraPrimerPlano`): cae al camino "bordes Canny de toda la
        # foto", y una foto de un único color no tiene ningún borde que encontrar.
        img = cv2.imread(str(_imagen_uniforme(Path(tempfile.mktemp(suffix='.png')))), cv2.IMREAD_COLOR)
        fg_vacia = np.zeros(img.shape[:2], dtype=bool)
        self.assertEqual(volumen.formas_dominantes(img, fg=fg_vacia), [])


@unittest.skipUnless(cv2 is not None, 'opencv-python no disponible en esta máquina')
class Horizonte(unittest.TestCase):
    def test_sin_linea_clara_da_sin_dato(self):
        img = cv2.imread(str(_tres_formas(Path(tempfile.mktemp(suffix='.png')))), cv2.IMREAD_COLOR)
        self.assertIsNone(volumen.horizonte(img))

    def test_linea_horizontal_clara_da_fraccion_de_altura(self):
        img = np.full((200, 400, 3), (30, 30, 30), np.uint8)
        cv2.rectangle(img, (0, 0), (399, 119), (180, 180, 180), -1)  # borde recto en y=120
        frac = volumen.horizonte(img)
        self.assertIsNotNone(frac)
        self.assertAlmostEqual(frac, 120 / 200, delta=0.05)


@unittest.skipUnless(cv2 is not None, 'opencv-python no disponible en esta máquina')
class Prompt3d(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='abyss_prompt3d_'))
        self.foto = _tres_formas(self.tmp / 'foto.png')

    def test_texto_y_escena_de_formas(self):
        ruta_txt = self.tmp / 'p.txt'
        ruta_escena = self.tmp / 'e.json'
        r = volumen.prompt3d(str(self.foto), salida=str(ruta_txt), escena=str(ruta_escena), avisar=lambda *a: None)

        texto = ruta_txt.read_text(encoding='utf-8')
        self.assertIn('ES:', texto)
        self.assertIn('EN:', texto)
        self.assertIn(r['paleta'][0]['hex'], texto)
        self.assertNotIn('sin_escena', r)

        datos = json.loads(ruta_escena.read_text(encoding='utf-8'))
        tipos = sorted(p['tipo'] for p in datos['piezas'])
        self.assertEqual(tipos, ['caja', 'esfera'])  # rectángulo->caja, esfera->esfera (§docstring)

    def test_sin_forma_clasificable_no_escribe_escena_falsa(self):
        foto = _triangulo(self.tmp / 'tri.png')
        r = volumen.prompt3d(str(foto), salida=str(self.tmp / 'p2.txt'), escena=str(self.tmp / 'e2.json'), avisar=lambda *a: None)
        self.assertIn('sin_escena', r)
        self.assertNotIn('escena', r)
        self.assertFalse((self.tmp / 'e2.json').exists())

    def test_cli_prompt3d(self):
        r = ay.ejecutar(ay.script('volumen.py'),
                         ['prompt3d', str(self.foto), '--salida', str(self.tmp / 'cli.txt')],
                         ay.entorno(self.tmp))
        self.assertEqual(r.returncode, 0, f'stdout={r.stdout!r} stderr={r.stderr!r}')
        datos = _ultima_linea_json(r.stdout)
        self.assertIn('paleta', datos)
        self.assertTrue((self.tmp / 'cli.txt').is_file())


if __name__ == '__main__':
    unittest.main()
