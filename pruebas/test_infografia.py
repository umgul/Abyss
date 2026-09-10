"""`infografia.py`: de un CSV/JSON a un SVG con la
biblioteca estándar. No usa `mem` ni red, así que se prueba en proceso (más rápido) e
independiente de `rutas.py`; solo el paso por la CLI (`_cli`) se cubre por subprocess una
vez, para comprobar que también funciona invocado como los demás guiones del paquete.

Casos mínimos de la tarea: CSV de 5 filas -> tantos `<rect>` como filas en barras, una
`<polyline>` por serie en líneas, título escapado (`<` -> `&lt;`)."""
import csv
import json
import os
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'abyss'))
import ayudas as ay
import infografia as inf

NS = {'s': 'http://www.w3.org/2000/svg'}


def _rects_de_barra(raiz):
    """Todos los `<rect>` salvo el rectángulo de fondo (`data-role="fondo"`, un solo
    rectángulo de página que `infografia.py` marca así para no confundirse con las
    barras de verdad)."""
    return [r for r in raiz.findall('.//s:rect', NS) if r.get('data-role') != 'fondo']


def _csv_5_filas(ruta, columnas_extra=False):
    filas = [
        ('ene', 120, 80), ('feb', 90, 95), ('mar', 140, 110),
        ('abr', 60, 70), ('may', 150, 130),
    ]
    with open(ruta, 'w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        if columnas_extra:
            w.writerow(['mes', 'ventas', 'gastos'])
            w.writerows(filas)
        else:
            w.writerow(['mes', 'ventas'])
            w.writerows([(m, v) for m, v, _ in filas])
    return ruta


class InfografiaBarras(unittest.TestCase):
    def test_tantos_rect_de_barra_como_filas(self):
        d = Path(tempfile.mkdtemp(prefix='abyss_infog_'))
        csvf = _csv_5_filas(d / 'datos.csv')
        svg_texto = inf.generar_svg(*inf.leer_datos(str(csvf)),
                                     {"tipo": "barras", "x": "mes", "y": "ventas",
                                      "titulo": None, "subtitulo": None, "fuente": None,
                                      "salida": None, "ancho": 1200, "alto": 675,
                                      "oscuro": False, "es": True})
        raiz = ET.fromstring(svg_texto)
        rects = _rects_de_barra(raiz)
        self.assertEqual(len(rects), 5, 'una barra por fila (5 filas)')

    def test_barras_h_tambien_tantos_rect_como_filas(self):
        d = Path(tempfile.mkdtemp(prefix='abyss_infog_'))
        csvf = _csv_5_filas(d / 'datos.csv')
        opts = {"tipo": "barras_h", "x": "mes", "y": "ventas", "titulo": None,
                "subtitulo": None, "fuente": None, "salida": None, "ancho": 1200,
                "alto": 675, "oscuro": False, "es": True}
        svg_texto = inf.generar_svg(*inf.leer_datos(str(csvf)), opts)
        raiz = ET.fromstring(svg_texto)
        self.assertEqual(len(_rects_de_barra(raiz)), 5)

    def test_titulo_se_escapa_en_el_svg(self):
        d = Path(tempfile.mkdtemp(prefix='abyss_infog_'))
        csvf = _csv_5_filas(d / 'datos.csv')
        opts = {"tipo": "barras", "x": "mes", "y": "ventas", "titulo": "Ventas < gastos",
                "subtitulo": None, "fuente": None, "salida": None, "ancho": 1200,
                "alto": 675, "oscuro": False, "es": True}
        svg_texto = inf.generar_svg(*inf.leer_datos(str(csvf)), opts)
        self.assertIn('&lt;', svg_texto, 'el "<" del título debe salir escapado en el SVG crudo')
        self.assertNotIn('< gastos', svg_texto, 'un "<" sin escapar rompería el XML')
        raiz = ET.fromstring(svg_texto)  # si no parsea, el escapado falló
        textos = [t.text for t in raiz.findall('.//s:text', NS) if t.text]
        self.assertIn('Ventas < gastos', textos, 'una vez parseado, el texto real debe leerse sin escapar')


class InfografiaPaleta(unittest.TestCase):
    """Fallo "roza" medido 7-sep: la paleta no tenía falsador. Mutando
    `paleta_color()` para que devolviera siempre `"none"` (todas las barras,
    líneas y la leyenda sin color) la SUITE ENTERA seguía en verde. Con UNA
    sola categoría y 6 series, los `<rect>` salen en el mismo orden que las
    series (`j=0..5`): deben ser los 5 tonos de `PALETA`, y la 6ª repetir el
    color de la 1ª (el docstring de `infografia.py` dice: "Paleta sobria fija de 5
    tonos (se repiten si hay más de 5 series)")."""

    def test_seis_series_usan_los_5_tonos_y_la_sexta_repite_la_primera(self):
        d = Path(tempfile.mkdtemp(prefix='abyss_infog_'))
        csvf = d / 'datos.csv'
        cols = ['mes'] + [f's{i}' for i in range(1, 7)]
        with open(csvf, 'w', newline='', encoding='utf-8') as fh:
            w = csv.writer(fh)
            w.writerow(cols)
            w.writerow(['ene', 10, 20, 30, 40, 50, 60])
        opts = {"tipo": "barras", "x": "mes", "y": ','.join(cols[1:]), "titulo": None,
                "subtitulo": None, "fuente": None, "salida": None, "ancho": 1200,
                "alto": 675, "oscuro": False, "es": True}
        svg_texto = inf.generar_svg(*inf.leer_datos(str(csvf)), opts)
        raiz = ET.fromstring(svg_texto)
        rects = _rects_de_barra(raiz)
        # con más de una serie también se dibuja la leyenda (un <rect> de 10x10
        # por swatch, en el mismo orden j=0..5) DESPUÉS de las barras: las 6
        # primeras (una categoría x 6 series) son las barras de verdad.
        self.assertEqual(len(rects), 12, '6 barras (1 categoría x 6 series) + 6 swatches de leyenda')
        fills = [r.get('fill') for r in rects[:6]]
        self.assertEqual(fills, inf.PALETA + [inf.PALETA[0]],
                          'los 5 tonos en orden, y la 6ª serie repite el color de la 1ª')


class InfografiaLineas(unittest.TestCase):
    def test_una_polyline_por_serie(self):
        d = Path(tempfile.mkdtemp(prefix='abyss_infog_'))
        csvf = _csv_5_filas(d / 'datos.csv', columnas_extra=True)
        opts = {"tipo": "lineas", "x": "mes", "y": "ventas,gastos", "titulo": None,
                "subtitulo": None, "fuente": None, "salida": None, "ancho": 1200,
                "alto": 675, "oscuro": False, "es": True}
        svg_texto = inf.generar_svg(*inf.leer_datos(str(csvf)), opts)
        raiz = ET.fromstring(svg_texto)
        polylines = raiz.findall('.//s:polyline', NS)
        self.assertEqual(len(polylines), 2, 'dos series (ventas, gastos) -> dos polyline')
        for p in polylines:
            puntos = p.get('points').split()
            self.assertEqual(len(puntos), 5, 'un punto por fila')

    def test_columna_no_numerica_da_error_claro(self):
        d = Path(tempfile.mkdtemp(prefix='abyss_infog_'))
        csvf = _csv_5_filas(d / 'datos.csv')
        opts = {"tipo": "lineas", "x": "mes", "y": "mes", "titulo": None, "subtitulo": None,
                "fuente": None, "salida": None, "ancho": 1200, "alto": 675,
                "oscuro": False, "es": True}
        with self.assertRaises(ValueError):
            inf.generar_svg(*inf.leer_datos(str(csvf)), opts)


class InfografiaColumnasInexistentes(unittest.TestCase):
    """Fallo "roza" medido 7-sep: `--x`/`--y` con una columna que no existe se
    tragaba en silencio (`r.get(col)` da `None`, no revienta) y producía un SVG
    MUDO con código 0 — contra ESPECIFICACION.md §3 ("cualquier argumento que no
    encaje ... sale con código 1 y un mensaje claro, nunca se traga en
    silencio"). El hermano `--y noexiste` sí fallaba, pero con un motivo
    engañoso ("no es numérica en alguna fila")."""

    def test_x_inexistente_revienta_con_el_nombre_en_el_mensaje(self):
        d = Path(tempfile.mkdtemp(prefix='abyss_infog_'))
        csvf = _csv_5_filas(d / 'datos.csv')
        opts = {"tipo": "barras", "x": "noexiste", "y": "ventas", "titulo": None,
                "subtitulo": None, "fuente": None, "salida": None, "ancho": 1200,
                "alto": 675, "oscuro": False, "es": True}
        with self.assertRaises(ValueError) as cm:
            inf.generar_svg(*inf.leer_datos(str(csvf)), opts)
        self.assertIn('noexiste', str(cm.exception))

    def test_y_inexistente_revienta_con_el_nombre_no_con_el_motivo_enganoso(self):
        d = Path(tempfile.mkdtemp(prefix='abyss_infog_'))
        csvf = _csv_5_filas(d / 'datos.csv')
        opts = {"tipo": "barras", "x": "mes", "y": "noexiste", "titulo": None,
                "subtitulo": None, "fuente": None, "salida": None, "ancho": 1200,
                "alto": 675, "oscuro": False, "es": True}
        with self.assertRaises(ValueError) as cm:
            inf.generar_svg(*inf.leer_datos(str(csvf)), opts)
        self.assertIn('noexiste', str(cm.exception))
        self.assertNotIn('no es numérica', str(cm.exception),
                          'no existe la columna en absoluto: el motivo no debe hablar de numéricos')

    def test_cli_x_inexistente_sale_con_codigo_no_cero_sin_escribir_svg(self):
        d = Path(tempfile.mkdtemp(prefix='abyss_infog_'))
        csvf = _csv_5_filas(d / 'datos.csv')
        r = ay.ejecutar(ay.script('infografia.py'),
                         [str(csvf), '--tipo', 'barras', '--x', 'noexiste'], dict(os.environ))
        self.assertNotEqual(r.returncode, 0, 'una columna inexistente no debe salir con código 0')
        self.assertFalse(list(d.glob('*.svg')), 'no debe escribir ningún SVG mudo')
        self.assertIn('noexiste', r.stdout)


class InfografiaTabla(unittest.TestCase):
    def test_tabla_tiene_cabecera_y_una_fila_por_registro(self):
        d = Path(tempfile.mkdtemp(prefix='abyss_infog_'))
        csvf = _csv_5_filas(d / 'datos.csv', columnas_extra=True)
        opts = {"tipo": "tabla", "x": None, "y": None, "titulo": "Resumen", "subtitulo": None,
                "fuente": None, "salida": None, "ancho": 800, "alto": 200,
                "oscuro": False, "es": True}
        filas, columnas = inf.leer_datos(str(csvf))
        svg_texto = inf.generar_svg(filas, columnas, opts)
        raiz = ET.fromstring(svg_texto)
        cabecera = [t.text for t in raiz.findall('.//s:text', NS) if t.text in columnas]
        self.assertEqual(set(cabecera), set(columnas))
        # alto mínimo pedido (200) debe crecer para caber cabecera + 5 filas
        alto_real = int(raiz.get('height'))
        self.assertGreater(alto_real, 200)


class InfografiaJson(unittest.TestCase):
    def test_json_lista_de_objetos_y_json_columnar_dan_lo_mismo(self):
        d = Path(tempfile.mkdtemp(prefix='abyss_infog_'))
        lista = [{"mes": "ene", "ventas": 10}, {"mes": "feb", "ventas": 20}]
        columnar = {"mes": ["ene", "feb"], "ventas": [10, 20]}
        (d / 'lista.json').write_text(json.dumps(lista), encoding='utf-8')
        (d / 'columnar.json').write_text(json.dumps(columnar), encoding='utf-8')
        f1, c1 = inf.leer_datos(str(d / 'lista.json'))
        f2, c2 = inf.leer_datos(str(d / 'columnar.json'))
        self.assertEqual(f1, f2)
        self.assertEqual(c1, c2)


class InfografiaCLI(unittest.TestCase):
    def test_cli_escribe_svg_valido_por_defecto_junto_al_csv(self):
        d = Path(tempfile.mkdtemp(prefix='abyss_infog_'))
        csvf = _csv_5_filas(d / 'datos.csv')
        r = ay.ejecutar(ay.script('infografia.py'), [str(csvf), '--tipo', 'barras'], dict(os.environ))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        salida = Path(r.stdout.strip().splitlines()[-1])
        self.assertTrue(salida.exists())
        ET.parse(salida)  # revienta si no es XML válido

    def test_tipo_desconocido_sale_con_1_sin_escribir_nada(self):
        d = Path(tempfile.mkdtemp(prefix='abyss_infog_'))
        csvf = _csv_5_filas(d / 'datos.csv')
        r = ay.ejecutar(ay.script('infografia.py'), [str(csvf), '--tipo', 'pastel'], dict(os.environ))
        self.assertEqual(r.returncode, 1)
        self.assertFalse(list(d.glob('*.svg')))

    def test_fichero_inexistente_sale_con_2(self):
        d = Path(tempfile.mkdtemp(prefix='abyss_infog_'))
        r = ay.ejecutar(ay.script('infografia.py'),
                         [str(d / 'no_existe.csv'), '--tipo', 'barras'], dict(os.environ))
        self.assertEqual(r.returncode, 2)
        self.assertIn('sin infografía', r.stdout)


class InfografiaAnchoAltoFueraDeRango(unittest.TestCase):
    """T2 revisor (7-sep): `--ancho`/`--alto` negativos o cero se aceptaban sin
    avisar (rc 0) y dejaban un SVG con `width`/`height` negativos que ningún
    navegador dibuja — contra ESPECIFICACION.md §3. El mínimo sale de los propios
    márgenes del módulo (`_margenes`), no de un número decretado."""

    def test_ancho_negativo_sale_con_codigo_no_cero_sin_escribir_svg(self):
        d = Path(tempfile.mkdtemp(prefix='abyss_infog_'))
        csvf = _csv_5_filas(d / 'datos.csv')
        destino = d / 'x.svg'
        r = ay.ejecutar(ay.script('infografia.py'),
                         [str(csvf), '--tipo', 'barras', '--ancho', '-5', '--salida', str(destino)],
                         dict(os.environ))
        self.assertNotEqual(r.returncode, 0, '--ancho -5 no debe salir con código 0')
        self.assertFalse(destino.exists(), 'no debe escribir ningún SVG mudo')

    def test_ancho_cero_sale_con_codigo_no_cero_sin_escribir_svg(self):
        d = Path(tempfile.mkdtemp(prefix='abyss_infog_'))
        csvf = _csv_5_filas(d / 'datos.csv')
        destino = d / 'x.svg'
        r = ay.ejecutar(ay.script('infografia.py'),
                         [str(csvf), '--tipo', 'barras', '--ancho', '0', '--salida', str(destino)],
                         dict(os.environ))
        self.assertNotEqual(r.returncode, 0, '--ancho 0 no debe salir con código 0')
        self.assertFalse(destino.exists(), 'no debe escribir ningún SVG mudo')

    def test_alto_negativo_sale_con_codigo_no_cero_sin_escribir_svg(self):
        d = Path(tempfile.mkdtemp(prefix='abyss_infog_'))
        csvf = _csv_5_filas(d / 'datos.csv')
        destino = d / 'x.svg'
        r = ay.ejecutar(ay.script('infografia.py'),
                         [str(csvf), '--tipo', 'barras', '--alto', '-100', '--salida', str(destino)],
                         dict(os.environ))
        self.assertNotEqual(r.returncode, 0, '--alto -100 no debe salir con código 0')
        self.assertFalse(destino.exists(), 'no debe escribir ningún SVG mudo')


if __name__ == '__main__':
    unittest.main()
