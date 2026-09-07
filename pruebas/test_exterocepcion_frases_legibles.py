"""`exterocepcion.py` `__main__` (fallo 6-sep, "roza"): dos salidas documentadas en
`skills/exterocepcion/SKILL.md` imprimían la representación cruda de un dict de
Python, o la palabra `None`, en vez de una frase. MEDIDO con HOME falso:
`exterocepcion.py --refrescar-ip --proyecto "$(pwd)"` con red imprimía
`{'nombre': '...', ..., 'ts': 1788729270.9143646}` (repr, con el timestamp en
crudo), y sin red imprimía exactamente `None`. Lo mismo `--dicho "estoy en
Madrid"` sin red: «aprendido: None». Contradice el punto 5 de la filosofía del
README ("sin red no hay lugar ni meteo: la respuesta siempre es 'sin dato'"), que
el resto del paquete sí cumple.

`_texto_lugar_ip`/`_texto_aprendido` son funciones puras nuevas (se extrajeron del
`__main__` para poder probarlas sin red ni subprocess); las pruebas de subprocess
de abajo comprueban además que el `__main__` de verdad las usa.
"""
import sys
import os
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'abyss'))
import unittest
import ayudas as ay

import exterocepcion


class TextoLugarIpNuncaEsReprNiNone(unittest.TestCase):
    def test_sin_dato_no_es_la_palabra_none(self):
        texto = exterocepcion._texto_lugar_ip(None)
        self.assertNotEqual(texto, 'None')
        self.assertIn('sin dato', texto)

    def test_con_dato_no_es_el_repr_del_dict(self):
        ip = {'nombre': 'Villafingida', 'region': 'Prueba', 'pais': 'ES',
              'lat': 41.0, 'lon': 2.0, 'fuente': 'IP', 'ts': 1788729270.9143646}
        texto = exterocepcion._texto_lugar_ip(ip)
        self.assertNotIn('{', texto, 'no debe ser el repr crudo del dict')
        self.assertNotIn('1788729270', texto, 'el timestamp en crudo no pinta nada en una frase legible')
        self.assertIn('Villafingida', texto)
        self.assertIn('ES', texto)


class TextoAprendidoNuncaEsNone(unittest.TestCase):
    def test_sin_nombre_no_dice_aprendido_none(self):
        texto = exterocepcion._texto_aprendido(None)
        self.assertNotIn('None', texto)
        self.assertIn('no reconocí', texto)

    def test_con_nombre_dice_aprendido(self):
        self.assertEqual(exterocepcion._texto_aprendido('Springfield'), 'aprendido: Springfield')


class CliDeVerdadUsaLasFrasesLegibles(unittest.TestCase):
    """Subprocess real, sin red (regla dura 2 del encargo): comprueba que el
    `__main__` de `exterocepcion.py` de verdad llama a las funciones de arriba, no
    solo que existan."""

    def test_refrescar_ip_sin_red_dice_sin_dato_no_none(self):
        proj = ay.nuevo_proyecto()
        env = ay.entorno(proj, ABYSS_SIN_RED='1')
        r = ay.ejecutar(ay.script('exterocepcion.py'), ['--refrescar-ip'], env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotEqual(r.stdout.strip(), 'None')
        self.assertIn('sin dato', r.stdout)
        self.assertIn('sin red', r.stdout)

    def test_dicho_sin_lugar_reconocible_no_dice_aprendido_none(self):
        proj = ay.nuevo_proyecto()
        env = ay.entorno(proj, ABYSS_SIN_RED='1')
        r = ay.ejecutar(ay.script('exterocepcion.py'),
                         ['--dicho', 'no hay ningún patrón de lugar en esta frase'], env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn('aprendido: None', r.stdout)
        self.assertIn('no reconocí', r.stdout)

    def test_dicho_con_lugar_pero_sin_red_tampoco_dice_aprendido_none(self):
        # la frase SÍ matchea RE_DICHO ("estoy en <Ciudad>"), pero sin red el
        # geocodificador no puede resolver nada: aprender_lugar devuelve None igual.
        proj = ay.nuevo_proyecto()
        env = ay.entorno(proj, ABYSS_SIN_RED='1')
        r = ay.ejecutar(ay.script('exterocepcion.py'), ['--dicho', 'estoy en Springfield'], env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn('aprendido: None', r.stdout)
        self.assertIn('no reconocí', r.stdout)


if __name__ == '__main__':
    unittest.main()
