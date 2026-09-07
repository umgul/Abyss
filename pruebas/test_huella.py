"""`huella.py` (ESPECIFICACION_TANDA2.md T2.2): todo lo que un hilo toca fuera de
su carpeta. Las funciones puras (`diferencias`, `debe_fotografiar`,
`parece_persistente`, `agrupar_por_raiz`, `informe`, `resumen_stop`, `limpiar`)
se prueban importando el módulo DIRECTAMENTE — igual que `cuerpo.py` (T2.3):
`huella.py` no toca `rutas.resolver()` ni stdin al importarse, así que
`foto()` se puede monkeypatchear con `unittest.mock.patch.object` sin lanzar
ningún proceso real. Los tres ganchos (`--arranque`/`--herramienta`/`--fin`) y
el ciclo de vida real de un proceso (arrancarlo de verdad, verlo en
`--informe`, matarlo con `--limpiar --si`) se prueban por subproceso, como el
resto de `abyss/`.
"""
import sys
import os
import json
import time
import subprocess
import tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import unittest
from unittest import mock
import ayudas as ay

sys.path.insert(0, str(ay.RAIZ))
from abyss import huella  # noqa: E402


# ---------- funciones puras: importadas directamente, sin subproceso ----------

class HeuristicaDeCoste(unittest.TestCase):
    def test_menos_de_tres_medidas_siempre_fotografia(self):
        self.assertTrue(huella.debe_fotografiar([], 'ls -la'))
        self.assertTrue(huella.debe_fotografiar([5000], 'ls -la'))

    def test_mediana_baja_siempre_fotografia(self):
        self.assertTrue(huella.debe_fotografiar([100, 200, 300], 'ls -la'))

    def test_mediana_alta_solo_si_parece_persistente(self):
        costes_lentos = [2000, 2000, 2000]
        self.assertFalse(huella.debe_fotografiar(costes_lentos, 'ls -la'))
        self.assertTrue(huella.debe_fotografiar(costes_lentos, 'python server.py &'))
        self.assertTrue(huella.debe_fotografiar(costes_lentos, 'node index.js'))
        self.assertTrue(huella.debe_fotografiar(costes_lentos, 'npm run serve'))
        self.assertTrue(huella.debe_fotografiar(costes_lentos, 'nohup ./cosa.sh'))
        self.assertTrue(huella.debe_fotografiar(costes_lentos, 'echo hola; sleep 5 &'))

    def test_costes_apuntar_recorta_ventana(self):
        proj = ay.nuevo_proyecto()
        mem = str(proj / 'memory')
        for i in range(huella.VENTANA_COSTES + 5):
            huella.costes_apuntar(mem, i)
        datos = huella.costes_leer(mem)
        self.assertEqual(len(datos), huella.VENTANA_COSTES)
        self.assertEqual(datos[-1], huella.VENTANA_COSTES + 4)


class Diferencias(unittest.TestCase):
    def test_detecta_puerto_y_proceso_nuevos(self):
        anterior = {'puertos': {'80': '1'}, 'procesos': {'1': {'nombre': 'a', 'inicio': 't1'}}}
        actual = {'puertos': {'80': '1', '443': '2'},
                  'procesos': {'1': {'nombre': 'a', 'inicio': 't1'}, '2': {'nombre': 'b', 'inicio': 't2'}}}
        diffs = huella.diferencias(anterior, actual)
        self.assertIn(('puerto_nuevo', {'puerto': '443', 'pid': '2'}), diffs)
        self.assertIn(('proceso_nuevo', {'pid': '2', 'nombre': 'b', 'inicio': 't2'}), diffs)
        self.assertEqual(len(diffs), 2)

    def test_pid_reciclado_con_otra_hora_cuenta_como_nuevo(self):
        """Mismo pid, hora de arranque distinta = proceso distinto de verdad."""
        anterior = {'puertos': {}, 'procesos': {'9': {'nombre': 'viejo', 'inicio': 't1'}}}
        actual = {'puertos': {}, 'procesos': {'9': {'nombre': 'nuevo', 'inicio': 't2'}}}
        diffs = huella.diferencias(anterior, actual)
        self.assertEqual(diffs, [('proceso_nuevo', {'pid': '9', 'nombre': 'nuevo', 'inicio': 't2'})])

    def test_sin_dato_en_un_lado_no_compara(self):
        anterior = {'puertos': None, 'procesos': {'1': {'nombre': 'a', 'inicio': 't1'}}}
        actual = {'puertos': {'80': '1'}, 'procesos': {'1': {'nombre': 'a', 'inicio': 't1'}}}
        self.assertEqual(huella.diferencias(anterior, actual), [])

    def test_nada_nuevo_no_reporta_nada(self):
        foto = {'puertos': {'80': '1'}, 'procesos': {'1': {'nombre': 'a', 'inicio': 't1'}}}
        self.assertEqual(huella.diferencias(foto, dict(foto)), [])


