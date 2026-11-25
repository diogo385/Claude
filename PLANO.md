# Argos Trade Cripto · Plano

Versão 2.2 · 25/11/2026 · sistema em **modo simulado**, rodando sozinho

> Na mitologia grega, Argos é o gigante de cem olhos que nunca dormia: um vigia que não descansa.

---

## 1. O que é e o que esperar

**O que é:** um robô **100% autônomo** que administra carteiras de cripto **só com saldo próprio**. Ele rebalanceia as carteiras, aproveita quedas com reservas e avisa **toda operação** no Telegram.

**Expectativa sincera, com base nos testes:**
- Quase todo o resultado vem do preço das moedas. O robô não cria lucro do nada.
- **Rebalancear funciona:** de 2021 a 2026, qualquer forma de rebalanceamento rendeu bem mais que a carteira parada (+128% a +195%, contra +89%). Quanto mais moedas na carteira, maior o ganho do rebalanceamento.
- **O jeito exato importa pouco:** rebalancear todo dia, a cada 3 meses ou uma vez por ano deu resultados parecidos, e a diferença veio mais da sorte de calendário.
- **As quedas doem em qualquer estratégia:** cerca de −60% em 2021–2022.
- É um projeto de **aprendizado, com risco limitado e custo zero**, não uma fonte de renda.

---

## 2. Regras que nunca mudam

1. **Só saldo próprio.** Sem margem, futuros, empréstimo ou dívida de qualquer tipo.
2. **O robô nunca saca** dinheiro da corretora.
3. **Só mercado à vista (spot)**, só ordens limitadas no dinheiro real e ordem mínima de R$ 10.
4. **Toda operação é avisada no Telegram na hora**, seja autônoma ou pedida: compras, vendas, aportes, montagens e uso das reservas.
5. **O próprio sistema nunca afrouxa as travas.** Mudança de regra só com decisão do dono.
6. **Na dúvida, não opera.** Erro de dados ou de conexão: nada muda, e ele tenta de novo na próxima checagem.
7. **O capital é um valor que você aceita perder.**

---

## 3. Decisões tomadas

| Item | Decisão | Motivo |
|---|---|---|
| Nome | **Argos Trade Cripto** (família Argos Trade; Argos Trade B3 no futuro) | — |
| Corretora (dinheiro real) | **Binance Brasil** | Taxa ~0,1%, melhor API e exigência de IP fixo para negociar. Tem CNPJ brasileiro, e a isenção de R$ 35 mil/mês precisa ser confirmada com o contador |
| Corretora estrangeira | **Descartada** | É legal, mas não "desvincula do Brasil": 15% sobre o lucro sem isenção, declaração por conta própria e remessa tratada como câmbio desde 2026 |
| Mercado Bitcoin | Descartado | Hack de US$ 49 milhões em nov/2026, com saques congelados |
| Infraestrutura do simulado | **GitHub Actions + GitHub Pages + Telegram** | Custo zero e funciona com o PC desligado |
| Autonomia | **100%** | Nenhuma situação normal pede ação do dono |
| Resumo diário | **7h (Brasília)** | Pedido do dono |

---

## 4. Como o dinheiro está dividido (simulado)

| Parte | Valor inicial | Para que serve |
|---|---|---|
| **Carteira principal** | R$ 1.000 | O foco do sistema: BTC 35 · ETH 15 · SOL 8 · XRP 5 · BNB 4 · LINK 3 · Reais 30 |
| **Reserva para quedas** | R$ 500 | Entra na carteira principal quando ela cai forte (degraus) |
| **Carteira satélite** | R$ 250 | Teste de risco maior: LTC 20 · DOGE 20 · ADA 18 · AVAX 16 · NEAR 16 · Reais 10 |
| **Reserva do giro** | R$ 100 | Compras automáticas de giro curto nas moedas da satélite |
| **Total depositado** | **R$ 1.850** | |

