"""`docs/leyes.md`/`docs/leyes.en.md` y `docs/AUDITORIA_DE_ABYSS.md`/
`docs/AUDITORIA_DE_ABYSS.en.md` son pares espejo (igual que README.md/README.en.md).
Tres cosas se comprueban de cada par:

1. Mismo número de secciones de primer nivel (`^## `) — si un idioma gana o
   pierde una sección, el otro se queda desincronizado sin que nadie lo note
   a simple vista.
2. Cada documento enlaza al otro en su "primera línea" — no la línea 1 del
   fichero a secas (esa es el título `# ...`), sino la primera línea no vacía
   que sigue al título, igual que hace README.md/README.en.md
   (`*[English version](README.en.md)*` / `*[Versión en castellano]
   (README.md)*`).
3. Ningún documento inglés lleva palabras de control castellanas («ley»,
   «medida», «vara») como palabra suelta. La excepción declarada («términos
   citados a propósito») no hace falta activarla a mano: `docs/
   AUDITORIA_DE_ABYSS.en.md` reproduce la salida CRUDA de `auditar.py`
   (`a_markdown()`) tal cual, que solo nombra ficheros como `varas.py`
   (plural, dentro de un `` ` ``) — nunca la palabra suelta «vara»; por eso el
   propio guion sirve de fixture real, sin necesitar datos sintéticos.

Un cuarto par, aparte, es README.md/README.en.md (arreglo README.en.md:296,
7-sep): la traducción de una negación es justo donde una garantía de
privacidad se invierte sin que nadie lo note a simple vista, así que hay una
clase propia para ese par y esa frase concreta (la vía `local` de
`imagen.py crear`), no una regla general de polaridad para todo el documento.
"""
import re
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DOCS = RAIZ / 'docs'

PARES = (
    (DOCS / 'leyes.md', DOCS / 'leyes.en.md'),
    (DOCS / 'AUDITORIA_DE_ABYSS.md', DOCS / 'AUDITORIA_DE_ABYSS.en.md'),
)

RE_SECCION = re.compile(r'^## ', re.MULTILINE)
RE_ENLACE = re.compile(r'\[[^\]]*\]\(([^)]+)\)')
# palabras de control, como palabra suelta (no dentro de "varas.py", "leyes.md"...)
RE_CONTROL = re.compile(r'\b(ley|medida|vara)\b', re.IGNORECASE)


def _primera_linea_tras_titulo(texto):
    """La primera línea no vacía después del título `# ...` (o de la línea 1
    si no hay título) — el mismo hueco donde README.md pone su enlace cruzado."""
    lineas = texto.splitlines()
    i = 1 if lineas and lineas[0].startswith('# ') else 0
    while i < len(lineas) and lineas[i].strip() == '':
        i += 1
    return lineas[i] if i < len(lineas) else ''


class DocumentosEspejoTienenLasMismasSecciones(unittest.TestCase):
    def test_mismo_numero_de_secciones_de_primer_nivel(self):
        for es, en in PARES:
            n_es = len(RE_SECCION.findall(es.read_text(encoding='utf-8')))
            n_en = len(RE_SECCION.findall(en.read_text(encoding='utf-8')))
            self.assertEqual(
                n_es, n_en,
                f'{es.name} tiene {n_es} secciones de primer nivel (`## `) y '
                f'{en.name} tiene {n_en} — deben coincidir')
            self.assertGreater(n_es, 0, f'{es.name} no declara ninguna sección `## `')


class DocumentosEspejoSeEnlazanEntreSi(unittest.TestCase):
    def test_cada_documento_enlaza_al_otro_en_su_primera_linea(self):
        for es, en in PARES:
            linea_es = _primera_linea_tras_titulo(es.read_text(encoding='utf-8'))
            linea_en = _primera_linea_tras_titulo(en.read_text(encoding='utf-8'))
            self.assertIn(en.name, linea_es,
                          f'{es.name} debe enlazar a {en.name} en su primera línea, no: {linea_es!r}')
            self.assertIn(es.name, linea_en,
                          f'{en.name} debe enlazar a {es.name} en su primera línea, no: {linea_en!r}')
            for etiqueta, linea in ((es.name, linea_es), (en.name, linea_en)):
                enlaces = RE_ENLACE.findall(linea)
                self.assertTrue(enlaces, f'{etiqueta}: la primera línea no lleva ningún enlace markdown')


class DocumentosInglesesNoLlevanPalabrasDeControlSueltas(unittest.TestCase):
    def test_sin_ley_medida_vara_como_palabra_suelta(self):
        for _, en in PARES:
            texto = en.read_text(encoding='utf-8')
            hallados = RE_CONTROL.findall(texto)
            self.assertEqual(
                hallados, [],
                f'{en.name} contiene palabras de control castellanas sueltas: {hallados} '
                '(si es un término citado a propósito, debe ir dentro de una palabra más larga '
                'o quedar fuera de este documento)')


class LaViaLocalDiceLoMismoEnLosDosReadme(unittest.TestCase):
    """README.en.md:296 decía de la vía `local` de `imagen.py crear` que
    'keeps the prompt off the machine' — lo CONTRARIO de README.md:292 («no
    saca el prompt de la máquina») y del propio README.en.md:391 («keeps the
    prompt on the machine»). Falsador barato: ninguna línea del inglés une
    `local` con «off the machine»; y mejor, toda frase que hable de qué le
    pasa al prompt por la vía `local` en relación con "the machine" tiene que
    decir 'on the machine' en inglés y NO decir 'saca el prompt' sin negar en
    castellano."""

    TEXTO_ES = (RAIZ / 'README.md').read_text(encoding='utf-8')
    TEXTO_EN = (RAIZ / 'README.en.md').read_text(encoding='utf-8')

    def test_ninguna_linea_del_ingles_une_local_con_off_the_machine(self):
        for n, linea in enumerate(self.TEXTO_EN.splitlines(), start=1):
            if 'local' in linea.lower() and 'off the machine' in linea.lower():
                self.fail(
                    f'README.en.md:{n} une "local" con "off the machine" — '
                    f'la vía local es la que SE QUEDA en la máquina, no la '
                    f'que sale de ella: {linea!r}')

    def test_las_frases_sobre_la_via_local_y_el_prompt_son_coherentes(self):
        frases_en = [l for l in self.TEXTO_EN.splitlines()
                     if 'local' in l.lower() and 'prompt' in l.lower()
                     and 'the machine' in l.lower()]
        self.assertTrue(
            frases_en,
            'README.en.md no tiene ninguna frase que junte `local`, "prompt" '
            'y "the machine" — el falsador se queda sin fixture')
        for linea in frases_en:
            self.assertIn('on the machine', linea,
                           f'debe decir "on the machine": {linea!r}')
            self.assertNotIn('off the machine', linea,
                              f'no debe decir "off the machine": {linea!r}')

        frases_es = [l for l in self.TEXTO_ES.splitlines()
                     if 'local' in l.lower() and 'prompt' in l.lower()
                     and 'máquina' in l.lower()]
        self.assertTrue(
            frases_es,
            'README.md no tiene ninguna frase que junte `local`, "prompt" y '
            '"máquina" — el falsador se queda sin fixture')
        for linea in frases_es:
            if 'saca el prompt' in linea.lower():
                self.assertIn('no saca el prompt', linea.lower(),
                               f'"saca el prompt" sin negar en: {linea!r}')


if __name__ == '__main__':
    unittest.main()
