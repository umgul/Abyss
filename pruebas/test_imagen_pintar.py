"""`imagen.py pintar` (ESPECIFICACION.md §3 y §6), adaptado al `imagen.py`/`pintor.py`
de 6-sep (cascada de proveedores para `crear`; `pintar` sigue siendo 100% local y
delega en `pintor._cli`). Se prueba el verbo completo por subprocess (igual que se
invocaría a mano), para cubrir también `rutas.resolver()`, `mem/imagenes/`... aunque
`pintar` en concreto escribe junto a la foto por defecto, no bajo `mem/` (ver
`pintor.pintar()`: `salida = dirname(ruta)` si no se pide otra).

Las comparaciones de `--acabado`/`--suave` (más pinceladas sin subir error; mismo
tamaño de PNG) están en `test_pintor_acabado_suave.py`, importando `pintor` en
proceso (no toca `rutas`, es más rápido y no depende de cómo lo invoque `imagen.py`).
El vídeo está en `test_imagen_video.py`; `crear`/`vias` en `test_imagen_crear_vias.py`.
"""
import sys
import os
import gzip
import json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import unittest
import ayudas as ay

try:
    from PIL import Image
except ImportError:
    Image = None


def _foto_sintetica(ruta, ancho=200, alto=150):
    img = Image.new('RGB', (ancho, alto))
    px = img.load()
    for y in range(alto):
        for x in range(ancho):
            px[x, y] = ((x * 3) % 256, (y * 5) % 256, ((x + y * 2) * 7) % 256)
    img.save(ruta)
    return ruta


def _ultima_linea_json(stdout):
    return json.loads([l for l in stdout.splitlines() if l.strip()][-1])


@unittest.skipUnless(Image is not None, 'Pillow no disponible (requirements.txt): pintor.py lo declara opcional')
class ImagenPintarCLI(unittest.TestCase):
    def test_pintar_produce_png_y_json_gz_con_html(self):
        proj = ay.nuevo_proyecto()
        foto = _foto_sintetica(proj / 'foto_sintetica.png')
        env = ay.entorno(proj)

        r = ay.ejecutar(ay.script('imagen.py'),
                         ['pintar', str(foto), '--ancho', '200', '--html'], env, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)

        datos = _ultima_linea_json(r.stdout)
        for clave in ('png', 'trazos', 'html', 'pinceladas', 'error_medio', 'W', 'H'):
            self.assertIn(clave, datos)
        self.assertEqual((datos['W'], datos['H']), (200, 150))

        with open(datos['png'], 'rb') as fh:
            self.assertEqual(fh.read(8), b'\x89PNG\r\n\x1a\n',
                              'debe ser un PNG válido de verdad, no solo un fichero con esa extensión')

        with gzip.open(datos['trazos'], 'rt', encoding='utf-8') as fh:
            estructura = json.load(fh)
        self.assertEqual(set(estructura.keys()), {'W', 'H', 'radios', 'trazos'})
        self.assertGreater(len(estructura['trazos']), 0)
        # cada trazo es [radio, "#rrggbb", [x0,y0,x1,y1,...]] (pintor.py, docstring)
        radio0, color0, puntos0 = estructura['trazos'][0]
        self.assertIsInstance(radio0, int)
        self.assertRegex(color0, r'^#[0-9a-f]{6}$')
        self.assertGreaterEqual(len(puntos0), 2)

        self.assertTrue(datos['html'] and os.path.exists(datos['html']), 'con --html debe escribir la página')
        with open(datos['html'], encoding='utf-8') as fh:
            self.assertIn('<canvas', fh.read())

    def test_pintar_sin_html_no_escribe_pagina(self):
        proj = ay.nuevo_proyecto()
        foto = _foto_sintetica(proj / 'foto_sintetica.png')
        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('imagen.py'), ['pintar', str(foto), '--ancho', '48'], env, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIsNone(_ultima_linea_json(r.stdout)['html'])

    def test_foto_inexistente_no_revienta(self):
        proj = ay.nuevo_proyecto()
        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('imagen.py'), ['pintar', str(proj / 'no_existe.png')], env)
        self.assertEqual(r.returncode, 2)
        self.assertIn('sin cuadro', r.stdout)
        self.assertFalse(list(proj.glob('*_pintada.png')))

    def test_proyecto_no_acaba_como_fichero_de_salida(self):
        """El valor de `--proyecto` no debe colarse como ruta de salida de `pintar`."""
        proj = ay.nuevo_proyecto()
        home_falso = ay.nuevo_proyecto()
        foto = _foto_sintetica(proj / 'foto_sintetica.png')
        marcador = 'marcador-de-proyecto-de-prueba'
        env = ay.entorno(proj)
        env.pop('ABYSS_PROYECTO', None)  # fuerza la resolución por --proyecto (orden 3 de rutas.resolver)
        env['HOME'] = env['USERPROFILE'] = str(home_falso)  # el proyecto marcador nace bajo un HOME desechable

        r = ay.ejecutar(ay.script('imagen.py'),
                         ['pintar', str(foto), '--ancho', '40', '--proyecto', marcador],
                         env, cwd=str(proj), timeout=60)

        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse((proj / marcador).exists(),
                          '--proyecto no debe acabar convertido en ruta/carpeta de salida')
        self.assertTrue((proj / 'foto_sintetica_pintada.png').exists(),
                         'con la bandera bien retirada, el cuadro sale junto a la foto (por defecto)')


if __name__ == '__main__':
    unittest.main()
