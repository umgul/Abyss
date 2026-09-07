# -*- coding: utf-8 -*-
"""`instalar.py` T5.1 (ESPECIFICACION_TANDA5.md): el instalador resuelve las
dependencias de terceros de cada módulo por sí mismo, con consentimiento y sin
mentir. Regla dura 6 del encargo: NADA de esto instala un paquete de verdad —
cada prueba que ejercita `--instalar-dependencias`/`instalar_dependencias()`
monkeypatchea `subprocess.run` (en proceso, sobre el módulo cargado) o lo
sustituye en un proceso hijo por `sitecustomize.py` (mismo método que
`test_imagen_dependencias_opcionales.py`) — nunca sale a la red, nunca llama a
un `pip` real.

Igual que `test_instalador.py`/`test_instalador_roza.py`: se importa
`instalar.py` DIRECTAMENTE por ruta de fichero (no hace red ni
`rutas.resolver()` a nivel de módulo)."""
import sys
import os
import re
import textwrap
import tempfile
import importlib.util
from pathlib import Path
from unittest import mock
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import unittest
import ayudas as ay


def _cargar_instalador():
    ruta = ay.RAIZ / 'instalar.py'
    spec = importlib.util.spec_from_file_location('abyss_instalador_bajo_prueba_dependencias', str(ruta))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _R:
    """Sustituto mínimo de `subprocess.CompletedProcess`: solo lo que
    `instalar.py` lee de verdad (`returncode`, `stdout`, `stderr`)."""

    def __init__(self, returncode=0, stdout='', stderr=''):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


# ---------------------------------------------------------------------------------
# Registro de dependencias: agrupado por módulo, comprobado con un import real.
# ---------------------------------------------------------------------------------
class RegistroDeDependenciasPorModulo(unittest.TestCase):
    def test_cada_entrada_declara_los_tres_campos(self):
        inst = _cargar_instalador()
        self.assertTrue(inst.DEPENDENCIAS, 'DEPENDENCIAS no debe estar vacío')
        for mid, entradas in inst.DEPENDENCIAS.items():
            self.assertIn(mid, inst.MODULOS_POR_ID, f'{mid}: debe ser un id real de MODULOS')
            self.assertTrue(entradas, f'{mid}: sin dependencias declaradas')
            for e in entradas:
                for campo in ('import_nombre', 'pip_nombre', 'para'):
                    self.assertIn(campo, e, f'{mid}: falta el campo "{campo}" en {e}')
                    self.assertTrue(str(e[campo]).strip(), f'{mid}: "{campo}" vacío en {e}')

    def test_import_disponible_es_un_import_real_no_una_lista_fija(self):
        """`_import_disponible` de verdad importa (bajo el intérprete que se le
        pida) — no consulta ninguna lista de paquetes "conocidos". La
        biblioteca estándar siempre "está"; un nombre inventado, nunca."""
        inst = _cargar_instalador()
        self.assertTrue(inst._import_disponible('os'))
        self.assertFalse(inst._import_disponible('paquete_inventado_para_esta_prueba_abyss'))

    def test_import_disponible_usa_el_python_exe_pedido_no_el_de_la_prueba(self):
        """Si `--python <exe>` señala OTRO intérprete, la comprobación debe
        correr bajo ESE — nunca bajo el que ejecuta el propio instalador."""
        inst = _cargar_instalador()
        vistos = []

        def _run_falso(cmd, **kw):
            vistos.append(cmd)
            return _R(returncode=0)

        with mock.patch.object(inst.subprocess, 'run', side_effect=_run_falso):
            inst._import_disponible('numpy', python_exe='C:\\otro\\python.exe')
        self.assertEqual(vistos[0][0], 'C:\\otro\\python.exe')
        self.assertIn('numpy', vistos[0][-1])


