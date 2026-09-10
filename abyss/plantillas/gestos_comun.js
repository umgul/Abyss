/* ════════════════════════════════════════════════════════════════════════════
   EL VOCABULARIO DE LA MANO — LA COPIA QUE MANDA

   Decisión del usuario, 8-sep-2026. Hasta hoy la misma gramática vivía escrita TRES veces:
   en `abyss/gestos.py` (que la sirve por HTTP y hoy no la consume nadie), dentro de
   `abyss/plantillas/kinetica.html`, y aquí. Tres copias que ya habían divergido: solo
   ésta tenía las reglas nuevas —sin espejo, más lenta, dos puños paran—, y las otras dos
   seguían con las viejas sin que nadie lo notara.

   A partir de ahora manda ésta. Quien la quiera, la importa; nadie la vuelve a copiar.
   Lo que cada visor decide por su cuenta NO es el vocabulario: es qué mueve cada gesto en
   SU pantalla, y eso vive en cada visor.
   ════════════════════════════════════════════════════════════════════════════ */

/* Vocabulario de gestos COMÚN a los visores. Un solo sitio, para que los tres se muevan
   igual y para que corregir uno los corrija todos.

   ── Lo que decidió cómo es ──────────────────────────────────────────────────────
   · MUCHO más lento. Antes la ganancia estaba puesta a ojo y se acumulaba por fotograma:
     a 60 por segundo, un gesto pequeño se convertía en un barrido. Ahora el movimiento se
     mide POR SEGUNDO y las velocidades están abajo, con nombre, para poder tocarlas.
   · SIN ESPEJO. La imagen se ve en espejo, porque es lo natural al verse a uno mismo, pero
     el MANDO no: mover la mano a la derecha mueve a la derecha en la pantalla, como el
     ratón. La cámara mira de frente, así que la derecha de quien está delante cae en la
     x PEQUEÑA de la imagen: por eso `dirX = 0.5 - x`. Esa línea es la que hay que mirar
     si algún día se mueve al revés.
   · Zona muerta en el centro: la mano nunca está quieta del todo, y sin ella la pantalla
     se va sola.
   · Los dos puños NO apagan la cámara. La apagaban, y apagarla es una puerta de un solo
     sentido: para volver hay que ir al botón. Ahora paran, que es lo que se quiere
     cuando uno cierra las dos manos.

   ── El vocabulario ─────────────────────────────────────────────────────────────
     una mano, dedos hacia un lado ....... mueve la navegación en esa dirección
     dos manos, separándose o juntándose . acerca o aleja
     un puño ............................. frena; sostenido, abre lo que tengas delante
     DOS puños ........................... para en seco
*/

export const VEL_X = 1.30;     // anchos de pantalla por segundo, a fondo
export const VEL_Y = 1.60;
export const VEL_ZOOM = 0.55;
export const ZONA = 0.13;      // hay que salirse de este círculo para que se mueva
export const SEG_PUNO = 0.8;   // aguantar el puño esto abre
export const TOLERA_MALOS = 6; // fotogramas sueltos que se perdonan en un gesto sostenido

const RATIO = 1.7;             // dedo extendido: heredado, no medido aquí
const PARES = [[4, 2], [8, 5], [12, 9], [16, 13], [20, 17]];
export const d3 = (a, b) => Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z);
export const dedosExtendidos = p =>
  PARES.reduce((n, q) => n + (d3(p[q[0]], p[0]) > RATIO * d3(p[q[1]], p[0]) ? 1 : 0), 0);

/* Un filtro por coordenada, para que la mano no tiemble en la pantalla. */
export class UnEuro {
  constructor(mc = 1.0, b = 0.015, dc = 1.0) {
    this.mc = mc; this.b = b; this.dc = dc; this.x = null; this.dx = 0; this.t = null;
  }
  alfa(te, c) { const tau = 1 / (2 * Math.PI * c); return 1 / (1 + tau / te); }
  filtra(x, t) {
    if (this.x === null) { this.x = x; this.t = t; return x; }
    const te = Math.max(1e-3, (t - this.t) / 1000); this.t = t;
    const dx = (x - this.x) / te;
    this.dx = this.alfa(te, this.dc) * dx + (1 - this.alfa(te, this.dc)) * this.dx;
    const c = this.mc + this.b * Math.abs(this.dx);
    this.x = this.alfa(te, c) * x + (1 - this.alfa(te, c)) * this.x;
    return this.x;
  }
}

export function creaSuavizador() {
  const f = [[], []];
  return (mano, pts, t) => {
    if (!f[mano].length)
      for (let i = 0; i < 21; i++) f[mano].push([new UnEuro(), new UnEuro(), new UnEuro()]);
    return pts.map((p, i) => ({ x: f[mano][i][0].filtra(p.x, t),
                                y: f[mano][i][1].filtra(p.y, t),
                                z: f[mano][i][2].filtra(p.z, t) }));
  };
}

