# prueba temporal, NO forma parte del paquete: se borra al terminar.
import json, os, subprocess, sys, tempfile, time, shutil, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import navegador_cdp as cdp
import navegador as nav

exe = nav.cual()
url = sys.argv[1]
salida = sys.argv[2]
script_js = sys.argv[3] if len(sys.argv) > 3 else None
ancho, alto = 1600, 900

perfil = tempfile.mkdtemp(prefix="abyss_cdp_manual_")
proc = subprocess.Popen(
    [exe, "--headless=new", "--remote-debugging-port=0", "--user-data-dir=" + perfil,
     "--no-first-run", "--no-default-browser-check", "--hide-scrollbars", "--disable-extensions",
     "--window-size=%d,%d" % (ancho, alto), "about:blank"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    puerto = cdp._puerto_de(perfil)
    wsurl = None
    for _ in range(20):
        objetivos = json.load(urllib.request.urlopen("http://127.0.0.1:%d/json/list" % puerto, timeout=10))
        wsurl = next((t["webSocketDebuggerUrl"] for t in objetivos if t.get("type") == "page"), None)
        if wsurl:
            break
        time.sleep(0.25)
    if not wsurl:
        raise RuntimeError("sin pestaña disponible")
    ws = cdp._Ws(wsurl)
    n = [0]
    def orden(metodo, params=None):
        n[0] += 1
        ws.manda({"id": n[0], "method": metodo, "params": params or {}})
        while True:
            r = ws.recibe()
            if r.get("id") == n[0]:
                if "error" in r:
                    raise RuntimeError("%s: %s" % (metodo, r["error"].get("message")))
                return r.get("result", {})

    orden("Page.enable")
    orden("Runtime.enable")
    orden("Emulation.setDeviceMetricsOverride", {"width": ancho, "height": alto, "deviceScaleFactor": 1, "mobile": False})
    orden("Page.navigate", {"url": url})
    time.sleep(1.5)
    if script_js:
        res = orden("Runtime.evaluate", {"expression": script_js, "awaitPromise": True, "returnByValue": True})
        print("evaluate ->", res)
        time.sleep(0.6)
    res = orden("Page.captureScreenshot", {"format": "png"})
    import base64
    datos = base64.b64decode(res["data"])
    with open(salida, "wb") as fh:
        fh.write(datos)
    print("bytes:", len(datos), "->", salida)
finally:
    try:
        proc.terminate(); proc.wait(timeout=8)
    except Exception:
        try: proc.kill()
        except Exception: pass
    shutil.rmtree(perfil, ignore_errors=True)
