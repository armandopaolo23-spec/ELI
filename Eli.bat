@echo off
REM ============================================================
REM Eli.bat — Lanzador de Eli, tu asistente de voz
REM Haz doble clic en este archivo para iniciar a Eli
REM ============================================================

REM --- Título de la ventana ---
REM Esto cambia el texto que aparece arriba en la barra de la ventana negra.
title Eli - Asistente de Voz

REM --- Ir a la carpeta del proyecto ---
REM "cd /d" cambia de carpeta Y de disco al mismo tiempo.
REM Sin "/d", si estás en D: y la carpeta está en C:, no funcionaría.
cd /d C:\Users\Lenovo\Eli

REM --- Activar el entorno virtual ---
REM "call" es necesario para ejecutar otro .bat sin que este se detenga.
REM Sin "call", Windows ejecutaría activate.bat y NUNCA volvería aquí,
REM así que main.py jamás se ejecutaría.
call venv\Scripts\activate.bat

REM --- Lanzar a Eli ---
python main.py

REM --- Pausar al final ---
REM Si Eli se cierra (o crashea), la ventana se quedaría abierta
REM mostrando "Presione una tecla para continuar..."
REM Así puedes leer cualquier error antes de que desaparezca.
echo.
echo Eli se ha detenido.
pause