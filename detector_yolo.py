"""Detector baseado em YOLO (biblioteca ultralytics).

Com o modelo pré-treinado (COCO) usa a classe "cow". Se você treinar um
modelo próprio com fotos aéreas (recomendado, veja o README), basta apontar
para o arquivo .pt: se ele tiver uma classe chamada gado/cow/boi/vaca/cattle
só ela é usada; caso contrário, todas as classes contam.
"""
from __future__ import annotations

import numpy as np

NOMES_GADO = {"cow", "cattle", "gado", "boi", "vaca", "bovino"}


class DetectorYolo:
    def __init__(self, caminho_modelo: str, confianca: float = 0.25,
                 tamanho_img: int = 640, dispositivo: str | None = None):
        from ultralytics import YOLO  # importado aqui para a interface abrir rápido

        self.modelo = YOLO(caminho_modelo)
        self.confianca = confianca
        self.tamanho_img = tamanho_img
        self.dispositivo = dispositivo
        nomes = self.modelo.names
        ids = [i for i, n in nomes.items() if str(n).lower() in NOMES_GADO]
        self.classes = ids or None

    def detectar_lote(self, blocos: list[np.ndarray]) -> list[list[tuple]]:
        resultados = self.modelo.predict(
            blocos,
            conf=self.confianca,
            imgsz=self.tamanho_img,
            classes=self.classes,
            device=self.dispositivo,
            verbose=False,
        )
        saida: list[list[tuple]] = []
        for r in resultados:
            caixas = r.boxes.xyxy.cpu().numpy()
            confs = r.boxes.conf.cpu().numpy()
            saida.append([(float(c[0]), float(c[1]), float(c[2]), float(c[3]), float(s))
                          for c, s in zip(caixas, confs)])
        return saida
