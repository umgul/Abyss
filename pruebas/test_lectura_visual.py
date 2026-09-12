"""`lectura_visual.py`: OCR y sus tres usos. No llama a `rutas.resolver()` a nivel de
módulo: las funciones puras se prueban con import directo, la CLI por subprocess. El
motor real se comprueba en caliente (`skipUnless`, nunca por `os.name`); todo se fuerza "sin dato" por env para que la suite nunca dependa de hardware real."""
import sys
import os
import json
import shutil
import tempfile
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ayudas as ay

sys.path.insert(0, str(ay.PKG))
import lectura_visual as lv  # noqa: E402  (sin rutas.resolver() a nivel de módulo: seguro importarlo aquí)

DATOS = ay.RAIZ / 'pruebas' / 'datos'
OCR_TEXTO = DATOS / 'ocr_texto.png'
OCR_TARJETA = DATOS / 'ocr_tarjeta.png'
OCR_PAPEL = DATOS / 'ocr_papel.png'
OCR_MANUAL_P1 = DATOS / 'ocr_manual_p1.png'
OCR_MANUAL_P2 = DATOS / 'ocr_manual_p2.png'

_TIENE_WINRT = lv.motor_winrt_disponible()
_TIENE_TESSERACT = bool(shutil.which('tesseract'))


def _ultima_linea_json(stdout):
    return json.loads([l for l in stdout.splitlines() if l.strip()][-1])


def _entorno_sin_ningun_motor(proj):
    env = ay.entorno(proj)
    env['ABYSS_LECTURA_VISUAL_SIN_WINRT'] = '1'
    env['ABYSS_LECTURA_VISUAL_SIN_TESSERACT'] = '1'
    return env


def _entorno_con_modulo_bloqueado(proj, nombre):
    """Bloquea el import de `nombre` (p. ej. 'cv2' o 'PIL') solo en el proceso hijo, con
    un `sitecustomize.py` propio antepuesto a `PYTHONPATH` (Pillow/numpy/cv2 siguen
    instalados en la máquina real; solo este proceso hijo no los ve)."""
    bloqueo_dir = Path(tempfile.mkdtemp(prefix='abyss_bloqueo_lv_'))
    (bloqueo_dir / 'sitecustomize.py').write_text(textwrap.dedent(f'''
        import sys
        import importlib.abc

        class _Bloqueador(importlib.abc.MetaPathFinder):
            def find_spec(self, name, path, target=None):
                if name.split(".")[0] == {nombre!r}:
                    raise ModuleNotFoundError(
                        "{{}} bloqueado por la prueba (sitecustomize)".format(name), name=name)
                return None

        sys.meta_path.insert(0, _Bloqueador())
    '''), encoding='utf-8')
    env = ay.entorno(proj)
    env['PYTHONPATH'] = str(bloqueo_dir) + os.pathsep + env.get('PYTHONPATH', '')
    return env


def _tesseract_falso_en_path(env, tsv_texto):
    """Añade al PATH un directorio con un `tesseract.cmd` que ignora sus argumentos y
    escribe `tsv_texto` por stdout, para probar el cableado de la "segunda vía" sin
    depender de que `tesseract` esté instalado (`shutil.which` resuelve `.cmd` por `PATHEXT`)."""
    carpeta = Path(tempfile.mkdtemp(prefix='abyss_tesseract_falso_'))
    marcador = carpeta / 'salida.tsv'
    marcador.write_text(tsv_texto, encoding='utf-8')
    script = carpeta / 'tesseract.cmd'
    # `type` en vez de un heredoc: nada de comillas raras que romper en un .cmd.
    script.write_text(f'@echo off\r\ntype "{marcador}"\r\n', encoding='utf-8')
    env = dict(env)
    env['PATH'] = str(carpeta) + os.pathsep + env.get('PATH', '')
    return env, carpeta


TSV_FALSO = (
    'level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\r\n'
    '5\t1\t1\t1\t1\t1\t10\t10\t50\t20\t95.0\tHola\r\n'
    '5\t1\t1\t1\t1\t2\t65\t12\t40\t18\t95.0\tMundo\r\n'
    '5\t1\t1\t1\t2\t1\t10\t40\t80\t20\t90.0\tFalso\r\n'
)


# ───────────────────────────── sin ningún motor (siempre determinista) ─────────────────────────────

