"""`modelo.py`: el aviso `[modelo]` sale solo con prueba de un downgrade automático —el bloque o la línea de fallback
de un safeguard, o una sesión que arranca por debajo del modelo que llevaba el hilo—; lo que el usuario elige con
`/model` se permite y un cambio sin rastro no avisa. `[modelo · revisión]` lista una vez los turnos respondidos durante
la bajada y no reinyecta lo dicho dentro de un tramo de `parentesis.py` (ese aviso vuelve a la API). Con el
marcapáginas, `recorrer()` da lo mismo que la lectura entera mientras el transcript crece."""
import sys
import os
import json
import random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import unittest
import ayudas as ay

F51, F5, O5, O48, S5 = 'claude-fable-5-1', 'claude-fable-5', 'claude-opus-5', 'claude-opus-4-8', 'claude-sonnet-5'


def _h(minuto, segundo=0):
    return f'2026-01-01T10:{minuto:02d}:{segundo:02d}Z'


class _Texto(unittest.TestCase):
    def texto(self, lineas, proj=None, veces=1):
        """Salida de `modelo.py <transcript>` (la misma `texto()` que usa `--despertar`, sin que nadie se trague sus
        excepciones), `veces` seguidas sobre el mismo proyecto."""
        proj = proj or ay.nuevo_proyecto()
        tp = proj / 'ses.jsonl'
        ay.escribir_jsonl(tp, lineas)
        env = ay.entorno(proj, ABYSS_SIN_RED='1')
        salidas = []
        for _ in range(veces):
            r = ay.ejecutar(ay.script('modelo.py'), [str(tp)], env)
            self.assertEqual(r.returncode, 0, r.stderr)
            salidas.append(r.stdout.strip())
        return salidas[0] if veces == 1 else salidas