# ---------------------------------------------------------------------------------
# T5.1, prueba de la especificación: "--dependencias sobre un entorno con una
# dependencia presente y otra ausente marca exactamente esa".
# ---------------------------------------------------------------------------------
class EstadoDeDependenciasMarcaExactamenteLoQueFalta(unittest.TestCase):
    def test_una_presente_y_otra_ausente_se_marcan_por_separado(self):
        inst = _cargar_instalador()
        presentes = {'PIL', 'numpy'}  # de 'imagen': Pillow y numpy sí; el resto no

        with mock.patch.object(inst, '_import_disponible', side_effect=lambda n, python_exe=None: n in presentes):
            estado = inst._estado_dependencias(['imagen'])

        por_import = {e['import_nombre']: e for e in estado['imagen']}
        self.assertFalse(por_import['PIL']['falta'], 'Pillow está presente: no debe marcarse "falta"')
        self.assertFalse(por_import['numpy']['falta'], 'numpy está presente: no debe marcarse "falta"')
        self.assertTrue(por_import['imageio_ffmpeg']['falta'], 'imageio-ffmpeg está ausente: debe marcarse')
        self.assertTrue(por_import['cv2']['falta'], 'opencv-python (opcional) ausente: se marca igual que las demás')

    def test_alternativa_satisfecha_por_una_no_marca_la_otra_como_falta(self):
        """lector_pdf: basta con fitz O pypdf. Si fitz está, pypdf NO debe
        contar como "falta" aunque su propio import falle — instalar las dos
        sería instalar de más para cubrir lo mismo."""
        inst = _cargar_instalador()
        with mock.patch.object(inst, '_import_disponible', side_effect=lambda n, python_exe=None: n == 'fitz'):
            estado = inst._estado_dependencias(['lector_pdf'])
        por_import = {e['import_nombre']: e for e in estado['lector_pdf']}
        self.assertFalse(por_import['fitz']['falta'])
        self.assertFalse(por_import['pypdf']['falta'], 'con fitz presente, pypdf no hace falta instalarlo también')

    def test_ninguna_alternativa_presente_pide_instalar_solo_la_preferida(self):
        inst = _cargar_instalador()
        with mock.patch.object(inst, '_import_disponible', return_value=False):
            paquetes = inst._paquetes_a_instalar(['lector_pdf'])
        self.assertEqual(paquetes, [('lector_pdf', 'PyMuPDF')],
                          'sin ninguna alternativa presente, se pide solo la primera declarada (PyMuPDF)')


# ---------------------------------------------------------------------------------
# T5.1, prueba de la especificación: "--instalar-dependencias imagen llama a
# sys.executable -m pip install con los paquetes de imagen y con ninguno más".
# ---------------------------------------------------------------------------------
class InstalarDependenciasLlamaAPipConLosPaquetesDelModuloYNadaMas(unittest.TestCase):
    def test_solo_los_paquetes_de_imagen_ninguno_mas(self):
        inst = _cargar_instalador()
        comandos = []

        def _run_falso(cmd, **kw):
            comandos.append(list(cmd))
            if '-c' in cmd:
                return _R(returncode=1)  # nada presente en el módulo bajo prueba
            return _R(returncode=0)

        with mock.patch.object(inst.subprocess, 'run', side_effect=_run_falso):
            mensajes, ok = inst.instalar_dependencias(['imagen'], python_exe='python-de-prueba')

        self.assertTrue(ok, mensajes)
        llamadas_install = [c for c in comandos if 'install' in c]
        self.assertEqual(len(llamadas_install), 4, comandos)
        for cmd in llamadas_install:
            self.assertEqual(cmd[:4], ['python-de-prueba', '-m', 'pip', 'install'],
                              'debe llamar a "sys.executable -m pip install <paquete>" (aquí, el --python pedido)')
        paquetes_pedidos = sorted(c[-1] for c in llamadas_install)
        self.assertEqual(paquetes_pedidos, sorted(['Pillow', 'numpy', 'imageio-ffmpeg', 'opencv-python']))
        for ajeno in ('mediapipe', 'PyMuPDF', 'pypdf'):
            self.assertNotIn(ajeno, paquetes_pedidos, f'"{ajeno}" no es de "imagen": no debe pedirse instalar')

    def test_una_a_una_nunca_todas_en_el_mismo_pip_install(self):
        inst = _cargar_instalador()
        comandos = []

        def _run_falso(cmd, **kw):
            comandos.append(list(cmd))
            return _R(returncode=1 if '-c' in cmd else 0)

        with mock.patch.object(inst.subprocess, 'run', side_effect=_run_falso):
            inst.instalar_dependencias(['imagen'])
        llamadas_install = [c for c in comandos if 'install' in c]
        self.assertEqual(len(llamadas_install), 4, 'cuatro llamadas a pip, una por paquete — nunca una sola con las 4')
        for cmd in llamadas_install:
            self.assertEqual(cmd.count('install'), 1)
            # exactamente un paquete tras "install" (nunca varios en la misma línea)
            self.assertEqual(len(cmd) - cmd.index('install') - 1, 1, cmd)

    def test_comando_se_enseña_antes_y_el_resultado_despues(self):
        """T5.1: 'enseñando el comando antes de correrlo y el resultado después.
        Nunca en silencio.'"""
        inst = _cargar_instalador()

        def _run_falso(cmd, **kw):
            return _R(returncode=1 if '-c' in cmd else 0)

        with mock.patch.object(inst.subprocess, 'run', side_effect=_run_falso):
            mensajes, ok = inst.instalar_dependencias(['imagen'], python_exe='python-de-prueba', idioma='es')

        self.assertTrue(ok)
        for paquete in ('Pillow', 'numpy', 'imageio-ffmpeg', 'opencv-python'):
            idx_comando = next(i for i, m in enumerate(mensajes)
                                if m.startswith('comando:') and paquete in m and 'install' in m)
            idx_resultado = mensajes.index(f'{paquete}: instalado')
            self.assertLess(idx_comando, idx_resultado,
                             f'{paquete}: el comando debe imprimirse ANTES que su resultado')

    def test_modulo_desconocido_para_dependencias_no_instala_nada(self):
        inst = _cargar_instalador()
        with mock.patch.object(inst.subprocess, 'run') as run_falso:
            paquetes = inst._paquetes_a_instalar(['esto_no_existe'])
            run_falso.assert_not_called()
        self.assertEqual(paquetes, [])


