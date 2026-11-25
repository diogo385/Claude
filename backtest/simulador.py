"""Backtest do rebalanceamento 50/15/35 contra referências simples.

Uso: python simulador.py <velas_1h.csv> <pasta_saida>
"""
import csv, json, sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

TAXA = 0.001        # 0,1% por operação (Binance)
DESLIZE = 0.0005    # 0,05% de diferença de preço na execução
CUSTO = TAXA + DESLIZE
ALVO = {"btc": 0.50, "eth": 0.15}   # o resto (35%) fica em reais
CAPITAL = 1000.0
ORDEM_MIN = 20.0
ORDEM_MAX = 0.15    # fração do patrimônio
OPS_DIA = 6
VOL_LIMITE, VOL_PAUSA_H = 0.06, 4


def carregar(caminho):
    with open(caminho) as f:
        r = csv.DictReader(f)
        return [(int(x["hora"]), float(x["btc"]), float(x["eth"])) for x in r]


def data(ms):
    return datetime.fromtimestamp(ms / 1000, timezone.utc)


@dataclass
class Carteira:
    reais: float
    qtd: dict = field(default_factory=lambda: {"btc": 0.0, "eth": 0.0})
    ops: int = 0
    taxas: float = 0.0

    def valor(self, px):
        return self.reais + sum(self.qtd[a] * px[a] for a in self.qtd)

    def negociar(self, ativo, reais, px):
        """reais > 0 compra, < 0 vende. Nunca usa saldo que não existe."""
        if reais > 0:
            reais = min(reais, self.reais)
            self.qtd[ativo] += reais * (1 - CUSTO) / px[ativo]
            self.reais -= reais
        else:
            reais = min(-reais, self.qtd[ativo] * px[ativo])
            self.qtd[ativo] -= reais / px[ativo]
            self.reais += reais * (1 - CUSTO)
        self.taxas += reais * CUSTO
        self.ops += 1
        assert self.reais >= -1e-9 and min(self.qtd.values()) >= -1e-12, "saldo negativo"


def comprar_alvo(c, px, alvo):
    v = c.reais
    for a, p in alvo.items():
        c.negociar(a, v * p, px)


def robo(velas, faixa_btc, faixa_eth):
    """Estratégia do plano: rebalanceia o ativo que sai da faixa, com as travas do porteiro."""
    c = Carteira(CAPITAL)
    _, b0, e0 = velas[0]
    comprar_alvo(c, {"btc": b0, "eth": e0}, ALVO)
    faixa = {"btc": faixa_btc, "eth": faixa_eth}
    curva, pausa_ate, dia, ops_dia, pico = [], 0, None, 0, CAPITAL
    alertas_queda = 0
    ant = None
    for t, b, e in velas:
        px = {"btc": b, "eth": e}
        v = c.valor(px)
        pico = max(pico, v)
        if v < pico * 0.75:
            alertas_queda += 1
        d = t // 86_400_000
        if d != dia:
            dia, ops_dia = d, 0
        if ant and max(abs(b / ant[0] - 1), abs(e / ant[1] - 1)) > VOL_LIMITE:
            pausa_ate = t + VOL_PAUSA_H * 3_600_000
        ant = (b, e)
        if t >= pausa_ate:
            for a in ("btc", "eth"):
                peso = c.qtd[a] * px[a] / v
                if abs(peso - ALVO[a]) > faixa[a] and ops_dia < OPS_DIA:
                    ajuste = (ALVO[a] - peso) * v
                    ajuste = max(-ORDEM_MAX * v, min(ORDEM_MAX * v, ajuste))
                    if abs(ajuste) >= ORDEM_MIN:
                        c.negociar(a, ajuste, px)
                        ops_dia += 1
                        v = c.valor(px)
        curva.append(c.valor(px))
    return curva, c, alertas_queda > 0


def parada(velas):
    c = Carteira(CAPITAL)
    _, b0, e0 = velas[0]
    comprar_alvo(c, {"btc": b0, "eth": e0}, ALVO)
    return [c.valor({"btc": b, "eth": e}) for _, b, e in velas], c


def anual(velas):
    """Rebalanceamento manual uma vez por ano (1º de janeiro)."""
    c = Carteira(CAPITAL)
    _, b0, e0 = velas[0]
    comprar_alvo(c, {"btc": b0, "eth": e0}, ALVO)
    curva, ano = [], data(velas[0][0]).year
    for t, b, e in velas:
        px = {"btc": b, "eth": e}
        if data(t).year != ano:
            ano = data(t).year
            v = c.valor(px)
            for a in ("btc", "eth"):
                ajuste = ALVO[a] * v - c.qtd[a] * px[a]
                if abs(ajuste) >= ORDEM_MIN:
                    c.negociar(a, ajuste, px)
        curva.append(c.valor(px))
    return curva, c


def btc_puro(velas):
    c = Carteira(CAPITAL)
    _, b0, e0 = velas[0]
    comprar_alvo(c, {"btc": b0, "eth": e0}, {"btc": 1.0})
    return [c.valor({"btc": b, "eth": e}) for _, b, e in velas], c


