"""Ningún guion que acepta `transcript_path` como posicional (ESPECIFICACION.md §2)
debe aceptar una bandera (`--proyecto`) ni un directorio (`.`) como si lo fuera:
`rutas.es_transcript()` exige fichero real + `.jsonl`."""
import sys
import os
import json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import unittest
import ayudas as ay


class ExterocepcionDirectorioNoEsTranscript(unittest.TestCase):
    def test_punto_no_crea_memory_en_el_padre(self):
        # `base` es un contenedor privado de esta prueba (no el temp compartido del
        # proceso): el «padre del cwd» que comprobamos no se ensucia con otras pruebas.
        base = ay.nuevo_proyecto()
        cwd_falso = base / 'subcarpeta'; cwd_falso.mkdir()
        proj = ay.nuevo_proyecto()  # el proyecto real, resuelto por ABYSS_PROYECTO
        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('exterocepcion.py'), ['.'], env, cwd=str(cwd_falso))
        self.assertEqual(r.returncode, 0, r.stderr)
        # os.path.exists() acepta directorios, por eso '.' podría colar como transcript_path
        self.assertFalse((base / 'memory').exists(),
                          "'.' no debe resolver proj como el padre del cwd")
        self.assertTrue((proj / 'memory').exists(), 'debe caer a ABYSS_PROYECTO')


class ModeloBanderaNoEsTranscript(unittest.TestCase):
    def test_proyecto_sin_valor_no_crea_memory_en_cwd_y_respeta_la_variable(self):
        proj = ay.nuevo_proyecto()
        cwd_ajeno = ay.nuevo_proyecto()  # un cwd cualquiera, DISTINTO del proyecto real
        env = ay.entorno(proj)
        # `--proyecto` sin valor detrás: si el primer positional se toma como
        # transcript_path, `dirname(abspath('--proyecto'))` == cwd, y crearía memory/ ahí.
        r = ay.ejecutar(ay.script('modelo.py'), ['--proyecto'], env, cwd=str(cwd_ajeno))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse((cwd_ajeno / 'memory').exists(),
                          "'--proyecto' (la bandera) no debe colar como transcript_path")
        self.assertTrue((proj / 'memory').exists(), 'debe respetar ABYSS_PROYECTO')

    def test_estado_con_directorio_no_es_transcript(self):
        proj = ay.nuevo_proyecto()
        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('modelo.py'), ['--estado', str(proj)], env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('preferido:', r.stdout)


class NoticiasDirectorioNoEsTranscript(unittest.TestCase):
    def test_punto_no_crea_memory_en_el_padre(self):
        base = ay.nuevo_proyecto()  # contenedor privado de ESTA prueba, no el temp compartido
        cwd_falso = base / 'subcarpeta'; cwd_falso.mkdir()
        proj = ay.nuevo_proyecto()
        # ABYSS_SIN_RED=1: sin caché de noticias.json, `noticias.py .` llamaría de
        # verdad a news.google.com.
        env = ay.entorno(proj, ABYSS_SIN_RED='1')
        r = ay.ejecutar(ay.script('noticias.py'), ['.'], env, cwd=str(cwd_falso))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse((base / 'memory').exists(),
                          "'.' no debe resolver proj como el padre del cwd")
        self.assertTrue((proj / 'memory').exists(), 'debe caer a ABYSS_PROYECTO')


class VigiaProbarConDirectorioAvisaClaro(unittest.TestCase):
    def test_probar_con_directorio_no_revienta(self):
        proj = ay.nuevo_proyecto()
        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('vigia.py'), ['--probar', str(proj)], env)
        self.assertEqual(r.returncode, 1)
        self.assertNotIn('Traceback', r.stderr)
        self.assertIn('transcript', r.stdout)


if __name__ == '__main__':
    unittest.main()