class SinNadaQueInstalarNoLlamaAPip(unittest.TestCase):
    def test_todo_presente_no_ejecuta_ningun_pip_install(self):
        inst = _cargar_instalador()
        llamadas_install = []

        def _run_falso(cmd, **kw):
            if 'install' in cmd:
                llamadas_install.append(cmd)
            return _R(returncode=0)  # todo presente

        with mock.patch.object(inst.subprocess, 'run', side_effect=_run_falso):
            mensajes, ok = inst.instalar_dependencias(['imagen'], idioma='es')
        self.assertTrue(ok)
        self.assertEqual(llamadas_install, [])
        self.assertIn(inst._texto('es', 'dep_nada_que_instalar'), mensajes)


# ---------------------------------------------------------------------------------
# T5.1, prueba de la especificación: "si el pip simulado falla, el resumen lo
# dice y el código de salida no es 0".
# ---------------------------------------------------------------------------------
class PipSimuladoQueFallaSeCuentaYNoDaCodigoDeSalida0(unittest.TestCase):
    def test_fallo_de_pip_marca_ok_false_y_dice_la_ultima_linea_del_error(self):
        inst = _cargar_instalador()

        def _run_falso(cmd, **kw):
            if '-c' in cmd:
                return _R(returncode=1)
            if 'install' in cmd:
                return _R(returncode=1, stdout='Collecting Pillow\n',
                           stderr='Could not find a version that satisfies the requirement (simulado)\n')
            return _R(returncode=0)

        with mock.patch.object(inst.subprocess, 'run', side_effect=_run_falso):
            mensajes, ok = inst.instalar_dependencias(['imagen'], idioma='es')

        self.assertFalse(ok, 'un pip que falla debe devolver ok=False (para que la CLI salga con código != 0)')
        self.assertTrue(
            any('FALLÓ' in m and 'Could not find a version that satisfies the requirement (simulado)' in m
                for m in mensajes),
            mensajes)

    def test_un_fallo_no_frena_el_resto_de_paquetes(self):
        """T5.1: 'se dice ... y se sigue con el resto. No se reintenta solo.'"""
        inst = _cargar_instalador()
        llamados = []

        def _run_falso(cmd, **kw):
            if '-c' in cmd:
                return _R(returncode=1)
            if 'install' in cmd:
                paquete = cmd[-1]
                llamados.append(paquete)
                return _R(returncode=1, stderr='error simulado\n') if paquete == 'Pillow' else _R(returncode=0)
            return _R(returncode=0)

        with mock.patch.object(inst.subprocess, 'run', side_effect=_run_falso):
            mensajes, ok = inst.instalar_dependencias(['imagen'], idioma='es')

        self.assertFalse(ok)
        self.assertEqual(llamados.count('Pillow'), 1, 'un fallo no debe reintentarse solo')
        self.assertEqual(sorted(llamados), sorted(['Pillow', 'numpy', 'imageio-ffmpeg', 'opencv-python']),
                          'los otros tres deben intentarse igual, aunque Pillow fallara')

    def test_excepcion_al_ejecutar_pip_tambien_marca_ok_false(self):
        """Sin pip / sin ese intérprete siquiera: `subprocess.run` puede lanzar
        (`FileNotFoundError`, etc.) en vez de devolver un `returncode` — debe
        contarse igual como fallo, nunca reventar `instalar_dependencias`."""
        inst = _cargar_instalador()

        def _run_falso(cmd, **kw):
            if '-c' in cmd:
                return _R(returncode=1)
            if 'install' in cmd:
                raise FileNotFoundError('no such file: pip (simulado)')
            return _R(returncode=0)

        with mock.patch.object(inst.subprocess, 'run', side_effect=_run_falso):
            mensajes, ok = inst.instalar_dependencias(['imagen'], idioma='es')
        self.assertFalse(ok)
        self.assertTrue(any('pip' in m.lower() for m in mensajes), mensajes)

    def test_cli_de_verdad_sale_con_codigo_distinto_de_cero(self):
        """Extremo a extremo por subprocess (mismo método que
        `test_imagen_dependencias_opcionales.py`: un `sitecustomize.py` propio
        antepuesto a PYTHONPATH sustituye `subprocess.run` en el PROCESO HIJO) —
        confirma que `ok=False` de arriba de verdad se traduce en un código de
        salida distinto de 0 en la CLI, sin tocar la red ni un pip real."""
        proj = ay.nuevo_proyecto()
        env = _entorno_con_pip_simulado_que_falla(proj)
        r = ay.ejecutar(ay.RAIZ / 'instalar.py', ['--instalar-dependencias', 'imagen'], env)
        self.assertNotEqual(r.returncode, 0, f'stdout={r.stdout!r} stderr={r.stderr!r}')
        self.assertIn('FALLÓ', r.stdout)
        self.assertNotIn('Traceback', r.stdout + r.stderr)


