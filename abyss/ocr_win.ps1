# -*- coding: utf-8 -*-
# OCR con el motor de Windows (WinRT, `Windows.Media.Ocr`), sin instalar nada.
#
# Uso:
#   powershell -NoProfile -NonInteractive -File ocr_win.ps1 -Ruta <imagen> [-Idioma es-ES]
#   powershell -NoProfile -NonInteractive -File ocr_win.ps1 -Comprobar   (sin imagen: solo
#       dice si el motor existe para los idiomas del perfil, o para -Idioma si se da)
#
# Salida: SIEMPRE una única línea JSON por stdout (para que quien invoque, `lectura_visual.py`,
# no tenga que distinguir texto suelto de un error) y el código de salida dice el motivo:
#   0 · éxito:            {"ok":true,"lineas":[{"texto":..,"x":..,"y":..,"ancho":..,"alto":..}, ...],
#                          "angulo":.., "ms":..}
#   2 · sin motor OCR:    {"ok":false,"motivo":"sin dato: no hay motor OCR para los idiomas del usuario"}
#       (falta el paquete de idioma, o esta versión de Windows no trae WinRT/Windows.Media.Ocr)
#   1 · fallo puntual:    {"ok":false,"motivo":"..."} (imagen inexistente, fichero corrupto,
#       la propia llamada a RecognizeAsync lanzó una excepción) — esto NO significa "sin
#       motor", significa que ESTA imagen no se pudo leer con el motor que sí existe.
#
# `x`/`y`/`ancho`/`alto` de cada línea son la caja que ENVUELVE sus palabras (WinRT da el
# cuadro por PALABRA, `OcrWord.BoundingRect`, no por línea; aquí se agregan al mínimo/máximo
# de sus palabras) — es lo que usa `lectura_visual.py` para el verbo `tarjeta` (nombre/cargo/
# empresa por tamaño y posición de línea, nunca por contenido inventado).
#
# Medido el 7-sep-2026 en la máquina de desarrollo (idioma del perfil `es-ES`, sin instalar
# nada): sobre una imagen sintética de 900x420 con 6 líneas (con acentos, un correo y un
# teléfono), 443 ms y las 6 líneas correctas — ver ESPECIFICACION_TANDA4.md §0.
param(
    [string]$Ruta = '',
    [string]$Idioma = '',
    [switch]$Comprobar
)
$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}

function Emitir($obj) {
    Write-Output ($obj | ConvertTo-Json -Compress -Depth 6)
}

function CrearMotor($idioma) {
    if ($idioma) {
        try {
            $lang = New-Object Windows.Globalization.Language($idioma)
            return [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($lang)
        } catch {
            return $null
        }
    }
    return [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
}

try {
    Add-Type -AssemblyName System.Runtime.WindowsRuntime | Out-Null
    [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime] | Out-Null
    [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics, ContentType = WindowsRuntime] | Out-Null
    [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime] | Out-Null
} catch {
    Emitir @{ ok = $false; motivo = "sin dato: no hay motor OCR (WinRT/Windows.Media.Ocr no disponible: $($_.Exception.Message))" }
    exit 2
}

$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
function Esperar($tarea, $tipo) {
    $m = $asTaskGeneric.MakeGenericMethod($tipo)
    $t = $m.Invoke($null, @($tarea))
    $t.Wait(-1) | Out-Null
    $t.Result
}

if ($Comprobar) {
    $motor = CrearMotor $Idioma
    if ($null -eq $motor) {
        Emitir @{ ok = $false; motivo = 'sin dato: no hay motor OCR para los idiomas del usuario' }
        exit 2
    }
    Emitir @{ ok = $true; idioma = $motor.RecognizerLanguage.LanguageTag }
    exit 0
}

if (-not $Ruta) {
    Emitir @{ ok = $false; motivo = 'falta -Ruta <imagen> (o usa -Comprobar)' }
    exit 1
}
if (-not (Test-Path -LiteralPath $Ruta)) {
    Emitir @{ ok = $false; motivo = "no existe la imagen: $Ruta" }
    exit 1
}

$t0 = Get-Date
try {
    $abs = (Resolve-Path -LiteralPath $Ruta).Path
    $file = Esperar ([Windows.Storage.StorageFile]::GetFileFromPathAsync($abs)) ([Windows.Storage.StorageFile])
    $stream = Esperar ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
    $decoder = Esperar ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
    $bitmap = Esperar ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
} catch {
    Emitir @{ ok = $false; motivo = "no se pudo leer la imagen: $($_.Exception.Message)" }
    exit 1
}

$motor = CrearMotor $Idioma
if ($null -eq $motor) {
    Emitir @{ ok = $false; motivo = 'sin dato: no hay motor OCR para los idiomas del usuario' }
    exit 2
}

try {
    $res = Esperar ($motor.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
} catch {
    Emitir @{ ok = $false; motivo = "el motor OCR falló sobre esta imagen: $($_.Exception.Message)" }
    exit 1
}

$lineas = @()
foreach ($linea in $res.Lines) {
    $palabras = @($linea.Words)
    if ($palabras.Count -gt 0) {
        $x1 = ($palabras | ForEach-Object { $_.BoundingRect.X } | Measure-Object -Minimum).Minimum
        $y1 = ($palabras | ForEach-Object { $_.BoundingRect.Y } | Measure-Object -Minimum).Minimum
        $x2 = ($palabras | ForEach-Object { $_.BoundingRect.X + $_.BoundingRect.Width } | Measure-Object -Maximum).Maximum
        $y2 = ($palabras | ForEach-Object { $_.BoundingRect.Y + $_.BoundingRect.Height } | Measure-Object -Maximum).Maximum
    } else {
        $x1 = 0; $y1 = 0; $x2 = 0; $y2 = 0
    }
    $lineas += [PSCustomObject]@{
        texto = $linea.Text
        x     = [math]::Round([double]$x1, 1)
        y     = [math]::Round([double]$y1, 1)
        ancho = [math]::Round([double]($x2 - $x1), 1)
        alto  = [math]::Round([double]($y2 - $y1), 1)
    }
}
$ms = [math]::Round(((Get-Date) - $t0).TotalMilliseconds, 0)
$angulo = $null
if ($res.TextAngle -ne $null) { $angulo = [math]::Round([double]$res.TextAngle, 2) }
Emitir @{ ok = $true; lineas = @($lineas); angulo = $angulo; ms = $ms }
exit 0