@unittest.skipUnless(os.name == 'nt', 'la exclusión de PIDs propios en foto() solo se ejercita aquí en Windows')
class FotoExcluyeProcesosPropios(unittest.TestCase):
    """T2.2, fallo medido 7-sep: sin esto, `foto()` cazaba su propio árbol de
    procesos (el `python` de este mismo `huella.py`, el shell que lo invocó, y
    el `powershell.exe` que la propia foto acaba de lanzar) como si fueran
    procesos nuevos de la sesión."""

    def test_descarta_self_padre_y_powershell_de_la_propia_medida(self):
        propio = str(os.getpid())
        padre = str(os.getppid())
        pid_ps_falso = 999999
        procesos_crudos = {
            propio: {'nombre': 'python', 'inicio': 'x'},
            padre: {'nombre': 'bash', 'inicio': 'y'},
            str(pid_ps_falso): {'nombre': 'powershell', 'inicio': 'z'},
            '424242': {'nombre': 'otro_proceso_real', 'inicio': 'w'},
        }
        with mock.patch.object(huella, 'leer_puertos_y_procesos_windows',
                                return_value=({}, procesos_crudos, pid_ps_falso)):
            foto_dict, _coste = huella.foto()
        self.assertNotIn(propio, foto_dict['procesos'], 'el propio intérprete no debe contar como proceso_nuevo')
        self.assertNotIn(padre, foto_dict['procesos'], 'quien lanzó el gancho no debe contar como proceso_nuevo')
        self.assertNotIn(str(pid_ps_falso), foto_dict['procesos'], 'el powershell que TOMA la foto no debe verse a sí mismo')
        self.assertIn('424242', foto_dict['procesos'], 'un proceso real y ajeno sigue contando')


class AgruparPorRaiz(unittest.TestCase):
    def test_agrupa_por_los_dos_primeros_segmentos(self):
        grupos = huella.agrupar_por_raiz([
            'C:\\Users\\x\\a.txt', 'C:\\Users\\y\\b.txt', 'C:\\Temp\\c.txt',
        ])
        self.assertEqual(set(grupos), {'C:\\Users', 'C:\\Temp'})
        self.assertEqual(len(grupos['C:\\Users']), 2)
        self.assertEqual(len(grupos['C:\\Temp']), 1)


