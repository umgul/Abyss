---
name: ojo
description: >
  Un fotograma de la webcam, solo cuando el usuario lo pide explícitamente en
  ese turno: "mira por la webcam", "haz una foto con la cámara", "qué ves por la
  cámara ahora mismo", "look through the webcam", "take a picture with the
  camera", "what do you see through the camera right now". Nunca se dispara por
  gancho ni por iniciativa propia del asistente — una cámara que se enciende
  sola no es un ojo, es vigilancia.
allowed-tools: Bash
---

# ojo

## Qué hace

Abre la cámara indicada (por defecto la 0), descarta los primeros fotogramas
(la exposición tarda en ajustarse) y guarda uno como `.jpg`. Requiere OpenCV
(`cv2`), una dependencia **opcional** del paquete — sin ella, imprime
"sin cv2: no hay ojo" y sale con código 1, sin hacer nada más.

## Cómo se ejecuta

```
python "${CLAUDE_PLUGIN_ROOT}/abyss/ojo.py" [ruta_salida.jpg] [indice_camara] --proyecto "$(pwd)"
```

Sin `ruta_salida`, escribe en `memory/ojo_AAAAMMDD_HHMMSS.jpg`. Como este guion
siempre se invoca a mano (nunca hay stdin de un gancho), `--proyecto <cwd>` (o
`ABYSS_PROYECTO`) es obligatorio para que sepa dónde guardar el fotograma; si
falta, `rutas.resolver()` avisa por stderr y sale.

Tras guardar el fotograma, léelo con la herramienta de lectura de imágenes para
poder describir lo que muestra — `ojo.py` solo lo captura, no lo interpreta.

## Qué devuelve

La ruta del `.jpg` escrito por stdout (o el mensaje de error: "sin cv2: no hay
ojo", "cámara N no disponible", "la cámara abrió pero no dio fotograma"). Cada
captura queda apuntada en `memory/ojo.log` (cuándo, cámara, tamaño).

## Qué sale de la máquina

Nada por red — el fotograma se queda en el disco local, en la ruta indicada (o
en `memory/`). Nadie más lo recibe salvo que el propio asistente lo suba a algún
otro sitio a petición explícita del usuario, algo que esta pieza no hace.

## Límites honestos

- Depende de OpenCV, no incluido por defecto; sin él, la pieza no hace nada.
- No hay control de resolución, enfoque ni exposición más allá de descartar los
  primeros fotogramas.
- El `.jpg` queda en disco sin cifrar como cualquier otro fichero de `memory/`.

## Reglas SGICP de esta pieza

- **Nunca por gancho**: es la única pieza para la que la ley no es "cómo medir"
  sino "cuándo no disparar". El consentimiento del turno actual es la condición,
  no una preferencia guardada ni un patrón detectado en el mensaje.
