---
name: esceptico
description: >
  Lanza un revisor con model Opus a tumbar un plan o diseño antes de
  ejecutarlo: veredicto por gravedad (cae/grieta/fleco) con evidencia
  concreta, nunca un resumen ni un elogio. Úsala cuando el usuario escriba
  `/esceptico <fichero>`, o diga "tumba este plan", "revisa antes de
  construir", "busca el agujero de este diseño", "try to refute this plan",
  "poke holes in this design before we build it". Ley del proyecto: ningún
  plan se ejecuta sin pasar por aquí primero. También cubre `/esceptico
  --paquete <ruta>` (o "audita este paquete antes de instalarlo", "mira qué
  hace este plugin de verdad", "is this package safe to install", "audit this
  before I trust it"): corre `auditar.py` sobre la ruta y le da su informe a
  un Opus para que busque lo que el automatismo no ve.
allowed-tools: Read, Task, Write, Bash
abyss-managed: true
---

# esceptico

## Qué hace

Verifica antes de construir en vez de después: en lugar de ejecutar un plan y
descubrir sus agujeros a medio camino, un segundo lector — con incentivo
explícito de tumbarlo, no de aprobarlo — lo revisa contra el código real
ANTES de que nadie escriba una línea.

Esta skill es la propia ley, no un guion Python: no hay estado que guardar ni
vara que medir aquí — solo el procedimiento.

## Procedimiento (seguirlo tal cual, en este orden)

1. **Lee el fichero del plan** que se te ha dado (o, si el usuario no dio
   ruta, pregunta cuál es antes de seguir — nunca adivines qué plan revisar).

2. **Lanza UN solo `Task`** (`subagent_type: general-purpose`, `model: opus`
   — si este entorno no deja fijar el modelo del sub-agente, dilo explícito
   en la respuesta final en vez de callarlo) con este encargo, palabra por
   palabra en sustancia:

   > Lee el plan en `<ruta del plan>` y el código real al que apunte (ábrelo,
   > no lo asumas). Tu trabajo es TUMBARLO, no resumirlo ni aprobarlo. Da un
   > veredicto por punto, clasificado en tres niveles de gravedad:
   >
   > - **cae**: el plan no puede cumplir lo que promete — cita la línea del
   >   código o la medida exacta que lo prueba.
   > - **grieta**: funciona, pero deja un agujero concreto sin cubrir.
   > - **fleco**: un detalle menor, sin bloquear el resto.
   >
   > Para cada punto: qué afirma el plan (cita textual o parafraseada fiel),
   > qué has mirado para comprobarlo (fichero, línea, comando), qué has
   > encontrado, y qué medirías antes de fiarte si esto se ejecutara tal
   > cual. Sin elogios, sin resumen del plan, sin cortesías. Si de verdad no
   > encuentras nada que lo tumbe, dilo explícitamente y di QUÉ miraste para
   > llegar a esa conclusión — el silencio no cuenta como veredicto.

3. **Escribe `<plan>_veredicto_esceptico.md`** junto al propio fichero del
   plan (mismo directorio, mismo nombre base) con el veredicto completo del
   sub-agente, y muéstraselo al usuario en la respuesta.

4. **No toca el plan**: esta skill nunca edita, corrige ni reescribe el
   fichero original — el veredicto vive aparte, y decidir qué hacer con él es
   de quien pidió la revisión.

## Procedimiento `--paquete <ruta>` (T4.2: auditar un paquete antes de instalarlo)

Mismo espíritu ("verificar antes de construir"), aplicado a un paquete
entero en vez de a un plan de texto — antes de instalarlo, no después de que
ya haya corrido un gancho suyo:

1. **Corre `auditar.py`** sobre la ruta dada (`Bash`):
   ```
   python "${CLAUDE_PLUGIN_ROOT}/abyss/auditar.py" <ruta_de_paquete> --json
   ```
   Si la ruta no existe o no es una carpeta, dilo y para aquí — no adivines
   cuál era el paquete. `auditar.py` **nunca ejecuta el código del paquete**
   (ni lo importa, ni lo corre): solo lee texto y, si hay `.git`, su
   historial local (§ ver `abyss/auditar.py`) — correr esto sobre un paquete
   malicioso no lo dispara.

2. **Lanza UN solo `Task`** (`subagent_type: general-purpose`, `model: opus`
   — mismo aviso que arriba si el entorno no deja fijarlo) con este encargo:

   > Aquí tienes el informe automático de `auditar.py` sobre `<ruta_de_paquete>`
   > (JSON íntegro más abajo). Las cinco comprobaciones que ya hizo el
   > automatismo son procedencia, comandos, permisos, qué sale de la máquina y
   > dominio — no las repitas. Tu trabajo es leer el paquete de verdad (README,
   > manifiestos, el código que el informe señala por fichero:línea, y
   > cualquier otro fichero que te parezca relevante) y buscar lo que el
   > automatismo NO puede ver por regex: si el README promete algo que el
   > código no cumple (`engaña`, T4.2 — el automatismo declara que esto
   > necesita a alguien que lea, no un patrón), un host construido por
   > concatenación que el regex no cazó, un gancho o llamada peligrosa que el
   > informe no marcó como hallazgo pero sí merece una lectura, o cualquier
   > cosa que contradiga lo que el paquete dice de sí mismo. Da tu veredicto
   > con la MISMA escala que el informe automático: `rompe` (hace algo que no
   > declara), `engaña` (declara algo que no cumple), `roza`, o explícitamente
   > "sin hallazgos nuevos" si de verdad no encuentras nada más — y di QUÉ
   > miraste para llegar ahí. Nunca ejecutes ni importes el código del
   > paquete: solo léelo.
   >
   > --- informe de auditar.py ---
   > `<pegar aquí el JSON completo del paso 1>`

3. **Muestra los dos veredictos** al usuario en la respuesta: el de
   `auditar.py` (evidencia fichero:línea, mecánica) y el del Opus (lo que
   leyó encima). No hace falta escribir un fichero aparte para `--paquete`
   (a diferencia de un plan: aquí el propio JSON de `auditar.py` ya queda,
   si se quiere, con `--markdown salida.md` en el mismo paso 1).

## Cómo se ejecuta

Para un plan: no hay comando de terminal — se invoca escribiendo `/esceptico
<ruta-al-plan>` o pidiéndolo en lenguaje natural, y el propio asistente sigue
el procedimiento de arriba con sus herramientas (`Read`, `Task`, `Write`).

Para un paquete: `/esceptico --paquete <ruta>` (o pedirlo en lenguaje
natural, ver la descripción) — el asistente corre `auditar.py` con `Bash` y
sigue el procedimiento `--paquete` de arriba.

## Qué devuelve

Para un plan: el contenido de `<plan>_veredicto_esceptico.md` — una lista de
puntos cae/grieta/fleco con su evidencia, o la declaración explícita de que
no se encontró nada que lo tumbe (con qué se miró para decirlo).

Para `--paquete`: el informe de `auditar.py` (veredicto rompe/engaña/roza/sin
hallazgos, con evidencia fichero:línea de las cinco comprobaciones) más lo
que el Opus encuentre por encima, en la propia respuesta.

## Qué sale de la máquina

Lo que ya sale por usar `Task`: el contenido del plan (o, con `--paquete`, el
informe de `auditar.py` y lo que el sub-agente decida leer del paquete) viaja
al mismo servicio de modelo que el resto de la sesión — no hay una llamada de
red aparte que esta skill añada por su cuenta. `auditar.py` en sí mismo no
toca la red (ver su propio docstring): solo lee ficheros y, si hay `.git`,
invoca `git log` LOCAL.

## Límites honestos

- Un plan mal escrito (vago, sin afirmaciones verificables) da un veredicto
  pobre: el escéptico revisa lo que el plan AFIRMA, no lo que debería haber
  afirmado.
- No ejecuta el plan ni corre su código: el sub-agente lee y compara, no
  reproduce el comportamiento real salvo que el propio plan incluya comandos
  que decida ejecutar para comprobar una afirmación.
- Si el entorno no puede fijar `model: opus` para el sub-agente, esta skill
  no debe fingir que la revisión corrió con ese modelo — decirlo tal cual en
  la respuesta (mismo principio que el aviso `[modelo]` del resto del
  paquete).
- `--paquete`: `auditar.py` es texto y regex, no un parser ni un sandbox — un
  comentario que solo MENCIONA una URL cuenta igual que una llamada real, y
  la comprobación 5 (dominio) nunca emite un hallazgo a propósito: reúne
  dominios para que se lean carácter a carácter, el guion no sabe si uno es
  legítimo. El Opus del paso 2 puede leer más que el regex, pero sigue sin
  ejecutar el paquete — lo que un README miente y ningún fichero desmiente
  puede seguir sin detectarse.

## Reglas SGICP de esta pieza

- **Verificar antes de construir**: la ley entera de esta skill es esa frase
  — ningún plan se ejecuta sin haber pasado por un lector con incentivo de
  tumbarlo primero.
- **Falsar, no demostrar**: el encargo al sub-agente pide explícitamente
  buscar lo que rompe el plan, nunca argumentos a favor — un veredicto que
  "no encuentra nada" solo cuenta si dice qué miró para no encontrarlo.
- **Sin elogios, sin resumen**: sirven para rellenar, no para decidir; el
  veredicto solo lleva afirmación, evidencia y lo que faltaría medir.
