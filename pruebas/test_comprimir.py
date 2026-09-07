"""`continuidad.py --comprimir` (ESPECIFICACION.md §2.4): gzipea las sesiones más
viejas que el corte y los lectores (aquí, `frases_usuario` a través de
`continuidad.py --falsar`, que llama a `hacer_bolsas()`) deben poder seguir
leyendo el `.jsonl.gz` igual que el `.jsonl` sin comprimir.
"""
import sys
import os
import time
import json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import unittest
import ayudas as ay


class ComprimirDejaSesionesLegibles(unittest.TestCase):
    def test_gz_legible_por_frases_usuario(self):
        proj = ay.nuevo_proyecto()
        sesiones = proj / 'memory' / 'sesiones'
        sid = 'ses-vieja-1'
        primera_frase = 'hola esto es una frase de prueba distintiva y bastante única para el test'
        ruta = ay.sesion_simple(sesiones / f'{sid}.jsonl',
                                 [primera_frase, 'segunda frase de la misma sesión antigua'])

        # la hacemos "vieja": mtime 40 días atrás (más que el corte por defecto de 30)
        vieja = time.time() - 40 * 86400
        os.utime(ruta, (vieja, vieja))

        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('continuidad.py'), ['--comprimir'], env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('sesiones comprimidas: 1', r.stdout)

        gz = sesiones / f'{sid}.jsonl.gz'
        self.assertTrue(gz.exists(), 'debe quedar el .jsonl.gz')
        self.assertFalse(ruta.exists(), 'el .jsonl sin comprimir debe desaparecer')

        bolsas_path = proj / 'memory' / 'bolsas.json'
        self.assertFalse(bolsas_path.exists())

        # --falsar llama a hacer_bolsas(), que usa frases_usuario() sobre CADA sesión
        # (.jsonl y .jsonl.gz por igual, §2.4)
        r2 = ay.ejecutar(ay.script('continuidad.py'), ['--falsar'], env)
        self.assertEqual(r2.returncode, 0, r2.stderr)
        self.assertTrue(bolsas_path.exists())

        bolsas = json.loads(bolsas_path.read_text(encoding='utf-8'))
        self.assertIn(sid, bolsas)
        self.assertEqual(bolsas[sid]['primera'], primera_frase)

    def test_no_toca_sesiones_mas_nuevas_que_el_corte(self):
        proj = ay.nuevo_proyecto()
        sesiones = proj / 'memory' / 'sesiones'
        ay.sesion_simple(sesiones / 'ses-reciente.jsonl', ['una sesión de ayer mismo, no hay que comprimirla'])
        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('continuidad.py'), ['--comprimir'], env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('sesiones comprimidas: 0', r.stdout)
        self.assertTrue((sesiones / 'ses-reciente.jsonl').exists())
        self.assertFalse((sesiones / 'ses-reciente.jsonl.gz').exists())


if __name__ == '__main__':
    unittest.main()
