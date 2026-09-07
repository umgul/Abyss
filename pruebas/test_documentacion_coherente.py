"""Tres fallos "engaña" del 6-sep sobre README.md/README.en.md:

(1) Prometían un gancho `PostModelSwitch`/`modelo.py --postswitch` que no existe en
    Claude Code (los eventos reales son PreToolUse, PostToolUse, Stop, SubagentStop,
    SessionStart, SessionEnd, UserPromptSubmit, PreCompact, Notification).
(2) La sección de privacidad decía "continuidad.py ... no hace ninguna llamada de
    red", falso: en `--arranque`/`--despertar` invoca a `exterocepcion.py`/
    `noticias.py`, que SÍ contactan con ipinfo.io/open-meteo.com/nominatim/
    news.google.com — justo la sección donde el lector decide si el gancho que
    corre en cada mensaje manda o no su IP fuera.
(3) `instalar.py` ya no declara el módulo `modelo` con gancho propio (MODULOS['modelo']
    ['hooks'] == []): README y código deben decir lo mismo.
"""
import re
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


class ReadmesNoPrometenPostModelSwitch(unittest.TestCase):
    def test_sin_bandera_postswitch_en_ningun_readme(self):
        # `--postswitch` ya no existe en modelo.py (se quitó con el gancho): si un
        # texto la sigue mencionando, está describiendo un comando que ya no corre.
        for nombre in ('README.md', 'README.en.md', 'skills/modelo/SKILL.md'):
            texto = (RAIZ / nombre).read_text(encoding='utf-8')
            self.assertNotIn('--postswitch', texto, f'{nombre} sigue mencionando la bandera del gancho retirado')

    def test_ningun_texto_reclama_un_gancho_postmodelswitch_activo(self):
        # "PostModelSwitch" SÍ puede aparecer para EXPLICAR que no existe (el
        # README y el SKILL.md lo hacen a propósito); lo que no puede aparecer es
        # la forma que reclama un gancho activo en ese evento.
        for nombre in ('README.md', 'README.en.md', 'skills/modelo/SKILL.md'):
            texto = (RAIZ / nombre).read_text(encoding='utf-8')
            self.assertNotIn('modelo.py --postswitch` en', texto)
            self.assertNotIn('modelo.py --postswitch` on', texto)
            self.assertNotIn('gancho `PostModelSwitch` ya corre', texto)
            self.assertNotIn('en `PostModelSwitch`', texto)

    def test_privacidad_ya_no_dice_que_todo_lo_demas_incluye_continuidad(self):
        # la frase vieja agrupaba a continuidad.py con los guiones que de verdad no
        # hacen red ("Todo lo demás (`continuidad.py`, `vigia.py`, ...)") — falsa,
        # porque --arranque/--despertar SÍ invocan a exterocepcion/noticias.
        for nombre in ('README.md', 'README.en.md'):
            texto = (RAIZ / nombre).read_text(encoding='utf-8')
            self.assertNotIn('(`continuidad.py`, `vigia.py`', texto,
                              f'{nombre} sigue agrupando a continuidad.py entre los que "no hacen red"')

    def test_privacidad_dice_que_continuidad_si_hace_red_indirecta(self):
        casos = (('README.md', 'no hace red POR SÍ MISMO'), ('README.en.md', 'makes no network calls BY ITSELF'))
        for nombre, marcador in casos:
            texto = (RAIZ / nombre).read_text(encoding='utf-8')
            self.assertIn(marcador, texto, f'{nombre} debe aclarar que continuidad.py sí hace red indirecta')
            self.assertIn('ipinfo.io', texto, f'{nombre} debe decir que continuidad SÍ contacta ipinfo.io indirectamente')


class InstalarYReadmeCoinciden(unittest.TestCase):
    def test_modulo_modelo_sin_hooks_en_instalar(self):
        import sys
        import importlib.util
        spec = importlib.util.spec_from_file_location('abyss_instalador_doc_check', str(RAIZ / 'instalar.py'))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertEqual(mod.MODULOS_POR_ID['modelo']['hooks'], [],
                          'el módulo modelo ya no debe declarar ningún gancho (PostModelSwitch no existe)')


