"""`imagen.py crear`: positional desconocido tras `salida` (ESPECIFICACION.md §3,
fallo 6-sep "engaña"). MEDIDO contra un servidor A1111 falso (ver
`test_imagen_crear_vias.py`): `imagen.py crear "gato" g1.png 512 384 7 --via
local` mandaba al servidor `{"width": 1024, "height": 1024, "seed": null}` — los
tres posicionales de más (ancho, alto, semilla tecleados sin bandera, la firma
vieja que la propia especificación seguía documentando) se descartaban en
silencio y `crear` seguía con sus valores por defecto, sin avisar ni salir con
error.

Ahora cualquier argumento que no encaje (un segundo/tercer/cuarto posicional
después de fijar `salida`, una bandera desconocida, o una bandera conocida sin su
valor detrás) hace que `_cli` salga con código 1 y un mensaje claro ANTES de tocar
`crear()` — por eso estas pruebas no necesitan mock de servidor ni red: el fallo
se detecta en el parseo de argumentos, antes de intentar generar nada.

SEGUNDA VUELTA (revisor Opus, fallo "roza" 6-sep): la guarda `i + 1 < len(resto)`
solo cubría el caso en que la bandera conocida era el ÚLTIMO argumento. Si detrás
venía OTRA bandera (`--ancho --via local`) o un valor no numérico (`--ancho abc`),
`int(v)` se tragaba el token y reventaba con una traza cruda de Python en vez de
salir con código 1 y un mensaje — justo lo que ESPECIFICACION.md §3 y el README
prometen que no pasa. Mismo patrón y mismo tipo en `abyss/ojo.py:39`
(`idx = int(argv[1])`, el índice de cámara)."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import unittest
import ayudas as ay


class ImagenCrearRechazaArgumentosSinReconocer(unittest.TestCase):
    def test_tres_posicionales_de_mas_no_se_tragan_en_silencio(self):
        proj = ay.nuevo_proyecto()
        env = ay.entorno(proj)

        # exactamente el caso medido el 6-sep: salida + tres posicionales de más
        # (ancho, alto, semilla sin bandera) además de --via.
        r = ay.ejecutar(ay.script('imagen.py'),
                         ['crear', 'un gato', 'g1.png', '512', '384', '7', '--via', 'local'],
                         env, timeout=15)

        # con el fallo: returncode 0 y (con red o servidor de verdad) una imagen de
        # 1024x1024 generada sin ningún aviso de que los tres números se ignoraron.
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
        # medido 6-sep: `--ancho --via local` colaba "--via" como el valor de
        # --ancho y `int("--via")` reventaba con ValueError sin capturar.
        proj = ay.nuevo_proyecto()
        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('imagen.py'), ['crear', 'un gato', '--ancho', '--via', 'local'], env, timeout=15)
        self.assertEqual(r.returncode, 1, f'stdout={r.stdout!r} stderr={r.stderr!r}')
        self.assertNotIn('Traceback', r.stderr, 'nunca una traza cruda, siempre un mensaje claro')

    def test_bandera_conocida_con_valor_no_numerico_no_revienta(self):
        # medido 6-sep: `--ancho abc` -> ValueError: invalid literal for int()
        proj = ay.nuevo_proyecto()
        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('imagen.py'), ['crear', 'un gato', '--ancho', 'abc'], env, timeout=15)
        self.assertEqual(r.returncode, 1, f'stdout={r.stdout!r} stderr={r.stderr!r}')
        self.assertNotIn('Traceback', r.stderr)
        self.assertIn('abc', r.stdout, 'el mensaje debe nombrar el valor que no entendió')

    def test_dos_banderas_numericas_seguidas_sin_valor_no_revienta(self):
        # medido 6-sep: `--semilla --alto 512` -> int("--alto") reventaba igual
        proj = ay.nuevo_proyecto()
        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('imagen.py'), ['crear', 'un gato', '--semilla', '--alto', '512'], env, timeout=15)
        self.assertEqual(r.returncode, 1, f'stdout={r.stdout!r} stderr={r.stderr!r}')
        self.assertNotIn('Traceback', r.stderr)


class OjoIndiceCamaraNoNumericoNoRevienta(unittest.TestCase):
    def test_indice_no_numerico_da_mensaje_claro_y_codigo_1(self):
        # mismo patrón, mismo tipo, en abyss/ojo.py (`idx = int(resto[1])`, verbo
        # `mirar`). Desde T4.6 `ojo.py` despacha por verbo: hay que anteponer `mirar`, si no el primer positional ("foto.jpg")
        # se lee como verbo y sale "verbo desconocido" antes de llegar a este chequeo.
        proj = ay.nuevo_proyecto()
        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('ojo.py'), ['mirar', 'foto.jpg', 'noesunnumero'], env, timeout=15)
        self.assertEqual(r.returncode, 1, f'stdout={r.stdout!r} stderr={r.stderr!r}')
        self.assertNotIn('Traceback', r.stderr)
        self.assertIn('noesunnumero', r.stdout, 'el mensaje debe nombrar el valor que no entendió')


if __name__ == '__main__':
    unittest.main()
