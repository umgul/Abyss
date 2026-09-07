"""`mapa_codigo.py` (T2.5 ESPECIFICACION_TANDA2.md). Igual que `cuerpo.py` y
`lector_pdf.py`: se importa directamente (sin subproceso) para las funciones
puras — no toca `rutas.resolver()` ni stdin al importarse.

Carpeta sintética con 2 módulos (uno con una clase de 2 métodos —uno decorado—
y una función suelta; el otro trivial), un fichero roto (error de sintaxis a
propósito) y dos ficheros DENTRO de directorios excluidos (`__pycache__`, `.git`)
que no deben aparecer en el mapa.
"""
import sys
import os
import json
import tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import unittest
import ayudas as ay

sys.path.insert(0, str(ay.RAIZ))
from abyss import mapa_codigo as mc  # noqa: E402

MODULO_A = '''"""Módulo A: hace cosas de prueba."""
import os
from collections import Counter as Contador


class Vehiculo(Base):
    """Un vehículo cualquiera."""

    def arrancar(self, fuerte=False):
        """Arranca el motor."""
        pass

    @staticmethod
    def modelo():
        return "generico"


def funcion_suelta(x, y=2):
    """Función suelta de prueba."""
    return x + y
'''

MODULO_B = '''"""Módulo B, más simple."""


def otra_funcion():
    pass
'''

ROTO = '''def funcion_incompleta(
    print("esto no cierra el parentesis"
'''


def _carpeta_sintetica():
    tmp = tempfile.mkdtemp(prefix='abyss_mapa_')
    raiz = os.path.join(tmp, 'paquete')
    os.makedirs(raiz, exist_ok=True)
    with open(os.path.join(raiz, 'modulo_a.py'), 'w', encoding='utf-8') as fh:
        fh.write(MODULO_A)
    with open(os.path.join(raiz, 'modulo_b.py'), 'w', encoding='utf-8') as fh:
        fh.write(MODULO_B)
    with open(os.path.join(raiz, 'roto.py'), 'w', encoding='utf-8') as fh:
        fh.write(ROTO)
    # ficheros DENTRO de directorios excluidos: no deben aparecer en el mapa
    for excluido in ('__pycache__', '.git', 'sub/node_modules'):
        d = os.path.join(raiz, excluido)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, 'no_debe_aparecer.py'), 'w', encoding='utf-8') as fh:
            fh.write('x = 1\n')
    return raiz


class ConstruirMapa(unittest.TestCase):
    def setUp(self):
        self.raiz = _carpeta_sintetica()
        self.por_fichero, self.lineas_mapa, self.lineas_codigo = mc.construir_mapa(self.raiz)
        self.analisis = dict(self.por_fichero)

    def test_solo_los_tres_ficheros_no_excluidos(self):
        self.assertEqual(sorted(self.analisis), ['modulo_a.py', 'modulo_b.py', 'roto.py'])

    def test_modulo_a_docstring_y_lineas(self):
        a = self.analisis['modulo_a.py']
        self.assertIsNone(a['error'])
        self.assertEqual(a['docstring'], 'Módulo A: hace cosas de prueba.')
        self.assertEqual(a['lineas'], len(MODULO_A.splitlines()))

    def test_modulo_a_imports(self):
        a = self.analisis['modulo_a.py']
        textos = [i['texto'] for i in a['imports']]
        self.assertIn('import os', textos)
        self.assertIn('from collections import Counter as Contador', textos)

    def test_modulo_a_clase_con_bases_y_dos_metodos(self):
        a = self.analisis['modulo_a.py']
        self.assertEqual(len(a['clases']), 1)
        c = a['clases'][0]
        self.assertEqual(c['nombre'], 'Vehiculo')
        self.assertEqual(c['bases'], ['Base'])
        self.assertEqual(c['docstring'], 'Un vehículo cualquiera.')
        self.assertEqual([m['nombre'] for m in c['metodos']], ['arrancar', 'modelo'])
        arrancar = c['metodos'][0]
        self.assertEqual(arrancar['firma'], 'self, fuerte=False')
        self.assertEqual(arrancar['docstring'], 'Arranca el motor.')
        self.assertEqual(arrancar['decoradores'], [])
        modelo = c['metodos'][1]
        self.assertEqual(modelo['decoradores'], ['staticmethod'])
        # líneas correctas: el método "arrancar" empieza en la línea 9 del fichero
        self.assertEqual(arrancar['linea_ini'], MODULO_A.splitlines().index('    def arrancar(self, fuerte=False):') + 1)

    def test_lineas_fin_exactas_clase_metodo_y_funcion(self):
        """T2.5, fallo "roza": `linea_fin` no tenía falsador — medido por
        mutación (sustituir TODOS los `node.end_lineno` por `node.lineno` en
        `mapa_codigo.py`, de modo que cada símbolo pasa a tener rango de una
        sola línea): las 19 pruebas anteriores seguían en verde porque solo se
        comprobaba `linea_ini`. Aquí se fija el rango EXACTO de la clase, sus
        dos métodos (uno de ellos decorado, cuyo `lineno` apunta al `def`, no
        al decorador) y la función suelta."""
        a = self.analisis['modulo_a.py']
        c = a['clases'][0]
        self.assertEqual((c['linea_ini'], c['linea_fin']), (6, 15))
        arrancar, modelo = c['metodos']
        self.assertEqual((arrancar['linea_ini'], arrancar['linea_fin']), (9, 11))
        self.assertEqual((modelo['linea_ini'], modelo['linea_fin']), (14, 15))
        f = a['funciones'][0]
        self.assertEqual((f['linea_ini'], f['linea_fin']), (18, 20))

    def test_modulo_a_funcion_suelta_con_firma(self):
        a = self.analisis['modulo_a.py']
        self.assertEqual(len(a['funciones']), 1)
        f = a['funciones'][0]
        self.assertEqual(f['nombre'], 'funcion_suelta')
        self.assertEqual(f['firma'], 'x, y=2')
        self.assertEqual(f['docstring'], 'Función suelta de prueba.')

    def test_modulo_b_trivial(self):
        b = self.analisis['modulo_b.py']
        self.assertIsNone(b['error'])
        self.assertEqual(len(b['funciones']), 1)
        self.assertEqual(b['funciones'][0]['nombre'], 'otra_funcion')

    def test_roto_no_tumba_el_resto_y_queda_senalado(self):
        r = self.analisis['roto.py']
        self.assertIsNotNone(r['error'])
        self.assertIn('no parsea', ' '.join(mc.lineas_texto(r, 'roto.py')))
        # y los otros dos SÍ se analizaron pese al roto
        self.assertIsNone(self.analisis['modulo_a.py']['error'])
        self.assertIsNone(self.analisis['modulo_b.py']['error'])

    def test_lineas_codigo_total_suma_los_tres(self):
        esperado = sum(len(t.splitlines()) for t in (MODULO_A, MODULO_B, ROTO))
        self.assertEqual(self.lineas_codigo, esperado)


