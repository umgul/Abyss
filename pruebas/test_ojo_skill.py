# -*- coding: utf-8 -*-
"""`skills/ojo/SKILL.md`: la descripción del
frontmatter es lo primero que lee el enrutador de skills, antes que nada del
cuerpo — así que el verbo que dispara cada frase importa tanto como la frase.

Fallo "rompe" medido 7-sep: la descripción listaba «lee lo que hay en esta
foto» / «read what's in this photo» como disparadores de `mirar` (el verbo que
ABRE LA WEBCAM), justo lo contrario de la ley que la propia skill declara dos
párrafos más abajo («una cámara que se enciende sola no es un ojo, es
vigilancia»). Quien pidiera leer una foto que YA TIENE se llevaba la cámara
encendida en vez de OCR (`texto`). Este falsador comprueba que cada frase
disparadora cuelga del verbo correcto, en los dos idiomas, sin fiarse de que
"la frase existe en algún sitio del fichero" — que es justo lo que un test
más laxo no habría cazado."""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ayudas as ay  # noqa: E402

RUTA_SKILL = ay.RAIZ / 'skills' / 'ojo' / 'SKILL.md'


def _colapsar(texto):
    """Espacios/saltos de línea a uno solo — el frontmatter YAML pliega
    (`description: >`) una frase larga en varias líneas del FICHERO; buscar
    "de un tirón" evita que un salto de línea (que no significa nada para
    quien lee la skill renderizada) rompa la búsqueda."""
    return re.sub(r'\s+', ' ', texto)


def _grupos_por_verbo(descripcion):
    """Trocea la descripción en los tramos de texto que preceden a cada marca
    `` (`verbo`) ``, EN EL ORDEN en que aparecen. Como las marcas son
    secuenciales y no se solapan, cada grupo capturado es exactamente el
    tramo de disparadores que la propia skill le atribuye a ese verbo — con
    los ocho verbos repetidos dos veces (castellano y luego inglés), salen 16
    grupos."""
    return re.findall(r'([^(]*?)\(`(\w+)`\)', descripcion)


class DisparadoresDeCadaVerboEnElGrupoCorrecto(unittest.TestCase):
    def setUp(self):
        self.assertTrue(RUTA_SKILL.is_file(), 'skills/ojo/SKILL.md debe existir en el repo')
        texto = RUTA_SKILL.read_text(encoding='utf-8')
        lineas = texto.splitlines()
        self.assertEqual(lineas[0].strip(), '---', 'el fichero debe empezar con frontmatter YAML')
        fin = next(i for i in range(1, len(lineas)) if lineas[i].strip() == '---')
        self.bloque = _colapsar('\n'.join(lineas[1:fin]))

    def test_los_dieciseis_grupos_sean_los_ocho_verbos_por_dos_idiomas(self):
        grupos = _grupos_por_verbo(self.bloque)
        verbos = [v for _, v in grupos]
        ocho = ['mirar', 'texto', 'fotocopia', 'tarjeta', 'manual', 'despiece', 'prompt3d', 'gestos']
        self.assertEqual(verbos, ocho + ocho, 'la descripción debe listar los ocho verbos, dos veces')

    def test_leer_una_foto_que_ya_se_tiene_no_cuelga_de_mirar_en_castellano(self):
        grupos = _grupos_por_verbo(self.bloque)
        grupo_mirar_es = grupos[0][0]
        self.assertNotIn('lee lo que hay en esta foto', grupo_mirar_es,
                          '"lee lo que hay en esta foto" es OCR de una foto YA TOMADA: '
                          'no debe disparar `mirar` (que abre la webcam)')

    def test_leer_una_foto_que_ya_se_tiene_cuelga_de_texto_en_castellano(self):
        grupos = _grupos_por_verbo(self.bloque)
        grupo_texto_es = grupos[1][0]
        self.assertIn('lee lo que hay en esta foto', grupo_texto_es,
                       '"lee lo que hay en esta foto" es OCR: debe disparar `texto`')

    def test_leer_una_foto_que_ya_se_tiene_no_cuelga_de_mirar_en_ingles(self):
        grupos = _grupos_por_verbo(self.bloque)
        grupo_mirar_en = grupos[8][0]
        self.assertEqual(grupos[8][1], 'mirar')
        self.assertNotIn("read what's in this photo", grupo_mirar_en,
                          '"read what\'s in this photo" no debe disparar `mirar` (abre la webcam)')

    def test_leer_una_foto_que_ya_se_tiene_cuelga_de_texto_en_ingles(self):
        grupos = _grupos_por_verbo(self.bloque)
        grupo_texto_en = grupos[9][0]
        self.assertEqual(grupos[9][1], 'texto')
        self.assertIn("read what's in this photo", grupo_texto_en,
                       '"read what\'s in this photo" es OCR: debe disparar `texto`')

    def test_mirar_conserva_disparadores_de_camara_en_vivo(self):
        grupos = _grupos_por_verbo(self.bloque)
        grupo_mirar_es = grupos[0][0]
        grupo_mirar_en = grupos[8][0]
        for frase in ('mira por la webcam', 'haz una foto con la cámara',
                      'qué ves por la cámara ahora mismo'):
            self.assertIn(frase, grupo_mirar_es)
        for frase in ('look through the', 'webcam', 'take a picture with the camera',
                      'what do you see through the', 'camera right now'):
            self.assertIn(frase, grupo_mirar_en)


if __name__ == '__main__':
    unittest.main()