class SinNingunMotorOCR(unittest.TestCase):
    def test_texto_sin_motor_da_codigo_2_y_mensaje_sin_dato(self):
        proj = ay.nuevo_proyecto()
        env = _entorno_sin_ningun_motor(proj)
        r = ay.ejecutar(ay.script('lectura_visual.py'), ['texto', str(OCR_TEXTO)], env)
        self.assertEqual(r.returncode, 2, f'stdout={r.stdout!r} stderr={r.stderr!r}')
        self.assertIn('sin dato: no hay motor OCR', r.stdout)
        self.assertNotIn('Traceback', r.stdout)
        self.assertNotIn('Traceback', r.stderr)

    def test_manual_sin_motor_da_codigo_2(self):
        proj = ay.nuevo_proyecto()
        env = _entorno_sin_ningun_motor(proj)
        r = ay.ejecutar(ay.script('lectura_visual.py'), ['manual', str(OCR_MANUAL_P1)], env)
        self.assertEqual(r.returncode, 2)
        self.assertIn('sin dato: no hay motor OCR', r.stdout)

    def test_tarjeta_sin_motor_da_codigo_2(self):
        proj = ay.nuevo_proyecto()
        env = _entorno_sin_ningun_motor(proj)
        r = ay.ejecutar(ay.script('lectura_visual.py'), ['tarjeta', str(OCR_TARJETA)], env)
        self.assertEqual(r.returncode, 2)
        self.assertIn('sin dato: no hay motor OCR', r.stdout)


# ───────────────────────────── segunda vía: tesseract (cableado, sin hardware) ─────────────────────────────

class TesseractComoSegundaViaFalso(unittest.TestCase):
    """`ABYSS_LECTURA_VISUAL_SIN_WINRT=1` apaga la primera vía; un `tesseract.cmd` falso en
    el PATH prueba que `leer()` cae a la segunda vía y agrupa su TSV por línea — nunca
    prueba precisión de reconocimiento real (eso lo mide `SegundaViaConTesseractReal`)."""

    def test_cli_texto_usa_tesseract_y_agrupa_por_linea(self):
        proj = ay.nuevo_proyecto()
        env = ay.entorno(proj)
        env['ABYSS_LECTURA_VISUAL_SIN_WINRT'] = '1'
        env, carpeta = _tesseract_falso_en_path(env, TSV_FALSO)
        self.addCleanup(shutil.rmtree, carpeta, ignore_errors=True)
        r = ay.ejecutar(ay.script('lectura_visual.py'), ['texto', str(OCR_TEXTO)], env)
        self.assertEqual(r.returncode, 0, f'stdout={r.stdout!r} stderr={r.stderr!r}')
        lineas = [l for l in r.stdout.splitlines() if l.strip()]
        self.assertIn('Hola Mundo', lineas)
        self.assertIn('Falso', lineas)


@unittest.skipUnless(_TIENE_TESSERACT, 'tesseract no está en el PATH en esta máquina '
                      '(medido 7-sep-2026)')
class SegundaViaConTesseractReal(unittest.TestCase):
    def test_ocr_tesseract_real_lee_algo(self):
        proj = ay.nuevo_proyecto()
        env = ay.entorno(proj)
        env['ABYSS_LECTURA_VISUAL_SIN_WINRT'] = '1'
        r = ay.ejecutar(ay.script('lectura_visual.py'), ['texto', str(OCR_TEXTO)], env)
        self.assertEqual(r.returncode, 0, f'stdout={r.stdout!r} stderr={r.stderr!r}')


class OcrTesseractEnProceso(unittest.TestCase):
    """`_ocr_tesseract()` en proceso, con `subprocess.run` sustituido (nunca toca
    un `tesseract` real): prueba SOLO el agrupado de palabras en líneas por
    `(block_num,par_num,line_num)` y la caja mínima/máxima resultante."""

    def test_agrupa_palabras_en_lineas_con_caja(self):
        import types
        from unittest import mock

        def _falso_run(args, **kwargs):
            return types.SimpleNamespace(returncode=0, stdout=TSV_FALSO, stderr='')

        with mock.patch.object(lv.subprocess, 'run', side_effect=_falso_run):
            out = lv._ocr_tesseract('tesseract-falso', 'no_importa.png')
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]['texto'], 'Hola Mundo')
        self.assertEqual(out[0]['x'], 10.0)
        self.assertEqual(out[0]['y'], 10.0)
        self.assertEqual(out[0]['ancho'], 95.0)  # de x=10 a x=105 (65+40)
        self.assertEqual(out[1]['texto'], 'Falso')

    def test_returncode_no_cero_lanza_con_stderr(self):
        import types
        from unittest import mock

        def _falso_run(args, **kwargs):
            return types.SimpleNamespace(returncode=1, stdout='', stderr='tesseract: error de verdad')

        with mock.patch.object(lv.subprocess, 'run', side_effect=_falso_run):
            with self.assertRaises(RuntimeError):
                lv._ocr_tesseract('tesseract-falso', 'no_importa.png')


# ───────────────────────────── texto (motor real de esta máquina) ─────────────────────────────

