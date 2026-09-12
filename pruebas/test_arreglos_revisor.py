"""`continuidad.py --arranque` mantiene su stdout como JSON válido aunque
`varas.py` avise por su cuenta, y `continuidad.py --cierre` deja rastro en
`mem/varas.log` cuando `varas.py` revienta con una excepción sin capturar."""
import sys
import os
import json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import unittest
import ayudas as ay


class ArranqueEnFrioNoRompeElJSON(unittest.TestCase):
    def test_arranque_bajo_umbral_sigue_siendo_json_valido(self):
        proj = ay.nuevo_proyecto()
        sid = 'ses-arranque-frio-1'
        tp = proj / f'{sid}.jsonl'
        ay.sesion_simple(tp, ['hola, primer mensaje de esta sesión que arranca en frío'])
        # hace falta al menos una ficha .md: sin ninguna, varas.py --index no escribe
        # nada (test_varas_no_crea_de_la_nada.py) y no llega a emitir el aviso que se
        # quiere ejercitar aquí.
        mem = proj / 'memory'; mem.mkdir(parents=True, exist_ok=True)
        (mem / 'una-ficha.md').write_text('---\ntype: reference\n---\ncontenido\n', encoding='utf-8')
        # ninguna sesión archivada en memory/sesiones/: la propia no cuenta (--arranque
        # cosecha las de OTROS hilos), así que varas.py dirá «sin vara todavía» por stdout.
        entrada = json.dumps({'session_id': sid, 'transcript_path': str(tp), 'cwd': str(proj)})
        env = ay.entorno(proj, ABYSS_SIN_RED='1')  # sin esto, --arranque llamaría a ipinfo/news.google real
        r = ay.ejecutar(ay.script('continuidad.py'), ['--arranque'], env, entrada=entrada)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.strip(), 'debería imprimir algo en --arranque')

        payload = json.loads(r.stdout)
        contexto = payload['hookSpecificOutput']['additionalContext']
        self.assertIn('sin vara', contexto)


class VarasQueRevientaDejaRastro(unittest.TestCase):
    def test_cierre_con_memory_md_como_directorio_deja_linea_en_varas_log(self):
        proj = ay.nuevo_proyecto()
        mem = proj / 'memory'
        mem.mkdir(parents=True, exist_ok=True)
        (mem / 'MEMORY.md').mkdir()  # MEMORY.md como directorio: varas.py revienta al
        # abrirlo (open() sobre un directorio) y sale con código != 0 y traza en stderr.

        sid = 'ses-cierre-revienta-1'
        tp = proj / f'{sid}.jsonl'
        ay.sesion_simple(tp, ['hola, esto es una sesión de prueba para el cierre'])
        entrada = json.dumps({'session_id': sid, 'transcript_path': str(tp), 'cwd': str(proj)})
        env = ay.entorno(proj)

        log = mem / 'varas.log'
        self.assertFalse(log.exists())

        r = ay.ejecutar(ay.script('continuidad.py'), ['--cierre'], env, entrada=entrada)
        # el gancho en sí no debe reventar aunque varas.py sí lo haga por dentro
        self.assertEqual(r.returncode, 0, r.stderr)

        self.assertTrue(log.exists(), 'debe quedar rastro del fallo de varas.py en varas.log')
        contenido = log.read_text(encoding='utf-8')
        self.assertTrue(contenido.strip(), 'el log no debe quedar vacío')
        self.assertIn('varas', contenido)


if __name__ == '__main__':
    unittest.main()
