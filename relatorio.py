"""Geração da planilha Excel com a contagem por foto e por piquete."""
from __future__ import annotations

import os
from collections import OrderedDict
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from nucleo import ResultadoImagem

CABECALHO_FILL = PatternFill("solid", fgColor="2F5D3A")
CABECALHO_FONT = Font(bold=True, color="FFFFFF")


def _cabecalho(ws, titulos):
    ws.append(titulos)
    for c in ws[1]:
        c.fill = CABECALHO_FILL
        c.font = CABECALHO_FONT
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.freeze_panes = "A2"


def _ajustar_larguras(ws, larguras):
    for i, w in enumerate(larguras, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w


def piquete_da_foto(caminho: str) -> str:
    """Usa o nome da pasta que contém a foto como identificação do piquete."""
    return os.path.basename(os.path.dirname(os.path.abspath(caminho))) or "-"


def gerar_planilha(resultados: list[ResultadoImagem], destino: str,
                   parametros: dict | None = None) -> str:
    wb = Workbook()

    # ---- Aba 1: Por foto ----
    ws = wb.active
    ws.title = "Por foto"
    _cabecalho(ws, ["Foto", "Piquete (pasta)", "Animais contados",
                    "Confiança média", "Largura (px)", "Altura (px)", "Imagem marcada"])
    for r in resultados:
        ws.append([
            os.path.basename(r.caminho),
            piquete_da_foto(r.caminho),
            r.contagem,
            round(r.confianca_media, 3),
            r.largura,
            r.altura,
            os.path.basename(r.caminho_marcada) if r.caminho_marcada else "",
        ])
    ultima = ws.max_row
    ws.append([])
    ws.append(["TOTAL", "", f"=SUM(C2:C{ultima})"])
    for c in ws[ws.max_row]:
        c.font = Font(bold=True)
    _ajustar_larguras(ws, [36, 24, 18, 16, 14, 14, 36])
    ws.row_dimensions[1].height = 30

    # ---- Aba 2: Por piquete ----
    ws2 = wb.create_sheet("Por piquete")
    _cabecalho(ws2, ["Piquete (pasta)", "Fotos", "Soma dos animais contados", "Maior contagem em uma foto"])
    grupos: "OrderedDict[str, list[ResultadoImagem]]" = OrderedDict()
    for r in resultados:
        grupos.setdefault(piquete_da_foto(r.caminho), []).append(r)
    for nome, lista in grupos.items():
        ws2.append([nome, len(lista), sum(x.contagem for x in lista),
                    max(x.contagem for x in lista)])
    ws2.append([])
    ws2.append(["Atenção: se duas fotos do mesmo piquete mostram a mesma área, "
                "os animais foram contados nas duas. Some apenas fotos sem sobreposição "
                "ou use a maior contagem."])
    ws2.cell(row=ws2.max_row, column=1).alignment = Alignment(wrap_text=True)
    _ajustar_larguras(ws2, [28, 10, 26, 26])
    ws2.row_dimensions[1].height = 30

    # ---- Aba 3: Informações ----
    ws3 = wb.create_sheet("Informações")
    ws3.append(["Gerado em", datetime.now().strftime("%d/%m/%Y %H:%M")])
    ws3.append(["Fotos processadas", len(resultados)])
    ws3.append(["Total de animais (soma)", sum(r.contagem for r in resultados)])
    for k, v in (parametros or {}).items():
        ws3.append([k, v])
    ws3.append([])
    ws3.append(["Observação", "Contagem automática por visão computacional. Confira por amostragem "
                              "nas imagens marcadas antes de usar o número oficialmente."])
    _ajustar_larguras(ws3, [28, 80])
    for row in ws3.iter_rows():
        row[0].font = Font(bold=True)

    os.makedirs(os.path.dirname(os.path.abspath(destino)), exist_ok=True)
    wb.save(destino)
    return destino
