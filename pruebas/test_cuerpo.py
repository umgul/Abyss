"""`cuerpo.py`: hardware de la máquina, con normal propia por cuantiles. No toca
`rutas.resolver()` ni stdin al importarse, así que las funciones puras se prueban con
import directo y cada instrumento se monkeypatchea aparte; el gancho real se prueba por subproceso, igual que el resto de la batería."""
import sys
import os
import json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import unittest
from unittest import mock
import ayudas as ay

sys.path.insert(0, str(ay.RAIZ))
from abyss import cuerpo  # noqa: E402


def _medida(cpu=50.0, ram=4096.0, disco=100.0, vram=None, temp=None, bat=None, cargando=False, ts=0.0):
    return {'ts': ts, 'cpu': cpu, 'ram_libre_mb': ram, 'disco_libre_gb': disco,
            'vram_libre_mib': vram, 'temp_gpu': temp, 'bateria_pct': bat, 'bateria_cargando': cargando}


class VaraPropiaPorCuantiles(unittest.TestCase):
    def test_sin_historial_dice_sin_vara(self):
        linea = cuerpo.texto_arranque(_medida(), [])
        self.assertIn('sin vara todavía (n=0)', linea)
        self.assertNotIn('p50 tuyo', linea)

    def test_tres_medidas_previas_sigue_sin_vara(self):
        hist = [_medida(cpu=c) for c in (40, 45, 50)]
        linea = cuerpo.texto_arranque(_medida(), hist)
        self.assertIn('sin vara todavía (n=3)', linea)
        self.assertNotIn('p50 tuyo', linea)

    def test_ocho_medidas_previas_ya_hay_cuantiles(self):
        hist = [_medida(cpu=c) for c in (10, 20, 30, 40, 50, 60, 70, 80)]
        linea = cuerpo.texto_arranque(_medida(cpu=50), hist)
        self.assertNotIn('sin vara todavía', linea)
        self.assertIn('p50 tuyo', linea)

    def test_cuantiles_none_bajo_el_umbral(self):
        hist = [_medida(cpu=c) for c in (10, 20, 30)]
        self.assertIsNone(cuerpo.cuantiles('cpu', hist))

    def test_cuantiles_por_canal_no_por_medida(self):
        # 8 medidas, pero NINGUNA trae vram: ese canal sigue sin vara aunque cpu ya la tenga
        hist = [_medida(cpu=c, vram=None) for c in range(8)]
        self.assertIsNotNone(cuerpo.cuantiles('cpu', hist))
        self.assertIsNone(cuerpo.cuantiles('vram_libre_mib', hist))


class FormatoDecimalCastellano(unittest.TestCase):
    """La línea del cuerpo debe imprimir los decimales con coma, no con punto, según
    el ejemplo literal de la especificación («ram libre 9,8 GB»)."""

    def test_valor_fmt_usa_coma_no_punto(self):
        # 10035 MB / 1024 = 9,8 GB — el mismo ejemplo literal
        self.assertEqual(cuerpo._valor_fmt('ram_libre_mb', 10035.0), '9,8 GB')
        self.assertNotIn('.', cuerpo._valor_fmt('ram_libre_mb', 10035.0))

    def test_linea_de_arranque_usa_coma(self):
        linea = cuerpo.texto_arranque(_medida(ram=10035.0), [])
        self.assertIn('9,8 GB', linea)
        self.assertNotIn('9.8', linea)


class SilencioDelGanchoDePrompt(unittest.TestCase):
    def _historial_normal(self):
        return [_medida(cpu=c) for c in (10, 11, 12, 13, 14, 15, 16, 17)]

    def test_silencio_dentro_de_lo_normal(self):
        hist = self._historial_normal()
        self.assertEqual(cuerpo.texto_despertar(_medida(cpu=13), hist), '')

    def test_avisa_por_encima_del_p95(self):
        hist = self._historial_normal()
        txt = cuerpo.texto_despertar(_medida(cpu=99), hist)
        self.assertTrue(txt.startswith('[cuerpo]'))
        self.assertIn('cpu', txt)
        self.assertIn('por encima de tu p95', txt)

    def test_avisa_por_debajo_del_p5(self):
        hist = self._historial_normal()
        txt = cuerpo.texto_despertar(_medida(cpu=0.1), hist)
        self.assertIn('por debajo de tu p5', txt)

    def test_sin_vara_nunca_avisa_aunque_el_valor_sea_extremo(self):
        hist = [_medida(cpu=c) for c in (10, 11, 12)]  # n=3, bajo UMBRAL_FRIO
        self.assertEqual(cuerpo.texto_despertar(_medida(cpu=99999), hist), '')

    def test_bateria_nunca_dispara_aviso(self):
        # cargar/descargar es normal por diseño: no es una vara de anomalía
        hist = [_medida(bat=b) for b in (80, 81, 82, 83, 84, 85, 86, 87)]
        self.assertEqual(cuerpo.texto_despertar(_medida(bat=1.0), hist), '')