@unittest.skipUnless(_TIENE_WINRT, 'sin motor OCR de Windows disponible en esta máquina')
class TextoConMotorReal(unittest.TestCase):
    def test_lee_las_lineas_en_orden(self):
        proj = ay.nuevo_proyecto()
        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('lectura_visual.py'), ['texto', str(OCR_TEXTO)], env)
        self.assertEqual(r.returncode, 0, f'stdout={r.stdout!r} stderr={r.stderr!r}')
        self.assertIn('Reunion de mantenimiento', r.stdout)
        self.assertIn('presion del deposito', r.stdout)
        # apunte de uso, provenance mínima (ESPECIFICACION.md §1)
        self.assertTrue((proj / 'memory' / 'lectura_visual.log').exists())

    def test_salida_escribe_fichero(self):
        proj = ay.nuevo_proyecto()
        env = ay.entorno(proj)
        tmp = tempfile.mkdtemp(prefix='abyss_lv_')
        salida = os.path.join(tmp, 'texto.txt')
        r = ay.ejecutar(ay.script('lectura_visual.py'), ['texto', str(OCR_TEXTO), '--salida', salida], env)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertTrue(os.path.exists(salida))
        with open(salida, encoding='utf-8') as fh:
            self.assertIn('mantenimiento', fh.read())

    def test_imagen_inexistente_codigo_2(self):
        proj = ay.nuevo_proyecto()
        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('lectura_visual.py'), ['texto', 'no_existe_de_verdad.png'], env)
        self.assertEqual(r.returncode, 2)
        self.assertIn('no existe', r.stdout)

    def test_falta_imagen_codigo_1(self):
        proj = ay.nuevo_proyecto()
        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('lectura_visual.py'), ['texto'], env)
        self.assertEqual(r.returncode, 1)


@unittest.skipUnless(os.name == 'nt', 'Set-Clipboard es la vía de Windows; en otro SO se prueba xclip/pbcopy solo si están')
class PortapapelesReal(unittest.TestCase):
    def test_copiar_devuelve_true_en_windows(self):
        self.assertTrue(lv.copiar_portapapeles('prueba de abyss, sin acentos raros: ñ á é'))


# ───────────────────────────── tarjeta (motor real) ─────────────────────────────

@unittest.skipUnless(_TIENE_WINRT, 'sin motor OCR de Windows disponible en esta máquina')
class TarjetaConMotorReal(unittest.TestCase):
    def test_extrae_los_campos_de_la_tarjeta_sintetica(self):
        proj = ay.nuevo_proyecto()
        env = ay.entorno(proj)
        tmp = tempfile.mkdtemp(prefix='abyss_lv_')
        base = os.path.join(tmp, 'tarjeta')
        r = ay.ejecutar(ay.script('lectura_visual.py'), ['tarjeta', str(OCR_TARJETA), '--salida', base], env)
        self.assertEqual(r.returncode, 0, f'stdout={r.stdout!r} stderr={r.stderr!r}')
        datos = _ultima_linea_json(r.stdout)
        self.assertEqual(datos['nombre'], 'Elena Martin Soler')
        self.assertEqual(datos['cargo'], 'Responsable de Compras')
        self.assertIn('Suministros Delta', datos['empresa'])
        self.assertIn('611', datos['telefono'])
        self.assertEqual(datos['correo'], 'compras@suministrosdelta.es')
        self.assertIn('suministrosdelta.es', datos['web'])
        self.assertTrue(os.path.exists(base + '.vcf'))
        self.assertTrue(os.path.exists(base + '.png'))
        with open(base + '.vcf', encoding='utf-8', newline='') as fh:  # newline='': no traducir \r\n a \n al leer
            vcf = fh.read()
        self.assertTrue(vcf.startswith('BEGIN:VCARD\r\n'))
        self.assertIn('FN:Elena Martin Soler', vcf)
        self.assertIn('EMAIL', vcf)
        self.assertTrue(vcf.rstrip('\r\n').endswith('END:VCARD'))

    def test_sin_pillow_da_codigo_2_sin_traceback(self):
        proj = ay.nuevo_proyecto()
        env = _entorno_con_modulo_bloqueado(proj, 'PIL')
        r = ay.ejecutar(ay.script('lectura_visual.py'), ['tarjeta', str(OCR_TARJETA)], env)
        self.assertEqual(r.returncode, 2, f'stdout={r.stdout!r} stderr={r.stderr!r}')
        self.assertIn('sin dato', r.stdout)
        self.assertIn('Pillow', r.stdout)
        self.assertNotIn('Traceback', r.stdout)
        self.assertNotIn('Traceback', r.stderr)


