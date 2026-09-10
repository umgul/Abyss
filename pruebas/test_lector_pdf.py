"""`lector_pdf.py`. Como `cuerpo.py`, se importa
DIRECTAMENTE (sin subproceso) para las funciones puras: no toca `rutas.resolver()`
ni stdin al importarse.

El PDF sintético de 6 páginas se construye con `fitz` (PyMuPDF) si está instalado
— si no, TODA la clase que lo usa se salta con `unittest.skipUnless` y el motivo
exacto («sin fitz (PyMuPDF): pip install pymupdf»), como pide el encargo. Dos
páginas (1 y 4) llevan un título a tamaño 24 sobre cuerpo a tamaño 11 → 2
secciones; solo la página 5 contiene la palabra «esdrujulisimo». Texto en ASCII
puro a propósito: la fuente base `helv` de PyMuPDF (`insert_text` sin fuente
Unicode incrustada) no representa bien los acentos (medido: los sustituye por
`�`) — no es un límite de `lector_pdf.py`, es de cómo se fabrica el PDF de
prueba, así que se evita en vez de ensuciar la prueba.
"""
import sys
import os
import json
import tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import unittest
from unittest import mock
import ayudas as ay

sys.path.insert(0, str(ay.RAIZ))
from abyss import lector_pdf as lp  # noqa: E402

try:
    import fitz
    _TIENE_FITZ = True
except ImportError:
    _TIENE_FITZ = False

try:
    import pypdf  # noqa: F401
    _TIENE_PYPDF = True
except ImportError:
    _TIENE_PYPDF = False

_CONTENIDO = [
    [("Capitulo Uno", 24), ("Aqui empieza el cuento con palabras normales.", 11),
     ("Mas texto de cuerpo para la pagina uno.", 11)],
    [("Texto de la pagina dos sin titulo grande.", 11), ("Sigue con mas contenido de cuerpo aqui.", 11)],
    [("Texto de la pagina tres cuerpo normal.", 11), ("Otra linea de cuerpo para variar el contenido.", 11)],
    [("Capitulo Dos", 24), ("La segunda seccion empieza en esta pagina cuatro.", 11),
     ("Mas cuerpo de la seccion dos.", 11)],
    [("La palabra esdrujulisimo aparece solo en esta pagina cinco.", 11), ("Cuerpo normal de la pagina cinco.", 11)],
    [("Ultima pagina del documento de prueba pagina seis.", 11), ("Cierre del contenido sintetico.", 11)],
]


def _pdf_sintetico(ruta):
    doc = fitz.open()
    for lineas in _CONTENIDO:
        pagina = doc.new_page(width=595, height=842)
        y = 72
        for texto, tam in lineas:
            pagina.insert_text((72, y), texto, fontsize=tam)
            y += tam + 14
    doc.save(ruta)
    doc.close()


