"""`vigia.py` (ESPECIFICACION.md §6):
- caza un número inventado en la última respuesta, pero NO uno que salió de un
  `tool_result` (evidencia real).
- `--descargo` hace que `--precision` deje de decir «sin vara» (y nunca finge
  1.00: §2.1c) — pasa a un número medido de verdad.
- fallo "engaña" del revisor 3 (6-sep): `--descargo` no validaba nada, así que
  cualquier sid/caza inventados se apuntaban igual y `--precision` podía dar
  hasta un cociente negativo (más descargos que cazas). Ahora `--descargo`
  exige los tres argumentos, rehúsa sid/caza vacíos, y comprueba que la caza
  esté realmente registrada para esa sid antes de escribir nada; `--precision`
  además capa los descargos a las cazas reales para que el cociente nunca se
  salga de [0,1] pase lo que pase en el fichero.
"""
import sys
import os
import json
import re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import unittest
import ayudas as ay


class VigiaCazaSoloLoQueNoSalioDeNinguo(unittest.TestCase):
    def test_no_caza_lo_que_salio_del_tool_result_y_si_lo_inventado(self):
        proj = ay.nuevo_proyecto()
        tp = proj / 'ses-vigia-1.jsonl'
        lineas = [
            ay.usuario('lee el fichero y dime cuántas líneas tiene', '2026-01-01T10:00:00Z'),
            ay.asistente_tool_use('Bash', {'command': 'wc -l archivo.txt'}, '2026-01-01T10:00:05Z'),
            ay.usuario_tool_result('42 archivo.txt', '2026-01-01T10:00:06Z'),
            ay.asistente_texto(
                'El fichero tiene 42 líneas y calculo que triplicado darían 999999 líneas.',
                '2026-01-01T10:00:10Z'),
        ]
        ay.escribir_jsonl(tp, lineas)
        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('vigia.py'), ['--probar', str(tp)], env)
        self.assertEqual(r.returncode, 0, r.stderr)

        salida = r.stdout.splitlines()
        idx = next(i for i, l in enumerate(salida) if l.startswith('--- respuesta analizada'))
        cazas = json.loads('\n'.join(salida[:idx]))
        self.assertIn('999999', cazas['numeros'])       # inventado: nadie lo dijo, cazado
        self.assertNotIn('42', cazas['numeros'])         # vino del tool_result: no se caza


class VigiaDescargoCambiaLaPrecision(unittest.TestCase):
    def test_descargo_saca_la_precision_del_sin_vara(self):
        proj = ay.nuevo_proyecto()
        sid = 'ses-precision-1'
        tp = proj / f'{sid}.jsonl'
        ay.escribir_jsonl(tp, [
            ay.usuario('cuéntame algo curioso', '2026-01-01T10:00:00Z'),
            ay.asistente_texto('Un dato curioso: el número 999999 no sale de ningún sitio.',
                                '2026-01-01T10:00:05Z'),
        ])
        env = ay.entorno(proj)

        # sin ninguna caza registrada todavía: --precision dice "sin vara", nunca 1.00
        r0 = ay.ejecutar(ay.script('vigia.py'), ['--precision'], env)
        self.assertEqual(r0.returncode, 0, r0.stderr)
        self.assertIn('sin vara', r0.stdout)

        # el hook por defecto (--verificar implícito) contra ese transcript: debe apuntar la caza
        entrada = json.dumps({'session_id': sid, 'transcript_path': str(tp), 'cwd': str(proj)})
        r1 = ay.ejecutar(ay.script('vigia.py'), [], env, entrada=entrada)
        self.assertEqual(r1.returncode, 0, r1.stderr)

        conf = proj / 'memory' / 'confabulaciones.jsonl'
        self.assertTrue(conf.exists())
        registros = [json.loads(l) for l in conf.read_text(encoding='utf-8').splitlines() if l.strip()]
        self.assertTrue(any('999999' in reg.get('numeros', []) for reg in registros))

        # HAY una caza dura ahora, pero SIN descargo sigue diciendo "sin vara" (§2.1c:
        # no se finge una precisión "1.00" solo porque nadie la ha descargado todavía)
        r2 = ay.ejecutar(ay.script('vigia.py'), ['--precision'], env)
        self.assertIn('sin vara', r2.stdout)
        self.assertNotIn('1.00', r2.stdout)

        # descargamos esa caza (era legítima)
        r3 = ay.ejecutar(ay.script('vigia.py'), ['--descargo', sid, '999999', 'cálculo mío mostrado'], env)
        self.assertEqual(r3.returncode, 0, r3.stderr)
        self.assertIn('descargo apuntado', r3.stdout)

        # ahora --precision da un número medido de verdad: ni "sin vara" ni un 1.00 de mentira
        r4 = ay.ejecutar(ay.script('vigia.py'), ['--precision'], env)
        self.assertEqual(r4.returncode, 0, r4.stderr)
        self.assertNotIn('sin vara', r4.stdout)
        self.assertNotIn('1.00', r4.stdout)
        self.assertIn('precisión aparente', r4.stdout)


