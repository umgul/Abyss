---
name: parentesis
description: >
  Marca un tramo de la conversación (o una sesión entera) para que no entre en
  la memoria futura, y recorta el transcript local ya cerrado. Actívala con:
  "esto no lo metas en tu memoria", "esto es un paréntesis", "elimina todo el
  rato que hemos hablado de X", "no guardes esta sesión", "don't remember
  this", "keep this off the record", "forget this part of the conversation".
  Nunca por gancho — solo cuando el usuario lo pide en ese turno.
allowed-tools: Bash
---

# parentesis

## Qué hace

Dos mecanismos distintos, y uno más bruto:

1. **Tramo por sesión** (`--abrir`/`--cerrar`): marca un inicio y un fin en
   `memory/parentesis.json`. No borra nada del transcript: hace que lo de
   dentro del tramo deje de ENTRAR en lo que este paquete vuelve a leer —
   `continuidad.py` copia la sesión a `sesiones/` saltando esas líneas, y las
   bolsas de palabras/la sala de los relojes heredan el filtro porque se
   construyen sobre lo mismo. Un tramo abierto y nunca cerrado se trata como
   abierto hasta el cierre de la sesión (nada se escapa por descuido).
2. **Sesión entera** (`--omitir-sesion`): la sesión completa nunca se copia a
   `sesiones/`, ni aunque la cierre otro hilo distinto.
3. **Corte del fichero local** (`--recortar`/`--recortar-tramo`): reescribe de
   verdad el `.jsonl` que usa la propia app de Claude Code para reconstruir el
   hilo, con una copia `.antes` del original. Solo tiene sentido con el hilo
   YA cerrado — si sigue vivo, la app puede volver a escribir encima.

## Cómo se ejecuta

```
python "${CLAUDE_PLUGIN_ROOT}/abyss/parentesis.py" --abrir [motivo] --proyecto "$(pwd)"
python "${CLAUDE_PLUGIN_ROOT}/abyss/parentesis.py" --cerrar --proyecto "$(pwd)"
python "${CLAUDE_PLUGIN_ROOT}/abyss/parentesis.py" --omitir-sesion [id] --proyecto "$(pwd)"
python "${CLAUDE_PLUGIN_ROOT}/abyss/parentesis.py" --recortar <transcript.jsonl> "<último mensaje del usuario que se conserva>" --proyecto "$(pwd)"
python "${CLAUDE_PLUGIN_ROOT}/abyss/parentesis.py" --recortar-tramo <transcript.jsonl> <inicio_iso> <fin_iso> --proyecto "$(pwd)"
```

Uso por el asistente: cuando el usuario lo pide, `--abrir`; al cambiar de
tema (o cuando el usuario dice que ya puede seguir grabándose), `--cerrar`; al
cerrar el hilo, si el usuario lo pidió explícitamente, `--recortar`. Nunca por
iniciativa propia sin que el usuario lo haya dicho en ese turno.

`--recortar`/`--recortar-tramo` se niegan (código 1, no tocan nada) si el hilo
sigue vivo (latido de menos de 2 minutos): la app puede estar a punto de
volver a escribir sobre ese mismo `.jsonl`. `--recortar` exige que el mensaje
dado coincida EXACTO (tras normalizar espacios) con algún mensaje real del
usuario en ese transcript — si no lo encuentra, no toca nada y lo dice.

## Qué devuelve

Confirmación por stdout de qué se marcó o recortó; código 1 y un mensaje claro
si se rehúsa (hilo vivo, mensaje no encontrado).

## Qué sale de la máquina

Nada. Todo local: `memory/parentesis.json`, `memory/sesiones/.omitir`, y el
propio `.jsonl` que se recorte (con su copia `.antes`).

## Límites honestos

- **No puede deshacer lo ya enviado**: dentro de un turno en curso, lo que ya
  viajó a la API de Anthropic YA VIAJÓ — ninguna herramienta local puede
  deshacerlo. Esto gobierna la memoria LOCAL de este paquete (lo que el propio
  asistente vuelve a leer en hilos futuros), no los servidores de Anthropic.
- Quien respeta el tramo (`parentesis.en_parentesis()`), medido y probado:
  `continuidad.guardar()`/`frases_usuario()`, la sala de relojes y las bolsas
  (heredado de `frases_usuario()`), `vigia.leer_turno()` (no lo usa como
  evidencia ni lo guarda en `confabulaciones.jsonl`), `propiocepcion.medir()`,
  `varas.py --index` (una lectura de una ficha hecha dentro del tramo no
  cuenta como uso, no le sube el ◆) y `modelo.recorrer()` (un turno respondido
  por otro modelo dentro del tramo no se reinyecta en el aviso
  `[modelo · revisión]` de `continuidad.py --despertar`).
- `--recortar`/`--recortar-tramo` solo aceptan `.jsonl` sin comprimir (el
  transcript vivo que usa la app nunca está gzipeado).

## Reglas SGICP de esta pieza

- **Fail-closed, nunca a medias**: `--recortar`/`--recortar-tramo` se niegan
  enteros (código 1) ante un hilo vivo o un mensaje que no encuentran, en vez
  de recortar "lo que se pueda" y dejar el transcript en un estado incierto.
- **La heurística se dice como heurística**: sin `--sesion` explícito, resolver
  de qué sesión se habla usa el hilo con el latido más reciente — con varios
  hilos mandando prompts a la vez de verdad podría acertar el equivocado; por
  eso `--sesion` explícito siempre gana si se da.
