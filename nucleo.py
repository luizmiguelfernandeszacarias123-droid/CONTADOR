"""Núcleo do contador de gado: divisão da foto em blocos, junção das
detecções, desenho das marcações e processamento de uma imagem.

Fotos aéreas costumam ser grandes (12-48 MP) e os animais ficam muito
pequenos. Redimensionar a foto inteira para 640 px faria o gado sumir.
Por isso a foto é cortada em blocos com sobreposição, cada bloco passa pelo
detector, e as caixas são unidas depois (removendo as duplicadas das bordas).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Callable, Iterable, Protocol

import cv2
import numpy as np

EXTENSOES_IMAGEM = (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp")


# --------------------------------------------------------------------------
# Tipos
# --------------------------------------------------------------------------
@dataclass
class Deteccao:
    x1: float
    y1: float
    x2: float
    y2: float
    conf: float

    @property
    def area(self) -> float:
        return max(0.0, self.x2 - self.x1) * max(0.0, self.y2 - self.y1)


@dataclass
class ResultadoImagem:
    caminho: str
    largura: int
    altura: int
    deteccoes: list[Deteccao] = field(default_factory=list)
    caminho_marcada: str | None = None

    @property
    def contagem(self) -> int:
        return len(self.deteccoes)

    @property
    def confianca_media(self) -> float:
        if not self.deteccoes:
            return 0.0
        return float(np.mean([d.conf for d in self.deteccoes]))


class Detector(Protocol):
    """Qualquer objeto com este método serve (YOLO real ou simulado)."""

    def detectar_lote(self, blocos: list[np.ndarray]) -> list[list[tuple]]:
        """Recebe blocos BGR; devolve, para cada um, lista de (x1,y1,x2,y2,conf)
        em coordenadas do próprio bloco."""
        ...


# --------------------------------------------------------------------------
# Blocos
# --------------------------------------------------------------------------
def _posicoes(total: int, tam: int, passo: int) -> list[int]:
    if total <= tam:
        return [0]
    pos = list(range(0, total - tam + 1, passo))
    if pos[-1] + tam < total:
        pos.append(total - tam)  # último bloco encostado na borda
    return pos


def gerar_blocos(largura: int, altura: int, tamanho: int = 640,
                 sobreposicao: float = 0.2) -> list[tuple[int, int, int, int]]:
    """Lista de (x, y, largura, altura) cobrindo a imagem toda."""
    sobreposicao = min(max(sobreposicao, 0.0), 0.9)
    passo = max(1, int(tamanho * (1 - sobreposicao)))
    blocos = []
    for y in _posicoes(altura, tamanho, passo):
        for x in _posicoes(largura, tamanho, passo):
            blocos.append((x, y, min(tamanho, largura), min(tamanho, altura)))
    return blocos


# --------------------------------------------------------------------------
# Junção das detecções (NMS)
# --------------------------------------------------------------------------
def mesclar_deteccoes(deteccoes: list[Deteccao], limite_iou: float = 0.45,
                      limite_contido: float = 0.8) -> list[Deteccao]:
    """Remove duplicatas vindas de blocos sobrepostos.

    Dois passos:
    1. Pedaços: um animal cortado na borda de um bloco gera uma caixa parcial
       (às vezes só uma fatia). Toda caixa que está quase toda dentro de uma
       caixa MAIOR é descartada, independentemente da confiança. Isso precisa
       vir antes do NMS: se o NMS fosse só por confiança, um pedaço com
       confiança igual ou maior eliminaria a caixa inteira do animal e o
       outro pedaço sobraria, contando o animal duas vezes.
    2. NMS clássico por IoU para as caixas duplicadas que sobraram.
    """
    if not deteccoes:
        return []
    caixas = np.array([[d.x1, d.y1, d.x2, d.y2] for d in deteccoes], dtype=np.float64)
    confs = np.array([d.conf for d in deteccoes], dtype=np.float64)
    areas = np.maximum(0, caixas[:, 2] - caixas[:, 0]) * np.maximum(0, caixas[:, 3] - caixas[:, 1])
    n = len(deteccoes)

    def interseccao(sel, outros):
        """Área de interseção entre as caixas `sel` e as caixas `outros` (len(sel) x len(outros))."""
        a, b = caixas[sel], caixas[outros]
        w = np.minimum(a[:, None, 2], b[None, :, 2]) - np.maximum(a[:, None, 0], b[None, :, 0])
        h = np.minimum(a[:, None, 3], b[None, :, 3]) - np.maximum(a[:, None, 1], b[None, :, 1])
        return np.maximum(0, w) * np.maximum(0, h)

    # ---- passo 1: remove pedaços contidos em caixas maiores ----
    # (ignora caixas gigantes, ex.: um grupo de animais detectado como um só,
    #  para que elas não "engulam" animais individuais)
    mediana = float(np.median(areas[areas > 0])) if np.any(areas > 0) else 0.0
    limite_gigante = 2.5 * mediana if mediana > 0 else np.inf
    com_area = np.where(areas > 0, areas, np.inf)
    todas = np.arange(n)
    pedaco = np.zeros(n, dtype=bool)
    passo = 512  # em blocos de linhas para não estourar a memória com rebanhos grandes
    for ini in range(0, n, passo):
        linhas = todas[ini:ini + passo]
        inter = interseccao(linhas, todas)                        # [i, j]
        dentro = inter / com_area[linhas][:, None]                # parte de i que está dentro de j
        maior = (areas[None, :] > areas[linhas][:, None]) & (areas[None, :] <= limite_gigante)
        pedaco[linhas] = np.any((dentro >= limite_contido) & maior, axis=1)

    # ---- passo 2: NMS por IoU entre as restantes (confiança, depois tamanho) ----
    ordem = sorted((i for i in range(n) if not pedaco[i]), key=lambda i: (-confs[i], -areas[i]))
    mantidos: list[int] = []
    for i in ordem:
        if mantidos:
            idx = np.array(mantidos)
            inter = interseccao([i], idx)[0]
            uniao = areas[i] + areas[idx] - inter
            iou = np.divide(inter, uniao, out=np.zeros_like(inter), where=uniao > 0)
            if np.any(iou >= limite_iou):
                continue
        mantidos.append(i)
    return [deteccoes[i] for i in sorted(mantidos)]


# --------------------------------------------------------------------------
# E/S de imagens (funciona com acentos e espaços no caminho, também no Windows)
# --------------------------------------------------------------------------
def ler_imagem(caminho: str) -> np.ndarray:
    dados = np.fromfile(caminho, dtype=np.uint8)
    img = cv2.imdecode(dados, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"Não foi possível abrir a imagem: {caminho}")
    return img


def salvar_imagem(caminho: str, img: np.ndarray, qualidade: int = 92) -> None:
    ext = os.path.splitext(caminho)[1].lower() or ".jpg"
    params = [cv2.IMWRITE_JPEG_QUALITY, qualidade] if ext in (".jpg", ".jpeg") else []
    ok, buf = cv2.imencode(ext, img, params)
    if not ok:
        raise ValueError(f"Falha ao gravar a imagem: {caminho}")
    buf.tofile(caminho)


def listar_imagens(pasta: str, recursivo: bool = True) -> list[str]:
    achados = []
    if recursivo:
        for raiz, _, arquivos in os.walk(pasta):
            for nome in arquivos:
                if nome.lower().endswith(EXTENSOES_IMAGEM):
                    achados.append(os.path.join(raiz, nome))
    else:
        for nome in os.listdir(pasta):
            if nome.lower().endswith(EXTENSOES_IMAGEM):
                achados.append(os.path.join(pasta, nome))
    return sorted(achados)


# --------------------------------------------------------------------------
# Desenho
# --------------------------------------------------------------------------
def desenhar_marcacoes(img: np.ndarray, deteccoes: Iterable[Deteccao]) -> np.ndarray:
    """Devolve cópia da imagem com uma caixa em cada animal e o total no topo."""
    saida = img.copy()
    altura, largura = saida.shape[:2]
    escala = max(altura, largura) / 2000.0
    espessura = max(2, int(round(2 * escala)))
    deteccoes = list(deteccoes)

    for d in deteccoes:
        p1 = (int(round(d.x1)), int(round(d.y1)))
        p2 = (int(round(d.x2)), int(round(d.y2)))
        cv2.rectangle(saida, p1, p2, (0, 0, 0), espessura + 2)      # contorno escuro
        cv2.rectangle(saida, p1, p2, (0, 255, 255), espessura)      # amarelo

    texto = f"Total: {len(deteccoes)}"
    fonte = cv2.FONT_HERSHEY_SIMPLEX
    tam = max(1.0, 1.6 * escala)
    esp_txt = max(2, int(round(3 * escala)))
    (tw, th), base = cv2.getTextSize(texto, fonte, tam, esp_txt)
    margem = int(12 * max(1.0, escala))
    cv2.rectangle(saida, (0, 0), (tw + 2 * margem, th + base + 2 * margem), (0, 0, 0), -1)
    cv2.putText(saida, texto, (margem, th + margem), fonte, tam,
                (255, 255, 255), esp_txt, cv2.LINE_AA)
    return saida


# --------------------------------------------------------------------------
# Processamento de uma imagem
# --------------------------------------------------------------------------
def contar_em_imagem(img: np.ndarray, detector: Detector, tamanho_bloco: int = 640,
                     sobreposicao: float = 0.2, tamanho_lote: int = 8) -> list[Deteccao]:
    altura, largura = img.shape[:2]
    blocos = gerar_blocos(largura, altura, tamanho_bloco, sobreposicao)
    todas: list[Deteccao] = []
    for i in range(0, len(blocos), tamanho_lote):
        lote = blocos[i:i + tamanho_lote]
        recortes = [img[y:y + h, x:x + w] for (x, y, w, h) in lote]
        resultados = detector.detectar_lote(recortes)
        for (x, y, _, _), dets in zip(lote, resultados):
            for (x1, y1, x2, y2, conf) in dets:
                todas.append(Deteccao(x1 + x, y1 + y, x2 + x, y2 + y, float(conf)))
    return mesclar_deteccoes(todas)


def processar_arquivo(caminho: str, detector: Detector, pasta_saida: str | None = None,
                      tamanho_bloco: int = 640, sobreposicao: float = 0.2) -> ResultadoImagem:
    img = ler_imagem(caminho)
    altura, largura = img.shape[:2]
    dets = contar_em_imagem(img, detector, tamanho_bloco, sobreposicao)
    res = ResultadoImagem(caminho=caminho, largura=largura, altura=altura, deteccoes=dets)
    if pasta_saida:
        os.makedirs(pasta_saida, exist_ok=True)
        base = os.path.splitext(os.path.basename(caminho))[0]
        destino = os.path.join(pasta_saida, f"{base}_marcada.jpg")
        salvar_imagem(destino, desenhar_marcacoes(img, dets))
        res.caminho_marcada = destino
    return res


def processar_lote(caminhos: list[str], detector: Detector, pasta_saida: str,
                   tamanho_bloco: int = 640, sobreposicao: float = 0.2,
                   progresso: Callable[[int, int, ResultadoImagem | None, str | None], None] | None = None,
                   cancelar: Callable[[], bool] | None = None) -> list[ResultadoImagem]:
    """Processa várias fotos. `progresso(i, total, resultado, erro)` é chamado a cada foto."""
    resultados: list[ResultadoImagem] = []
    total = len(caminhos)
    for i, caminho in enumerate(caminhos, start=1):
        if cancelar and cancelar():
            break
        try:
            r = processar_arquivo(caminho, detector, pasta_saida, tamanho_bloco, sobreposicao)
            resultados.append(r)
            if progresso:
                progresso(i, total, r, None)
        except Exception as e:  # uma foto ruim não derruba o lote
            if progresso:
                progresso(i, total, None, f"{os.path.basename(caminho)}: {e}")
    return resultados
