@echo off
REM Local Media Downloader - haz doble clic en este archivo para usar la app.
REM No necesitas escribir comandos: arranca el servicio local y abre el navegador.
REM Deja la ventana abierta mientras lo uses. Para detener: Ctrl+C.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Start-LMD.ps1"
pause
