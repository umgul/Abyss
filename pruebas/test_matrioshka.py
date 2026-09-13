"""La matrioshka de la medida (`propiocepcion.extraer()`): una sola lectura por fichero da la
medida, las frases del usuario y las lecturas de fichas, recordadas en `memory/.matrioshka/`
con la firma del fichero. Se comprueba contra `oraculo_medida.py` —la misma semántica escrita
a la manera directa— que da exactamente lo mismo en frío y en caliente; que la muñeca se usa
y se invalida cuando toca; que nunca decide un resultado; y que de una sesión omitida no
queda texto bajo `memory/`."""
import sys
import os
import json
import gzip
import time
import shutil
import tempfile
import unicodedata
import importlib.util
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import unittest
import ayudas as ay

PRUEBAS = Path(__file__).resolve().parent
T = '2026-01-01T{}Z'
NFC_MEDIA = unicodedata.normalize('NFC', 'ficha-medía.md')
NFD_MEDIA = unicodedata.normalize('NFD', 'ficha-medía.md')
LARGA = 'ficha-de-nombre-largo-' + 'x' * 220 + '.md'   # cerca del tope de un nombre de fichero
FICHAS = ['ficha-a.md', 'ficha-b.md', 'ficha-c.md', 'ficha-d.md', 'ficha-e.md', 'ficha-secreta.md',
          'ficha-escrita.md', 'ficha-z.md', NFC_MEDIA, NFD_MEDIA, 'b.md', 'lejos-1.md', 'lejos-2.md',
          LARGA, 'nunca-leida.md']


def _compacta(d):
    return json.dumps(d, separators=(',', ':'), ensure_ascii=False)


def _read(ficha, ts, **extra):
    d = {'type': 'assistant', 'timestamp': ts,
         'message': {'content': [{'type': 'tool_use', 'name': 'Read', 'input': {'file_path': f'/proyecto/memory/{ficha}'}}]}}
    d.update(extra)
    return _compacta(d)