As moedas foram escolhidas entre os pares em reais da Binance, pelo volume negociado. As memecoins puras (PEPE, SHIB) e as moedas novas demais (SUI, POL, RENDER) ficaram de fora.

---

## 5. Regras de operação

### 5.1 Rebalanceamento: carteira principal e satélite
- **Checagem a cada 15 minutos.**
- Opera sempre a **moeda mais fora do alvo** e a devolve exatamente ao alvo.
- **Gatilho:** desvio de **1 ponto** ou mais, em qualquer operação do dia.
- Antes, as operações extras do dia exigiam 2,5 pontos. No teste simulado, todas passaram a usar 1 ponto.
- **Na satélite**, como ela é pequena, a ordem mínima de R$ 10 faz o rebalanceamento só acontecer com desvios de ~4 a 5 pontos.
- **Máximo de 20 operações por dia em cada carteira** (teste simulado), com contadores separados.
- **Custo simulado:** 0,1% de taxa + 0,05% de diferença de preço por operação.

### 5.2 Reserva para quedas da principal (R$ 500)
- Entram **R$ 125** quando a carteira principal cai **20%, 30%, 40% e 50%** desde o pico.
- A queda é medida pela **cota da carteira**, sem contar os aportes.
- O dinheiro entra como reais, e o rebalanceamento compra as moedas que mais caíram.
- Se a carteira fizer um novo pico e ainda houver reserva, os degraus voltam a valer.

### 5.3 Reserva do giro da satélite (R$ 100)
- **Monitora as 5 moedas a cada 15 minutos.** Cada uma tem um status: normal, caindo, sinal de compra ou em giro. O robô compra e vende sozinho.
- **Compra:** quando a moeda está **10% ou mais abaixo do topo de 14 dias** e já **subiu 3% desde o fundo de 3 dias**, ou seja, parou de cair. O robô compra **R$ 25**, com **uma posição aberta por moeda**.
- **Venda:** quando a posição chega a **+1,5%**. Isso cobre ~0,3% de custos (ida e volta) e deixa **~1,2% de ganho líquido**. O dinheiro volta para a reserva.
- Essas posições ficam **separadas do rebalanceamento**, e pode haver **várias operações por dia**.
- **No máximo 2 posições abertas ao mesmo tempo.** No backtest, isso deixou a reserva em +R$ 18,87, contra +R$ 3,11 sem limite.
- A saída por tempo ("vender empatado depois de X dias") foi testada e **piorou** o resultado. Não foi adotada.
- **Sem stop.** Se a moeda continuar caindo, a posição fica presa. O dono aceitou esse risco.

### 5.4 Aportes
- Aportes novos são feitos a pedido do dono. Cada um é lançado no extrato, avisado no Telegram e incluído na comparação "sem robô", para ela continuar justa.

---

## 6. Horários

| Quando | O quê |
|---|---|
| **A cada 15 minutos** | Rebalanceamento das duas carteiras, giro da satélite e reserva principal |
| **7h (Brasília)** | Resumo do dia no Telegram e registro de um ponto no histórico |

O GitHub pode atrasar as execuções agendadas em alguns minutos. Para não sobrecarregar o site, o estado só é gravado quando algo acontece ou cerca de 1 vez por hora.

---

## 7. Avisos no Telegram (bot "Argos Trade Cripto")

Toda mensagem começa com `🧪 Argos Trade Cripto · SIMULADO`.

| Evento | Mensagem |
|---|---|
| Rebalanceamento | 🟢 COMPRA / 🔴 VENDA, com o motivo e "operação N de até 20 hoje" |
| Satélite | 🛰️ Satélite · COMPRA / VENDA |
| Giro da satélite | 🔄 GIRO · COMPRA AUTOMÁTICA (com a venda programada) e 🔄 GIRO · VENDA AUTOMÁTICA (lucro) |
| Reserva principal | 💰 Reserva acionada (degrau, valor e saldo restante) |
| Aportes e montagens | 💵 Aporte, seguido de uma mensagem para cada compra |
| Resumo das 7h | ☀️ Patrimônio total, carteira, reserva, satélite, comparação "sem robô", operações das últimas 24 h e divisão |
| Falha | ⚠️ O robô não conseguiu rodar (nada é alterado) |