class MedirConInstrumentosSimulados(unittest.TestCase):
    def test_medir_junta_los_seis_canales(self):
        with mock.patch.object(cuerpo, 'leer_cpu', return_value=12.0), \
                mock.patch.object(cuerpo, 'leer_ram_libre', return_value=2048.0), \
                mock.patch.object(cuerpo, 'leer_disco_libre', return_value=99.0), \
                mock.patch.object(cuerpo, 'leer_gpu', return_value=(4096.0, 60.0)), \
                mock.patch.object(cuerpo, 'leer_bateria', return_value=(87.0, True)):
            m = cuerpo.medir('no-hace-falta-un-mem-real-aqui')
        self.assertEqual(m['cpu'], 12.0)
        self.assertEqual(m['ram_libre_mb'], 2048.0)
        self.assertEqual(m['disco_libre_gb'], 99.0)
        self.assertEqual(m['vram_libre_mib'], 4096.0)
        self.assertEqual(m['temp_gpu'], 60.0)
        self.assertEqual(m['bateria_pct'], 87.0)
        self.assertTrue(m['bateria_cargando'])

    def test_sin_nvidia_smi_es_sin_dato_no_cero(self):
        with mock.patch.object(cuerpo, 'leer_cpu', return_value=10.0), \
                mock.patch.object(cuerpo, 'leer_ram_libre', return_value=1024.0), \
                mock.patch.object(cuerpo, 'leer_disco_libre', return_value=50.0), \
                mock.patch.object(cuerpo, 'leer_gpu', return_value=(None, None)), \
                mock.patch.object(cuerpo, 'leer_bateria', return_value=(None, None)):
            m = cuerpo.medir('x')
        self.assertIsNone(m['vram_libre_mib'])
        self.assertIsNone(m['temp_gpu'])
        linea = cuerpo.texto_arranque(m, [])
        self.assertIn('vram libre sin dato', linea)
        self.assertIn('temp gpu sin dato', linea)
        self.assertIn('batería sin dato', linea)

    def test_leer_gpu_real_no_revienta_sin_gpu(self):
        """Llamada REAL (sin mock) a `leer_gpu()`: si esta máquina no tiene
        `nvidia-smi`, debe devolver (None, None) sin lanzar excepción — no hace
        falta tener una GPU NVIDIA para que la suite pase."""
        vram, temp = cuerpo.leer_gpu()
        self.assertTrue(vram is None or isinstance(vram, float))
        self.assertTrue(temp is None or isinstance(temp, float))


class HistorialEnDisco(unittest.TestCase):
    def test_guardar_y_leer_conserva_el_orden(self):
        proj = ay.nuevo_proyecto()
        mem = str(proj / 'memory')
        os.makedirs(mem, exist_ok=True)
        self.assertEqual(cuerpo.historial(mem), [])
        cuerpo.guardar(mem, _medida(cpu=1))
        cuerpo.guardar(mem, _medida(cpu=2))
        hist = cuerpo.historial(mem)
        self.assertEqual([h['cpu'] for h in hist], [1, 2])

    def test_leer_disco_libre_real(self):
        proj = ay.nuevo_proyecto()
        mem = str(proj / 'memory')
        os.makedirs(mem, exist_ok=True)
        gb = cuerpo.leer_disco_libre(mem)
        self.assertTrue(gb is None or gb > 0)