def _corpus(proj):
    """Tres sesiones con lo que separa una medida de otra; cada línea dice por qué está."""
    mem = proj / 'memory'
    ses = mem / 'sesiones'
    ses.mkdir(parents=True, exist_ok=True)
    a = [
        _compacta({'type': 'user', 'timestamp': T.format('09:00:00'),   # compactación de primera: su hora cuenta, su turno no
                   'message': {'content': 'This session is being continued from a previous conversation'}}),
        _compacta(ay.usuario('hola, empezamos con la medida', T.format('09:01:00'))),
        _compacta({'type': 'assistant', 'requestId': 'r1', 'timestamp': T.format('09:02:00'),
                   'message': {'usage': {'output_tokens': 10, 'output_tokens_details': {'thinking_tokens': 4},
                                         'cache_read_input_tokens': 100},
                               'content': [{'type': 'tool_use', 'name': 'Read',
                                            'input': {'file_path': '/proyecto/memory/ficha-a.md'}}]}}),
        _compacta(ay.usuario_tool_result('cat memory/ficha-b.md', T.format('09:03:00'))),
        _read('ficha-c.md', T.format('09:04:00'), isSidechain=True),     # sidechain: fuera de la medida, dentro de las lecturas
        'cat memory/ficha-d.md en una línea que no es JSON',
        _compacta(ay.usuario('no, eso no es así', T.format('09:05:00'))),
        _read(LARGA, T.format('09:06:00')),
        _compacta(ay.usuario('secretounico dentro del tramo', T.format('09:10:00'))),
        _read('ficha-secreta.md', T.format('09:11:00')),
        _compacta(ay.asistente_tool_use('Write', {'file_path': '/proyecto/memory/ficha-escrita.md', 'content': 'x'},
                                        T.format('09:20:00'))),
        _compacta(ay.asistente_tool_use('Bash', {'command': 'cat >> ~/proyecto/memory/ficha-z.md <<FIN'},
                                        T.format('09:21:00'))),
        _compacta(ay.usuario_tool_result('cat memory/' + NFD_MEDIA, T.format('09:22:00'))),
        _compacta(ay.usuario_tool_result('cat memory/lejos-1.md' + ' x' * 400 + ' memory/lejos-2.md', T.format('09:24:00'))),
        _compacta(ay.asistente_tool_use('Agent', {'model': 'sonnet', 'prompt': 'p'}, T.format('09:25:00'))),
        _compacta(ay.asistente_tool_use('WebSearch', {'query': 'q'}, T.format('09:26:00'))),
        _compacta(ay.usuario('  varias    palabras   separadas  ', T.format('09:27:00'))),
        _compacta({'type': 'user', 'isMeta': True, 'message': {'content': 'meta'}, 'timestamp': T.format('09:28:00')}),
        _compacta(ay.usuario('<command-name>/model</command-name>', T.format('09:30:00'))),   # comando de última: su hora cuenta
    ]
    (proj / 'ses-a.jsonl').write_text('\n'.join(a) + '\n', encoding='utf-8')
    b = [ay.usuario('primera frase de la sesión archivada', T.format('10:00:00')),
         ay.asistente_texto('respuesta', T.format('10:01:00')),
         ay.usuario('segunda frase antes del tramo', T.format('10:01:30')),
         ay.usuario('palabraoculta tras abrir el tramo', T.format('10:03:00')),
         ay.usuario('otra más tras abrir el tramo', T.format('10:04:00'))]
    with gzip.open(ses / 'ses-b.jsonl.gz', 'wt', encoding='utf-8') as fh:
        for d in b:
            fh.write(json.dumps(d, ensure_ascii=False) + '\n')
    c = [_compacta(ay.usuario('sesión con una línea rara', T.format('11:00:00'))),
         _compacta(ay.usuario_tool_result('cat memory/a-b.md', T.format('11:01:00'))),   # `b.md` está dentro de `a-b.md`
         json.dumps('cat memory/ficha-e.md dentro de una cadena JSON')]                   # JSON válido que no es un objeto
    (proj / 'ses-c.jsonl').write_text('\n'.join(c) + '\n', encoding='utf-8')
    (mem / 'parentesis.json').write_text(json.dumps({
        'ses-a': [{'inicio': '2026-01-01T09:09:00+00:00', 'fin': '2026-01-01T09:12:00+00:00', 'motivo': 'prueba'}],
        'ses-b': [{'inicio': '2026-01-01T10:02:00+00:00', 'fin': None, 'motivo': 'prueba'}],
    }), encoding='utf-8')
    (proj / '_fichas.json').write_text(json.dumps(FICHAS, ensure_ascii=True), encoding='utf-8')


COMPARAR = r'''
import sys, os, json, glob
sys.path.insert(0, sys.argv[1]); sys.path.insert(0, sys.argv[2])
import propiocepcion as P
import oraculo_medida as O
modo = sys.argv[3]
with open(sys.argv[4], encoding='utf-8') as fh:
    fichas = json.load(fh)
with open(os.path.join(P.mem, 'parentesis.json'), encoding='utf-8') as fh:
    tramos = {sid: [(t.get('inicio'), t.get('fin')) for t in lst] for sid, lst in json.load(fh).items()}
out = {}
if modo == 'extraer':
    for ruta in (os.path.join(P.proj, 'ses-a.jsonl'), os.path.join(P.SES, 'ses-b.jsonl.gz')):
        e = P.extraer(ruta)
        out[os.path.basename(ruta)] = {'medida': e['medida'] == O.medir(ruta, tramos)[1],
                                       'frases': e['frases'] == O.frases_usuario(ruta, tramos)}
if modo == 'rara':
    ruta = os.path.join(P.proj, 'ses-c.jsonl')
    limpia = os.path.join(P.mem, 'ses-c-limpia.jsonl')
    with open(ruta, encoding='utf-8') as fh:
        lineas = fh.readlines()
    with open(limpia, 'w', encoding='utf-8') as fh:
        fh.writelines(l for l in lineas if not l.startswith('"'))
    e = P.extraer(ruta)
    out['medida'] = e['medida'] == O.medir(limpia, tramos)[1]
    out['frases'] = e['frases'] == O.frases_usuario(limpia, tramos)
esperado = {f: sorted(s) for f, s in O.lecturas(P.proj, fichas, tramos).items()}
nuevo = {f: set() for f in fichas}
for sp in glob.glob(os.path.join(P.proj, '*.jsonl')):
    trozos = P.lecturas(sp)
    for f in fichas:
        if f in trozos:
            nuevo[f].add(os.path.basename(sp)[:-6])
nuevo = {f: sorted(s) for f, s in nuevo.items()}
out['lecturas'] = nuevo == esperado
out['esperado'] = esperado
out['nuevo'] = nuevo
print(json.dumps(out, ensure_ascii=True))
'''

