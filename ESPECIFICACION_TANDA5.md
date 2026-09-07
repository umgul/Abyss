# QUINTA TANDA · que se instale solo, que hable dos idiomas, y que se sepa contar
Abyss · 7-sep-2026 · complemento de las cuatro anteriores (mismas reglas: ley o medida; fail-closed;
nada personal; castellano en el código; cada cifra medida en UNA máquina y dicha como tal).

## 0 · Por qué
Petición del autor (7-sep 19:18): «no sabemos a qué máquinas se va a instalar la habilidad», así que
el paquete tiene que resolver por sí mismo lo que necesita; el lanzador, el instalador y los
documentos tienen que estar en español y en inglés; y hace falta un vídeo corto que enseñe lo que hace
cada pieza, con demostración cuando se pueda.

## T5.1 · El instalador resuelve dependencias, con consentimiento y sin mentir
Hoy `requirements.txt` va entero comentado y cada módulo dice «pip install …» cuando falla. Eso vale
en la máquina de quien lo escribió; no vale para una máquina cualquiera.

- **Registro de dependencias por módulo**, en `instalar.py`, con tres campos por cada una: nombre de
  importación, nombre en pip, y para qué sirve. Ejemplos (comprobar cada uno contra el código, no
  copiar esta lista a ciegas): `imagen`/`pintor` → Pillow, numpy; `video` → imageio-ffmpeg;
  `ojo` → opencv-python; `lector_pdf` → PyMuPDF o pypdf; `gestos` → mediapipe; `lienzo` → opencv-python
  (opcional, con camino en Python puro si falta).
- **`instalar.py --dependencias`**: mira qué falta para los módulos marcados (con un `import` real, no
  una lista), y lo dice en una tabla: módulo · falta · paquete pip · tamaño aproximado si se conoce.
- **`instalar.py --instalar-dependencias [mod1,mod2]`** y una casilla en la ventana: instala con
  `sys.executable -m pip install <paquete>`, UNA a una, enseñando el comando antes de correrlo y el
  resultado después. Nunca en silencio, nunca en el arranque, nunca dentro de un gancho.
- **Fail-closed y honesto**: si no hay pip, si no hay red, si el `pip install` devuelve error, se dice
  con la última línea del error y se sigue con el resto; el módulo afectado queda marcado como «sin
  dependencia» y su guion sigue diciendo qué falta. No se reintenta solo.
- **Lo que NO puede instalar, dicho en la tabla y en el README**: binarios del sistema. En concreto:
  - OCR: en Windows el motor viene con el sistema (WinRT, medido: responde en `es-ES` sin instalar
    nada). En Linux y macOS **no hay motor incluido**: el instalador puede poner `pytesseract` por
    pip, pero el binario `tesseract` se instala con el gestor del sistema, y el instalador escribe el
    comando exacto (`sudo apt install tesseract-ocr tesseract-ocr-spa`, `brew install tesseract
    tesseract-lang`) en vez de fingir que puede.
  - `taller.py` (torch + diffusers): pesa gigas y depende de la tarjeta. El instalador NO lo instala:
    detecta si hay GPU NVIDIA (`nvidia-smi`) y escribe el comando de instalación que corresponde, con
    su aviso de tamaño. Igual que hoy.
- **Desinstalar**: `--desinstalar-dependencias` NO existe. Quitar paquetes de Python del entorno de
  alguien es más peligroso que ponerlos; se dice en el README y se deja al usuario.
- Pruebas: con un `pip` simulado (monkeypatch de `subprocess.run`), `--instalar-dependencias imagen`
  llama a `sys.executable -m pip install` con los paquetes de imagen y con ninguno más; si el pip
  simulado falla, el resumen lo dice y el código de salida no es 0; `--dependencias` sobre un entorno
  con una dependencia presente y otra ausente marca exactamente esa; y ningún gancho instala nada.

