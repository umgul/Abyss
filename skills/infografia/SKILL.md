---
name: infografia
description: >
  De un CSV o JSON a un SVG limpio (barras, barras horizontales, líneas o
  tabla), biblioteca estándar sin dependencias. Actívala cuando el usuario
  pida visualizar datos tabulares sin abrir una hoja de cálculo: "hazme un
  gráfico de barras con estos datos", "convierte este CSV en una infografía",
  "make a bar chart from this data", "turn this JSON into a line chart". Sin
  gancho: siempre a petición.
allowed-tools: Bash
---

# infografia

## Qué hace

Lee un `.csv` con cabecera, o un `.json` (lista de objetos, o un objeto de
columnas) y dibuja un SVG con paleta sobria fija (5 tonos), tipografía
`system-ui`, ejes con ticks "bonitos" (pasos 1-2-5 de la propia escala de los
datos), etiquetas de valor, leyenda si hay más de una serie, y pie con la
fuente si se da. Todo texto pasa por `xml.sax.saxutils.escape` antes de entrar
en el SVG.

## Cómo se ejecuta

```
python "${CLAUDE_PLUGIN_ROOT}/abyss/infografia.py" <datos.csv|datos.json> --tipo barras|barras_h|lineas|tabla \
    [--x columna] [--y columna[,columna2,...]] \
    [--titulo "…"] [--subtitulo "…"] [--fuente "…"] \
    [--salida f.svg] [--ancho 1200] [--alto 675] [--oscuro] [--es|--no-es]
```

Nota: este guion NO resuelve un proyecto de Claude Code (no acepta
`--proyecto` ni escribe en `memory/`) — es una herramienta de transformación
pura, como `pintor.py`.

`--x` (por defecto, la primera columna) marca la categoría; `--y` (por
defecto, la segunda) marca el valor — con varias separadas por comas, cada
una es una serie. En `--tipo tabla` no hay `--x`/`--y`: se dibujan todas las
columnas, o solo las que traiga `--y` como filtro, en ese orden. `--oscuro`
pinta sobre `#0f0e0e` en vez de blanco. `--es` (por defecto) usa coma decimal
y punto de millar; `--no-es` usa el formato inglés.

## Qué devuelve

La ruta del `.svg` escrito por stdout (por defecto,
`<datos_sin_extensión>_infografia.svg`), o `sin infografía: <motivo>` con
código 2 si los datos no se pueden leer o dibujar.

## Qué sale de la máquina

Nada. No hay red, no hay `memory/`: solo se escribe el `.svg` pedido.

## Límites honestos

- El SVG no se convierte a PNG aquí (no hay librería de rasterizado en la
  biblioteca estándar): se abre tal cual en cualquier navegador, o se incrusta
  con `<img src="...svg">`.
- Sin reescalado de etiquetas del eje de categorías: con muchas categorías o
  etiquetas largas, se solapan — toca acortarlas en los datos o pedir un
  `--ancho` mayor.
- No elige "el mejor" tipo de gráfico: el tipo lo decide quien lo pide.

## Reglas SGICP de esta pieza

- **Nada que no se pueda verificar mirando el propio SVG**: los ticks del eje
  salen de la escala real de los datos (pasos 1-2-5), nunca de un número fijo
  de rayas puesto a mano.
- **Texto siempre escapado**: un título con `<` o `&` no rompe el fichero —
  se comprueba con el propio parser XML, no a ojo.