class ElAvisoEsSoloParaElDowngradeAutomatico(_Texto):
    def test_hilo_que_empieza_en_opus_no_avisa(self):
        self.assertEqual(self.texto([ay.usuario('hola', _h(1)), ay.asistente_texto('hola', _h(1, 5), modelo=O5)]), '')

    def test_cambio_sin_rastro_no_avisa(self):
        self.assertEqual(self.texto([
            ay.usuario('uno', _h(1)), ay.asistente_texto('a', _h(1, 5), modelo=F51),
            ay.usuario('dos', _h(2)), ay.asistente_texto('b', _h(2, 5), modelo=O48),
        ]), '')

    def test_safeguard_avisa_y_propone_volver_al_modelo_de_origen(self):
        salida = self.texto([
            ay.usuario('uno', _h(1)), ay.asistente_texto('a', _h(1, 5), modelo=F51),
            ay.usuario('dos', _h(2)), ay.asistente_fallback('b', _h(2, 5), de=F51, a=O48, request_id='r1'),
            ay.sistema_fallback(_h(2, 6), F51, O48, request_id='r1'),
        ])
        self.assertIn('[modelo] downgrade automático', salida)
        self.assertIn('safeguard', salida)
        self.assertIn(f'/model {F51}` para regresar', salida)
        self.assertIn(f'/model {O48}` y dejo de avisar', salida)

    def test_safeguard_en_el_primer_turno_tambien_avisa(self):
        salida = self.texto([ay.usuario('uno', _h(1)), ay.asistente_fallback('a', _h(1, 5), de=F5, a=O48)])
        self.assertIn(f'/model {F5}` para regresar', salida)

    def test_la_referencia_es_el_modelo_de_origen_y_no_el_ultimo_model(self):
        salida = self.texto([
            ay.model_elegido(O5, _h(0)),
            ay.usuario('uno', _h(1)), ay.asistente_texto('a', _h(1, 5), modelo=O5),
            ay.usuario('dos', _h(2)), ay.asistente_fallback('b', _h(2, 5), de=F5, a=O48),
        ])
        self.assertIn(f'/model {F5}` para regresar', salida)

    def test_la_linea_system_sin_bloque_tambien_avisa(self):
        salida = self.texto([
            ay.usuario('uno', _h(1)), ay.asistente_texto('a', _h(1, 5), modelo=F5),
            ay.usuario('dos', _h(2)), ay.asistente_texto('b', _h(2, 5), modelo=O48),
            ay.sistema_fallback(_h(2, 7), F5, O48),
        ])
        self.assertIn(f'/model {F5}` para regresar', salida)

    def test_model_posterior_permite_quedarse_con_el_de_reserva(self):
        self.assertEqual(self.texto([
            ay.usuario('uno', _h(1)), ay.asistente_fallback('a', _h(1, 5), de=F51, a=O48),
            ay.model_elegido(O48, _h(1, 30)),
            ay.usuario('dos', _h(2)), ay.asistente_texto('b', _h(2, 5), modelo=O48),
        ]), '')

    def test_bajada_manual_sin_fallback_no_avisa(self):
        self.assertEqual(self.texto([
            ay.usuario('uno', _h(1)), ay.asistente_texto('a', _h(1, 5), modelo=F51),
            ay.model_elegido(S5, _h(1, 30)),
            ay.usuario('dos', _h(2)), ay.asistente_texto('b', _h(2, 5), modelo=S5),
        ]), '')

    def test_model_escrito_al_acabar_el_turno_con_hora_anterior_no_apaga_el_aviso(self):
        salida = self.texto([
            ay.usuario('uno', _h(1)), ay.asistente_texto('a', _h(1, 5), modelo=O5),
            ay.asistente_fallback('b', _h(1, 20), de=F51, a=O48),
            ay.model_elegido(F51, _h(1, 10)),
        ])
        self.assertIn(f'/model {F51}` para regresar', salida)

    def test_la_linea_system_del_mismo_request_no_reabre_la_bajada(self):
        self.assertEqual(self.texto([
            ay.usuario('uno', _h(1)), ay.asistente_fallback('a', _h(1, 5), de=F51, a=O48, request_id='r1'),
            ay.model_elegido(O48, _h(1, 6)),
            ay.sistema_fallback(_h(1, 7), F51, O48, request_id='r1'),
        ]), '')

    def test_otro_modelo_que_responde_cierra_la_bajada(self):
        salida = self.texto([
            ay.usuario('uno', _h(1)), ay.asistente_fallback('a', _h(1, 5), de=F51, a=O48),
            ay.usuario('dos', _h(2)), ay.asistente_texto('b', _h(2, 5), modelo=F51),
        ])
        self.assertNotIn('[modelo] downgrade', salida)

    def test_un_safeguard_tras_volver_avisa_otra_vez(self):
        salida = self.texto([
            ay.usuario('uno', _h(1)), ay.asistente_fallback('a', _h(1, 5), de=F51, a=O48),
            ay.model_elegido(F51, _h(1, 30)),
            ay.usuario('dos', _h(2)), ay.asistente_fallback('b', _h(2, 5), de=F51, a=O48),
        ])
        self.assertIn('[modelo] downgrade', salida)

    def test_un_prompt_que_pega_un_comando_model_no_es_una_eleccion(self):
        self.assertIn('[modelo] downgrade', self.texto([
            ay.usuario('uno', _h(1)), ay.asistente_fallback('a', _h(1, 5), de=F51, a=O48),
            ay.usuario(f'mira lo que sale: <command-name>/model</command-name><command-args>{O48}</command-args>', _h(2)),
        ]))

    def test_synthetic_no_es_un_modelo(self):
        self.assertEqual(self.texto([
            ay.usuario('uno', _h(1)), ay.asistente_texto('a', _h(1, 5), modelo=F51),
            ay.usuario('dos', _h(2)), ay.asistente_texto('API Error', _h(2, 5), modelo='<synthetic>'),
        ]), '')
        self.assertIn('[modelo] downgrade', self.texto([
            ay.usuario('uno', _h(1)), ay.asistente_fallback('a', _h(1, 5), de=F51, a=O48),
            ay.usuario('dos', _h(2)), ay.asistente_texto('API Error', _h(2, 5), modelo='<synthetic>'),
        ]))