class EspecificacionImagenCoincideConElCodigo(unittest.TestCase):
    """ESPECIFICACION.md §3 (fallo 6-sep, "roza"): decía "Ambos [crear y pintar]
    apuntan en mem/imagen.log" (MEDIDO: solo `crear` escribe ahí) y "solo pinceles
    ≥ 3 px" (MEDIDO: `pintor.py --html-r-min` vale 2 por defecto)."""

    def test_no_dice_ambos_apuntan_en_imagen_log(self):
        texto = (RAIZ / 'ESPECIFICACION.md').read_text(encoding='utf-8')
        self.assertNotIn('Ambos apuntan en', texto)
        self.assertIn('Solo `crear` apunta en', texto)

    def test_umbral_html_es_2_no_3(self):
        texto = (RAIZ / 'ESPECIFICACION.md').read_text(encoding='utf-8')
        self.assertNotIn('≥ 3 px', texto)
        self.assertIn('≥ 2 px', texto)
        # y que de verdad coincide con el valor por defecto real del código
        pintor = (RAIZ / 'abyss' / 'pintor.py').read_text(encoding='utf-8')
        self.assertIn('--html-r-min', pintor)


class ReadmeAvisaDelPythonPelado(unittest.TestCase):
    """Fallo 6-sep, "engaña": los 5 ganchos de hooks/hooks.json invocan `python` a
    secas (sin detección de intérprete, a diferencia de instalar.py) — en macOS
    moderno no existe `python` (solo python3), y en Windows sin Python de
    python.org puede ser el alias de la Microsoft Store. El README prometía que
    "los ganchos del plugin funcionan solos, en cualquier proyecto, nada más
    instalarlo" sin ese matiz."""

    def test_hooks_json_sigue_usando_python_pelado(self):
        # si esto deja de ser cierto (se pasa a un lanzador que detecta el
        # intérprete), el aviso del README quedaría obsoleto y habría que quitarlo.
        # Segunda tanda (7-sep): +3 huella (SessionStart/PostToolUse/Stop) + 2 cuerpo
        # (SessionStart/UserPromptSubmit) sobre los 4 de antes (continuidad x3, vigia).
        texto = (RAIZ / 'hooks' / 'hooks.json').read_text(encoding='utf-8')
        comandos = re.findall(r'"command":\s*"([^"]+)"', texto)
        self.assertEqual(len(comandos), 9)
        self.assertTrue(all(c.startswith('python ') for c in comandos), comandos)

    def test_los_dos_readme_avisan_del_limite(self):
        for nombre in ('README.md', 'README.en.md'):
            texto = (RAIZ / nombre).read_text(encoding='utf-8')
            self.assertIn('python.org', texto, f'{nombre} debe avisar del límite de `python` pelado en los ganchos del plugin')


def _colapsar(texto):
    return re.sub(r'\s+', ' ', texto)


class ReadmesCuentanLosGanchosBien(unittest.TestCase):
    """Fallo 6-sep, "roza": README.md/README.en.md decían "cinco ganchos"/"five
    hooks" en el párrafo del límite de `python` pelado, resto de la retirada del
    gancho PostModelSwitch — cuando `hooks/hooks.json` ya solo declara cuatro. El
    número se deriva del propio `hooks.json` (no se repite a mano en el test) para
    que un cambio futuro en el número de ganchos no vuelva a desincronizar los
    README sin que la suite lo note."""

    NUMEROS_ES = {1: 'un', 2: 'dos', 3: 'tres', 4: 'cuatro', 5: 'cinco', 6: 'seis',
                  7: 'siete', 8: 'ocho', 9: 'nueve', 10: 'diez'}
    NUMEROS_EN = {1: 'one', 2: 'two', 3: 'three', 4: 'four', 5: 'five', 6: 'six',
                  7: 'seven', 8: 'eight', 9: 'nine', 10: 'ten'}

    def test_el_numero_escrito_coincide_con_hooks_json(self):
        texto_hooks = (RAIZ / 'hooks' / 'hooks.json').read_text(encoding='utf-8')
        n = len(re.findall(r'"command":\s*"([^"]+)"', texto_hooks))
        self.assertGreater(n, 0, 'hooks/hooks.json debería declarar al menos un gancho')

        es = _colapsar((RAIZ / 'README.md').read_text(encoding='utf-8'))
        en = _colapsar((RAIZ / 'README.en.md').read_text(encoding='utf-8'))
        self.assertIn(f'{self.NUMEROS_ES[n]} ganchos de [`hooks/hooks.json`]', es,
                      f'README.md debe decir "{self.NUMEROS_ES[n]} ganchos", como hooks.json declara ({n})')
        self.assertIn(f'{self.NUMEROS_EN[n]} hooks in [`hooks/hooks.json`]', en,
                      f'README.en.md debe decir "{self.NUMEROS_EN[n]} hooks", como hooks.json declara ({n})')


