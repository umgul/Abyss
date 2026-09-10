# -*- coding: utf-8 -*-
"""Que nadie vuelva a colar un `sys.stdout.reconfigure(...)` suelto en `abyss/`.

## El fallo que esto vigila

34 módulos hacían `sys.stdout.reconfigure(encoding="utf-8")` sin tocar la página de
códigos de la consola (medido con `chcp` en la máquina de desarrollo: la página activa
en una consola española suele ser la 850, y ahí los dos bytes de una `ñ` —C3 y B1— se
pintan como dos símbolos sueltos). No era un fallo de codificación, era que la salida y
la ventana hablaban idiomas distintos — y encima solo se veía en una consola de verdad:
por una tubería o redirigido a fichero, la salida sale bien, que es justo por qué había
sobrevivido tanto. `abyss/consola.py` (`preparar()`) lo arregla: pone la página en UTF-8
ANTES de reconfigurar la salida, y la devuelve al salir. El barrido del 10-sep enchufó
`consola.preparar()` en los 33 módulos de `abyss/` que tocaban la salida por su cuenta
(19 ya lo llevaban; 15 más — `gestos.py`, `imagen.py`, `infografia.py`, `kinetica.py`,
`lectura_visual.py`, `lienzo.py`, `mundo.py`, `ojo.py`, `pintor.py`, `presenta.py`,
`render3d.py`, `taller.py`, `video_composicion.py`, `video_pintura.py`, `volumen.py` — se
arreglaron ese día, cada uno a mano porque la llamada vivía DENTRO de un
`if __name__ == '__main__':`, no arriba del fichero, y un reemplazo automático se habría
llevado por delante ese matiz).

Sin esta prueba, un módulo nuevo (o uno de estos 33 "reparado" mal en un cambio futuro)
podría reintroducir `sys.stdout.reconfigure(...)`/`sys.stderr.reconfigure(...)` a pelo y
nadie lo notaría hasta volver a ver los acentos rotos en una consola de verdad — el mismo
motivo por el que el fallo original sobrevivió tanto.

## Cómo escanea

Por `ast`, igual que el escáner de literales de `test_instalador_idioma.py`
(`NingunTextoQuedaFueraDelDiccionario`): recorre cada `.py` DIRECTAMENTE dentro de
`abyss/` (sin bajar a subcarpetas — no las hay) y busca cualquier `Call` cuya forma sea
`<algo>.stdout.reconfigure(...)` o `<algo>.stderr.reconfigure(...)`. Con `ast` en vez de
una búsqueda de texto porque lo que importa es la LLAMADA real, no la palabra suelta en
un comentario o una cadena (este mismo fichero, por ejemplo, menciona la llamada varias
veces en el docstring de arriba, y no debe autoacusarse).

Única excepción: `abyss/consola.py`, que es donde la llamada VIVE a propósito (dentro de
`preparar()`) — el propio encargo dice "consola.py tiene el suyo a propósito y NO se
toca". `instalar.py`, en la raíz del repo (no dentro de `abyss/`), tiene un fallback
documentado con la misma forma por si `consola.py` no cargara por ruta; queda fuera del
barrido a propósito (no es un módulo de `abyss/`, y su comentario ya explica por qué
sigue ahí) — `test_falsador_cazaria_ese_mismo_fallback_si_estuviera_en_abyss` demuestra
que el escáner SÍ lo cazaría si viviera donde no debe.
"""
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
    """`True` si `nodo` es una llamada con la forma `<algo>.stdout.reconfigure(...)`
    o `<algo>.stderr.reconfigure(...)` — sin exigir que `<algo>` sea literalmente el
    nombre `sys` (un `import sys as s` seguiría teniendo esta forma, y no es lo que
    este paquete hace nunca, pero el escáner no depende de ese detalle)."""
    if not isinstance(nodo, ast.Call):
        return False
    func = nodo.func
    if not (isinstance(func, ast.Attribute) and func.attr == 'reconfigure'):
        return False
    base = func.value
    return isinstance(base, ast.Attribute) and base.attr in ('stdout', 'stderr')


def _reconfigures_sueltos(ruta):
    """Lista de `'ruta:lineno'` para cada llamada sospechosa en `ruta`. `ruta` puede
    no existir como `.py` válido (el falsador usa un fichero de mentira) — cualquier
    fallo de parseo se deja subir, porque un `.py` real del paquete debe parsear
    siempre; si no parsea, la prueba debe reventar igual de ruidosa que un error de
    sintaxis real."""
    fuente = Path(ruta).read_text(encoding='utf-8')
    arbol = ast.parse(fuente, filename=str(ruta))
    return [f'{ruta}:{nodo.lineno}' for nodo in ast.walk(arbol)
            if _es_reconfigure_de_stdout_o_stderr(nodo)]


def _modulos_abyss():
    """Cada `.py` directamente dentro de `abyss/`, salvo `_EXCLUIDO` — no hace falta
    bajar a subcarpetas: `abyss/` no tiene ninguna con código (medido con `find`)."""
    return sorted(p for p in ay.PKG.glob('*.py') if p.name != _EXCLUIDO)