class LineasTextoGreppable(unittest.TestCase):
    def setUp(self):
        self.raiz = _carpeta_sintetica()
        por_fichero, _, _ = mc.construir_mapa(self.raiz)
        self.analisis = dict(por_fichero)

    def test_formato_clase_y_metodo(self):
        lineas = mc.lineas_texto(self.analisis['modulo_a.py'], 'modulo_a.py')
        conjunto = '\n'.join(lineas)
        self.assertRegex(conjunto, r'modulo_a\.py:\d+-\d+  class Vehiculo\(Base\)  — Un vehículo cualquiera\.')
        self.assertRegex(conjunto, r'modulo_a\.py:\d+-\d+  Vehiculo\.arrancar\(self, fuerte=False\)  — Arranca el motor\.')
        self.assertRegex(conjunto, r'modulo_a\.py:\d+-\d+  @staticmethod Vehiculo\.modelo\(\)')

    def test_formato_roto_una_sola_linea_sin_rango(self):
        lineas = mc.lineas_texto(self.analisis['roto.py'], 'roto.py')
        self.assertEqual(len(lineas), 1)
        self.assertTrue(lineas[0].startswith('roto.py  (no parsea:'))


class EscribirMapaEnDisco(unittest.TestCase):
    def setUp(self):
        self.raiz = _carpeta_sintetica()
        self.proj = ay.nuevo_proyecto()
        self.mem = str(self.proj / 'memory')
        os.makedirs(self.mem, exist_ok=True)

    def test_escribe_txt_por_defecto_bajo_mem_mapas(self):
        r = mc.escribir_mapa(self.mem, self.raiz)
        self.assertTrue(os.path.isfile(r['ruta_txt']))
        self.assertEqual(os.path.dirname(r['ruta_txt']), os.path.join(self.mem, 'mapas'))
        self.assertEqual(r['ficheros'], 3)
        self.assertEqual(r['rotos'], ['roto.py'])
        self.assertIsNone(r['ruta_json'])

    def test_salida_personalizada_no_json_por_defecto(self):
        destino = os.path.join(str(self.proj), 'mi_mapa.txt')
        r = mc.escribir_mapa(self.mem, self.raiz, salida=destino)
        self.assertEqual(r['ruta_txt'], destino)
        self.assertTrue(os.path.isfile(destino))

    def test_json_solo_si_se_pide(self):
        r = mc.escribir_mapa(self.mem, self.raiz, con_json=True)
        self.assertIsNotNone(r['ruta_json'])
        self.assertTrue(os.path.isfile(r['ruta_json']))
        with open(r['ruta_json'], encoding='utf-8') as fh:
            datos = json.load(fh)
        self.assertEqual(sorted(datos), ['modulo_a.py', 'modulo_b.py', 'roto.py'])

    def test_medida_mapa_frente_a_codigo(self):
        r = mc.escribir_mapa(self.mem, self.raiz)
        self.assertGreater(r['lineas_codigo'], 0)
        self.assertGreater(r['lineas_mapa'], 0)
        self.assertIsNotNone(r['proporcion'])
        self.assertAlmostEqual(r['proporcion'], r['lineas_mapa'] / r['lineas_codigo'])

    def test_ultimo_mapa_y_buscar(self):
        r = mc.escribir_mapa(self.mem, self.raiz)
        self.assertEqual(mc.ultimo_mapa(self.mem), r['ruta_txt'])
        encontradas = mc.buscar_en_mapa(r['ruta_txt'], 'arrancar')
        self.assertTrue(any('Vehiculo.arrancar' in l for l in encontradas))

    def test_sin_mapa_todavia(self):
        self.assertIsNone(mc.ultimo_mapa(self.mem))


