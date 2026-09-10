"""Exterocepción: lo de FUERA que puedo medir en cada prompt.

- lugar: DOS instrumentos, y cuando no coinciden se enseñan los dos, no decido yo:
    · `ip`   → geolocalización por IP (ipinfo.io, https); se refresca en cada arranque.
    · `dicho`→ lo que el usuario dice en la conversación («estoy en Madrid», «desde
               París», «he llegado a la torre Eiffel»): se geocodifica (open-meteo;
               si no es una ciudad, Nominatim/OpenStreetMap) y se guarda con hora.
               Gana el más reciente en la lectura principal; el otro se muestra si
               discrepa.
  NO se usa ningún otro programa de mensajería: leer sus actualizaciones le robaría
  los mensajes a quien los escribió.
- meteo: open-meteo.com (sin clave) con la lat/lon del lugar principal; cache 15 min.
- canal: `entrypoint` + `origin.kind` del último mensaje del usuario en el transcript.
         Hasta hoy todo es «claude-desktop»; si un día aparece otro valor, ese será el móvil.
- ojo:   la webcam va aparte (`ojo.py`), solo cuando el usuario lo pide.

DEPENDENCIAS EXTERNAS declaradas: ipinfo.io (lugar por IP), open-meteo.com (geocodificar
ciudades y leer el tiempo), nominatim.openstreetmap.org (geocodificar lo que no es una
ciudad). Todo es LECTURA de instrumentos: nada se inventa; sin red o con la API caída,
«sin dato», nunca un valor puesto a mano.

Carpeta de datos: NUNCA `dirname(__file__)` (eso sería la carpeta del CÓDIGO instalado).
Se resuelve con `rutas.resolver()` (ver `rutas.py` y ESPECIFICACION.md §1) a partir de la
pista disponible en cada llamada (normalmente el `transcript_path` que ya trae quien nos
invoca). Si NADA la resuelve —p. ej. nos importa `continuidad.py` con el stdin del gancho
ya consumido y sin `ABYSS_PROYECTO`— no reventamos al que nos llama: cada función dice
«sin dato» (fail-closed), salvo el uso manual por `__main__`, que si no hay proyecto avisa
claro y sale (para eso está `rutas.resolver()`: quien lo teclea a mano necesita saberlo).
"""
import sys
try:                       # la consola de Windows y la salida tienen que hablar
    from . import consola  # el mismo idioma: ver abyss/consola.py
except ImportError:
    import consola
consola.preparar()
import os, re, json, time, urllib.request, urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rutas  # noqa: E402

WMO = {0: 'despejado', 1: 'casi despejado', 2: 'nubes y claros', 3: 'cubierto', 45: 'niebla', 48: 'niebla con escarcha',
       51: 'llovizna ligera', 53: 'llovizna', 55: 'llovizna densa', 61: 'lluvia ligera', 63: 'lluvia', 65: 'lluvia fuerte',
       71: 'nieve ligera', 73: 'nieve', 75: 'nieve fuerte', 80: 'chubascos ligeros', 81: 'chubascos', 82: 'chubascos fuertes',
       95: 'tormenta', 96: 'tormenta con granizo', 99: 'tormenta con granizo fuerte'}
# Es una lista, y sé lo que valen las listas: si falla, el lugar queda como estaba (no se inventa).
RE_DICHO = re.compile(
    r'\b(?:estoy|estamos|ando|me encuentro|he llegado|hemos llegado|llegu[eé]|acabo de llegar|te escribo|escribo|me pillas)\s+'
    r'(?:en|a|desde)\s+(?:la |el |los |las )?([A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñü]+(?:\s+(?:de|del|la|el|los|las|d\')?\s*[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñü]+){0,3})',
    re.U)

_CACHE = {}  # 'proj'/'mem' una vez resueltos en este proceso: no se vuelve a preguntar