class NingunModuloDeAbyssReconfiguraSueltoLaSalida(unittest.TestCase):
    """La prueba real: sobre el código de verdad, hoy, ninguno de los `.py` de
    `abyss/` (salvo `consola.py`) debe reconfigurar `stdout`/`stderr` sin pasar por
    `consola.preparar()`."""

    def test_sin_reconfigure_suelto_en_ningun_modulo(self):
        hallazgos = []
        for ruta in _modulos_abyss():
            hallazgos.extend(_reconfigures_sueltos(ruta))
        self.assertEqual(
            hallazgos, [],
            'sys.stdout/stderr.reconfigure(...) suelto (sin pasar por consola.preparar()) '
            'en:\n' + '\n'.join(hallazgos))

    def test_todos_los_modulos_que_tocan_la_salida_llaman_a_consola_preparar(self):
        """Complemento del anterior: no basta con que no haya `reconfigure` suelto,
        cada uno de los 33 módulos que SÍ tocaban la salida (19 de antes + los 15 de
        este barrido) debe llamar a `consola.preparar()` de verdad — así una futura
        limpieza que borrara la llamada entera (sin dejar ningún `reconfigure`
        suelto tampoco) no pasaría desapercibida como "arreglada"."""
        se_esperaba = {
            # ya enchufados antes de este barrido (9-sep)
            'auditar.py', 'continuidad.py', 'cuerpo.py', 'exterocepcion.py', 'fondo.py',
            'huella.py', 'kinetico.py', 'kinetico_servidor.py', 'lector_pdf.py',
            'mapa_codigo.py', 'modelo.py', 'navegador.py', 'navegador_cdp.py',
            'noticias.py', 'parentesis.py', 'propiocepcion.py', 'varas.py', 'vigia.py',
            # los 15 de este barrido (10-sep)
            'gestos.py', 'imagen.py', 'infografia.py', 'kinetica.py', 'lectura_visual.py',
            'lienzo.py', 'mundo.py', 'ojo.py', 'pintor.py', 'presenta.py', 'render3d.py',
            'taller.py', 'video_composicion.py', 'video_pintura.py', 'volumen.py',
        }
        sin_preparar = [nombre for nombre in se_esperaba
                        if 'consola.preparar()' not in (ay.PKG / nombre).read_text(encoding='utf-8')]
        self.assertEqual(sin_preparar, [], f'sin consola.preparar(): {sin_preparar}')


class FalsadorElEscanerCazaUnReconfigureSueltoDeVerdad(unittest.TestCase):
    """Sin esto, `test_sin_reconfigure_suelto_en_ningun_modulo` podría estar
    pasando en verde porque el escáner no reconoce ninguna llamada (p. ej. una
    forma de `ast` mal escrita), no porque el código esté limpio de verdad. Mismo
    criterio que `test_el_propio_escaner_caza_una_cadena_suelta_de_verdad` en
    `test_instalador_idioma.py`: un fichero de mentira, con la forma mínima real
    del fallo, DEBE saltar."""

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
        """El hallazgo real (ver docstring de cabecera): en 15 de los 15 módulos la
        llamada vivía dentro de `if __name__ == '__main__':`, no arriba del
        fichero. El escáner tiene que cazarla ahí igual — si solo mirara el nivel
        superior del módulo, este barrido habría pasado igual de en blanco con el
        fallo todavía dentro."""
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
        """Falsador del falsador: un `sys.stdout.write(...)` normal, o
        `sys.stdout.flush()`, no debe saltar — si esto fallara, el escáner sería
        demasiado ancho y `test_sin_reconfigure_suelto_en_ningun_modulo` estaría
        vigilando cosas que no le tocan (varios módulos de `abyss/` hacen
        `sys.stdout.flush()` de verdad, ver `taller.py`/`kinetica.py`)."""
        señuelo = self._escribir("import sys\nsys.stdout.write('hola')\nsys.stdout.flush()\n")
        self.assertEqual(_reconfigures_sueltos(señuelo), [])

    def test_no_caza_la_mencion_en_un_comentario_o_una_cadena(self):
        """Falsador de un escáner por texto plano en vez de `ast`: la palabra
        `reconfigure` puede aparecer en un comentario o docstring (como en la
        cabecera de este mismo fichero de pruebas) sin que haya ninguna llamada
        real — no debe contar."""
        señuelo = self._escribir(
            '# esto menciona sys.stdout.reconfigure(encoding="utf-8") en un comentario\n'
            '"""y también en un docstring: sys.stderr.reconfigure(encoding=\'utf-8\')"""\n'
            'print("no llamo a nada")\n')
        self.assertEqual(_reconfigures_sueltos(señuelo), [])

    def test_no_se_autoacusa_este_propio_fichero_de_pruebas(self):
        """Este mismo fichero menciona la llamada varias veces en su docstring de
        cabecera (para explicar qué vigila) — el escáner sobre su propio código NO
        debe encontrar nada, o la prueba se estaría rompiendo a sí misma."""
        self.assertEqual(_reconfigures_sueltos(Path(__file__)), [])


class ConsolaPyQuedaExcluidoAPropositoYElFallbackDeInstalarQuedaFueraDeAmbito(unittest.TestCase):
    """`abyss/consola.py` es donde la llamada vive a propósito (dentro de
    `preparar()`): el escaneo real la deja pasar por nombre de fichero, no porque
    el escáner no la vea. `instalar.py` (la raíz del repo, no `abyss/`) tiene un
    fallback documentado con la misma forma; queda fuera del barrido porque no es
    un módulo de `abyss/` — el falsador de abajo prueba que el escáner SÍ lo
    cazaría si alguien lo copiara dentro de `abyss/` por error."""

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