CRECE_MIENTRAS_SE_LEE = r'''
import sys, json
sys.path.insert(0, sys.argv[1])
import propiocepcion as P
leer = P._leer_sesion
def leer_y_que_crezca(path, lista):
    resultado = leer(path, lista)
    with open(path, 'a', encoding='utf-8') as fh:   # otro hilo escribe justo mientras esta lectura acaba
        fh.write(json.dumps({"type": "user", "message": {"content": "llega mientras se lee"},
                             "timestamp": "2026-01-01T10:59:00Z"}) + "\n")
    return resultado
P._leer_sesion = leer_y_que_crezca
print(P.extraer(sys.argv[2])['medida']['turnos_usuario'])
'''

OMITE_MIENTRAS_SE_LEE = r'''
import sys, subprocess
sys.path.insert(0, sys.argv[1])
import propiocepcion as P
leer = P._leer_sesion
def leer_y_que_la_omitan(path, lista):
    resultado = leer(path, lista)
    r = subprocess.run([sys.executable, sys.argv[3], '--omitir-sesion', sys.argv[4]], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(r.stderr)
    return resultado
P._leer_sesion = leer_y_que_la_omitan
P.extraer(sys.argv[2])
'''


def _comparar(test, proj, modo):
    guion = proj / '_comparar.py'
    guion.write_text(COMPARAR, encoding='utf-8')
    r = ay.ejecutar(guion, [ay.PKG, PRUEBAS, modo, proj / '_fichas.json'], ay.entorno(proj), timeout=60)
    test.assertEqual(r.returncode, 0, r.stderr)
    return json.loads(r.stdout.strip().splitlines()[-1])


def _medir(test, proj):
    r = ay.ejecutar(ay.script('propiocepcion.py'), [], ay.entorno(proj))
    test.assertEqual(r.returncode, 0, r.stderr)
    return json.loads((proj / 'memory' / 'propiocepcion.json').read_text(encoding='utf-8'))