def _entorno_con_pip_simulado_que_falla(proj):
    """`sitecustomize.py` propio antepuesto a `PYTHONPATH` (mismo método que
    `pruebas/test_imagen_dependencias_opcionales.py`): sustituye
    `subprocess.run` DEL PROCESO HIJO por una versión que dice "falta todo" a
    cada comprobación de import y "error simulado" a cada `pip install` — en
    ningún caso llega a la red ni a un pip de verdad."""
    bloqueo_dir = Path(tempfile.mkdtemp(prefix='abyss_pip_falso_'))
    (bloqueo_dir / 'sitecustomize.py').write_text(textwrap.dedent('''
        import subprocess as _sp

        class _R:
            def __init__(self, returncode=0, stdout="", stderr=""):
                self.returncode = returncode
                self.stdout = stdout
                self.stderr = stderr

        def _fake_run(cmd, *a, **kw):
            cmd = [str(c) for c in cmd]
            if "-c" in cmd:
                return _R(returncode=1, stderr="ModuleNotFoundError (simulado)\\n")
            if "install" in cmd:
                return _R(returncode=1, stderr="ERROR: pip simulado, sin red de verdad\\n")
            return _R(returncode=0)

        _sp.run = _fake_run
    '''), encoding='utf-8')
    env = ay.entorno(proj)
    env['PYTHONPATH'] = str(bloqueo_dir) + os.pathsep + env.get('PYTHONPATH', '')
    return env


# ---------------------------------------------------------------------------------
# T5.1, prueba de la especificación: "ningún gancho instala nada".
# ---------------------------------------------------------------------------------
class NingunGanchoInstalaNada(unittest.TestCase):
    def test_ningun_modulo_declara_un_gancho_de_dependencias(self):
        inst = _cargar_instalador()
        for mod in inst.MODULOS:
            for evento, args, timeout in mod.get('hooks', ()):
                self.assertNotIn('--instalar-dependencias', args, f'{mod["id"]}/{evento}')
                self.assertNotIn('--dependencias', args, f'{mod["id"]}/{evento}')

    def test_hooks_json_del_plugin_no_menciona_dependencias_ni_instalar_py(self):
        texto = (ay.RAIZ / 'hooks' / 'hooks.json').read_text(encoding='utf-8')
        self.assertNotIn('--instalar-dependencias', texto)
        self.assertNotIn('--dependencias', texto)
        self.assertNotIn('instalar.py', texto, 'instalar.py no es un guion de gancho')

    def test_instalar_dependencias_nunca_se_llama_desde_instalar_o_desinstalar(self):
        """`instalar()`/`desinstalar()` (lo que SÍ corre, indirectamente, desde
        cualquier flujo automatizable) no deben invocar `instalar_dependencias`
        por su cuenta — es un verbo aparte, solo a petición explícita."""
        inst = _cargar_instalador()
        import inspect
        for nombre_fn in ('instalar', 'desinstalar'):
            fuente = inspect.getsource(getattr(inst, nombre_fn))
            self.assertNotIn('instalar_dependencias(', fuente, f'{nombre_fn}() no debe llamar a instalar_dependencias')


