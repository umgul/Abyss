"""README.md, README.en.md, ESPECIFICACION.md y el manifiesto del plugin dicen lo
mismo que el código: sin ganchos inexistentes, sin promesas de privacidad falsas,
sin firmas de comandos viejas."""
import json
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
    """ESPECIFICACION.md §3: solo `crear` apunta en `mem/imagen.log` y el umbral de
    pincel del HTML es el valor por defecto real de `pintor.py --html-r-min`."""

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


class ElPluginNoTraeGanchos(unittest.TestCase):
    """La vía `/plugin install` instala solo skills: Claude Code cargaría solo un
    `hooks/hooks.json`, así que no debe existir, y los README lo dicen."""

    def test_no_hay_hooks_json_ni_clave_hooks(self):
        self.assertFalse((RAIZ / 'hooks').exists(), 'hooks/ se cargaría solo al instalar el plugin')
        manifiesto = json.loads((RAIZ / '.claude-plugin' / 'plugin.json').read_text(encoding='utf-8'))
        self.assertNotIn('hooks', manifiesto)
        self.assertNotIn('hooks', manifiesto.get('keywords', []))

    def test_los_dos_readme_dicen_que_el_plugin_solo_trae_skills(self):
        es = _colapsar((RAIZ / 'README.md').read_text(encoding='utf-8'))
        en = _colapsar((RAIZ / 'README.en.md').read_text(encoding='utf-8'))
        self.assertIn('El plugin no declara ningún gancho', es)
        self.assertIn('The plugin declares no hooks', en)


def _colapsar(texto):
    return re.sub(r'\s+', ' ', texto)


class DesinstaladorNoPrometeByteAByte(unittest.TestCase):
    """El desinstalador devuelve el mismo CONTENIDO de `settings.json`, no el mismo
    texto (`_escribir_json` reescribe con `indent=2`); los tres textos lo dicen así."""

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
    """ESPECIFICACION.md §3 describe la firma real de `crear` (banderas, no
    posicionales) y las seis vías con `local` primero."""

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
    """`docs/` lleva exactamente su lista blanca (sin fichas de diseño personales) y
    `leyes.md` tiene seis leyes, como dice ESPECIFICACION.md §5."""

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
                          'de auditoría (y su espejo en inglés)')

    def test_leyes_md_tiene_exactamente_seis_leyes_numeradas(self):
        texto = (RAIZ / 'docs' / 'leyes.md').read_text(encoding='utf-8')
        numeros = re.findall(r'^## (\d+) ·', texto, re.MULTILINE)
        self.assertEqual(numeros, [str(n) for n in range(1, 7)],
                          'docs/leyes.md debe tener exactamente seis leyes numeradas 1..6')


class NingunGanchoDeclaraStatusMessage(unittest.TestCase):
    """El esquema documentado de un gancho `command` es {type, command, timeout}:
    ni el ejemplo ni `instalar.py` escriben un `statusMessage` sin respaldo."""

    def test_el_ejemplo_no_lleva_statusmessage(self):
        texto = (RAIZ / 'docs' / 'ganchos_settings_ejemplo.json').read_text(encoding='utf-8')
        self.assertNotIn('statusMessage', texto)

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
    """Fallo "engaña" medido 7-sep: README.md describía los cinco verbos de
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