class LoMismoQueElOraculo(unittest.TestCase):
    def test_el_corpus_toca_cada_borde(self):
        """Control del propio corpus: sin esto, una igualdad con el oráculo podría ser vacía."""
        proj = ay.nuevo_proyecto(); _corpus(proj)
        esperado = _comparar(self, proj, 'lecturas')['esperado']
        self.assertEqual(esperado['ficha-a.md'], ['ses-a'])
        self.assertEqual(esperado['ficha-c.md'], ['ses-a'], 'un Read en sidechain cuenta como lectura')
        self.assertEqual(esperado['ficha-d.md'], ['ses-a'], 'una línea que no es JSON cuenta como lectura')
        self.assertEqual(esperado['ficha-e.md'], ['ses-c'], 'una cadena JSON cuenta como lectura')
        self.assertEqual(esperado['ficha-secreta.md'], [], 'lo leído dentro del tramo no cuenta')
        self.assertEqual(esperado[NFC_MEDIA], ['ses-a'], 'la línea se compara en NFC')
        self.assertEqual(esperado[NFD_MEDIA], [], 'un nombre en NFD no casa con la línea en NFC')
        self.assertEqual(esperado['b.md'], ['ses-a', 'ses-c'], 'por subcadena, como siempre')
        self.assertEqual(esperado['lejos-2.md'], ['ses-a'])
        self.assertEqual(esperado[LARGA], ['ses-a'], 'un nombre largo tiene que caber entero en su trozo')
        self.assertEqual(esperado['nunca-leida.md'], [])

    def test_extraer_en_frio_y_en_caliente(self):
        proj = ay.nuevo_proyecto(); _corpus(proj)
        for vuelta in ('en frío', 'en caliente'):
            out = _comparar(self, proj, 'extraer')
            self.assertEqual(out['ses-a.jsonl'], {'medida': True, 'frases': True}, vuelta)
            self.assertEqual(out['ses-b.jsonl.gz'], {'medida': True, 'frases': True}, vuelta)
            self.assertTrue(out['lecturas'], f'{vuelta}: {out}')
            self.assertTrue((proj / 'memory' / '.matrioshka' / 'ses-a.json').exists(), vuelta)

    def test_lecturas_sin_muneca_no_escriben_nada(self):
        proj = ay.nuevo_proyecto(); _corpus(proj)
        out = _comparar(self, proj, 'lecturas')
        self.assertTrue(out['lecturas'], out)
        self.assertFalse((proj / 'memory' / '.matrioshka').exists(), 'lecturas() por su cuenta no guarda muñecas')

    def test_la_linea_json_que_no_es_objeto_solo_cuenta_para_lecturas(self):
        proj = ay.nuevo_proyecto(); _corpus(proj)
        out = _comparar(self, proj, 'rara')
        self.assertEqual((out['medida'], out['frases'], out['lecturas']), (True, True, True), out)


class CamposDeOtraForma(unittest.TestCase):
    def test_lo_que_no_se_entiende_no_cuenta_y_el_resto_se_mide(self):
        """`message`, `usage` o `input` que no son objetos, números escritos como texto y horas
        que no son ISO: la sesión se mide igual (medida y frases, por la CLI y por `--probar`)."""
        proj = ay.nuevo_proyecto()
        lineas = [
            ay.usuario('primera frase normal', T.format('10:00:00')),
            {'type': 'assistant', 'timestamp': T.format('10:01:00'), 'message': 'un mensaje que es una cadena'},
            {'type': 'assistant', 'timestamp': T.format('10:02:00'), 'requestId': 'r1',
             'message': {'usage': 'no es un objeto', 'content': 7}},
            {'type': 'assistant', 'timestamp': T.format('10:03:00'), 'requestId': 'r2',
             'message': {'usage': {'output_tokens': 'diez', 'output_tokens_details': 'nada', 'cache_read_input_tokens': 5},
                         'content': [{'type': 'tool_use', 'name': 'Agent', 'input': 'no es un objeto'}]}},
            {'type': 'user', 'timestamp': 1767261840, 'message': {'content': 'segunda frase con hora numérica'}},
            {'type': 'user', 'timestamp': 'ayer por la tarde', 'message': {'content': 'tercera frase con hora ilegible'}},
            ay.usuario('última frase normal', T.format('10:30:00')),
        ]
        texto = ''.join(json.dumps(d, ensure_ascii=False) + '\n' for d in lineas)
        (proj / 'ses-rara.jsonl').write_text(texto, encoding='utf-8')
        m = _medir(self, proj)['ses-rara']
        self.assertEqual(m['turnos_usuario'], 4)
        self.assertEqual((m['respuestas'], m['cache_leida'], m['tokens_salida'], m['herramientas']), (1, 5, 0, 1))
        self.assertEqual(m['sondas'], {'por-defecto': 1})
        self.assertEqual(m['horas'], 0.5, 'de 10:00 a 10:30: la hora ilegible no cuenta')

        ses = proj / 'memory' / 'sesiones'
        ses.mkdir(parents=True, exist_ok=True)
        (ses / 'ses-rara.jsonl').write_text(texto, encoding='utf-8')
        r = ay.ejecutar(ay.script('continuidad.py'), ['--probar', 'frase normal'], ay.entorno(proj, ABYSS_SIN_RED='1'))
        self.assertEqual(r.returncode, 0, r.stderr)
        bolsas = json.loads((proj / 'memory' / 'bolsas.json').read_text(encoding='utf-8'))
        self.assertIn('tercera', bolsas['ses-rara']['todo'])


