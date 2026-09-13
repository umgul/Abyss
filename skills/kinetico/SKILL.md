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
  "explore this folder tree with the camera". También una colección con
  portadas, como estantería: "hazme una estantería 3D con mis películas",
  "abre mi colección de libros en 3D", "monta mi carpeta de discos como una
  estantería", "turn my movie folder into a 3D shelf", "browse my book collection
  in 3D with my hand". Se distingue de `kinetica`, que
  despieza UN objeto de UNA foto: aquí no hay ninguna foto, hay un conjunto de
  cosas. La cámara solo se enciende a petición explícita de este turno — nunca
  por gancho — y el visor funciona sin ella, con ratón.
allowed-tools: Bash
abyss-managed: true
---

# kinetico

## Qué hace

Convierte un conjunto de cosas relacionadas en algo 3D que se recorre con la mano
delante de la cámara. Tres modos, una sola orden:

```
python "${CLAUDE_PLUGIN_ROOT}/abyss/kinetico.py" arbol <carpeta> [--hondura N] [--tope N] [--fondo-escritorio]     [--salida DIR] [--puerto 8890] [--sin-abrir] [--solo-montar] [--sin-manos]
python "${CLAUDE_PLUGIN_ROOT}/abyss/kinetico.py" datos <nodos.json> [--salida DIR] [...]
python "${CLAUDE_PLUGIN_ROOT}/abyss/kinetico.py" estanteria <carpeta> [--fichas fichas.json] [--titulo T]     [--hondura 3] [--fondo imagen | --fondo-escritorio] [--salida DIR] [--puerto 8890] [...]
```

- **`arbol <carpeta>`** es el explorador de ficheros: cada fichero una esfera,
  cada carpeta un cubo, la planta es la profundidad y el color es la familia
  de formato. Se puede **entrar** en una carpeta y **abrir** un fichero con el
  programa que el sistema tenga asociado, los dos con la mano.
- **`datos <nodos.json>`** come el contrato genérico y sirve para cualquier
  otra cosa: un grafo de módulos, un catálogo, lo que traiga su adaptador.
- **`estanteria <carpeta>`** es una colección con portadas —libros, películas y
  series, discos, fotos, documentos— puesta como una estantería circular. Cada
  fichero es una obra; la portada sale de una imagen con su mismo nombre (el
  póster, la carátula; si la comparten varias obras numeradas, cada una lleva su
  número) o del propio fichero (primera página de un PDF, un fotograma del vídeo,
  la miniatura de un documento de Office). El puño la abre con el programa del
  sistema.

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

## La receta de una estantería («hazme una estantería con mis películas»)

1. **Monta sin servir y mira qué sale**:
   `python "${CLAUDE_PLUGIN_ROOT}/abyss/kinetico.py" estanteria "<carpeta>" --solo-montar --sin-manos`.
   Imprime cada obra y de dónde sale su portada. Si una imagen es el póster de una
   obra pero su nombre no casa (lleva una palabra de más), eso se arregla en la
   ficha con `portada`.
2. **Busca cada obra identificable en una fuente y escribe `fichas.json`** fuera
   de la carpeta del usuario (no escribas dentro de su colección sin preguntar):

   ```json
   {"titulo": "Mis películas", "etiqueta_autor": "dirección",
    "obras": [
     {"ficheros": ["2. Película.mkv"], "titulo": "Película", "autor": "Directora",
      "anio": 1982, "sinopsis": "…", "fuente": "https://es.wikipedia.org/wiki/…"},
     {"patron": "Serie X ", "sinopsis": "…", "fuente": "https://…",
      "nota": "Episodio {n} de la serie; la sinopsis es de la serie, no del episodio. "},
     {"ficheros": ["7. Otra.mp4"], "portada": "Extras/Otra(s).png"}]}
   ```

   Autor, año y sinopsis **solo con `fuente` http(s)**: sin ella el visor no los
   enseña y la ficha dice «sin dato con fuente». Si no estás seguro de qué artículo
   corresponde a un fichero (un corto de aficionados con el nombre de una película
   famosa, por ejemplo), no le pongas ficha: una sinopsis de otra obra es peor que
   ninguna. `patron` vale para los episodios de una serie; `{n}` en `nota` es el
   número final de cada título.
3. **Sírvela**: la misma orden sin `--solo-montar`, con `--fichas fichas.json` y,
   si la colección trae una imagen de fondo, `--fondo "ruta/dentro/de/la/carpeta.png"`
   (esa imagen deja de contar como obra).

La estantería no usa la red: las fichas las trae quien monta, con sus propias
herramientas y citando la fuente. Dependencias opcionales, con su hueco dicho si
faltan: PyMuPDF para la primera página de un PDF e imageio-ffmpeg para el fotograma
y la duración de un vídeo.

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

- **El explorador no abre ningún fichero para mirarlo por dentro.** El color de
  formato sale de la EXTENSIÓN del nombre, así que un `.txt` que en realidad sea
  otra cosa se pinta como texto. La procedencia de la escena lo declara con esas
  palabras. La estantería sí lee lo justo para la portada (la primera página, un
  fotograma, la miniatura guardada), sin sacar nada de la máquina.
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
la escena no existe. Los dos son POST, para que una visita suelta, una precarga o un
enlace no abran nada. Y el servidor rechaza cualquier petición cuyo `Host` u `Origin` no
sea el propio visor en `127.0.0.1` (`abyss/puerta_local.py`): otra web abierta en el
mismo navegador no puede pedirle que abra nada, ni leer la escena.

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