class TarjetaHeuristicaPuraSinOCR(unittest.TestCase):
    """`_clasificar_lineas()`/`_nombre_cargo_empresa()`/`vcard_de()` en proceso, sobre
    líneas sintéticas (sin motor de OCR): la heurística de tamaño/posición y la
    generación de vCard son deterministas y no dependen de Windows ni de `tesseract`."""

    def test_nombre_es_la_linea_de_mayor_caja_y_empresa_por_sufijo(self):
        lineas = [
            {'texto': 'Juan Perez Gomez', 'x': 0, 'y': 0, 'ancho': 300, 'alto': 30},
            {'texto': 'Ingeniero Jefe', 'x': 0, 'y': 40, 'ancho': 150, 'alto': 18},
            {'texto': 'Talleres Norte S.A.', 'x': 0, 'y': 65, 'ancho': 160, 'alto': 18},
            {'texto': 'Tel. 933 445 566', 'x': 0, 'y': 100, 'ancho': 140, 'alto': 16},
            {'texto': 'juan@talleresnorte.com', 'x': 0, 'y': 130, 'ancho': 180, 'alto': 16},
        ]
        telefono, correo, web, resto = lv._clasificar_lineas(lineas)
        self.assertEqual(telefono, '933 445 566')
        self.assertEqual(correo, 'juan@talleresnorte.com')
        self.assertEqual(web, '')  # ninguna línea de web suelta en este caso
        nombre, cargo, empresa = lv._nombre_cargo_empresa(resto)
        self.assertEqual(nombre, 'Juan Perez Gomez')
        self.assertEqual(empresa, 'Talleres Norte S.A.')
        self.assertEqual(cargo, 'Ingeniero Jefe')

    def test_sin_lineas_sobrantes_todo_vacio(self):
        self.assertEqual(lv._nombre_cargo_empresa([]), ('', '', ''))

    def test_telefono_corto_no_se_cuenta_como_telefono(self):
        """Menos de 7 dígitos (p. ej. un número de habitación o de planta) no
        debe colarse como teléfono — declarado en `_clasificar_lineas`."""
        telefono, _correo, _web, resto = lv._clasificar_lineas([{'texto': 'Planta 3, puerta 12', 'alto': 20}])
        self.assertEqual(telefono, '')
        self.assertEqual(len(resto), 1)

    def test_vcard_sin_campos_omite_esas_lineas(self):
        vcf = lv.vcard_de({'nombre': '', 'cargo': '', 'empresa': '', 'telefono': '', 'correo': '', 'web': ''})
        self.assertIn('FN:(sin nombre reconocido)', vcf)
        for etiqueta in ('ORG:', 'TITLE:', 'TEL', 'EMAIL', 'URL:'):
            self.assertNotIn(etiqueta, vcf)

    def test_vcard_web_sin_esquema_le_pone_http(self):
        vcf = lv.vcard_de({'nombre': 'X', 'web': 'www.ejemplo.es'})
        self.assertIn('URL:http://www.ejemplo.es', vcf)


# ───────────────────────────── manual (motor real) ─────────────────────────────

@unittest.skipUnless(_TIENE_WINRT, 'sin motor OCR de Windows disponible en esta máquina')
class ManualConMotorReal(unittest.TestCase):
    def test_ordena_por_pagina_une_guion_y_numera_pasos(self):
        proj = ay.nuevo_proyecto()
        env = ay.entorno(proj)
        tmp = tempfile.mkdtemp(prefix='abyss_lv_')
        salida = os.path.join(tmp, 'manual.md')
        # se dan en orden "2, 1" a propósito: el guion debe reordenar por página detectada
        r = ay.ejecutar(ay.script('lectura_visual.py'),
                         ['manual', str(OCR_MANUAL_P2), str(OCR_MANUAL_P1), '--salida', salida], env)
        self.assertEqual(r.returncode, 0, f'stdout={r.stdout!r} stderr={r.stderr!r}')
        with open(salida, encoding='utf-8') as fh:
            md = fh.read()
        pos_p1 = md.index('página 1')
        pos_p2 = md.index('página 2')
        self.assertLess(pos_p1, pos_p2, 'la página 1 debe salir antes que la página 2 aunque se dieran al revés')
        # el guion de corte "ali-" + "mentacion" debe quedar unido, sin el guion
        self.assertIn('alimentacion', md.replace('\n', ' '))
        self.assertNotIn('ali-', md)
        # los tres pasos, detectados y renumerados como lista markdown
        self.assertIn('1. Conecta el cable', md)
        self.assertIn('2. Enciende el interruptor', md)
        self.assertIn('3. Aprieta el tornillo final', md)

    def test_una_sola_imagen_sin_pagina_usa_nombre_de_fichero(self):
        proj = ay.nuevo_proyecto()
        env = ay.entorno(proj)
        tmp = tempfile.mkdtemp(prefix='abyss_lv_')
        salida = os.path.join(tmp, 'manual.md')
        r = ay.ejecutar(ay.script('lectura_visual.py'), ['manual', str(OCR_TEXTO), '--salida', salida], env)
        self.assertEqual(r.returncode, 0, r.stdout)
        with open(salida, encoding='utf-8') as fh:
            md = fh.read()
        self.assertIn('imagen 1', md)

    def test_imagen_inexistente_entre_varias_codigo_2(self):
        proj = ay.nuevo_proyecto()
        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('lectura_visual.py'), ['manual', str(OCR_MANUAL_P1), 'fantasma.png'], env)
        self.assertEqual(r.returncode, 2)
        self.assertIn('fantasma.png', r.stdout)


