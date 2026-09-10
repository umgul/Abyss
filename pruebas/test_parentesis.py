"""`parentesis.py` (ESPECIFICACION.md §8).

Casos: `--abrir`/`--cerrar` marcan un tramo por sesión y no duplican uno ya
abierto; `--omitir-sesion` escribe (una vez) en sesiones/.omitir; `--recortar`
conserva hasta la respuesta al mensaje dado y deja `.antes`, y se niega sobre un
hilo con latido reciente; `--recortar-tramo` quita solo las líneas del tramo de
tiempo dado; y, de punta a punta, un tramo marcado hace que `continuidad.py
--cierre` no copie esas líneas a sesiones/ ni las bolsas lleven sus palabras.
"""
import sys
import os
import json
import time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import unittest
import ayudas as ay


class AbrirYCerrar(unittest.TestCase):
    def test_abrir_cerrar_marca_tramo(self):
        proj = ay.nuevo_proyecto()
        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('parentesis.py'), ['--abrir', 'probando', '--sesion', 'sid-1'], env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('abierto', r.stdout)

        datos = json.loads((proj / 'memory' / 'parentesis.json').read_text(encoding='utf-8'))
        self.assertEqual(len(datos['sid-1']), 1)
        self.assertIsNone(datos['sid-1'][0]['fin'])
        self.assertEqual(datos['sid-1'][0]['motivo'], 'probando')

        r2 = ay.ejecutar(ay.script('parentesis.py'), ['--cerrar', '--sesion', 'sid-1'], env)
        self.assertEqual(r2.returncode, 0, r2.stderr)
        self.assertIn('cerrado', r2.stdout)
        datos2 = json.loads((proj / 'memory' / 'parentesis.json').read_text(encoding='utf-8'))
        self.assertIsNotNone(datos2['sid-1'][0]['fin'])

    def test_abrir_dos_veces_no_duplica(self):
        proj = ay.nuevo_proyecto()
        env = ay.entorno(proj)
        ay.ejecutar(ay.script('parentesis.py'), ['--abrir', 'uno', '--sesion', 'sid-1'], env)
        r = ay.ejecutar(ay.script('parentesis.py'), ['--abrir', 'dos', '--sesion', 'sid-1'], env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('ya había un paréntesis abierto', r.stdout)
        datos = json.loads((proj / 'memory' / 'parentesis.json').read_text(encoding='utf-8'))
        self.assertEqual(len(datos['sid-1']), 1, 'no debe abrir un segundo tramo mientras el primero sigue abierto')

    def test_cerrar_sin_nada_abierto_lo_dice(self):
        proj = ay.nuevo_proyecto()
        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('parentesis.py'), ['--cerrar', '--sesion', 'sid-nunca-abierta'], env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('no hay ningún paréntesis abierto', r.stdout)

    def test_sin_sesion_y_sin_latido_vivo_se_niega(self):
        proj = ay.nuevo_proyecto()
        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('parentesis.py'), ['--abrir', 'motivo'], env)
        self.assertEqual(r.returncode, 1)
        self.assertIn('no se sabe de que sesion', r.stderr)

    def test_usa_el_latido_mas_reciente_como_heuristica(self):
        proj = ay.nuevo_proyecto()
        vivo = proj / 'memory' / '.vivo'
        vivo.mkdir(parents=True, exist_ok=True)
        (vivo / 'sid-viejo.json').write_text(json.dumps({'id': 'sid-viejo', 'ts': time.time() - 500}), encoding='utf-8')
        (vivo / 'sid-fresco.json').write_text(json.dumps({'id': 'sid-fresco', 'ts': time.time()}), encoding='utf-8')
        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('parentesis.py'), ['--abrir', 'motivo'], env)  # sin --sesion
        self.assertEqual(r.returncode, 0, r.stderr)
        datos = json.loads((proj / 'memory' / 'parentesis.json').read_text(encoding='utf-8'))
        self.assertIn('sid-fresco', datos)
        self.assertNotIn('sid-viejo', datos)