class LaMunecaSeUsaYSeInvalida(unittest.TestCase):
    def _sesion(self):
        proj = ay.nuevo_proyecto()
        tp = ay.sesion_simple(proj / 'ses-m.jsonl', ['uno dos', 'tres cuatro', 'cinco seis'])
        return proj, tp

    def test_con_la_misma_firma_no_se_reabre_el_fichero(self):
        """El transcript cambiado por basura del MISMO tamaño y con su mtime de antes da la
        medida recordada: la prueba de que se usa la muñeca, y el límite escrito de la firma."""
        proj, tp = self._sesion()
        antes = _medir(self, proj)['ses-m']
        st = os.stat(tp)
        tp.write_bytes(b'x' * st.st_size)
        os.utime(tp, ns=(st.st_atime_ns, st.st_mtime_ns))
        self.assertEqual(_medir(self, proj)['ses-m'], antes)

    def test_una_linea_nueva_la_invalida(self):
        proj, tp = self._sesion()
        self.assertEqual(_medir(self, proj)['ses-m']['turnos_usuario'], 3)
        with open(tp, 'a', encoding='utf-8') as fh:
            fh.write(json.dumps(ay.usuario('siete ocho', T.format('10:05:00'))) + '\n')
        self.assertEqual(_medir(self, proj)['ses-m']['turnos_usuario'], 4)

    def test_abrir_un_tramo_la_invalida(self):
        proj, tp = self._sesion()
        self.assertEqual(_medir(self, proj)['ses-m']['turnos_usuario'], 3)
        (proj / 'memory' / 'parentesis.json').write_text(json.dumps({'ses-m': [
            {'inicio': '2026-01-01T10:00:30+00:00', 'fin': '2026-01-01T10:01:30+00:00', 'motivo': 'prueba'}]}),
            encoding='utf-8')
        self.assertEqual(_medir(self, proj)['ses-m']['turnos_usuario'], 2)
        st = os.stat(tp)
        tp.write_bytes(b'x' * st.st_size)
        os.utime(tp, ns=(st.st_atime_ns, st.st_mtime_ns))
        self.assertEqual(_medir(self, proj)['ses-m']['turnos_usuario'], 2,
                         'con un tramo en la firma la muñeca también acierta: no se ha releído la basura')

    def test_otro_codigo_obliga_a_releer(self):
        """La huella del código va en la firma: con un byte más en `propiocepcion.py`, lo
        recordado deja de valer y se relee (aquí, basura del mismo tamaño que ya no da turnos)."""
        proj, tp = self._sesion()
        copia = Path(tempfile.mkdtemp(prefix='abyss_codigo_')) / 'abyss'
        shutil.copytree(ay.PKG, copia, ignore=shutil.ignore_patterns('vendor', '__pycache__', 'config.json'))
        propio = proj / 'memory' / 'propiocepcion.json'

        def medir_con_la_copia():
            r = ay.ejecutar(copia / 'propiocepcion.py', [], ay.entorno(proj))
            self.assertEqual(r.returncode, 0, r.stderr)
            return json.loads(propio.read_text(encoding='utf-8'))

        self.assertIn('ses-m', medir_con_la_copia())
        st = os.stat(tp)
        tp.write_bytes(b'x' * st.st_size)
        os.utime(tp, ns=(st.st_atime_ns, st.st_mtime_ns))
        self.assertIn('ses-m', medir_con_la_copia(), 'control: mismo código y misma firma, sale de la muñeca')
        with open(copia / 'propiocepcion.py', 'a', encoding='utf-8') as fh:
            fh.write('\n# otra versión del código\n')
        self.assertNotIn('ses-m', medir_con_la_copia(), 'con otra huella se relee, y la basura no da turnos')

    def test_con_la_ultima_linea_a_medias_no_se_guarda(self):
        proj = ay.nuevo_proyecto()
        tp = proj / 'ses-media.jsonl'
        completas = ''.join(json.dumps(ay.usuario(f'frase {i}', T.format(f'10:0{i}:00'))) + '\n' for i in range(3))
        tp.write_text(completas + '{"type": "user", "message": {"con', encoding='utf-8')   # un escritor a mitad de línea
        muneca = proj / 'memory' / '.matrioshka' / 'ses-media.json'
        self.assertEqual(_medir(self, proj)['ses-media']['turnos_usuario'], 3)
        self.assertFalse(muneca.exists(), 'lo leído con la última línea a medias no se recuerda')
        tp.write_text(completas, encoding='utf-8')
        self.assertEqual(_medir(self, proj)['ses-media']['turnos_usuario'], 3)
        self.assertTrue(muneca.exists())

    def test_una_muneca_rota_o_con_otra_forma_no_cambia_nada(self):
        proj, _ = self._sesion()
        limpia = _medir(self, proj)['ses-m']
        muneca = proj / 'memory' / '.matrioshka' / 'ses-m.json'
        for contenido in (b'{roto', b'{"entradas": {}}', b'[]', b'\xff\xfe\x00 bytes que no son utf-8',
                          json.dumps({'entradas': [{'firma': 'otra forma'}]}).encode('ascii')):
            muneca.write_bytes(contenido)
            self.assertEqual(_medir(self, proj)['ses-m'], limpia, contenido)
        self.assertEqual(json.loads(muneca.read_text(encoding='utf-8'))['entradas'][-1]['medida'], limpia,
                         'tras una muñeca ilegible se relee y se vuelve a guardar bien')

    def test_sin_poder_escribirla_el_resultado_es_el_mismo(self):
        proj, _ = self._sesion()
        (proj / 'memory').mkdir(parents=True, exist_ok=True)
        (proj / 'memory' / '.matrioshka').write_text('no soy una carpeta', encoding='utf-8')
        self.assertEqual(_medir(self, proj)['ses-m']['turnos_usuario'], 3)
        self.assertTrue((proj / 'memory' / '.matrioshka').is_file())

    def test_un_surrogate_suelto_en_medio_no_impide_guardarla(self):
        proj = ay.nuevo_proyecto()
        lineas = [ay.usuario('primera frase', T.format('10:00:00')),
                  ay.usuario('un emoji cortado \ud83d en medio', T.format('10:01:00')),
                  ay.usuario('última frase', T.format('10:02:00'))]
        (proj / 'ses-s.jsonl').write_text(''.join(json.dumps(d, ensure_ascii=True) + '\n' for d in lineas), encoding='utf-8')
        primera = _medir(self, proj)['ses-s']
        self.assertTrue((proj / 'memory' / '.matrioshka' / 'ses-s.json').exists())
        self.assertEqual(_medir(self, proj)['ses-s'], primera)
        self.assertEqual(primera['turnos_usuario'], 3)