class ElArranqueQueBajaDelModeloDelHilo(_Texto):
    def test_reanudar_por_debajo_del_modelo_del_hilo_avisa(self):
        salida = self.texto([
            ay.usuario('uno', _h(1)), ay.asistente_texto('a', _h(1, 5), modelo=F51),
            ay.marca_sesion(_h(5)),
            ay.usuario('dos', _h(6)), ay.asistente_texto('b', _h(6, 5), modelo=O5),
        ])
        self.assertIn('[modelo] downgrade automático', salida)
        self.assertIn(f'/model {F51}` para regresar', salida)

    def test_con_model_tras_reanudar_no_avisa(self):
        self.assertEqual(self.texto([
            ay.usuario('uno', _h(1)), ay.asistente_texto('a', _h(1, 5), modelo=F51),
            ay.marca_sesion(_h(5)), ay.model_elegido(O5, _h(5, 30)),
            ay.usuario('dos', _h(6)), ay.asistente_texto('b', _h(6, 5), modelo=O5),
        ]), '')

    def test_reanudar_por_encima_no_avisa(self):
        self.assertEqual(self.texto([
            ay.usuario('uno', _h(1)), ay.asistente_texto('a', _h(1, 5), modelo=S5),
            ay.marca_sesion(_h(5)),
            ay.usuario('dos', _h(6)), ay.asistente_texto('b', _h(6, 5), modelo=O5),
        ]), '')

    def test_la_generacion_cuenta_dentro_de_la_familia(self):
        self.assertIn(f'/model {O5}` para regresar', self.texto([
            ay.usuario('uno', _h(1)), ay.asistente_texto('a', _h(1, 5), modelo=O5),
            ay.marca_sesion(_h(5), fuente='startup'),
            ay.usuario('dos', _h(6)), ay.asistente_texto('b', _h(6, 5), modelo=O48),
        ]))
        self.assertEqual(self.texto([
            ay.usuario('uno', _h(1)), ay.asistente_texto('a', _h(1, 5), modelo=O48),
            ay.marca_sesion(_h(5)),
            ay.usuario('dos', _h(6)), ay.asistente_texto('b', _h(6, 5), modelo=O5),
        ]), '')

    def test_la_marca_con_error_no_bloqueante_tambien_cuenta(self):
        self.assertIn('[modelo] downgrade', self.texto([
            ay.usuario('uno', _h(1)), ay.asistente_texto('a', _h(1, 5), modelo=F51),
            ay.marca_sesion(_h(5), tipo='hook_non_blocking_error'),
            ay.usuario('dos', _h(6)), ay.asistente_texto('b', _h(6, 5), modelo=O5),
        ]))

    def test_compactar_no_es_un_arranque(self):
        self.assertEqual(self.texto([
            ay.usuario('uno', _h(1)), ay.asistente_texto('a', _h(1, 5), modelo=F51),
            ay.marca_sesion(_h(5), fuente='compact'),
            ay.usuario('dos', _h(6)), ay.asistente_texto('b', _h(6, 5), modelo=O5),
        ]), '')

    def test_reanudar_tras_un_safeguard_compara_con_el_modelo_de_origen(self):
        self.assertIn(f'/model {F51}` para regresar', self.texto([
            ay.usuario('uno', _h(1)), ay.asistente_fallback('a', _h(1, 5), de=F51, a=O48),
            ay.marca_sesion(_h(5)),
            ay.usuario('dos', _h(6)), ay.asistente_texto('b', _h(6, 5), modelo=O5),
        ]))