def _mem(tp=None, stdin_json=None):
    """Carpeta de datos para ESTA llamada, cacheada por proceso. `tp` es el
    `transcript_path` si lo tenemos a mano (lo trae quien nos invoca); con él
    `rutas.resolver()` acierta sin tocar stdin. Si no hay pista ni caché previa y
    tampoco `--proyecto`/`ABYSS_PROYECTO`, no reventamos: devolvemos None y quien
    llama dice «sin dato» (fail-closed, [[verificar-antes-de-construir]])."""
    if _CACHE.get('mem'):
        return _CACHE['mem']
    if stdin_json is None:
        stdin_json = {'transcript_path': tp} if tp else {}
    try:
        proj, mem = rutas.resolver(stdin_json=stdin_json)
    except SystemExit:
        return None
    _CACHE['proj'], _CACHE['mem'] = proj, mem
    return mem


def _ruta(nombre, tp=None):
    m = _mem(tp)
    return os.path.join(m, nombre) if m else None


def _get(url, timeout=3, presupuesto=None):
    """Petición GET → JSON. `timeout` bajado de 6 a 3 s por defecto (medido 6-sep: con
    la red en agujero negro cada llamada consumía su timeout entero; presupuesto o no,
    una llamada suelta no debe poder colgar más de unos pocos segundos).

    `presupuesto` (`rutas.Presupuesto`), si se pasa, ACOTA el timeout de ESTA llamada
    al tiempo que quede del total compartido — y si ya no queda nada, ni lo intenta
    (`TimeoutError` inmediato, sin tocar la red).

    `ABYSS_SIN_RED=1`: interruptor explícito para pruebas (§6/§9 del encargo 6-sep) —
    corta la red al instante, nunca a medio timeout, para que la suite no dependa de
    si la máquina que la corre tiene internet."""
    if os.environ.get('ABYSS_SIN_RED') == '1':
        raise RuntimeError('sin red (ABYSS_SIN_RED=1)')
    if presupuesto is not None:
        timeout = presupuesto.restante(timeout)
    with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'abyss-exterocepcion (Claude Code, uso personal)'}), timeout=timeout) as r:
        return json.load(r)


def _leer(tp=None):
    try:
        with open(_ruta('lugar.json', tp), encoding='utf-8') as fh:
            d = json.load(fh)
        if 'ip' in d or 'dicho' in d:
            return d
        return {'ip': d} if d.get('lat') else {}  # formato antiguo (solo IP)
    except Exception:
        return {}


def _escribir(d, tp=None):
    ruta = _ruta('lugar.json', tp)
    if not ruta:
        return  # sin proyecto no hay dónde guardar; se pierde este dato, no se inventa otro sitio
    with open(ruta, 'w', encoding='utf-8') as fh:
        json.dump(d, fh, ensure_ascii=False, indent=1)


def lugar_ip(refrescar=False, tp=None, presupuesto=None):
    d = _leer(tp)
    if not refrescar and d.get('ip'):
        return d['ip']
    try:
        r = _get('https://ipinfo.io/json', presupuesto=presupuesto)
        lat, lon = (r.get('loc') or ',').split(',')
        d['ip'] = {'nombre': r.get('city'), 'region': r.get('region'), 'pais': r.get('country'),
                   'lat': float(lat), 'lon': float(lon), 'fuente': 'IP', 'ts': time.time()}
        _escribir(d, tp)
    except Exception:
        pass
    return d.get('ip')


def geocodificar(nombre, presupuesto=None):
    """Ciudad → open-meteo; si no, lugar/monumento → Nominatim. None si nada."""
    try:
        r = _get('https://geocoding-api.open-meteo.com/v1/search?name=' + urllib.parse.quote(nombre) + '&count=1&language=es', presupuesto=presupuesto)
        if r.get('results'):
            g = r['results'][0]
            return {'nombre': g['name'], 'region': g.get('admin1'), 'pais': g.get('country_code'), 'lat': g['latitude'], 'lon': g['longitude']}
    except Exception:
        pass
    try:
        r = _get('https://nominatim.openstreetmap.org/search?q=' + urllib.parse.quote(nombre) + '&format=json&limit=1&accept-language=es', presupuesto=presupuesto)
        if r:
            g = r[0]; partes = g.get('display_name', '').split(', ')
            return {'nombre': partes[0] if partes else nombre, 'region': ', '.join(partes[1:3]), 'pais': partes[-1] if partes else None,
                    'lat': float(g['lat']), 'lon': float(g['lon'])}
    except Exception:
        pass
    return None