class OmitirSesion(unittest.TestCase):
    def test_omitir_sesion_escribe_una_vez(self):
        proj = ay.nuevo_proyecto()
        env = ay.entorno(proj)
        r1 = ay.ejecutar(ay.script('parentesis.py'), ['--omitir-sesion', 'sid-2'], env)
        self.assertEqual(r1.returncode, 0, r1.stderr)
        omitir = proj / 'memory' / 'sesiones' / '.omitir'
        self.assertEqual(omitir.read_text(encoding='utf-8').strip(), 'sid-2')

        r2 = ay.ejecutar(ay.script('parentesis.py'), ['--omitir-sesion', 'sid-2'], env)
        self.assertEqual(r2.returncode, 0, r2.stderr)
        self.assertIn('ya estaba', r2.stdout)
        lineas = [l for l in omitir.read_text(encoding='utf-8').splitlines() if l.strip()]
        self.assertEqual(lineas, ['sid-2'], 'no debe duplicar la línea')


class Recortar(unittest.TestCase):
    def _transcript(self, proj, sid):
        tp = proj / f'{sid}.jsonl'
        ay.escribir_jsonl(tp, [
            ay.usuario('hola', '2026-01-01T10:00:00Z'),
            ay.asistente_texto('hola tambien', '2026-01-01T10:00:05Z'),
            ay.usuario('cuentame algo', '2026-01-01T10:05:00Z'),
            ay.asistente_texto('aqui algo', '2026-01-01T10:05:05Z'),
            ay.usuario('gracias', '2026-01-01T10:10:00Z'),
            ay.asistente_texto('de nada', '2026-01-01T10:10:05Z'),
        ])
        return tp

    def test_recortar_conserva_hasta_la_respuesta_al_mensaje(self):
        proj = ay.nuevo_proyecto()
        sid = 'ses-recorte-1'
        tp = self._transcript(proj, sid)
        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('parentesis.py'), ['--recortar', str(tp), 'cuentame algo'], env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((proj / f'{sid}.jsonl.antes').exists(), 'debe dejar copia .antes')

        lineas = tp.read_text(encoding='utf-8').strip().splitlines()
        self.assertEqual(len(lineas), 4)
        ultimo = json.loads(lineas[-1])
        self.assertEqual(ultimo['message']['content'][0]['text'], 'aqui algo')
        # el original queda intacto en .antes
        antes = json.loads((proj / f'{sid}.jsonl.antes').read_text(encoding='utf-8').strip().splitlines()[-1])
        self.assertEqual(antes['message']['content'][0]['text'], 'de nada')

    def test_recortar_mensaje_inexistente_no_toca_nada(self):
        proj = ay.nuevo_proyecto()
        sid = 'ses-recorte-2'
        tp = self._transcript(proj, sid)
        original = tp.read_text(encoding='utf-8')
        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('parentesis.py'), ['--recortar', str(tp), 'esto no lo dijo nadie'], env)
        self.assertEqual(r.returncode, 1)
        self.assertIn('no se encontró', r.stdout)
        self.assertEqual(tp.read_text(encoding='utf-8'), original)
        self.assertFalse((proj / f'{sid}.jsonl.antes').exists())

    def test_recortar_se_niega_con_hilo_vivo(self):
        proj = ay.nuevo_proyecto()
        sid = 'ses-recorte-3'
        tp = self._transcript(proj, sid)
        original = tp.read_text(encoding='utf-8')
        vivo = proj / 'memory' / '.vivo'
        vivo.mkdir(parents=True, exist_ok=True)
        (vivo / f'{sid}.json').write_text(json.dumps({'id': sid, 'ts': time.time()}), encoding='utf-8')
        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('parentesis.py'), ['--recortar', str(tp), 'cuentame algo'], env)
        self.assertEqual(r.returncode, 1)
        self.assertIn('se niega', r.stdout)
        self.assertEqual(tp.read_text(encoding='utf-8'), original, 'un hilo vivo no se toca')
        self.assertFalse((proj / f'{sid}.jsonl.antes').exists())

    def test_recortar_con_latido_viejo_si_procede(self):
        proj = ay.nuevo_proyecto()
        sid = 'ses-recorte-4'
        tp = self._transcript(proj, sid)
        vivo = proj / 'memory' / '.vivo'
        vivo.mkdir(parents=True, exist_ok=True)
        (vivo / f'{sid}.json').write_text(json.dumps({'id': sid, 'ts': time.time() - 300}), encoding='utf-8')
        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('parentesis.py'), ['--recortar', str(tp), 'cuentame algo'], env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((proj / f'{sid}.jsonl.antes').exists())

    def test_recortar_tramo_quita_solo_lo_marcado(self):
        proj = ay.nuevo_proyecto()
        sid = 'ses-tramo-1'
        tp = proj / f'{sid}.jsonl'
        ay.escribir_jsonl(tp, [
            ay.usuario('a', '2026-01-01T10:00:00Z'),
            ay.usuario('SECRETO b', '2026-01-01T10:05:00Z'),
            ay.usuario('SECRETO c', '2026-01-01T10:06:00Z'),
            ay.usuario('d', '2026-01-01T10:10:00Z'),
        ])
        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('parentesis.py'),
                         ['--recortar-tramo', str(tp), '2026-01-01T10:04:30Z', '2026-01-01T10:06:30Z'], env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((proj / f'{sid}.jsonl.antes').exists())
        restante = tp.read_text(encoding='utf-8')
        self.assertNotIn('SECRETO', restante)
        self.assertIn('"a"', restante)
        self.assertIn('"d"', restante)


