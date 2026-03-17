# Distribucion Windows

## Objetivo

Generar una carpeta portable para usuarios de Windows que no tienen instalado Python, Playwright ni Google Chrome.

El build distribuible incluye:

- runtime de Python dentro del ejecutable PyInstaller
- `schema.sql` y assets de la app
- driver de Playwright
- Chromium de Playwright embebido

La base de datos del usuario no viaja dentro del paquete. Se guarda en:

`%LOCALAPPDATA%\MonitorSubastas\data\monitor.db`

Eso permite actualizar la app sin perder historial local.

## Estrategia recomendada

Primera etapa:

- publicar `dist/MonitorSubastas-win64-vX.Y.Z.zip`
- compartirlo por GitHub Releases, carpeta de red interna o SharePoint
- el usuario descomprime y ejecuta `MonitorSubastas.exe`

Esta etapa ya resuelve el problema principal: uso sin instalar Python ni navegador.

Segunda etapa opcional:

- agregar instalador `Inno Setup` o `MSIX`
- accesos directos, desinstalacion y firma de codigo

## Requisitos para generar el build

En la maquina de build:

1. Tener el repo.
2. Tener `.venv` con dependencias instaladas.
3. Tener Chromium descargado por Playwright:

```powershell
.venv\Scripts\playwright install chromium
```

## Comando de build

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows.ps1
```

Salida esperada:

- carpeta: `dist/MonitorSubastas`
- zip listo para compartir: `dist/MonitorSubastas-win64-vX.Y.Z.zip`

## Como compartirlo en la empresa

Opcion mas simple y util hoy:

1. Subir el `.zip` a GitHub Releases privado o a una carpeta compartida interna.
2. Enviar una instruccion corta:
   "Descargar, descomprimir y ejecutar `MonitorSubastas.exe`."
3. Si queres centralizar versiones, publicar siempre el ultimo zip en la misma ubicacion.

## Importante sobre actualizaciones automaticas

La ventana de actualizacion actual fue pensada para reemplazar un ejecutable puntual.

Como el build recomendado hoy es `one-folder` con recursos y Chromium incluidos:

- la distribucion correcta es actualizar la carpeta completa o el `.zip`
- no conviene depender todavia del auto-update de solo `.exe`

Si despues queremos, el siguiente paso natural es adaptar el actualizador para descargar un `.zip` completo y reemplazar toda la carpeta de aplicacion.