def aprender_lugar(prompt, tp=None, presupuesto=None):
    """Si el usuario dice dónde está, geocodifica y guarda como `dicho`. Devuelve el
    nombre o None."""
    m = RE_DICHO.search(prompt or '')
    if not m:
        return None
    g = geocodificar(m.group(1).strip(), presupuesto=presupuesto)
    if not g:
        return None
    d = _leer(tp); d['dicho'] = {**g, 'fuente': 'usuario', 'texto': m.group(0), 'ts': time.time()}
    try:
        _escribir(d, tp)
    except Exception:
        pass  # sin proyecto resoluble no se guarda esta vez; no debe tumbar al que nos llama
    return g['nombre']


def lugar(tp=None, presupuesto=None):
    """(principal, secundario_si_discrepa). Principal = la lectura más reciente."""
    d = _leer(tp); ip = d.get('ip'); di = d.get('dicho')
    if not ip and not di:
        ip = lugar_ip(tp=tp, presupuesto=presupuesto)
    cands = [x for x in (ip, di) if x]
    if not cands:
        return None, None
    p = max(cands, key=lambda x: x.get('ts', 0))
    otro = [x for x in cands if x is not p]
    sec = otro[0] if otro and (otro[0].get('nombre') != p.get('nombre')) else None
    return p, sec


def meteo(lg, max_edad_s=900, tp=None, presupuesto=None):
    """Tiempo actual en el lugar; cache 15 min. None si no hay red o lugar. La caché en
    disco es un extra: si no hay proyecto resoluble se pide igualmente a la red y se
    devuelve, solo que sin guardar para la próxima vez."""
    if not lg:
        return None
    ruta = _ruta('meteo.json', tp)
    try:
        with open(ruta, encoding='utf-8') as fh:
            c = json.load(fh)
        if time.time() - c.get('ts', 0) < max_edad_s and c.get('lat') == lg['lat']:
            return c
    except Exception:
        pass
    try:
        d = _get(f"https://api.open-meteo.com/v1/forecast?latitude={lg['lat']}&longitude={lg['lon']}"
                 "&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m,is_day&timezone=auto",
                 presupuesto=presupuesto)
        cu = d['current']
        out = {'temp': cu['temperature_2m'], 'humedad': cu['relative_humidity_2m'], 'codigo': cu['weather_code'],
               'cielo': WMO.get(cu['weather_code'], f"código {cu['weather_code']}"), 'viento': cu['wind_speed_10m'],
               'dia': bool(cu['is_day']), 'hora_dato': cu['time'], 'lat': lg['lat'], 'ts': time.time()}
        if ruta:
            with open(ruta, 'w', encoding='utf-8') as fh:
                json.dump(out, fh, ensure_ascii=False, indent=1)
        return out
    except Exception:
        return None


def canal(transcript_path):
    """Último `entrypoint` / `origin.kind` con que habló el usuario, tal cual está en el transcript."""
    if not transcript_path or not os.path.exists(transcript_path):
        return None
    ult = None
    try:
        with open(transcript_path, encoding='utf-8', errors='ignore') as fh:
            for line in fh:
                if '"entrypoint"' not in line:
                    continue
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                if d.get('type') == 'user' and isinstance((d.get('message') or {}).get('content'), str) and not d.get('isMeta'):
                    o = d.get('origin') or {}
                    kind = o.get('kind') if isinstance(o, dict) else o
                    if kind and kind != 'human':  # notificaciones y sistema no son el canal del usuario (17ª forma)
                        continue
                    ult = (d.get('entrypoint'), kind)
    except Exception:
        return None
    return ult


