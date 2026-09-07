"""`imagen.py video` (ESPECIFICACION.md §6, tarea B item 1b): un vídeo corto codificado
desde el `.json.gz` que deja `pintor.pintar()`. Todo en local (sin red). Si falta
`imageio_ffmpeg` (dependencia OPCIONAL, requirements.txt), la prueba se salta con el
motivo en vez de fallar.
"""
import sys
import os
import tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import unittest
import ayudas as ay

sys.path.insert(0, str(ay.PKG))

try:
    from PIL import Image
    import pintor
except ImportError:
    Image = None
    pintor = None

try:
    import imageio_ffmpeg
    _FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()
    FFMPEG_DISPONIBLE = bool(_FFMPEG_EXE)
    _MOTIVO_SIN_FFMPEG = ''
except Exception as e:
    FFMPEG_DISPONIBLE = False
    _MOTIVO_SIN_FFMPEG = f'falta imageio_ffmpeg (requirements.txt: opcional para vídeo) — {type(e).__name__}: {e}'


@unittest.skipUnless(pintor is not None, 'Pillow/numpy no disponibles (requirements.txt): hacen falta para fabricar los trazos de prueba')
class ImagenVideo(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix='abyss_video_')
        img = Image.new('RGB', (60, 40))
        px = img.load()
        for y in range(40):
            for x in range(60):
                px[x, y] = ((x * 4) % 256, (y * 6) % 256, ((x + y) * 5) % 256)
        foto = os.path.join(self.d, 'foto.png')
        img.save(foto)
        # trazos rápidos de fabricar: imagen chica, sin --alta ni --acabado
        r = pintor.pintar(foto, salida=self.d, ancho=60, semilla=3, avisar=lambda *a: None)
        self.trazos = r['trazos']

    @unittest.skipUnless(FFMPEG_DISPONIBLE, _MOTIVO_SIN_FFMPEG or 'falta imageio_ffmpeg')
    def test_video_de_un_segundo_a_160px_existe_y_pesa_mas_de_1000_bytes(self):
        proj = ay.nuevo_proyecto()
        salida = os.path.join(self.d, 'salida.mp4')
        env = ay.entorno(proj)

        r = ay.ejecutar(ay.script('imagen.py'),
                         ['video', self.trazos, salida, '--segundos', '1', '--ancho', '160'],
                         env, timeout=90)

        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(os.path.exists(salida), 'debe existir el .mp4')
        self.assertGreater(os.path.getsize(salida), 1000, 'el .mp4 debe pesar más de 1000 bytes')


if __name__ == '__main__':
    unittest.main()
