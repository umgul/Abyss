---
name: esceptico
description: >
  Lanza un revisor con model Opus a tumbar un plan o diseño antes de
  ejecutarlo: veredicto por gravedad (cae/grieta/fleco) con evidencia
  concreta, nunca un resumen ni un elogio. Úsala cuando el usuario escriba
  `/esceptico <fichero>`, o diga "tumba este plan", "revisa antes de
  construir", "busca el agujero de este diseño", "try to refute this plan",
  "poke holes in this design before we build it". Ley del proyecto: ningún
  plan se ejecuta sin pasar por aquí primero.
allowed-tools: Read, Task, Write
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

## Cómo se ejecuta

No hay comando de terminal: se invoca escribiendo `/esceptico <ruta-al-plan>`
o pidiéndolo en lenguaje natural. El propio asistente sigue el procedimiento
de arriba con sus herramientas (`Read`, `Task`, `Write`).

## Qué devuelve

El contenido de `<plan>_veredicto_esceptico.md`: una lista de puntos
cae/grieta/fleco con su evidencia, o la declaración explícita de que no se
encontró nada que lo tumbe (con qué se miró para decirlo).

## Qué sale de la máquina

Lo que ya sale por usar `Task`: el contenido del plan y del código que se le
pase al sub-agente viaja al mismo servicio de modelo que el resto de la
sesión — no hay una llamada de red aparte que esta skill añada por su cuenta.

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

## Reglas SGICP de esta pieza

- **Verificar antes de construir**: la ley entera de esta skill es esa frase
  — ningún plan se ejecuta sin haber pasado por un lector con incentivo de
  tumbarlo primero.
- **Falsar, no demostrar**: el encargo al sub-agente pide explícitamente
  buscar lo que rompe el plan, nunca argumentos a favor — un veredicto que
  "no encuentra nada" solo cuenta si dice qué miró para no encontrarlo.
- **Sin elogios, sin resumen**: sirven para rellenar, no para decidir; el
  veredicto solo lleva afirmación, evidencia y lo que faltaría medir.
