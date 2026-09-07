// orbita_minima.js — control de órbita propio de Abyss, embebible sin red.
//
// T3.1 pide órbita con OrbitControls embebido; no existe build UMD de
// OrbitControls desde three.js r152 (el oficial solo se distribuye como módulo
// ES bajo `examples/jsm/controls/`, y cdnjs no aloja ningún paquete con él —
// comprobado 7-sep-2026 contra api.cdnjs.com), así que no hay build UMD que
// embeber junto a `vendor/three.min.js` (que sí es la última versión UMD,
// r160). Por eso se embebe este control propio con el mismo gesto de uso
// (arrastrar para orbitar, rueda para zoom, botón derecho para desplazar el
// objetivo) — desviación consciente del contrato, no una lectura suya, sin
// depender de módulos ES ni de ningún fichero externo.
//
// API mínima: `new OrbitaMinima(camera, dominio, objetivo)` y `.update()` en cada
// fotograma (coloca la cámara y llama a `camera.lookAt(objetivo)`; el objetivo se
// puede mover leyendo/escribiendo `.target`).
//
// Licencia: la del propio repositorio (Apache-2.0, ver LICENSE en la raíz de
// Abyss) — código propio, no derivado de three.js.
(function (global) {
  'use strict';

  function OrbitaMinima(camera, dominio, objetivo) {
    this.camera = camera;
    this.dominio = dominio;
    this.target = objetivo.clone();

    var offset = camera.position.clone().sub(this.target);
    this.radio = Math.max(0.001, offset.length());
    this.theta = Math.atan2(offset.x, offset.z);
    this.phi = Math.acos(Math.min(1, Math.max(-1, offset.y / this.radio)));

    this._arrastre = null;
    var self = this;

    dominio.style.touchAction = 'none';
    dominio.addEventListener('contextmenu', function (e) { e.preventDefault(); });

    dominio.addEventListener('pointerdown', function (e) {
      self._arrastre = { boton: e.button, x: e.clientX, y: e.clientY };
      try { dominio.setPointerCapture(e.pointerId); } catch (err) { /* headless: sin puntero real */ }
    });
    dominio.addEventListener('pointerup', function () { self._arrastre = null; });
    dominio.addEventListener('pointerleave', function () { self._arrastre = null; });

    dominio.addEventListener('pointermove', function (e) {
      if (!self._arrastre) return;
      var dx = e.clientX - self._arrastre.x;
      var dy = e.clientY - self._arrastre.y;
      self._arrastre.x = e.clientX;
      self._arrastre.y = e.clientY;
      if (self._arrastre.boton === 0) {
        // botón izquierdo: orbitar
        self.theta -= dx * 0.006;
        self.phi = Math.min(Math.PI - 0.02, Math.max(0.02, self.phi - dy * 0.006));
      } else {
        // botón derecho o central: desplazar el objetivo (paneo)
        var factor = self.radio * 0.0016;
        var dirCam = new global.THREE.Vector3();
        self.camera.getWorldDirection(dirCam);
        var derecha = new global.THREE.Vector3().crossVectors(dirCam, self.camera.up).normalize();
        var arriba = new global.THREE.Vector3().crossVectors(derecha, dirCam).normalize();
        self.target.addScaledVector(derecha, -dx * factor);
        self.target.addScaledVector(arriba, dy * factor);
      }
    });

    dominio.addEventListener('wheel', function (e) {
      e.preventDefault();
      self.radio *= Math.pow(1.0012, e.deltaY);
      self.radio = Math.max(0.02, self.radio);
    }, { passive: false });
  }

  OrbitaMinima.prototype.update = function () {
    var sp = Math.sin(this.phi);
    var x = this.radio * sp * Math.sin(this.theta);
    var y = this.radio * Math.cos(this.phi);
    var z = this.radio * sp * Math.cos(this.theta);
    this.camera.position.set(this.target.x + x, this.target.y + y, this.target.z + z);
    this.camera.lookAt(this.target);
  };

  global.OrbitaMinima = OrbitaMinima;
})(typeof window !== 'undefined' ? window : this);