class ManualHeuristicaPuraSinOCR(unittest.TestCase):
    def test_une_guion_de_corte_pegando_sin_espacio(self):
        out = lv._unir_guiones_de_corte(['Conecta el cable de ali-', 'mentacion al enchufe', 'Fin.'])
        self.assertEqual(out, ['Conecta el cable de alimentacion al enchufe', 'Fin.'])

    def test_no_une_un_guion_suelto_ni_un_rango(self):
        out = lv._unir_guiones_de_corte(['Paginas 10-20', 'Ver el indice -', 'siguiente parrafo'])
        self.assertEqual(out[0], 'Paginas 10-20')  # el guion no está pegado a un salto de palabra

    def test_detecta_pagina_por_varios_patrones(self):
        self.assertEqual(lv._detectar_pagina(['algo', 'Pagina 7', 'mas']), 7)
        self.assertEqual(lv._detectar_pagina(['Page 3 of 10']), 3)
        self.assertEqual(lv._detectar_pagina(['4/12']), 4)
        self.assertEqual(lv._detectar_pagina(['texto normal', '9']), 9)
        self.assertIsNone(lv._detectar_pagina(['sin ningun numero de pagina aqui']))

    def test_formatea_pasos_numero_palabra_y_vineta(self):
        self.assertEqual(lv._formatear_paso('1. Primero', 1), ('1. Primero', True))
        self.assertEqual(lv._formatear_paso('Paso 2: Segundo', 1), ('2. Segundo', True))
        self.assertEqual(lv._formatear_paso('Step: Tercero', 5), ('5. Tercero', True))
        self.assertEqual(lv._formatear_paso('- Un punto suelto', 1), ('- Un punto suelto', True))
        texto_libre, es_paso = lv._formatear_paso('Solo una frase cualquiera', 1)
        self.assertFalse(es_paso)
        self.assertEqual(texto_libre, 'Solo una frase cualquiera')

    def test_no_ordena_si_falta_el_numero_en_alguna_pagina(self):
        """Si SOLO una página trae número, se mantiene el orden de entrada: no se reordena
        a medias ni se adivina un hueco. "b" detecta página 99 (alta) pero se da ANTES que
        "a" (sin número); si reordenase por número, "b" saldría después."""
        from unittest import mock
        paginas = {
            'a.png': [{'texto': 'sin numero aqui'}],
            'b.png': [{'texto': 'Pagina 99'}],
        }

        def _falso_leer(ruta, idioma=None, avisar=print):
            return {'motor': 'falso', 'lineas': paginas[os.path.basename(ruta)]}

        with mock.patch.object(lv, 'leer', side_effect=_falso_leer):
            md = lv.manual(['b.png', 'a.png'])
        self.assertLess(md.index('página 99'), md.index('imagen 2'))


# ───────────────────────────── fotocopia (necesita cv2/numpy, no OCR) ─────────────────────────────

