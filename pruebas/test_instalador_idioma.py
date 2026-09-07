# -*- coding: utf-8 -*-
"""`instalar.py` T5.2 (ESPECIFICACION_TANDA5.md): español e inglés en el propio
instalador. Todo lo que ve el usuario (ventana, botones, avisos, tabla de
módulos, mensajes de error, resumen final) pasa por `TEXTOS`/`_texto()`, con
`--idioma es|en` o, por defecto, el idioma del sistema. Los guiones de
`abyss/*.py` siguen en castellano siempre — eso NO es lo que se prueba aquí.

Tres pruebas de la especificación:
  1. `--idioma en --listar` no imprime ni una palabra de la lista castellana de
     control («módulo», «instalado», «ganchos») — con su falsador: `--idioma es`
     SÍ debe llevarlas, para que la prueba (1) no sea vacuamente cierta.
  2. Ningún texto del instalador queda fuera del diccionario: un escaneo por
     `ast` de `instalar.py` busca cadenas literales (o f-strings con parte
     literal) que lleguen de verdad a `print`/`input`/`sys.stderr.write`/los
     diálogos de Tk/`mensajes.append` SIN pasar por `_texto(...)` — con dos
     excepciones documentadas y comprobadas por su cuenta: el nombre del propio
     programa ("instalar:", invariante en los dos idiomas, como "git:") y la
     ÚNICA línea bilingüe a propósito (el error de un `--idioma` inválido, antes
     de que haya ningún idioma resuelto con el que elegir uno).
  3. `TEXTOS['es']` y `TEXTOS['en']` declaran EXACTAMENTE las mismas claves —
     una traducción a medias (con `_texto()` cayendo a castellano en silencio)
     no debe pasar desapercibida.

Arreglo del 7-sep (hallazgo del revisor sobre instalar.py:534 y :1309): dos
bloques largos vivían FUERA de `TEXTOS` (la columna «para qué» de
`--dependencias`, en `DEPENDENCIAS[...]['para']`; y la línea de cada módulo en
`--listar`, en `MODULOS[...]['linea']`) y salían en castellano crudo con
`--idioma en`, sin ninguna nota que lo avisara — pese a que el propio
comentario de cabecera de `TEXTOS` prometía que TODA cadena que ve el usuario
pasa por su traducción. Ahora cada entrada lleva su `para_en`/`linea_en`
emparejado (mismo fail-closed que `_texto()`: cae al castellano si falta la
traducción), elegido por `_para_localizado()`/`_linea_localizada()` — ver
`IdiomaEnNoDejaBloquesLargosSinTraducir` (falsador con la lista de palabras de
control del propio hallazgo) y `DependenciasYModulosCaenAlCastellanoSiFaltaLaTraduccion`.

Igual que `test_instalador.py`/`test_instalador_roza.py`: se importa
`instalar.py` DIRECTAMENTE por ruta de fichero para las pruebas en proceso
(`_cargar_instalador`), y por `subprocess` (vía `ayudas.ejecutar`) para las que
miden la salida de la CLI de verdad — la única forma de comprobar qué ve el
usuario en su terminal tal cual sale."""
import ast
import os
import re
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import unittest
import ayudas as ay


def _cargar_instalador():
    ruta = ay.RAIZ / 'instalar.py'
    import importlib.util
    spec = importlib.util.spec_from_file_location('abyss_instalador_bajo_prueba_idioma', str(ruta))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _listar(idioma, extra_env=None):
    """`instalar.py --listar --idioma <idioma>` de verdad, por subprocess, sobre
    un `settings.json` temporal (nunca el real) — mide la salida TAL COMO la
    vería el usuario, no una `_listar()` en proceso que podría no coincidir con
    lo que la CLI hace de verdad."""
    tmp = Path(tempfile.mkdtemp(prefix='abyss_listar_idioma_'))
    settings_ruta = tmp / 'settings.json'
    env = dict(os.environ)
    if extra_env:
        env.update(extra_env)
    r = ay.ejecutar(ay.RAIZ / 'instalar.py',
                     ['--listar', '--idioma', idioma, '--settings', str(settings_ruta)], env)
    return r


def _dependencias(idioma, extra_env=None):
    """`instalar.py --dependencias --idioma <idioma>` de verdad, por subprocess
    (mismo motivo que `_listar()`: medir la salida tal cual la ve el usuario)."""
    env = dict(os.environ)
    if extra_env:
        env.update(extra_env)
    r = ay.ejecutar(ay.RAIZ / 'instalar.py', ['--dependencias', '--idioma', idioma], env)
    return r


