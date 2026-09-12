# -*- coding: utf-8 -*-
"""Ningún módulo de `abyss/` (salvo `consola.py`) debe llamar a
`.reconfigure(...)` en stdout/stderr sin pasar por `consola.preparar()`.
Escanea con `ast` la llamada real, no el texto — así no se autoacusa."""
import ast
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ayudas as ay

# el propio consola.py es donde la llamada vive a propósito: excluido por nombre,
# no por ruta relativa, para que el escaneo no dependa de cómo se invoque pytest
_EXCLUIDO = 'consola.py'


def _es_reconfigure_de_stdout_o_stderr(nodo):
    """`True` si `nodo` tiene la forma `<algo>.stdout.reconfigure(...)` o
    `<algo>.stderr.reconfigure(...)` — sin exigir que `<algo>` sea literalmente
    `sys`: el escáner no depende de ese detalle."""
    if not isinstance(nodo, ast.Call):
        return False
    func = nodo.func
    if not (isinstance(func, ast.Attribute) and func.attr == 'reconfigure'):
        return False
    base = func.value
    return isinstance(base, ast.Attribute) and base.attr in ('stdout', 'stderr')


def _reconfigures_sueltos(ruta):
    """Lista de `'ruta:lineno'` para cada llamada sospechosa en `ruta`. Un fallo
    de parseo se deja subir sin capturar: un `.py` real del paquete debe
    parsear siempre, y si no, la prueba debe reventar igual de ruidosa."""
    fuente = Path(ruta).read_text(encoding='utf-8')
    arbol = ast.parse(fuente, filename=str(ruta))
    return [f'{ruta}:{nodo.lineno}' for nodo in ast.walk(arbol)
            if _es_reconfigure_de_stdout_o_stderr(nodo)]


def _modulos_abyss():
    """Cada `.py` directamente dentro de `abyss/`, salvo `_EXCLUIDO` — no hace
    falta bajar a subcarpetas: `abyss/` no tiene ninguna con código."""
    return sorted(p for p in ay.PKG.glob('*.py') if p.name != _EXCLUIDO)


class NingunModuloDeAbyssReconfiguraSueltoLaSalida(unittest.TestCase):
    def test_sin_reconfigure_suelto_en_ningun_modulo(self):
        hallazgos = []
        for ruta in _modulos_abyss():
            hallazgos.extend(_reconfigures_sueltos(ruta))
        self.assertEqual(
            hallazgos, [],
            'sys.stdout/stderr.reconfigure(...) suelto (sin pasar por consola.preparar()) '
            'en:\n' + '\n'.join(hallazgos))

    def test_todos_los_modulos_que_tocan_la_salida_llaman_a_consola_preparar(self):
        """Complementa el anterior: no basta con que no haya `reconfigure` suelto,
        cada módulo que toca la salida debe llamar a `consola.preparar()` de
        verdad — así una limpieza que borrara la llamada entera no pasaría
        desapercibida."""
        se_esperaba = {
            'auditar.py', 'continuidad.py', 'cuerpo.py', 'exterocepcion.py', 'fondo.py',
            'huella.py', 'kinetico.py', 'kinetico_servidor.py', 'lector_pdf.py',
            'mapa_codigo.py', 'modelo.py', 'navegador.py', 'navegador_cdp.py',
            'noticias.py', 'parentesis.py', 'propiocepcion.py', 'varas.py', 'vigia.py',
            'gestos.py', 'imagen.py', 'infografia.py', 'kinetica.py', 'lectura_visual.py',
            'lienzo.py', 'mundo.py', 'ojo.py', 'pintor.py', 'presenta.py', 'render3d.py',
            'taller.py', 'video_composicion.py', 'video_pintura.py', 'volumen.py',
        }
        sin_preparar = [nombre for nombre in se_esperaba
                        if 'consola.preparar()' not in (ay.PKG / nombre).read_text(encoding='utf-8')]
        self.assertEqual(sin_preparar, [], f'sin consola.preparar(): {sin_preparar}')


