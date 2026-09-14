"""El marcapáginas (`marcapaginas.py`) con el vigía: en cada Stop solo se leen las líneas nuevas y la evidencia
derivada crece en `memory/.marcapaginas/<sid>/`. Se comprueba contra `oraculo_turno.py` —la lectura entera de siempre—
que da lo mismo mientras el transcript crece, que se relee desde cero cuando algo de la firma no casa, que nunca decide
un resultado, que de una sesión omitida o recortada no queda nada, y que el barrido deja solo lo vivo."""
import sys
import os
import json
import time
import shutil
import tempfile
import importlib.util
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import unittest
import ayudas as ay

PRUEBAS = Path(__file__).resolve().parent
SID = 'ses-marca'

LEER = r'''
import sys, os, json, re
sys.path.insert(0, sys.argv[1]); sys.path.insert(0, sys.argv[2])
tp, sid = sys.argv[3], sys.argv[4]
respuestas = json.loads(sys.argv[5])
import vigia as V
import marcapaginas as MP
import oraculo_turno as O
lineas = [0]
original = MP.Lectura.lineas_nuevas
def contadas(self):
    for x in original(self):
        lineas[0] += 1
        yield x
MP.Lectura.lineas_nuevas = contadas
if len(sys.argv) > 6 and sys.argv[6] == 'falla-escritura':
    def falla(self, nombre, texto):
        raise OSError(28, 'No space left on device')
    MP.Lectura.escribir = falla
tramos = {sid: [tuple(t) for t in V.PZ.tramos(sid)]}
ev_o, fin_o = O.leer_turno(tp, tramos, sid=sid)
E, fin_n = V.leer_turno_marcado(tp, sid=sid)
carpeta = os.path.join(V.mem, '.marcapaginas', sid)
def fichero(n):
    try:
        return open(os.path.join(carpeta, n), 'rb').read().decode('utf-8', 'surrogatepass')
    except OSError:
        return None
marcado = isinstance(E.crudo, V._EnFichero)
out = {'lineas': lineas[0], 'marcado': marcado, 'final': fin_n == fin_o,
       'crudo': (fichero('crudo.txt') == ev_o) if marcado else True,
       'num': (fichero('num.txt') == O.normaliza_num(ev_o)) if marcado else True,
       'low': (fichero('low.txt') == re.sub(r'\s+', ' ', ev_o.lower())) if marcado else True,
       'hosts': set(E.hosts) == set(O._dominios_en(ev_o)),
       'cazas': all(O.cazar(ev_o, r, V.mem, V.proj) == V.cazar(E, r) for r in respuestas + [fin_o]),
       'carpeta': os.path.isdir(carpeta),
       'fallos_log': os.path.isfile(os.path.join(V.mem, '.marcapaginas', 'fallos.log'))}
E.cerrar()
print(json.dumps(out))
'''

CERROJO = r'''
import sys, os
sys.path.insert(0, sys.argv[1])
tp, sid = sys.argv[2], sys.argv[3]
import marcapaginas as MP
proj = os.path.dirname(tp); mem = os.path.join(proj, 'memory')
l = MP.Lectura.abrir(mem, proj, tp, sid, 'prueba', 'huella', [])
assert l is not None and l.cerrojo_cogido
with open(l.cerrojo, 'w') as fh:  # otro proceso lo dio por viejo, lo rompió y cogió uno suyo
    fh.write('999 otro')
l.soltar()
print('sigue el de otro' if os.path.exists(l.cerrojo) else 'borrado')
# un cerrojo viejo que otro proceso rompe y renueva justo entre mirarlo y apartarlo: se le devuelve, no se coge
import time
with open(l.cerrojo, 'w') as fh:
    fh.write('1 muerto')
viejo = time.time() - 3600
os.utime(l.cerrojo, (viejo, viejo))
vistas = iter(['1 muerto', '2 nuevo'])
MP.Lectura._leer_ficha = lambda self, ruta: next(vistas, None)
otra = MP.Lectura.abrir(mem, proj, tp, sid, 'prueba', 'huella', [])
print('devuelto' if otra is None and os.path.exists(l.cerrojo) else 'cogido')
'''