@unittest.skipUnless(lv._CV2_OK, 'cv2/numpy no están instalados en esta máquina')
class FotocopiaConCv2Real(unittest.TestCase):
    def test_con_cuadrilatero_claro_recorta_y_endereza(self):
        proj = ay.nuevo_proyecto()
        env = ay.entorno(proj)
        tmp = tempfile.mkdtemp(prefix='abyss_lv_')
        salida = os.path.join(tmp, 'foto.png')
        r = ay.ejecutar(ay.script('lectura_visual.py'),
                         ['fotocopia', str(OCR_PAPEL), '--salida', salida], env)
        self.assertEqual(r.returncode, 0, f'stdout={r.stdout!r} stderr={r.stderr!r}')
        datos = _ultima_linea_json(r.stdout)
        self.assertTrue(datos['recortado'])
        self.assertTrue(os.path.exists(salida))

    def test_sin_cuadrilatero_no_finge_recorte(self):
        proj = ay.nuevo_proyecto()
        env = ay.entorno(proj)
        tmp = tempfile.mkdtemp(prefix='abyss_lv_')
        salida = os.path.join(tmp, 'foto.png')
        # ocr_texto.png es fondo blanco liso con texto: sin ningún borde de "papel" que recortar
        r = ay.ejecutar(ay.script('lectura_visual.py'),
                         ['fotocopia', str(OCR_TEXTO), '--salida', salida], env)
        self.assertEqual(r.returncode, 0, r.stdout)
        datos = _ultima_linea_json(r.stdout)
        self.assertFalse(datos['recortado'])
        self.assertIn('sin cuadrilátero claro', r.stdout)
        self.assertTrue(os.path.exists(salida))  # se escribe igual, sin fingir el recorte

    def test_modos_color_gris_umbral_dan_ficheros_distintos(self):
        proj = ay.nuevo_proyecto()
        env = ay.entorno(proj)
        tmp = tempfile.mkdtemp(prefix='abyss_lv_')
        tamanos = {}
        for modo in ('color', 'gris', 'umbral'):
            salida = os.path.join(tmp, f'{modo}.png')
            r = ay.ejecutar(ay.script('lectura_visual.py'),
                             ['fotocopia', str(OCR_PAPEL), f'--{modo}', '--salida', salida], env)
            self.assertEqual(r.returncode, 0, f'{modo}: {r.stdout!r}')
            self.assertTrue(os.path.exists(salida))
            tamanos[modo] = os.path.getsize(salida)
        # tres modos distintos casi nunca pesan lo mismo byte a byte (heurística de humo)
        self.assertEqual(len(set(tamanos.values())), 3, tamanos)

    def test_salida_pdf_por_extension(self):
        proj = ay.nuevo_proyecto()
        env = ay.entorno(proj)
        tmp = tempfile.mkdtemp(prefix='abyss_lv_')
        salida = os.path.join(tmp, 'foto.pdf')
        r = ay.ejecutar(ay.script('lectura_visual.py'),
                         ['fotocopia', str(OCR_PAPEL), '--salida', salida], env)
        self.assertEqual(r.returncode, 0, r.stdout)
        with open(salida, 'rb') as fh:
            self.assertEqual(fh.read(5), b'%PDF-')


class FotocopiaValidacionDeArgumentos(unittest.TestCase):
    """Errores de uso (argumentos incompatibles) se detectan en el propio análisis de `argv`,
    antes de tocar `cv2`. Vía normal: `<imagen>` o `--camara`, una de las dos; `--escaner`
    no participa en ese conflicto — es opcional y cae a la vía normal si no hay."""

    def test_dos_flags_de_modo_a_la_vez_es_error(self):
        proj = ay.nuevo_proyecto()
        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('lectura_visual.py'),
                         ['fotocopia', str(OCR_PAPEL), '--color', '--gris'], env)
        self.assertEqual(r.returncode, 1)

    def test_sin_imagen_ni_camara_es_error(self):
        proj = ay.nuevo_proyecto()
        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('lectura_visual.py'), ['fotocopia'], env)
        self.assertEqual(r.returncode, 1)
        self.assertIn('--camara', r.stdout)

    def test_solo_escaner_sin_via_normal_es_error(self):
        """`--escaner` nunca basta por sí solo: sin `<imagen>` ni `--camara` es el mismo
        error de uso que sin nada, y ni siquiera llega a preguntar por un escáner real
        (no hace falta forzar `ABYSS_LECTURA_VISUAL_SIN_WIA`)."""
        proj = ay.nuevo_proyecto()
        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('lectura_visual.py'), ['fotocopia', '--escaner'], env)
        self.assertEqual(r.returncode, 1)

    def test_imagen_y_camara_a_la_vez_es_error(self):
        proj = ay.nuevo_proyecto()
        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('lectura_visual.py'), ['fotocopia', str(OCR_PAPEL), '--camara'], env)
        self.assertEqual(r.returncode, 1)

    def test_imagen_y_escaner_a_la_vez_NO_es_error(self):
        """`--escaner` no es exclusivo con `<imagen>`: es una fuente opcional que se
        intenta antes y cae a la imagen si falla. Aquí solo se comprueba que la
        combinación no se rechaza (`--salida` a un temporal, para no escribir en `pruebas/datos/`)."""
        proj = ay.nuevo_proyecto()
        env = ay.entorno(proj)
        env['ABYSS_LECTURA_VISUAL_SIN_WIA'] = '1'
        tmp = tempfile.mkdtemp(prefix='abyss_lv_')
        salida = os.path.join(tmp, 'foto.png')
        r = ay.ejecutar(ay.script('lectura_visual.py'),
                         ['fotocopia', str(OCR_PAPEL), '--escaner', '--salida', salida], env)
        self.assertNotEqual(r.returncode, 1, f'stdout={r.stdout!r} stderr={r.stderr!r}')

    def test_paginas_mayor_uno_sin_camara_es_error(self):
        proj = ay.nuevo_proyecto()
        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('lectura_visual.py'),
                         ['fotocopia', str(OCR_PAPEL), '--paginas', '3'], env)
        self.assertEqual(r.returncode, 1)

    def test_paginas_mayor_uno_con_salida_png_es_error(self):
        proj = ay.nuevo_proyecto()
        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('lectura_visual.py'),
                         ['fotocopia', '--camara', '--paginas', '2', '--salida', 'x.png'], env)
        self.assertEqual(r.returncode, 1)
        self.assertIn('.pdf', r.stdout)