class FalsadorElEscanerCazaUnReconfigureSueltoDeVerdad(unittest.TestCase):
    """Sin esto, el escáner podría estar pasando en verde porque no reconoce
    ninguna llamada (un patrón de `ast` mal escrito), no porque el código esté
    limpio de verdad: un fichero de mentira con la forma mínima real debe saltar."""

    def _escribir(self, cuerpo):
        tmp = Path(tempfile.mkdtemp(prefix='abyss_reconfigure_falso_'))
        señuelo = tmp / 'senuelo.py'
        señuelo.write_text(cuerpo, encoding='utf-8')
        return señuelo

    def test_caza_stdout_reconfigure_suelto(self):
        señuelo = self._escribir(
            "import sys\n"
            "try:\n"
            "    sys.stdout.reconfigure(encoding='utf-8')\n"
            "except Exception:\n"
            "    pass\n")
        hallazgos = _reconfigures_sueltos(señuelo)
        self.assertEqual(len(hallazgos), 1, hallazgos)
        self.assertTrue(hallazgos[0].endswith(':3'), hallazgos)

    def test_caza_stderr_reconfigure_suelto_tambien(self):
        señuelo = self._escribir("import sys\nsys.stderr.reconfigure(encoding='utf-8')\n")
        hallazgos = _reconfigures_sueltos(señuelo)
        self.assertEqual(len(hallazgos), 1, hallazgos)

    def test_caza_dentro_de_una_funcion_no_solo_arriba_del_fichero(self):
        """La llamada puede vivir dentro de `if __name__ == '__main__':`, no
        solo arriba del fichero: el escáner tiene que cazarla ahí igual, no
        solo al nivel superior del módulo."""
        señuelo = self._escribir(
            "import sys\n"
            "def _cli(argv):\n"
            "    return 0\n"
            "if __name__ == '__main__':\n"
            "    try:\n"
            "        sys.stdout.reconfigure(encoding='utf-8')\n"
            "    except Exception:\n"
            "        pass\n"
            "    sys.exit(_cli(sys.argv[1:]))\n")
        hallazgos = _reconfigures_sueltos(señuelo)
        self.assertEqual(len(hallazgos), 1, hallazgos)

    def test_no_caza_una_llamada_que_no_es_reconfigure(self):
        """Falsador del falsador: `sys.stdout.write(...)`/`.flush()` normales no
        deben saltar, o el escáner vigilaría cosas que no le tocan (varios
        módulos sí llaman a `.flush()` de verdad)."""
        señuelo = self._escribir("import sys\nsys.stdout.write('hola')\nsys.stdout.flush()\n")
        self.assertEqual(_reconfigures_sueltos(señuelo), [])

    def test_no_caza_la_mencion_en_un_comentario_o_una_cadena(self):
        """Falsador de un escáner por texto plano en vez de `ast`: la palabra
        `reconfigure` puede aparecer en un comentario o docstring sin que haya
        ninguna llamada real — no debe contar."""
        señuelo = self._escribir(
            '# esto menciona sys.stdout.reconfigure(encoding="utf-8") en un comentario\n'
            '"""y también en un docstring: sys.stderr.reconfigure(encoding=\'utf-8\')"""\n'
            'print("no llamo a nada")\n')
        self.assertEqual(_reconfigures_sueltos(señuelo), [])

    def test_no_se_autoacusa_este_propio_fichero_de_pruebas(self):
        """Este fichero menciona `reconfigure` en su propio docstring: el
        escáner sobre su propio código no debe encontrar nada, o se estaría
        rompiendo a sí mismo."""
        self.assertEqual(_reconfigures_sueltos(Path(__file__)), [])


class ConsolaPyQuedaExcluidoAPropositoYElFallbackDeInstalarQuedaFueraDeAmbito(unittest.TestCase):
    """`consola.py` es donde la llamada vive a propósito: el escaneo la deja
    pasar por nombre de fichero, no porque no la vea. `instalar.py` (raíz del
    repo, no `abyss/`) tiene el mismo patrón pero queda fuera por no ser de `abyss/`."""

    def test_consola_py_de_verdad_lleva_la_llamada_pero_queda_excluido(self):
        ruta_consola = ay.PKG / 'consola.py'
        # de verdad la lleva (si esto fallara, la exclusión estaría probando que no
        # excluye nada: consola.py habría dejado de reconfigurar la salida)
        self.assertTrue(_reconfigures_sueltos(ruta_consola),
                         'consola.py debería llevar su propio reconfigure dentro de preparar()')
        self.assertNotIn(ruta_consola, _modulos_abyss(),
                          'consola.py no debe entrar en el barrido de módulos')

    def test_falsador_cazaria_ese_mismo_fallback_si_estuviera_en_abyss(self):
        fallback_de_instalar_py = (
            "import os, sys\n"
            "try:\n"
            "    pass  # aqui iria la carga de consola.py por ruta\n"
            "except Exception:\n"
            "    try:\n"
            "        sys.stdout.reconfigure(encoding='utf-8')\n"
            "    except Exception:\n"
            "        pass\n")
        tmp = Path(tempfile.mkdtemp(prefix='abyss_fallback_falso_'))
        copia_en_abyss = tmp / 'copia_del_fallback.py'
        copia_en_abyss.write_text(fallback_de_instalar_py, encoding='utf-8')
        self.assertTrue(_reconfigures_sueltos(copia_en_abyss),
                         'el escáner debería cazar este fallback si viviera dentro de abyss/')


if __name__ == '__main__':
    unittest.main()
