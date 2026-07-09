@echo off
title Servidor ERP Nicoletti
cd /d "%~dp0"
echo ==================================================
echo           INICIANDO SERVIDOR ERP NICOLETTI
echo ==================================================
echo.
python erp_api.py
echo.
echo Servidor detenido.
pause
