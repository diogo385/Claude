"""Gera o gráfico do backtest. Uso: python grafico.py <pasta_resultado>"""
import csv, sys
from datetime import datetime
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as md

pasta = Path(sys.argv[1])
linhas = list(csv.DictReader(open(pasta / "curva_diaria.csv")))
d = [datetime.strptime(x["data"], "%Y-%m-%d") for x in linhas]
fig, ax = plt.subplots(figsize=(11, 5.2), dpi=150)
fig.patch.set_facecolor("#0b111c"); ax.set_facecolor("#0b111c")
for chave, rot, cor, lw in [("btc", "100% BTC (comprar e segurar)", "#7a8496", 1.2),
                            ("parada", "Carteira 50/15/35 parada", "#ffb547", 1.4),
                            ("robo", "Robô (faixa de 5 pontos)", "#3ee0ff", 2.0)]:
    ax.plot(d, [float(x[chave]) for x in linhas], label=rot, color=cor, lw=lw)
ax.axhline(1000, color="#2c4170", lw=1, ls="--")
ax.axvline(datetime(2024, 1, 1), color="#9b7bff", lw=1, ls=":")
ax.text(datetime(2024, 1, 20), ax.get_ylim()[1] * 0.93, "validação →", color="#9b7bff", fontsize=9)
ax.set_title("R$ 1.000 aplicados em jan/2021 · BTC/BRL e ETH/BRL · taxas incluídas", color="#dbe6ff", fontsize=11, loc="left")
ax.tick_params(colors="#7d8db0"); ax.xaxis.set_major_formatter(md.DateFormatter("%Y"))
ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"R$ {v:,.0f}".replace(",", ".")))
for s in ax.spines.values(): s.set_color("#1d2a44")
ax.grid(color="#1d2a44", lw=0.6)
leg = ax.legend(facecolor="#0b111c", edgecolor="#1d2a44", labelcolor="#dbe6ff", fontsize=9, loc="upper left")
fig.tight_layout(); fig.savefig(pasta / "grafico.png", facecolor=fig.get_facecolor())
print("ok")
