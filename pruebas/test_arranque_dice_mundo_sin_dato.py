"""`continuidad.py --arranque` (fallo 6-sep, "roza"): con la red muerta, el
`additionalContext` no mencionaba el lugar en absoluto — silencio, no "sin dato".
`--arranque` refrescaba la IP (`exterocepcion.lugar_ip(refrescar=True, ...)`) pero
nunca llamaba a `exterocepcion.texto()` (a diferencia de `--despertar`, que sí lo
hace) para componer la línea `[mundo] ...`; si `lugar_ip()` fallaba en silencio y
`noticias.texto()` tampoco devolvía nada, el texto de arranque no llevaba ni rastro
de que se hubiera intentado mirar el mundo.

`ABYSS_SIN_RED=1` corta la red al instante (ver `ayudas.py`/regla dura 2 del
encargo: "sin red en la suite")."""
import sys
import os
import json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import unittest
import ayudas as ay


class ArranqueDiceMundoAunqueLaRedEsteMuerta(unittest.TestCase):
    def test_sin_red_el_additionalcontext_menciona_mundo_sin_dato(self):
        proj = ay.nuevo_proyecto()
        sid = 'ses-arranque-mundo-1'
        tp = proj / f'{sid}.jsonl'
        ay.sesion_simple(tp, ['hola, quiero probar que el arranque diga algo del mundo'])
        mem = proj / 'memory'; mem.mkdir(parents=True, exist_ok=True)

        entrada = json.dumps({'session_id': sid, 'transcript_path': str(tp), 'cwd': str(proj)})
        env = ay.entorno(proj, ABYSS_SIN_RED='1')
        r = ay.ejecutar(ay.script('continuidad.py'), ['--arranque'], env, entrada=entrada)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.strip())

        payload = json.loads(r.stdout)
        contexto = payload['hookSpecificOutput']['additionalContext']
        # con el fallo: nada de "[mundo]" aparecía aquí, ni siquiera un "sin dato"
        self.assertIn('[mundo]', contexto)
        self.assertIn('sin dato', contexto)


if __name__ == '__main__':
    unittest.main()
