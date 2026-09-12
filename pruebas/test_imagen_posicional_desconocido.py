"""`imagen.py crear` rechaza con código 1 y mensaje claro cualquier argumento que no
reconoce tras `salida` (positional de más, bandera desconocida, bandera sin valor o
seguida de otra bandera, valor no numérico; ESPECIFICACION.md §3): sin mock de servidor, el fallo se detecta en el parseo, antes de tocar `crear()`."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import unittest
import ayudas as ay


class ImagenCrearRechazaArgumentosSinReconocer(unittest.TestCase):
    def test_tres_posicionales_de_mas_no_se_tragan_en_silencio(self):
        proj = ay.nuevo_proyecto()
        env = ay.entorno(proj)

        # salida + tres posicionales de más (ancho, alto, semilla sin bandera) además de --via
        r = ay.ejecutar(ay.script('imagen.py'),
                         ['crear', 'un gato', 'g1.png', '512', '384', '7', '--via', 'local'],
                         env, timeout=15)

        self.assertEqual(r.returncode, 1, f'stdout={r.stdout!r} stderr={r.stderr!r}')
        self.assertIn('no reconocido', r.stdout)
        self.assertIn('512', r.stdout, 'el mensaje debe nombrar el argumento que no entendió')
        self.assertFalse((proj / 'memory' / 'imagenes').exists(),
                          'no debe llegar ni a intentar generar nada (nunca llama a crear())')

    def test_bandera_conocida_sin_valor_detras_no_se_traga(self):
        proj = ay.nuevo_proyecto()
        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('imagen.py'), ['crear', 'un gato', '--ancho'], env, timeout=15)
        self.assertEqual(r.returncode, 1, f'stdout={r.stdout!r} stderr={r.stderr!r}')
        self.assertIn('no reconocido', r.stdout)

    def test_bandera_desconocida_no_se_traga(self):
        proj = ay.nuevo_proyecto()
        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('imagen.py'), ['crear', 'un gato', '--altura', '512'], env, timeout=15)
        self.assertEqual(r.returncode, 1, f'stdout={r.stdout!r} stderr={r.stderr!r}')
        self.assertIn('no reconocido', r.stdout)

    def test_bandera_conocida_seguida_de_otra_bandera_no_revienta(self):
        proj = ay.nuevo_proyecto()
        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('imagen.py'), ['crear', 'un gato', '--ancho', '--via', 'local'], env, timeout=15)
        self.assertEqual(r.returncode, 1, f'stdout={r.stdout!r} stderr={r.stderr!r}')
        self.assertNotIn('Traceback', r.stderr, 'nunca una traza cruda, siempre un mensaje claro')

    def test_bandera_conocida_con_valor_no_numerico_no_revienta(self):
        proj = ay.nuevo_proyecto()
        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('imagen.py'), ['crear', 'un gato', '--ancho', 'abc'], env, timeout=15)
        self.assertEqual(r.returncode, 1, f'stdout={r.stdout!r} stderr={r.stderr!r}')
        self.assertNotIn('Traceback', r.stderr)
        self.assertIn('abc', r.stdout, 'el mensaje debe nombrar el valor que no entendió')

    def test_dos_banderas_numericas_seguidas_sin_valor_no_revienta(self):
        proj = ay.nuevo_proyecto()
        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('imagen.py'), ['crear', 'un gato', '--semilla', '--alto', '512'], env, timeout=15)
        self.assertEqual(r.returncode, 1, f'stdout={r.stdout!r} stderr={r.stderr!r}')
        self.assertNotIn('Traceback', r.stderr)


class OjoIndiceCamaraNoNumericoNoRevienta(unittest.TestCase):
    def test_indice_no_numerico_da_mensaje_claro_y_codigo_1(self):
        # ojo.py despacha por verbo: hay que anteponer "mirar" o el primer
        # positional se lee como verbo y sale "verbo desconocido".
        proj = ay.nuevo_proyecto()
        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('ojo.py'), ['mirar', 'foto.jpg', 'noesunnumero'], env, timeout=15)
        self.assertEqual(r.returncode, 1, f'stdout={r.stdout!r} stderr={r.stderr!r}')
        self.assertNotIn('Traceback', r.stderr)
        self.assertIn('noesunnumero', r.stdout, 'el mensaje debe nombrar el valor que no entendió')


if __name__ == '__main__':
    unittest.main()
