@echo off
REM Gera o executavel do Contador de Gado (rode no WINDOWS, com Python 3.10-3.12 instalado).
REM Resultado: dist\ContadorGado\ContadorGado.exe  (distribua a pasta inteira)

setlocal
cd /d "%~dp0"

echo [1/4] Criando ambiente virtual...
py -3 -m venv venv || goto erro
call venv\Scripts\activate.bat

echo [2/4] Instalando dependencias (pode demorar, o PyTorch e grande)...
python -m pip install --upgrade pip || goto erro
python -m pip install -r requirements.txt || goto erro

echo [3/4] Baixando o modelo pre-treinado (precisa de internet)...
if not exist modelo mkdir modelo
if not exist modelo\yolov8m.pt (
    pushd modelo
    python -c "from ultralytics import YOLO; YOLO('yolov8m.pt')" || (popd & goto erro)
    popd
)

echo [4/4] Empacotando...
pyinstaller --noconfirm --clean --onedir --windowed --name ContadorGado ^
    --collect-all ultralytics ^
    --hidden-import detector_yolo ^
    --add-data "modelo;modelo" ^
    app.py || goto erro

echo.
echo Pronto! Executavel em: dist\ContadorGado\ContadorGado.exe
echo Para usar um modelo treinado por voce, coloque-o em dist\ContadorGado\modelo\gado.pt

REM Se o Inno Setup 6 estiver instalado, cria tambem o instalador.
set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ISCC%" (
    echo Criando o instalador...
    "%ISCC%" instalador.iss && echo Instalador em: instalador\InstalarContadorGado.exe
) else (
    echo Para gerar tambem o instalador, instale o Inno Setup 6 ^(jrsoftware.org/isdl.php^) e rode este arquivo de novo.
)
pause
exit /b 0

:erro
echo.
echo Algo deu errado. Leia a mensagem acima.
pause
exit /b 1
