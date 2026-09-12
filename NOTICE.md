# NOTICE — lo que este paquete usa y no es suyo

Abyss se publica bajo Apache-2.0 (ver `LICENSE`). Usa tres obras de terceros. Solo
una viaja dentro del repositorio; las otras dos las descarga `instalar.py` cuando el
usuario lo pide, y cada descarga deja su licencia al lado. Cada una conserva su
licencia, y aquí están todas juntas para que se vean de un vistazo.

| qué | dónde queda | viaja en el repo | de quién | licencia | su texto |
|---|---|---|---|---|---|
| three.js r160 (`three.min.js`, 669.884 B) | `abyss/vendor/` | sí | three.js Authors | MIT | `abyss/vendor/LICENSE-three.txt` |
| MediaPipe Tasks Vision 0.10.14 + `hand_landmarker.task` (~27 MB) | `abyss/vendor/mp/` | no: `python instalar.py --manos` | Google | Apache-2.0 | `abyss/vendor/mp/LICENSE-mediapipe.txt` |
| U²-Net p (`u2netp.onnx`, 4.574.861 B) | `abyss/vendor/modelos/` | no: `python instalar.py --modelo` | Xuebin Qin et al. (red) · Daniel Gatis / rembg (el fichero) | Apache-2.0 · MIT | `abyss/vendor/modelos/LICENSE-u2netp.txt` |

Los tamaños están medidos con `os.path.getsize`, no estimados.

## Por qué solo viaja three.js

Un repositorio que solo contiene texto se puede leer entero antes de instalarlo,
que es justamente lo que hace `abyss/auditar.py`. `three.min.js` es la excepción
declarada: ya estaba en la historia del repositorio y sin él los visores 3D no
arrancan. MediaPipe y U²-Net p son binarios que se piden aparte, con una orden
explícita y nunca en silencio; sin ellos los visores cinéticos funcionan sin manos
(y lo dicen en pantalla) y `fondo.py` usa el motor que tenga y declara cuál. Los
textos de licencia sí viajan, para poder leerlos antes de bajar nada.

## Lo que este paquete NO hace con ellas

- No entrena, no reentrena y no modifica ningún modelo.
- No redistribuye ninguna versión alterada: los ficheros son los que se bajaron.
- No manda nada a ningún servidor: las tres corren en la máquina del usuario.

## Lo que sí es de este paquete

Todo lo demás — el código de `abyss/`, las plantillas, las skills, las pruebas y
la documentación — es obra propia y va bajo Apache-2.0, igual que el conjunto.
