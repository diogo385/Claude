"""Argos Trade Cripto · robô de rebalanceamento em MODO SIMULADO (carteira diversificada).

- Usa preços reais e públicos da Binance (sem conta, sem chave).
- Opera um dinheiro de mentira: R$ 1.000 iniciais.
- Carteira-alvo: BTC 35% · ETH 15% · SOL 8% · XRP 5% · BNB 4% · LINK 3% · reais 30%.
- Checa o mercado a cada 4 horas e opera o ativo mais fora do alvo. Até 3 operações por dia:
  a 1ª quando o desvio chega a 1 ponto; a 2ª e a 3ª só se a oportunidade for muito boa
  (desvio de 2,5 pontos ou mais). O resumo diário sai na checagem das 7h (Brasília).
- Reserva de oportunidade: R$ 500 fora da carteira. Entra em degraus de R$ 125 quando a carteira
  cai 20%, 30%, 40% e 50% desde o pico (medido por cota, sem contar os aportes).
- Carteira satélite (risco maior): aporte de R$ 250 em LTC 20% · DOGE 20% · ADA 18% · AVAX 16% · NEAR 16%
  · reais 10%, com as mesmas regras de operação e sem reserva. Operações em simulado/operacoes_satelite.csv.
- Guarda tudo em simulado/estado.json, simulado/operacoes.csv e simulado/historico.csv.
- Avisa no Telegram se TELEGRAM_TOKEN e TELEGRAM_CHAT_ID estiverem configurados.

Uso: python robo_simulado.py
"""
import csv
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

PASTA = Path(__file__).resolve().parent
ESTADO = PASTA / "estado.json"
OPERACOES = PASTA / "operacoes.csv"
HISTORICO = PASTA / "historico.csv"
OPERACOES_SAT = PASTA / "operacoes_satelite.csv"
EXTRATO = PASTA / "extrato.csv"   # toda entrada e saída de dinheiro, com o saldo em reais da conta

VERSAO = 2
CAPITAL = 1000.0
ALVO = {"btc": 0.35, "eth": 0.15, "sol": 0.08, "xrp": 0.05, "bnb": 0.04, "link": 0.03}  # o resto (30%) fica em reais
PARES = {a: a.upper() + "BRL" for a in ALVO}
SAT_APORTE = 250.0
SAT_ALVO = {"ltc": 0.20, "doge": 0.20, "ada": 0.18, "avax": 0.16, "near": 0.16}  # o resto (10%) fica em reais
SAT_PARES = {a: a.upper() + "BRL" for a in SAT_ALVO}
SAT_RESERVA = 100.0      # saldo da satélite, parado, usado só em oportunidades
OPORT_QUEDA = 0.10       # moeda 10% ou mais abaixo do topo dos últimos 14 dias...
OPORT_TOPO_DIAS = 14
OPORT_REPIQUE = 0.03     # ...e 3% ou mais acima do fundo dos últimos 3 dias (parou de cair)
OPORT_FUNDO_DIAS = 3
OPORT_VALOR = 25.0       # quanto compra em cada oportunidade (no máximo 1 posição aberta por moeda)
OPORT_LUCRO = 0.015      # vende com +1,5%: cobre ~0,3% de custos (ida e volta) e deixa ~1,2% de ganho
INTERVALO_CARTEIRAS = 3.5  # horas: rebalanceamento das carteiras segue a cada ~4 h; oportunidades, toda hora
DESVIO_MIN = 0.01        # 1ª operação do dia: ativo 1 ponto ou mais fora do alvo
DESVIO_EXTRA = 0.025     # 2ª e 3ª operações do dia: só com 2,5 pontos ou mais (oportunidade muito boa)
MAX_OPS_DIA = 3          # no máximo 3 operações por dia
HORA_RESUMO = 7          # a partir desta hora (Brasília) manda o resumo do dia
TAXA = 0.001             # 0,1% (Binance)
DESLIZE = 0.0005         # 0,05% de diferença de preço
CUSTO = TAXA + DESLIZE
ORDEM_MIN = 10.0         # ignora ajustes menores que R$ 10 (mínimo da Binance)
FONTES = ["https://data-api.binance.vision", "https://api.binance.com"]
BRASILIA = timezone(timedelta(hours=-3))
ROTULO = "🧪 Argos Trade Cripto · SIMULADO"
RESERVA_INICIAL = 500.0  # saldo disponível na corretora, fora da carteira
DEGRAUS = [0.20, 0.30, 0.40, 0.50]   # quedas da carteira (desde o pico) que liberam a reserva
APORTE = 125.0           # quanto entra em cada degrau


