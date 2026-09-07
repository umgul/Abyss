"""`continuidad.py --despertar` (gancho UserPromptSubmit): en cada prompt debe
añadir `[tiempo]` siempre. `[mundo]` (exterocepción) puede faltar sin red
(ESPECIFICACION.md §6) — aquí se preseeda `lugar.json`/`meteo.json` para que la
prueba no dependa de si HAY red en la máquina que la corre: así es determinista Y
además comprueba que, cuando SÍ hay lugar/meteo, `[mundo]` sale con esos datos.
"""
import sys
import os
import json
import time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import unittest
import ayudas as ay


class DespertarAgregaTiempoYMundo(unittest.TestCase):
    def test_despertar_incluye_tiempo(self):
        proj = ay.nuevo_proyecto()
        sid = 'ses-despertar-1'
        tp = proj / f'{sid}.jsonl'
        ay.escribir_jsonl(tp, [ay.usuario('hola, esto es una prueba de arranque de sesión',
                                           '2026-01-01T10:00:00Z')])

        mem = proj / 'memory'
        mem.mkdir(parents=True, exist_ok=True)
        # preseeda lugar/meteo: [mundo] no depende de la red real ni de si la hay aquí
        (mem / 'lugar.json').write_text(json.dumps({'ip': {
            'nombre': 'Villafingida', 'region': 'Prueba', 'pais': 'ES',
            'lat': 41.0, 'lon': 2.0, 'fuente': 'IP', 'ts': time.time()}}), encoding='utf-8')
        (mem / 'meteo.json').write_text(json.dumps({
            'temp': 20.0, 'humedad': 55, 'codigo': 0, 'cielo': 'despejado', 'viento': 10.0,
            'dia': True, 'hora_dato': '2026-01-01T10:00', 'lat': 41.0, 'ts': time.time()}),
            encoding='utf-8')

        entrada = json.dumps({'session_id': sid, 'transcript_path': str(tp), 'cwd': str(proj),
                               'prompt': 'un prompt cualquiera del usuario sin patrones especiales'})
        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('continuidad.py'), ['--despertar'], env, entrada=entrada)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.strip(), 'debería imprimir algo en --despertar')

        payload = json.loads(r.stdout)
        contexto = payload['hookSpecificOutput']['additionalContext']
        self.assertIn('[tiempo]', contexto)
        # con lugar/meteo preseedados y cacheados, [mundo] debe salir con esos datos
        self.assertIn('[mundo]', contexto)
        self.assertIn('Villafingida', contexto)

    def test_despertar_sin_pista_de_proyecto_calla(self):
        """Sin `transcript_path` ni `cwd` en el stdin del gancho, `rutas.es_mio()` no
        puede decidir a quién pertenece el hilo y se calla (fail-closed) aunque
        `ABYSS_PROYECTO` sí resuelva `mem` — «sin proyecto no hay datos» es
        distinto de «no sé si este hilo es mío»."""
        proj = ay.nuevo_proyecto()
        entrada = json.dumps({'session_id': 'sid-sin-pista', 'prompt': 'hola'})
        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('continuidad.py'), ['--despertar'], env, entrada=entrada)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), '')


if __name__ == '__main__':
    unittest.main()
