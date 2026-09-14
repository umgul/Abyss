---
name: modelo
description: >
  Avisa cuando Claude Code baja de modelo sin que el usuario lo elija (un
  safeguard que pasa la sesión a un modelo de reserva, o una sesión que se
  reanuda por debajo del modelo que llevaba el hilo) y, al salir de esa bajada,
  lista una vez los turnos respondidos durante ella para revisarlos. Úsala
  cuando el usuario pregunte qué modelo está respondiendo o pida revisar lo
  dicho durante un cambio: "qué modelo me está respondiendo", "he vuelto al
  modelo bueno, revisa lo que dijo el otro", "which model is answering right
  now", "I'm back on my model, check what the other one said". Sin gancho
  propio: corre como librería dentro de `continuidad.py --despertar`, en cada
  prompt.
allowed-tools: Bash
---

# modelo

## Qué hace

Lee el transcript de la sesión y solo avisa con prueba de un cambio
automático:

- **safeguard**: la primera respuesta del modelo de reserva trae un bloque
  `fallback` con el modelo de origen y el de reserva (o, en versiones que no lo
  escribían, la línea `system` `model_refusal_fallback`).
- **arranque**: tras reanudar o arrancar la sesión (la marca que deja un gancho
  SessionStart), la primera respuesta llega de un modelo por debajo del que
  llevaba el hilo, sin `/model` entre medias. Por debajo es de una familia
  inferior (mythos > fable > opus > sonnet > haiku) o de una generación anterior
  dentro de la misma (claude-opus-4-8 está por debajo de claude-opus-5).

Mientras dura, cada prompt lleva `[modelo] downgrade automático: …` con el
comando para volver al modelo de origen y el comando para quedarse con el de
reserva sin más avisos. Un `/model` hecho después del cambio lo da por decidido
por el usuario, elija el modelo que elija: **bajar a mano se permite**. Cuando
ya responde otro modelo que el de reserva, `[modelo · revisión]` lista una vez
los turnos respondidos durante la bajada, con lo que dijo el de reserva aunque
el turno lo acabara otro; quedarse con el de reserva no dispara revisión.

**Límite honesto de origen, no de esta pieza**: ningún gancho puede devolver la
sesión a otro modelo; el regreso siempre lo teclea la persona con `/model`.
Claude Code tiene un evento `PostModelSwitch` (aparece en transcripts de
2.1.255 a 2.1.260, siempre junto a un `/model`), pero no hay medida de si salta
con el selector, con un fallback o al reanudar, así que `modelo.py` no lo usa ni
lleva gancho propio: la detección ocurre dentro de `continuidad.py
--despertar`, que llama a `modelo.texto(tp)` en cada prompt.

## Cómo se ejecuta

Sin gancho propio: la detección ya corre sola dentro de `continuidad.py
--despertar`. A mano, para consultar el estado:

```
python "${CLAUDE_PLUGIN_ROOT}/abyss/modelo.py" --estado <transcript.jsonl> --proyecto "$(pwd)"
```

## Qué devuelve

`--estado` imprime el último modelo que respondió, la bajada automática activa
(de qué modelo a cuál, y si fue por safeguard o por arranque) o `ninguno`, y el
aviso vigente (o "(sin aviso)"). Una revisión pendiente se enseña sin gastarla:
la única vez que cuenta es la que inyecta `continuidad.py --despertar`.

## Qué sale de la máquina

Nada. Todo local: lee el transcript, guarda hasta dónde lo leyó en
`memory/.marcapaginas/<id>/modelo.json` y la hora del último turno revisado en
`memory/.modelo_revisado/<id>`.

## Límites honestos

- Solo detecta y avisa; nunca vuelve el modelo automáticamente.
- Un cambio que no deja rastro en el transcript (sin `/model`, sin fallback,
  sin marca de sesión; los hay en versiones 2.1.219–2.1.237) no avisa: nada
  dice si fue a mano o automático.
- El aviso de arranque necesita que algún gancho SessionStart deje su marca en
  el transcript (el de `continuidad.py --arranque`, instalado junto al
  `--despertar` que llama a este módulo, ya la deja) y llega en el prompt
  SIGUIENTE a la primera respuesta: al enviar el primero aún no ha respondido
  nadie. Una sesión nueva
  no sabe con qué modelo iba otro hilo. Si la app escribiera un `/model` por su
  cuenta al reanudar, contaría como elección del usuario.
- `<synthetic>` (errores de la API, límites de uso) no es un modelo: no cuenta.
- Sin gancho propio: si nadie escribe un prompt (`UserPromptSubmit`), no hay
  ocasión de detectar el cambio — se entera en el SIGUIENTE mensaje, no al
  instante en que ocurre.
- Lo dicho dentro de un tramo de `parentesis` no vuelve en `[modelo · revisión]`;
  los sucesos de modelo de dentro del tramo (fallback, `/model`) sí cuentan,
  porque no llevan texto del usuario.

## Reglas SGICP de esta pieza

- **Ley o medida, nunca estado**: no dice "el modelo empeoró" — dice qué modelo
  respondió, de cuál venía y qué rastro del transcript lo prueba.
- **Fail-closed**: como librería, si no puede resolver el proyecto no revienta
  a quien la llama — se pierde el aviso de ese turno, nunca se inventa uno.
  Ejecutado a mano, si falla la resolución del proyecto, avisa claro por stderr.