# ---------- utilidades ----------
def brl(v):
    s = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"


def preco(v):
    """Preço com casas suficientes para moedas baratas (ex.: DOGE a R$ 0,3132)."""
    casas = 2 if v >= 10 else 4 if v >= 0.01 else 8
    s = f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"


def num(v, casas):
    return f"{v:.{casas}f}".replace(".", ",")


def pct(v, casas=1):
    return ("+" if v >= 0 else "") + num(v * 100, casas) + "%"


def telegram(texto):
    token, chat = os.environ.get("TELEGRAM_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    print("\n--- mensagem ---\n" + texto + "\n----------------")
    if not token or not chat:
        print("(Telegram não configurado: mensagem só no registro)")
        return
    dados = urllib.parse.urlencode({"chat_id": chat, "text": texto}).encode()
    try:
        urllib.request.urlopen(f"https://api.telegram.org/bot{token}/sendMessage", dados, timeout=30).read()
    except Exception as e:  # não derruba o robô por falha de aviso
        print(f"Falha ao enviar para o Telegram: {type(e).__name__}")


def precos():
    todos = PARES | SAT_PARES
    simbolos = urllib.parse.quote(json.dumps(list(todos.values()), separators=(",", ":")))
    erros = []
    for base in FONTES:
        try:
            with urllib.request.urlopen(f"{base}/api/v3/ticker/price?symbols={simbolos}", timeout=30) as r:
                lido = {x["symbol"]: float(x["price"]) for x in json.loads(r.read())}
            px = {a: lido[p] for a, p in todos.items()}
            if all(v > 0 for v in px.values()):
                return px
        except Exception as e:
            erros.append(f"{base}: {type(e).__name__}")
    raise RuntimeError("Não consegui ler os preços da Binance (" + "; ".join(erros) + ")")


# ---------- carteira ----------
def valor(c, px, alvo=ALVO):
    return c["reais"] + sum(c.get(a, 0.0) * px[a] for a in alvo)


def pesos(c, px, alvo=ALVO):
    v = valor(c, px, alvo)
    return {a: c.get(a, 0.0) * px[a] / v for a in alvo} | {"reais": c["reais"] / v}


def montar(px, alvo=ALVO, capital=CAPITAL):
    c = {"reais": capital}
    for a, p in alvo.items():
        gasto = capital * p
        c[a] = gasto * (1 - CUSTO) / px[a]
        c["reais"] -= gasto
    return c


def estado_inicial(px, agora):
    return {
        "versao": VERSAO,
        "inicio": agora.isoformat(),
        "alvo": ALVO,
        "pares": PARES,
        "gatilho": DESVIO_MIN,
        "gatilho_extra": DESVIO_EXTRA,
        "max_ops_dia": MAX_OPS_DIA,
        "carteira": montar(px),
        "parada": montar(px),            # mesma carteira, nunca rebalanceada (comparação)
        "pico": CAPITAL,
        "operacoes": len(ALVO),
        "rebalanceamentos": 0,
        "taxas": CAPITAL * sum(ALVO.values()) * CUSTO,
        "ultima_execucao": None,
    }


def rebalancear(c, px, limite, ja_feitas, ALVO=ALVO):
    """Opera o(s) ativo(s) mais fora do alvo, até `limite` operações. Nunca usa saldo que não existe.
    A 1ª operação do dia exige DESVIO_MIN; as seguintes exigem DESVIO_EXTRA."""
    feitas = []
    v = valor(c, px, ALVO)
    fila = sorted(ALVO, key=lambda a: -abs(c[a] * px[a] / v - ALVO[a]))
    for a in fila:
        if len(feitas) >= limite:
            break
        peso = c[a] * px[a] / v
        ajuste = ALVO[a] * v - c[a] * px[a]
        gatilho = DESVIO_MIN if ja_feitas + len(feitas) == 0 else DESVIO_EXTRA
        if abs(peso - ALVO[a]) < gatilho or abs(ajuste) < ORDEM_MIN:
            continue
        if ajuste > 0:  # compra
            gasto = min(ajuste, c["reais"])
            qtd = gasto * (1 - CUSTO) / px[a]
            c["reais"] -= gasto
            c[a] += qtd
            feitas.append({"tipo": "COMPRA", "ativo": a, "qtd": qtd, "reais": gasto, "taxa": gasto * CUSTO, "peso_antes": peso})
        else:           # venda
            venda = min(-ajuste, c[a] * px[a])
            qtd = venda / px[a]
            c[a] -= qtd
            c["reais"] += venda * (1 - CUSTO)
            feitas.append({"tipo": "VENDA", "ativo": a, "qtd": qtd, "reais": venda, "taxa": venda * CUSTO, "peso_antes": peso})
        if c["reais"] < -1e-9 or c[a] < -1e-12:
            raise RuntimeError("Trava: saldo negativo detectado. Nenhuma dívida é permitida.")
        v = valor(c, px, ALVO)
    return feitas


def texto_pesos(p, alvo=ALVO):
    return " · ".join(f"{a.upper()} {p[a]*100:.0f}%" for a in alvo) + f" · R$ {p['reais']*100:.0f}%"


def qtd_txt(q):
    return num(q, 6 if q < 1 else 4 if q < 100 else 2)


# ---------- reserva de oportunidade ----------
def preparar_reserva(est, novo):
    """Cria a reserva no estado. Em carteira já existente, ajusta o histórico para incluir os R$ 500."""
    if "reserva" in est:
        return False
    est["reserva"] = {"saldo": RESERVA_INICIAL, "usados": [], "aportes": []}
    est["parada_reserva"] = RESERVA_INICIAL          # na comparação, a carteira parada também tem R$ 500 parados
    est["investido"] = CAPITAL
    est["capital_total"] = CAPITAL + RESERVA_INICIAL
    est["pico_cota"] = max(1.0, est.get("pico", CAPITAL) / CAPITAL)
    if not novo and HISTORICO.exists():
        linhas = HISTORICO.read_text().strip().split("\n")
        novas = [linhas[0]]
        for l in linhas[1:]:
            d, pat, par, n = l.split(";")
            novas.append(f"{d};{float(pat) + RESERVA_INICIAL:.2f};{float(par) + RESERVA_INICIAL:.2f};{n}")
        HISTORICO.write_text("\n".join(novas) + "\n")
    return not novo


def usar_reserva(est, c, v, agora):
    """Aplica os degraus da reserva conforme a queda da cota desde o pico. Devolve os aportes feitos."""
    res = est["reserva"]
    cota = v / est["investido"]
    if cota >= est["pico_cota"]:
        est["pico_cota"] = cota
        res["usados"] = []                    # novo pico: degraus voltam a valer (se ainda houver reserva)
    queda = 1 - cota / est["pico_cota"]
    feitos = []
    for nivel in DEGRAUS:
        if queda >= nivel and nivel not in res["usados"] and res["saldo"] > 0:
            x = min(res["saldo"], APORTE)
            res["saldo"] -= x
            res["usados"].append(nivel)
            c["reais"] += x
            est["investido"] += x
            ap = {"data_hora": agora.strftime("%Y-%m-%d %H:%M"), "degrau": nivel, "valor": x, "queda": round(queda, 4)}
            res["aportes"].append(ap)
            feitos.append(ap)
    return feitos


# ---------- carteira satélite ----------
def preparar_satelite(est, px, agora):
    """Faz o aporte de R$ 250 na carteira satélite (uma vez). Devolve as compras de montagem."""
    if "satelite" in est:
        return []
    c = montar(px, SAT_ALVO, SAT_APORTE)
    est["satelite"] = {
        "inicio": agora.isoformat(), "aporte": SAT_APORTE, "alvo": SAT_ALVO, "pares": SAT_PARES,
        "carteira": c, "parada": dict(c), "ops_dia": {"data": agora.date().isoformat(), "n": 0},
        "rebalanceamentos": 0, "taxas": SAT_APORTE * sum(SAT_ALVO.values()) * CUSTO, "pico": SAT_APORTE,
    }
    est["capital_total"] = est.get("capital_total", CAPITAL) + SAT_APORTE
    return [{"tipo": "COMPRA", "ativo": a, "qtd": c[a], "reais": SAT_APORTE * w, "taxa": SAT_APORTE * w * CUSTO,
             "peso_antes": 0.0, "montagem": True} for a, w in SAT_ALVO.items()]


def fechamentos_horarios(par, horas=OPORT_TOPO_DIAS * 24 + 1):
    for base in FONTES:
        try:
            with urllib.request.urlopen(f"{base}/api/v3/klines?symbol={par}&interval=1h&limit={horas}", timeout=30) as r:
                return [float(k[4]) for k in json.loads(r.read())]
        except Exception:
            continue
    return None


def oportunidades_satelite(est, px, agora):
    """Reserva da satélite: cria (uma vez), vende posições com lucro e compra nas oportunidades.
    Devolve (criada, vendas, compras)."""
    sat = est["satelite"]
    criada = False
    if "reserva" not in sat:
        sat["reserva"] = {"saldo": SAT_RESERVA}
        sat["posicoes"], sat["ultima_oport"], sat["parada_reserva"] = [], {}, SAT_RESERVA
        est["capital_total"] = est.get("capital_total", CAPITAL) + SAT_RESERVA
        criada = True
    res, vendas, compras = sat["reserva"], [], []
    # 1) saída: posição de oportunidade com +30% é vendida e o dinheiro volta para a reserva
    for pos in list(sat["posicoes"]):
        a = pos["ativo"]
        if px[a] >= pos["preco"] * (1 + OPORT_LUCRO):
            bruto = pos["qtd"] * px[a]
            res["saldo"] += bruto * (1 - CUSTO)
            sat["posicoes"].remove(pos)
            vendas.append({"tipo": "LUCRO", "ativo": a, "qtd": pos["qtd"], "reais": bruto, "taxa": bruto * CUSTO,
                           "peso_antes": 0.0, "ganho": bruto * (1 - CUSTO) - pos["custo"]})
    # 2) sinais das moedas e entrada nas oportunidades
    sinais = {}
    for a, par in SAT_PARES.items():
        fech = fechamentos_horarios(par)
        if not fech or len(fech) < 72:
            sinais[a] = {"status": "sem dados"}
            continue
        topo, fundo = max(fech + [px[a]]), min(fech[-(OPORT_FUNDO_DIAS * 24 + 1):] + [px[a]])
        queda, repique = 1 - px[a] / topo, px[a] / fundo - 1
        aberta = any(p["ativo"] == a for p in sat["posicoes"])
        if aberta:
            status = "posição aberta"
        elif queda < OPORT_QUEDA:
            status = "normal"
        elif repique < OPORT_REPIQUE:
            status = "caindo"
        else:
            status = "oportunidade"
        if status == "oportunidade" and res["saldo"] >= OPORT_VALOR:
            qtd = OPORT_VALOR * (1 - CUSTO) / px[a]
            res["saldo"] -= OPORT_VALOR
            sat["posicoes"].append({"ativo": a, "qtd": qtd, "preco": px[a], "custo": OPORT_VALOR, "data": agora.isoformat()})
            compras.append({"tipo": "OPORTUNIDADE", "ativo": a, "qtd": qtd, "reais": OPORT_VALOR, "taxa": OPORT_VALOR * CUSTO,
                            "peso_antes": 0.0, "queda": queda, "repique": repique})
            status = "comprou"
        sinais[a] = {"status": status, "queda": round(queda, 4), "repique": round(repique, 4)}
    sat["sinais"] = sinais
    return criada, vendas, compras


def valor_satelite(sat, px):
    """Carteira satélite + posições de oportunidade + reserva da satélite."""
    pos = sum(p["qtd"] * px[p["ativo"]] for p in sat.get("posicoes", []))
    return valor(sat["carteira"], px, SAT_ALVO) + pos + sat.get("reserva", {}).get("saldo", 0.0)


def registrar(arquivo, ops, px, agora):
    if not arquivo.exists():
        arquivo.write_text("data_hora;tipo;ativo;quantidade;valor_reais;preco;taxa;peso_antes\n")
    with open(arquivo, "a", newline="") as f:
        w = csv.writer(f, delimiter=";")
        for op in ops:
            w.writerow([agora.strftime("%Y-%m-%d %H:%M"), op["tipo"], op["ativo"].upper(), f"{op['qtd']:.8f}",
                        f"{op['reais']:.2f}", f"{px[op['ativo']]:.8f}", f"{op['taxa']:.4f}", f"{op['peso_antes']:.4f}"])


# ---------- extrato ----------
def mov_operacao(op, px, conta, agora, montagem=False):
    """Converte uma compra/venda em linha de extrato (valor com sinal = efeito no saldo em reais)."""
    a = op["ativo"].upper()
    valor = -op["reais"] if op["tipo"] == "COMPRA" else op["reais"] - op["taxa"]
    desc = f"{'Compra' if op['tipo'] == 'COMPRA' else 'Venda'} de {qtd_txt(op['qtd'])} {a} a {preco(px[op['ativo']])}"
    if montagem:
        desc += " (montagem)"
    return {"data_hora": agora.strftime("%Y-%m-%d %H:%M"), "conta": conta, "tipo": op["tipo"], "descricao": desc,
            "valor": valor, "taxa": op["taxa"]}


def lancar(movs):
    """Acrescenta movimentações ao extrato, recalculando o saldo em reais a partir da última linha."""
    if not movs:
        return
    if not EXTRATO.exists():
        EXTRATO.write_text("data_hora;conta;tipo;descricao;valor;taxa;saldo_reais\n")
    linhas = EXTRATO.read_text().strip().split("\n")
    saldo = float(linhas[-1].split(";")[-1]) if len(linhas) > 1 else 0.0
    with open(EXTRATO, "a", newline="") as f:
        w = csv.writer(f, delimiter=";")
        for m in movs:
            saldo += m["valor"]
            w.writerow([m["data_hora"], m["conta"], m["tipo"], m["descricao"], f"{m['valor']:.2f}", f"{m['taxa']:.4f}", f"{saldo:.2f}"])


# ---------- execução ----------
def main():
    agora = datetime.now(BRASILIA)
    hoje = agora.date().isoformat()
    px = precos()
    novo = not ESTADO.exists()
    est = estado_inicial(px, agora) if novo else json.loads(ESTADO.read_text())
    c = est["carteira"]
    migrou = preparar_reserva(est, novo)
    aportes = [] if novo else usar_reserva(est, c, valor(c, px), agora)   # reserva principal: checada a cada execução

    if est.get("ops_dia", {}).get("data") != hoje:
        est["ops_dia"] = {"data": hoje, "n": 0}
    limite = MAX_OPS_DIA - est["ops_dia"]["n"]
    ult_cart = est.get("ultima_checagem_carteiras")
    checar_carteiras = novo or not ult_cart or (agora - datetime.fromisoformat(ult_cart)).total_seconds() >= INTERVALO_CARTEIRAS * 3600
    if checar_carteiras:
        est["ultima_checagem_carteiras"] = agora.isoformat()
    feitas = [] if novo or limite <= 0 or not checar_carteiras else rebalancear(c, px, limite, est["ops_dia"]["n"])
    est["gatilho"], est["gatilho_extra"], est["max_ops_dia"] = DESVIO_MIN, DESVIO_EXTRA, MAX_OPS_DIA
    # carteira satélite: aporte (uma vez) e rebalanceamento com as mesmas regras, contador próprio
    sat_montagem = [] if novo else preparar_satelite(est, px, agora)
    sat_feitas = []
    if "satelite" in est and not sat_montagem:
        sat = est["satelite"]
        if sat["ops_dia"].get("data") != hoje:
            sat["ops_dia"] = {"data": hoje, "n": 0}
        lim = MAX_OPS_DIA - sat["ops_dia"]["n"]
        sat_feitas = [] if lim <= 0 or not checar_carteiras else rebalancear(sat["carteira"], px, lim, sat["ops_dia"]["n"], SAT_ALVO)
        sat["ops_dia"]["n"] += len(sat_feitas)
        sat["rebalanceamentos"] += len(sat_feitas)
        sat["taxas"] += sum(f["taxa"] for f in sat_feitas)
        est["ops_periodo"] = est.get("ops_periodo", 0) + len(sat_feitas)
    sat_res_criada, sat_vendas_op, sat_compras_op = False, [], []
    if "satelite" in est and not sat_montagem:
        sat_res_criada, sat_vendas_op, sat_compras_op = oportunidades_satelite(est, px, agora)
        est["ops_periodo"] += len(sat_vendas_op) + len(sat_compras_op)
    est["ops_dia"]["n"] += len(feitas)
    est["rebalanceamentos"] = est.get("rebalanceamentos", 0) + len(feitas)
    est["operacoes"] += len(feitas)
    est["ops_periodo"] = est.get("ops_periodo", 0) + len(feitas)   # operações desde o último resumo
    est["taxas"] += sum(f["taxa"] for f in feitas)
    resumo_agora = novo or (agora.hour >= HORA_RESUMO and est.get("ultimo_resumo") != hoje)
    if resumo_agora:
        est["ultimo_resumo"] = hoje
    v, v_parada = valor(c, px), valor(est["parada"], px)
    est["pico"] = max(est["pico"], v)
    est["pico_cota"] = max(est["pico_cota"], v / est["investido"])
    reserva = est["reserva"]["saldo"]
    v_sat = v_sat_par = 0.0
    if "satelite" in est:
        sat = est["satelite"]
        v_sat = valor_satelite(sat, px)
        v_sat_par = valor(sat["parada"], px, SAT_ALVO) + sat.get("parada_reserva", 0.0)
        sat["pico"] = max(sat.get("pico", SAT_APORTE), v_sat)
    v_tot, v_par_tot = v + reserva + v_sat, v_parada + est["parada_reserva"] + v_sat_par
    est["ultima_execucao"] = agora.isoformat()
    est["ultimos_precos"] = px

    # registros
    if not OPERACOES.exists():
        OPERACOES.write_text("data_hora;tipo;ativo;quantidade;valor_reais;preco;taxa;peso_antes\n")
    with open(OPERACOES, "a", newline="") as f:
        w = csv.writer(f, delimiter=";")
        for op in feitas:
            w.writerow([agora.strftime("%Y-%m-%d %H:%M"), op["tipo"], op["ativo"].upper(), f"{op['qtd']:.8f}",
                        f"{op['reais']:.2f}", f"{px[op['ativo']]:.6f}", f"{op['taxa']:.4f}", f"{op['peso_antes']:.4f}"])
    registrar(OPERACOES_SAT, sat_montagem + sat_feitas + sat_vendas_op + sat_compras_op, px, agora)
    quando = agora.strftime("%Y-%m-%d %H:%M")
    movs = []
    if novo:
        movs.append({"data_hora": quando, "conta": "Principal", "tipo": "DEPÓSITO", "descricao": "Depósito inicial da carteira principal", "valor": CAPITAL, "taxa": 0})
        for a, w in ALVO.items():
            movs.append(mov_operacao({"tipo": "COMPRA", "ativo": a, "qtd": c[a], "reais": CAPITAL * w, "taxa": CAPITAL * w * CUSTO}, px, "Principal", agora, True))
    if migrou:
        movs.append({"data_hora": quando, "conta": "Reserva", "tipo": "DEPÓSITO", "descricao": "Reserva de oportunidade", "valor": RESERVA_INICIAL, "taxa": 0})
    for ap in aportes:
        movs.append({"data_hora": quando, "conta": "Reserva", "tipo": "TRANSFERÊNCIA",
                     "descricao": f"Reserva → carteira principal: {brl(ap['valor'])} (degrau de {ap['degrau']*100:.0f}%)", "valor": 0.0, "taxa": 0})
    movs += [mov_operacao(op, px, "Principal", agora) for op in feitas]
    if sat_montagem:
        movs.append({"data_hora": quando, "conta": "Satélite", "tipo": "DEPÓSITO", "descricao": "Aporte da carteira satélite", "valor": SAT_APORTE, "taxa": 0})
        movs += [mov_operacao(op, px, "Satélite", agora, True) for op in sat_montagem]
    movs += [mov_operacao(op, px, "Satélite", agora) for op in sat_feitas]
    if sat_res_criada:
        movs.append({"data_hora": quando, "conta": "Satélite", "tipo": "DEPÓSITO", "descricao": "Reserva da satélite (para oportunidades)", "valor": SAT_RESERVA, "taxa": 0})
    for op in sat_vendas_op:
        m = mov_operacao(dict(op, tipo="VENDA"), px, "Satélite", agora); m["descricao"] += f" (lucro de oportunidade, {brl(op['ganho'])})"; movs.append(m)
    for op in sat_compras_op:
        m = mov_operacao(dict(op, tipo="COMPRA"), px, "Satélite", agora); m["descricao"] += " (oportunidade, com a reserva da satélite)"; movs.append(m)
    lancar(movs)
    if not HISTORICO.exists():
        HISTORICO.write_text("data;patrimonio;carteira_parada;operacoes_no_dia\n")
    ops_24h = est["ops_periodo"]
    if resumo_agora:  # uma linha por dia, na checagem da manhã
        with open(HISTORICO, "a") as f:
            f.write(f"{agora:%Y-%m-%d};{v_tot:.2f};{v_par_tot:.2f};{ops_24h}\n")
        est["ops_periodo"] = 0
    ESTADO.write_text(json.dumps(est, indent=2, ensure_ascii=False))

    # mensagens
    if novo:
        compras = "\n".join(f"• {a.upper()} {ALVO[a]*100:.0f}% a {preco(px[a])}" for a in ALVO)
        telegram(f"{ROTULO} · Carteira nova iniciada\n"
                 f"Dinheiro de mentira: {brl(CAPITAL)} na carteira + {brl(RESERVA_INICIAL)} de reserva\n{compras}\n• Reais {(1 - sum(ALVO.values()))*100:.0f}%\n"
                 f"Checo o mercado a cada 4 horas. Faço até 3 operações por dia: a 1ª quando um ativo desvia 1 ponto do alvo; a 2ª e a 3ª só se a oportunidade for muito boa (2,5 pontos ou mais). Resumo todo dia às 7h.")
        return
    degraus_txt = ", ".join(f"{d*100:.0f}%" for d in DEGRAUS)
    if migrou:
        telegram(f"{ROTULO} · 💰 Reserva de oportunidade criada\n"
                 f"{brl(RESERVA_INICIAL)} disponíveis na corretora, fora da carteira.\n"
                 f"Entram em degraus de {brl(APORTE)} quando a carteira cair {degraus_txt} desde o pico.\n"
                 f"Patrimônio total agora: {brl(v_tot)}")
    for ap in aportes:
        telegram(f"{ROTULO} · 💰 Reserva acionada\n"
                 f"A carteira caiu {num(ap['queda']*100, 1)}% desde o pico (degrau de {ap['degrau']*100:.0f}%).\n"
                 f"{brl(ap['valor'])} entraram na carteira. O rebalanceamento distribui entre as moedas que mais caíram.\n"
                 f"Reserva restante: {brl(est['reserva']['saldo'])} · degraus usados: {len(est['reserva']['usados'])} de {len(DEGRAUS)}")
    SAT = "🛰️ Satélite"
    if sat_montagem:
        telegram(f"{ROTULO} · {SAT} · 💵 Aporte de {brl(SAT_APORTE)}\n"
                 f"Nova carteira satélite (risco maior), separada da carteira principal, que continua igual.\n"
                 f"Divisão: " + " · ".join(f"{a.upper()} {w*100:.0f}%" for a, w in SAT_ALVO.items()) + f" · Reais {(1 - sum(SAT_ALVO.values()))*100:.0f}%\n"
                 f"Mesmas regras de operação, sem reserva. Seguem as {len(sat_montagem)} compras.\n"
                 f"Patrimônio total agora: {brl(v_tot)}")
        for o in sat_montagem:
            a = o["ativo"]
            telegram(f"{ROTULO} · {SAT} · 🟢 COMPRA\n"
                     f"{qtd_txt(o['qtd'])} {a.upper()} por {brl(o['reais'])} ({preco(px[a])}/{a.upper()})\n"
                     f"Motivo: montagem da satélite (alvo {SAT_ALVO[a]*100:.0f}%)\n"
                     f"Taxa: {brl(o['taxa'])}")
    if sat_res_criada:
        telegram(f"{ROTULO} · {SAT} · 💰 Reserva da satélite criada\n"
                 f"{brl(SAT_RESERVA)} parados, destinados à satélite. Uso só em oportunidade: moeda {OPORT_QUEDA*100:.0f}% ou mais abaixo do topo de {OPORT_TOPO_DIAS} dias "
                 f"e já {OPORT_REPIQUE*100:.0f}% acima do fundo de {OPORT_FUNDO_DIAS} dias. Compra de {brl(OPORT_VALOR)}, venda com +{num(OPORT_LUCRO*100, 1)}%.\n"
                 f"Patrimônio total agora: {brl(v_tot)}")
    for op in sat_compras_op:
        a = op["ativo"]
        telegram(f"{ROTULO} · {SAT} · 🎯 OPORTUNIDADE · 🟢 COMPRA\n"
                 f"{qtd_txt(op['qtd'])} {a.upper()} por {brl(op['reais'])} ({preco(px[a])}/{a.upper()})\n"
                 f"Motivo: {a.upper()} está {num(op['queda']*100, 1)}% abaixo do topo de {OPORT_TOPO_DIAS} dias e subiu {num(op['repique']*100, 1)}% desde o fundo de {OPORT_FUNDO_DIAS} dias.\n"
                 f"Venda programada em {preco(px[a] * (1 + OPORT_LUCRO))} (+{num(OPORT_LUCRO*100, 1)}%). Reserva da satélite: {brl(est['satelite']['reserva']['saldo'])}")
    for op in sat_vendas_op:
        a = op["ativo"]
        telegram(f"{ROTULO} · {SAT} · 💰 LUCRO · 🔴 VENDA\n"
                 f"{qtd_txt(op['qtd'])} {a.upper()} por {brl(op['reais'])} ({preco(px[a])}/{a.upper()})\n"
                 f"Posição de oportunidade atingiu +{num(OPORT_LUCRO*100, 1)}%. Ganho líquido: {brl(op['ganho'])}.\n"
                 f"O dinheiro voltou para a reserva da satélite: {brl(est['satelite']['reserva']['saldo'])}")
    for i, op in enumerate(sat_feitas, start=1):
        a = op["ativo"]; n = est["satelite"]["ops_dia"]["n"] - len(sat_feitas) + i
        emoji = "🟢" if op["tipo"] == "COMPRA" else "🔴"
        telegram(f"{ROTULO} · {SAT} · {emoji} {op['tipo']}\n"
                 f"{qtd_txt(op['qtd'])} {a.upper()} por {brl(op['reais'])} ({preco(px[a])}/{a.upper()})\n"
                 f"Motivo: {a.upper()} estava em {num(op['peso_antes']*100, 1)}% da satélite (alvo {SAT_ALVO[a]*100:.0f}%)\n"
                 f"Taxa: {brl(op['taxa'])} · operação {n} de até {MAX_OPS_DIA} hoje na satélite")
    n_antes = est["ops_dia"]["n"] - len(feitas)
    for i, op in enumerate(feitas, start=1):
        a = op["ativo"]
        n = n_antes + i
        if n >= MAX_OPS_DIA:
            rodape = f"Operação {n} de {MAX_OPS_DIA} hoje. Limite do dia atingido."
        else:
            rodape = f"Operação {n} de até {MAX_OPS_DIA} hoje. Outra hoje só se a oportunidade for muito boa (desvio de 2,5 pontos ou mais)."
        emoji = "🟢" if op["tipo"] == "COMPRA" else "🔴"
        telegram(f"{ROTULO} · {emoji} {op['tipo']}\n"
                 f"{qtd_txt(op['qtd'])} {a.upper()} por {brl(op['reais'])} ({preco(px[a])}/{a.upper()})\n"
                 f"Motivo: {a.upper()} estava em {num(op['peso_antes']*100, 1)}% da carteira (alvo {ALVO[a]*100:.0f}%)\n"
                 f"Taxa: {brl(op['taxa'])}\n"
                 f"{rodape}")
    if not resumo_agora:
        return
    dias = (agora.date() - datetime.fromisoformat(est["inicio"]).date()).days
    resumo = (f"{ROTULO} · ☀️ Resumo da manhã · {agora:%d/%m}\n"
              f"Patrimônio total: {brl(v_tot)} ({pct(v_tot / est['capital_total'] - 1)} desde o início, {dias} {'dia' if dias == 1 else 'dias'})\n"
              f"Carteira: {brl(v)} · Reserva: {brl(reserva)} ({len(est['reserva']['usados'])} de {len(DEGRAUS)} degraus usados)\n"
              + (f"Satélite: {brl(v_sat)} ({pct(v_sat / (SAT_APORTE + est['satelite'].get('parada_reserva', 0)) - 1)}) · reserva dela: {brl(est['satelite'].get('reserva', {}).get('saldo', 0))} · oportunidades abertas: {len(est['satelite'].get('posicoes', []))}\n" if "satelite" in est else "") +
              f"Sem robô (tudo parado): {brl(v_par_tot)} → robô {'+' if v_tot >= v_par_tot else '−'}{brl(abs(v_tot - v_par_tot))} de diferença\n"
              f"Operações nas últimas 24 h: {ops_24h} · rebalanceamentos: {est['rebalanceamentos']} · taxas: {brl(est['taxas'])}\n"
              f"Divisão: {texto_pesos(pesos(c, px))}")
    queda = 1 - (v / est["investido"]) / est["pico_cota"]
    if queda >= 0.10:
        prox = next((d for d in DEGRAUS if d not in est["reserva"]["usados"]), None)
        resumo += f"\nℹ️ Carteira {num(queda*100, 0)}% abaixo do pico." + (
            f" Próximo degrau da reserva em {prox*100:.0f}%." if prox and est["reserva"]["saldo"] > 0 else " Sigo operando normalmente.")
    telegram(resumo)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        telegram(f"{ROTULO} · ⚠️ O robô não conseguiu rodar agora.\nMotivo: {e}\n"
                 f"Nada foi alterado na carteira simulada. Tento de novo na próxima checagem (em até 4 horas).")
        sys.exit(1)
