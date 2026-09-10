"""`propiocepcion.py` — el tramo de `parentesis.py`
debe quedar FUERA de la medida, igual que `continuidad.frases_usuario()`.

Fallo medido 7-sep: `medir()` nunca llamaba a `parentesis.en_parentesis()`, así
que los turnos/palabras/fichas de dentro de un tramo abierto SÍ entraban en
`mem/propiocepcion.json` (y de ahí al reloj de la sesión vía
`continuidad.hacer_reloj()`) — contra lo que exige T2.1 ("propiocepción...
ignoran el tramo"). `test_arranque_en_frio.py` ya cubre el arranque en frío de
este mismo módulo; aquí solo el tramo.
"""
import sys
import os
import json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import unittest
import ayudas as ay


class TramoNoEntraEnPropiocepcion(unittest.TestCase):
    def test_medir_salta_los_turnos_dentro_del_tramo(self):
        proj = ay.nuevo_proyecto()
        sid = 'ses-propio-tramo-1'
        tp = proj / f'{sid}.jsonl'
        ay.escribir_jsonl(tp, [
            ay.usuario('primero fuera del parentesis', '2026-01-01T10:00:00Z'),
            ay.usuario('segundo dentro secreto uno', '2026-01-01T10:05:00Z'),
            ay.usuario('tercero dentro secreto dos', '2026-01-01T10:06:00Z'),
            ay.usuario('cuarto fuera otra vez', '2026-01-01T10:10:00Z'),
            ay.usuario('quinto tambien fuera', '2026-01-01T10:15:00Z'),
        ])
        mem = proj / 'memory'
        mem.mkdir(parents=True, exist_ok=True)
        (mem / 'parentesis.json').write_text(json.dumps({
            sid: [{'inicio': '2026-01-01T10:04:30+00:00', 'fin': '2026-01-01T10:06:30+00:00', 'motivo': 'prueba'}]
        }), encoding='utf-8')

        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('propiocepcion.py'), [sid], env)
        self.assertEqual(r.returncode, 0, r.stderr)

        medido = json.loads((proj / 'memory' / 'propiocepcion.json').read_text(encoding='utf-8'))
        self.assertIn(sid, medido)
        # con el fallo, esto daba 5 (los 5 turnos, incluidos los 2 del tramo)
        self.assertEqual(medido[sid]['turnos_usuario'], 3,
                          'los 2 turnos dentro del tramo no deben contar')
        self.assertEqual(medido[sid]['palabras_usuario'], 11,
                          '"segundo dentro secreto uno" y "tercero dentro secreto dos" (4+4 palabras) no deben sumar')

    def test_sin_ningun_tramo_no_cambia_nada(self):
        """Sin `parentesis.json`, `en_parentesis()` siempre da False: el nuevo
        filtro no debe restar ni un turno a una sesión sin ningún tramo."""
        proj = ay.nuevo_proyecto()
        sid = 'ses-sin-tramo-1'
        tp = proj / f'{sid}.jsonl'
        ay.sesion_simple(tp, ['uno', 'dos', 'tres'])
        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('propiocepcion.py'), [sid], env)
        self.assertEqual(r.returncode, 0, r.stderr)
        medido = json.loads((proj / 'memory' / 'propiocepcion.json').read_text(encoding='utf-8'))
        self.assertEqual(medido[sid]['turnos_usuario'], 3)


if __name__ == '__main__':
    unittest.main()