# Vocabulario de control castellano — exactamente el que cita la especificación
# (T5.2, prueba de `--idioma en --listar`). Palabra completa (`\b`) e
# insensible a mayúsculas: así "módulos" (plural, aparece en la línea de
# `mapa_codigo`, que es documentación del código y se muestra en los dos
# idiomas a propósito) no cuenta como la palabra de control "módulo".
_PALABRAS_DE_CONTROL_ES = ('módulo', 'instalado', 'ganchos')


def _palabras_de_control_presentes(texto):
    return [p for p in _PALABRAS_DE_CONTROL_ES
            if re.search(rf'\b{re.escape(p)}\b', texto, re.IGNORECASE)]


class ListarEnInglesNoLlevaVocabularioDeControlCastellano(unittest.TestCase):
    """T5.2, prueba de la especificación, literal: "--idioma en --listar no
    imprime ni una palabra de la lista castellana de control"."""

    def test_idioma_en_listar_sin_palabras_de_control(self):
        r = _listar('en')
        self.assertEqual(r.returncode, 0, f'stdout={r.stdout!r} stderr={r.stderr!r}')
        presentes = _palabras_de_control_presentes(r.stdout)
        self.assertEqual(presentes, [],
                          f'--idioma en --listar no debe llevar vocabulario de control castellano: {presentes}')

    def test_falsador_idioma_es_listar_si_las_lleva(self):
        """Si esta prueba NO estuviera cazando nada de verdad (p. ej. porque
        ninguna palabra de control apareciera jamás en la salida, en ningún
        idioma), la prueba de arriba sería trivialmente cierta y no mediría
        nada. En castellano («toca: ganchos ...», la etiqueta "instalado"/
        "no instalado") SÍ deben salir."""
        r = _listar('es')
        self.assertEqual(r.returncode, 0, f'stdout={r.stdout!r} stderr={r.stderr!r}')
        presentes = _palabras_de_control_presentes(r.stdout)
        self.assertTrue(presentes, '--idioma es --listar debería llevar vocabulario de control castellano '
                                    '(si esto falla, la prueba de arriba no está midiendo nada)')

    def test_idioma_en_no_omite_la_documentacion_de_los_modulos(self):
        """El detalle `toca`/`aviso` SÍ se omite en inglés (decisión de diseño,
        ver el comentario junto a `TEXTOS` en instalar.py): la línea de cada
        módulo se sigue viendo en los dos idiomas, pero desde el arreglo del
        7-sep (ENGAÑA: la especificación promete que TODA cadena que ve el
        usuario pasa por su traducción) ya NO es el mismo castellano crudo en
        inglés — `mod['linea_en']` la traduce de verdad."""
        r = _listar('en')
        self.assertIn('continuidad', r.stdout)
        self.assertIn("Stitches memory across threads", r.stdout,
                       'la línea de "continuidad" debe salir traducida (mod["linea_en"]) con --idioma en')
        self.assertNotIn('Cose la memoria entre hilos', r.stdout,
                          '--idioma en no debe dejar la línea de "continuidad" en castellano crudo')

    def test_idioma_es_sigue_mostrando_la_linea_en_castellano(self):
        """Falsador de la prueba de arriba: en castellano la línea debe seguir
        siendo la de `mod['linea']`, nunca la traducción."""
        r = _listar('es')
        self.assertIn('Cose la memoria entre hilos', r.stdout)


# Palabras castellanas de control para el falsador de abajo — las mismas
# cuatro que cita el hallazgo del 7-sep («para», «con», «sin», «lee»), palabra
# completa e insensible a mayúsculas (para no cazar, p. ej., "lee" dentro de
# "lees" en inglés... aunque en la práctica esa palabra no aparece en inglés).
_PALABRAS_DE_CONTROL_ES_BLOQUES_LARGOS = ('para', 'con', 'sin', 'lee')
_TILDE_O_ENYE = re.compile(r'[áéíóúÁÉÍÓÚñÑ]')