class InformeConFotoSimulada(unittest.TestCase):
    """`informe()` con `foto_actual` inyectado: sin lanzar PowerShell ni tocar
    procesos reales."""

    def _preparar(self, mem, sid, eventos):
        for e in eventos:
            huella.registrar(mem, sid, e)

    def test_proceso_con_hora_distinta_no_cuenta_como_vivo(self):
        proj = ay.nuevo_proyecto()
        mem = str(proj / 'memory')
        sid = 'sid-1'
        self._preparar(mem, sid, [
            {'ts': 't', 'tipo': 'proceso_nuevo', 'pid': '123', 'nombre': 'python', 'inicio': '2026-01-01T10:00:00'},
        ])
        # el pid 123 SIGUE existiendo ahora, pero con OTRA hora de arranque: no es el mismo proceso
        foto_actual = {'puertos': {}, 'procesos': {'123': {'nombre': 'otra_cosa', 'inicio': '2026-02-02T00:00:00'}}}
        inf = huella.informe(mem, sid, foto_actual=foto_actual)
        self.assertEqual(inf['procesos_vivos'], [])

    def test_proceso_con_misma_hora_cuenta_como_vivo(self):
        proj = ay.nuevo_proyecto()
        mem = str(proj / 'memory')
        sid = 'sid-2'
        self._preparar(mem, sid, [
            {'ts': 't', 'tipo': 'proceso_nuevo', 'pid': '123', 'nombre': 'python', 'inicio': '2026-01-01T10:00:00'},
        ])
        foto_actual = {'puertos': {}, 'procesos': {'123': {'nombre': 'python', 'inicio': '2026-01-01T10:00:00'}}}
        inf = huella.informe(mem, sid, foto_actual=foto_actual)
        self.assertEqual(len(inf['procesos_vivos']), 1)
        self.assertEqual(inf['procesos_vivos'][0]['pid'], '123')

    def test_sin_dato_no_finge_lista_vacia(self):
        proj = ay.nuevo_proyecto()
        mem = str(proj / 'memory')
        sid = 'sid-3'
        inf = huella.informe(mem, sid, foto_actual={'puertos': None, 'procesos': None})
        self.assertTrue(inf['sin_dato_puertos'])
        self.assertTrue(inf['sin_dato_procesos'])

    def test_ficheros_escritos_agrupados(self):
        proj = ay.nuevo_proyecto()
        mem = str(proj / 'memory')
        sid = 'sid-4'
        self._preparar(mem, sid, [
            {'ts': 't', 'tipo': 'escrito', 'ruta': 'C:\\Users\\x\\a.txt'},
            {'ts': 't', 'tipo': 'escrito', 'ruta': 'C:\\Users\\x\\b.txt'},
        ])
        inf = huella.informe(mem, sid, foto_actual={'puertos': {}, 'procesos': {}})
        self.assertEqual(len(inf['ficheros_escritos']['C:\\Users']), 2)


class ResumenStop(unittest.TestCase):
    """`resumen_stop()` ya NO usa el último snapshot guardado — lo compara con
    una foto FRESCA (`informe()` sin `foto_actual`), así que aquí `foto()` se
    monkeypatchea para simular esa foto sin lanzar PowerShell de verdad (T2.2,
    fallo "el snapshot rancio hace tautológico cualquier proceso_nuevo": ver
    docstring de `resumen_stop()`)."""

    def test_sin_snapshot_calla(self):
        proj = ay.nuevo_proyecto()
        mem = str(proj / 'memory')
        self.assertEqual(huella.resumen_stop(mem, 'sid-sin-snapshot'), '')

    def test_sin_ningun_evento_registrado_ni_fotografia(self):
        """Sin `proceso_nuevo`/`puerto_nuevo` en el registro, ni se paga la foto:
        si `foto()` se llamara igualmente, este mock reventaría la prueba."""
        proj = ay.nuevo_proyecto()
        mem = str(proj / 'memory')
        sid = 'sid-5'
        huella.snapshot_escribir(mem, sid, {'puertos': {}, 'procesos': {}})
        with mock.patch.object(huella, 'foto', side_effect=AssertionError('no debía fotografiar')):
            self.assertEqual(huella.resumen_stop(mem, sid), '')

    def test_con_algo_registrado_pero_ya_muerto_calla(self):
        """Fallo T2.2 medido 7-sep: con el snapshot rancio, un proceso_nuevo
        detectado en la ÚLTIMA foto salía SIEMPRE "vivo" en --fin porque esa
        foto ES la misma en la que se cazó. Con una foto fresca que ya no lo ve,
        --fin debe callar — es justo lo que antes NO pasaba."""
        proj = ay.nuevo_proyecto()
        mem = str(proj / 'memory')
        sid = 'sid-6b'
        huella.registrar(mem, sid, {'ts': 't', 'tipo': 'proceso_nuevo', 'pid': '1', 'nombre': 'x', 'inicio': 'h1'})
        huella.snapshot_escribir(mem, sid, {'puertos': {}, 'procesos': {'1': {'nombre': 'x', 'inicio': 'h1'}}})
        # foto FRESCA: el proceso '1' ya no existe (murió entre medias)
        with mock.patch.object(huella, 'foto', return_value=({'puertos': {}, 'procesos': {}}, 5)):
            self.assertEqual(huella.resumen_stop(mem, sid), '')

    def test_con_algo_vivo_de_verdad_avisa(self):
        proj = ay.nuevo_proyecto()
        mem = str(proj / 'memory')
        sid = 'sid-6'
        huella.registrar(mem, sid, {'ts': 't', 'tipo': 'proceso_nuevo', 'pid': '1', 'nombre': 'x', 'inicio': 'h1'})
        huella.registrar(mem, sid, {'ts': 't', 'tipo': 'puerto_nuevo', 'puerto': '8080', 'pid': '1'})
        # foto FRESCA que SÍ sigue viendo el proceso y el puerto vivos ahora mismo
        with mock.patch.object(huella, 'foto',
                                return_value=({'puertos': {'8080': '1'}, 'procesos': {'1': {'nombre': 'x', 'inicio': 'h1'}}}, 5)):
            txt = huella.resumen_stop(mem, sid)
        self.assertEqual(txt, '[huella] 1 proceso y 1 puerto abiertos por este hilo siguen vivos: --informe')


