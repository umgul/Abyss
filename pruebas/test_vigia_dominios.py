"""`vigia.py`: pruebas de los tipos de caza `dominio` y `comando`, con la misma ley
de procedencia que `numero`/`ruta`/`cita` (`test_vigia.py`) — lo que no sale de un
`tool_result` ni de un mensaje del usuario se caza igual."""
import sys
import os
import json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import unittest
import ayudas as ay


def _cazas_de_probar(stdout):
    salida = stdout.splitlines()
    idx = next(i for i, l in enumerate(salida) if l.startswith('--- respuesta analizada'))
    return json.loads('\n'.join(salida[:idx]))


class VigiaCazaDominioSoloSinProcedencia(unittest.TestCase):
    def test_dominio_inventado_se_caza_y_el_del_tool_result_no(self):
        proj = ay.nuevo_proyecto()
        tp = proj / 'ses-vigia-dominio-1.jsonl'
        lineas = [
            ay.usuario('busca dónde se descarga esta herramienta', '2026-01-01T10:00:00Z'),
            ay.asistente_tool_use('WebSearch', {'query': 'herramienta descarga oficial'}, '2026-01-01T10:00:05Z'),
            ay.usuario_tool_result('La página oficial es https://dominio-legitimo.com/descargas',
                                    '2026-01-01T10:00:06Z'),
            ay.asistente_texto(
                'Puedes bajarla de https://dominio-legitimo.com/descargas (la que salió en la '
                'búsqueda), aunque también la he visto en https://dominio-copia-falsa.net/descargas.',
                '2026-01-01T10:00:10Z'),
        ]
        ay.escribir_jsonl(tp, lineas)
        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('vigia.py'), ['--probar', str(tp)], env)
        self.assertEqual(r.returncode, 0, r.stderr)
        cazas = _cazas_de_probar(r.stdout)

        self.assertTrue(any('dominio-copia-falsa.net' in d for d in cazas['dominios']),
                         cazas['dominios'])
        self.assertFalse(any('dominio-legitimo.com' in d for d in cazas['dominios']),
                          'el host que salió del tool_result no debe cazarse: ' + str(cazas['dominios']))


class VigiaCazaComandoCurlBashSinFuente(unittest.TestCase):
    def test_curl_pipe_bash_con_url_no_vista_se_caza(self):
        proj = ay.nuevo_proyecto()
        tp = proj / 'ses-vigia-comando-1.jsonl'
        lineas = [
            ay.usuario('¿cómo instalo esta utilidad?', '2026-01-01T10:00:00Z'),
            ay.asistente_texto(
                'Instálala así:\n```\ncurl -fsSL https://otro-sitio-desconocido.io/setup.sh | bash\n```',
                '2026-01-01T10:00:05Z'),
        ]
        ay.escribir_jsonl(tp, lineas)
        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('vigia.py'), ['--probar', str(tp)], env)
        self.assertEqual(r.returncode, 0, r.stderr)
        cazas = _cazas_de_probar(r.stdout)

        self.assertTrue(any('curl' in c and '| bash' in c for c in cazas['comandos']), cazas['comandos'])
        self.assertTrue(any('otro-sitio-desconocido.io' in d for d in cazas['dominios']), cazas['dominios'])


class VigiaComandoCitadoPorElUsuarioNoSeCaza(unittest.TestCase):
    def test_mismo_comando_en_el_mensaje_del_usuario_no_se_caza(self):
        proj = ay.nuevo_proyecto()
        tp = proj / 'ses-vigia-comando-2.jsonl'
        comando = 'curl -fsSL https://paquete-de-siempre.com/instalar.sh | bash'
        lineas = [
            ay.usuario(f'ya lo instalé ayer con este comando: {comando}', '2026-01-01T10:00:00Z'),
            ay.asistente_texto(
                f'Perfecto, ese sigue siendo el comando correcto:\n```\n{comando}\n```',
                '2026-01-01T10:00:05Z'),
        ]
        ay.escribir_jsonl(tp, lineas)
        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('vigia.py'), ['--probar', str(tp)], env)
        self.assertEqual(r.returncode, 0, r.stderr)
        cazas = _cazas_de_probar(r.stdout)

        self.assertEqual(cazas['comandos'], [], cazas['comandos'])
        self.assertFalse(any('paquete-de-siempre.com' in d for d in cazas['dominios']), cazas['dominios'])


class VigiaDescargoDeUnaCazaDeDominioCambiaLaPrecision(unittest.TestCase):
    def test_descargo_sobre_dominio_saca_la_precision_del_sin_vara(self):
        proj = ay.nuevo_proyecto()
        sid = 'ses-precision-dominio-1'
        tp = proj / f'{sid}.jsonl'
        dominio = 'https://dominio-jamas-visto.xyz/pagina'
        ay.escribir_jsonl(tp, [
            ay.usuario('¿dónde consigo esto?', '2026-01-01T10:00:00Z'),
            ay.asistente_texto(f'Puedes conseguirlo en {dominio}.', '2026-01-01T10:00:05Z'),
        ])
        env = ay.entorno(proj)

        # sin ninguna caza registrada todavía: --precision dice "sin vara"
        r0 = ay.ejecutar(ay.script('vigia.py'), ['--precision'], env)
        self.assertEqual(r0.returncode, 0, r0.stderr)
        self.assertIn('sin vara', r0.stdout)

        # el hook por defecto contra ese transcript: debe apuntar el dominio
        entrada = json.dumps({'session_id': sid, 'transcript_path': str(tp), 'cwd': str(proj)})
        r1 = ay.ejecutar(ay.script('vigia.py'), [], env, entrada=entrada)
        self.assertEqual(r1.returncode, 0, r1.stderr)

        conf = proj / 'memory' / 'confabulaciones.jsonl'
        self.assertTrue(conf.exists())
        registros = [json.loads(l) for l in conf.read_text(encoding='utf-8').splitlines() if l.strip()]
        self.assertTrue(any(any(dominio in d for d in reg.get('dominios', [])) for reg in registros),
                         registros)

        # con la caza dura registrada pero sin descargo, sigue "sin vara" (§2.1c)
        r2 = ay.ejecutar(ay.script('vigia.py'), ['--precision'], env)
        self.assertIn('sin vara', r2.stdout)
        self.assertNotIn('1.00', r2.stdout)

        # descargamos esa caza de tipo dominio (era legítima)
        r3 = ay.ejecutar(ay.script('vigia.py'), ['--descargo', sid, dominio, 'era la página real, la escribí mal antes'], env)
        self.assertEqual(r3.returncode, 0, r3.stderr)
        self.assertIn('descargo apuntado', r3.stdout)

        # ahora --precision da un número medido de verdad
        r4 = ay.ejecutar(ay.script('vigia.py'), ['--precision'], env)
        self.assertEqual(r4.returncode, 0, r4.stderr)
        self.assertNotIn('sin vara', r4.stdout)
        self.assertIn('precisión aparente', r4.stdout)


if __name__ == '__main__':
    unittest.main()