## T5.2 · Español e inglés en el lanzador, el instalador y los documentos
- **Instalador bilingüe**: un diccionario `TEXTOS = {"es": {...}, "en": {...}}` en `instalar.py`, con
  el idioma por `--idioma es|en`, y por defecto el del sistema (`locale.getdefaultlocale()`; si no
  empieza por `es`, inglés). Toda cadena que vea el usuario pasa por ahí: ventana, botones, avisos,
  tabla de módulos, mensajes de error y resumen final. Nada de cadenas sueltas en el código.
- **Los mensajes de los guiones** siguen en castellano (es el idioma del código y así está declarado),
  salvo los que el instalador imprime.
- **Documentos**: `README.md` y `README.en.md` ya existen y son espejo; se añaden
  `docs/leyes.en.md` y, si el informe de auditoría se publica, `docs/AUDITORIA_DE_ABYSS.en.md`.
  Cada par lleva el enlace al otro en la primera línea.
- **Las SKILL.md** se quedan en castellano con los disparadores en los dos idiomas, que es lo que hace
  que Claude las active escriba quien escriba en el idioma que sea.
- Pruebas: `--idioma en --listar` no imprime ni una palabra de la lista castellana de control
  («módulo», «instalado», «ganchos»); las dos versiones de cada documento tienen el mismo número de
  secciones de primer nivel; y ningún texto del instalador queda fuera del diccionario (una prueba que
  busca literales sospechosos en el código).

## T5.3 · `presenta.py`: el vídeo de un minuto, generado por el propio paquete
No es un vídeo montado a mano: lo produce el paquete corriendo sus propias piezas, para que lo que se
ve sea de verdad y se pueda rehacer cuando algo cambie.
- `presenta.py [--salida abyss_1min.mp4] [--idioma es|en] [--segundos 60] [--ancho 1920]`: genera el
  vídeo encadenando bloques. Cada bloque = una tarjeta de título (nombre de la pieza y una línea de
  qué hace) + su demostración REAL, generada en el momento con la propia herramienta:
  | bloque | qué se ve | de dónde sale |
  |---|---|---|
  | apertura | el nombre y una frase: dieciséis piezas que miden en vez de decretar | tarjeta |
  | memoria y continuidad | el índice con sus pesos ◆ recalculándose | salida real de `varas --index` sobre un proyecto de ejemplo |
  | honestidad | el vigía cazando un número inventado y bloqueando una vez | salida real de `vigia --probar` |
  | auditoría | las cinco comprobaciones sobre el propio paquete | `auditar.py` sobre el repo |
  | sentidos | la línea de arranque con lugar, meteo y cuerpo | `cuerpo` y `exterocepcion` en un proyecto de ejemplo |
  | pintor | una foto convirtiéndose en cuadro, acelerado | `video_pintura.py` sobre trazos reales |
  | estilos | la misma foto en óleo, acuarela, carbón y tinta, en cuatro cuartos | `pintor.py` |
  | mundo | un motivo buscado en un museo y pintado | `mundo` + `pintor` |
  | el ojo | una foto de un texto → texto plano en el portapapeles; y una foto de un folio → fotocopia | `ojo texto`, `ojo fotocopia` |
  | 3D | una escena girando y abriéndose en vista explosionada | `render3d --png` en varios fotogramas |
  | holograma | los cuatro cuadrantes espejados | `render3d --holograma` |
  | cierre | cómo se instala, en una línea | tarjeta |
- Tipografía y paleta sobrias, las mismas de `infografia.py`; texto en el idioma pedido; sin música
  (quien lo publique le pone la suya); 1920×1080 a 30 fps con `imageio_ffmpeg`, que ya está.
- **Presupuesto de tiempo declarado**: si la suma de bloques pasa de `--segundos`, se recortan los
  tramos más largos y se DICE cuáles, en vez de acelerarlo todo hasta que no se entienda.
- Si una pieza no está disponible en la máquina (sin OpenCV, sin motor OCR, sin navegador para el 3D),
  su bloque se salta y el vídeo lo dice en una línea al final: se hizo con lo que había.
- Pruebas: con las piezas simuladas, `presenta.py --segundos 12` produce un mp4 de más de 10 s y menos
  de 14, con tantos bloques como piezas disponibles; y con todas las piezas ausentes, no revienta: sale
  un vídeo de apertura y cierre diciendo que no había nada que enseñar.