class DesinstaladorNoPrometeByteAByte(unittest.TestCase):
    """Fallo 6-sep, "engaña": ESPECIFICACION.md §6 prometía que el desinstalador
    devuelve `settings.json` "byte a byte" salvo lo nuestro — falso, MEDIDO en
    `test_instalador.py` (ciclo completo con un JSON de formato ajeno: "iguales
    byte a byte: False" / "mismo JSON cargado: True"): `_escribir_json` siempre
    reescribe con su propio `indent=2`. Los tres textos deben decir lo mismo:
    mismo CONTENIDO, no mismo texto; el formato original queda en la copia `.bak`."""

    def test_especificacion_no_promete_byte_a_byte_sin_matizar(self):
        texto = (RAIZ / 'ESPECIFICACION.md').read_text(encoding='utf-8')
        self.assertNotIn('devuelve byte a byte salvo lo nuestro', texto)
        self.assertIn('mismo CONTENIDO, no el mismo texto', texto)

    def test_los_dos_readme_avisan_del_limite_del_formato(self):
        casos = (('README.md', 'mismo *contenido*'), ('README.en.md', 'same *content*'))
        for nombre, marcador in casos:
            texto = (RAIZ / nombre).read_text(encoding='utf-8')
            self.assertIn(marcador, texto, f'{nombre} debe avisar de que el desinstalador no restaura byte a byte')
            self.assertIn('.bak', texto)


class EspecificacionImagenFirmaYCascadaReales(unittest.TestCase):
    """Fallo 6-sep, "engaña": ESPECIFICACION.md §3 seguía documentando la firma
    vieja de `crear` (posicionales `[ancho] [alto] [semilla]`, que `imagen.py`
    ignora en silencio desde que se pasó a banderas) y la cascada vieja de dos
    vías (Pollinations sin clave → HuggingFace) cuando el código tiene seis vías
    con `local` primero. MEDIDO contra un servidor A1111 falso en
    `test_imagen_crear_vias.py` y `test_imagen_posicional_desconocido.py`."""

    def test_no_describe_los_positionales_viejos(self):
        texto = (RAIZ / 'ESPECIFICACION.md').read_text(encoding='utf-8')
        self.assertNotIn('[ancho] [alto] [semilla]', texto)
        self.assertNotIn('Pollinations sin clave', texto)

    def test_describe_las_banderas_y_las_seis_vias(self):
        texto = _colapsar((RAIZ / 'ESPECIFICACION.md').read_text(encoding='utf-8'))
        for bandera in ('--ancho N', '--alto N', '--semilla N', '--via'):
            self.assertIn(bandera, texto)
        for via in ('local', 'pollinations', 'cloudflare', 'together', 'huggingface', 'horde'):
            self.assertIn(via, texto)


class EspecificacionDocsYLeyesCoinciden(unittest.TestCase):
    """Fallo 6-sep, "roza": ESPECIFICACION.md §5 prometía que `docs/` lleva "las
    fichas originales tal cual" (MEDIDO: `docs/` solo contiene `leyes.md` y
    `ganchos_settings_ejemplo.json` — las fichas personales del autor no se
    publican, a propósito) y "las siete leyes del SGICP propio" (MEDIDO:
    `docs/leyes.md` tiene SEIS leyes numeradas, más una sección de resumen final
    que no es una séptima ley)."""

    def test_no_promete_fichas_originales_ni_siete_leyes(self):
        texto = (RAIZ / 'ESPECIFICACION.md').read_text(encoding='utf-8')
        self.assertNotIn('fichas originales tal cual', texto)
        self.assertNotIn('siete leyes', texto)
        self.assertIn('SEIS leyes', texto)

    def test_docs_no_lleva_fichas_de_diseno_originales(self):
        docs = RAIZ / 'docs'
        nombres = sorted(p.name for p in docs.iterdir() if p.is_file())
        self.assertEqual(nombres, ['ganchos_settings_ejemplo.json', 'leyes.md'],
                          'docs/ no debe llevar más que el leyes.md destilado y el ejemplo de ganchos')

    def test_leyes_md_tiene_exactamente_seis_leyes_numeradas(self):
        texto = (RAIZ / 'docs' / 'leyes.md').read_text(encoding='utf-8')
        numeros = re.findall(r'^## (\d+) ·', texto, re.MULTILINE)
        self.assertEqual(numeros, [str(n) for n in range(1, 7)],
                          'docs/leyes.md debe tener exactamente seis leyes numeradas 1..6')