def _bloques_largos_sin_traducir_presentes(texto):
    """Vocabulario de control de `_PALABRAS_DE_CONTROL_ES_BLOQUES_LARGOS`
    presente como palabra completa, o cualquier tilde/eñe — señal de que un
    bloque largo (la columna «para qué» de `--dependencias`, o la línea de
    `--listar`) se quedó en castellano crudo pese a `--idioma en`."""
    hallados = [p for p in _PALABRAS_DE_CONTROL_ES_BLOQUES_LARGOS
                if re.search(rf'\b{re.escape(p)}\b', texto, re.IGNORECASE)]
    if _TILDE_O_ENYE.search(texto):
        hallados.append('<tilde/eñe>')
    return hallados


class IdiomaEnNoDejaBloquesLargosSinTraducir(unittest.TestCase):
    """Falsador del hallazgo del revisor (7-sep, instalar.py:534 y :1309): antes
    de `para_en`/`linea_en`, `--idioma en --dependencias` imprimía las 12 filas
    con la columna «para qué» ENTERA en castellano (viene de
    `DEPENDENCIAS[...]['para']`, instalar.py:534, sin pasar por `_texto()`), y
    `--idioma en --listar` imprimía 22 de sus 24 líneas con la descripción de
    módulo entera en castellano (`mod['linea']`, instalar.py:1309) — sin
    ninguna nota que lo avisara para `--dependencias`, y con una nota en
    `--listar` que además explicaba mal lo que pasaba (justificaba omitir
    `toca`/`aviso`, control vocabulary pequeño, y dejaba sin explicar el bloque
    grande que sí se imprimía). Estas pruebas exigen que ninguno de los dos
    bloques largos quede sin traducir: ni una tilde/eñe, ni las palabras de
    control «para»/«con»/«sin»/«lee» como palabra completa."""

    def test_dependencias_en_sin_bloques_largos_sin_traducir(self):
        r = _dependencias('en')
        self.assertEqual(r.returncode, 0, f'stdout={r.stdout!r} stderr={r.stderr!r}')
        hallados = _bloques_largos_sin_traducir_presentes(r.stdout)
        self.assertEqual(hallados, [],
                          f'--idioma en --dependencias no debe llevar castellano sin traducir: {hallados}\n'
                          f'{r.stdout}')

    def test_falsador_dependencias_es_si_los_lleva(self):
        r = _dependencias('es')
        self.assertEqual(r.returncode, 0, f'stdout={r.stdout!r} stderr={r.stderr!r}')
        hallados = _bloques_largos_sin_traducir_presentes(r.stdout)
        self.assertTrue(hallados, '--idioma es --dependencias debería llevar castellano '
                                   '(si esto falla, la prueba de arriba no está midiendo nada)')

    def test_listar_en_sin_bloques_largos_sin_traducir(self):
        r = _listar('en')
        self.assertEqual(r.returncode, 0, f'stdout={r.stdout!r} stderr={r.stderr!r}')
        hallados = _bloques_largos_sin_traducir_presentes(r.stdout)
        self.assertEqual(hallados, [],
                          f'--idioma en --listar no debe llevar castellano sin traducir: {hallados}\n{r.stdout}')

    def test_falsador_listar_es_si_los_lleva(self):
        r = _listar('es')
        self.assertEqual(r.returncode, 0, f'stdout={r.stdout!r} stderr={r.stderr!r}')
        hallados = _bloques_largos_sin_traducir_presentes(r.stdout)
        self.assertTrue(hallados, '--idioma es --listar debería llevar castellano '
                                   '(si esto falla, la prueba de arriba no está midiendo nada)')