def _hace(ts):
    s = time.time() - ts
    return f'{s / 60:.0f} min' if s < 5400 else f'{s / 3600:.1f} h' if s < 48 * 3600 else f'{s / 86400:.0f} días'


def texto(transcript_path=None, presupuesto=None):
    partes = []
    p, sec = lugar(tp=transcript_path, presupuesto=presupuesto)
    if p:
        t = f"lugar {p.get('nombre') or '?'} ({p.get('pais') or '?'}; {'lo dijiste hace ' + _hace(p['ts']) if p.get('fuente') == 'usuario' else 'por IP'})"
        if sec:
            t += f" · {'la IP dice' if sec.get('fuente') == 'IP' else 'dijiste'} {sec.get('nombre')}" + ('' if sec.get('fuente') == 'IP' else f" hace {_hace(sec['ts'])}")
        partes.append(t)
        m = meteo(p, tp=transcript_path, presupuesto=presupuesto)
        partes.append(f"meteo {m['cielo']}, {m['temp']:.0f} °C, humedad {m['humedad']}%, viento {m['viento']:.0f} km/h, {'de día' if m['dia'] else 'de noche'}" if m
                      else 'meteo sin dato (sin red o API caída)')
    else:
        partes.append('lugar sin dato (sin red)')
    c = canal(transcript_path)
    if c:
        partes.append(f"canal {c[0] or '?'}" + (f"/{c[1]}" if c[1] else ''))
    return '[mundo] ' + ' · '.join(partes)


def _texto_lugar_ip(ip):
    """Frase legible para `--refrescar-ip` (fallo 6-sep, "roza"): antes se hacía
    `print(lugar_ip(...))`, que imprimía el repr crudo del dict de Python (con el
    timestamp en bruto) cuando había dato, o literalmente la palabra `None` sin red
    — ninguna de las dos es una frase. El punto 5 de la filosofía del README ("sin
    red no hay lugar ni meteo: la respuesta siempre es 'sin dato'") ya lo cumple
    `texto()`; esto compone la misma idea para esta salida más corta."""
    if not ip:
        return 'lugar por IP: sin dato (sin red)'
    return f"lugar por IP: {ip.get('nombre') or '?'} ({ip.get('pais') or '?'})"


def _texto_aprendido(nombre):
    """Frase legible para `--dicho` (fallo 6-sep, "roza"): antes `aprendido: None`
    cuando la frase no traía ningún lugar reconocible (ni por regex, ni porque el
    geocodificador no tuvo red)."""
    return f'aprendido: {nombre}' if nombre else 'no reconocí ningún lugar en la frase'


if __name__ == '__main__':
    a = sys.argv[1:]
    # uso manual: si se pasa un transcript como posicional, es también la pista de proyecto.
    # `rutas.es_transcript` exige fichero real + `.jsonl` (§2 ESPECIFICACION.md): ni una
    # bandera como `--proyecto` ni un directorio como `.` cuelan como transcript_path
    # (medido 6-sep: `.` resolvía `proj` como el PADRE del cwd).
    tp_arg = a[0] if a and rutas.es_transcript(a[0]) else None
    sj = {'transcript_path': tp_arg} if tp_arg else None
    # a mano SÍ queremos el error claro de rutas.resolver() si no hay proyecto (no lo tragamos)
    _CACHE['proj'], _CACHE['mem'] = rutas.resolver(argv=a, stdin_json=sj)
    if a and a[0] == '--refrescar-ip':
        print(_texto_lugar_ip(lugar_ip(refrescar=True)))
        sys.exit(0)
    if a and a[0] == '--dicho':
        print(_texto_aprendido(aprender_lugar(' '.join(a[1:]))))
        print(texto())
        sys.exit(0)
    print(texto(tp_arg))
