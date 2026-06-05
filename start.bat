@echo off
echo.
echo   ══════════════════════════════════════
echo     ENCARNADO - Portal do Benfica
echo   ══════════════════════════════════════
echo.
echo   A instalar dependencias...
pip install -r requirements.txt -q

echo   A criar pastas...
if not exist "data" mkdir data
if not exist "public\assets\images" mkdir public\assets\images

echo.
echo   Site publico : http://localhost:5000
echo   Administracao: http://localhost:5000/admin
echo   Login        : admin / encarnado2025
echo.
echo   Pressione CTRL+C para parar.
echo.

python server.py
pause
