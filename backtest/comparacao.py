"""Compara rebalanceamento por calendário e faixas largas.

Uso: python comparacao.py <velas_1h.csv>
"""
import sys
from simulador import *
velas = carregar(sys.argv[1])
def calendario(v, chave):
    c = Carteira(CAPITAL); _, b0, e0 = v[0]; comprar_alvo(c, {"btc": b0, "eth": e0}, ALVO)
    curva, ult = [], chave(data(v[0][0]))
    for t, b, e in v:
        px = {"btc": b, "eth": e}; k = chave(data(t))
        if k != ult:
            ult = k; val = c.valor(px)
            for a in ("btc", "eth"):
                aj = ALVO[a] * val - c.qtd[a] * px[a]
                if abs(aj) >= ORDEM_MIN: c.negociar(a, aj, px)
        curva.append(c.valor(px))
    return curva, c
blocos = {"completo 2021-26": ((2021,1,1),(2026,11,26)), "calibração 2021-23": ((2021,1,1),(2024,1,1)), "validação 2024-26": ((2024,1,1),(2026,11,26))}
print(f"{'estratégia':28s}" + "".join(f"{n:>22s}" for n in blocos))
linhas = {
 "parada (sem rebalancear)": lambda v: parada(v),
 "mensal": lambda v: calendario(v, lambda d: (d.year, d.month)),
 "trimestral": lambda v: calendario(v, lambda d: (d.year, (d.month-1)//3)),
 "anual": lambda v: anual(v),
 "robô faixa 5 pts": lambda v: robo(v, .05, .03)[:2],
 "robô faixa 10 pts": lambda v: robo(v, .10, .06)[:2],
 "robô faixa 15 pts": lambda v: robo(v, .15, .09)[:2],
 "robô faixa 20 pts": lambda v: robo(v, .20, .12)[:2],
}
for nome, fn in linhas.items():
    cel = []
    for a, b in blocos.values():
        cv, c = fn(periodo(velas, a, b)); r = resumo(cv, c)
        cel.append(f"{r['retorno_pct']:+.0f}% q{r['queda_max_pct']:.0f}% n{r['operacoes']}")
    print(f"{nome:28s}" + "".join(f"{x:>22s}" for x in cel))