class IntegracionConContinuidad(unittest.TestCase):
    def test_tramo_no_viaja_a_sesiones_ni_a_bolsas(self):
        proj = ay.nuevo_proyecto()
        sid = 'ses-integra-1'
        tp = proj / f'{sid}.jsonl'
        ay.escribir_jsonl(tp, [
            ay.usuario('hola esto es fuera del parentesis palabraexterior', '2026-01-01T10:00:00Z'),
            ay.asistente_texto('ok', '2026-01-01T10:00:05Z'),
            ay.usuario('secretounico esto no debe guardarse jamas', '2026-01-01T10:05:00Z'),
            ay.asistente_texto('entendido secretounico', '2026-01-01T10:05:05Z'),
            ay.usuario('esto es despues fuera otra vez palabraposteriordistinta', '2026-01-01T10:10:00Z'),
        ])
        mem = proj / 'memory'
        mem.mkdir(parents=True, exist_ok=True)
        (mem / 'parentesis.json').write_text(json.dumps({
            sid: [{'inicio': '2026-01-01T10:04:30+00:00', 'fin': '2026-01-01T10:06:00+00:00', 'motivo': 'prueba'}]
        }), encoding='utf-8')

        entrada = json.dumps({'session_id': sid, 'transcript_path': str(tp), 'cwd': str(proj)})
        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('continuidad.py'), ['--cierre'], env, entrada=entrada)
        self.assertEqual(r.returncode, 0, r.stderr)

        copia = mem / 'sesiones' / f'{sid}.jsonl'
        self.assertTrue(copia.exists())
        contenido = copia.read_text(encoding='utf-8')
        self.assertNotIn('secretounico', contenido)
        self.assertIn('palabraexterior', contenido)
        self.assertIn('palabraposteriordistinta', contenido)

        bolsas = json.loads((mem / 'bolsas.json').read_text(encoding='utf-8'))
        todo = bolsas.get(sid, {}).get('todo', {})
        self.assertNotIn('secretounico', todo)
        self.assertIn('palabraexterior', todo)

    def test_omitir_sesion_impide_toda_copia(self):
        proj = ay.nuevo_proyecto()
        sid = 'ses-omitida-1'
        tp = proj / f'{sid}.jsonl'
        ay.escribir_jsonl(tp, [ay.usuario('esto no debe guardarse en absoluto', '2026-01-01T10:00:00Z')])
        env = ay.entorno(proj)
        r0 = ay.ejecutar(ay.script('parentesis.py'), ['--omitir-sesion', sid], env)
        self.assertEqual(r0.returncode, 0, r0.stderr)

        entrada = json.dumps({'session_id': sid, 'transcript_path': str(tp), 'cwd': str(proj)})
        r = ay.ejecutar(ay.script('continuidad.py'), ['--cierre'], env, entrada=entrada)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse((proj / 'memory' / 'sesiones' / f'{sid}.jsonl').exists())
        self.assertFalse((proj / 'memory' / 'sesiones' / f'{sid}.jsonl.gz').exists())