class ArrancarConInstrumentosSimulados(unittest.TestCase):
    def test_arrancar_guarda_snapshot_y_evento_inicio(self):
        proj = ay.nuevo_proyecto()
        mem = str(proj / 'memory')
        with mock.patch.object(huella, 'foto', return_value=({'puertos': {'80': '1'}, 'procesos': {}}, 42)):
            huella.arrancar(mem, 'sid-arranque')
        self.assertEqual(huella.snapshot_leer(mem, 'sid-arranque'), {'puertos': {'80': '1'}, 'procesos': {}})
        evs = huella.eventos(mem, 'sid-arranque')
        self.assertEqual(len(evs), 1)
        self.assertEqual(evs[0]['tipo'], 'inicio')
        self.assertEqual(evs[0]['puertos_iniciales'], 1)
        self.assertEqual(evs[0]['foto_ms'], 42)


class LimpiarRespectaCarpetas(unittest.TestCase):
    def test_no_borra_fuera_de_temp_ni_mem(self):
        # `ay.nuevo_proyecto()` ya vive bajo el temp REAL del sistema (aislamiento
        # de pruebas, §2 de la tarea) — así que para poder probar de verdad el
        # caso "fuera de temp Y de mem" hay que controlar qué considera
        # `huella.py` que ES el temp: se monkeypatchea `tempfile.gettempdir()` a
        # una carpeta hermana de `proj`, distinta de donde vive el fichero
        # "fuera" y de `mem`.
        proj = ay.nuevo_proyecto()
        mem = str(proj / 'memory')
        sid = 'sid-7'
        fuera = str(proj / 'proyecto_real' / 'codigo_fuente.py')
        os.makedirs(os.path.dirname(fuera), exist_ok=True)
        with open(fuera, 'w', encoding='utf-8') as fh:
            fh.write('no me toques')
        huella.registrar(mem, sid, {'ts': 't', 'tipo': 'escrito', 'ruta': fuera})
        tmp_falso = str(proj / 'tmp_falso')
        os.makedirs(tmp_falso, exist_ok=True)
        with mock.patch.object(huella, 'foto', return_value=({'puertos': {}, 'procesos': {}}, 1)), \
             mock.patch.object(huella.tempfile, 'gettempdir', return_value=tmp_falso):
            texto = huella.limpiar(mem, sid, confirmar=True)
        self.assertTrue(os.path.exists(fuera), 'un fichero fuera de temp/ y mem/ no se borra nunca')
        self.assertIn('no se tocan', texto)
        self.assertIn(fuera, texto)

    def test_borra_lo_que_esta_bajo_el_temp_real(self):
        proj = ay.nuevo_proyecto()
        mem = str(proj / 'memory')
        sid = 'sid-8'
        fd, ruta_tmp = tempfile.mkstemp(prefix='abyss_borrable_')
        os.close(fd)
        huella.registrar(mem, sid, {'ts': 't', 'tipo': 'escrito', 'ruta': ruta_tmp})
        try:
            with mock.patch.object(huella, 'foto', return_value=({'puertos': {}, 'procesos': {}}, 1)):
                texto = huella.limpiar(mem, sid, confirmar=True)
            self.assertFalse(os.path.exists(ruta_tmp), 'un fichero bajo el temp real del sistema sí se borra')
            self.assertIn('borrado', texto)
        finally:
            if os.path.exists(ruta_tmp):
                os.remove(ruta_tmp)

    def test_memory_md_y_fichas_bajo_mem_no_se_borran(self):
        """Fallo "rompe" medido 7-sep (T2.2): antes CUALQUIER ruta bajo `mem`
        contaba como borrable (esta misma prueba, antes, se llamaba
        `test_bajo_mem_tambien_se_borra` y afirmaba justo lo contrario), así
        que un `Write` de la sesión sobre la memoria de verdad del usuario
        (`MEMORY.md`, una ficha nueva) se borraba sin copia de seguridad con
        `--limpiar --si` — el rito normal de cierre de este mismo paquete
        («fichas -> el índice se recalcula solo»), justo lo que
        `instalar.DATOS_GENERADOS` excluye a propósito
        ("eso es lo que él puso o su memoria de verdad") y lo que README.md
        promete que el desinstalador NUNCA borra por defecto. Se aísla
        `tempfile.gettempdir()` (que en las pruebas vive bajo el mismo temp del
        sistema que `mem` y taparía el fallo dejando pasar por la rama de
        temp/) a una carpeta hermana, igual que `test_no_borra_fuera_de_temp_ni_mem`."""
        proj = ay.nuevo_proyecto()
        mem = str(proj / 'memory')
        sid = 'sid-9'
        os.makedirs(mem, exist_ok=True)
        memory_md = os.path.join(mem, 'MEMORY.md')
        ficha = os.path.join(mem, 'ficha-nueva.md')
        for ruta, txt in ((memory_md, '# índice'), (ficha, '# ficha nueva')):
            with open(ruta, 'w', encoding='utf-8') as fh:
                fh.write(txt)
        huella.registrar(mem, sid, {'ts': 't', 'tipo': 'escrito', 'ruta': memory_md})
        huella.registrar(mem, sid, {'ts': 't', 'tipo': 'escrito', 'ruta': ficha})
        tmp_falso = str(proj / 'tmp_falso')
        os.makedirs(tmp_falso, exist_ok=True)
        with mock.patch.object(huella, 'foto', return_value=({'puertos': {}, 'procesos': {}}, 1)), \
             mock.patch.object(huella.tempfile, 'gettempdir', return_value=tmp_falso):
            texto = huella.limpiar(mem, sid, confirmar=True)
        self.assertTrue(os.path.exists(memory_md), 'MEMORY.md nunca se borra, aunque esté "bajo mem"')
        self.assertTrue(os.path.exists(ficha), 'una ficha .md nunca se borra, aunque esté "bajo mem"')
        self.assertIn('no se tocan', texto)
        self.assertIn(memory_md, texto)
        self.assertIn(ficha, texto)

    def test_bajo_una_subcarpeta_generada_de_mem_si_se_borra(self):
        """Lo que SÍ sigue siendo zona borrable: las subcarpetas que este
        paquete genera por su cuenta bajo `mem` (`mem/huella/`, `mem/mapas/`,
        `mem/pdf/`, T2.2) — el corte no es "nada bajo mem", es "solo lo que
        genera este paquete"."""
        proj = ay.nuevo_proyecto()
        mem = str(proj / 'memory')
        sid = 'sid-generado'
        carpeta = os.path.join(mem, 'mapas')
        os.makedirs(carpeta, exist_ok=True)
        ruta = os.path.join(carpeta, 'un_repo.txt')
        with open(ruta, 'w', encoding='utf-8') as fh:
            fh.write('mapa')
        huella.registrar(mem, sid, {'ts': 't', 'tipo': 'escrito', 'ruta': ruta})
        tmp_falso = str(proj / 'tmp_falso')
        os.makedirs(tmp_falso, exist_ok=True)
        with mock.patch.object(huella, 'foto', return_value=({'puertos': {}, 'procesos': {}}, 1)), \
             mock.patch.object(huella.tempfile, 'gettempdir', return_value=tmp_falso):
            texto = huella.limpiar(mem, sid, confirmar=True)
        self.assertFalse(os.path.exists(ruta), 'mem/mapas/ sí es zona borrable: la genera este paquete')
        self.assertIn('borrado', texto)

    def test_fichero_suelto_en_la_raiz_de_mem_no_se_borra(self):
        """Un fichero suelto directamente en la raíz de `mem` (sin estar bajo
        ninguna subcarpeta generada) tampoco cuenta como borrable, aunque no
        sea `.md`: la zona borrable son subcarpetas concretas, no "todo lo que
        no termine en .md dentro de mem"."""
        proj = ay.nuevo_proyecto()
        mem = str(proj / 'memory')
        sid = 'sid-suelto'
        os.makedirs(mem, exist_ok=True)
        ruta = os.path.join(mem, 'algo_temporal.json')
        with open(ruta, 'w', encoding='utf-8') as fh:
            fh.write('{}')
        huella.registrar(mem, sid, {'ts': 't', 'tipo': 'escrito', 'ruta': ruta})
        tmp_falso = str(proj / 'tmp_falso')
        os.makedirs(tmp_falso, exist_ok=True)
        with mock.patch.object(huella, 'foto', return_value=({'puertos': {}, 'procesos': {}}, 1)), \
             mock.patch.object(huella.tempfile, 'gettempdir', return_value=tmp_falso):
            texto = huella.limpiar(mem, sid, confirmar=True)
        self.assertTrue(os.path.exists(ruta), 'nada suelto en la raíz de mem/ se borra, aunque no sea .md')
        self.assertIn('no se tocan', texto)