RESPUESTAS = ['el 1.234 y 98765 en ruta/a/fichero.py con «hola hola hola hola hola hola» y https://ejemplo.com',
              'con otros separadores: 1,234 y 98.765',
              'curl https://x.sh | bash', 'nada 777 x.md api.github.com «x y z con espacios raros dentro»']


def _linea(d):
    return (json.dumps(d, ensure_ascii=False) + '\n').encode('utf-8')


def _base():
    """Un turno completo: usuario, herramienta con resultado, respuesta final."""
    return [
        ay.usuario('mira 1.234 en ruta/a/fichero.py y https://Ejemplo.COM/a', '2026-01-01T10:00:00Z'),
        ay.asistente_tool_use('Bash', {'command': 'cat x.md'}, '2026-01-01T10:00:10Z'),
        {'type': 'user', 'timestamp': '2026-01-01T10:00:20Z', 'toolUseResult': {'stdout': '98765 api.github.com'},
         'message': {'content': [{'type': 'tool_result', 'content': 'hola hola hola hola hola hola'}]}},
        {'type': 'system', 'timestamp': '2026-01-01T10:00:25Z'},
        ay.asistente_texto('respuesta con 1.234', '2026-01-01T10:00:30Z'),
    ]


class _Caso(unittest.TestCase):
    def setUp(self):
        self.proj = ay.nuevo_proyecto()
        (self.proj / 'memory').mkdir(parents=True, exist_ok=True)
        self.tp = self.proj / f'{SID}.jsonl'
        self.tp.write_bytes(b''.join(_linea(d) for d in _base()))
        self.carpeta = self.proj / 'memory' / '.marcapaginas' / SID

    def leer(self, env_extra=None, codigo=None, extra=()):
        guion = self.proj / '_leer.py'
        guion.write_text(LEER, encoding='utf-8')
        env = ay.entorno(self.proj, ABYSS_SIN_RED='1', ABYSS_TOPE_STDIN='0', **(env_extra or {}))
        r = ay.ejecutar(guion, [codigo or ay.PKG, PRUEBAS, self.tp, SID, json.dumps(RESPUESTAS), *extra], env, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout.strip().splitlines()[-1])

    def igual(self, out, msg=''):
        self.assertEqual({k: out[k] for k in ('final', 'crudo', 'num', 'low', 'hosts', 'cazas')},
                         dict.fromkeys(('final', 'crudo', 'num', 'low', 'hosts', 'cazas'), True), f'{msg} {out}')

    def anadir(self, *lineas, crlf=False):
        with open(self.tp, 'ab') as fh:
            for d in lineas:
                b = _linea(d) if isinstance(d, dict) else d
                fh.write(b.replace(b'\n', b'\r\n') if crlf else b)


class Crece(_Caso):
    def test_solo_se_leen_las_lineas_nuevas_y_da_lo_mismo(self):
        primero = self.leer()
        self.igual(primero, 'primera lectura')
        self.assertEqual(primero['lineas'], len(_base()))
        self.anadir(ay.usuario('otra pregunta con Σ y ΑΣ y  espacios raros', '2026-01-01T10:01:00Z'),
                    ay.asistente_texto('otra respuesta', '2026-01-01T10:01:30Z'))
        segundo = self.leer()
        self.igual(segundo, 'tras crecer')
        self.assertEqual(segundo['lineas'], 2, 'solo las dos líneas nuevas')

    def test_crlf_y_retorno_suelto_cuentan_como_en_modo_texto(self):
        self.leer()
        dos = _linea(ay.usuario('a 11', '2026-01-01T10:02:00Z')).rstrip(b'\n') + b'\r' + _linea(ay.usuario('b 22', '2026-01-01T10:02:01Z'))
        self.anadir(dos, ay.asistente_texto('final 33', '2026-01-01T10:02:02Z'), crlf=True)
        self.igual(self.leer(), 'CRLF y \\r suelto')

    def test_la_frontera_de_low_se_cose_bien(self):
        self.leer()
        for texto in ('x', ' y', 'x ', ' y', '', '   ', 'fin'):
            self.anadir(ay.usuario(texto, '2026-01-01T10:03:00Z'))
            self.igual(self.leer(), f'pieza {texto!r}')

    def test_una_ultima_linea_sin_salto_que_es_json_se_lee_entera(self):
        self.leer()
        self.anadir(_linea(ay.asistente_texto('sin salto 4444', '2026-01-01T10:04:00Z')).rstrip(b'\n'))
        out = self.leer()
        self.igual(out, 'cola JSON sin salto')
        self.assertFalse(out['marcado'], 'esa vez sin marcapáginas: la lectura entera de siempre')

    def test_una_ultima_linea_a_medio_escribir_no_cambia_nada(self):
        self.leer()
        self.anadir(b'{"type": "user", "message": {"con')
        out = self.leer()
        self.igual(out, 'cola a medias')

    def test_un_surrogate_suelto_se_guarda_y_se_busca(self):
        self.leer()
        self.anadir(('{"type": "user", "timestamp": "2026-01-01T10:05:00Z", "message": {"content": "roto \\ud83d 5555"}}\n').encode('ascii'))
        self.igual(self.leer(), 'surrogate')


