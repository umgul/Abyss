"""`video_composicion.py` (hermano de `video_pintura.py` para las composiciones de
`lienzo.py` que no son pinceladas: `cubista`/`surrealista`). Mismo patrón que
`test_imagen_video.py`: se salta si falta `imageio_ffmpeg` (dependencia opcional).
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'abyss'))

try:
    from PIL import Image
except ImportError:
    Image = None

try:
    import imageio_ffmpeg
    _FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()
    FFMPEG_DISPONIBLE = bool(_FFMPEG_EXE)
    _MOTIVO_SIN_FFMPEG = ''
except Exception as e:
    FFMPEG_DISPONIBLE = False
    _MOTIVO_SIN_FFMPEG = f'falta imageio_ffmpeg (requirements.txt: opcional para vídeo) — {type(e).__name__}: {e}'

import video_composicion as vc


def _pasos_sinteticos(d, n=5, ancho=64, alto=48):
    """`n` fotogramas PNG numerados como los que escribe `lienzo._escribir_pasos` — un
    degradado que crece de paso en paso, para poder distinguir uno de otro a simple
    vista si hiciera falta depurar."""
    rutas = []
    for k in range(n):
        img = Image.new('RGB', (ancho, alto), (20 + k * 20, 40, 60))
        ruta = os.path.join(d, f'paso_{k:03d}.png')
        img.save(ruta)
        rutas.append(ruta)
    return rutas


@unittest.skipUnless(Image is not None, 'Pillow no disponible: hace falta para fabricar los pasos de prueba')
class VideoDePasos(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix='abyss_video_composicion_')

    def test_sin_pasos_en_el_directorio_da_runtimeerror_claro(self):
        vacio = os.path.join(self.d, 'vacio')
        os.makedirs(vacio)
        with self.assertRaises(RuntimeError) as ctx:
            vc.video(vacio, os.path.join(self.d, 's.mp4'), avisar=lambda *a: None)
        self.assertIn('sin pasos', str(ctx.exception))

    def test_pasos_de_tamano_distinto_da_runtimeerror_claro(self):
        distintos = os.path.join(self.d, 'distintos')
        os.makedirs(distintos)
        Image.new('RGB', (64, 48)).save(os.path.join(distintos, 'paso_000.png'))
        Image.new('RGB', (80, 60)).save(os.path.join(distintos, 'paso_001.png'))
        with self.assertRaises(RuntimeError) as ctx:
            vc.video(distintos, os.path.join(self.d, 's.mp4'), avisar=lambda *a: None)
        self.assertIn('deben medir igual', str(ctx.exception))

    @unittest.skipUnless(FFMPEG_DISPONIBLE, _MOTIVO_SIN_FFMPEG or 'falta imageio_ffmpeg')
    def test_video_de_verdad_pesa_mas_de_1000_bytes_y_dura_lo_esperado(self):
        pasos_dir = os.path.join(self.d, 'pasos')
        os.makedirs(pasos_dir)
        n = 5
        _pasos_sinteticos(pasos_dir, n=n)
        salida = os.path.join(self.d, 'proceso.mp4')

        r = vc.video(pasos_dir, salida, segundos=2.0, fps=30, hold_ini=0.4, hold_fin=0.6,
                     avisar=lambda *a: None)

        self.assertEqual(r['pasos'], n)
        self.assertTrue(os.path.exists(salida))
        self.assertGreater(os.path.getsize(salida), 1000, 'el .mp4 debe pesar más de 1000 bytes')
        # frames = hold_ini + n pasos repartidos + hold_fin, la MISMA cuenta que hace
        # video() por dentro — aquí se repite el cálculo para falsar que el .mp4 real
        # (leído por su tamaño/frames devueltos, no solo "no reventó") tiene la
        # duración que promete el docstring, no una cifra cualquiera.
        fps = 30
        nf_paso = max(1, round(2.0 * fps / n))
        esperado = int(0.4 * fps) + n * nf_paso + int(0.6 * fps)
        self.assertEqual(r['frames'], esperado)
        self.assertAlmostEqual(r['duracion'], round(esperado / fps, 2), places=2)

    @unittest.skipUnless(FFMPEG_DISPONIBLE, _MOTIVO_SIN_FFMPEG or 'falta imageio_ffmpeg')
    def test_ancho_pedido_reescala_el_video(self):
        pasos_dir = os.path.join(self.d, 'pasos2')
        os.makedirs(pasos_dir)
        _pasos_sinteticos(pasos_dir, n=3, ancho=100, alto=50)
        salida = os.path.join(self.d, 'proceso2.mp4')
        r = vc.video(pasos_dir, salida, segundos=1.0, ancho=200, avisar=lambda *a: None)
        self.assertEqual(r['W'], 200)
        self.assertEqual(r['H'], 100)


if __name__ == '__main__':
    unittest.main()