def dca_btc(velas, meses=12):
    """Compra BTC em 12 parcelas mensais iguais e depois segura."""
    c = Carteira(CAPITAL)
    parcela, feitas, mes, curva = CAPITAL / meses, 0, None, []
    for t, b, e in velas:
        px = {"btc": b, "eth": e}
        m = (data(t).year, data(t).month)
        if m != mes and feitas < meses:
            mes = m
            c.negociar("btc", parcela, px)
            feitas += 1
        curva.append(c.valor(px))
    return curva, c


def queda_max(curva):
    pico, pior = curva[0], 0.0
    for v in curva:
        pico = max(pico, v)
        pior = min(pior, v / pico - 1)
    return pior


def resumo(curva, c):
    return {"final": round(curva[-1], 2), "retorno_pct": round((curva[-1] / CAPITAL - 1) * 100, 1),
            "queda_max_pct": round(queda_max(curva) * 100, 1), "operacoes": c.ops, "taxas": round(c.taxas, 2)}


def periodo(velas, ini, fim):
    a = int(datetime(*ini, tzinfo=timezone.utc).timestamp() * 1000)
    b = int(datetime(*fim, tzinfo=timezone.utc).timestamp() * 1000)
    return [v for v in velas if a <= v[0] < b]


def rodar(velas, faixa=0.05):
    r = {}
    curva_r, c_r, queda25 = robo(velas, faixa, faixa * 0.6)
    curva_p, c_p = parada(velas)
    r["robo"] = resumo(curva_r, c_r) | {"alerta_queda_25": queda25}
    r["parada"] = resumo(curva_p, c_p)
    r["anual"] = resumo(*anual(velas))
    r["dca_btc"] = resumo(*dca_btc(velas))
    r["btc"] = resumo(*btc_puro(velas))
    # trava "robô 5 pontos pior que a carteira parada"
    gatilho = next((i for i, (x, y) in enumerate(zip(curva_r, curva_p)) if (x - y) / CAPITAL < -0.05), None)
    r["robo"]["trava_5pts_disparou"] = None if gatilho is None else data(velas[gatilho][0]).strftime("%Y-%m-%d")
    r["robo"]["vs_parada_pts"] = round(r["robo"]["retorno_pct"] - r["parada"]["retorno_pct"], 1)
    return r, curva_r, curva_p


def main(entrada, saida):
    velas = carregar(entrada)
    saida = Path(saida)
    saida.mkdir(parents=True, exist_ok=True)
    fim_dados = data(velas[-1][0])
    fim = (fim_dados.year, fim_dados.month, fim_dados.day, fim_dados.hour + 1 if fim_dados.hour < 23 else 23)
    res = {"premissas": {"taxa_pct": TAXA * 100, "deslize_pct": DESLIZE * 100, "capital": CAPITAL,
                         "alvo": "50% BTC / 15% ETH / 35% reais", "dados": f"{data(velas[0][0]):%Y-%m-%d} a {fim_dados:%Y-%m-%d}"}}
    blocos = {"completo": ((2021, 1, 1), fim), "calibracao_2021_2023": ((2021, 1, 1), (2024, 1, 1)),
              "validacao_2024_2026": ((2024, 1, 1), fim)}
    curvas = {}
    for nome, (a, b) in blocos.items():
        v = periodo(velas, a, b)
        res[nome], cr, cp = rodar(v)
        if nome == "completo":
            curvas = {"hora": [x[0] for x in v], "robo": cr, "parada": cp, "btc": btc_puro(v)[0]}
    res["sensibilidade_faixa"] = {}
    for f in (0.03, 0.05, 0.10):
        for nome in ("calibracao_2021_2023", "validacao_2024_2026"):
            r, _, _ = rodar(periodo(velas, *blocos[nome]), f)
            res["sensibilidade_faixa"][f"{int(f*100)}pts_{nome}"] = {"robo_pct": r["robo"]["retorno_pct"],
                "parada_pct": r["parada"]["retorno_pct"], "vs_parada_pts": r["robo"]["vs_parada_pts"], "operacoes": r["robo"]["operacoes"]}
    res["ano_a_ano"] = {}
    for ano in range(2021, fim_dados.year + 1):
        v = periodo(velas, (ano, 1, 1), (ano + 1, 1, 1) if ano < fim_dados.year else fim)
        r, _, _ = rodar(v)
        res["ano_a_ano"][ano] = {k: r[k]["retorno_pct"] for k in ("robo", "parada", "anual", "btc")} | {
            "vs_parada_pts": r["robo"]["vs_parada_pts"], "operacoes": r["robo"]["operacoes"], "taxas": r["robo"]["taxas"]}
    (saida / "resultado.json").write_text(json.dumps(res, indent=2, ensure_ascii=False))
    # curva diária para gráfico
    with open(saida / "curva_diaria.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["data", "robo", "parada", "btc"])
        ultimo = None
        for i, h in enumerate(curvas["hora"]):
            d = data(h).strftime("%Y-%m-%d")
            if d != ultimo:
                w.writerow([d, round(curvas["robo"][i], 2), round(curvas["parada"][i], 2), round(curvas["btc"][i], 2)])
                ultimo = d
    print(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
