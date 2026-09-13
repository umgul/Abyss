# -*- coding: utf-8 -*-
"""Sirve `plantillas/instalador.html` y le da los verbos que ya tiene la ventana Tk de
`instalar.py` (`_abrir_ventana`): instalar, desinstalar, dependencias, claves, cerrar.
Existe porque Tk en Windows no pinta bordes redondeados, sombras, interletrado ni
diálogos vestibles, y esa ventana es la primera pantalla que alguien ve al publicar
este paquete.

CERO lógica de instalación duplicada: qué es un módulo, qué gancho lleva, cómo se
instala o desinstala vive SOLO en `instalar.py` (raíz del repo). Este fichero lo carga
por ruta absoluta (no por import normal: `instalar.py` vive fuera del paquete `abyss/`)
y llama a sus funciones reales (`instalar()`, `desinstalar()`,
`instalar_dependencias()`, `_tabla_dependencias()`, `_texto()`, `MODULOS`,
`DEPENDENCIAS`, `estado_modulo()`) — nunca reimplementa esa lógica, para no acabar con
dos implementaciones (web y Tk) que se desincronicen.

Propio de aquí: servir `plantillas/instalador.html` (único fichero, sin más estáticos);
las rutas JSON que envuelven esas funciones para `fetch()` (`/api/estado`,
`/api/dependencias`, `/api/claves`, `/api/instalar`, `/api/desinstalar`,
`/api/instalar_dependencias`, `/api/cerrar`); y la lectura de
`plantillas/imagen_config.json`/`mem/imagen_config.json` para la ventana de claves —
misma lectura que `instalar._ventana_claves()`, nunca se manda el VALOR de una clave,
solo si está puesta o vacía.

Seguridad: el servidor se ata SOLO a `127.0.0.1`, nunca a `0.0.0.0`. Los verbos que
cambian algo son siempre `POST`; un `GET` solo lee y nunca deja nada instalado. El
verbo POST evita que una visita suelta o una precarga disparen algo solas, pero POST
no frena a OTRA WEB: eso lo corta `puerta_local.rechazo()`, que exige `Origin`/`Host`
de este mismo servidor al principio de cada verbo.
"""
import argparse
import http.server
import importlib.util
import json
import os
import sys
import threading
import urllib.parse

try:                       # la consola de Windows y la salida tienen que hablar
    from . import consola  # el mismo idioma: ver abyss/consola.py
except ImportError:
    import consola
consola.preparar()

try:
    from . import navegador
except ImportError:
    import navegador

try:
    from . import puerta_local
except ImportError:
    import puerta_local

PKG = os.path.dirname(os.path.abspath(__file__))       # abyss/ (este fichero vive aquí)
RAIZ = os.path.dirname(PKG)                             # raíz del repo, junto a instalar.py
RUTA_HTML = os.path.join(PKG, 'plantillas', 'instalador.html')
RUTA_PLANTILLA_CLAVES = os.path.join(RAIZ, 'plantillas', 'imagen_config.json')
PUERTO_POR_DEFECTO = 8877


