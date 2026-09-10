# -*- coding: utf-8 -*-
"""Falsador del gesto viejo: la documentación no puede prometer una captura que
ya no existe.

Fallo medido el 8-sep, "engaña". `abyss/plantillas/kinetica.html` cambió el
gesto de la palma: la mano abierta y quieta ya no dispara ninguna captura, abre
un HOLOGRAMA (cuatro copias espejadas de la pieza que se esté viendo, al modo
de la figura que se proyecta sobre una pirámide de metacrilato — la propia
pantalla dice que no es un holograma de verdad) y, dentro de él, CERRAR la mano
abre el sitio oficial, pero solo si la ficha trae `reconocimiento` con
evidencia. La documentación se quedó una versión atrás en dos sitios:

- `skills/kinetica/SKILL.md`: «mano abierta y quieta 3 s | captura un PNG
  (descarga local del navegador)» — falso desde que existe el holograma.
- `skills/ojo/SKILL.md`: «mano abierta y quieta un segundo captura PNG» —
  doblemente desfasado: ni es un segundo (la constante del visor es otra), ni
  captura nada; `gestos.py` solo publica la etiqueta `gesto_completado` en su
  JSON y nadie la consume.

Cuatro reglas, todas derivadas del código (nunca escritas a mano aquí), para
que la prueba caiga si se revierte el texto O si se revierte el código:

(a) ninguna de las dos skills puede decir que la mano abierta capture un PNG;
(b) si una skill nombra el gesto de la palma, tiene que nombrar el holograma;
(c) los segundos que diga la skill para ese gesto tienen que ser los de
    `SEG_QUIETA` en `abyss/plantillas/kinetica.html` — y los del gesto de
    quietud de `gestos.py` que cita `skills/ojo/SKILL.md`, los de
    `VOCABULARIO['segundos_captura_quieta']` en `abyss/gestos.py`, que NO son
    los mismos (los dos vocabularios han divergido a propósito);
(d) si una skill menciona el enlace al sitio oficial, tiene que decir también
    que sin reconocimiento no hay enlace.

Y una quinta, del lado del código: la plantilla tiene que seguir teniendo el
holograma y la puerta del enlace — si alguien deshace ese cambio, esta prueba
se pone en rojo antes que la documentación quede mintiendo al revés.
"""
import re
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PLANTILLA = RAIZ / 'abyss' / 'plantillas' / 'kinetica.html'
GESTOS_PY = RAIZ / 'abyss' / 'gestos.py'
KINETICA_PY = RAIZ / 'abyss' / 'kinetica.py'
SKILLS = {
    'skills/kinetica/SKILL.md': RAIZ / 'skills' / 'kinetica' / 'SKILL.md',
    'skills/ojo/SKILL.md': RAIZ / 'skills' / 'ojo' / 'SKILL.md',
}

# el gesto, tal y como lo nombran las dos skills
GESTO = 'mano abierta y quieta'
VENTANA = 200  # caracteres de contexto tras el gesto: lo que se le atribuye a él

RE_SEG_QUIETA = re.compile(r'\bSEG_QUIETA\s*=\s*([0-9]+(?:\.[0-9]+)?)')
RE_SEG_GESTOS = re.compile(r"'segundos_captura_quieta'\s*:\s*([0-9]+(?:\.[0-9]+)?)")
RE_SEGUNDOS = re.compile(re.escape(GESTO) + r'\s*(?:durante\s+)?(?:≥\s*)?(\d+(?:[.,]\d+)?)\s*s\b')
RE_NEGACION = re.compile(r'\b(no|nunca|ning[uú]n\w*|solo|s[oó]lo|sin|ya no)\b')
RE_COMO = re.compile(r"'como':\s*'(\w+)'")


def _llano(texto):
    """Texto plano comparable: sin adornos de markdown (`*`, `` ` ``, `>` de
    cita) y con los espacios y saltos de línea colapsados a uno — así una
    frase partida en dos líneas del fichero se sigue encontrando entera."""
    return re.sub(r'\s+', ' ', re.sub(r'[*`>]', '', texto)).lower()


def _leer(ruta):
    return _llano(ruta.read_text(encoding='utf-8'))


def _numero(cadena):
    return float(cadena.replace(',', '.'))


def _ventanas_del_gesto(texto):
    """(posición, contexto) de cada mención del gesto de la palma."""
    return [(m.start(), texto[m.end():m.end() + VENTANA])
            for m in re.finditer(re.escape(GESTO), texto)]


class ConstantesDelCodigo(unittest.TestCase):
    """La vara de esta prueba sale del código, no de este fichero."""

    def test_la_plantilla_declara_seg_quieta(self):
        m = RE_SEG_QUIETA.search(PLANTILLA.read_text(encoding='utf-8'))
        self.assertIsNotNone(
            m, 'abyss/plantillas/kinetica.html debe declarar SEG_QUIETA: es la '
               'constante contra la que se contrasta lo que dicen las skills')
        self.assertGreater(float(m.group(1)), 0)

    def test_gestos_py_declara_su_propio_segundos_de_quietud(self):
        m = RE_SEG_GESTOS.search(GESTOS_PY.read_text(encoding='utf-8'))
        self.assertIsNotNone(
            m, "abyss/gestos.py debe declarar 'segundos_captura_quieta' en su vocabulario")

    def test_la_plantilla_sigue_teniendo_holograma_y_puerta_del_enlace(self):
        # falsador del lado del CÓDIGO: si alguien devuelve el gesto a "capturar
        # un PNG", esto cae antes de que la documentación pase a mentir al revés.
        html = PLANTILLA.read_text(encoding='utf-8')
        for marca in ('abrirHolograma(', 'RECON.url', 'holoAbierto'):
            self.assertIn(marca, html,
                          f'la plantilla ya no trae {marca!r}: el holograma del gesto de la '
                          'palma habría desaparecido y la documentación quedaría desfasada')
        self.assertRegex(
            html, r'if\s*\(\s*RECON\.url\s*\)',
            'el enlace oficial debe seguir dependiendo de que exista reconocimiento')