/* Una vara de esta sesión: percentiles con ancho mínimo. Por debajo de ese ancho la
   ventana no mide un gesto, amplifica el temblor, así que se ensancha en vez de afinar. */
export class Vara {
  constructor(pb = 5, pa = 95, minimo = 30, anchoMin = 0.38) {
    this.v = []; this.pb = pb; this.pa = pa; this.minimo = minimo; this.anchoMin = anchoMin;
  }
  mete(x) { if (isFinite(x)) { this.v.push(x); if (this.v.length > 900) this.v.shift(); } }
  get hay() { return this.v.length >= this.minimo; }
  corte(p) { const s = [...this.v].sort((a, b) => a - b);
             return s[Math.min(s.length - 1, Math.floor(p / 100 * (s.length - 1)))]; }
  ventana() {
    let lo = this.corte(this.pb), hi = this.corte(this.pa);
    if (!(hi > lo)) return null;
    const f = this.anchoMin - (hi - lo);
    if (f > 0) { lo -= f / 2; hi += f / 2; }
    return [lo, hi];
  }
  norm(x) { if (!this.hay) return 0.5; const w = this.ventana(); if (!w) return 0.5;
            return Math.max(0, Math.min(1, (x - w[0]) / (w[1] - w[0]))); }
  texto() {
    if (!this.hay) return 'sin vara todavía (n=' + this.v.length + ')';
    const w = this.ventana(); if (!w) return 'sin vara útil';
    const c = this.corte(this.pa) - this.corte(this.pb);
    return w[0].toFixed(3) + ' .. ' + w[1].toFixed(3)
         + (c < this.anchoMin ? ' (ensanchada: medida ' + c.toFixed(3) + ')' : '');
  }
}

/* Lee las manos de un fotograma y devuelve el mando, ya en unidades por segundo.
   `estado` es un objeto que el visor conserva entre fotogramas (guarda los relojes de los
   gestos sostenidos). Devuelve {dx, dy, zoom, dedos, manos, abrir, parar, avanceAbrir}. */
export function leerMando(manos, t, dt, estado, varaEscala) {
  const r = { dx: 0, dy: 0, zoom: 0, dedos: 0, manos: manos.length,
              abrir: false, parar: false, avanceAbrir: 0 };
  if (!manos.length) {
    estado.puno = null; estado.malos = 0;
    return r;
  }
  const p = manos[0];
  const nd = dedosExtendidos(p);
  r.dedos = nd;

  // ── mover: la mano fuera de la zona muerta empuja, y sigue empujando mientras aguante
  if (nd >= 2) {
    const dirX = 0.5 - p[9].x;      // SIN espejo: su derecha es la derecha de la pantalla
    const dirY = p[9].y - 0.5;      // hacia abajo en la imagen = bajar
    const mX = Math.hypot(dirX, 0), mY = Math.hypot(0, dirY);
    if (mX > ZONA) r.dx = Math.sign(dirX) * (Math.abs(dirX) - ZONA) * VEL_X * dt;
    if (mY > ZONA) r.dy = Math.sign(dirY) * (Math.abs(dirY) - ZONA) * VEL_Y * dt;
  }

  // ── dos manos: acercar y alejar por su separación
  if (manos.length === 2) {
    const sep = d3(manos[0][0], manos[1][0]);
    if (varaEscala) {
      varaEscala.mete(sep);
      if (varaEscala.hay && estado.sepAntes != null)
        r.zoom = (varaEscala.norm(sep) - varaEscala.norm(estado.sepAntes)) * VEL_ZOOM * 60 * dt;
    }
    estado.sepAntes = sep;
  } else estado.sepAntes = null;

  const nd2 = manos.length === 2 ? dedosExtendidos(manos[1]) : null;

  // ── los dos puños paran en seco, y mientras estén cerrados no se mueve nada
  if (manos.length === 2 && nd <= 1 && nd2 <= 1) {
    r.parar = true; r.dx = r.dy = r.zoom = 0;
    estado.puno = null;
    return r;
  }

  // ── un puño frena, y si se aguanta abre lo que haya delante. Cero o UN dedo: con el
  //    puño cerrado el pulgar sigue contando como extendido bastantes veces, y con la
  //    regla estricta no saltaba casi nunca
  if (manos.length === 1 && nd <= 1) {
    estado.malos = 0; r.parar = true; r.dx = r.dy = 0;
    estado.puno = estado.puno ?? t;
    r.avanceAbrir = Math.min(1, (t - estado.puno) / (SEG_PUNO * 1000));
    if (r.avanceAbrir >= 1) { r.abrir = true; estado.puno = null; }
  } else if (estado.puno != null) {
    if (++estado.malos > TOLERA_MALOS) { estado.puno = null; estado.malos = 0; }
  }
  return r;
}
