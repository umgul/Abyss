"""`open()` sin gestor de contexto en varios guiones (fallo 6-sep, "roza"): MEDIDO
que la suite escupía 8 `ResourceWarning` de ficheros sin cerrar en cada corrida
(`settings.json`, `settings.json.tmp-abyss`, `abyss_manifiesto.json.tmp-abyss`,
`config.json.tmp-abyss`, y el mismo patrón en `varas.py`, `continuidad.py`,
`exterocepcion.py`, `noticias.py`, `modelo.py`). Ahora todo pasa por `with open(...)`.

Cada caso se lanza como lo haría un gancho real (por subprocess, igual que el resto
de la suite) con `PYTHONWARNINGS=always::ResourceWarning` para que el HIJO imprima
por su stderr cualquier fichero que quede sin cerrar (CPython emite el aviso en
cuanto el recuento de referencias libera el objeto — normalmente antes de que el
proceso termine, no hace falta esperar a un ciclo de gc). Con el fallo, `stderr`
llevaba la palabra «ResourceWarning»; con el arreglo, no debe aparecer nunca.
"""
import sys
import os
import json
import time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import unittest
import ayudas as ay


def _entorno_con_avisos(proj, **extra):
    env = ay.entorno(proj, **extra)
    env['PYTHONWARNINGS'] = 'always::ResourceWarning'
    return env


class InstalarSinFicherosSinCerrar(unittest.TestCase):
    def test_listar_no_deja_resource_warning(self):
        proj = ay.nuevo_proyecto()
        settings_ruta = proj / 'settings.json'
        settings_ruta.write_text(json.dumps({'showThinkingSummaries': True, 'hooks': {}}), encoding='utf-8')
        env = _entorno_con_avisos(proj)
        r = ay.ejecutar(ay.RAIZ / 'instalar.py', ['--listar', '--settings', str(settings_ruta)], env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn('ResourceWarning', r.stderr, r.stderr)


class VarasIndexSinFicherosSinCerrar(unittest.TestCase):
    def test_index_no_deja_resource_warning(self):
        proj = ay.nuevo_proyecto()
        mem = proj / 'memory'
        mem.mkdir(parents=True, exist_ok=True)
        (mem / 'una-ficha.md').write_text('---\ntype: reference\n---\ncontenido de la ficha [[otra-ficha]]\n',
                                           encoding='utf-8')
        (mem / 'otra-ficha.md').write_text('---\ntype: reference\n---\notro contenido\n', encoding='utf-8')
        (mem / 'MEMORY.md').write_text('# Mi memoria\n[una](una-ficha.md)\n[otra](otra-ficha.md)\n',
                                        encoding='utf-8')
        env = _entorno_con_avisos(proj)
        r = ay.ejecutar(ay.script('varas.py'), ['--index'], env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn('ResourceWarning', r.stderr, r.stderr)


class ContinuidadCierreSinFicherosSinCerrar(unittest.TestCase):
    def test_cierre_no_deja_resource_warning(self):
        proj = ay.nuevo_proyecto()
        sid = 'ses-sin-warnings-1'
        tp = proj / f'{sid}.jsonl'
        ay.sesion_simple(tp, ['hola, sesión de prueba para comprobar que no quedan ficheros sin cerrar'])
        entrada = json.dumps({'session_id': sid, 'transcript_path': str(tp), 'cwd': str(proj)})
        env = _entorno_con_avisos(proj)
        r = ay.ejecutar(ay.script('continuidad.py'), ['--cierre'], env, entrada=entrada)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn('ResourceWarning', r.stderr, r.stderr)


class ModeloEstadoSinFicherosSinCerrar(unittest.TestCase):
    def test_estado_no_deja_resource_warning(self):
        proj = ay.nuevo_proyecto()
        mem = proj / 'memory'
        mem.mkdir(parents=True, exist_ok=True)
        (mem / 'modelo_preferido.json').write_text(
            json.dumps({'modelo': 'claude-fable-5-1', 'ts': time.time()}), encoding='utf-8')
        env = _entorno_con_avisos(proj)
        r = ay.ejecutar(ay.script('modelo.py'), ['--estado'], env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn('ResourceWarning', r.stderr, r.stderr)


if __name__ == '__main__':
    unittest.main()