def _cargar_instalador():
    """Carga `instalar.py` (raíz del repo) por ruta — ver el docstring del módulo. Sin
    `except` propio a propósito: si no se puede cargar, este servidor tampoco puede
    funcionar y debe fallar alto y claro, no arrancar a medias sirviendo una página que
    no podrá instalar nada."""
    ruta = os.path.join(RAIZ, 'instalar.py')
    spec = importlib.util.spec_from_file_location('abyss_instalador_nucleo', ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


instalador = _cargar_instalador()

# Contexto de ESTA invocación: se resuelve UNA vez al arrancar (`main()`) y los
# manejadores de petición solo lo leen — nunca se recalcula por petición, para que
# --settings/--proyecto/--python sean estables durante toda la sesión (igual que la
# ventana Tk los recibe una vez de `__main__`).
_CTX = {
    'idioma': 'es',
    'settings_ruta': None,
    'python_exe': None,
    'skills_dir': None,
    'proyecto': None,
    'mem': None,
}


def _idioma_de(qs_o_cuerpo):
    valor = None
    if isinstance(qs_o_cuerpo, dict):
        v = qs_o_cuerpo.get('idioma')
        valor = v[0] if isinstance(v, list) else v
    if valor not in ('es', 'en'):
        valor = _CTX['idioma']
    return valor


def _textos_completos(idioma):
    """Todas las cadenas de `TEXTOS` para `idioma` (fail-closed: lo que falte cae al
    castellano, igual que `instalar._texto()`). Se manda el diccionario entero para que
    la página cambie de idioma sin pedir cada texto suelto; ninguna traducción se
    duplica aquí, todas vienen de `instalar.TEXTOS`."""
    fusion = dict(instalador.TEXTOS.get('es', {}))
    fusion.update(instalador.TEXTOS.get(idioma, {}))
    return fusion


def _estado(idioma):
    ctx = _CTX
    settings = instalador._leer_json(ctx['settings_ruta'])
    modulos = []
    for mod in instalador.MODULOS:
        st = instalador.estado_modulo(settings, mod, ctx['settings_ruta'], ctx['skills_dir'])
        clave_estado = instalador._ETIQUETA_ESTADO_CLAVE[st]
        modulos.append({
            'id': mod['id'],
            'defecto': bool(mod.get('defecto', True)),
            'especial': mod.get('especial') or '',
            'estado_clave': clave_estado,
            'etiqueta_estado': instalador._texto(idioma, clave_estado),
            'linea': instalador._linea_localizada(idioma, mod),
            'toca': instalador._campo_localizado(idioma, mod, 'toca'),
            'aviso': instalador._campo_localizado(idioma, mod, 'aviso') if mod.get('aviso') else '',
        })
    return {
        'idioma': idioma,
        'settings_ruta': ctx['settings_ruta'],
        'settings_existe': os.path.exists(ctx['settings_ruta']),
        'proyecto': ctx['proyecto'],
        'mem_resuelto': bool(ctx['mem']),
        'modulos': modulos,
        'textos': _textos_completos(idioma),
    }


def _claves_estado(idioma):
    """Misma lectura que `instalar._ventana_claves()`/`instalar._claves()`: la plantilla
    del repo y el `mem/imagen_config.json` del proyecto, si lo hay. Nunca se manda el
    valor de una clave, solo si está puesta o vacía."""
    try:
        with open(RUTA_PLANTILLA_CLAVES, encoding='utf-8') as fh:
            base = json.load(fh)
    except (OSError, ValueError) as e:
        return {'error': '%s: %s' % (type(e).__name__, e)}
    ayuda = base.get('_ayuda') or {}
    mem = _CTX['mem']
    ruta = os.path.join(mem, 'imagen_config.json') if mem else None
    actual = {}
    if ruta and os.path.isfile(ruta):
        try:
            with open(ruta, encoding='utf-8') as fh:
                actual = json.load(fh)
        except (OSError, ValueError):
            actual = {}
    campos = []
    for campo, info in ayuda.items():
        puesta = bool(actual.get(campo) or base.get(campo))
        campos.append({
            'campo': campo,
            'puesta': puesta,
            'desbloquea': info.get('desbloquea', ''),
            'sin_ella': info.get('sin_ella', ''),
            'donde': info.get('donde', ''),
            'nota': info.get('nota', ''),
        })
    return {'ruta': ruta, 'campos': campos, 'textos': _textos_completos(idioma)}


def _guardar_claves(valores):
    """Igual que `guardar()` en `instalar._ventana_claves()`: solo escribe lo tecleado de
    verdad (campo vacío = "déjalo como estaba", nunca "bórralo"), fusionado sobre la
    plantilla y lo que ya hubiera; `_ayuda` se descarta antes de guardar."""
    mem = _CTX['mem']
    if not mem:
        return {'ok': False, 'motivo': 'sin_proyecto'}
    try:
        with open(RUTA_PLANTILLA_CLAVES, encoding='utf-8') as fh:
            base = json.load(fh)
    except (OSError, ValueError) as e:
        return {'ok': False, 'motivo': 'plantilla: %s' % e}
    ruta = os.path.join(mem, 'imagen_config.json')
    actual = {}
    if os.path.isfile(ruta):
        try:
            with open(ruta, encoding='utf-8') as fh:
                actual = json.load(fh)
        except (OSError, ValueError):
            actual = {}
    nuevos = {c: str(v).strip() for c, v in (valores or {}).items() if str(v).strip()}
    if not nuevos:
        return {'ok': False, 'motivo': 'sin_cambios'}
    datos = dict(base)
    datos.update(actual)
    datos.update(nuevos)
    datos.pop('_ayuda', None)
    os.makedirs(mem, exist_ok=True)
    with open(ruta, 'w', encoding='utf-8') as fh:
        json.dump(datos, fh, ensure_ascii=False, indent=2)
    return {'ok': True, 'guardadas': len(nuevos), 'ruta': ruta}


class _Manejador(http.server.BaseHTTPRequestHandler):
    server_version = 'AbyssInstaladorWeb/1'
    protocol_version = 'HTTP/1.1'

    def log_message(self, formato, *args):
        pass  # silencioso: la consola la lleva `main()` con sus propios avisos

    # ── salida ───────────────────────────────────────────────────────────
    def _json(self, datos, codigo=200):
        cuerpo = json.dumps(datos, ensure_ascii=False).encode('utf-8')
        self.send_response(codigo)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(cuerpo)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(cuerpo)

    def _html(self):
        try:
            with open(RUTA_HTML, 'rb') as fh:
                cuerpo = fh.read()
        except OSError as e:
            self.send_error(500, 'no se pudo leer instalador.html (%s)' % e)
            return
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(cuerpo)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(cuerpo)

    def _cuerpo_json(self):
        largo = int(self.headers.get('Content-Length') or 0)
        crudo = self.rfile.read(largo) if largo else b''
        try:
            return json.loads(crudo.decode('utf-8') or '{}')
        except ValueError:
            return {}

    # ── lectura: nunca instala nada ──────────────────────────────────────
    def do_GET(self):
        motivo = puerta_local.rechazo(self)
        if motivo:
            puerta_local.descartar_cuerpo(self)
            self._json({'error': motivo}, 403)
            return
        partes = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(partes.query)
        idioma = _idioma_de(qs)
        if partes.path in ('/', '/instalador.html'):
            self._html()
        elif partes.path == '/api/estado':
            self._json(_estado(idioma))
        elif partes.path == '/api/dependencias':
            # Mismo criterio que `hacer_dependencias()` en la ventana Tk: de los módulos
            # marcados, solo los que tienen dependencias registradas; si ninguno las
            # tiene, se comprueban todos los de `DEPENDENCIAS`. Se devuelve la lista ya
            # resuelta para que el POST que instala use exactamente la misma.
            marcados_raw = (qs.get('modulos', ['']) or [''])[0]
            marcados = [m for m in marcados_raw.split(',') if m]
            resueltos = [m for m in marcados if m in instalador.DEPENDENCIAS] or list(instalador.DEPENDENCIAS)
            tabla = instalador._tabla_dependencias(idioma, resueltos, _CTX['python_exe'])
            self._json({'tabla': tabla, 'modulos_resueltos': resueltos,
                        'confirmar': instalador._texto(idioma, 'msg_confirmar_instalar_dependencias')})
        elif partes.path == '/api/claves':
            self._json(_claves_estado(idioma))
        else:
            self.send_error(404, 'no encontrado')

    # ── escritura: los cuatro verbos que de verdad cambian algo, + cerrar ──
    def do_POST(self):
        motivo = puerta_local.rechazo(self)
        if motivo:
            puerta_local.descartar_cuerpo(self)
            self.close_connection = True  # cierra tras el rechazo: no reusar esta conexión
            self._json({'error': motivo}, 403)
            return
        partes = urllib.parse.urlparse(self.path)
        cuerpo = self._cuerpo_json()
        idioma = _idioma_de(cuerpo)
        ctx = _CTX

        if partes.path == '/api/instalar':
            ids = [str(i) for i in (cuerpo.get('ids') or [])]
            if ctx['mem'] is None:
                self._json({'error': 'sin_proyecto'})
                return
            tg = cuerpo.get('telegram') or {}
            telegram = (tg.get('token'), tg.get('chat')) if tg.get('token') or tg.get('chat') else None
            mensajes = instalador.instalar(ids, settings_ruta=ctx['settings_ruta'],
                                            python_exe=ctx['python_exe'], mem=ctx['mem'],
                                            telegram=telegram, skills_dir=ctx['skills_dir'],
                                            idioma=idioma)
            # Lo que falta tras instalar (paquetes/claves) se comprueba y se ofrece aquí
            # mismo, para que quien acaba de pulsar el botón no tenga que adivinar que
            # falta abrir además dependencias/claves; si no falta nada, no se dice nada.
            faltan = instalador._paquetes_a_instalar(ids, ctx['python_exe'])
            # `_claves_estado` nunca manda el valor de una clave, solo si está puesta:
            # eso es lo único que hace falta aquí.
            _cl = _claves_estado(idioma)
            vacias = [c['campo'] for c in (_cl.get('campos') or []) if not c.get('puesta')]
            self._json({'mensajes': mensajes,
                        'pendiente': {'paquetes': [p[1] for p in faltan],
                                      'modulos': sorted({p[0] for p in faltan}),
                                      'claves_vacias': vacias}})

        elif partes.path == '/api/desinstalar':
            ids = [str(i) for i in (cuerpo.get('ids') or [])]
            if ctx['mem'] is None:
                self._json({'error': 'sin_proyecto'})
                return
            borrar = bool(cuerpo.get('borrar_datos'))
            mensajes = instalador.desinstalar(ids, settings_ruta=ctx['settings_ruta'], mem=ctx['mem'],
                                               borrar_datos=borrar, skills_dir=ctx['skills_dir'],
                                               idioma=idioma)
            self._json({'mensajes': mensajes})

        elif partes.path == '/api/instalar_dependencias':
            modulos = [str(m) for m in (cuerpo.get('modulos') or [])] or None
            mensajes, ok = instalador.instalar_dependencias(modulos, python_exe=ctx['python_exe'],
                                                              idioma=idioma)
            self._json({'mensajes': mensajes, 'ok': ok})

        elif partes.path == '/api/claves':
            self._json(_guardar_claves(cuerpo.get('valores') or {}))

        elif partes.path == '/api/cerrar':
            self._json({'ok': True})
            # Se responde ANTES de parar: `shutdown()` bloquea hasta que el bucle de
            # `serve_forever()` lo nota, y aquí estamos en el hilo de ESTA petición
            # (servidor con hilos, `ThreadingHTTPServer`) — llamarlo desde un hilo
            # aparte con un respiro corto asegura que la respuesta ya salió por el
            # socket antes de que el servidor empiece a cerrarse.
            threading.Timer(0.2, self.server.shutdown).start()

        else:
            self.send_error(404, 'no encontrado')


def _analizar_argv(argv):
    p = argparse.ArgumentParser(
        description='Instalador web de Abyss: sirve plantillas/instalador.html y llama a las '
                    'mismas funciones de instalar.py que usan la CLI y la ventana Tk.')
    p.add_argument('--puerto', type=int, default=PUERTO_POR_DEFECTO)
    p.add_argument('--settings', default=None, help='ruta a settings.json (por defecto, la del usuario)')
    p.add_argument('--python', dest='python_exe', default=None, help='intérprete a anotar en los ganchos')
    p.add_argument('--proyecto', default=None, help='cwd del proyecto cuya memoria (mem/) se usa')
    p.add_argument('--skills-dir', dest='skills_dir', default=None)
    p.add_argument('--idioma', choices=('es', 'en'), default=None)
    p.add_argument('--sin-abrir', action='store_true',
                    help='no lanza el navegador (para servir y capturar aparte, p. ej. en pruebas)')
    return p.parse_args(argv)


def main(argv=None):
    ns = _analizar_argv(sys.argv[1:] if argv is None else argv)

    idioma = ns.idioma or instalador._idioma_sistema()
    settings_ruta = ns.settings or instalador.SETTINGS_POR_DEFECTO
    python_exe = ns.python_exe or sys.executable
    skills_dir = ns.skills_dir or instalador.SKILLS_DIR_POR_DEFECTO
    # Mismo criterio que `instalar._resolver_mem()`: con `--proyecto` se busca ESE
    # cwd (saneado igual que lo sanearía Claude Code); sin él, cae al cwd de este
    # proceso — nunca se inventa ni se adivina uno "por defecto" (rutas.py §1).
    proj, mem = instalador._resolver_mem(['--proyecto', ns.proyecto] if ns.proyecto else [])

    _CTX.update(idioma=idioma, settings_ruta=settings_ruta, python_exe=python_exe,
                skills_dir=skills_dir, proyecto=proj, mem=mem)

    # SOLO 127.0.0.1 — nunca 0.0.0.0 (ver docstring de arriba).
    httpd = http.server.ThreadingHTTPServer(('127.0.0.1', ns.puerto), _Manejador)
    url = 'http://127.0.0.1:%d/' % ns.puerto
    print('instalador web: sirviendo %s (settings: %s)' % (url, settings_ruta))
    if not ns.sin_abrir:
        # Sin cámara: esta página no la usa, así que no hace falta escribir el
        # permiso en el perfil propio (ver docstring de `navegador.conceder_camara`).
        threading.Timer(0.4, lambda: navegador.abrir(url, modo='app', camara=False,
                                                       avisar=print)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