class IntegracionConVigia(unittest.TestCase):
    """Fallo "engaña" medido 7-sep: `vigia.leer_turno()` no miraba el tramo en
    absoluto, así que una respuesta dicha DENTRO de un paréntesis abierto sí se
    verificaba, y sus fragmentos podían quedar guardados (literales, hasta 40
    caracteres) en `confabulaciones.jsonl` — justo lo que el tramo promete que
    no viaja. Ver `parentesis.en_parentesis()` y `vigia.leer_turno()`."""

    def test_respuesta_dentro_del_tramo_no_se_verifica_ni_se_guarda(self):
        proj = ay.nuevo_proyecto()
        sid = 'ses-vigia-tramo-1'
        tp = proj / f'{sid}.jsonl'
        ay.escribir_jsonl(tp, [
            ay.usuario('cuentame algo dentro del parentesis', '2026-01-01T10:05:00Z'),
            ay.asistente_texto('Un dato secreto: el numero 7777777 no sale de ningun sitio.',
                                '2026-01-01T10:05:05Z'),
        ])
        mem = proj / 'memory'
        mem.mkdir(parents=True, exist_ok=True)
        (mem / 'parentesis.json').write_text(json.dumps({
            sid: [{'inicio': '2026-01-01T10:04:00+00:00', 'fin': '2026-01-01T10:06:00+00:00', 'motivo': 'prueba'}]
        }), encoding='utf-8')

        entrada = json.dumps({'session_id': sid, 'transcript_path': str(tp), 'cwd': str(proj)})
        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('vigia.py'), [], env, entrada=entrada)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), '', 'una respuesta entera dentro del tramo no debe generar bloqueo')

        conf = mem / 'confabulaciones.jsonl'
        self.assertFalse(conf.exists(), 'nada de lo dicho dentro del tramo debe llegar a confabulaciones.jsonl')

    def test_respuesta_fuera_del_tramo_se_sigue_verificando(self):
        """Control: sin tocar nada dentro del tramo, el vigía sigue cazando lo
        de siempre — el filtro no lo apaga en general, solo dentro del tramo."""
        proj = ay.nuevo_proyecto()
        sid = 'ses-vigia-fuera-1'
        tp = proj / f'{sid}.jsonl'
        ay.escribir_jsonl(tp, [
            ay.usuario('cuentame algo fuera del parentesis', '2026-01-01T10:20:00Z'),
            ay.asistente_texto('Un dato curioso: el numero 8888888 no sale de ningun sitio.',
                                '2026-01-01T10:20:05Z'),
        ])
        mem = proj / 'memory'
        mem.mkdir(parents=True, exist_ok=True)
        (mem / 'parentesis.json').write_text(json.dumps({
            sid: [{'inicio': '2026-01-01T10:04:00+00:00', 'fin': '2026-01-01T10:06:00+00:00', 'motivo': 'prueba'}]
        }), encoding='utf-8')

        entrada = json.dumps({'session_id': sid, 'transcript_path': str(tp), 'cwd': str(proj)})
        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('vigia.py'), [], env, entrada=entrada)
        self.assertEqual(r.returncode, 0, r.stderr)

        conf = mem / 'confabulaciones.jsonl'
        self.assertTrue(conf.exists())
        registros = [json.loads(l) for l in conf.read_text(encoding='utf-8').splitlines() if l.strip()]
        self.assertTrue(any('8888888' in reg.get('numeros', []) for reg in registros))


