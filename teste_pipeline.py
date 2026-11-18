"""Teste do pipeline sem precisar do YOLO: usa um detector simulado (por cor)
em uma foto sintética. Rode com:  python teste_pipeline.py
Se a contagem final for igual ao número de animais desenhados, a divisão em
blocos, a remoção de duplicatas, o desenho e a planilha estão funcionando.
"""
import os
import random
import sys
import tempfile

import cv2
import numpy as np
from openpyxl import load_workbook

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nucleo import gerar_blocos, processar_lote, salvar_imagem  # noqa: E402
from relatorio import gerar_planilha  # noqa: E402


class DetectorSimulado:
    """Acha manchas marrons (os 'animais' sintéticos) em cada bloco."""

    def detectar_lote(self, blocos):
        saida = []
        for b in blocos:
            hsv = cv2.cvtColor(b, cv2.COLOR_BGR2HSV)
            mascara = cv2.inRange(hsv, (5, 80, 40), (25, 255, 200))
            n, _, stats, _ = cv2.connectedComponentsWithStats(mascara)
            dets = []
            for i in range(1, n):
                x, y, w, h, area = stats[i]
                if area >= 30:  # ignora ruído (mas aceita animais parcialmente cortados)
                    dets.append((x, y, x + w, y + h, 0.9))
            saida.append(dets)
        return saida


def criar_foto(caminho, largura, altura, n, semente, forcar_bordas):
    rnd = random.Random(semente)
    img = np.full((altura, largura, 3), (60, 140, 70), np.uint8)  # pasto (BGR)
    centros = []
    # animais deliberadamente em cima das bordas dos blocos (x=640, 1152, y=640...)
    for cx in forcar_bordas:
        centros.append((cx, rnd.randint(100, altura - 100)))
    while len(centros) < n:
        c = (rnd.randint(60, largura - 60), rnd.randint(60, altura - 60))
        if all((c[0] - o[0]) ** 2 + (c[1] - o[1]) ** 2 > 90 ** 2 for o in centros):
            centros.append(c)
    # garante distância mínima também entre os forçados
    for c in centros:
        cv2.ellipse(img, c, (28, 16), rnd.randint(0, 180), 0, 360, (30, 70, 130), -1)
    salvar_imagem(caminho, img)
    return len(centros)


def main():
    blocos = gerar_blocos(3000, 2000, 640, 0.2)
    print(f"Blocos para 3000x2000: {len(blocos)}")

    with tempfile.TemporaryDirectory() as tmp:
        pasta_fotos = os.path.join(tmp, "Piquete Norte")
        os.makedirs(pasta_fotos)
        esperado = []
        caminhos = []
        for k, (n, semente) in enumerate([(40, 1), (65, 2), (5, 3)]):
            cam = os.path.join(pasta_fotos, f"voo_{k + 1:02d} áção.jpg")  # acento de propósito
            esperado.append(criar_foto(cam, 3000, 2000, n, semente, [640, 1152, 1664, 2176]))
            caminhos.append(cam)

        saida = os.path.join(tmp, "resultado")
        resultados = processar_lote(caminhos, DetectorSimulado(), saida)
        obtido = [r.contagem for r in resultados]
        print("Esperado:", esperado)
        print("Obtido:  ", obtido)
        assert obtido == esperado, "Contagem diferente do esperado!"

        for r in resultados:
            assert r.caminho_marcada and os.path.getsize(r.caminho_marcada) > 10_000

        xlsx = gerar_planilha(resultados, os.path.join(saida, "contagem_gado.xlsx"),
                              {"Modelo": "simulado"})
        wb = load_workbook(xlsx)
        print("Abas:", wb.sheetnames)
        linhas = list(wb["Por foto"].iter_rows(min_row=2, max_row=4, values_only=True))
        assert [l[2] for l in linhas] == esperado
        assert wb["Por piquete"]["A2"].value == "Piquete Norte"
        assert wb["Por piquete"]["C2"].value == sum(esperado)

        # guarda uma amostra para inspeção visual
        amostra = os.environ.get("AMOSTRA")
        if amostra:
            import shutil
            shutil.copy(resultados[0].caminho_marcada, amostra)
    print("OK - pipeline completo funcionando.")


if __name__ == "__main__":
    main()
