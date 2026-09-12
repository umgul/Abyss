"""`varas.py --index` (ESPECIFICACION.md §2.3): si `MEMORY.md` supera 24 KB,
recorta las líneas de más de 200 caracteres en su ÚLTIMO separador ' · ' dentro
del límite — nunca a medias de un enlace, nunca borrando una línea entera.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import unittest
import ayudas as ay

LIMITE_LINEA = 200
LIMITE_ARCHIVO = 24 * 1024
SEP = ' · '


class VarasIndexRecortaSinBorrar(unittest.TestCase):
    def test_recorta_linea_larga_y_respeta_24kb_sin_perder_lineas(self):
        proj = ay.nuevo_proyecto()
        mem = proj / 'memory'
        mem.mkdir(parents=True, exist_ok=True)

        # una línea deliberadamente larga (>200) con varios separadores ' · '
        segmento = 'texto de relleno para hacer la línea muy larga'
        linea_larga = SEP.join(f'{segmento} número {i}' for i in range(12))
        self.assertGreater(len(linea_larga), LIMITE_LINEA)

        NUM_FILLER = 320
        TARGET_INDEX = 150  # 0-based dentro de `lineas`; línea 1-based = TARGET_INDEX + 1
        # cabecera genérica a propósito (no la de un MEMORY.md real): la leyenda se
        # inserta tras la primera línea que empiece por '# ', sea cual sea su texto.
        lineas = ['# Mi memoria', '> Varas: placeholder']
        lineas += [f'línea de relleno número {i:03d} para engordar el fichero de pruebas '
                   'y superar el límite sin tocar nada más aquí.' for i in range(NUM_FILLER)]
        lineas[2 + TARGET_INDEX] = linea_larga
        contenido = '\n'.join(lineas) + '\n'
        self.assertGreater(len(contenido.encode('utf-8')), LIMITE_ARCHIVO,
                            'el fixture de la prueba debe superar 24 KB para ejercitar el recorte')

        idx_path = mem / 'MEMORY.md'
        idx_path.write_text(contenido, encoding='utf-8')

        n_lineas_antes = len(contenido.split('\n'))

        env = ay.entorno(proj)
        # --recortar explícito: sin la bandera solo avisaría, no recorta (ESPECIFICACION.md §2.3)
        r = ay.ejecutar(ay.script('varas.py'), ['--index', '--recortar'], env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('recortadas', r.stdout)

        backups = list(mem.glob('MEMORY.md.abyss-*.bak'))
        self.assertEqual(len(backups), 1, 'debe quedar UNA copia fechada del índice antes de recortar')
        self.assertEqual(backups[0].read_text(encoding='utf-8'), contenido,
                          'la copia fechada debe ser el índice ANTES del recorte')
        linea_num_esperada = 2 + TARGET_INDEX + 1  # 1-based
        self.assertIn(f'línea {linea_num_esperada}:', r.stdout)

        nuevo = idx_path.read_text(encoding='utf-8')
        lineas_nuevas = nuevo.split('\n')
        self.assertEqual(len(lineas_nuevas), n_lineas_antes, 'no debe borrarse ninguna línea')

        linea_resultante = lineas_nuevas[2 + TARGET_INDEX]
        corte_esperado = linea_larga.rfind(SEP, 0, LIMITE_LINEA)
        self.assertNotEqual(corte_esperado, -1)
        self.assertEqual(linea_resultante, linea_larga[:corte_esperado])
        self.assertLessEqual(len(linea_resultante), LIMITE_LINEA)
        self.assertTrue(linea_resultante, 'la línea recortada no debe quedar vacía')
        self.assertLess(len(linea_resultante), len(linea_larga))

        # el resto de líneas de relleno (≤200 chars) no se tocan
        self.assertEqual(lineas_nuevas[3], lineas[3])


if __name__ == '__main__':
    unittest.main()