# ---------- ganchos reales y ciclo de vida de un proceso: por subproceso ----------

class GanchoHerramienta(unittest.TestCase):
    def test_write_registra_la_ruta(self):
        proj = ay.nuevo_proyecto()
        sid = 'ses-write-1'
        tp = proj / f'{sid}.jsonl'
        tp.write_text('', encoding='utf-8')
        env = ay.entorno(proj)
        entrada = json.dumps({'session_id': sid, 'transcript_path': str(tp), 'cwd': str(proj),
                               'tool_name': 'Write', 'tool_input': {'file_path': str(proj / 'algo.txt')}})
        r = ay.ejecutar(ay.script('huella.py'), ['--herramienta'], env, entrada=entrada)
        self.assertEqual(r.returncode, 0, r.stderr)
        log = proj / 'memory' / 'huella' / f'{sid}.jsonl'
        self.assertTrue(log.exists())
        eventos = [json.loads(l) for l in log.read_text(encoding='utf-8').splitlines() if l.strip()]
        self.assertEqual(len(eventos), 1)
        self.assertEqual(eventos[0]['tipo'], 'escrito')
        self.assertEqual(eventos[0]['ruta'], str(proj / 'algo.txt'))

    def test_herramienta_ajena_no_registra_nada(self):
        proj = ay.nuevo_proyecto()
        sid = 'ses-read-1'
        tp = proj / f'{sid}.jsonl'
        tp.write_text('', encoding='utf-8')
        env = ay.entorno(proj)
        entrada = json.dumps({'session_id': sid, 'transcript_path': str(tp), 'cwd': str(proj),
                               'tool_name': 'Read', 'tool_input': {'file_path': str(proj / 'algo.txt')}})
        r = ay.ejecutar(ay.script('huella.py'), ['--herramienta'], env, entrada=entrada)
        self.assertEqual(r.returncode, 0, r.stderr)
        log = proj / 'memory' / 'huella' / f'{sid}.jsonl'
        self.assertFalse(log.exists(), 'Read no toca nada fuera del sandbox que a huella le importe')