class GanchosYCliPorSubproceso(unittest.TestCase):
    def test_arranque_imprime_json_valido_y_guarda(self):
        proj = ay.nuevo_proyecto()
        sid = 'ses-cuerpo-arranque'
        tp = proj / f'{sid}.jsonl'
        ay.escribir_jsonl(tp, [ay.usuario('hola, primera línea de la sesión')])
        entrada = json.dumps({'session_id': sid, 'transcript_path': str(tp), 'cwd': str(proj)})
        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('cuerpo.py'), ['--arranque'], env, entrada=entrada)
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        contexto = payload['hookSpecificOutput']['additionalContext']
        self.assertEqual(payload['hookSpecificOutput']['hookEventName'], 'SessionStart')
        self.assertTrue(contexto.startswith('[cuerpo]'))
        self.assertTrue((proj / 'memory' / 'cuerpo.jsonl').exists())

    def test_despertar_sin_pista_de_proyecto_calla(self):
        proj = ay.nuevo_proyecto()
        entrada = json.dumps({'session_id': 'sid-sin-pista', 'prompt': 'hola'})
        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('cuerpo.py'), ['--despertar'], env, entrada=entrada)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), '')

    def test_cli_manual_imprime_linea_y_guarda(self):
        proj = ay.nuevo_proyecto()
        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('cuerpo.py'), [], env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.strip().startswith('[cuerpo]'))
        self.assertTrue((proj / 'memory' / 'cuerpo.jsonl').exists())

    def test_cli_json(self):
        proj = ay.nuevo_proyecto()
        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('cuerpo.py'), ['--json'], env)
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertIn('medida', payload)
        self.assertIn('cuantiles', payload)

    def test_historial_cli_respeta_n(self):
        proj = ay.nuevo_proyecto()
        env = ay.entorno(proj)
        ay.ejecutar(ay.script('cuerpo.py'), [], env)
        ay.ejecutar(ay.script('cuerpo.py'), [], env)
        r = ay.ejecutar(ay.script('cuerpo.py'), ['--historial', '1'], env)
        self.assertEqual(r.returncode, 0, r.stderr)
        lineas = [l for l in r.stdout.strip().splitlines() if l.strip()]
        self.assertEqual(len(lineas), 1)

    def test_bandera_desconocida_sale_con_codigo_1(self):
        proj = ay.nuevo_proyecto()
        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('cuerpo.py'), ['--bandera-inventada'], env)
        self.assertEqual(r.returncode, 1)
        self.assertIn('--bandera-inventada', r.stdout)

    def test_bandera_desconocida_con_valor_sale_con_codigo_1(self):
        proj = ay.nuevo_proyecto()
        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('cuerpo.py'), ['--bandera-inventada', '7'], env)
        self.assertEqual(r.returncode, 1)
        self.assertIn('--bandera-inventada', r.stdout)

    def test_posicional_de_mas_sale_con_codigo_1(self):
        proj = ay.nuevo_proyecto()
        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('cuerpo.py'), ['posicional_de_mas'], env)
        self.assertEqual(r.returncode, 1)
        self.assertIn('posicional_de_mas', r.stdout)

    def test_historial_no_numerico_sale_con_codigo_1(self):
        proj = ay.nuevo_proyecto()
        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('cuerpo.py'), ['--historial', 'no-es-un-numero'], env)
        self.assertEqual(r.returncode, 1)
        self.assertIn('no-es-un-numero', r.stdout)


class HistorialConVaraNoMiente(unittest.TestCase):
    """`--historial` no debe decir "sin vara todavía" para una fila cuando el proyecto
    ya tiene 8+ medidas anteriores: cada fila se compara contra todo lo anterior a
    ella, no contra un historial vacío."""

    def test_con_ocho_o_mas_medidas_no_dice_sin_vara(self):
        proj = ay.nuevo_proyecto()
        env = ay.entorno(proj)
        # 10 medidas guardadas; --historial 2 pide las 2 últimas. Cada una se
        # compara contra TODO lo anterior a ella (8 y 9 medidas respectivamente),
        # las dos por encima de UMBRAL_FRIO=8: ninguna de las 2 filas debe mentir
        # «sin vara todavía».
        for _ in range(10):
            r = ay.ejecutar(ay.script('cuerpo.py'), [], env)
            self.assertEqual(r.returncode, 0, r.stderr)
        r = ay.ejecutar(ay.script('cuerpo.py'), ['--historial', '2'], env)
        self.assertEqual(r.returncode, 0, r.stderr)
        lineas = [l for l in r.stdout.strip().splitlines() if l.strip()]
        self.assertEqual(len(lineas), 2)
        for linea in lineas:
            self.assertNotIn('sin vara todavía', linea,
                              f'con 8+ medidas previas ya hay vara: {linea!r}')


if __name__ == '__main__':
    unittest.main()
