"""Auditoría con la misma lupa en todos los guiones que aceptan un `transcript_path`
como argumento posicional a mano (ESPECIFICACION.md §2, punto 2 del encargo del
6-sep): ni una bandera (`--proyecto`) ni un directorio (`.`) pueden colar como
transcript_path — `rutas.es_transcript()` exige fichero real + `.jsonl`.

- `exterocepcion.py .` (bug medido: `os.path.exists` aceptaba directorios) ya no
  crea `memory/` en el padre del cwd.
- `modelo.py --proyecto` (bug medido: CUALQUIER primer positional que no fuera
  literalmente la cadena `--estado` se tomaba como transcript_path, incluida la
  propia bandera `--proyecto`) ya no crea `memory/` en el cwd, y cae a
  `ABYSS_PROYECTO` cuando `--proyecto` no trae un valor que resolver.
- `noticias.py .` (mismo bug que exterocepcion) tampoco crea `memory/` en el padre.
- `vigia.py --probar <directorio>` avisa con un mensaje claro en vez de reventar
  con una traza cruda.

`NoticiasDirectorioNoEsTranscript` pasa `ABYSS_SIN_RED=1` (fallo 6-sep, "la suite no
es independiente de la red"): sin caché de `noticias.json`, `noticias.py .` llamaría
de verdad a `news.google.com` — la regla dura 2 del encargo exige la suite sin red.
"""
import sys
import os
import json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import unittest
import ayudas as ay


class ExterocepcionDirectorioNoEsTranscript(unittest.TestCase):
    def test_punto_no_crea_memory_en_el_padre(self):
        # `base` es un contenedor PRIVADO de esta prueba (no el directorio temporal
        # del sistema, compartido por todo el proceso): así el «padre del cwd» que
        # comprobamos no puede ensuciarse con lo que deje cualquier otra prueba, ni
        # ensuciar el temp real de la máquina.
        base = ay.nuevo_proyecto()
        cwd_falso = base / 'subcarpeta'; cwd_falso.mkdir()
        proj = ay.nuevo_proyecto()  # el proyecto real, resuelto por ABYSS_PROYECTO
        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('exterocepcion.py'), ['.'], env, cwd=str(cwd_falso))
        self.assertEqual(r.returncode, 0, r.stderr)
        # con el fallo (c), '.' colaba como transcript_path (os.path.exists acepta
        # directorios) y resolvía proj como el PADRE del cwd, es decir `base`
        self.assertFalse((base / 'memory').exists(),
                          "'.' no debe resolver proj como el padre del cwd")
        self.assertTrue((proj / 'memory').exists(), 'debe caer a ABYSS_PROYECTO')


class ModeloBanderaNoEsTranscript(unittest.TestCase):
    def test_proyecto_sin_valor_no_crea_memory_en_cwd_y_respeta_la_variable(self):
        proj = ay.nuevo_proyecto()
        cwd_ajeno = ay.nuevo_proyecto()  # un cwd cualquiera, DISTINTO del proyecto real
        env = ay.entorno(proj)
        # `--proyecto` sin valor detrás: con el fallo (b), el primer positional se
        # tomaba como transcript_path aunque fuera la propia bandera, y
        # `dirname(abspath('--proyecto'))` == cwd → creaba memory/ ahí, ignorando
        # tanto `--proyecto <valor>` (que aquí no trae valor) como ABYSS_PROYECTO.
        r = ay.ejecutar(ay.script('modelo.py'), ['--proyecto'], env, cwd=str(cwd_ajeno))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse((cwd_ajeno / 'memory').exists(),
                          "'--proyecto' (la bandera) no debe colar como transcript_path")
        self.assertTrue((proj / 'memory').exists(), 'debe respetar ABYSS_PROYECTO')

    def test_estado_con_directorio_no_es_transcript(self):
        proj = ay.nuevo_proyecto()
        env = ay.entorno(proj)
        # --estado con un argumento que NO es un .jsonl real: antes se colaba tal cual
        r = ay.ejecutar(ay.script('modelo.py'), ['--estado', str(proj)], env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('preferido:', r.stdout)


class NoticiasDirectorioNoEsTranscript(unittest.TestCase):
    def test_punto_no_crea_memory_en_el_padre(self):
        base = ay.nuevo_proyecto()  # contenedor privado de ESTA prueba, no el temp compartido
        cwd_falso = base / 'subcarpeta'; cwd_falso.mkdir()
        proj = ay.nuevo_proyecto()
        # ABYSS_SIN_RED=1: sin cache de noticias.json, `noticias.py .` llamaría de
        # verdad a news.google.com (regla dura 2 del encargo: "sin red en la suite").
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