class LaRevisionListaUnaVezLoRespondidoDuranteLaBajada(_Texto):
    LINEAS = [
        ay.usuario('antes de la bajada', _h(1)), ay.asistente_texto('dicho por fable', _h(1, 5), modelo=F51),
        ay.usuario('primera en la bajada', _h(2)), ay.asistente_fallback('dicho por opus uno', _h(2, 5), de=F51, a=O48),
        ay.usuario('segunda en la bajada', _h(3)), ay.asistente_texto('dicho por opus dos', _h(3, 5), modelo=O48),
        ay.model_elegido(F51, _h(3, 30)),
        ay.usuario('ya de vuelta', _h(4)), ay.asistente_texto('dicho por fable otra vez', _h(4, 5), modelo=F51),
    ]

    def test_una_vez_y_solo_los_turnos_de_la_bajada(self):
        primera, segunda = self.texto(self.LINEAS, veces=2)
        self.assertIn('[modelo · revisión]', primera)
        self.assertIn('en 2 turno(s)', primera)
        self.assertIn('primera en la bajada', primera)
        self.assertIn('dicho por opus dos', primera)
        self.assertNotIn('antes de la bajada', primera)
        self.assertNotIn('ya de vuelta', primera)
        self.assertEqual(segunda, '')

    def test_llega_en_el_prompt_que_sigue_al_model_de_vuelta(self):
        salida = self.texto(self.LINEAS[:7])
        self.assertIn(f'[modelo · revisión] Terminó el downgrade automático: ahora responde {F51}', salida)
        self.assertIn('en 2 turno(s)', salida, 'el turno aún sin cerrar también se respondió durante la bajada')

    def test_una_marca_vieja_con_un_numero_no_se_salta_turnos(self):
        proj = ay.nuevo_proyecto()
        (proj / 'memory' / '.modelo_revisado').mkdir(parents=True)
        (proj / 'memory' / '.modelo_revisado' / 'ses').write_text('55', encoding='utf-8')
        self.assertIn('en 2 turno(s)', self.texto(self.LINEAS, proj=proj))

    def test_un_turno_que_cae_y_vuelve_al_de_origen_se_revisa_con_lo_que_dijo_la_bajada(self):
        proj = ay.nuevo_proyecto()
        salida = self.texto([
            ay.usuario('uno', _h(1)),
            ay.asistente_texto('dicho por fable antes de caer', _h(1, 2), modelo=F51),
            ay.asistente_fallback('dicho por opus', _h(1, 5), de=F51, a=O48),
            ay.asistente_texto('dicho por fable', _h(1, 40), modelo=F51),
            ay.model_elegido(F51, _h(1, 20)),  # hecho a mitad de turno, escrito al acabarlo
        ], proj=proj)
        self.assertIn(f'ahora responde {F51}', salida)
        self.assertIn(f'{O48} · usuario: «uno» → «dicho por opus»', salida)
        tp = proj / 'ses.jsonl'
        with open(tp, 'a', encoding='utf-8') as fh:
            for d in (ay.model_elegido(O5, _h(2)), ay.usuario('dos', _h(3)), ay.asistente_texto('b', _h(3, 5), modelo=O5)):
                fh.write(json.dumps(d, ensure_ascii=False) + '\n')
        r = ay.ejecutar(ay.script('modelo.py'), [str(tp)], ay.entorno(proj, ABYSS_SIN_RED='1'))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), '', 'tras bajar a mano no queda nada pendiente que salga del revés')

    def test_estado_la_ensena_sin_gastarla(self):
        proj = ay.nuevo_proyecto()
        tp = proj / 'ses.jsonl'
        ay.escribir_jsonl(tp, self.LINEAS)
        r = ay.ejecutar(ay.script('modelo.py'), ['--estado', str(tp)], ay.entorno(proj, ABYSS_SIN_RED='1'))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('[modelo · revisión]', r.stdout)
        self.assertIn('[modelo · revisión]', self.texto(self.LINEAS, proj=proj), 'la de --despertar sigue pendiente')

    def test_quedarse_con_el_de_reserva_no_dispara_revision(self):
        self.assertEqual(self.texto(self.LINEAS[:6] + [
            ay.model_elegido(O48, _h(3, 30)),
            ay.usuario('sigo con opus', _h(4)), ay.asistente_texto('vale', _h(4, 5), modelo=O48),
        ]), '')


def _transcript_con_downgrade(tp):
    ay.escribir_jsonl(tp, [
        ay.usuario('esto es secretisimo rododendro y no debe volver a leerse jamas', '2026-01-01T10:05:00Z'),
        ay.asistente_fallback('respondo con el dato secretisimo 987654 y la ruta C:/secreto/rododendro.txt',
                              '2026-01-01T10:05:05Z', de=F51, a=O48),
        ay.model_elegido(F51, '2026-01-01T10:05:40Z'),
        ay.usuario('sigamos charlando', '2026-01-01T10:06:00Z'),
        ay.asistente_texto('vale, ya vuelvo a fable', '2026-01-01T10:06:05Z', modelo=F51),
    ])