class SeReleeDesdeCero(_Caso):
    def test_un_recorte_del_transcript(self):
        self.leer()
        lineas = self.tp.read_bytes().splitlines(keepends=True)
        self.tp.write_bytes(b''.join(lineas[:2]) + _linea(ay.asistente_texto('otra cosa 6666', '2026-01-01T10:06:00Z')))
        out = self.leer()
        self.igual(out, 'recortado')
        self.assertEqual(out['lineas'], 3)

    def test_otro_contenido_en_la_cabeza_con_la_misma_longitud(self):
        relleno = ay.usuario('relleno ' + 'r' * (70 * 1024), '2026-01-01T10:00:40Z')
        self.anadir(relleno)
        self.leer()
        self.tp.write_bytes(self.tp.read_bytes().replace(b'mira 1.234', b'mira 9.876', 1))
        self.anadir(ay.usuario('sigo', '2026-01-01T10:08:00Z'))
        out = self.leer()
        self.igual(out, 'cabeza cambiada')
        self.assertEqual(out['lineas'], len(_base()) + 2, 'se relee desde cero')

    def test_otro_contenido_en_la_cola_con_la_misma_longitud(self):
        relleno = ay.usuario('relleno ' + 'r' * (70 * 1024), '2026-01-01T09:59:00Z')
        self.tp.write_bytes(_linea(relleno) + b''.join(_linea(d) for d in _base()))
        self.leer()
        self.tp.write_bytes(self.tp.read_bytes().replace(b'98765 api.github.com', b'12345 api.github.com', 1))
        self.anadir(ay.usuario('sigo', '2026-01-01T10:08:00Z'))
        out = self.leer()
        self.igual(out, 'cola cambiada')
        self.assertEqual(out['lineas'], len(_base()) + 2, 'se relee desde cero')

    def test_abrir_un_tramo(self):
        self.leer()
        (self.proj / 'memory' / 'parentesis.json').write_text(json.dumps({SID: [
            {'inicio': '2026-01-01T10:00:15+00:00', 'fin': '2026-01-01T10:00:22+00:00', 'motivo': 'prueba'}]}), encoding='utf-8')
        out = self.leer()
        self.igual(out, 'con tramo')
        self.assertEqual(out['lineas'], len(_base()))

    def test_otra_huella_de_codigo(self):
        self.leer()
        copia = Path(tempfile.mkdtemp(prefix='abyss_codigo_')) / 'abyss'
        shutil.copytree(ay.PKG, copia, ignore=shutil.ignore_patterns('vendor', '__pycache__', 'config.json'))
        with open(copia / 'vigia.py', 'a', encoding='utf-8') as fh:
            fh.write('\n# otra versión\n')
        out = self.leer(codigo=copia)
        self.igual(out, 'otra huella')
        self.assertEqual(out['lineas'], len(_base()))

    def test_un_fichero_de_datos_mas_corto_o_borrado(self):
        for nombre in ('crudo.txt', 'num.txt', 'low.txt'):
            self.leer()
            (self.carpeta / nombre).unlink()
            out = self.leer()
            self.igual(out, f'sin {nombre}')
            self.assertEqual(out['lineas'], len(_base()) + 0, f'sin {nombre} se empieza de cero')
            with open(self.carpeta / nombre, 'r+b') as fh:
                fh.truncate(3)
            out = self.leer()
            self.igual(out, f'{nombre} más corto')

    def test_un_fichero_de_datos_mas_largo_se_trunca(self):
        self.leer()
        with open(self.carpeta / 'num.txt', 'ab') as fh:
            fh.write(b'\n777777 basura de un proceso matado')
        self.anadir(ay.asistente_texto('y 777777', '2026-01-01T10:07:00Z'))
        out = self.leer()
        self.igual(out, 'datos más largos')
        self.assertEqual(out['lineas'], 1)

    def test_un_estado_roto(self):
        self.leer()
        (self.carpeta / 'vigia.json').write_bytes(b'{roto')
        out = self.leer()
        self.igual(out, 'estado roto')
        self.assertEqual(out['lineas'], len(_base()))


