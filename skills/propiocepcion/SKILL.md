---
name: propiocepcion
description: >
  Mide una sesión de Claude Code desde su propio transcript (horas, turnos,
  herramientas, tokens, correcciones) y da su percentil contra todas las sesiones
  medidas del proyecto — nunca un juicio como "sesión intensa". Úsala cuando el
  usuario pregunte por el esfuerzo de la sesión actual o pasada: "cómo de larga
  fue esta sesión comparada con las demás", "en qué percentil cae esta sesión",
  "how demanding was this session", "compare this session to my other threads".
  No la dispara ningún gancho por sí sola: la usan `continuidad.py` y `varas.py`
  como librería, o se ejecuta a mano.
allowed-tools: Bash
---

# propiocepcion

## Qué hace

Recorre un transcript `.jsonl`/`.jsonl.gz` y mide, sin interpretar: horas entre
primer y último timestamp, turnos del usuario, palabras del usuario, número de
respuestas, llamadas a herramientas, tokens de salida, tokens pensados, tokens de
caché leídos, usos de `WebSearch`/`WebFetch`, y un proxy tosco de "correcciones"
(mensajes del usuario que empiezan negando o corrigiendo: "no", "mal", "eso no",
"te equivocas"…). Guarda todo en `memory/propiocepcion.json` y da, para una
sesión dada, su percentil contra todas las sesiones medidas hasta ese momento en
cada una de esas claves.

## Cómo se ejecuta

```
python "${CLAUDE_PLUGIN_ROOT}/abyss/propiocepcion.py" --proyecto "$(pwd)"                 # la sesión más reciente
python "${CLAUDE_PLUGIN_ROOT}/abyss/propiocepcion.py" <id-de-sesion> --proyecto "$(pwd)"  # una sesión concreta
```

El módulo resuelve `proj`/`mem` **al importarse** (no solo en `__main__`), así que
`--proyecto <cwd>` o `ABYSS_PROYECTO` hacen falta incluso si otro guion lo importa
como librería fuera del contexto de un gancho.

## Qué devuelve

Reescribe `memory/propiocepcion.json` (un diccionario por id de sesión con las
claves de arriba) e imprime por stdout la sesión pedida contra la distribución:
valor, mediana y percentil por clave — o "sin vara todavía (n=…)" si no hay
corpus suficiente.

## Qué sale de la máquina

Nada. Todo local: solo lee transcripts de `memory/sesiones/` (y del proyecto) y
escribe `propiocepcion.json`.

## Límites honestos

- El proxy de "corrección" es un patrón de texto tosco sobre el arranque del
  mensaje: cuenta falsos positivos ("no sé si...") y se pierde correcciones
  formuladas de otra manera. Se declara como proxy, no como verdad.
- "Fichas escritas" solo ve `Write`/`cat >>` hacia rutas con `memory` en el
  nombre: un guardado por otra vía no deja huella aquí.
- No mide nada subjetivo — no hay campo "cansancio" ni "ánimo"; si el usuario
  pregunta eso, la respuesta correcta es remitir a los números de esta medida y
  decir que no hay instrumento para lo demás.

## Reglas SGICP de esta pieza

- **Ley o medida, nunca estado**: nunca digas "esta sesión fue dura" a partir de
  esto — di el número (horas, turnos, tokens) y el percentil que ocupa.
- **Cortes por cuantiles**: el percentil es siempre contra la distribución
  *actual* de todas las sesiones medidas, que rota con cada sesión nueva; no hay
  un valor de referencia congelado.
- **Arranque en frío**: con menos de `UMBRAL_FRIO` = 8 sesiones medidas,
  `percentiles()` devuelve `None` en vez de inventar un percentil sobre un
  puñado de puntos que no significan nada. Repite "sin vara todavía (n=…)" tal
  cual si es lo que sale — no lo redondees a un número.
