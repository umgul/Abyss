"""Marcapáginas: seguir leyendo el transcript de una sesión desde donde se quedó.

Un transcript de Claude Code solo crece: se le añaden líneas al final. Los lectores que lo recorren en cada turno
—`vigia.py --verificar` en cada Stop, `modelo.recorrer()` en cada prompt desde `continuidad.py --despertar`— guardan
aquí, por sesión, hasta qué byte leyeron (siempre el final de una línea), el estado que llevaban en ese punto y la firma
de lo leído: la huella de su código, los tramos de paréntesis de la sesión, y el sha1 de la cabeza (los primeros
min(64 KB, offset) bytes) y de la cola (los 64 KB anteriores al offset). Si la firma casa, se lee solo lo nuevo; si no,
desde el principio. Un lector puede llevar además ficheros de datos que crecen con él (la evidencia del vigía): su
longitud confirmada va en el estado y cada fichero tiene que medirla; si mide más se trunca, si mide menos se empieza de
cero.

«Línea» significa lo mismo que al leer el fichero en modo texto: se lee en binario, se corta por `\\n`, cada trozo se
decodifica en UTF-8 dejando fuera lo inválido, y `\\r\\n` y `\\r` sueltos cuentan como salto. Si lo que queda tras el
último `\\n` contiene una línea que ya es JSON, esa vez no hay marcapáginas: un escritor a mitad de línea nunca deja JSON
válido, así que en la práctica no pasa, y si pasa quien llama lee entero como siempre.

Sin marcapáginas —lectura entera en memoria, como siempre— para `.jsonl.gz`, sesiones de `sesiones/.omitir`, carpeta que
no se puede escribir, cerrojo cogido por otro proceso del mismo lector, o cualquier fallo del estado (que se apunta en
`fallos.log`).

Datos en `mem/.marcapaginas/<sid>/`: `<lector>.json` (estado), `<lector>.lock` (cerrojo) y los ficheros del lector.
Al cerrar una sesión (`continuidad.py --cierre`) se borra su carpeta. Cada vez que un lector confirma su estado, y al
arrancar o cerrar cualquier sesión del proyecto, se barren las carpetas de sesiones omitidas, sin transcript, sin tocar
en 6 horas, y todas menos las 4 más recientes, con los temporales y cerrojos apartados que dejó un proceso muerto. Lo
que no se barre es la carpeta de una sesión que no llegó a cerrarse en un proyecto que nadie vuelve a abrir."""
import os
import sys
import json
import time
import shutil
import hashlib
import unicodedata

try:
    from . import rutas
except ImportError:
    import rutas

TROZO = 64 * 1024           # cabeza y cola de la firma
BLOQUE = 8 * 1024 * 1024    # lectura en bloques: un transcript de 150 MB no se carga entero
CERROJO_VIEJO_S = 120       # un cerrojo más viejo es de un proceso que murió
HORAS_SIN_TOCAR = 6
MAX_SESIONES = 4
TOPE_LOG = 64 * 1024


def huella(*nombres):
    """sha1 de los bytes de los ficheros del código (junto a `rutas.py`) más la versión de Python y la de su tabla
    Unicode: lo que decide qué sale de una línea. None si alguno no se puede leer: sin huella no hay marcapáginas."""
    h = hashlib.sha1()
    try:
        for nombre in nombres:
            with open(os.path.join(rutas.CODE, nombre), 'rb') as fh:
                h.update(fh.read())
    except OSError:
        return None
    h.update(f'{sys.version_info[0]}.{sys.version_info[1]} {unicodedata.unidata_version}'.encode('ascii'))
    return h.hexdigest()


def omitidas(mem):
    """Ids de `sesiones/.omitir`: de esas sesiones no se guarda nada aquí."""
    try:
        with open(os.path.join(mem, 'sesiones', '.omitir'), encoding='utf-8') as fh:
            return {l.strip() for l in fh if l.strip()}
    except Exception:
        return set()


def lineas_de(bloque):
    """Las líneas de un bloque de bytes, sin su salto, como las da el modo texto (UTF-8 con `errors='ignore'`,
    `\\r\\n` y `\\r` sueltos como salto). Si el bloque acaba en salto, el último elemento es ''."""
    return bloque.decode('utf-8', errors='ignore').replace('\r\n', '\n').replace('\r', '\n').split('\n')


