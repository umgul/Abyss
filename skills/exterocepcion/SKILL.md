---
name: exterocepcion
description: >
  Lugar (por IP y por lo dicho en la conversación), meteo del lugar, y canal de
  entrada del último mensaje — instrumentos de fuera, nunca inventados. Úsala
  cuando el usuario pregunte dónde está el asistente situado, qué tiempo hace, o
  diga dónde está él: "¿qué hora es y dónde estoy?", "qué tiempo hace ahí",
  "estoy en Madrid", "he llegado a Barcelona", "what time is it and where am I",
  "what's the weather like there", "I'm in Paris now". No la dispara ningún
  gancho propio — la usa `continuidad.py` en `--arranque`/`--despertar` — pero
  puede ejecutarse a mano para refrescar el lugar por IP o registrar lo dicho.
allowed-tools: Bash
---

# exterocepcion

## Qué hace

Dos instrumentos de lugar, mostrados los dos si discrepan (no decide el
asistente cuál es cierto):

- **`ip`**: geolocalización por IP (`ipinfo.io`), se refresca en cada arranque de
  sesión.
- **`dicho`**: lo que el usuario dice en la conversación ("estoy en Madrid",
  "desde París", "he llegado a la torre Eiffel"); se geocodifica con
  `open-meteo.com` si parece una ciudad, o `nominatim.openstreetmap.org` si no,
  y se guarda con hora. Gana el más reciente en la lectura principal; el otro se
  muestra si discrepa.

Con el lugar principal, **meteo** consulta `open-meteo.com` (cache 15 min, sin
clave). **Canal** lee `entrypoint`/`origin.kind` del último mensaje del
transcript (hoy solo se ha visto `claude-desktop`).

La webcam (**ojo**) es un instrumento aparte — ver la skill `ojo` — y nunca se
mezcla con esto.

## Cómo se ejecuta

```
python "${CLAUDE_PLUGIN_ROOT}/abyss/exterocepcion.py" --proyecto "$(pwd)"                     # texto [mundo] actual
python "${CLAUDE_PLUGIN_ROOT}/abyss/exterocepcion.py" --refrescar-ip --proyecto "$(pwd)"       # fuerza refresco de lugar por IP
python "${CLAUDE_PLUGIN_ROOT}/abyss/exterocepcion.py" --dicho "estoy en Sevilla" --proyecto "$(pwd)"
```

## Qué devuelve

Una línea `[mundo] lugar … · meteo … · canal …`, o "lugar sin dato (sin red)" /
"meteo sin dato (sin red o API caída)" cuando la red o la API fallan — nunca un
valor puesto a mano en su lugar.

## Qué sale de la máquina

La IP del usuario viaja a `ipinfo.io`; el nombre de ciudad dicho por el usuario
(o de donde se geocodifique) viaja a `open-meteo.com` y, si hace falta,
`nominatim.openstreetmap.org`; la lat/lon del lugar principal viaja a
`open-meteo.com` para el tiempo. Ningún otro dato de la conversación sale por
aquí. No se lee ninguna otra aplicación de mensajería para inferir el lugar:
eso robaría mensajes escritos para otra persona.

## Límites honestos

- El lugar por IP puede equivocarse de ciudad (VPN, redes móviles) y solo se
  refresca al arrancar una sesión.
- "Lo dicho" solo reconoce un patrón fijo de fórmulas ("estoy en…", "he
  llegado a…", "desde…") — cualquier otra forma de decir dónde se está no se
  captura.
- Sin red, cada instrumento falla por su cuenta y dice "sin dato"; no hay caso en
  que uno se invente para rellenar el hueco del otro.

## Reglas SGICP de esta pieza

- **Fail-closed, nunca inventar**: sin red o con la API caída, la respuesta es
  siempre "sin dato", nunca un valor puesto a mano ni el último dato cacheado
  presentado como si fuera fresco.
- **Ley o medida**: el lugar y el meteo son lecturas directas de un instrumento
  externo, no una inferencia — cuando hay dos lecturas que discrepan (IP vs.
  dicho), se muestran las dos en vez de que el asistente elija una.
