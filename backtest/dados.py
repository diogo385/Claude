"""Baixa velas de 1 hora (BTC/BRL e ETH/BRL) do arquivo público da Binance.

Uso: python dados.py <pasta_destino>
Gera <pasta_destino>/velas_1h.csv com colunas: hora, btc, eth (preço de fechamento em R$).
"""
import csv, io, sys, zipfile, json, urllib.request
from datetime import datetime, timezone
from pathlib import Path

PARES = {"btc": "BTCBRL", "eth": "ETHBRL"}
INICIO = (2021, 1)
ARQUIVO = "https://data.binance.vision/data/spot/monthly/klines/{s}/1h/{s}-1h-{a}-{m:02d}.zip"
API = "https://data-api.binance.vision/api/v3/klines?symbol={s}&interval=1h&limit=1000&startTime={t}"


def baixar(url):
    with urllib.request.urlopen(url, timeout=60) as r:
        return r.read()


def ms(t):
    t = int(t)
    return t // 1000 if t > 10**14 else t  # a partir de 2025 a Binance usa microssegundos


def meses_ate_hoje():
    hoje = datetime.now(timezone.utc)
    a, m = INICIO
    while (a, m) < (hoje.year, hoje.month):
        yield a, m
        a, m = (a + 1, 1) if m == 12 else (a, m + 1)


def velas(simbolo):
    fech = {}
    for a, m in meses_ate_hoje():
        try:
            z = zipfile.ZipFile(io.BytesIO(baixar(ARQUIVO.format(s=simbolo, a=a, m=m))))
        except Exception:
            continue  # mês ainda não publicado
        with z.open(z.namelist()[0]) as f:
            for linha in csv.reader(io.TextIOWrapper(f)):
                if linha and linha[0].isdigit():
                    fech[ms(linha[0])] = float(linha[4])
    # completa o mês corrente pela API pública
    t = max(fech) + 3600_000 if fech else 0
    while True:
        lote = json.loads(baixar(API.format(s=simbolo, t=t)))
        if not lote:
            break
        for k in lote:
            fech[ms(k[0])] = float(k[4])
        t = ms(lote[-1][0]) + 3600_000
        if len(lote) < 1000:
            break
    return fech


def main(destino):
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    series = {nome: velas(s) for nome, s in PARES.items()}
    horas = sorted(set(series["btc"]) & set(series["eth"]))
    with open(destino / "velas_1h.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["hora", "btc", "eth"])
        for h in horas:
            w.writerow([h, series["btc"][h], series["eth"][h]])
    ini = datetime.fromtimestamp(horas[0] / 1000, timezone.utc)
    fim = datetime.fromtimestamp(horas[-1] / 1000, timezone.utc)
    print(f"{len(horas)} horas de {ini:%Y-%m-%d} a {fim:%Y-%m-%d %H:%M} UTC")


if __name__ == "__main__":
    main(sys.argv[1])