---

## 8. Onde acompanhar

| Página | Endereço | O que mostra |
|---|---|---|
| **Monitor** | diogo385.github.io/Claude | Patrimônio total, evolução, **ganhos e perdas por cripto**, carteira principal, satélite, fluxo de decisão e agentes |
| **Histórico** | botão no monitor | Todas as operações agrupadas por dia, com filtros (principal, satélite, giros, reserva) |
| **Mercado ao vivo** | botão 📈 no monitor | Gráfico de velas das 6 moedas da principal, livro de ofertas, negociações e linhas de gatilho do robô |
| **Extrato** | botão no monitor | Toda entrada e saída de dinheiro com o saldo em reais, as duas reservas e os sinais da satélite |
| **Regras** | botão no monitor | Todas as regras num lugar só |

**Comandos no Telegram:** /status, /hoje, /pausar, /retomar e /ajuda. A resposta chega na próxima checagem (até ~15 min).

**Painéis de desempenho (monitor):**
- **Resultado por período:** 24 horas, 7 dias, 30 dias e desde o início, descontando os aportes.
- **"O robô está se pagando?":** ganho das operações antes das taxas, taxas pagas e resultado líquido contra o "sem robô", com um veredito.
- **Giro da satélite:** giros concluídos, lucro realizado e médio, tempo médio em posição, posições abertas (custo → vale agora) e reserva disponível.
- **Queda desde o pico:** gráfico abaixo da evolução do patrimônio, descontando aportes.

**Bloco "Ganhos e perdas por cripto" (monitor), ao vivo:** para cada moeda, o valor **aplicado**, quanto **vale agora**, o ganho ou perda em R$ e em %, o preço médio de compra (custo médio com taxas), a cotação e a **variação de 24h**. As moedas ficam agrupadas em principal, satélite e giros abertos, com o total de cada grupo. No topo: total aplicado, valor atual, resultado em aberto, resultado já realizado, melhor e pior moeda.
| Maquete do console | claude.ai (artefato) | Versão de exemplo, sem dados reais |

---

## 9. Infraestrutura do simulado (custo zero)

| Peça | Como funciona |
|---|---|
| Robô | `simulado/robo_simulado.py`, que o **GitHub Actions** roda a cada 15 minutos |
| Preços | Dados públicos da Binance (`data-api.binance.vision`), sem conta e sem chave |
| Dados | `simulado/estado.json`, `historico.csv`, `operacoes.csv`, `operacoes_satelite.csv` e `extrato.csv`, gravados no repositório a cada execução |
| Avisos | Bot do Telegram. O token e o Chat ID ficam como **segredos do GitHub** |
| Monitor | **GitHub Pages** a partir do branch do projeto |
| Arquivo | A carteira v1 (BTC/ETH, 24–25/11) está guardada em `simulado/arquivo/v1-btc-eth/` |

**Atenção:** o repositório é **público**. Para o simulado não há problema, porque os segredos ficam escondidos, mas ele deve virar **privado antes do dinheiro real**.

---

## 10. Resumo dos testes (backtest com dados reais da Binance)

| Teste | Resultado principal |
|---|---|
| Rebalanceamento 50/15/35, 2021–2026 | Robô +146% contra +89% da carteira parada. Rebalancear 1 vez por ano deu +195% |
| Frequência | Diário, trimestral, anual ou por faixas: todos parecidos (+128% a +195%) |
| "Oportunidades" frequentes na principal | Pioraram (+66% a +102%), porque as taxas comem o ganho |
| Carteira diversificada (6 moedas) | +88% contra +63% da 50/15/35 (jun/2021–nov/2026), com queda máxima um pouco maior |
| Até 3 operações por dia, extras com 2,5 pts | Mesmo resultado; as extras são raras |
| Gatilho de 1 ponto | Mesmo resultado, com o dobro de operações (~6 por mês) |
| Reserva em degraus (R$ 500) | Mesmo lucro de investir tudo, com queda menor (−58% contra −65%) quando a queda vem cedo |
| Moedas da satélite desde 2025 | Caíram de 83% a 86%. A cesta perdeu 46% com o robô, contra 55% parada |
| Reserva da satélite, giro curto (+1,5%) | −32% contra −33% com a reserva parada: 180 vendas com lucro, mas 5 posições presas |