class CicloDeVidaDeUnProcesoReal(unittest.TestCase):
    """T2.2, prueba mínima pedida: un Bash que arranca `python -c "import time;
    time.sleep(30)"` aparece en `--informe`, y `--limpiar --si` lo mata de
    verdad. Se usa un proceso que duerme mucho más que la duración de la
    prueba para que siga vivo en el momento de comprobarlo."""

    def test_informe_ve_el_proceso_y_limpiar_lo_mata(self):
        proj = ay.nuevo_proyecto()
        sid = 'ses-vivo-1'
        tp = proj / f'{sid}.jsonl'
        tp.write_text('', encoding='utf-8')
        env = ay.entorno(proj)
        entrada_base = json.dumps({'session_id': sid, 'transcript_path': str(tp), 'cwd': str(proj)})
        r = ay.ejecutar(ay.script('huella.py'), ['--arranque'], env, entrada=entrada_base)
        self.assertEqual(r.returncode, 0, r.stderr)

        proc = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
        try:
            time.sleep(0.5)  # que el nuevo proceso ya tenga StartTime asentado
            entrada_h = json.dumps({
                'session_id': sid, 'transcript_path': str(tp), 'cwd': str(proj), 'tool_name': 'Bash',
                'tool_input': {'command': 'python -c "import time; time.sleep(60)"'},
            })
            r = ay.ejecutar(ay.script('huella.py'), ['--herramienta'], env, entrada=entrada_h)
            self.assertEqual(r.returncode, 0, r.stderr)

            r = ay.ejecutar(ay.script('huella.py'), ['--informe', sid], env)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn(str(proc.pid), r.stdout, 'el pid del proceso real debe salir en --informe')

            # dry-run: no debe matarlo
            r = ay.ejecutar(ay.script('huella.py'), ['--limpiar', sid], env)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn('simulación', r.stdout)
            self.assertIsNone(proc.poll(), 'sin --si no se mata nada')

            r = ay.ejecutar(ay.script('huella.py'), ['--limpiar', sid, '--si'], env)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn('matado', r.stdout)

            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
            self.assertIsNotNone(proc.poll(), 'el proceso debe estar muerto tras --limpiar --si')
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=5)

    def test_pid_con_hora_de_arranque_distinta_no_se_mata(self):
        """Un evento registrado a mano para un pid que SÍ existe ahora mismo (el
        propio proceso de la prueba, `os.getpid()`) pero con una hora de arranque
        que NO coincide con la real: `--limpiar --si` no debe tocarlo."""
        proj = ay.nuevo_proyecto()
        sid = 'ses-pid-reciclado-1'
        mem = proj / 'memory'
        huella_mod_dir = mem / 'huella'
        huella_mod_dir.mkdir(parents=True, exist_ok=True)
        (huella_mod_dir / f'{sid}.jsonl').write_text(
            json.dumps({'ts': 't', 'tipo': 'proceso_nuevo', 'pid': str(os.getpid()),
                        'nombre': 'python', 'inicio': '1999-01-01T00:00:00'}) + '\n',
            encoding='utf-8')
        env = ay.entorno(proj)

        r = ay.ejecutar(ay.script('huella.py'), ['--informe', sid], env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('procesos vivos: ninguno', r.stdout,
                       'la hora registrada (1999) no coincide con la real: no cuenta como vivo')

        r = ay.ejecutar(ay.script('huella.py'), ['--limpiar', sid, '--si'], env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('ninguno vivo que matar', r.stdout)
        self.assertNotIn(str(os.getpid()), r.stdout)


class GanchoFin(unittest.TestCase):
    def test_fin_silencioso_sin_snapshot(self):
        proj = ay.nuevo_proyecto()
        sid = 'ses-fin-1'
        tp = proj / f'{sid}.jsonl'
        tp.write_text('', encoding='utf-8')
        env = ay.entorno(proj)
        entrada = json.dumps({'session_id': sid, 'transcript_path': str(tp), 'cwd': str(proj)})
        r = ay.ejecutar(ay.script('huella.py'), ['--fin'], env, entrada=entrada)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), '')


