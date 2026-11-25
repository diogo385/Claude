"""Argo Trade Cripto · robô de rebalanceamento em MODO SIMULADO.

- Usa preços reais e públicos da Binance (sem conta, sem chave).
- Opera um dinheiro de mentira: R$ 1.000 iniciais.
- Carteira-alvo: 50% BTC, 15% ETH, 35% reais.
- Checa o mercado a cada 4 horas. Faz NO MÁXIMO 1 operação por dia, no ativo mais fora do alvo,
  quando ele desvia 1,5 ponto ou mais. O resumo diário sai na checagem das 21h.
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

CAPITAL = 1000.0
ALVO = {"btc": 0.50, "eth": 0.15}          # o resto (35%) fica em reais
DESVIO_MIN = 0.015                         # oportunidade: ativo 1,5 ponto ou mais fora do alvo
MAX_OPS_DIA = 1                            # no máximo 1 operação por dia
HORA_RESUMO = 20                           # a partir desta hora (Brasília) manda o resumo do dia
TAXA = 0.001                               # 0,1% (Binance)
DESLIZE = 0.0005                           # 0,05% de diferença de preço
ORDEM_MIN = 20.0                           # ignora ajustes menores que R$ 20
PARES = {"btc": "BTCBRL", "eth": "ETHBRL"}
FONTES = ["https://data-api.binance.vision", "https://api.binance.com"]
BRASILIA = timezone(timedelta(hours=-3))
NOMES = {"btc": "BTC", "eth": "ETH"}


# ---------- utilidades ----------
def brl(v):
    s = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"


def pct(v, casas=1):
    s = f"{v * 100:+.{casas}f}".replace(".", ",")
    return f"{s}%"


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
    erros = []
    for base in FONTES:
        try:
            px = {}
            for ativo, par in PARES.items():
                with urllib.request.urlopen(f"{base}/api/v3/ticker/price?symbol={par}", timeout=30) as r:
                    px[ativo] = float(json.loads(r.read())["price"])
            if all(v > 0 for v in px.values()):
                return px
        except Exception as e:
            erros.append(f"{base}: {type(e).__name__}")
    raise RuntimeError("Não consegui ler os preços da Binance (" + "; ".join(erros) + ")")


# ---------- carteira ----------
def valor(c, px):
    return c["reais"] + sum(c[a] * px[a] for a in ALVO)


def estado_inicial(px, agora):
    def comprar_alvo():
        c = {"reais": CAPITAL, "btc": 0.0, "eth": 0.0}
        for a, p in ALVO.items():
            gasto = CAPITAL * p
            c[a] = gasto * (1 - TAXA - DESLIZE) / px[a]
            c["reais"] -= gasto
        return c
    return {
        "inicio": agora.isoformat(),
        "carteira": comprar_alvo(),
        "parada": comprar_alvo(),           # mesma carteira, nunca rebalanceada (comparação)
        "pico": CAPITAL,
        "operacoes": 0,
        "taxas": CAPITAL * (1 - ALVO_RESTO()) * (TAXA + DESLIZE),
        "ultima_execucao": None,
    }


def ALVO_RESTO():
    return 1 - sum(ALVO.values())


def rebalancear(c, px, limite):
    """Opera no(s) ativo(s) mais fora do alvo, até `limite` operações. Nunca usa saldo que não existe."""
    feitas = []
    v = valor(c, px)
    fila = sorted(ALVO, key=lambda a: -abs(c[a] * px[a] / v - ALVO[a]))
    for a in fila:
        if len(feitas) >= limite:
            break
        peso = c[a] * px[a] / v
        ajuste = ALVO[a] * v - c[a] * px[a]
        if abs(peso - ALVO[a]) < DESVIO_MIN or abs(ajuste) < ORDEM_MIN:
            continue
        custo = TAXA + DESLIZE
        if ajuste > 0:  # compra
            gasto = min(ajuste, c["reais"])
            qtd = gasto * (1 - custo) / px[a]
            c["reais"] -= gasto
            c[a] += qtd
            feitas.append({"tipo": "COMPRA", "ativo": a, "qtd": qtd, "reais": gasto, "taxa": gasto * custo, "peso_antes": peso})
        else:           # venda
            venda = min(-ajuste, c[a] * px[a])
            qtd = venda / px[a]
            c[a] -= qtd
            c["reais"] += venda * (1 - custo)
            feitas.append({"tipo": "VENDA", "ativo": a, "qtd": qtd, "reais": venda, "taxa": venda * custo, "peso_antes": peso})
        if c["reais"] < -1e-9 or c[a] < -1e-12:
            raise RuntimeError("Trava: saldo negativo detectado. Nenhuma dívida é permitida.")
    return feitas


def pesos(c, px):
    v = valor(c, px)
    return {a: c[a] * px[a] / v for a in ALVO} | {"reais": c["reais"] / v}


def texto_pesos(p):
    return f"BTC {p['btc']*100:.0f}% · ETH {p['eth']*100:.0f}% · R$ {p['reais']*100:.0f}%"


# ---------- execução diária ----------
def main():
    agora = datetime.now(BRASILIA)
    px = precos()
    novo = not ESTADO.exists()
    est = estado_inicial(px, agora) if novo else json.loads(ESTADO.read_text())
    c = est["carteira"]

    hoje = agora.date().isoformat()
    if est.get("ops_dia", {}).get("data") != hoje:
        est["ops_dia"] = {"data": hoje, "n": 0}
    limite = MAX_OPS_DIA - est["ops_dia"]["n"]
    feitas = [] if novo or limite <= 0 else rebalancear(c, px, limite)
    est["ops_dia"]["n"] += len(feitas)
    est["rebalanceamentos"] = est.get("rebalanceamentos", 0) + len(feitas)
    resumo_agora = novo or (agora.hour >= HORA_RESUMO and est.get("ultimo_resumo") != hoje)
    if resumo_agora:
        est["ultimo_resumo"] = hoje
    v, v_parada = valor(c, px), valor(est["parada"], px)
    est["pico"] = max(est["pico"], v)
    est["operacoes"] += len(feitas) + (2 if novo else 0)
    est["taxas"] = est.get("taxas", 0) + sum(f["taxa"] for f in feitas)
    est["ultima_execucao"] = agora.isoformat()

    # registros
    if not OPERACOES.exists():
        OPERACOES.write_text("data_hora;tipo;ativo;quantidade;valor_reais;preco;taxa;peso_antes\n")
    with open(OPERACOES, "a", newline="") as f:
        w = csv.writer(f, delimiter=";")
        for op in feitas:
            w.writerow([agora.strftime("%Y-%m-%d %H:%M"), op["tipo"], NOMES[op["ativo"]], f"{op['qtd']:.8f}",
                        f"{op['reais']:.2f}", f"{px[op['ativo']]:.2f}", f"{op['taxa']:.4f}", f"{op['peso_antes']:.4f}"])
    if not HISTORICO.exists():
        HISTORICO.write_text("data;patrimonio;carteira_parada;preco_btc;preco_eth;operacoes_no_dia\n")
    if resumo_agora:  # uma linha por dia, na checagem da noite
        with open(HISTORICO, "a") as f:
            f.write(f"{agora:%Y-%m-%d};{v:.2f};{v_parada:.2f};{px['btc']:.2f};{px['eth']:.2f};{est['ops_dia']['n']}\n")
    ESTADO.write_text(json.dumps(est, indent=2, ensure_ascii=False))

    # mensagens
    rot = "🧪 Argo Trade Cripto · SIMULADO"
    if novo:
        telegram(f"{rot} · Robô iniciado\n"
                 f"Carteira de mentira: {brl(CAPITAL)}\n"
                 f"Comprado: 50% BTC ({brl(px['btc'])}/BTC) e 15% ETH ({brl(px['eth'])}/ETH), 35% em reais.\n"
                 f"Checo o mercado a cada 4 horas e faço no máximo 1 operação por dia, quando um ativo desviar 1,5 ponto ou mais do alvo. Resumo todo dia às 21h.")
        return
    for op in feitas:
        emoji = "🟢" if op["tipo"] == "COMPRA" else "🔴"
        telegram(f"{rot} · {emoji} {op['tipo']}\n"
                 f"{op['qtd']:.6f}".replace(".", ",") + f" {NOMES[op['ativo']]} por {brl(op['reais'])} ({brl(px[op['ativo']])}/{NOMES[op['ativo']]})\n"
                 f"Motivo: {NOMES[op['ativo']]} estava em {str(round(op['peso_antes']*100, 1)).replace('.', ',')}% da carteira (alvo {ALVO[op['ativo']]*100:.0f}%)\n"
                 f"Taxa: {brl(op['taxa'])}\n"
                 f"Operação do dia feita. Próxima, só a partir de amanhã.")
    if not resumo_agora:
        return
    inicio = datetime.fromisoformat(est["inicio"])
    dias = (agora.date() - inicio.date()).days
    resumo = (f"{rot} · 📊 Resumo {agora:%d/%m}\n"
              f"Patrimônio: {brl(v)} ({pct(v / CAPITAL - 1)} desde o início, {dias} dias)\n"
              f"Carteira parada: {brl(v_parada)} → robô {'+' if v >= v_parada else '−'}{brl(abs(v - v_parada))} de diferença\n"
              f"Operações hoje: {est['ops_dia']['n']} de {MAX_OPS_DIA} · rebalanceamentos: {est['rebalanceamentos']} · taxas: {brl(est['taxas'])}\n"
              f"Carteira: {texto_pesos(pesos(c, px))}\n"
              f"BTC {brl(px['btc'])} · ETH {brl(px['eth'])}")
    if v < est["pico"] * 0.75:
        resumo += f"\nℹ️ Patrimônio {pct(v / est['pico'] - 1, 0)} abaixo do pico. Sigo operando normalmente."
    telegram(resumo)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        telegram(f"🧪 Argo Trade Cripto · SIMULADO · ⚠️ O robô não conseguiu rodar agora.\nMotivo: {e}\nNada foi alterado na carteira simulada. Tento de novo na próxima checagem (em até 4 horas).")
        sys.exit(1)
