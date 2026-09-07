"""Arranque en frío (ESPECIFICACION.md §2.2): con menos de
`propiocepcion.UMBRAL_FRIO` (8) sesiones medidas, ni `propiocepcion.py` inventa un
percentil ni `continuidad.py` (la sala de los relojes) despierta nada — aunque el
prompt sea CASI IDÉNTICO al contenido de una sesión guardada. Se prueba con 0 y con
3 sesiones, tal como pide §6.
"""
import sys
import os
import json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import unittest
import ayudas as ay


class PropiocepcionNoInventaPercentiles(unittest.TestCase):
    def test_cero_sesiones(self):
        proj = ay.nuevo_proyecto()
        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('propiocepcion.py'), [], env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('sin datos que medir todavía', r.stdout)
        self.assertNotIn('percentil', r.stdout)

    def test_tres_sesiones_dice_sin_vara(self):
        proj = ay.nuevo_proyecto()
        sesiones = proj / 'memory' / 'sesiones'
        for nombre in ('sesA', 'sesB', 'sesC'):
            ay.sesion_simple(sesiones / f'{nombre}.jsonl',
                              [f'hola quiero probar la sesión {nombre} con varias palabras seguidas'])
        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('propiocepcion.py'), [], env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('sin vara todavía (n=3)', r.stdout)
        self.assertNotIn('percentil', r.stdout)

        # las 3 sesiones SÍ se midieron (lo medible no se inventa; el percentil sí se calla)
        medido = json.loads((proj / 'memory' / 'propiocepcion.json').read_text(encoding='utf-8'))
        self.assertEqual(len(medido), 3)
        self.assertTrue(all(m['turnos_usuario'] > 0 for m in medido.values()))


class SalaDeRelojesNoDespiertaEnFrio(unittest.TestCase):
    def test_cero_sesiones_no_despierta(self):
        proj = ay.nuevo_proyecto()
        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('continuidad.py'), ['--probar', 'una frase cualquiera de prueba'], env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('(nada despierta)', r.stdout)

    def test_tres_sesiones_parecidas_tampoco_despiertan(self):
        proj = ay.nuevo_proyecto()
        sesiones = proj / 'memory' / 'sesiones'
        frase_identica = 'quiero hablar largo y tendido sobre el proyecto abyss y sus varas medidas'
        ay.sesion_simple(sesiones / 'ses1.jsonl',
                          [frase_identica, 'una segunda frase distinta para variar el contenido de la sesión'])
        ay.sesion_simple(sesiones / 'ses2.jsonl',
                          ['otra sesión completamente distinta hablando de otra cosa cualquiera'])
        ay.sesion_simple(sesiones / 'ses3.jsonl',
                          ['tercera sesión con contenido diferente sobre temas variados'])
        env = ay.entorno(proj)
        # el sondeo es CASI IDÉNTICO al contenido de ses1: sin el arranque en frío, despertaría
        r = ay.ejecutar(ay.script('continuidad.py'), ['--probar', frase_identica], env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('(nada despierta)', r.stdout)


if __name__ == '__main__':
    unittest.main()