def _es_json(texto):
    try:
        json.loads(texto)
        return True
    except Exception:
        return False


def _sha1(b):
    return hashlib.sha1(b).hexdigest()


def apuntar_fallo(mem, lector, sid, e):
    """Una línea en `mem/.marcapaginas/fallos.log` por cada fallo de la capa del estado (se vacía al pasar de 64 KB):
    sin marcapáginas cada llamada es más lenta, y así queda dicho por qué."""
    try:
        base = os.path.join(mem, rutas.MARCAPAGINAS)
        os.makedirs(base, exist_ok=True)
        ruta = os.path.join(base, 'fallos.log')
        modo = 'w' if os.path.exists(ruta) and os.path.getsize(ruta) > TOPE_LOG else 'a'
        with open(ruta, modo, encoding='utf-8') as fh:
            fh.write(f'{time.strftime("%Y-%m-%dT%H:%M:%S")} {lector} {str(sid)[:8]} {e.__class__.__name__}: {str(e)[:200]}\n')
    except Exception:
        pass


def olvidar(mem, sid):
    """Borra lo guardado de una sesión (su carpeta entera)."""
    if mem and sid:
        shutil.rmtree(os.path.join(mem, rutas.MARCAPAGINAS, sid), ignore_errors=True)


def barrer(mem, proj):
    """Quita de `mem/.marcapaginas/` las carpetas de sesiones omitidas, sin transcript en `proj`, sin tocar en
    HORAS_SIN_TOCAR, y todas menos las MAX_SESIONES más recientes; de las que quedan, los temporales y los cerrojos
    apartados de más de CERROJO_VIEJO_S (un proceso que murió a mitad). Devuelve cuántas carpetas quitó."""
    base = os.path.join(mem, rutas.MARCAPAGINAS)
    try:
        nombres = os.listdir(base)
    except OSError:
        return 0
    om = omitidas(mem); ahora = time.time(); vivas = []; n = 0
    for sid in nombres:
        carpeta = os.path.join(base, sid)
        if not os.path.isdir(carpeta):
            continue
        try:
            dentro = os.listdir(carpeta)
            tocada = max([os.path.getmtime(os.path.join(carpeta, f)) for f in dentro] + [os.path.getmtime(carpeta)])
        except OSError:
            continue
        if sid in om or not os.path.exists(os.path.join(proj, sid + '.jsonl')) or ahora - tocada > HORAS_SIN_TOCAR * 3600:
            shutil.rmtree(carpeta, ignore_errors=True); n += 1
            continue
        vivas.append((tocada, carpeta))
        for f in dentro:
            if f.endswith('.tmp') or '.lock.' in f:
                ruta = os.path.join(carpeta, f)
                try:
                    if ahora - os.path.getmtime(ruta) > CERROJO_VIEJO_S:
                        os.remove(ruta)
                except OSError:
                    pass
    for _, carpeta in sorted(vivas, reverse=True)[MAX_SESIONES:]:
        shutil.rmtree(carpeta, ignore_errors=True); n += 1
    return n