class DependenciasYModulosCaenAlCastellanoSiFaltaLaTraduccion(unittest.TestCase):
    """`_para_localizado()`/`_linea_localizada()` (T5.2): mismo fail-closed que
    `_texto()` — si una entrada NO declarara `para_en`/`linea_en`, cae al
    castellano de `para`/`linea` en vez de imprimir una fila muda o reventar."""

    def test_para_localizado_cae_al_castellano_si_falta_para_en(self):
        inst = _cargar_instalador()
        entrada_sin_traducir = {'para': 'texto castellano de prueba sin para_en'}
        self.assertEqual(inst._para_localizado('en', entrada_sin_traducir),
                          'texto castellano de prueba sin para_en')

    def test_para_localizado_usa_para_en_cuando_existe(self):
        inst = _cargar_instalador()
        entrada = {'para': 'texto castellano', 'para_en': 'english text'}
        self.assertEqual(inst._para_localizado('en', entrada), 'english text')
        self.assertEqual(inst._para_localizado('es', entrada), 'texto castellano')

    def test_linea_localizada_cae_al_castellano_si_falta_linea_en(self):
        inst = _cargar_instalador()
        mod_sin_traducir = {'linea': 'línea castellana de prueba sin linea_en'}
        self.assertEqual(inst._linea_localizada('en', mod_sin_traducir),
                          'línea castellana de prueba sin linea_en')

    def test_linea_localizada_usa_linea_en_cuando_existe(self):
        inst = _cargar_instalador()
        mod = {'linea': 'línea castellana', 'linea_en': 'english line'}
        self.assertEqual(inst._linea_localizada('en', mod), 'english line')
        self.assertEqual(inst._linea_localizada('es', mod), 'línea castellana')

    def test_todas_las_entradas_de_verdad_declaran_su_traduccion(self):
        """Falsador de una regresión donde alguien añadiera un módulo o una
        dependencia nueva y se olvidara de `linea_en`/`para_en`: el fallback
        haría que la CLI real siguiera pasando esta prueba en silencio, pero
        aquí se exige la traducción completa sobre los datos reales (no una
        entrada suelta como arriba)."""
        inst = _cargar_instalador()
        sin_linea_en = [m['id'] for m in inst.MODULOS if not m.get('linea_en', '').strip()]
        self.assertEqual(sin_linea_en, [], f'módulos sin linea_en: {sin_linea_en}')
        sin_para_en = [(mid, e['pip_nombre']) for mid, entradas in inst.DEPENDENCIAS.items()
                        for e in entradas if not e.get('para_en', '').strip()]
        self.assertEqual(sin_para_en, [], f'dependencias sin para_en: {sin_para_en}')


