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
    que no es una séptima ley).

    T4.2 (7-sep) añadió `docs/AUDITORIA_DE_ABYSS.md` (el primer informe de
    `auditar.py`, corrido sobre el propio paquete) a la lista blanca: sigue sin
    haber fichas de diseño personales, pero la lista de lo permitido en `docs/`
    tenía que crecer con ese fichero o quedaba una lista blanca desactualizada
    tumbando la suite entera.

    T5.2 (7-sep) añadió los espejos en inglés que la propia especificación pide
    («se añaden `docs/leyes.en.md` y ... `docs/AUDITORIA_DE_ABYSS.en.md`»,
    ESPECIFICACION_TANDA5.md §T5.2): misma razón, la lista blanca vuelve a
    crecer con esos dos ficheros o la suite entera queda en rojo por un
    requisito de la propia especificación."""

    def test_no_promete_fichas_originales_ni_siete_leyes(self):
        texto = (RAIZ / 'ESPECIFICACION.md').read_text(encoding='utf-8')
        self.assertNotIn('fichas originales tal cual', texto)
        self.assertNotIn('siete leyes', texto)
        self.assertIn('SEIS leyes', texto)

    def test_docs_no_lleva_fichas_de_diseno_originales(self):
        docs = RAIZ / 'docs'
        nombres = sorted(p.name for p in docs.iterdir() if p.is_file())
        permitidos = ['AUDITORIA_DE_ABYSS.en.md', 'AUDITORIA_DE_ABYSS.md',
                      'ganchos_settings_ejemplo.json', 'leyes.en.md', 'leyes.md']
        self.assertEqual(nombres, permitidos,
                          'docs/ no debe llevar más que la lista blanca declarada: el leyes.md '
                          'destilado (y su espejo en inglés), el ejemplo de ganchos, y el informe '
                          'de auditoría de T4.2 (y su espejo en inglés de T5.2)')

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


class ReadmeNoVendeLosVerbosDeLaManoComoHechos(unittest.TestCase):
    """Fallo "engaña" medido 7-sep (T4.5): README.md describía los cinco verbos de
    `gestos.py` como si ya movieran algo en pantalla («número de dedos aísla capas
    del despiece, pellizco desliza la explosión, pose de la palma orbita la
    cámara, mano abierta y quieta un segundo captura PNG, dos manos escalan») —
    MEDIDO falso: `gestos.py` solo publica campos en un JSON por HTTP (cero
    `imwrite`/`.save(` en el fichero) y `render3d.py` no sondea ese `/estado` en
    ninguna parte (cero `fetch`/`8799`/`/estado` referidos a él). El propio
    `gestos.py` lo declara en su docstring («esa reactividad ... NO está hecha
    aquí»); ese límite no llegaba al README, que es lo que lee quien instala."""

    def test_no_repite_la_lista_de_verbos_como_hechos(self):
        texto = (RAIZ / 'README.md').read_text(encoding='utf-8')
        frase_vieja = (
            'número de dedos aísla capas del despiece, pellizco desliza la '
            'explosión (normalizado por percentiles de la propia sesión), pose '
            'de la palma orbita la cámara, mano abierta y quieta un segundo '
            'captura PNG, dos manos escalan'
        )
        self.assertNotIn(frase_vieja, texto,
                          'README.md no debe describir los verbos de gestos.py como efectos ya hechos')

    def test_tabla_dice_que_sirve_estado_y_nada_lo_consume(self):
        texto = _colapsar((RAIZ / 'README.md').read_text(encoding='utf-8'))
        self.assertIn('sirve por HTTP local, SOLO en `127.0.0.1`, el estado de la mano', texto)
        self.assertIn('Nada consume ese estado todavía', texto)
        self.assertIn('la página de `render3d.py` no lee `/estado` ni reacciona', texto)
        self.assertIn('ningún PNG se captura', texto)

    def test_limites_honestos_declara_que_nada_lo_consume(self):
        texto = _colapsar((RAIZ / 'README.md').read_text(encoding='utf-8'))
        self.assertIn('la página que genera `render3d.py` no lee `/estado` ni reacciona a él', texto)
        self.assertIn('ningún gesto llega a capturar un PNG', texto)

    def test_sentidos_ya_no_dice_que_la_mano_maneja_la_escena_sin_matiz(self):
        texto = _colapsar((RAIZ / 'README.md').read_text(encoding='utf-8'))
        self.assertNotIn('la mano maneja la escena vía MediaPipe con vocabulario propio, sirve HTTP',
                          texto)
        self.assertIn('pero nada lo consume', texto)


def _seccion(texto, encabezado):
    """Cuerpo de una sección `## <encabezado>` hasta la siguiente `## ` (o el final
    del fichero) — para no confundir una frase de otra sección con la que toca."""
    m = re.search(r'^## ' + re.escape(encabezado) + r'\s*$', texto, re.MULTILINE)
    if not m:
        return ''
    resto = texto[m.end():]
    fin = re.search(r'^## ', resto, re.MULTILINE)
    return resto[:fin.start()] if fin else resto


class ReadmesDicenLoQuePresentaPublicaEnElVideo(unittest.TestCase):
    """Fallo "grave" medido 7-sep: el capítulo de privacidad enumeraba 12 piezas
    y NO mencionaba `presenta.py` — la única cuyo PRODUCTO está pensado para
    publicarse. `presenta.py` toca la red por su cuenta (bloque «mundo»:
    `mundo.buscar()`/`descargar()`; bloque «sentidos»: `exterocepcion.py`) Y,
    MEDIDO abriendo el propio vídeo de demostración del paquete (fotograma
    ~17 s, «Sentidos»), deja grabados en el `.mp4` el municipio de quien lo
    generó (por IP, marca «(ES; por IP)»), su meteorología local y la
    telemetría de su máquina — sin ni un aviso en el README (grep de
    "lugar/ubicaci/personal/compartir/publicar/privacidad" sobre
    `presenta.py` solo devuelve el comentario que anonimiza la ruta del disco
    del bloque «auditoría», dos bloques antes).

    El arreglo de código (que el bloque «sentidos» deje de mostrar lugar/meteo
    por defecto, o los pida tras una bandera explícita) es de `presenta.py`,
    fuera del alcance de esta prueba (que solo vigila README.md/README.en.md);
    esta clase falsa que, MIENTRAS ese arreglo no exista, los dos README dicen
    la verdad completa: qué toca la red y qué queda grabado en el vídeo."""

    SECCION_ES = ('Privacidad y qué sale de la máquina', 'Límites honestos')
    SECCION_EN = ('Privacy and what leaves the machine', 'Honest limits')

    def test_presenta_py_aparece_en_privacidad_de_los_dos_readme(self):
        for nombre, (privacidad, _limites) in (('README.md', self.SECCION_ES),
                                                ('README.en.md', self.SECCION_EN)):
            texto = (RAIZ / nombre).read_text(encoding='utf-8')
            cuerpo = _seccion(texto, privacidad)
            self.assertIn('presenta.py', cuerpo,
                          f'{nombre}: el capítulo de privacidad no menciona presenta.py')

    def test_privacidad_dice_que_bloques_mundo_y_sentidos_tocan_la_red(self):
        casos = (
            ('README.md', self.SECCION_ES[0],
             ('exterocepcion.py', 'mundo.buscar', 'ABYSS_SIN_RED')),
            ('README.en.md', self.SECCION_EN[0],
             ('exterocepcion.py', 'mundo.buscar', 'ABYSS_SIN_RED')),
        )
        for nombre, encabezado, marcadores in casos:
            texto = (RAIZ / nombre).read_text(encoding='utf-8')
            cuerpo = _seccion(texto, encabezado)
            bloque_presenta = cuerpo[cuerpo.find('`presenta.py`'):]
            self.assertTrue(bloque_presenta, f'{nombre}: no se encontró la entrada de presenta.py')
            for marcador in marcadores:
                self.assertIn(marcador, bloque_presenta,
                              f'{nombre}: la entrada de presenta.py no menciona {marcador!r}')

    def test_privacidad_dice_lo_que_el_video_deja_grabado(self):
        casos = (
            ('README.md', self.SECCION_ES[0], ('municipio', 'meteorolog', 'telemetría', '(ES; por IP)')),
            ('README.en.md', self.SECCION_EN[0], ('municipality', 'weather', 'telemetry', '(ES; by IP)')),
        )
        for nombre, encabezado, marcadores in casos:
            texto = (RAIZ / nombre).read_text(encoding='utf-8')
            cuerpo = _seccion(texto, encabezado)
            bloque_presenta = cuerpo[cuerpo.find('`presenta.py`'):]
            for marcador in marcadores:
                self.assertIn(marcador, bloque_presenta,
                              f'{nombre}: no dice que el vídeo deja grabado {marcador!r}')

    def test_limites_honestos_avisa_de_la_fuga_en_los_dos_readme(self):
        casos = (('README.md', self.SECCION_ES[1]), ('README.en.md', self.SECCION_EN[1]))
        for nombre, encabezado in casos:
            texto = (RAIZ / nombre).read_text(encoding='utf-8')
            cuerpo = _seccion(texto, encabezado)
            self.assertIn('presenta.py', cuerpo,
                          f'{nombre}: "Límites honestos"/"Honest limits" no avisa de presenta.py')
            bloque_presenta = cuerpo[cuerpo.find('`presenta.py`'):]
            self.assertIn('ABYSS_SIN_RED', bloque_presenta,
                          f'{nombre}: el límite de presenta.py no menciona ABYSS_SIN_RED')

    def test_ningun_nombre_de_municipio_real_se_cuela_en_el_ejemplo(self):
        # regla dura 4 del encargo (test_sin_datos_personales.py): nada personal en
        # el repo — el municipio MEDIDO en el vídeo de demostración (un dato real de
        # quien lo generó) no debe copiarse aquí, ni como ejemplo "ilustrativo".
        for nombre in ('README.md', 'README.en.md'):
            texto = (RAIZ / nombre).read_text(encoding='utf-8')
            self.assertNotIn('Arenys', texto, f'{nombre}: no debe nombrar el municipio real medido')


if __name__ == '__main__':
    unittest.main()
