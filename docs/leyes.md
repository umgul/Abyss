# Leyes del SGICP propio

Destilado de las fichas de diseño originales, que no se publican por ser notas personales
del autor (con su fecha y su voz en primera persona). Aquí solo las leyes, secas, y qué
pieza del paquete mide cada una. No son buenas prácticas genéricas: son las reglas concretas
que este código cumple o, si no puede, dice que no mide en vez de inventar.

## 1 · Ley o medida, nunca estado

Ninguna pieza declara cómo "está" el hilo (cansado, contento, con prisa). O hay un
instrumento que mide algo del transcript, o hay una regla fija que se aplica igual siempre
(una ley), o no hay nada que decir. No existe una tercera cosa que se decrete a ojo.

- `propiocepcion.py` no dice "vas cansado": dice cuántas horas, turnos, herramientas y
  tokens tuvo la sesión, y en qué percentil cae contra las demás.
- `vigia.py` no juzga "esto es mentira": caza números, rutas y citas que no aparecen en
  la evidencia (lo que dijo el usuario o devolvió una herramienta) y deja la corrección a
  quien escribió la respuesta.
- Las frases en primera persona sobre el propio estado ("me alegra", "tengo ganas") se
  cuentan como *estados sin vara* — no se prohíben (son actos de habla), pero tampoco se
  toman como medida de nada.

## 2 · Cortes por cuantiles, nunca umbrales fijos

Ninguna pieza compara contra un número puesto a mano. Cada corte sale de la propia
distribución acumulada hasta ese momento, y se recalcula cada vez que hay datos nuevos
("normales que rotan").

- `varas.py` reparte ◆/◆◆/◆◆◆ por el decil y los tramos de la distribución de uso
  medido de las fichas — no por un número de citas fijo.
- `propiocepcion.py` da el percentil de la sesión actual contra todas las sesiones
  medidas hasta hoy, no contra un valor de referencia congelado.
- `continuidad.py` (la sala de los relojes) despierta un reloj solo si su parecido queda
  por encima de la media + 1 desviación típica *de ese prompt en concreto*, nunca de un
  número absoluto.

## 3 · El nulo como suelo

Antes de que una vara pueda decir "esto destaca", tiene que saber cuánto vale el ruido de
fondo: qué puntuación alcanzan frases que no tienen nada que ver con el proyecto. Ese techo
del ruido (el "nulo") es el suelo por debajo del cual nunca se dispara nada, y se recalcula
con el corpus — no es una constante escrita una vez y olvidada.

- `continuidad.py` mantiene una lista fija de frases ajenas al proyecto (recetas, fútbol,
  hipotecas…) y usa 1,5× el parecido máximo que alcanzan contra las sesiones guardadas
  como suelo de la sala de los relojes. Se recalcula en cada cosecha (`hacer_bolsas`).
- `noticias.py` exige que un tema automático supere ese mismo suelo antes de admitirlo:
  que sus titulares se parezcan a las conversaciones reales, no solo que existan.

## 4 · Cazar lo que no salió de ninguna parte

El vigía no detecta mentiras: detecta ausencia de fuente. Un número, una ruta o una cita
entre «» que no aparece ni en lo que dijo el usuario ni en lo que devolvió una herramienta
en toda la sesión es, por definición, algo que no vino de ningún sitio verificable — se
haya inventado o se haya calculado sin enseñar el cálculo.

- `vigia.py --verificar` (gancho `Stop`) hace exactamente esa comparación y bloquea el
  cierre del turno la primera vez que encuentra algo así, para que se reescriba.
- Las citas entre «» se dividen en dos tipos porque no pesan igual: `cita` (hay un verbo
  de atribución cerca — alguien la habría dicho así de verdad) y `parafrasis` (comillas de
  estilo o traducción, sin ese texto exacto en la evidencia).
- Límite declarado: esto no juzga afirmaciones sin número ni cita — ahí no llega — y un
  número que por casualidad aparece en cualquier salida de herramienta se da por cubierto
  aunque no tenga relación real (falso negativo conocido).

## 5 · Una vara sin varianza no mide

Una vara que nunca se ha puesto a prueba no tiene precisión: tiene silencio. Si nadie ha
usado nunca el mecanismo de descargo, decir "acierto 100%" no significa que la vara sea
perfecta, significa que nadie ha mirado si se equivoca.

- `vigia.py --precision` compara cazas totales contra descargos (`--descargo`); con cero
  descargos dice explícitamente "sin vara" en vez de imprimir un 1.00 engañoso.
- Corolario del arranque en frío (§2.2 de `ESPECIFICACION.md`): con menos de
  `propiocepcion.UMBRAL_FRIO` (8) sesiones medidas no hay corpus con el que comparar, así
  que `propiocepcion.percentiles()` devuelve `None`, `varas.py --index` no pone ningún ◆
  y la sala de los relojes no despierta nada. Fail-closed: nunca se inventa un percentil
  sobre una distribución que casi no existe.

## 6 · Falsar antes de fiarse

Ninguna vara nueva se activa sin probarla primero contra datos reales y contra el nulo.