# ---------------------------------------------------------------------------------
# Lo que NO se puede instalar por pip (T5.1): tesseract fuera de Windows, y
# torch/diffusers para taller.py con el comando EXACTO según haya o no GPU NVIDIA.
# ---------------------------------------------------------------------------------
class NoInstalablesDicenElComandoDelSistemaSinFingir(unittest.TestCase):
    def test_comando_torch_cambia_segun_haya_gpu_nvidia(self):
        inst = _cargar_instalador()
        with mock.patch.object(inst, '_hay_gpu_nvidia', return_value=False):
            self.assertEqual(inst._comando_taller_torch(), 'pip install torch')
        with mock.patch.object(inst, '_hay_gpu_nvidia', return_value=True):
            self.assertIn('cu121', inst._comando_taller_torch())

    def test_hay_gpu_nvidia_no_revienta_sin_nvidia_smi(self):
        inst = _cargar_instalador()
        with mock.patch.object(inst.subprocess, 'run', side_effect=FileNotFoundError('sin nvidia-smi')):
            self.assertFalse(inst._hay_gpu_nvidia())

    def test_tabla_dice_apt_en_linux_y_brew_en_macos_nunca_los_dos_a_la_vez(self):
        inst = _cargar_instalador()
        with mock.patch.object(inst, '_import_disponible', return_value=True), \
             mock.patch.object(inst, '_hay_gpu_nvidia', return_value=False):
            with mock.patch.object(inst.platform, 'system', return_value='Linux'):
                texto_linux = inst._tabla_dependencias('es', ['imagen'])
            with mock.patch.object(inst.platform, 'system', return_value='Darwin'):
                texto_mac = inst._tabla_dependencias('es', ['imagen'])
            with mock.patch.object(inst.platform, 'system', return_value='Windows'):
                texto_win = inst._tabla_dependencias('es', ['imagen'])
        self.assertIn('apt install tesseract-ocr', texto_linux)
        self.assertNotIn('brew', texto_linux)
        self.assertIn('brew install tesseract', texto_mac)
        self.assertNotIn('apt install', texto_mac)
        self.assertNotIn('tesseract', texto_win, 'en Windows el motor ya viene con el sistema (WinRT)')

    def test_ojo_no_registra_pytesseract_como_dependencia(self):
        """`lectura_visual.py` llama al binario `tesseract` por PATH/subprocess
        (TSV), nunca importa `pytesseract` — instalarlo por pip no activaría
        nada, así que no debe figurar como paquete de pip de ningún módulo."""
        inst = _cargar_instalador()
        for entradas in inst.DEPENDENCIAS.values():
            for e in entradas:
                self.assertNotEqual(e['pip_nombre'].lower(), 'pytesseract',
                                     'el código llama al binario tesseract directamente, no a pytesseract')


# ---------------------------------------------------------------------------------
# `--instalar-dependencias` con valor OPCIONAL: sin lista, no debe tragarse la
# siguiente bandera (p. ej. `--idioma en`) como si fuera la lista de módulos.
# ---------------------------------------------------------------------------------
class InstalarDependenciasValorOpcionalNoSeTragaOtraBandera(unittest.TestCase):
    def test_sin_lista_seguido_de_otra_bandera_no_la_toma_como_modulos(self):
        inst = _cargar_instalador()
        self.assertIsNone(inst._valor_flag_opcional(['--instalar-dependencias', '--idioma', 'en'],
                                                      '--instalar-dependencias'))
        self.assertEqual(inst._lista_flag_opcional(['--instalar-dependencias', '--idioma', 'en'],
                                                     '--instalar-dependencias'), [])

    def test_con_lista_de_verdad_la_toma(self):
        inst = _cargar_instalador()
        self.assertEqual(inst._valor_flag_opcional(['--instalar-dependencias', 'imagen,ojo'],
                                                     '--instalar-dependencias'), 'imagen,ojo')
        self.assertEqual(inst._lista_flag_opcional(['--instalar-dependencias', 'imagen,ojo'],
                                                     '--instalar-dependencias'), ['imagen', 'ojo'])

    def test_argumento_no_reconocido_acepta_las_dos_formas(self):
        inst = _cargar_instalador()
        self.assertIsNone(inst._argumento_no_reconocido(['--instalar-dependencias']))
        self.assertIsNone(inst._argumento_no_reconocido(['--instalar-dependencias', 'imagen']))
        self.assertIsNone(inst._argumento_no_reconocido(['--instalar-dependencias', '--idioma', 'en']))
        self.assertIsNone(inst._argumento_no_reconocido(['--dependencias']))


if __name__ == '__main__':
    unittest.main()
