---
name: kinetico
description: >
  Recorrer con la mano un conjunto de cosas que se relacionan entre sí: una
  carpeta del disco, un grafo de dependencias, un catálogo. Levanta un edificio
  3D navegable por gestos delante de la cámara, donde cada cosa es una esfera o
  un cubo y su tamaño, su planta y su color salen de los datos, no de un
  adorno. Actívala con: "abre mis documentos con kinético", "enséñame esta
  carpeta en 3D y déjame moverme con la mano", "quiero navegar mis archivos con
  gestos", "monta un mapa 3D de los módulos de este proyecto", "explórame este
  árbol de carpetas con la cámara". Y en inglés: "open my documents with
  kinetic", "show me this folder in 3D and let me move with my hand", "let me
  browse my files with gestures", "build a 3D map of this project's modules",
  "explore this folder tree with the camera". Se distingue de `kinetica`, que
  despieza UN objeto de UNA foto: aquí no hay ninguna foto, hay un conjunto de
  cosas. La cámara solo se enciende a petición explícita de este turno — nunca
  por gancho — y el visor funciona sin ella, con ratón.
allowed-tools: Bash
---

# kinetico

## Qué hace

Convierte un conjunto de cosas relacionadas en un edificio 3D que se recorre
con la mano delante de la cámara. Dos modos, una sola orden:

```
python "${CLAUDE_PLUGIN_ROOT}/abyss/kinetico.py" arbol <carpeta> [--hondura N] [--tope N] \
    [--salida DIR] [--puerto 8890] [--sin-abrir] [--solo-montar] [--sin-manos]
python "${CLAUDE_PLUGIN_ROOT}/abyss/kinetico.py" datos <nodos.json> [--salida DIR] [...]
```

- **`arbol <carpeta>`** es el explorador de ficheros: cada fichero una esfera,
  cada carpeta un cubo, la planta es la profundidad y el color es la familia
  de formato. Se puede **entrar** en una carpeta y **abrir** un fichero con el
  programa que el sistema tenga asociado, los dos con la mano.
- **`datos <nodos.json>`** come el contrato genérico y sirve para cualquier
  otra cosa: un grafo de módulos, un catálogo, lo que traiga su adaptador.

## Cuándo NO es esto

- Si lo que hay es **una foto de un objeto** y se quiere ver por dentro, eso es
  `kinetica`, no esto. Aquí no se despieza nada: se recorre un conjunto.
- Si se quiere un **render de un modelo 3D** que ya existe (.glb, .obj, .stl),
  eso es `render3d`.
- Si se quiere un **diagrama plano** de dependencias, eso es `mapa_codigo`, que
  además no pide cámara ni navegador.

## La receta de «abre mis documentos con kinético»

```bash
python "${CLAUDE_PLUGIN_ROOT}/abyss/kinetico.py" arbol "$HOME/Documents" --hondura 1
```

`--hondura 1` es lo que hace que sea un explorador y no un volcado: a
profundidad 1 las subcarpetas se resumen en un cubo cada una, con cuántos
ficheros llevan dentro, y se entra en ellas con el gesto. Con `--hondura 2` o
más se aplanan dos niveles de golpe y salen miles de bolas que no se pueden
mirar. **Medido el 9-sep-2026** sobre una carpeta Documents real: con
`--hondura 2` salían 2.002 cosas; con `--hondura 1`, 195 — de las cuales 16
carpetas y 179 ficheros.

## Los gestos

| gesto | qué hace |
|---|---|
| mano a los lados | gira el edificio |
| mano arriba y abajo | sube y baja de planta |
| dos manos acercándose o alejándose | acerca o aleja la cámara |
| un puño | abre la cosa que tengas delante (la ficha) |
| **segundo puño sobre la misma** | actúa: **entra** en la carpeta o **abre** el fichero |
| dos puños | paran en seco |

Sin cámara el visor sigue siendo usable: se arrastra con el ratón, se acerca
con la rueda, se pincha una cosa para abrir su ficha y se busca por nombre en
el buscador de arriba. El ratón además **enciende lo que roza**, que es la
pista de qué se va a abrir.

## Lo que este visor NO hace, y hay que decirlo

- **No abre ningún fichero para mirarlo por dentro.** El color de formato sale
  de la EXTENSIÓN del nombre, así que un `.txt` que en realidad sea otra cosa
  se pinta como texto. La procedencia de la escena lo declara con esas
  palabras.
- **La planta no es una medida, es un decreto**: la profundidad de carpeta la
  decide quien monta, no la fuente.
- **El tamaño se escala dentro de cada forma, no entre formas.** Una esfera
  vale BYTES y un cubo vale FICHEROS DENTRO: son unidades distintas y ponerlas
  en la misma regla no significaría nada. Medido: una carpeta de 100 ficheros
  da log2(101) = 6,7 y un fichero de 1 MB da log2(1e6) = 19,9.
- **Un fichero suelto no trae descripción**, así que su ficha dice «sin dato con
  fuente» en vez de inventarse un resumen.

## Los dos verbos, y por qué van por lista blanca

El servidor (`abyss/kinetico_servidor.py`) expone `POST /entrar` y
`POST /abrir`. En los dos casos el destino se busca **en el diccionario de la
escena que está montada**: no es una ruta que llegue de fuera, es una clave que
tiene que existir en el `nodos.json` recién escrito, y además se comprueba que
lo resuelto siga colgando de la carpeta con la que se abrió. Lo que no esté en
la escena no existe. Los dos son POST a propósito: una visita suelta, una
precarga o un enlace no abren nada.

## La cámara

Solo se enciende cuando el usuario lo pide **en ese turno**, pulsando
«Encender cámara» en la propia página. Nunca por gancho, nunca al arrancar. El
permiso del navegador se guarda por origen incluyendo el puerto, en un perfil
propio bajo `%LOCALAPPDATA%\abyss\navegador`, y no toca el navegador del
usuario.

## Grabar

El botón «Grabar» pide al navegador compartir pantalla —el mismo selector de
*Pantalla completa / Ventana / Pestaña* de cualquier videollamada— y guarda un
`.webm`. Tiene que salir de un clic, así que no se puede disparar con un gesto.
Si se cancela el selector, se cae a grabar un lienzo compuesto con la escena y
la cámara, que es peor demostración pero nunca un botón muerto.

## Si falta MediaPipe

El visor se sirve igual, **sin manos**, y lo dice en pantalla al encender la
cámara. Se descarga con `python instalar.py --manos`. Esta skill nunca lo
descarga por su cuenta.