class VigiaDescargoRechazaSinArgumentos(unittest.TestCase):
    def test_descargo_sin_argumentos_no_escribe_nada(self):
        proj = ay.nuevo_proyecto()
        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('vigia.py'), ['--descargo'], env)
        self.assertNotEqual(r.returncode, 0, r.stdout)
        conf = proj / 'memory' / 'confabulaciones.jsonl'
        self.assertFalse(conf.exists(), 'un descargo sin argumentos no debe crear/escribir confabulaciones.jsonl')

    def test_descargo_con_sid_o_caza_vacios_no_escribe_nada(self):
        proj = ay.nuevo_proyecto()
        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('vigia.py'), ['--descargo', '', '', 'motivo'], env)
        self.assertNotEqual(r.returncode, 0, r.stdout)
        conf = proj / 'memory' / 'confabulaciones.jsonl'
        self.assertFalse(conf.exists())


class VigiaDescargoRechazaCazaInventada(unittest.TestCase):
    def test_descargo_con_sid_o_caza_inventados_se_rechaza(self):
        proj = ay.nuevo_proyecto()
        sid = 'ses-real-1'
        tp = proj / f'{sid}.jsonl'
        ay.escribir_jsonl(tp, [
            ay.usuario('cuéntame algo curioso', '2026-01-01T10:00:00Z'),
            ay.asistente_texto('Un dato curioso: el número 111222 no sale de ningún sitio.',
                                '2026-01-01T10:00:05Z'),
        ])
        env = ay.entorno(proj)
        entrada = json.dumps({'session_id': sid, 'transcript_path': str(tp), 'cwd': str(proj)})
        r1 = ay.ejecutar(ay.script('vigia.py'), [], env, entrada=entrada)
        self.assertEqual(r1.returncode, 0, r1.stderr)
        conf = proj / 'memory' / 'confabulaciones.jsonl'
        self.assertTrue(conf.exists())
        antes = conf.read_text(encoding='utf-8')

        # sid que no existe en absoluto
        r2 = ay.ejecutar(ay.script('vigia.py'), ['--descargo', 'sesion-que-no-existe', '111222', 'motivo'], env)
        self.assertNotEqual(r2.returncode, 0, r2.stdout)

        # sid real, pero la caza es inventada (no está entre las registradas de esa sid)
        r3 = ay.ejecutar(ay.script('vigia.py'), ['--descargo', sid, 'una caza que nunca hubo', 'porque sí'], env)
        self.assertNotEqual(r3.returncode, 0, r3.stdout)

        despues = conf.read_text(encoding='utf-8')
        self.assertEqual(antes, despues, 'ningún descargo inventado debe llegar a escribirse en el fichero')


class VigiaPrecisionNuncaNegativa(unittest.TestCase):
    def test_mas_descargos_que_cazas_no_da_precision_fuera_de_0_1(self):
        proj = ay.nuevo_proyecto()
        sid = 'ses-exceso-1'
        tp = proj / f'{sid}.jsonl'
        ay.escribir_jsonl(tp, [
            ay.usuario('dime algo', '2026-01-01T10:00:00Z'),
            ay.asistente_texto('El número 333444 no sale de ningún sitio.', '2026-01-01T10:00:05Z'),
        ])
        env = ay.entorno(proj)
        entrada = json.dumps({'session_id': sid, 'transcript_path': str(tp), 'cwd': str(proj)})
        r1 = ay.ejecutar(ay.script('vigia.py'), [], env, entrada=entrada)
        self.assertEqual(r1.returncode, 0, r1.stderr)

        # una única caza dura registrada, pero la descargamos DOS veces (descargo
        # válido y repetido: nada impide llamar --descargo otra vez sobre la misma
        # caza real) — sin el tope, desc=2 > tot=1 y la precisión se iría a negativo
        for _ in range(2):
            r = ay.ejecutar(ay.script('vigia.py'), ['--descargo', sid, '333444', 'cálculo mío mostrado'], env)
            self.assertEqual(r.returncode, 0, r.stdout)

        rp = ay.ejecutar(ay.script('vigia.py'), ['--precision'], env)
        self.assertEqual(rp.returncode, 0, rp.stderr)
        m = re.search(r'precisión aparente (-?[\d.]+|nan)', rp.stdout)
        self.assertIsNotNone(m, rp.stdout)
        if m.group(1) != 'nan':
            valor = float(m.group(1))
            self.assertGreaterEqual(valor, 0.0, rp.stdout)
            self.assertLessEqual(valor, 1.0, rp.stdout)


if __name__ == '__main__':
    unittest.main()