class NingunTextoQuedaFueraDelDiccionario(unittest.TestCase):
    """T5.2, prueba de la especificación, literal: "ningún texto del instalador
    queda fuera del diccionario (una prueba que busca literales sospechosos en
    el código)". Escaneo estático por `ast`: cualquier cadena (o f-string con
    parte literal) que llegue de verdad al usuario — como argumento de
    `print`/`input`/`sys.stderr.write`/`messagebox.*`/`simpledialog.askstring`/
    `root.title`/`tk.Label(text=...)`/`tk.Button(text=...)`, o como argumento de
    `mensajes.append(...)` (la lista que `instalar()`/`desinstalar()` devuelven
    para que la CLI/ventana lo impriman) — debe pasar por `_texto(...)`. No es
    exhaustivo (una cadena compuesta con `+` fuera de esos casos se deja pasar:
    ver `_literal_sospechoso`), pero si esto encuentra algo, es una cadena
    suelta de verdad, no un falso positivo de la propia herramienta."""

    _SINKS = frozenset({'print', 'input', 'write', 'showinfo', 'showerror',
                         'showwarning', 'askyesno', 'askstring', 'title'})
    _WIDGETS_CON_TEXT_KW = frozenset({'Label', 'Button'})

    @staticmethod
    def _nombre_func(nodo_func):
        if isinstance(nodo_func, ast.Name):
            return nodo_func.id
        if isinstance(nodo_func, ast.Attribute):
            return nodo_func.attr
        return None

    @classmethod
    def _es_texto_call(cls, nodo):
        return isinstance(nodo, ast.Call) and cls._nombre_func(nodo.func) == '_texto'

    @classmethod
    def _contiene_texto_call(cls, nodo):
        return any(cls._es_texto_call(n) for n in ast.walk(nodo))

    @staticmethod
    def _tiene_letras(s):
        return bool(re.search(r'[^\W\d_]', s, re.UNICODE))

    @staticmethod
    def _solo_prefijo_herramienta(estatico):
        """`True` si, quitando todo lo que no sea letra ASCII, lo único que
        queda es "instalar" — el nombre del propio programa (`instalar.py`),
        invariante en los dos idiomas (como "git:" o "npm ERR!"): no es
        vocabulario de interfaz que haya que traducir."""
        limpio = re.sub(r'[^a-zA-Z]', '', estatico).lower()
        return limpio in ('', 'instalar')

    @classmethod
    def _texto_estatico(cls, nodo):
        """Las partes literales de `nodo` si es una cadena o un f-string; `None`
        si no es ninguna de las dos, o si ya contiene una llamada a `_texto`
        (en cuyo caso el texto real SÍ sale del diccionario, aunque el nodo
        entero no sea directamente esa llamada — p. ej. no debería darse en
        este código, pero un `f'{_texto(...)} fijo'` seguiría contando el
        texto fijo como sospechoso, que es lo correcto)."""
        if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
            return nodo.value
        if isinstance(nodo, ast.JoinedStr):
            partes_dinamicas_con_texto = any(
                isinstance(v, ast.FormattedValue) and cls._contiene_texto_call(v.value)
                for v in nodo.values)
            estatico = ''.join(v.value for v in nodo.values if isinstance(v, ast.Constant))
            return None if (partes_dinamicas_con_texto and not estatico.strip()) else estatico
        return None

    @classmethod
    def _literal_sospechoso(cls, nodo):
        if cls._contiene_texto_call(nodo):
            return False
        estatico = cls._texto_estatico(nodo)
        if estatico is None:
            return False
        if not cls._tiene_letras(estatico):
            return False  # solo espacios/puntuación/separadores (p. ej. " [", "] ")
        if cls._solo_prefijo_herramienta(estatico):
            return False  # "instalar: " — nombre del programa, no vocabulario de interfaz
        return True

    @classmethod
    def _hallazgos(cls, ruta):
        lineas_fuente = Path(ruta).read_text(encoding='utf-8').splitlines()
        arbol = ast.parse('\n'.join(lineas_fuente), filename=str(ruta))
        hallazgos = []
        for nodo in ast.walk(arbol):
            if not isinstance(nodo, ast.Call):
                continue
            nombre = cls._nombre_func(nodo.func)
            if nombre in cls._SINKS or nombre in cls._WIDGETS_CON_TEXT_KW:
                candidatos = list(nodo.args)
                candidatos += [kw.value for kw in nodo.keywords if kw.arg in ('text', 'message')]
                for arg in candidatos:
                    if cls._literal_sospechoso(arg):
                        # única excepción documentada: el error de bootstrap de
                        # `--idioma` inválido, ANTES de que haya idioma resuelto
                        # (marcado en el propio código, ver instalar.py).
                        ventana = lineas_fuente[max(0, nodo.lineno - 3):nodo.lineno]
                        if any('bilingue-a-proposito' in l for l in ventana):
                            continue
                        hallazgos.append(f'{ruta}:{nodo.lineno}: {nombre}(...) con literal fuera de TEXTOS')
            elif isinstance(nodo.func, ast.Attribute) and nodo.func.attr == 'append':
                objeto = nodo.func.value
                if isinstance(objeto, ast.Name) and objeto.id == 'mensajes':
                    for arg in nodo.args:
                        if cls._literal_sospechoso(arg):
                            hallazgos.append(f'{ruta}:{nodo.lineno}: mensajes.append(...) con literal fuera de TEXTOS')
        return hallazgos

    def test_sin_literales_sospechosos_en_instalar_py(self):
        hallazgos = self._hallazgos(ay.RAIZ / 'instalar.py')
        self.assertEqual(hallazgos, [], 'literales fuera de TEXTOS:\n' + '\n'.join(hallazgos))

    def test_el_propio_escaner_caza_una_cadena_suelta_de_verdad(self):
        """Falsador: sin esto, un escáner que nunca encuentra nada podría estar
        roto (p. ej. por no reconocer ninguna llamada) en vez de "todo limpio".
        Un `print('texto suelto en castellano')` de mentira, en un fichero
        temporal con la misma forma mínima, SÍ debe salir."""
        tmp = Path(tempfile.mkdtemp(prefix='abyss_escaner_falso_'))
        señuelo = tmp / 'señuelo.py'
        señuelo.write_text(
            "def _texto(idioma, clave, **fmt):\n"
            "    return clave\n"
            "print('esto es un texto suelto en castellano')\n",
            encoding='utf-8')
        hallazgos = self._hallazgos(señuelo)
        self.assertTrue(hallazgos, 'el escáner debe cazar una cadena suelta de verdad en un print()')