def _seg_quieta():
    return float(RE_SEG_QUIETA.search(PLANTILLA.read_text(encoding='utf-8')).group(1))


def _seg_gestos():
    return float(RE_SEG_GESTOS.search(GESTOS_PY.read_text(encoding='utf-8')).group(1))


class NingunaSkillPrometeLaCapturaVieja(unittest.TestCase):
    def test_la_fila_falsa_de_la_tabla_ya_no_existe(self):
        texto = _leer(SKILLS['skills/kinetica/SKILL.md'])
        self.assertNotIn('captura un png (descarga local del navegador)', texto,
                         'skills/kinetica/SKILL.md sigue prometiendo el gesto viejo')

    def test_ojo_ya_no_dice_quieta_un_segundo(self):
        for nombre, ruta in SKILLS.items():
            self.assertNotIn('quieta un segundo', _leer(ruta),
                             f'{nombre} sigue con el texto viejo del gesto («quieta un segundo»)')

    def test_a_la_palma_no_se_le_atribuye_ningun_png(self):
        for nombre, ruta in SKILLS.items():
            texto = _leer(ruta)
            for pos, contexto in _ventanas_del_gesto(texto):
                for m in re.finditer('png', contexto):
                    entre = contexto[:m.start()]
                    self.assertRegex(
                        entre, RE_NEGACION,
                        f'{nombre}: el gesto de la palma (posición {pos}) vuelve a llevar '
                        f'un PNG detrás sin negarlo — {contexto[:m.end()]!r}')


class LaPalmaSeExplicaConElHolograma(unittest.TestCase):
    def test_si_se_nombra_el_gesto_se_nombra_el_holograma(self):
        for nombre, ruta in SKILLS.items():
            texto = _leer(ruta)
            if GESTO in texto:
                self.assertIn('holograma', texto,
                              f'{nombre} nombra el gesto de la palma pero no dice que abre '
                              'un holograma: es lo único que hace hoy')

    def test_las_dos_skills_nombran_el_gesto(self):
        # sin esto, las reglas de arriba se cumplirían trivialmente borrando el gesto
        for nombre, ruta in SKILLS.items():
            self.assertIn(GESTO, _leer(ruta),
                          f'{nombre} debe seguir explicando el gesto de la palma')


class LosSegundosSalenDelCodigo(unittest.TestCase):
    def test_los_segundos_del_gesto_son_los_de_seg_quieta(self):
        esperado = _seg_quieta()
        for nombre, ruta in SKILLS.items():
            dichos = [_numero(x) for x in RE_SEGUNDOS.findall(_leer(ruta))]
            self.assertTrue(
                dichos,
                f'{nombre} no dice cuántos segundos hay que aguantar la mano quieta '
                f'(SEG_QUIETA vale {esperado:g} en la plantilla)')
            for v in dichos:
                self.assertEqual(
                    v, esperado,
                    f'{nombre} dice {v:g} s para el gesto de la palma y la plantilla '
                    f'declara SEG_QUIETA = {esperado:g}')

    def test_ojo_cita_bien_el_segundo_de_quietud_de_gestos_py(self):
        # el otro vocabulario, el de gestos.py, tiene su propia constante: la skill
        # de `ojo` la cita, y tiene que ser la del código, no la del visor.
        v = _seg_gestos()
        texto = _leer(SKILLS['skills/ojo/SKILL.md'])
        escrito = ('%.1f' % v).replace('.', ',')
        self.assertIn(f'{escrito} s', texto,
                      f"skills/ojo/SKILL.md debe citar segundos_captura_quieta = {escrito} s, "
                      'el valor real de abyss/gestos.py')
        self.assertNotEqual(v, _seg_quieta(),
                            'si los dos vocabularios volvieran a coincidir, hay que reescribir '
                            'el párrafo que dice que han divergido')


class SinReconocimientoNoHayEnlace(unittest.TestCase):
    FRASE = 'sin reconocimiento no hay enlace'

    def test_quien_menciona_el_enlace_menciona_su_condicion(self):
        for nombre, ruta in SKILLS.items():
            texto = _leer(ruta)
            if 'sitio oficial' in texto or 'enlace oficial' in texto:
                self.assertIn(self.FRASE, texto,
                              f'{nombre} promete un enlace al sitio oficial sin decir que '
                              'sin reconocimiento no hay enlace')

    def test_la_skill_de_kinetica_nombra_las_vias_de_reconocimiento_del_codigo(self):
        # los valores de `como` que kinetica.py sabe escribir en piezas.json,
        # leídos del propio código: si aparece uno nuevo, la skill tiene que decirlo.
        codigo = KINETICA_PY.read_text(encoding='utf-8')
        valores = set(RE_COMO.findall(codigo))
        self.assertTrue(valores, 'kinetica.py debe escribir algún `como` en el reconocimiento')
        texto = _leer(SKILLS['skills/kinetica/SKILL.md'])
        for valor in sorted(valores):
            self.assertIn(valor, texto,
                          f'skills/kinetica/SKILL.md no explica el reconocimiento `{valor}`, '
                          'que kinetica.py sí puede escribir en piezas.json')


if __name__ == '__main__':
    unittest.main()
