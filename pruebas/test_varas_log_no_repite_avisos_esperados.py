"""`continuidad.py` (fallo 6-sep, "roza"): cada arranque y cada cierre por debajo del
umbral en frío escribían en `mem/varas.log` la MISMA línea de aviso ("sin vara
todavía", y ahora también "sin índice ni fichas todavía"). MEDIDO: en un proyecto
virgen, tras un solo ciclo arranque+cierre el fichero ya llevaba dos entradas
idénticas salvo la fecha. Con las 8 sesiones que exige el umbral son al menos 16
entradas repetidas de un aviso que no es un fallo, y el fichero crece sin tope.

Ahora esos avisos ESPERADOS de un pase silencioso (arranque en frío, proyecto
virgen) se filtran igual que ya se filtraba la línea de confirmación "índice
reescrito N bytes": si no queda nada más, `varas.log` ni se toca.
"""
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

        # con el fallo, varas.log existía con DOS entradas del mismo aviso «sin vara
        # todavía»/«sin índice ni fichas todavía» — un aviso esperado, no un fallo.
        self.assertFalse(varas_log.exists(),
                          f'varas.log no debería existir solo por avisos esperados de arranque en frío: '
                          f'{varas_log.read_text(encoding="utf-8") if varas_log.exists() else ""}')


if __name__ == '__main__':
    unittest.main()