class FotocopiaSinCv2(unittest.TestCase):
    def test_sin_cv2_da_codigo_2_sin_traceback(self):
        proj = ay.nuevo_proyecto()
        env = _entorno_con_modulo_bloqueado(proj, 'cv2')
        r = ay.ejecutar(ay.script('lectura_visual.py'), ['fotocopia', str(OCR_PAPEL)], env)
        self.assertEqual(r.returncode, 2, f'stdout={r.stdout!r} stderr={r.stderr!r}')
        self.assertIn('sin dato', r.stdout)
        self.assertIn('opencv-python', r.stdout)
        self.assertNotIn('Traceback', r.stdout)
        self.assertNotIn('Traceback', r.stderr)


# ───────────────────────────── escáner WIA: siempre forzado, nunca hardware real ─────────────────────────────

class EscanerForzadoSinTocarHardware(unittest.TestCase):
    def test_funcion_escanear_wia_forzada_no_lanza_powershell(self):
        """`escanear_wia()` con la variable puesta devuelve `ok: False` sin ejecutar ningún
        `subprocess.run`: se comprueba con un mock que registra si se llamó, no solo el
        resultado ("ok: False" no distingue "no lo intentó" de "lo intentó y falló")."""
        from unittest import mock
        viejo = os.environ.get('ABYSS_LECTURA_VISUAL_SIN_WIA')
        os.environ['ABYSS_LECTURA_VISUAL_SIN_WIA'] = '1'
        try:
            with mock.patch.object(lv.subprocess, 'run') as mock_run:
                res = lv.escanear_wia('no_importa.bmp')
                mock_run.assert_not_called()
        finally:
            if viejo is None:
                os.environ.pop('ABYSS_LECTURA_VISUAL_SIN_WIA', None)
            else:
                os.environ['ABYSS_LECTURA_VISUAL_SIN_WIA'] = viejo
        self.assertFalse(res['ok'])
        self.assertIn('sin dato', res['motivo'])


class EscanerFisicoNoSeProbo(unittest.TestCase):
    @unittest.skip('--escaner NO se ejerce contra el escáner físico en esta batería '
                    '(el encargo lo prohíbe explícitamente); el camino "sin escáner" se prueba '
                    'forzado con ABYSS_LECTURA_VISUAL_SIN_WIA en EscanerForzadoSinTocarHardware')
    def test_no_se_prueba_contra_hardware_real(self):
        pass  # intencionadamente vacío: la prueba existe para DEJAR CONSTANCIA del porqué del salto


@unittest.skipUnless(lv._CV2_OK, 'cv2/numpy no están instalados en esta máquina')
class FotocopiaEscanerCaeALaViaNormal(unittest.TestCase):
    """Sin escáner, `fotocopia` no revienta: avisa y sigue por la vía normal ya dada
    (`<imagen>` aquí), igual que si `--escaner` no se hubiera puesto."""

    def test_escaner_mas_imagen_forzado_sin_wia_usa_el_fichero_sin_error(self):
        proj = ay.nuevo_proyecto()
        env = ay.entorno(proj)
        env['ABYSS_LECTURA_VISUAL_SIN_WIA'] = '1'
        tmp = tempfile.mkdtemp(prefix='abyss_lv_')
        salida = os.path.join(tmp, 'foto.png')
        r = ay.ejecutar(ay.script('lectura_visual.py'),
                         ['fotocopia', str(OCR_PAPEL), '--escaner', '--salida', salida], env)
        self.assertEqual(r.returncode, 0, f'stdout={r.stdout!r} stderr={r.stderr!r}')
        self.assertIn('sin escáner: uso la cámara o un fichero', r.stdout)
        self.assertTrue(os.path.exists(salida))
        datos = _ultima_linea_json(r.stdout)
        self.assertEqual(datos['entrada'], str(OCR_PAPEL))  # NO el fichero temporal del escáner


# ───────────────────────────── cámara: siempre forzada, nunca hardware real ─────────────────────────────

