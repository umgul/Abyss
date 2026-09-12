"""`continuidad.py --despertar`: cada prompt añade `[tiempo]`; `[mundo]` puede
faltar sin red (ESPECIFICACION.md §6). Aquí se preseeda `lugar.json`/`meteo.json`
para que la prueba sea determinista sin depender de la red de la máquina."""
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
        # preseeda lugar/meteo para que [mundo] no dependa de la red real
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
        # lugar/meteo preseedados y cacheados: [mundo] debe traer esos datos
        self.assertIn('[mundo]', contexto)
        self.assertIn('Villafingida', contexto)

    def test_despertar_sin_pista_de_proyecto_calla(self):
        """Sin `transcript_path` ni `cwd`, `rutas.es_mio()` no sabe a quién pertenece
        el hilo y calla (fail-closed) aunque `ABYSS_PROYECTO` resuelva `mem`: «sin
        proyecto no hay datos» es distinto de «no sé si este hilo es mío»."""
        proj = ay.nuevo_proyecto()
        entrada = json.dumps({'session_id': 'sid-sin-pista', 'prompt': 'hola'})
        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('continuidad.py'), ['--despertar'], env, entrada=entrada)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), '')


if __name__ == '__main__':
    unittest.main()
