"""Contador de Gado - interface gráfica (tkinter).

Uso: escolha as fotos (ou uma pasta), clique em "Contar gado". O programa grava,
na pasta de resultados, as imagens marcadas e a planilha Excel.
"""
from __future__ import annotations

import os
import queue
import sys
import threading
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk

from nucleo import EXTENSOES_IMAGEM, listar_imagens, processar_lote
from relatorio import gerar_planilha

TITULO = "Contador de Gado por Foto Aérea"


def pasta_do_programa() -> str:
    """Pasta onde está o .exe (ou o app.py, em modo desenvolvimento)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def pasta_embutida() -> str:
    """Pasta com arquivos empacotados dentro do .exe (PyInstaller)."""
    return getattr(sys, "_MEIPASS", pasta_do_programa())


def localizar_modelo() -> str:
    """Ordem: modelo/gado.pt ao lado do programa (seu modelo treinado) ->
    modelo embutido no .exe -> yolov8m.pt (baixado na primeira execução)."""
    candidatos = [
        os.path.join(pasta_do_programa(), "modelo", "gado.pt"),
        os.path.join(pasta_embutida(), "modelo", "gado.pt"),
        os.path.join(pasta_embutida(), "modelo", "yolov8m.pt"),
    ]
    for c in candidatos:
        if os.path.isfile(c):
            return c
    return "yolov8m.pt"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(TITULO)
        self.geometry("860x600")
        self.minsize(760, 520)

        self.caminhos: list[str] = []
        self.pasta_saida = tk.StringVar(value=os.path.join(
            os.path.expanduser("~"), "Documents", "ContadorGado"))
        self.modelo = tk.StringVar(value=localizar_modelo())
        self.sensibilidade = tk.DoubleVar(value=0.25)
        self.tamanho_bloco = tk.IntVar(value=640)
        self.fila: "queue.Queue" = queue.Queue()
        self.cancelar = False
        self.trabalhando = False
        self.ultima_pasta = None
        self.mapa_marcadas: dict[str, str] = {}

        self._montar()
        self.after(150, self._consumir_fila)

    # ---------------- interface ----------------
    def _montar(self):
        pad = {"padx": 10, "pady": 4}

        quadro1 = ttk.LabelFrame(self, text="1. Fotos")
        quadro1.pack(fill="x", **pad)
        ttk.Button(quadro1, text="Escolher fotos...", command=self.escolher_fotos).pack(side="left", padx=6, pady=6)
        ttk.Button(quadro1, text="Escolher pasta...", command=self.escolher_pasta).pack(side="left", padx=6, pady=6)
        self.lbl_fotos = ttk.Label(quadro1, text="Nenhuma foto selecionada")
        self.lbl_fotos.pack(side="left", padx=10)

        quadro2 = ttk.LabelFrame(self, text="2. Configurações")
        quadro2.pack(fill="x", **pad)
        quadro2.columnconfigure(1, weight=1)
        ttk.Label(quadro2, text="Pasta de resultados:").grid(row=0, column=0, sticky="w", padx=6, pady=3)
        ttk.Entry(quadro2, textvariable=self.pasta_saida).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Button(quadro2, text="Alterar...", command=self.escolher_saida).grid(row=0, column=2, padx=6)

        ttk.Label(quadro2, text="Modelo (.pt):").grid(row=1, column=0, sticky="w", padx=6, pady=3)
        ttk.Entry(quadro2, textvariable=self.modelo).grid(row=1, column=1, sticky="ew", padx=6)
        ttk.Button(quadro2, text="Alterar...", command=self.escolher_modelo).grid(row=1, column=2, padx=6)

        ttk.Label(quadro2, text="Sensibilidade (menor = acha mais):").grid(row=2, column=0, sticky="w", padx=6, pady=3)
        linha = ttk.Frame(quadro2)
        linha.grid(row=2, column=1, sticky="w", padx=6)
        ttk.Scale(linha, from_=0.05, to=0.90, variable=self.sensibilidade, length=220,
                  command=lambda _=None: self.lbl_sens.config(text=f"{self.sensibilidade.get():.2f}")).pack(side="left")
        self.lbl_sens = ttk.Label(linha, text="0.25", width=5)
        self.lbl_sens.pack(side="left", padx=6)

        ttk.Label(quadro2, text="Tamanho do bloco (px):").grid(row=3, column=0, sticky="w", padx=6, pady=3)
        ttk.Combobox(quadro2, textvariable=self.tamanho_bloco, values=[416, 640, 960, 1280],
                     width=8, state="readonly").grid(row=3, column=1, sticky="w", padx=6)

        quadro3 = ttk.Frame(self)
        quadro3.pack(fill="x", **pad)
        self.btn_contar = ttk.Button(quadro3, text="Contar gado", command=self.iniciar)
        self.btn_contar.pack(side="left", padx=6)
        self.btn_cancelar = ttk.Button(quadro3, text="Cancelar", command=self.pedir_cancelar, state="disabled")
        self.btn_cancelar.pack(side="left", padx=6)
        self.btn_abrir = ttk.Button(quadro3, text="Abrir pasta de resultados", command=self.abrir_resultados, state="disabled")
        self.btn_abrir.pack(side="left", padx=6)
        self.lbl_total = ttk.Label(quadro3, text="Total: -", font=("Segoe UI", 14, "bold"))
        self.lbl_total.pack(side="right", padx=10)

        self.barra = ttk.Progressbar(self, mode="determinate")
        self.barra.pack(fill="x", padx=10, pady=2)
        self.lbl_status = ttk.Label(self, text="Pronto.")
        self.lbl_status.pack(anchor="w", padx=10)

        quadro4 = ttk.LabelFrame(self, text="Resultados (dê dois cliques para ver a foto marcada)")
        quadro4.pack(fill="both", expand=True, **pad)
        self.tabela = ttk.Treeview(quadro4, columns=("foto", "piquete", "qtd"), show="headings", height=8)
        self.tabela.heading("foto", text="Foto")
        self.tabela.heading("piquete", text="Piquete (pasta)")
        self.tabela.heading("qtd", text="Animais")
        self.tabela.column("foto", width=380)
        self.tabela.column("piquete", width=220)
        self.tabela.column("qtd", width=90, anchor="center")
        rolagem = ttk.Scrollbar(quadro4, orient="vertical", command=self.tabela.yview)
        self.tabela.configure(yscrollcommand=rolagem.set)
        self.tabela.pack(side="left", fill="both", expand=True)
        rolagem.pack(side="right", fill="y")
        self.tabela.bind("<Double-1>", self.abrir_marcada)

    # ---------------- seleção ----------------
    def _definir_fotos(self, caminhos: list[str]):
        self.caminhos = caminhos
        n = len(caminhos)
        self.lbl_fotos.config(text=f"{n} foto(s) selecionada(s)" if n else "Nenhuma foto selecionada")

    def escolher_fotos(self):
        tipos = " ".join(f"*{e}" for e in EXTENSOES_IMAGEM)
        arquivos = filedialog.askopenfilenames(title="Escolha as fotos aéreas",
                                               filetypes=[("Imagens", tipos), ("Todos", "*.*")])
        if arquivos:
            self._definir_fotos(list(arquivos))

    def escolher_pasta(self):
        pasta = filedialog.askdirectory(title="Escolha a pasta com as fotos (subpastas incluídas)")
        if pasta:
            fotos = listar_imagens(pasta, recursivo=True)
            if not fotos:
                messagebox.showwarning(TITULO, "Nenhuma imagem encontrada nessa pasta.")
                return
            self._definir_fotos(fotos)

    def escolher_saida(self):
        pasta = filedialog.askdirectory(title="Pasta para salvar os resultados")
        if pasta:
            self.pasta_saida.set(pasta)

    def escolher_modelo(self):
        arq = filedialog.askopenfilename(title="Modelo YOLO (.pt)", filetypes=[("Modelo", "*.pt")])
        if arq:
            self.modelo.set(arq)

    # ---------------- execução ----------------
    def iniciar(self):
        if self.trabalhando:
            return
        if not self.caminhos:
            messagebox.showinfo(TITULO, "Escolha as fotos ou uma pasta primeiro.")
            return
        pasta = os.path.join(self.pasta_saida.get(), datetime.now().strftime("contagem_%Y-%m-%d_%H%M%S"))
        self.ultima_pasta = pasta
        self.mapa_marcadas.clear()
        for item in self.tabela.get_children():
            self.tabela.delete(item)
        self.lbl_total.config(text="Total: -")
        self.cancelar = False
        self.trabalhando = True
        self.btn_contar.config(state="disabled")
        self.btn_cancelar.config(state="normal")
        self.btn_abrir.config(state="disabled")
        self.barra.config(value=0, maximum=len(self.caminhos))
        self.lbl_status.config(text="Carregando o modelo (na primeira vez pode demorar)...")

        parametros = {
            "Modelo": self.modelo.get(),
            "Sensibilidade (confiança mínima)": round(self.sensibilidade.get(), 2),
            "Tamanho do bloco (px)": self.tamanho_bloco.get(),
            "Sobreposição dos blocos": "20%",
        }
        args = (list(self.caminhos), pasta, self.modelo.get(),
                float(self.sensibilidade.get()), int(self.tamanho_bloco.get()), parametros)
        threading.Thread(target=self._trabalho, args=args, daemon=True).start()

    def _trabalho(self, caminhos, pasta, modelo, confianca, bloco, parametros):
        try:
            from detector_yolo import DetectorYolo
            detector = DetectorYolo(modelo, confianca=confianca, tamanho_img=bloco)

            def progresso(i, total, res, erro):
                self.fila.put(("progresso", i, total, res, erro))

            resultados = processar_lote(caminhos, detector, pasta, tamanho_bloco=bloco,
                                        progresso=progresso, cancelar=lambda: self.cancelar)
            planilha = None
            if resultados:
                planilha = gerar_planilha(resultados, os.path.join(pasta, "contagem_gado.xlsx"), parametros)
            self.fila.put(("fim", resultados, planilha))
        except Exception as e:
            self.fila.put(("falha", str(e)))

    def _consumir_fila(self):
        try:
            while True:
                msg = self.fila.get_nowait()
                tipo = msg[0]
                if tipo == "progresso":
                    _, i, total, res, erro = msg
                    self.barra.config(value=i)
                    if res:
                        from relatorio import piquete_da_foto
                        nome = os.path.basename(res.caminho)
                        self.tabela.insert("", "end", iid=res.caminho,
                                           values=(nome, piquete_da_foto(res.caminho), res.contagem))
                        if res.caminho_marcada:
                            self.mapa_marcadas[res.caminho] = res.caminho_marcada
                        self.lbl_status.config(text=f"Foto {i} de {total}: {nome} -> {res.contagem} animais")
                    else:
                        self.lbl_status.config(text=f"Erro: {erro}")
                elif tipo == "fim":
                    _, resultados, planilha = msg
                    total = sum(r.contagem for r in resultados)
                    self.lbl_total.config(text=f"Total: {total}")
                    self.lbl_status.config(text="Cancelado." if self.cancelar else "Concluído. Planilha e imagens salvas.")
                    self._liberar()
                    self.btn_abrir.config(state="normal")
                elif tipo == "falha":
                    self._liberar()
                    self.lbl_status.config(text="Falhou.")
                    messagebox.showerror(TITULO, f"Não foi possível concluir:\n\n{msg[1]}")
        except queue.Empty:
            pass
        self.after(150, self._consumir_fila)

    def _liberar(self):
        self.trabalhando = False
        self.btn_contar.config(state="normal")
        self.btn_cancelar.config(state="disabled")

    def pedir_cancelar(self):
        self.cancelar = True
        self.lbl_status.config(text="Cancelando após a foto atual...")

    # ---------------- abrir arquivos ----------------
    def _abrir(self, caminho: str):
        try:
            if sys.platform.startswith("win"):
                os.startfile(caminho)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                os.system(f'open "{caminho}"')
            else:
                os.system(f'xdg-open "{caminho}"')
        except Exception as e:
            messagebox.showerror(TITULO, str(e))

    def abrir_resultados(self):
        if self.ultima_pasta and os.path.isdir(self.ultima_pasta):
            self._abrir(self.ultima_pasta)

    def abrir_marcada(self, _evento=None):
        sel = self.tabela.selection()
        if sel and sel[0] in self.mapa_marcadas:
            self._abrir(self.mapa_marcadas[sel[0]])


if __name__ == "__main__":
    App().mainloop()