class CamaraForzadaSinTocarHardware(unittest.TestCase):
    def test_funcion_capturar_camara_forzada_no_abre_video_capture(self):
        """Mismo patrón que la prueba equivalente del escáner: con
        `ABYSS_LECTURA_VISUAL_SIN_CAMARA` puesta, `capturar_camara()` devuelve `ok: False`
        sin llegar a `_abrir_camara()`/`cv2.VideoCapture`, comprobado con un mock de llamada."""
        from unittest import mock
        viejo = os.environ.get('ABYSS_LECTURA_VISUAL_SIN_CAMARA')
        os.environ['ABYSS_LECTURA_VISUAL_SIN_CAMARA'] = '1'
        try:
            with mock.patch.object(lv, '_abrir_camara') as mock_abrir:
                res = lv.capturar_camara(0)
                mock_abrir.assert_not_called()
        finally:
            if viejo is None:
                os.environ.pop('ABYSS_LECTURA_VISUAL_SIN_CAMARA', None)
            else:
                os.environ['ABYSS_LECTURA_VISUAL_SIN_CAMARA'] = viejo
        self.assertFalse(res['ok'])
        self.assertIn('sin dato', res['motivo'])

    @unittest.skipUnless(lv._CV2_OK, 'cv2/numpy no están instalados en esta máquina')
    def test_cli_camara_forzada_da_sin_dato_y_codigo_2(self):
        proj = ay.nuevo_proyecto()
        env = ay.entorno(proj)
        env['ABYSS_LECTURA_VISUAL_SIN_CAMARA'] = '1'
        r = ay.ejecutar(ay.script('lectura_visual.py'), ['fotocopia', '--camara'], env)
        self.assertEqual(r.returncode, 2, f'stdout={r.stdout!r} stderr={r.stderr!r}')
        self.assertIn('sin dato', r.stdout)
        self.assertIn('cámara', r.stdout)


class CamaraFisicaNoSeProbo(unittest.TestCase):
    @unittest.skip('Regla dura del encargo: la cámara NO se enciende en esta batería '
                    'salvo lo imprescindible, y nunca por gancho; el camino "sin cámara" se '
                    'prueba forzado con ABYSS_LECTURA_VISUAL_SIN_CAMARA en CamaraForzadaSinTocarHardware')
    def test_no_se_prueba_contra_hardware_real(self):
        pass  # intencionadamente vacío: la prueba existe para DEJAR CONSTANCIA del porqué del salto


# ───────────────────────────── fotocopia: varias páginas → un solo PDF ─────────────────────────────

@unittest.skipUnless(lv._CV2_OK and lv._PIL_OK, 'cv2/numpy/Pillow no están instalados en esta máquina')
class GuardarPaginasMultiplesEnProceso(unittest.TestCase):
    """`_guardar_paginas()` en proceso, sobre imágenes ya procesadas por
    `_procesar_documento()` (nunca cámara ni escáner): varias páginas se juntan en un
    PDF, y un PNG rehúsa llevar más de una."""

    def test_una_pagina_igual_que_guardar_imagen(self):
        final, _recortado = lv._procesar_documento(lv.cv2.imread(str(OCR_PAPEL)), modo='color')
        tmp = tempfile.mkdtemp(prefix='abyss_lv_')
        salida = os.path.join(tmp, 'una.png')
        lv._guardar_paginas([final], salida)
        self.assertTrue(os.path.exists(salida))

    def test_varias_paginas_en_png_es_rehusado(self):
        final, _recortado = lv._procesar_documento(lv.cv2.imread(str(OCR_PAPEL)), modo='color')
        tmp = tempfile.mkdtemp(prefix='abyss_lv_')
        with self.assertRaises(ValueError):
            lv._guardar_paginas([final, final], os.path.join(tmp, 'varias.png'))

    def test_varias_paginas_juntan_en_un_pdf_multipagina(self):
        f1, _r1 = lv._procesar_documento(lv.cv2.imread(str(OCR_PAPEL)), modo='color')
        f2, _r2 = lv._procesar_documento(lv.cv2.imread(str(OCR_TEXTO)), modo='color')
        tmp = tempfile.mkdtemp(prefix='abyss_lv_')
        salida_1 = os.path.join(tmp, 'una.pdf')
        salida_2 = os.path.join(tmp, 'dos.pdf')
        lv._guardar_paginas([f1], salida_1)
        lv._guardar_paginas([f1, f2], salida_2)
        self.assertTrue(os.path.exists(salida_2))
        with open(salida_2, 'rb') as fh:
            self.assertEqual(fh.read(5), b'%PDF-')
        # heurística de humo (como los tres modos color/gris/umbral más arriba):
        # un pdf de dos páginas casi nunca pesa lo mismo o menos que uno de una
        self.assertGreater(os.path.getsize(salida_2), os.path.getsize(salida_1))


# ───────────────────────────── CLI: verbo desconocido / ayuda ─────────────────────────────

class CliGeneral(unittest.TestCase):
    def test_sin_argumentos_imprime_ayuda_codigo_1(self):
        proj = ay.nuevo_proyecto()
        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('lectura_visual.py'), [], env)
        self.assertEqual(r.returncode, 1)
        self.assertIn('texto', r.stdout)
        self.assertIn('fotocopia', r.stdout)

    def test_verbo_desconocido_codigo_1(self):
        proj = ay.nuevo_proyecto()
        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('lectura_visual.py'), ['inventado'], env)
        self.assertEqual(r.returncode, 1)
        self.assertIn('verbo desconocido', r.stdout)


if __name__ == '__main__':
    unittest.main()