class NingunGanchoDeclaraStatusMessage(unittest.TestCase):
    """Fallo 6-sep, "roza": `statusMessage` en los ganchos de `hooks/hooks.json`
    (y en el ejemplo de `docs/ganchos_settings_ejemplo.json`, y en lo que escribe
    `instalar.py`) no se pudo verificar contra la documentación oficial de ganchos
    (skill `hook-development`: el esquema de un gancho `command` es {type, command,
    timeout}) ni contra ningún `settings.json` real de esta máquina. Se quitó de
    los tres sitios en vez de publicar una promesa sin comprobar."""

    def test_hooks_json_y_el_ejemplo_no_llevan_statusmessage(self):
        for nombre in ('hooks/hooks.json', 'docs/ganchos_settings_ejemplo.json'):
            texto = (RAIZ / nombre).read_text(encoding='utf-8')
            self.assertNotIn('statusMessage', texto, f'{nombre} no debe declarar statusMessage')

    def test_instalar_py_no_escribe_statusmessage(self):
        texto = (RAIZ / 'instalar.py').read_text(encoding='utf-8')
        self.assertNotIn("'statusMessage'", texto)
        self.assertNotIn('"statusMessage"', texto)


class SkillParentesisNoMienteSobreElVigia(unittest.TestCase):
    """Fallo "engaña" medido 7-sep (ronda 2): `skills/parentesis/SKILL.md` decía
    «El vigía (`vigia.py`) no usa el tramo como evidencia todavía» — falso:
    `vigia.leer_turno()` SÍ llama a `parentesis.en_parentesis()` desde la primera
    tanda (ver `pruebas/test_parentesis.py::IntegracionConVigia`), y el SKILL
    tampoco mencionaba los dos agujeros que SÍ existían entonces (`modelo.py`,
    `varas.py`) — ambos cerrados en esta misma ronda (ver `test_modelo.py` y
    `test_varas_index.py`)."""

    def test_no_repite_la_afirmacion_falsa(self):
        texto = (RAIZ / 'skills' / 'parentesis' / 'SKILL.md').read_text(encoding='utf-8')
        self.assertNotIn('no usa el tramo como evidencia todavía', texto)

    def test_dice_que_el_vigia_si_lo_respeta(self):
        texto = (RAIZ / 'skills' / 'parentesis' / 'SKILL.md').read_text(encoding='utf-8')
        self.assertIn('vigia.leer_turno()', texto)
        self.assertIn('modelo.recorrer()', texto)


class ReadmesDicenElCasoCrlfDelLimiteHonesto(unittest.TestCase):
    """Fallo "roza" medido 7-sep (ronda 2): el «límite honesto» del instalador
    listaba como ejemplos «indent=4» y «orden de claves distinto», pero
    `_escribir_json` fija `newline='\\n'` a propósito — MEDIDO: un
    `settings.json` de partida en CRLF vuelve en LF tras un ciclo instalar→
    desinstalar (mismo JSON, fichero entero marcado como modificado), y ese
    caso —el fin de línea habitual en Windows— no aparecía en la lista."""

    def test_menciona_crlf_en_el_limite_honesto(self):
        for nombre in ('README.md', 'README.en.md'):
            texto = (RAIZ / nombre).read_text(encoding='utf-8')
            self.assertIn('CRLF', texto, f'{nombre} debe nombrar el caso CRLF en su límite honesto')


if __name__ == '__main__':
    unittest.main()