class ParentesisNoViajaAlAvisoDeRevision(unittest.TestCase):
    def _despertar(self, proj, sid, tp):
        env = ay.entorno(proj, ABYSS_SIN_RED='1')
        entrada = json.dumps({'session_id': sid, 'transcript_path': str(tp), 'cwd': str(proj), 'prompt': 'sigamos'})
        r = ay.ejecutar(ay.script('continuidad.py'), ['--despertar'], env, entrada=entrada)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def test_sin_tramo_el_turno_de_la_bajada_si_se_reinyecta(self):
        """Control: sin ningún paréntesis marcado, el mecanismo de revisión sigue
        funcionando como siempre — el filtro no apaga la función en general."""
        proj = ay.nuevo_proyecto()
        sid = 'ses-modelo-control'
        tp = proj / f'{sid}.jsonl'
        _transcript_con_downgrade(tp)
        salida = self._despertar(proj, sid, tp)
        self.assertIn('secretisimo', salida, 'sin tramo, el aviso de revisión sí debe citar el turno de la bajada')
        self.assertIn('987654', salida)

    def test_con_tramo_el_turno_de_la_bajada_no_se_reinyecta(self):
        proj = ay.nuevo_proyecto()
        sid = 'ses-modelo-tramo'
        tp = proj / f'{sid}.jsonl'
        _transcript_con_downgrade(tp)
        mem = proj / 'memory'
        mem.mkdir(parents=True, exist_ok=True)
        # el tramo cubre EXACTAMENTE el turno respondido durante la bajada (10:05:00 a 10:05:05) y se cierra antes
        # del `/model` de vuelta (10:05:40) y del turno siguiente (10:06:00).
        (mem / 'parentesis.json').write_text(json.dumps({
            sid: [{'inicio': '2026-01-01T10:04:00+00:00', 'fin': '2026-01-01T10:05:30+00:00', 'motivo': 'prueba'}]
        }), encoding='utf-8')
        salida = self._despertar(proj, sid, tp)
        self.assertNotIn('secretisimo', salida, 'nada dicho DENTRO del tramo debe volver a viajar al prompt')
        self.assertNotIn('987654', salida)
        self.assertNotIn('rododendro', salida)
        # con el único turno de la bajada oculto, no queda nada que revisar: sin aviso
        self.assertNotIn('[modelo', salida)

    def test_tramo_abierto_sin_cerrar_tambien_oculta(self):
        """Un tramo `--abrir` sin `--cerrar` (`fin: None`) se trata como abierto
        hasta ahora mismo (`parentesis.en_parentesis()`): nada dicho DESPUÉS del
        `--abrir` y nunca cerrado debe reinyectarse."""
        proj = ay.nuevo_proyecto()
        sid = 'ses-modelo-abierto'
        tp = proj / f'{sid}.jsonl'
        _transcript_con_downgrade(tp)
        mem = proj / 'memory'
        mem.mkdir(parents=True, exist_ok=True)
        (mem / 'parentesis.json').write_text(json.dumps({
            sid: [{'inicio': '2026-01-01T10:04:00+00:00', 'fin': None, 'motivo': 'prueba'}]
        }), encoding='utf-8')
        salida = self._despertar(proj, sid, tp)
        self.assertNotIn('secretisimo', salida)
        self.assertNotIn('vale, ya vuelvo a fable', salida)

    def test_la_respuesta_dicha_dentro_del_tramo_no_viaja_aunque_el_prompt_quede_fuera(self):
        proj = ay.nuevo_proyecto()
        tp = proj / 'ses.jsonl'
        _transcript_con_downgrade(tp)
        (proj / 'memory').mkdir(parents=True, exist_ok=True)
        (proj / 'memory' / 'parentesis.json').write_text(json.dumps({
            'ses': [{'inicio': '2026-01-01T10:05:02+00:00', 'fin': '2026-01-01T10:05:10+00:00', 'motivo': 'prueba'}]}),
            encoding='utf-8')
        r = ay.ejecutar(ay.script('modelo.py'), [str(tp)], ay.entorno(proj, ABYSS_SIN_RED='1'))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('[modelo · revisión]', r.stdout, 'el turno se listó: su prompt quedó fuera del tramo')
        self.assertNotIn('987654', r.stdout)

    def test_un_model_dicho_dentro_del_tramo_si_cuenta(self):
        """Lo que no viaja es el texto; el `/model` no lleva texto del usuario y decide igual dentro del tramo."""
        proj = ay.nuevo_proyecto()
        tp = proj / 'ses.jsonl'
        ay.escribir_jsonl(tp, [
            ay.usuario('uno', _h(1)), ay.asistente_fallback('a', _h(1, 5), de=F51, a=O48),
            ay.model_elegido(O48, _h(1, 30)),
            ay.usuario('dos', _h(2)), ay.asistente_texto('b', _h(2, 5), modelo=O48),
        ])
        (proj / 'memory').mkdir(parents=True, exist_ok=True)
        (proj / 'memory' / 'parentesis.json').write_text(json.dumps({
            'ses': [{'inicio': _h(1, 20), 'fin': _h(1, 40), 'motivo': 'prueba'}]}), encoding='utf-8')
        r = ay.ejecutar(ay.script('modelo.py'), [str(tp)], ay.entorno(proj, ABYSS_SIN_RED='1'))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), '')