@unittest.skipUnless(_TIENE_FITZ, 'sin fitz (PyMuPDF): pip install pymupdf — no se puede construir el PDF sintético')
class LectorPdfConPdfSintetico(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='abyss_pdf_')
        self.ruta_pdf = os.path.join(self.tmp, 'sintetico.pdf')
        _pdf_sintetico(self.ruta_pdf)
        self.mem = os.path.join(self.tmp, 'memory')
        os.makedirs(self.mem, exist_ok=True)

    def test_indexar_extrae_seis_paginas_y_dos_secciones(self):
        indice, err = lp.indexar(self.mem, self.ruta_pdf)
        self.assertIsNone(err)
        self.assertEqual(indice['motor'], 'fitz')
        self.assertEqual(indice['num_paginas'], 6)
        self.assertEqual(len(indice['secciones']), 2)
        self.assertEqual(indice['secciones'][0], {'titulo': 'Capitulo Uno', 'pagina_inicio': 1})
        self.assertEqual(indice['secciones'][1], {'titulo': 'Capitulo Dos', 'pagina_inicio': 4})

    def test_indice_queda_escrito_en_mem_pdf_por_sha1(self):
        indice, _ = lp.indexar(self.mem, self.ruta_pdf)
        ruta_idx = os.path.join(self.mem, 'pdf', f"{indice['sha1']}.json")
        self.assertTrue(os.path.isfile(ruta_idx))
        with open(ruta_idx, encoding='utf-8') as fh:
            en_disco = json.load(fh)
        self.assertEqual(en_disco['sha1'], lp.sha1_fichero(self.ruta_pdf))

    def test_cargar_o_indexar_reusa_el_indice_ya_escrito(self):
        indice1, _ = lp.indexar(self.mem, self.ruta_pdf)
        with mock.patch.object(lp, 'extraer', side_effect=AssertionError('no debería reextraer con índice ya en disco')):
            indice2, err = lp.cargar_o_indexar(self.mem, self.ruta_pdf)
        self.assertIsNone(err)
        self.assertEqual(indice1, indice2)

    def test_texto_secciones_numerado(self):
        indice, _ = lp.indexar(self.mem, self.ruta_pdf)
        txt = lp.texto_secciones(indice)
        self.assertIn('1. Capitulo Uno (página 1)', txt)
        self.assertIn('2. Capitulo Dos (página 4)', txt)

    def test_buscar_palabra_exclusiva_de_la_pagina_5(self):
        indice, _ = lp.indexar(self.mem, self.ruta_pdf)
        resultados = lp.buscar(indice, 'esdrujulisimo', k=5)
        self.assertTrue(resultados)
        self.assertEqual(resultados[0]['pagina'], 5)
        self.assertEqual(resultados[0]['seccion'], 'Capitulo Dos')  # página 5 cae dentro de la sección 2

    def test_ahorro_da_proporcion_menor_que_uno(self):
        indice, _ = lp.indexar(self.mem, self.ruta_pdf)
        buscados, total, prop = lp.ahorro(indice, 'esdrujulisimo', k=1)
        self.assertLess(buscados, total)
        self.assertLess(prop, 1.0)
        self.assertGreater(prop, 0.0)

    def test_leer_por_pagina_suelta(self):
        indice, _ = lp.indexar(self.mem, self.ruta_pdf)
        self.assertIn('esdrujulisimo', lp.leer(indice, '5'))

    def test_leer_por_rango_de_paginas_con_prefijo_p(self):
        indice, _ = lp.indexar(self.mem, self.ruta_pdf)
        texto = lp.leer(indice, 'p1-p2')
        self.assertIn('Capitulo Uno', texto)
        self.assertIn('pagina dos', texto)
        self.assertNotIn('esdrujulisimo', texto)

    def test_leer_por_titulo_de_seccion_hasta_la_siguiente(self):
        indice, _ = lp.indexar(self.mem, self.ruta_pdf)
        texto = lp.leer(indice, 'capitulo dos')  # subcadena, sin distinguir mayúsculas
        self.assertIn('Capitulo Dos', texto)
        self.assertIn('esdrujulisimo', texto)      # página 5, dentro de la sección 2
        self.assertNotIn('Capitulo Uno', texto)     # la sección 1 quedó fuera

    def test_leer_especificacion_no_reconocida_devuelve_none(self):
        indice, _ = lp.indexar(self.mem, self.ruta_pdf)
        self.assertIsNone(lp.leer(indice, 'un título que no existe en absoluto'))

    @unittest.skipUnless(_TIENE_PYPDF, 'sin pypdf: pip install pypdf')
    def test_motor_pypdf_forzado_detecta_las_mismas_dos_secciones(self):
        """`ABYSS_PDF_FORZAR_MOTOR=pypdf` fuerza la heurística de TEXTO aunque
        `fitz` esté instalado: «Capitulo Uno»/«Capitulo Dos» también empiezan por
        una palabra de `RE_CAPITULO`, así que la detecta igual sin mirar tamaños
        de letra."""
        with mock.patch.dict(os.environ, {'ABYSS_PDF_FORZAR_MOTOR': 'pypdf'}):
            paginas, secciones, motor, motivo = lp.extraer(self.ruta_pdf)
        self.assertIsNone(motivo)
        self.assertEqual(motor, 'pypdf')
        self.assertEqual(len(paginas), 6)
        self.assertEqual([s['pagina_inicio'] for s in secciones], [1, 4])


