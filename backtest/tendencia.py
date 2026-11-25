"""Backtest: regra atual x regras que concentram em BTC/ETH quando a tendência de alta está confirmada.
Uso: python tendencia.py <pasta>   (baixa as velas de 1h que faltarem para <pasta>/<PAR>.json)
"""
import json, sys
import dados
from datetime import datetime, timezone
from pathlib import Path

d = Path(sys.argv[1]); CUSTO = 0.0015
BASE = {"BTCBRL": .35, "ETHBRL": .15, "SOLBRL": .08, "XRPBRL": .05, "BNBBRL": .04, "LINKBRL": .03}
d.mkdir(parents=True, exist_ok=True)
for s in BASE:
    if not (d / f"{s}.json").exists():
        (d / f"{s}.json").write_text(json.dumps(dados.velas(s)))
S = {s: {int(k): v for k, v in json.loads((d / f"{s}.json").read_text()).items()} for s in BASE}
horas = sorted(set.intersection(*[set(v) for v in S.values()]))
ms = lambda *a: int(datetime(*a, tzinfo=timezone.utc).timestamp() * 1000)
DIA = 86400000


def tendencias(simbolo, dias_media, folga=0.03):
    """Para cada dia: True se a moeda está em tendência de alta (preço acima da média de N dias, com folga contra vai-e-vem)."""
    serie = sorted(S[simbolo].items())
    fech = {}
    for h, p in serie:
        fech[h // DIA] = p  # último preço do dia
    dias = sorted(fech)
    out, alta, janela, soma, trocas = {}, False, [], 0.0, 0
    for dd in dias:
        janela.append(fech[dd]); soma += fech[dd]
        if len(janela) > dias_media: soma -= janela.pop(0)
        media = soma / len(janela)
        antes = alta
        if len(janela) >= min(dias_media, 60):
            if fech[dd] > media * (1 + folga): alta = True
            elif fech[dd] < media * (1 - folga): alta = False
        trocas += antes != alta
        out[dd + 1] = alta  # só vale no dia seguinte (sem olhar o futuro)
    return out, trocas


def alvo_do_dia(regra, alta):
    """Devolve o alvo de cada moeda conforme a regra e a tendência (alta = {simbolo: bool})."""
    a = dict(BASE)
    if regra == "moderada":      # BTC 45 / ETH 20 em alta; o resto igual; reais caem de 30 para até 15
        if alta["BTCBRL"]: a["BTCBRL"] = .45
        if alta["ETHBRL"]: a["ETHBRL"] = .20
    elif regra == "forte":       # BTC 55 / ETH 25 em alta; as outras encolhem; reais caem para até 5
        if alta["BTCBRL"]: a["BTCBRL"] = .55
        if alta["ETHBRL"]: a["ETHBRL"] = .25
        if alta["BTCBRL"] and alta["ETHBRL"]:
            for k in ("SOLBRL", "XRPBRL", "BNBBRL", "LINKBRL"): a[k] = BASE[k] * .75
    elif regra == "quase tudo":  # BTC 65 / ETH 30 em alta (95%), zerando as outras; fora da alta, volta ao normal
        if alta["BTCBRL"] and alta["ETHBRL"]:
            a = {k: 0.0 for k in BASE}; a["BTCBRL"], a["ETHBRL"] = .65, .30
        elif alta["BTCBRL"]:
            a["BTCBRL"] = .65
            for k in ("SOLBRL", "XRPBRL", "BNBBRL", "LINKBRL"): a[k] = 0.0
    return a


def sim(regra, h0, h1, T, gatilho=0.01, cada=4, max_dia=20, minimo=10, marcos=()):
    hs = [h for h in horas if h0 <= h < h1]
    p0 = {a: S[a][hs[0]] for a in BASE}
    q = {a: 1000 * w * (1 - CUSTO) / p0[a] for a, w in BASE.items()}
    reais = 1000 * (1 - sum(BASE.values())); taxas = 1000 * sum(BASE.values()) * CUSTO
    pico, pior, ops, dia, n = 1000, 0, 0, None, 0
    alvo = dict(BASE); alta = {k: False for k in BASE}; fotos = {}
    for i, h in enumerate(hs):
        px = {a: S[a][h] for a in BASE}
        v = reais + sum(q[a] * px[a] for a in BASE)
        if h // DIA != dia:
            dia, n = h // DIA, 0
            alta = {k: T[k].get(dia, False) for k in ("BTCBRL", "ETHBRL")}
            alta.update({k: T[k].get(dia, False) for k in BASE if k in T})
            if regra not in ("parada", "atual", "freio"): alvo = alvo_do_dia(regra, alta)
        for m in marcos:
            if m not in fotos and h >= m: fotos[m] = v
        if regra != "parada" and i % cada == 0:
            while n < max_dia:
                a = max(BASE, key=lambda a: abs(q[a] * px[a] / v - alvo[a]))
                dev = q[a] * px[a] / v - alvo[a]
                g = gatilho
                if regra == "freio" and dev > 0 and alta.get(a): g = 0.05  # em alta, só vende com 5 pontos de desvio
                if abs(dev) < g or abs(dev * v) < minimo: break
                aj = -dev * v
                if aj > 0:
                    aj = min(aj, reais)
                    if aj < minimo: break
                    q[a] += aj * (1 - CUSTO) / px[a]; reais -= aj
                else:
                    q[a] -= -aj / px[a]; reais += -aj * (1 - CUSTO)
                taxas += abs(aj) * CUSTO; ops += 1; n += 1
                v = reais + sum(q[a] * px[a] for a in BASE)
        pico = max(pico, v); pior = min(pior, v / pico - 1)
    return v, pior, ops, taxas, len(hs) / 24, fotos


REGRAS = [("parada", "Sem robô (compra e nunca mexe)"), ("atual", "Regra atual (alvo fixo, BTC 35 / ETH 15)"),
          ("freio", "Freio de venda na alta"), ("moderada", "Concentra moderado (BTC 45 / ETH 20)"),
          ("forte", "Concentra forte (BTC 55 / ETH 25)"), ("quase tudo", "Quase tudo em BTC/ETH (65 / 30)")]
INI, FIM = ms(2021, 6, 18), ms(2026, 12, 1)
ANOS = [ms(a, 1, 1) for a in range(2022, 2027)]

for media in (200, 100):
    T = {}; trocas = {}
    for k in BASE: T[k], trocas[k] = tendencias(k, media)
    print(f"\n===== sinal de alta: preço acima da média de {media} dias (folga de 3%) · BTC trocou de sinal {trocas['BTCBRL']}x, ETH {trocas['ETHBRL']}x =====")
    print(f"{'regra':44s} {'total':>7s} {'pior queda':>10s} {'ops/mês':>8s} {'taxas':>7s} | por ano: 2021(2ºsem) 2022 2023 2024 2025 2026")
    for cod, nome in REGRAS:
        v, pior, ops, tx, dias, fotos = sim(cod, INI, FIM, T, marcos=ANOS)
        pts = [1000] + [fotos[m] for m in ANOS if m in fotos] + [v]
        anos = " ".join(f"{pts[i + 1] / pts[i] * 100 - 100:+5.0f}%" for i in range(len(pts) - 1))
        print(f"{nome:44s} {v / 10 - 100:+6.0f}% {pior * 100:9.0f}% {ops / dias * 30:8.1f} {tx:7.0f} | {anos}")
    v, pior, *_ = sim("atual", ms(2024, 1, 1), FIM, T); print("validação 2024-26:", end=" ")
    for cod, nome in REGRAS:
        v, pior, ops, tx, dias, _ = sim(cod, ms(2024, 1, 1), FIM, T)
        print(f"{cod} {v / 10 - 100:+.0f}% (queda {pior * 100:.0f}%)", end=" · ")
    print()

print("\nmoedas no período:", " ".join(f"{s[:-3]} {S[s][[h for h in horas if h < FIM][-1]] / S[s][[h for h in horas if h >= INI][0]] * 100 - 100:+.0f}%" for s in BASE))