class FicheroConBomUtf8(unittest.TestCase):
    """T2 revisor (7-sep): un `.py` VÁLIDO que empieza con BOM UTF-8 (EF BB BF —
    lo escriben Visual Studio, PowerShell ISE y el Bloc de notas en Windows) se
    listaba como roto («SyntaxError: invalid non-printable character U+FEFF») y
    todos sus símbolos desaparecían del mapa, pese a que Python lo importa y
    ejecuta sin problema. `analizar_fichero()` debe abrir con `utf-8-sig`."""

    def test_bom_no_es_error_de_sintaxis_y_su_funcion_aparece(self):
        tmp = tempfile.mkdtemp(prefix='abyss_mapa_bom_')
        ruta = os.path.join(tmp, 'bom.py')
        contenido = '"""Con BOM."""\ndef f():\n    return 42\n'
        with open(ruta, 'wb') as fh:
            fh.write(b'\xef\xbb\xbf' + contenido.encode('utf-8'))
        por_fichero, _, _ = mc.construir_mapa(tmp)
        analisis = dict(por_fichero)
        self.assertIn('bom.py', analisis)
        a = analisis['bom.py']
        self.assertIsNone(a['error'], f'no debería fallar: {a.get("error")}')
        self.assertEqual([f['nombre'] for f in a['funciones']], ['f'])

    def test_bom_por_cli_no_sale_en_rotos_y_su_funcion_esta_en_el_txt(self):
        tmp = tempfile.mkdtemp(prefix='abyss_mapa_bom_')
        with open(os.path.join(tmp, 'bom.py'), 'wb') as fh:
            fh.write(b'\xef\xbb\xbf' + '"""Con BOM."""\ndef f():\n    return 42\n'.encode('utf-8'))
        proj = ay.nuevo_proyecto()
        mem = str(proj / 'memory')
        os.makedirs(mem, exist_ok=True)
        r = mc.escribir_mapa(mem, tmp)
        self.assertEqual(r['rotos'], [])
        with open(r['ruta_txt'], encoding='utf-8') as fh:
            texto = fh.read()
        self.assertIn('bom.py:', texto)
        self.assertIn('f(', texto)


class CliPorSubproceso(unittest.TestCase):
    def setUp(self):
        self.raiz = _carpeta_sintetica()
        self.proj = ay.nuevo_proyecto()
        self.env = ay.entorno(self.proj)

    def test_construir_por_cli_y_buscar(self):
        r = ay.ejecutar(ay.script('mapa_codigo.py'), [self.raiz, '--json'], self.env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('ficheros analizados: 3', r.stdout)
        self.assertIn('no parsean: roto.py', r.stdout)
        self.assertIn('json:', r.stdout)

        r2 = ay.ejecutar(ay.script('mapa_codigo.py'), ['--buscar', 'arrancar'], self.env)
        self.assertEqual(r2.returncode, 0, r2.stderr)
        self.assertIn('Vehiculo.arrancar', r2.stdout)

    def test_carpeta_inexistente(self):
        r = ay.ejecutar(ay.script('mapa_codigo.py'), [str(self.proj / 'no-existe')], self.env)
        self.assertEqual(r.returncode, 1)
        self.assertIn('no existe la carpeta', r.stdout)

    def test_buscar_sin_mapa_previo(self):
        r = ay.ejecutar(ay.script('mapa_codigo.py'), ['--buscar', 'algo'], self.env)
        self.assertEqual(r.returncode, 1)
        self.assertIn('sin ningún mapa todavía', r.stdout)

    def test_bandera_desconocida_sale_con_codigo_1(self):
        r = ay.ejecutar(ay.script('mapa_codigo.py'), [self.raiz, '--bandera-inventada'], self.env)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('--bandera-inventada', r.stdout)

    def test_bandera_desconocida_con_valor_sale_con_codigo_1(self):
        r = ay.ejecutar(ay.script('mapa_codigo.py'), [self.raiz, '--bandera-inventada', '3'], self.env)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('--bandera-inventada', r.stdout)

    def test_segundo_posicional_sale_con_codigo_1(self):
        r = ay.ejecutar(ay.script('mapa_codigo.py'),
                         [self.raiz, 'segundo_posicional_de_mas'], self.env)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('segundo_posicional_de_mas', r.stdout)


if __name__ == '__main__':
    unittest.main()