class UnEscritorALaVez(unittest.TestCase):
    def test_lo_leido_mientras_crece_no_se_queda_como_recordado(self):
        """Si el fichero crece durante la lectura, esa lectura no se guarda: ni con la firma de
        antes ni con la de después. El proceso siguiente tiene que ver la línea nueva."""
        proj = ay.nuevo_proyecto()
        tp = ay.sesion_simple(proj / 'ses-viva.jsonl', ['uno', 'dos', 'tres'])
        guion = proj / '_crece.py'
        guion.write_text(CRECE_MIENTRAS_SE_LEE, encoding='utf-8')
        r = ay.ejecutar(guion, [ay.PKG, tp], ay.entorno(proj))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip().splitlines()[-1], '3', 'esa lectura vio lo que había al empezar')
        self.assertFalse((proj / 'memory' / '.matrioshka' / 'ses-viva.json').exists(),
                         'la lectura que vio crecer el fichero no se guarda con ninguna firma')
        self.assertEqual(_medir(self, proj)['ses-viva']['turnos_usuario'], 4)


class OmitirMientrasSeLee(unittest.TestCase):
    def test_la_lectura_que_acaba_despues_de_omitir_no_deja_muneca(self):
        proj = ay.nuevo_proyecto()
        sid = 'ses-carrera'
        tp = ay.sesion_simple(proj / f'{sid}.jsonl', ['uno', 'dos'])
        guion = proj / '_omite.py'
        guion.write_text(OMITE_MIENTRAS_SE_LEE, encoding='utf-8')
        r = ay.ejecutar(guion, [ay.PKG, tp, ay.script('parentesis.py'), sid], ay.entorno(proj))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(sid, (proj / 'memory' / 'sesiones' / '.omitir').read_text(encoding='utf-8'))
        self.assertFalse((proj / 'memory' / '.matrioshka' / f'{sid}.json').exists())

    @unittest.skipUnless(os.name == 'nt', 'solo Windows impide borrar un fichero que otro proceso tiene abierto')
    def test_si_no_puede_borrar_la_muneca_lo_dice_y_la_quita_el_barrido(self):
        proj = ay.nuevo_proyecto()
        sid = 'ses-abierta'
        ay.sesion_simple(proj / f'{sid}.jsonl', ['uno'])
        _medir(self, proj)
        muneca = proj / 'memory' / '.matrioshka' / f'{sid}.json'
        self.assertTrue(muneca.exists())
        env = ay.entorno(proj, ABYSS_SIN_RED='1')
        with open(muneca, encoding='utf-8'):
            r = ay.ejecutar(ay.script('parentesis.py'), ['--omitir-sesion', sid], env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('no se pudo borrar', r.stdout)
        r = ay.ejecutar(ay.script('continuidad.py'), ['--cosecha'], env, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(muneca.exists())


class LoOmitidoNoDejaTexto(unittest.TestCase):
    def test_lo_dicho_tras_omitir_no_aparece_en_ningun_fichero_de_memory(self):
        proj = ay.nuevo_proyecto()
        sid = 'ses-omitida-matrioshka'
        tp = ay.sesion_simple(proj / f'{sid}.jsonl', ['antes de pedir que no se guarde'])
        env = ay.entorno(proj, ABYSS_SIN_RED='1')
        entrada = json.dumps({'session_id': sid, 'transcript_path': str(tp), 'cwd': str(proj)})
        muneca = proj / 'memory' / '.matrioshka' / f'{sid}.json'

        r = ay.ejecutar(ay.script('continuidad.py'), ['--cierre'], env, entrada=entrada, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(muneca.exists(), 'antes de omitir, la sesión tiene muñeca')
        r = ay.ejecutar(ay.script('parentesis.py'), ['--omitir-sesion', sid], env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(muneca.exists(), '--omitir-sesion se lleva la muñeca')

        with open(tp, 'a', encoding='utf-8') as fh:
            fh.write(json.dumps(ay.usuario('palabraunicaomitida dicha después', T.format('10:30:00'))) + '\n')
        for modo in ('--cierre', '--arranque'):
            r = ay.ejecutar(ay.script('continuidad.py'), [modo], env, entrada=entrada, timeout=60)
            self.assertEqual(r.returncode, 0, r.stderr)
        r = ay.ejecutar(ay.script('varas.py'), ['--index'], env)
        self.assertEqual(r.returncode, 0, r.stderr)

        for ruta in (proj / 'memory').rglob('*'):
            if ruta.is_file():
                self.assertNotIn(b'palabraunicaomitida', ruta.read_bytes(), str(ruta))
        self.assertFalse(muneca.exists(), 'de una sesión omitida no queda muñeca: ni del transcript ni de su copia')


class ElBarrido(unittest.TestCase):
    def test_quita_lo_que_ya_no_tiene_fichero_y_los_temporales_viejos(self):
        proj = ay.nuevo_proyecto()
        ay.sesion_simple(proj / 'ses-sigue.jsonl', ['sigue aquí'])
        munecas = proj / 'memory' / '.matrioshka'
        munecas.mkdir(parents=True)
        (munecas / 'ses-sin-fichero.json').write_text('{"entradas": []}', encoding='utf-8')
        viejo = munecas / 'ses-sigue.json.111.tmp'
        viejo.write_text('{', encoding='utf-8')
        hace_una_hora = time.time() - 3600
        os.utime(viejo, (hace_una_hora, hace_una_hora))
        reciente = munecas / 'ses-sigue.json.222.tmp'
        reciente.write_text('{', encoding='utf-8')
        ay.sesion_simple(proj / 'ses-omitida.jsonl', ['esta no se guarda'])
        (proj / 'memory' / 'sesiones').mkdir(parents=True, exist_ok=True)
        (proj / 'memory' / 'sesiones' / '.omitir').write_text('ses-omitida\n', encoding='utf-8')
        (munecas / 'ses-omitida.json').write_text('{"entradas": []}', encoding='utf-8')

        r = ay.ejecutar(ay.script('continuidad.py'), ['--cosecha'], ay.entorno(proj, ABYSS_SIN_RED='1'), timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse((munecas / 'ses-omitida.json').exists(), 'la de una sesión omitida se va aunque siga su transcript')
        self.assertFalse((munecas / 'ses-sin-fichero.json').exists())
        self.assertFalse(viejo.exists())
        self.assertTrue(reciente.exists(), 'un temporal reciente puede ser de otro proceso escribiendo ahora')
        self.assertTrue((munecas / 'ses-sigue.json').exists())


class FrioYCalienteDejanLosMismosFicheros(unittest.TestCase):
    def test_tres_cosechas_con_y_sin_munecas(self):
        proj = ay.nuevo_proyecto()
        mem = proj / 'memory'
        mem.mkdir(parents=True)
        for i in range(9):
            ay.sesion_simple(proj / f'ses-{i}.jsonl', [f'frase {j} de la sesión {i} con palabradistinta{i}' for j in range(3)],
                             inicio=datetime(2026, 1, 1 + i, 10, 0, 0, tzinfo=timezone.utc))
        for f in ('uno.md', 'dos.md'):
            (mem / f).write_text('---\ntype: reference\n---\ncontenido\n', encoding='utf-8')
        (mem / 'MEMORY.md').write_text('# Índice\n- [uno](uno.md)\n- [dos](dos.md)\n', encoding='utf-8')
        with open(proj / 'ses-0.jsonl', 'a', encoding='utf-8') as fh:
            fh.write(_read('uno.md', '2026-01-01T10:10:00Z') + '\n')
        env = ay.entorno(proj, ABYSS_SIN_RED='1')

        def cosecha():
            r = ay.ejecutar(ay.script('continuidad.py'), ['--cosecha'], env, timeout=60)
            self.assertEqual(r.returncode, 0, r.stderr)
            return {n: (mem / n).read_bytes() for n in ('propiocepcion.json', 'bolsas.json', 'relojes.jsonl', 'MEMORY.md')}

        fria = cosecha()
        self.assertTrue((mem / '.matrioshka').is_dir())
        self.assertEqual(cosecha(), fria, 'en caliente')
        shutil.rmtree(mem / '.matrioshka')
        self.assertEqual(cosecha(), fria, 'sin muñecas otra vez')
        self.assertIn('[uno](uno.md) ◆', fria['MEMORY.md'].decode('utf-8'), 'la lectura de uno.md cuenta')


class BorrarDatosSeLlevaLaMatrioshka(unittest.TestCase):
    def test_esta_entre_los_datos_generados(self):
        spec = importlib.util.spec_from_file_location('abyss_instalador_bajo_prueba_matrioshka', str(ay.RAIZ / 'instalar.py'))
        inst = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(inst)
        self.assertIn('.matrioshka', inst.DATOS_GENERADOS)


if __name__ == '__main__':
    unittest.main()