class NuncaDecideElResultado(_Caso):
    def test_sin_poder_escribir(self):
        (self.proj / 'memory' / '.marcapaginas').write_text('no soy una carpeta', encoding='utf-8')
        self.igual(self.leer(), 'sin carpeta')

    def test_con_el_cerrojo_cogido_por_otro(self):
        self.leer()
        (self.carpeta / 'vigia.lock').write_text('123', encoding='utf-8')
        self.anadir(ay.asistente_texto('con cerrojo 8888', '2026-01-01T10:08:00Z'))
        out = self.leer()
        self.igual(out, 'cerrojo reciente')
        self.assertFalse(out['marcado'])
        viejo = time.time() - 3600
        os.utime(self.carpeta / 'vigia.lock', (viejo, viejo))
        out = self.leer()
        self.igual(out, 'cerrojo viejo')
        self.assertEqual(out['lineas'], 1, 'un cerrojo viejo es de un proceso muerto: se coge')

    def test_si_falla_la_escritura_de_los_datos_se_lee_entero_y_se_apunta(self):
        out = self.leer(extra=['falla-escritura'])
        self.igual(out, 'escritura que falla')
        self.assertFalse(out['marcado'])
        self.assertTrue(out['fallos_log'])

    def test_soltar_no_quita_un_cerrojo_que_ya_es_de_otro(self):
        guion = self.proj / '_cerrojo.py'
        guion.write_text(CERROJO, encoding='utf-8')
        r = ay.ejecutar(guion, [ay.PKG, self.tp, SID], ay.entorno(self.proj, ABYSS_SIN_RED='1'))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip().splitlines()[-2:], ['sigue el de otro', 'devuelto'])

    def test_de_una_sesion_omitida_no_se_guarda_nada(self):
        ses = self.proj / 'memory' / 'sesiones'
        ses.mkdir(parents=True, exist_ok=True)
        (ses / '.omitir').write_text(SID + '\n', encoding='utf-8')
        out = self.leer()
        self.igual(out, 'omitida')
        self.assertFalse(out['marcado'])
        self.assertFalse(out['carpeta'])