O código e os resultados estão em `backtest/` e no `backtest/RESULTADO.md`.

---

## 11. Travas

| Trava | Situação |
|---|---|
| Saldo negativo ou qualquer sinal de dívida | Para tudo e avisa |
| Ordem maior que o saldo disponível | Nunca acontece: o robô limita ao saldo |
| Mais de 20 operações por dia em cada carteira | Bloqueado |
| Falha de preços ou de conexão | Nada muda, tenta de novo e avisa |
| Robô sem rodar | O monitor mostra **ATRASO** depois de 3 horas sem checagem |
| Queda de 7% em 24 h | **Trava de queda:** pausa só as compras de giro da satélite até recuperar (com aviso) |
| Dono quer parar | **/pausar** no Telegram para tudo; **/retomar** volta (só o chat do dono é aceito) |
| Falhas | Registradas em `simulado/saude.json` e mostradas no monitor (falhas em 24 h e link para as execuções) |
| Queda forte | Só aviso e uso da reserva. Nunca vende tudo em pânico |

**No dinheiro real, entram também:** chave de API sem saque e restrita ao IP do servidor, conta de margem nunca ativada, e checagem periódica das permissões da chave.

---

## 12. Fases

| Fase | Situação | Critério para avançar |
|---|---|---|
| 0 · Pesquisa e plano | ✅ Concluída | — |
| 1 · Backtest | ✅ Concluída | Rebalancear ganhou da carteira parada |
| **2 · Simulado ao vivo** | **🟡 Em andamento desde 24/11/2026** | 60 a 90 dias sem falha grave e com resultado coerente com o backtest |
| 3 · Dinheiro real pequeno | Pendente | Repositório privado, conta na Binance Brasil (KYC e 2FA), servidor com IP fixo (Oracle Cloud gratuito, em São Paulo), chave sem saque e o mesmo código com executor real |
| 4 · Continuidade | Pendente | Revisão mensal, e mais capital só se o dono quiser |

**Regras previstas para o dinheiro real** (pesquisa: Shrimpy, XBTO, Elliptic e as recomendações da Anthropic para agentes):
- voltar a **faixas mais largas** (2 a 5 pontos), com **rebalanceamento parcial** (só metade do caminho até o alvo) e **faixas assimétricas** (vender mais rápido nas altas, comprar com mais calma nas quedas), porque faixas de 1% são as mais prejudicadas pelas taxas;
- **pagar as taxas em BNB** (cerca de 25% de desconto na Binance) e usar ordens limitadas;
- **confirmação do dono no Telegram** para operações acima de um valor (por exemplo, R$ 100) e para aportes;
- o modo de teste atual (1 ponto, a cada 15 minutos, até 20 por dia) fica só no simulado, e o quadro "O robô está se pagando?" decide com dados.

**Por que a fase 3 precisa de servidor:** o GitHub Actions muda de IP a cada execução, e a Binance só deixa a chave negociar a partir de um IP fixo.

**Quando desistir:** se o robô não ganhar da carteira parada depois das taxas, se alguma trava falhar, ou se o projeto deixar de ser útil.

---

## 13. Impostos (confirmar com o contador)
- **Corretora brasileira:** isenção para vendas de até R$ 35 mil por mês. A MP 1.303, que acabaria com ela, caducou em 2025, mas o tema pode voltar.
- **Binance Brasil:** há indicação de que vale a regra de corretora nacional, por ter CNPJ, mas **não está confirmado**.
- **Corretora estrangeira:** 15% sobre o lucro, sem isenção.
- O extrato (`simulado/extrato.csv`) já registra cada operação com data, valor e taxa, o que facilita a declaração e a DeCripto.