class TextosDeclaraLasMismasClavesEnLosDosIdiomas(unittest.TestCase):
    """Una clave presente en 'es' pero ausente en 'en' (o al revés) es una
    traducción a medias que `_texto()` disimularía cayendo a castellano en
    silencio — mejor cazarla aquí, en la propia estructura del diccionario."""

    def test_mismas_claves_es_en(self):
        inst = _cargar_instalador()
        claves_es = set(inst.TEXTOS['es'])
        claves_en = set(inst.TEXTOS['en'])
        self.assertEqual(claves_es, claves_en,
                          f'claves solo en es: {claves_es - claves_en} · claves solo en en: {claves_en - claves_es}')

    def test_ninguna_plantilla_vacia_salvo_la_declarada(self):
        """Toda clave debe tener texto no vacío en los dos idiomas — salvo
        `listar_detalle_nota` en castellano, que es intencionadamente '' (en
        castellano SÍ se imprime el detalle `toca`/`aviso`; no hace falta nota)."""
        inst = _cargar_instalador()
        vacias_permitidas = {('es', 'listar_detalle_nota')}
        for idioma, tabla in inst.TEXTOS.items():
            for clave, valor in tabla.items():
                if (idioma, clave) in vacias_permitidas:
                    continue
                self.assertTrue(str(valor).strip(), f'TEXTOS[{idioma!r}][{clave!r}] está vacío')


class TextoCaeACastellanoAntesQueReventar(unittest.TestCase):
    def test_idioma_desconocido_no_revienta(self):
        inst = _cargar_instalador()
        self.assertEqual(inst._texto('fr', 'estado_instalado'), inst.TEXTOS['es']['estado_instalado'])

    def test_clave_desconocida_no_revienta(self):
        inst = _cargar_instalador()
        # sin clave en ningún lado: se devuelve la propia clave, nunca una excepción
        self.assertEqual(inst._texto('en', 'clave_que_no_existe_de_verdad'), 'clave_que_no_existe_de_verdad')


class IdiomaPorDefectoEsElDelSistemaSiNoEsElInvalido(unittest.TestCase):
    """T5.2: "por defecto, el del sistema (locale.getdefaultlocale(); si no
    empieza por es, inglés)". Se prueba `_idioma_sistema()` en proceso (rápido)
    monkeypatcheando `locale.getdefaultlocale` — nunca cambia el locale de
    verdad del proceso de pruebas."""

    def test_locale_es_dice_es(self):
        from unittest import mock
        inst = _cargar_instalador()
        with mock.patch.object(inst.locale, 'getdefaultlocale', return_value=('es_ES', 'UTF-8')):
            self.assertEqual(inst._idioma_sistema(), 'es')

    def test_locale_en_dice_en(self):
        from unittest import mock
        inst = _cargar_instalador()
        with mock.patch.object(inst.locale, 'getdefaultlocale', return_value=('en_US', 'UTF-8')):
            self.assertEqual(inst._idioma_sistema(), 'en')

    def test_sin_locale_ni_entorno_dice_en(self):
        from unittest import mock
        inst = _cargar_instalador()
        env_sin_idioma = {k: v for k, v in os.environ.items()
                           if k not in ('LC_ALL', 'LANG', 'LC_MESSAGES')}
        with mock.patch.object(inst.locale, 'getdefaultlocale', return_value=(None, None)), \
             mock.patch.object(inst.os, 'environ', env_sin_idioma):
            self.assertEqual(inst._idioma_sistema(), 'en',
                              'sin ninguna pista de idioma, T5.2 pide caer a inglés, nunca a castellano por defecto')


class InstalarYDesinstalarDefectoEsCastellanoSiempre(unittest.TestCase):
    """`instalar()`/`desinstalar()` NUNCA deben leer el idioma del sistema por
    su cuenta (eso lo decide la CLI/ventana y se lo pasa ya resuelto) — su
    propio parámetro por defecto es 'es' literal. Falsador de una regresión
    donde alguien intentara "simplificar" metiendo `_idioma_sistema()` como
    valor por defecto de `idioma=` en `instalar()`: eso haría que llamarlas
    directamente (como hacen `test_instalador.py`/`test_esceptico_skill.py`,
    que nunca pasan `idioma=`) dependiera del locale de la máquina que corre
    las pruebas — justo lo que esta prueba impide."""

    def test_instalar_por_defecto_es_es_pase_lo_que_pase_en_el_sistema(self):
        from unittest import mock
        inst = _cargar_instalador()
        with mock.patch.object(inst, '_idioma_sistema', return_value='en'):
            import inspect
            firma = inspect.signature(inst.instalar)
            self.assertEqual(firma.parameters['idioma'].default, 'es')
            firma_des = inspect.signature(inst.desinstalar)
            self.assertEqual(firma_des.parameters['idioma'].default, 'es')


if __name__ == '__main__':
    unittest.main()