class BanderaDesconocidaEnCLI(unittest.TestCase):
    """T2 revisor (7-sep): `_parse_argv` ignoraba en silencio toda bandera que
    no fuera `--si`/`--proyecto`/`--sesion` (`continue` explícito). Quien
    tecleara `--yes`, `--si` con tilde o cualquier otra cosa detrás de
    `--limpiar` obtenía la simulación normal con código 0, sin ninguna pista
    de que la bandera no se reconoció — contra ESPECIFICACION.md §3."""

    def test_informe_con_bandera_inventada_sale_con_codigo_1(self):
        proj = ay.nuevo_proyecto()
        sid = 'sid-informe-bandera-mala'
        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('huella.py'), ['--informe', sid, '--bandera-inventada'], env)
        self.assertEqual(r.returncode, 1)
        self.assertIn('--bandera-inventada', r.stderr)

    def test_limpiar_con_yes_en_vez_de_si_sale_con_codigo_1_y_no_simula(self):
        proj = ay.nuevo_proyecto()
        sid = 'sid-limpiar-yes'
        env = ay.entorno(proj)
        r = ay.ejecutar(ay.script('huella.py'), ['--limpiar', sid, '--yes'], env)
        self.assertEqual(r.returncode, 1)
        self.assertIn('--yes', r.stderr)
        self.assertNotIn('borraría', r.stdout)
        self.assertNotIn('mataría', r.stdout)