- La sala de los relojes se probó con leave-one-out (`continuidad.py --falsar`): la
  primera frase de cada sesión contra las bolsas sin esa frase, y contra frases ajenas
  nuevas que nunca deberían despertar nada.
- Los temas automáticos de `noticias.py` pasaron por cinco mediciones sucesivas antes de
  activarse (cada una destapó un ruido distinto: jerga interna, fragmentos de rutas de
  Windows, cabeceras de resúmenes de compactación) y la relevancia final exige superar el
  suelo del nulo, no solo "dar dos titulares".

## Qué mide cada pieza (resumen)

| Pieza | Qué mide o vigila | Con qué vara |
|---|---|---|
| `propiocepcion.py` | Esfuerzo de una sesión (horas, turnos, herramientas, tokens, correcciones) | Percentil contra las demás sesiones; `None` en frío |
| `varas.py` | Peso de uso real de cada ficha de memoria (citas + lecturas) | Cuantiles de la distribución de uso actual |
| `continuidad.py` (sala) | Parecido entre el prompt y sesiones pasadas | Coseno TF-IDF sobre el suelo del nulo + media/σ del prompt |
| `vigia.py` | Números/rutas/citas de la propia respuesta sin fuente verificable | Presencia en la evidencia (usuario + herramientas); precisión por descargos |
| `modelo.py` | Si se está respondiendo fuera del modelo preferido | Comparación exacta contra `modelo_preferido.json`, sin inferencia |
| `noticias.py` (temas auto) | Si un nombre propio recurrente merece ser tema de prensa | Frecuencia por sesión + parecido de sus titulares sobre el suelo del nulo |

## Piezas de la segunda tanda

No todas miden contra una vara con cuantiles — algunas aplican una regla fija
(ley) o transforman sin medir nada (una herramienta de manos). La tabla dice
cuál es cuál, y qué NO promete cada una — la misma honestidad de arriba, dicha
del lado de lo que no llega a ser una vara.

| Pieza | Qué hace | Mide o aplica | Qué NO promete |
|---|---|---|---|
| `parentesis.py` | Marca un tramo (o una sesión) para que no entre en memoria futura | Ley: filtra por marca de tiempo, nunca borra lo ya enviado | No deshace lo que ya viajó a la API dentro de un turno |
| `huella.py` | Registra ficheros/procesos/puertos que un hilo toca fuera de su carpeta | Mide el coste (ms) de su propia foto y decide su heurística de cuándo repetirla contra SU mediana, no un número fijo | No ve lo que otro programa (no este hilo) dejó abierto; guarda el TEXTO de cada comando de Bash/PowerShell (recortado a 200 caracteres, en local) — si sueles pasar claves por línea de comandos, quedarán ahí; `--limpiar --si` solo borra bajo temp/ o bajo una subcarpeta que él mismo genera en `mem` (`huella/`, `mapas/`, `pdf/`) — nunca `MEMORY.md` ni una ficha `*.md`; APAGADO por defecto solo vía `instalar.py`, encendido si se instala el plugin entero |
| `cuerpo.py` | El cuerpo de la máquina (cpu/ram/disco/vram/temp/batería) | Cuantiles p5/p50/p95 del propio historial, arranque en frío con `UMBRAL_FRIO`=8 igual que `propiocepcion.py` | Nunca ordena nada (no cierra procesos, no baja de modelo): mide, no decide; los seis canales se muestran en `SessionStart`, pero `UserPromptSubmit` solo vigila cinco — la batería no, porque su propia oscilación normal al (des)enchufar la sacaría de su p5 cada vez |
| `lector_pdf.py` | Indexa un PDF por página/sección y busca por TF-IDF | Mide caracteres leídos vs. PDF entero (`--ahorro`), sin vara de cuantiles | El ahorro es de LECTURA, no de calidad de respuesta — eso pide un A/B no hecho |
| `mapa_codigo.py` | Índice greppable de un repo Python con `ast` | Mide líneas de mapa vs. líneas de código (proporción), sin vara de cuantiles | No mide si el mapa BASTA para entender el código — solo cuánto pesa frente al código |
| `esceptico` (skill) | Ley «ningún plan sin escéptico»: un revisor Opus busca lo que tumba un plan | Ley: veredicto por gravedad (cae/grieta/fleco) con evidencia citada, nunca un resumen ni un elogio | No ejecuta el plan; si el entorno no fija `model: opus`, debe decirlo, no callarlo |
| `infografia.py` | CSV/JSON a SVG limpio | Transforma sin medir: ticks 1-2-5 de la propia escala de los datos | No elige el tipo de gráfico ni rasteriza a PNG |
| `lienzo.py` | Operar con imágenes reales (fundir, collage, restaurar, pintar por números, borrar) | Mide contraste/ruido antes-después en `restaurar`; el límite de `borrar` sin taller está medido en su prueba (error bajo la mitad del inicial) | No genera nada nuevo ni entiende la escena — son operaciones deterministas sobre los píxeles dados |
| `taller.py` | Servidor local mínimo de texto→imagen (boquilla A1111) | Aplica: sirve `txt2img`, nada más | No mide VRAM sin GPU real que medir; no implementa `img2img` con máscara todavía |