class LoQueSeQuitaNoSigueVivo(_Caso):
    def test_omitir_y_recortar_borran_el_marcapaginas(self):
        env = ay.entorno(self.proj, ABYSS_SIN_RED='1')
        self.leer()
        self.assertTrue(self.carpeta.is_dir())
        r = ay.ejecutar(ay.script('parentesis.py'), ['--recortar-tramo', self.tp, '2026-01-01T10:00:15Z', '2026-01-01T10:00:22Z'], env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(self.carpeta.exists(), '--recortar-tramo se lleva lo derivado')
        self.leer()
        r = ay.ejecutar(ay.script('parentesis.py'), ['--omitir-sesion', SID], env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(self.carpeta.exists(), '--omitir-sesion se lleva lo derivado')

    def test_cerrar_la_sesion_borra_su_marcapaginas_y_barre_el_resto(self):
        self.leer()
        vieja = self.proj / 'memory' / '.marcapaginas' / 'vieja'
        vieja.mkdir(parents=True)
        (vieja / 'vigia.json').write_text('{}', encoding='utf-8')
        (self.proj / 'vieja.jsonl').write_text('', encoding='utf-8')
        t = time.time() - 7 * 3600
        os.utime(vieja / 'vigia.json', (t, t)); os.utime(vieja, (t, t))
        entrada = json.dumps({'session_id': SID, 'transcript_path': str(self.tp), 'cwd': str(self.proj)})
        r = ay.ejecutar(ay.script('continuidad.py'), ['--cierre'], ay.entorno(self.proj, ABYSS_SIN_RED='1'),
                        entrada=entrada, timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(self.carpeta.exists(), 'la sesión que se cierra se lleva su marcapáginas')
        self.assertFalse(vieja.exists(), 'y el cierre barre las carpetas de más de 6 h')


class ElBarrido(_Caso):
    def test_deja_solo_lo_vivo(self):
        base = self.proj / 'memory' / '.marcapaginas'
        ahora = time.time()

        def carpeta(sid, horas, transcript=True):
            c = base / sid
            c.mkdir(parents=True, exist_ok=True)
            (c / 'vigia.json').write_text('{}', encoding='utf-8')
            t = ahora - horas * 3600
            os.utime(c / 'vigia.json', (t, t)); os.utime(c, (t, t))
            if transcript:
                (self.proj / f'{sid}.jsonl').write_text('', encoding='utf-8')
            return c

        vieja = carpeta('vieja', 7)
        sin_transcript = carpeta('sin-transcript', 0.1, transcript=False)
        omitida = carpeta('omitida', 0.1)
        (self.proj / 'memory' / 'sesiones').mkdir(parents=True, exist_ok=True)
        (self.proj / 'memory' / 'sesiones' / '.omitir').write_text('omitida\n', encoding='utf-8')
        recientes = [carpeta(f'reciente-{i}', 0.5 + i) for i in range(5)]
        self.leer()
        self.assertTrue(self.carpeta.is_dir(), 'la de la sesión que acaba de leer se queda')
        for c in (vieja, sin_transcript, omitida, recientes[3], recientes[4]):
            self.assertFalse(c.exists(), c.name)
        for c in recientes[:3]:
            self.assertTrue(c.exists(), c.name)

    def test_quita_temporales_y_cerrojos_apartados_viejos_de_una_carpeta_viva(self):
        self.leer()
        viejo = self.carpeta / 'vigia.json.4242.tmp'
        apartado = self.carpeta / 'vigia.lock.abcd'
        reciente = self.carpeta / 'vigia.json.4343.tmp'
        for f in (viejo, apartado, reciente):
            f.write_text('{', encoding='utf-8')
        t = time.time() - 3600
        for f in (viejo, apartado):
            os.utime(f, (t, t))
        self.anadir(ay.usuario('sigo', '2026-01-01T10:08:00Z'))
        self.leer()
        self.assertFalse(viejo.exists())
        self.assertFalse(apartado.exists())
        self.assertTrue(reciente.exists(), 'uno reciente puede ser de un proceso que sigue escribiendo')


class ElGanchoStop(_Caso):
    def test_bloquea_en_frio_y_en_caliente(self):
        self.anadir(ay.usuario('y ahora qué', '2026-01-01T10:09:00Z'),
                    ay.asistente_texto('te digo 424242 y 313131 y la ruta inventada/nunca.py', '2026-01-01T10:09:30Z'))
        entrada = json.dumps({'session_id': SID, 'transcript_path': str(self.tp), 'cwd': str(self.proj)})
        env = ay.entorno(self.proj, ABYSS_SIN_RED='1')
        for vuelta in ('frío', 'caliente'):
            r = ay.ejecutar(ay.script('vigia.py'), ['--verificar'], env, entrada=entrada, timeout=60)
            self.assertEqual(r.returncode, 0, r.stderr)
            razon = json.loads(r.stdout)['reason']
            for caza in ('424242', '313131', 'inventada/nunca.py'):
                self.assertIn(caza, razon, vuelta)
            self.assertNotIn('1.234', razon.split('números sin fuente:')[1].split(';')[0], vuelta)
        self.assertTrue((self.carpeta / 'vigia.json').exists())


class BorrarDatosSeLlevaElMarcapaginas(unittest.TestCase):
    def test_esta_entre_los_datos_generados(self):
        spec = importlib.util.spec_from_file_location('abyss_instalador_bajo_prueba_marcapaginas', str(ay.RAIZ / 'instalar.py'))
        inst = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(inst)
        self.assertIn('.marcapaginas', inst.DATOS_GENERADOS)


if __name__ == '__main__':
    unittest.main()