class Lectura:
    """Una lectura con marcapáginas del transcript de una sesión:

        l = Lectura.abrir(mem, proj, tp, sid, 'vigia', huella, tramos, ficheros=('crudo.txt',))
        if l is None: ...leer entero como siempre...
        estado = l.estado                  # el del lector donde se quedó, o None si se empieza de cero
        try:
            for linea in l.lineas_nuevas(): ...
            l.escribir('crudo.txt', texto)
            l.confirmar(estado_nuevo)      # datos, estado atómico, barrido
            ...abrir los datos confirmados mientras el cerrojo sigue cogido...
        finally:
            l.soltar()                     # suelta el cerrojo; sin confirmar, lo añadido se trunca en la próxima
    """

    def __init__(self):
        self.cerrojo = None
        self.cerrojo_cogido = False
        self.ficha = f'{os.getpid()} {os.urandom(8).hex()}'  # lo que se escribe en el cerrojo: de quién es
        self.datos = {}
        self.estado = None

    @classmethod
    def abrir(cls, mem, proj, tp, sid, lector, huella_lector, tramos, ficheros=()):
        if not (mem and proj and sid and tp and huella_lector) or str(tp).endswith('.gz') or not os.path.isfile(tp):
            return None
        if sid in omitidas(mem):
            return None
        l = cls()
        try:
            return l._abrir(mem, proj, tp, sid, lector, huella_lector, [list(t) for t in tramos], tuple(ficheros))
        except Exception as e:
            apuntar_fallo(mem, lector, sid, e)
            l.soltar()
            return None

    def _abrir(self, mem, proj, tp, sid, lector, huella_lector, tramos, ficheros):
        self.mem, self.proj, self.tp, self.sid, self.lector = mem, proj, tp, sid, lector
        self.huella, self.tramos, self.ficheros = huella_lector, tramos, ficheros
        self.carpeta = os.path.join(mem, rutas.MARCAPAGINAS, sid)
        os.makedirs(self.carpeta, exist_ok=True)
        self.cerrojo = os.path.join(self.carpeta, lector + '.lock')
        if not self._coger_cerrojo():
            return None
        guardado = self._leer_estado()
        with open(tp, 'rb') as fh:
            tam = os.fstat(fh.fileno()).st_size
            fin = self._ultimo_salto(fh, tam)
            offset = guardado.get('offset')
            valido = (guardado.get('huella') == huella_lector and guardado.get('tramos') == tramos
                      and isinstance(offset, int) and not isinstance(offset, bool) and 0 <= offset <= fin)
            cabeza = cola = b''
            if valido:
                fh.seek(0); cabeza = fh.read(min(TROZO, offset))
                ini = max(0, offset - TROZO); fh.seek(ini); cola = fh.read(offset - ini)
                valido = _sha1(cabeza) == guardado.get('cabeza') and _sha1(cola) == guardado.get('cola')
            longitudes = guardado.get('datos') if valido else None
            if valido:
                for nombre in ficheros:
                    n = (longitudes or {}).get(nombre)
                    ruta = os.path.join(self.carpeta, nombre)
                    if not isinstance(n, int) or not os.path.isfile(ruta) or os.path.getsize(ruta) < n:
                        valido = False
                        break
            fh.seek(fin)
            resto = fh.read(tam - fin)
        if resto and any(_es_json(linea) for linea in lineas_de(resto)):
            self.soltar()
            return None
        if not valido:
            offset = 0; cabeza = cola = b''; longitudes = {}
        for nombre in ficheros:
            f = open(os.path.join(self.carpeta, nombre), 'ab' if valido else 'wb')
            if valido:
                f.truncate(longitudes[nombre])
            self.datos[nombre] = f
        self.offset = self.procesado = offset
        self.fin = fin
        self.cabeza, self.cola = cabeza, cola
        self.estado = guardado.get('lector') if valido else None
        return self

    def _leer_ficha(self, ruta):
        try:
            with open(ruta, encoding='ascii', errors='replace') as fh:
                return fh.read()
        except OSError:
            return None

    def _coger_cerrojo(self):
        for _ in (0, 1):
            try:
                fd = os.open(self.cerrojo, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, self.ficha.encode('ascii'))
                os.close(fd)
                self.cerrojo_cogido = True
                return True
            except FileExistsError:
                try:
                    if time.time() - os.path.getmtime(self.cerrojo) <= CERROJO_VIEJO_S:
                        return False
                    # Un cerrojo viejo es de un proceso que murió. Se aparta con un nombre propio antes de borrarlo y
                    # se comprueba que lo apartado es lo que se vio viejo: si otro proceso lo rompió y cogió uno nuevo
                    # entre medias, se le devuelve y esta lectura se queda sin marcapáginas.
                    visto = self._leer_ficha(self.cerrojo)
                    apartado = f'{self.cerrojo}.{self.ficha.split()[1]}'
                    os.replace(self.cerrojo, apartado)
                    if visto is not None and self._leer_ficha(apartado) == visto:
                        os.remove(apartado)
                        continue
                    os.replace(apartado, self.cerrojo)
                except OSError:
                    pass
                return False
        return False

    def _leer_estado(self):
        try:
            with open(os.path.join(self.carpeta, self.lector + '.json'), encoding='utf-8') as fh:
                estado = json.load(fh)
            return estado if isinstance(estado, dict) else {}
        except Exception:
            return {}

    @staticmethod
    def _ultimo_salto(fh, tam):
        """Posición justo después del último `\\n` del fichero (0 si no hay ninguno)."""
        pos = tam
        while pos > 0:
            ini = max(0, pos - TROZO)
            fh.seek(ini)
            k = fh.read(pos - ini).rfind(b'\n')
            if k != -1:
                return ini + k + 1
            pos = ini
        return 0

    def lineas_nuevas(self):
        """Las líneas completas desde donde se quedó hasta el último `\\n` que había al abrir."""
        with open(self.tp, 'rb') as fh:
            fh.seek(self.offset)
            pendiente = self.fin - self.offset
            resto = b''
            while pendiente > 0:
                bloque = fh.read(min(BLOQUE, pendiente))
                if not bloque:
                    break
                pendiente -= len(bloque)
                datos = resto + bloque
                corte = datos.rfind(b'\n')
                if corte == -1:
                    resto = datos
                    continue
                trozo = datos[:corte + 1]
                resto = datos[corte + 1:]
                self._consumir(trozo)
                yield from lineas_de(trozo)[:-1]

    def _consumir(self, trozo):
        if len(self.cabeza) < TROZO:
            self.cabeza += trozo[:TROZO - len(self.cabeza)]
        self.cola = (self.cola + trozo)[-TROZO:]
        self.procesado += len(trozo)

    def escribir(self, nombre, texto):
        self.datos[nombre].write(texto.encode('utf-8', 'surrogatepass'))

    def confirmar(self, estado_lector):
        """Cierra los datos, escribe el estado de forma atómica (temporal con pid + `os.replace`) y barre, sin soltar el
        cerrojo: quien llama abre los datos confirmados antes de `soltar()`. Si la sesión entró en `.omitir` mientras
        se leía, la carpeta se borra en el acto. Devuelve True si datos y estado quedaron escritos; un fallo se apunta,
        no pasa de aquí y devuelve False (quien llama no debe fiarse de los datos)."""
        ruta = os.path.join(self.carpeta, self.lector + '.json')
        tmp = f'{ruta}.{os.getpid()}.tmp'
        bien = False
        try:
            longitudes = {}
            for nombre, f in self.datos.items():
                f.flush()
                longitudes[nombre] = os.fstat(f.fileno()).st_size
                f.close()
            self.datos = {}
            estado = {'offset': self.procesado, 'huella': self.huella, 'tramos': self.tramos,
                      'cabeza': _sha1(self.cabeza), 'cola': _sha1(self.cola), 'datos': longitudes,
                      'lector': estado_lector}
            with open(tmp, 'w', encoding='utf-8') as fh:
                json.dump(estado, fh, ensure_ascii=True)
            os.replace(tmp, ruta)
            bien = True
            if self.sid in omitidas(self.mem):
                shutil.rmtree(self.carpeta, ignore_errors=True)
        except Exception as e:
            apuntar_fallo(self.mem, self.lector, self.sid, e)
            self._cerrar_datos()
            try:
                os.remove(tmp)
            except OSError:
                pass
        try:
            barrer(self.mem, self.proj)
        except Exception as e:
            apuntar_fallo(self.mem, self.lector, self.sid, e)
        return bien

    def ruta_dato(self, nombre):
        return os.path.join(self.carpeta, nombre)

    def _cerrar_datos(self):
        for f in self.datos.values():
            try:
                f.close()
            except Exception:
                pass
        self.datos = {}

    def soltar(self):
        """Cierra lo que siga abierto y quita el cerrojo, solo si sigue siendo el suyo (lleva su ficha)."""
        self._cerrar_datos()
        if self.cerrojo_cogido:
            if self._leer_ficha(self.cerrojo) == self.ficha:
                try:
                    os.remove(self.cerrojo)
                except OSError:
                    pass
            self.cerrojo_cogido = False
