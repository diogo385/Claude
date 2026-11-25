"""Argo Trade Cripto · robô de rebalanceamento em MODO SIMULADO (carteira diversificada).

- Usa preços reais e públicos da Binance (sem conta, sem chave).
- Opera um dinheiro de mentira: R$ 1.000 iniciais.
- Carteira-alvo: BTC 35% · ETH 15% · SOL 8% · XRP 5% · BNB 4% · LINK 3% · reais 30%.
- Checa o mercado a cada 4 horas e opera o ativo mais fora do alvo. Até 3 operações por dia:
  a 1ª quando o desvio chega a 1,5 ponto; a 2ª e a 3ª só se a oportunidade for muito boa
  (desvio de 2,5 pontos ou mais). O resumo diário sai na checagem das 7h (Brasília).
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

VERSAO = 2
CAPITAL = 1000.0
ALVO = {"btc": 0.35, "eth": 0.15, "sol": 0.08, "xrp": 0.05, "bnb": 0.04, "link": 0.03}  # o resto (30%) fica em reais
PARES = {a: a.upper() + "BRL" for a in ALVO}
DESVIO_MIN = 0.015       # 1ª operação do dia: ativo 1,5 ponto ou mais fora do alvo
DESVIO_EXTRA = 0.025     # 2ª e 3ª operações do dia: só com 2,5 pontos ou mais (oportunidade muito boa)
MAX_OPS_DIA = 3          # no máximo 3 operações por dia
HORA_RESUMO = 7          # a partir desta hora (Brasília) manda o resumo do dia
TAXA = 0.001             # 0,1% (Binance)
DESLIZE = 0.0005         # 0,05% de diferença de preço
CUSTO = TAXA + DESLIZE
ORDEM_MIN = 20.0         # ignora ajustes menores que R$ 20
FONTES = ["https://data-api.binance.vision", "https://api.binance.com"]
BRASILIA = timezone(timedelta(hours=-3))
ROTULO = "🧪 Argo Trade Cripto · SIMULADO"


# ---------- utilidades ----------
def brl(v):
    s = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
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
    simbolos = urllib.parse.quote(json.dumps(list(PARES.values()), separators=(",", ":")))
    erros = []
    for base in FONTES:
        try:
            with urllib.request.urlopen(f"{base}/api/v3/ticker/price?symbols={simbolos}", timeout=30) as r:
                lido = {x["symbol"]: float(x["price"]) for x in json.loads(r.read())}
            px = {a: lido[p] for a, p in PARES.items()}
            if all(v > 0 for v in px.values()):
                return px
        except Exception as e:
            erros.append(f"{base}: {type(e).__name__}")
    raise RuntimeError("Não consegui ler os preços da Binance (" + "; ".join(erros) + ")")


# ---------- carteira ----------
def valor(c, px):
    return c["reais"] + sum(c.get(a, 0.0) * px[a] for a in ALVO)


def pesos(c, px):
    v = valor(c, px)
    return {a: c.get(a, 0.0) * px[a] / v for a in ALVO} | {"reais": c["reais"] / v}


def montar(px):
    c = {"reais": CAPITAL}
    for a, p in ALVO.items():
        gasto = CAPITAL * p
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


def rebalancear(c, px, limite, ja_feitas):
    """Opera o(s) ativo(s) mais fora do alvo, até `limite` operações. Nunca usa saldo que não existe.
    A 1ª operação do dia exige DESVIO_MIN; as seguintes exigem DESVIO_EXTRA."""
    feitas = []
    v = valor(c, px)
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
        v = valor(c, px)
    return feitas


def texto_pesos(p):
    return " · ".join(f"{a.upper()} {p[a]*100:.0f}%" for a in ALVO) + f" · R$ {p['reais']*100:.0f}%"


def qtd_txt(q):
    return num(q, 6 if q < 1 else 4 if q < 100 else 2)


# ---------- execução ----------
def main():
    agora = datetime.now(BRASILIA)
    hoje = agora.date().isoformat()
    px = precos()
    novo = not ESTADO.exists()
    est = estado_inicial(px, agora) if novo else json.loads(ESTADO.read_text())
    c = est["carteira"]

    if est.get("ops_dia", {}).get("data") != hoje:
        est["ops_dia"] = {"data": hoje, "n": 0}
    limite = MAX_OPS_DIA - est["ops_dia"]["n"]
    feitas = [] if novo or limite <= 0 else rebalancear(c, px, limite, est["ops_dia"]["n"])
    est["gatilho"], est["gatilho_extra"], est["max_ops_dia"] = DESVIO_MIN, DESVIO_EXTRA, MAX_OPS_DIA
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
    if not HISTORICO.exists():
        HISTORICO.write_text("data;patrimonio;carteira_parada;operacoes_no_dia\n")
    ops_24h = est["ops_periodo"]
    if resumo_agora:  # uma linha por dia, na checagem da manhã
        with open(HISTORICO, "a") as f:
            f.write(f"{agora:%Y-%m-%d};{v:.2f};{v_parada:.2f};{ops_24h}\n")
        est["ops_periodo"] = 0
    ESTADO.write_text(json.dumps(est, indent=2, ensure_ascii=False))

    # mensagens
    if novo:
        compras = "\n".join(f"• {a.upper()} {ALVO[a]*100:.0f}% a {brl(px[a])}" for a in ALVO)
        telegram(f"{ROTULO} · Carteira nova iniciada\n"
                 f"Dinheiro de mentira: {brl(CAPITAL)}\n{compras}\n• Reais {(1 - sum(ALVO.values()))*100:.0f}%\n"
                 f"Checo o mercado a cada 4 horas. Faço até 3 operações por dia: a 1ª quando um ativo desvia 1,5 ponto do alvo; a 2ª e a 3ª só se a oportunidade for muito boa (2,5 pontos ou mais). Resumo todo dia às 7h.")
        return
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
                 f"{qtd_txt(op['qtd'])} {a.upper()} por {brl(op['reais'])} ({brl(px[a])}/{a.upper()})\n"
                 f"Motivo: {a.upper()} estava em {num(op['peso_antes']*100, 1)}% da carteira (alvo {ALVO[a]*100:.0f}%)\n"
                 f"Taxa: {brl(op['taxa'])}\n"
                 f"{rodape}")
    if not resumo_agora:
        return
    dias = (agora.date() - datetime.fromisoformat(est["inicio"]).date()).days
    resumo = (f"{ROTULO} · ☀️ Resumo da manhã · {agora:%d/%m}\n"
              f"Patrimônio: {brl(v)} ({pct(v / CAPITAL - 1)} desde o início, {dias} {'dia' if dias == 1 else 'dias'})\n"
              f"Carteira parada: {brl(v_parada)} → robô {'+' if v >= v_parada else '−'}{brl(abs(v - v_parada))} de diferença\n"
              f"Operações nas últimas 24 h: {ops_24h} · rebalanceamentos: {est['rebalanceamentos']} · taxas: {brl(est['taxas'])}\n"
              f"Carteira: {texto_pesos(pesos(c, px))}")
    if v < est["pico"] * 0.75:
        resumo += f"\nℹ️ Patrimônio {pct(v / est['pico'] - 1, 0)} abaixo do pico. Sigo operando normalmente."
    telegram(resumo)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        telegram(f"{ROTULO} · ⚠️ O robô não conseguiu rodar agora.\nMotivo: {e}\n"
                 f"Nada foi alterado na carteira simulada. Tento de novo na próxima checagem (em até 4 horas).")
        sys.exit(1)
