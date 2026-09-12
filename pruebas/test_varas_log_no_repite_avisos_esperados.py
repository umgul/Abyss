"""`continuidad.py`: los avisos esperados de un pase silencioso (arranque en frío,
proyecto virgen — "sin vara todavía", "sin índice ni fichas todavía") no deben
escribirse en `mem/varas.log`; si no queda nada más, el fichero ni se crea."""
import sys
import os
import json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import unittest
import ayudas as ay


class CierresEnFrioNoLlenanVarasLog(unittest.TestCase):
    def test_dos_cierres_seguidos_no_dejan_avisos_repetidos(self):
        proj = ay.nuevo_proyecto()
        env = ay.entorno(proj)
        varas_log = proj / 'memory' / 'varas.log'

        for i in range(2):
            sid = f'ses-frio-{i}'
            tp = proj / f'{sid}.jsonl'
            ay.sesion_simple(tp, [f'hola, mensaje de la sesión {i} para el ciclo de cierre'])
            entrada = json.dumps({'session_id': sid, 'transcript_path': str(tp), 'cwd': str(proj)})
            r = ay.ejecutar(ay.script('continuidad.py'), ['--cierre'], env, entrada=entrada)
            self.assertEqual(r.returncode, 0, r.stderr)

        # «sin vara todavía» y «sin índice ni fichas todavía» son avisos esperados,
        # no un fallo: no deben quedar registrados en varas.log.
        self.assertFalse(varas_log.exists(),
                          f'varas.log no debería existir solo por avisos esperados de arranque en frío: '
                          f'{varas_log.read_text(encoding="utf-8") if varas_log.exists() else ""}')


if __name__ == '__main__':
    unittest.main()