@unittest.skipUnless(_TIENE_FITZ, 'sin fitz (PyMuPDF): pip install pymupdf — no se puede construir el PDF sintético')
class CliPorSubproceso(unittest.TestCase):
    """La parte de `__main__` (resolución de `mem`, `--proyecto`, argv) no la
    ejercen las pruebas de arriba (llaman a las funciones puras directamente) —
    aquí sí, lanzando el guion de verdad como lo haría el usuario."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='abyss_pdf_cli_')
        self.ruta_pdf = os.path.join(self.tmp, 'sintetico.pdf')
        _pdf_sintetico(self.ruta_pdf)
        self.proj = ay.nuevo_proyecto()
        self.env = ay.entorno(self.proj)

    def test_indexar_por_cli(self):
        r = ay.ejecutar(ay.script('lector_pdf.py'), ['--indexar', self.ruta_pdf], self.env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('6 páginas', r.stdout)
        self.assertIn('2 secciones', r.stdout)
        self.assertTrue(os.path.isdir(self.proj / 'memory' / 'pdf'))

    def test_secciones_por_cli(self):
        r = ay.ejecutar(ay.script('lector_pdf.py'), ['--secciones', self.ruta_pdf], self.env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('Capitulo Uno', r.stdout)
        self.assertIn('Capitulo Dos', r.stdout)

    def test_buscar_por_cli(self):
        r = ay.ejecutar(ay.script('lector_pdf.py'), ['--buscar', self.ruta_pdf, 'esdrujulisimo'], self.env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('página 5', r.stdout)

    def test_ahorro_por_cli(self):
        r = ay.ejecutar(ay.script('lector_pdf.py'), ['--ahorro', self.ruta_pdf, 'esdrujulisimo', '1'], self.env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('ahorro de lectura', r.stdout)

    def test_leer_seccion_desconocida_sale_con_error(self):
        r = ay.ejecutar(ay.script('lector_pdf.py'), ['--leer', self.ruta_pdf, 'no existe esto'], self.env)
        self.assertEqual(r.returncode, 1)
        self.assertIn('no encuentro', r.stdout)


class SinMotorDeExtraccion(unittest.TestCase):
    def test_indexar_dice_sin_dato_si_no_hay_fitz_ni_pypdf(self):
        proj = ay.nuevo_proyecto()
        mem = str(proj / 'memory')
        ruta_falsa = str(proj / 'no_hace_falta_que_exista.pdf')
        # el PDF ni siquiera necesita existir de verdad para probar ESTA rama:
        # se comprueba antes que el fichero exista, así que se crea uno vacío
        with open(ruta_falsa, 'wb') as fh:
            fh.write(b'%PDF-1.4\n%%EOF\n')
        with mock.patch.object(lp, 'extraer', return_value=(None, None, None, 'sin dato: pip install pymupdf (o pypdf)')):
            indice, err = lp.indexar(mem, ruta_falsa)
        self.assertIsNone(indice)
        self.assertEqual(err, 'sin dato: pip install pymupdf (o pypdf)')

    def test_indexar_fichero_inexistente(self):
        proj = ay.nuevo_proyecto()
        mem = str(proj / 'memory')
        indice, err = lp.indexar(mem, str(proj / 'no_existe.pdf'))
        self.assertIsNone(indice)
        self.assertIn('no existe', err)


class IndexarConFicheroQueNoEsPdf(unittest.TestCase):
    """Fallo "engaña" medido 7-sep: `extraer()` solo atrapaba
    `ImportError`, así que un fichero de texto plano renombrado a `.pdf` hacía
    que `fitz` (instalado) reventara con `pymupdf.FileDataError` como
    traceback completo por stderr (con la ruta absoluta del fichero dentro) en
    vez del mensaje limpio que usa el resto del paquete — y la cascada a
    `pypdf`, que si podría intentarlo, nunca llegaba a ejecutarse."""

    def _fichero_falso(self, proj):
        ruta = proj / 'no_es_un_pdf.pdf'
        ruta.write_text('esto es texto plano, no un PDF de verdad\n', encoding='utf-8')
        return ruta

    def test_texto_plano_renombrado_a_pdf_no_revienta_por_cli(self):
        proj = ay.nuevo_proyecto()
        env = ay.entorno(proj)
        ruta_falsa = self._fichero_falso(proj)
        r = ay.ejecutar(ay.script('lector_pdf.py'), ['--indexar', str(ruta_falsa)], env)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        # lo que NO debe pasar: un traceback de Python crudo (con el fallo
        # original, esto es justo lo que salía).
        self.assertNotIn('Traceback (most recent call last)', r.stderr, r.stderr)
        self.assertNotIn('Traceback (most recent call last)', r.stdout, r.stdout)
        self.assertTrue(r.stdout.strip(), 'debe imprimir un mensaje limpio en vez de nada')
        # fallo "roza" medido 7-sep: `pypdf` avisa por SU PROPIO logger ("invalid
        # pdf header", "EOF marker not found") aunque el mensaje limpio de arriba
        # ya lo explica por stdout — nada debe salir por stderr en este caso.
        self.assertEqual(r.stderr.strip(), '', r.stderr)

    def test_extraer_a_pelo_no_propaga_la_excepcion(self):
        proj = ay.nuevo_proyecto()
        ruta_falsa = self._fichero_falso(proj)
        paginas, secciones, motor, motivo = lp.extraer(str(ruta_falsa))
        self.assertIsNone(motor)
        self.assertIsNone(paginas)
        self.assertIsNotNone(motivo)
        self.assertNotIn('Traceback', motivo)


@unittest.skipUnless(_TIENE_FITZ, 'sin fitz (PyMuPDF): pip install pymupdf')
class HeuristicaDeSeccionCasoMinimo(unittest.TestCase):
    """Fallo "roza" medido 7-sep: con una página de EXACTAMENTE dos líneas
    (título + una sola línea de cuerpo — la forma MÍNIMA usada como
    falsador), `tamanos[n // 2]` daba la mediana SUPERIOR para `n` par; con
    n=2 eso es el propio tamaño del título (mediana == p90), así que
    `tamano > mediana` no era nunca cierto y NINGUNA sección salía detectada.
    El falsador anterior usaba cuerpo abundante (3+ líneas por página), que
    escondía justo este caso."""

    def _pdf_de_una_pagina(self, ruta, lineas):
        doc = fitz.open()
        pagina = doc.new_page(width=595, height=842)
        y = 72
        for texto, tam in lineas:
            pagina.insert_text((72, y), texto, fontsize=tam)
            y += tam + 14
        doc.save(ruta)
        doc.close()

    def test_titulo_mas_una_sola_linea_de_cuerpo_se_detecta(self):
        tmp = tempfile.mkdtemp(prefix='abyss_pdf_min_')
        ruta = os.path.join(tmp, 'minimo.pdf')
        self._pdf_de_una_pagina(ruta, [('Titulo Solo', 24), ('Una linea de cuerpo nada mas.', 11)])
        _paginas, secciones = lp.extraer_fitz(ruta)
        # con el fallo, esto daba [] (0 secciones)
        self.assertEqual(len(secciones), 1, secciones)
        self.assertEqual(secciones[0]['titulo'], 'Titulo Solo')

    def test_solo_el_titulo_sin_cuerpo_no_revienta(self):
        """Caso degenerado (n=1): sin nada con que contrastar no hay sección
        que detectar — no es un fallo, es que no hay maquetación que comparar;
        sobre todo, no debe reventar."""
        tmp = tempfile.mkdtemp(prefix='abyss_pdf_min_')
        ruta = os.path.join(tmp, 'solotitulo.pdf')
        self._pdf_de_una_pagina(ruta, [('Titulo Solo', 24)])
        _paginas, secciones = lp.extraer_fitz(ruta)
        self.assertEqual(secciones, [])


class BuscarOrdenaPorPuntuacionDescendente(unittest.TestCase):
    """Fallo "roza": el orden de `--buscar` no tenía falsador — medido
    por mutación (invertir `puntuaciones.sort(...)` para devolver PRIMERO la
    página MENOS relevante), las 23 pruebas anteriores seguían en verde porque
    su única consulta aparecía en una sola página (con un resultado, cualquier
    orden pasa). Aquí la consulta aparece en DOS páginas con frecuencia muy
    distinta y se exige orden descendente ESTRICTO, con la más repetida
    primero — con la mutación de arriba, esto falla."""

    def test_pagina_con_mas_repeticiones_sale_primero_y_en_orden_descendente(self):
        indice = {
            'paginas': [
                'aqui se habla una vez de manzana y nada mas relevante en esta pagina',
                'manzana manzana manzana aparece muchisimas veces aqui manzana otra vez',
                'esta pagina no menciona en absoluto la palabra que se busca',
            ],
            'secciones': [],
        }
        resultados = lp.buscar(indice, 'manzana', k=5)
        self.assertEqual(len(resultados), 2, resultados)
        self.assertEqual(resultados[0]['pagina'], 2, 'la página con más repeticiones debe salir primera')
        self.assertGreater(resultados[0]['puntuacion'], resultados[1]['puntuacion'])
        puntuaciones = [r['puntuacion'] for r in resultados]
        self.assertEqual(puntuaciones, sorted(puntuaciones, reverse=True),
                          'las puntuaciones deben venir en orden descendente estricto')


class HeuristicaDeTituloEnTexto(unittest.TestCase):
    """La heurística de `extraer_pypdf()` (sin tamaños de fuente): mayúsculas,
    numeración de apartado o «Capítulo»/«Chapter»/«Sección»/«Section»."""

    def test_mayusculas_cuenta_como_titulo(self):
        self.assertTrue(lp._es_titulo_heuristico('INTRODUCCION GENERAL'))

    def test_numerado_cuenta_como_titulo(self):
        self.assertTrue(lp._es_titulo_heuristico('2.3 Resultados preliminares'))

    def test_capitulo_cuenta_como_titulo(self):
        self.assertTrue(lp._es_titulo_heuristico('Capítulo 5'))

    def test_frase_normal_no_cuenta(self):
        self.assertFalse(lp._es_titulo_heuristico('esto es una frase de cuerpo cualquiera'))

    def test_linea_larga_no_cuenta_aunque_sea_mayusculas(self):
        self.assertFalse(lp._es_titulo_heuristico('X' * 90))


if __name__ == '__main__':
    unittest.main()