CRECER = r'''
import sys, os, json
sys.path.insert(0, sys.argv[1])
tp, pasos = sys.argv[2], json.load(open(sys.argv[3], encoding='utf-8'))
import marcapaginas as MP
import modelo as M
leidas = [0]
original = MP.Lectura.lineas_nuevas
def contadas(self):
    for x in original(self):
        leidas[0] += 1
        yield x
MP.Lectura.lineas_nuevas = contadas
fallos = []
for i, paso in enumerate(pasos):
    if paso.get('parentesis') is not None:
        with open(os.path.join(os.environ['ABYSS_PROYECTO'], 'memory', 'parentesis.json'), 'w', encoding='utf-8') as fh:
            json.dump({'ses': paso['parentesis']}, fh)
    with open(tp, 'ab') as fh:
        fh.write(paso['bytes'].encode('utf-8', 'surrogatepass'))
    e = M.recorrer(tp)
    PZ, tramos = M._tramos_de('ses', tp)
    if e != M._leer_entero(tp, PZ, tramos):
        fallos.append(i)
print(json.dumps({'fallos': fallos, 'leidas': leidas[0]}))
'''


def _pasos(semilla, n=80):
    """Un transcript que crece línea a línea con todo lo que `_paso()` distingue, cortes CRLF y `\\r` suelto, líneas
    rotas, y un tramo de paréntesis que aparece a mitad (obliga a releer desde cero)."""
    rnd = random.Random(semilla)
    modelos = [F51, F5, O5, O48, S5]
    reloj = [0]

    def hora(atras=0):
        reloj[0] += rnd.randint(1, 30)
        s = reloj[0] - atras
        return f'2026-01-01T{10 + s // 3600:02d}:{s // 60 % 60:02d}:{s % 60:02d}Z'

    def fabricar(i):
        k = rnd.randrange(14)
        mo = rnd.choice(modelos)
        if k == 0:
            return ay.usuario(f'pregunta {i} con Σ y  espacios', hora())
        if k == 1:
            return ay.asistente_texto(f'respuesta {i}', hora(), modelo=mo)
        if k == 2:
            return ay.asistente_fallback(f'reserva {i}', hora(), de=rnd.choice(modelos), a=mo, request_id=f'r{i % 5}')
        if k == 3:
            return ay.sistema_fallback(hora(), rnd.choice(modelos), mo, request_id=rnd.choice([None, f'r{i % 5}']))
        if k == 4:
            return ay.model_elegido(rnd.choice(modelos + ['opus', 'default']), hora(atras=rnd.choice([0, 0, 90])))
        if k == 5:
            return ay.marca_sesion(hora(), fuente=rnd.choice(['startup', 'resume', 'compact']),
                                   tipo=rnd.choice(['hook_success', 'hook_non_blocking_error']))
        if k == 6:
            return ay.asistente_texto('API Error', hora(), modelo='<synthetic>')
        if k == 7:
            d = ay.asistente_fallback(f'lateral {i}', hora(), de=F51, a=S5)
            d['isSidechain'] = True
            return d
        if k == 8:
            d = ay.usuario(f'meta {i}', hora())
            d['isMeta'] = True
            return d
        if k == 9:
            return [1, 2]
        if k == 10:
            return '{"type": "user", "mess'
        if k == 11:
            return {'type': 'assistant', 'message': 'no es un objeto', 'timestamp': hora()}
        if k == 12:
            return ay.usuario_tool_result(f'resultado {i}', hora())
        return {'type': 'attachment', 'attachment': ['no', 'es', 'dict'], 'timestamp': hora()}

    pasos = []
    tramo_en = rnd.randrange(n // 3, 2 * n // 3)
    for i in range(n):
        d = fabricar(i)
        texto = d if isinstance(d, str) else json.dumps(d, ensure_ascii=False)
        fin = rnd.choice(['\n', '\n', '\n', '\r\n'])
        if rnd.random() < 0.1:
            otro = fabricar(i)
            texto += '\r' + (otro if isinstance(otro, str) else json.dumps(otro, ensure_ascii=False))
        paso = {'bytes': texto + fin}
        if i == tramo_en:
            paso['parentesis'] = [{'inicio': '2026-01-01T10:05:00Z', 'fin': rnd.choice([None, '2026-01-01T10:12:00Z'])}]
        pasos.append(paso)
    return pasos


class ElMarcapaginasDaLoMismoQueLeerEntero(unittest.TestCase):
    def test_en_cada_corte_mientras_crece(self):
        for semilla in range(4):
            with self.subTest(semilla=semilla):
                proj = ay.nuevo_proyecto()
                (proj / 'memory').mkdir(parents=True, exist_ok=True)
                tp = proj / 'ses.jsonl'
                tp.write_bytes(b'')
                pasos = _pasos(semilla)
                ruta_pasos = proj / '_pasos.json'
                ruta_pasos.write_text(json.dumps(pasos), encoding='utf-8')
                guion = proj / '_crecer.py'
                guion.write_text(CRECER, encoding='utf-8')
                r = ay.ejecutar(guion, [ay.PKG, tp, ruta_pasos], ay.entorno(proj, ABYSS_SIN_RED='1'), timeout=120)
                self.assertEqual(r.returncode, 0, r.stderr)
                out = json.loads(r.stdout.strip().splitlines()[-1])
                self.assertEqual(out['fallos'], [], f'el estado incremental difiere de la lectura entera en {out}')
                self.assertTrue((proj / 'memory' / '.marcapaginas' / 'ses' / 'modelo.json').is_file())

    def test_solo_se_leen_las_lineas_nuevas(self):
        proj = ay.nuevo_proyecto()
        (proj / 'memory').mkdir(parents=True, exist_ok=True)
        tp = proj / 'ses.jsonl'
        tp.write_bytes(b'')
        lineas = [ay.usuario('uno', _h(1)), ay.asistente_fallback('a', _h(1, 5), de=F51, a=O48),
                  ay.usuario('dos', _h(2)), ay.asistente_texto('b', _h(2, 5), modelo=O48)]
        pasos = [{'bytes': ''.join(json.dumps(d) + '\n' for d in lineas[:3])},
                 {'bytes': json.dumps(lineas[3]) + '\n'}]
        ruta_pasos = proj / '_pasos.json'
        ruta_pasos.write_text(json.dumps(pasos), encoding='utf-8')
        guion = proj / '_crecer.py'
        guion.write_text(CRECER, encoding='utf-8')
        r = ay.ejecutar(guion, [ay.PKG, tp, ruta_pasos], ay.entorno(proj, ABYSS_SIN_RED='1'), timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout.strip().splitlines()[-1])
        self.assertEqual(out, {'fallos': [], 'leidas': 4}, 'tres líneas en la primera lectura y una en la segunda')


if __name__ == '__main__':
    unittest.main()
