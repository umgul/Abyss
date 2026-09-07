"""fallo 6-sep, "roza": con una tubería de stdin abierta que nunca manda EOF, cada
guion con gancho pagaba el tope de `rutas.leer_stdin()` DOS VECES, porque el atajo
escrito para evitarlo no se comprobaba a tiempo: `continuidad.py` lee stdin,
resuelve, y fija `ABYSS_PROYECTO` "para que quien nos importe después no relea
stdin" — pero `propiocepcion.py` (a quien `continuidad.py` importa justo después)
volvía a llamar a `rutas.leer_stdin()` A SECAS a nivel de módulo, sin mirar antes
si `ABYSS_PROYECTO` ya bastaba. MEDIDO 6-sep con el tope por defecto (3 s):
`continuidad.py --cosecha` tardaba 6,18 s y `varas.py` 6,09 s antes de hacer nada,
mientras `propiocepcion.py` sola tardaba 3,07 s (ese primer toque SÍ hace falta
cuando de verdad no hay otra pista: no es el fallo).

Arreglo con alcance ACOTADO (probado 6-sep, ver abajo): `propiocepcion.py` y
`varas.py` pasan a `rutas.leer_stdin_si_hace_falta()`, que mira
`--proyecto`/`ABYSS_PROYECTO` ANTES de tocar stdin — SEGURO en estos dos porque
ninguno usa `_STDIN` más que para alimentar `rutas.resolver()` (ni `session_id` ni
`transcript_path` ni `cwd` se leen de ahí en ningún otro sitio del fichero).

`continuidad.py` y `vigia.py` se probaron con el MISMO cambio y se revirtió: los
dos usan `session_id`/`transcript_path`/`cwd`/`prompt` del `_STDIN` que leen al
principio para su propia lógica de `__main__` (más abajo en el fichero, no solo
para resolver `proj`/`mem`) — hacerlos perezosos rompía `--arranque`/`--despertar`/
`--verificar` en CUALQUIER invocación que ya trajera `ABYSS_PROYECTO` puesto Y
JSON real por stdin a la vez, que es exactamente como `ayudas.entorno()` monta
casi toda esta batería: con el cambio aplicado a los cuatro, `additionalContext`
salía vacío y `test_despertar.py`, `test_arreglos_revisor.py`, `test_vigia.py` y
otros se rompían. Por eso estos dos siguen con `leer_stdin()` a secas, a
propósito — `LosDosConLogicaPropiaSiguenLeyendoASecas` de abajo lo deja fijado
para que no se "arregle" otra vez de la misma forma equivocada.
"""
import sys
import os
import time
import subprocess
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import unittest
import ayudas as ay


class PropiocepcionNoReleeStdinConAbyssProyectoPuesto(unittest.TestCase):
    def test_propiocepcion_no_espera_el_tope_con_abyss_proyecto_puesto(self):
        proj = ay.nuevo_proyecto()
        (proj / 'memory').mkdir(parents=True, exist_ok=True)
        env = ay.entorno(proj)  # ABYSS_PROYECTO puesto y CONSERVADO
        env['ABYSS_TOPE_STDIN'] = '5'  # si por lo que sea SÍ leyera, tardaría ~5s: de sobra para notarlo

        with subprocess.Popen(
            [sys.executable, str(ay.script('propiocepcion.py'))],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding='utf-8', errors='replace', env=env,
        ) as proc:
            t0 = time.monotonic()
            try:
                # A PROPÓSITO: no se escribe nada en proc.stdin ni se cierra — una
                # tubería abierta que nunca manda EOF, igual que en
                # test_leer_stdin_no_bloquea.py.
                rc = proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
                self.fail('propiocepcion.py tardó más de 8s con ABYSS_PROYECTO puesto: '
                          'seguía leyendo stdin (y pagando su tope) aunque ya no hacía falta')
            elapsed = time.monotonic() - t0
            out = proc.stdout.read()
            err = proc.stderr.read()

        self.assertEqual(rc, 0, f'stdout={out!r} stderr={err!r}')
        self.assertLess(elapsed, 2.0,
                         f'con el fallo tardaría en torno al tope (5s aquí); tardó {elapsed:.1f}s')


class VarasTampocoReleeStdinConAbyssProyectoPuesto(unittest.TestCase):
    def test_varas_index_no_espera_el_tope_con_abyss_proyecto_puesto(self):
        proj = ay.nuevo_proyecto()
        (proj / 'memory').mkdir(parents=True, exist_ok=True)
        env = ay.entorno(proj)
        env['ABYSS_TOPE_STDIN'] = '5'

        with subprocess.Popen(
            [sys.executable, str(ay.script('varas.py')), '--index'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding='utf-8', errors='replace', env=env,
        ) as proc:
            t0 = time.monotonic()
            try:
                rc = proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
                self.fail('varas.py --index se quedó colgado más de 8s con ABYSS_PROYECTO puesto')
            elapsed = time.monotonic() - t0
            out = proc.stdout.read()
            err = proc.stderr.read()

        self.assertEqual(rc, 0, f'stdout={out!r} stderr={err!r}')
        self.assertLess(elapsed, 2.0,
                         f'con el fallo tardaría en torno al tope (5s aquí); tardó {elapsed:.1f}s')


class LosDosQueSoloAlimentanResolverUsanElAtajoPerezoso(unittest.TestCase):
    """Comprobación directa por código fuente (igual que
    `ContinuidadNoHeredaStdinHaciaVaras` en test_leer_stdin_no_bloquea.py): medir
    la cadena de imports real por timing es frágil de más; aquí se comprueba que
    los DOS guiones que solo usan `_STDIN` para alimentar `resolver()`
    (`propiocepcion.py`, `varas.py`) llaman a la variante perezosa."""

    def test_propiocepcion_y_varas_llaman_a_la_variante_perezosa(self):
        raiz_abyss = Path(ay.PKG)
        for nombre in ('propiocepcion.py', 'varas.py'):
            texto = (raiz_abyss / nombre).read_text(encoding='utf-8')
            self.assertIn('rutas.leer_stdin_si_hace_falta(', texto,
                          f'{nombre} debe leer stdin con leer_stdin_si_hace_falta(), '
                          f'no con leer_stdin() a secas (fallo 6-sep)')
            self.assertNotIn('_STDIN = rutas.leer_stdin()', texto)


class LosDosConLogicaPropiaSiguenLeyendoASecas(unittest.TestCase):
    """Fija a propósito el límite del arreglo (ver docstring del módulo): aplicar
    el mismo atajo a `continuidad.py`/`vigia.py` se probó y rompía su propia lógica
    (usan `session_id`/`transcript_path`/`cwd`/`prompt` de `_STDIN`, no solo para
    resolver `proj`/`mem`) en cualquier invocación con `ABYSS_PROYECTO` puesto Y
    JSON real por stdin — que es como `ayudas.entorno()` monta casi toda la
    batería. Si esto empieza a fallar, alguien intentó "arreglarlo" otra vez de la
    misma forma equivocada: antes de tocarlo, correr la suite entera."""

    def test_continuidad_y_vigia_siguen_con_leer_stdin_a_secas(self):
        raiz_abyss = Path(ay.PKG)
        for nombre in ('continuidad.py', 'vigia.py'):
            texto = (raiz_abyss / nombre).read_text(encoding='utf-8')
            self.assertIn('_STDIN = rutas.leer_stdin()', texto,
                          f'{nombre} debe seguir leyendo con leer_stdin() a secas '
                          f'(usa otros campos de _STDIN además de para resolver())')


if __name__ == '__main__':
    unittest.main()
