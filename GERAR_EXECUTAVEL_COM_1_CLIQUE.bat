@echo off
chcp 65001 > nul
title Criando Executavel do Mosaico Thumbnail Pro

echo ========================================================
echo   CRIANDO EXECUTAVEL (.EXE) AUTOMATICAMENTE
echo ========================================================
echo.
echo 1. Instalando bibliotecas necessarias...
py -m pip install -r requirements.txt

echo.
echo 2. Compilando o programa em arquivo .EXE com ICONE OFICIAL...
py -m PyInstaller --noconfirm --onefile --windowed --name "MosaicoThumbnailPro_Portatil" --icon="icon.ico" --add-data "icon.png;." --clean main.py

echo.
echo ========================================================
echo   PRONTO! O executavel foi criado com sucesso!
echo.
echo   Localizacao: pasta "dist\MosaicoThumbnailPro_Portatil.exe"
echo ========================================================
echo.
pause