---

## 14. Riscos

| Risco | Mitigação |
|---|---|
| Queda forte das moedas | Reserva em degraus, reais na carteira e capital pequeno |
| Moedas da satélite (alta volatilidade) | Valor pequeno, separado da principal, risco aceito |
| Posições de giro presas | Uma por moeda, R$ 25 cada, no máximo R$ 125 |
| Corretora quebrar ou travar saques | No real, deixar lá só o capital do robô |
| Bug no código | Simulado primeiro, travas e limites pequenos |
| Repositório público | Fechar antes do dinheiro real |
| Mudança de imposto ou regulação | Acompanhar e revisar com o contador |

---

## 15. Estrutura do repositório

```
index.html            monitor (GitHub Pages)
painel-ativos.html    mercado ao vivo
historico.html        histórico de operações
extrato.html          extrato da conta
regras.html           regras
assets/               logo e ícone
simulado/
  robo_simulado.py    o robô
  estado.json         estado das carteiras e reservas
  historico.csv       patrimônio diário (7h)
  operacoes.csv       operações da principal
  operacoes_satelite.csv
  extrato.csv         entradas e saídas de dinheiro
  arquivo/            carteiras antigas
backtest/             testes históricos e resultados
.github/workflows/    agendamento do robô (a cada 15 minutos)
PLANO.md              este documento
```

---

## 16. Histórico de decisões

| Data | Mudança |
|---|---|
| 24/11 | Pesquisa, prognóstico, plano v1, backtest e painel de mercado. Robô simulado BTC/ETH no ar, com Telegram |
| 24/11 | Nome Argo Trade Cripto. Monitor no estilo terminal, no GitHub Pages |
| 25/11 | Carteira diversificada de 6 moedas, recomeçada do zero (a BTC/ETH foi arquivada) |
| 25/11 | Até 3 operações por dia (extras com 2,5 pts). Resumo movido para as 7h |
| 25/11 | Reserva para quedas de R$ 500 em degraus de R$ 125 |
| 25/11 | Gatilho de 1,5 para 1 ponto e ordem mínima de R$ 10 |
| 25/11 | Nome final: **Argos** Trade Cripto. Logo provisório |
| 25/11 | Monitor reorganizado, página de regras, mercado ao vivo em página própria |
| 25/11 | Corretora estrangeira avaliada e descartada. Fica a Binance Brasil |
| 25/11 | Carteira satélite de R$ 250 (LTC, DOGE, ADA, AVAX, NEAR), abaixo da principal no monitor |
| 25/11 | Extrato da conta. Quadro da reserva movido para o extrato |
| 25/11 | Reserva da satélite de R$ 100: giro curto com venda em +1,5%. Robô passa a rodar toda hora |
| 25/11 | Monitor com ganhos e perdas por cripto (aplicado × vale agora, variação de 24h). Histórico em página própria |
| 25/11 | Robô passa a checar a cada 15 minutos (carteiras seguem a cada ~4 h) |
| 25/11 | Limite de operações por dia de 3 para 20 em cada carteira |
| 25/11 | Rebalanceamento a cada 15 minutos e todas as operações com gatilho de 1 ponto (teste simulado) |
| 25/11 | Pesquisa (GitHub, estudos e Anthropic) e recomendações implementadas: comandos e pausa pelo Telegram, trava de queda em 24 h, máximo de 2 giros abertos, painéis de desempenho, gráfico de queda e registro de falhas |
| 25/11 | Agendamento passa a ser disparado pelo cron-job.org a cada 15 minutos (o agendamento do GitHub não disparava) |
| 25/11 | "Oportunidade" vira "giro" (satélite) e "reserva para quedas" (principal), deixando claro que tudo é automático |