class GanchoHerramientaToolInputNoEsDict(unittest.TestCase):
    """T2 revisor (7-sep): el gancho PostToolUse (`--herramienta`) hacía
    `tool_input.get(...)` tras un `_STDIN.get('tool_input') or {}` — una cadena
    no vacía o una lista pasan ese `or {}` sin problema y no tienen `.get`, así
    que revienta con un `AttributeError` sin capturar (traceback por stderr,
    código 1), justo lo contrario de lo que promete el docstring del módulo
    («nada se imprime: es instrumentación silenciosa»)."""

    def test_tool_input_cadena_no_revienta(self):
        proj = ay.nuevo_proyecto()
        sid = 'ses-tool-input-cadena'
        tp = proj / f'{sid}.jsonl'
        tp.write_text('', encoding='utf-8')
        env = ay.entorno(proj)
        entrada = json.dumps({'session_id': sid, 'transcript_path': str(tp), 'cwd': str(proj),
                               'tool_name': 'Write', 'tool_input': 'una cadena'})
        r = ay.ejecutar(ay.script('huella.py'), ['--herramienta'], env, entrada=entrada)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stderr, '')

    def test_tool_input_lista_no_revienta(self):
        proj = ay.nuevo_proyecto()
        sid = 'ses-tool-input-lista'
        tp = proj / f'{sid}.jsonl'
        tp.write_text('', encoding='utf-8')
        env = ay.entorno(proj)
        entrada = json.dumps({'session_id': sid, 'transcript_path': str(tp), 'cwd': str(proj),
                               'tool_name': 'Bash', 'tool_input': ['no', 'es', 'un', 'dict']})
        r = ay.ejecutar(ay.script('huella.py'), ['--herramienta'], env, entrada=entrada)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stderr, '')


class GanchoFinDePuntaAPuntaConBashReal(unittest.TestCase):
    """El falsador que faltaba (T2.2, fallo medido 7-sep): con la cadena REAL
    arranque -> herramienta (un `Bash` inocuo de verdad, sin mockear `foto()`)
    -> fin, `--fin` no debe decir nada. Antes de este arreglo, un solo `echo
    uno` bastaba para que `--fin` avisara de "3 proceso ... siguen vivos" que
    en ESE MISMO instante `--informe` (foto fresca) ya no veía."""

    def test_arranque_bash_inocuo_fin_calla(self):
        proj = ay.nuevo_proyecto()
        sid = 'ses-e2e-bash-inocuo-1'
        tp = proj / f'{sid}.jsonl'
        tp.write_text('', encoding='utf-8')
        env = ay.entorno(proj)

        entrada_arranque = json.dumps({'session_id': sid, 'transcript_path': str(tp), 'cwd': str(proj)})
        r = ay.ejecutar(ay.script('huella.py'), ['--arranque'], env, entrada=entrada_arranque)
        self.assertEqual(r.returncode, 0, r.stderr)

        entrada_bash = json.dumps({'session_id': sid, 'transcript_path': str(tp), 'cwd': str(proj),
                                    'tool_name': 'Bash', 'tool_input': {'command': 'echo uno'}})
        r = ay.ejecutar(ay.script('huella.py'), ['--herramienta'], env, entrada=entrada_bash)
        self.assertEqual(r.returncode, 0, r.stderr)

        entrada_fin = json.dumps({'session_id': sid, 'transcript_path': str(tp), 'cwd': str(proj)})
        r = ay.ejecutar(ay.script('huella.py'), ['--fin'], env, entrada=entrada_fin)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), '',
                          f'--fin no debe avisar de nada tras un Bash inocuo: {r.stdout!r}')


if __name__ == '__main__':
    unittest.main()
