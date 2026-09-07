---
name: modelo
description: >
  Detecta si Claude Code está respondiendo con un modelo distinto del
  preferido (downgrade por un safeguard) y, al volver, marca los turnos
  respondidos por el otro modelo para revisarlos una vez. Úsala cuando el
  usuario pregunte qué modelo está respondiendo o pida revisar lo dicho durante
  un cambio: "qué modelo me está respondiendo", "he vuelto al modelo bueno,
  revisa lo que dijo el otro", "which model is answering right now", "I'm back
  on my preferred model, check what the other one said". Sin gancho propio:
  corre como librería dentro de `continuidad.py --despertar`, en cada prompt.
allowed-tools: Bash
---

# modelo

## Qué hace

Compara el modelo que respondió el último turno (leído del transcript) contra
`memory/modelo_preferido.json` (el último modelo que el usuario fijó con
`/model`). Si el modelo activo no es el preferido, añade un aviso `[modelo]`
con el comando exacto para volver. Si el usuario **acaba de volver** al
preferido y hubo turnos respondidos por otro modelo mientras tanto, añade una
vez `[modelo · revisión]` listando esos turnos para que se repasen — volver al
preferido es la ocasión de revisar lo dicho por el otro.

**Límite honesto de origen, no de esta pieza**: no existe forma de que un gancho
devuelva la sesión al modelo preferido por sí solo, y Claude Code no tiene
ningún evento que observe un cambio de modelo desde dentro de la sesión (los
eventos reales son PreToolUse, PostToolUse, Stop, SubagentStop, SessionStart,
SessionEnd, UserPromptSubmit, PreCompact, Notification — no existen
«PostModelSwitch» ni «PreModelSwitch»). Por eso `modelo.py` no lleva gancho
propio: la detección ocurre dentro de `continuidad.py --despertar`, que ya
llama a `modelo.texto(tp)` en cada prompt. El regreso siempre lo teclea la
persona con `/model`.

## Cómo se ejecuta

Sin gancho propio: la detección ya corre sola dentro de `continuidad.py
--despertar`. A mano, para consultar el estado:

```
python "${CLAUDE_PLUGIN_ROOT}/abyss/modelo.py" --estado --proyecto "$(pwd)"
```

## Qué devuelve

`--estado` imprime el modelo preferido, el modelo actual, y el aviso vigente (o
"(sin aviso)").

## Qué sale de la máquina

Nada. Todo local: lee el transcript y escribe `modelo_preferido.json`.

## Límites honestos

- Solo detecta y avisa; nunca vuelve el modelo automáticamente.
- La comparación es exacta contra el nombre guardado, sin inferencia de
  familias "parecidas" más allá de la lista fija de nombres considerados
  equivalentes al preferido.
- Sin gancho propio: si nadie escribe un prompt (`UserPromptSubmit`), no hay
  ocasión de detectar el cambio — se entera en el SIGUIENTE mensaje, no al
  instante en que ocurre.

## Reglas SGICP de esta pieza

- **Ley o medida, nunca estado**: no dice "el modelo empeoró" — dice qué modelo
  respondió cada turno, comparado exactamente con lo que el usuario fijó.
- **Fail-closed**: como librería, si no puede resolver el proyecto no revienta
  a quien la llama — se pierde el aviso de ese turno, nunca se inventa uno.
  Ejecutado a mano, si falla la resolución del proyecto, avisa claro por stderr.