class TramoAbiertoSinCerrarNoSeEscapa(unittest.TestCase):
    """Fallo "roza" medido 7-sep: la rama más crítica de `en_parentesis()` —un
    tramo `--abrir` sin `--cerrar` (`fin: None`), que el propio docstring
    describe como «nada de lo posterior al --abrir se escapa igual»— no tenía
    ningún falsador. Mutando `if fin is None: return True` a `return False`
    (un tramo sin cerrar deja de proteger absolutamente nada) la SUITE ENTERA
    seguía en verde. Aquí se ejercita de punta a punta: `--abrir` real, sin
    `--cerrar`, y `continuidad.py --cierre` sobre un transcript cuyo último
    mensaje cae DESPUÉS del `--abrir`."""

    def test_lo_dicho_tras_abrir_sin_cerrar_no_llega_a_sesiones(self):
        proj = ay.nuevo_proyecto()
        sid = 'ses-abierto-1'
        tp = proj / f'{sid}.jsonl'
        ay.escribir_jsonl(tp, [
            ay.usuario('esto es antes del parentesis palabraantes', '2026-01-01T10:00:00Z'),
            ay.asistente_texto('ok', '2026-01-01T10:00:05Z'),
            ay.usuario('secretoabierto esto no debe guardarse nunca', '2026-01-01T10:05:00Z'),
            ay.asistente_texto('entendido secretoabierto', '2026-01-01T10:05:05Z'),
        ])
        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('parentesis.py'), ['--abrir', 'motivo', '--sesion', sid], env)
        self.assertEqual(r.returncode, 0, r.stderr)
        ruta_json = proj / 'memory' / 'parentesis.json'
        datos = json.loads(ruta_json.read_text(encoding='utf-8'))
        self.assertIsNone(datos[sid][0]['fin'], 'nunca se cierra: fin debe seguir en None')
        # `--abrir` marca el inicio a la hora ACTUAL de la prueba (muy posterior a las
        # marcas de tiempo sintéticas de 2026-01-01): se reescribe a mano para que el
        # tramo cubra justo el transcript sintético, sin tocar nada más del fichero.
        datos[sid][0]['inicio'] = '2026-01-01T10:04:30+00:00'
        ruta_json.write_text(json.dumps(datos), encoding='utf-8')

        entrada = json.dumps({'session_id': sid, 'transcript_path': str(tp), 'cwd': str(proj)})
        r2 = ay.ejecutar(ay.script('continuidad.py'), ['--cierre'], env, entrada=entrada)
        self.assertEqual(r2.returncode, 0, r2.stderr)

        copia = proj / 'memory' / 'sesiones' / f'{sid}.jsonl'
        self.assertTrue(copia.exists())
        contenido = copia.read_text(encoding='utf-8')
        self.assertNotIn('secretoabierto', contenido,
                          'un tramo abierto y nunca cerrado debe seguir ocultando todo lo posterior al --abrir')
        self.assertIn('palabraantes', contenido, 'lo dicho ANTES del --abrir no está en ningún tramo')


class FinCorruptoSigueOcultando(unittest.TestCase):
    """Fallo "roza" medido 7-sep: la otra rama fail-closed de `en_parentesis()`
    —un `fin` que no se puede parsear como fecha sigue ocultando en vez de
    dejar pasar ("mejor de más que de menos, ahí ya sabemos que el tramo
    existe")— tampoco tenía falsador. Mutando `except Exception: return True`
    a `return False` en esa rama, la suite entera también seguía en verde."""

    def test_fin_no_parseable_sigue_ocultando(self):
        proj = ay.nuevo_proyecto()
        sid = 'ses-fin-corrupto-1'
        tp = proj / f'{sid}.jsonl'
        ay.escribir_jsonl(tp, [
            ay.usuario('antes del tramo palabraantes2', '2026-01-01T10:00:00Z'),
            ay.usuario('secretocorrupto dentro del tramo con fin roto', '2026-01-01T10:05:00Z'),
            ay.asistente_texto('entendido secretocorrupto', '2026-01-01T10:05:05Z'),
        ])
        mem = proj / 'memory'
        mem.mkdir(parents=True, exist_ok=True)
        (mem / 'parentesis.json').write_text(json.dumps({
            sid: [{'inicio': '2026-01-01T10:04:00+00:00', 'fin': 'no-es-fecha', 'motivo': 'prueba'}]
        }), encoding='utf-8')

        entrada = json.dumps({'session_id': sid, 'transcript_path': str(tp), 'cwd': str(proj)})
        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('continuidad.py'), ['--cierre'], env, entrada=entrada)
        self.assertEqual(r.returncode, 0, r.stderr)

        copia = mem / 'sesiones' / f'{sid}.jsonl'
        self.assertTrue(copia.exists())
        contenido = copia.read_text(encoding='utf-8')
        self.assertNotIn('secretocorrupto', contenido, 'un fin corrupto debe seguir ocultando (fail-closed)')
        self.assertIn('palabraantes2', contenido, 'lo dicho ANTES del tramo no está oculto')


if __name__ == '__main__':
    unittest.main()
