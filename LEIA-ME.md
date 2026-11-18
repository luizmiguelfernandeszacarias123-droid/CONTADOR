# Contador de Gado por Foto Aérea

Programa de desktop que conta animais em fotos aéreas (drone). Para cada foto gera:
- a imagem com uma caixa em cada animal e o total no canto;
- uma planilha Excel (`contagem_gado.xlsx`) com contagem por foto, por piquete (nome da pasta) e total.

## O que foi testado e o que NÃO foi

| Parte | Situação |
|---|---|
| Divisão da foto em blocos, remoção de duplicatas, marcações, planilha | Testado (`teste_pipeline.py`): 30 fotos sintéticas, contagem exata em todas |
| Detector YOLO real (`detector_yolo.py`) | **Não testado** (o ambiente onde foi escrito não tinha acesso ao PyPI) |
| Janela (`app.py`) e geração do `.exe` | **Não testados** (sem tkinter nem Windows no ambiente) |

Espere pequenos ajustes ao rodar pela primeira vez no seu computador.

## Como gerar o instalador (InstalarContadorGado.exe)

**Opção A, no seu Windows:** instale o Python e o [Inno Setup 6](https://jrsoftware.org/isdl.php), depois dê dois cliques em `build_exe.bat`. Ele cria o programa e, em seguida, `instalador\InstalarContadorGado.exe`.

**Opção B, sem instalar nada no seu computador:** crie um repositório no GitHub com esta pasta, abra a aba *Actions*, escolha *Gerar instalador (Windows)* e clique em *Run workflow*. Em cerca de 15-25 minutos o instalador fica disponível em *Artifacts*. (Esse fluxo também não foi executado ainda.)

O instalador instala para o usuário atual, sem pedir senha de administrador, e cria atalhos no menu Iniciar e (opcional) na área de trabalho.

## Como gerar só o .exe (no Windows)

1. Instale o Python 3.10, 3.11 ou 3.12 (marque "Add Python to PATH").
2. Dê dois cliques em `build_exe.bat` (precisa de internet; baixa ~2 GB de dependências).
3. O programa fica em `dist\ContadorGado\`. Distribua a **pasta inteira**.

Para testar sem gerar o .exe: `pip install -r requirements.txt` e depois `python app.py`.

## Como usar

1. **Escolher fotos** ou **Escolher pasta** (subpastas entram; cada pasta vira um "piquete" na planilha).
2. Ajuste a **sensibilidade** se necessário (menor = detecta mais, mas erra mais).
3. **Contar gado**. Resultados em `Documentos\ContadorGado\contagem_AAAA-MM-DD_HHMMSS\`.

## Limite importante: precisão

O modelo pré-treinado (COCO, classe "vaca") foi treinado principalmente com fotos feitas de lado.
Em fotos aéreas, vistas de cima, ele costuma **perder animais ou confundir sombras**. Use-o para
testar o fluxo; para contagem confiável, treine com fotos suas:

1. Corte suas fotos em recortes de 640x640 e marque cada animal (Roboflow, CVAT ou LabelImg), formato YOLO, uma classe `gado`. Algumas centenas de animais marcados já melhoram muito.
2. Treine: `yolo detect train data=gado.yaml model=yolov8m.pt imgsz=640 epochs=100`
3. Copie `runs/detect/train/weights/best.pt` para `modelo/gado.pt` ao lado do programa. Ele passa a ser usado automaticamente.

Dicas de voo: altura constante (animais com ~30-60 px na foto), luz sem sombra longa, e fotos com
pouca sobreposição entre si, senão o mesmo animal é contado duas vezes (aviso também na planilha).
Confira sempre por amostragem nas imagens marcadas antes de usar o número oficialmente.
