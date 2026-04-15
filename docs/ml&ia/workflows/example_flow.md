# Exemplo de Fluxo: Compra de Veículo

Este documento descreve o fluxo completo de uma conversa de compra — do primeiro contato até o registro do lead no CRM.

---

## Contexto

O cliente acessa o ChatGPT App ou Claude com o MCP Primeira Mão configurado e inicia uma conversa.

---

## Passo 1 — Busca inicial

**Cliente:** "Tem algum Honda Civic disponível?"

**LLM chama:** `buscar_veiculo(consulta="Honda Civic")`

**Sistema:**
1. Extrai palavras-chave → `["honda", "civic"]`
2. Carrega estoque consolidado de todas as lojas
3. Fase 2 AND → encontra veículos com "honda" AND "civic"
4. Pré-renderiza cards com imagem, preço e link

**LLM exibe:**
```
![Honda Civic Touring 2021](https://cdn.mobiauto.com.br/...)
### **Honda Civic Touring 2021**
| | |
|---|---|
| 📍 Loja | SN GO BURITI |
| 🗓️ Ano | 2021 |
| 📏 KM | 32.000 km |
| 🎨 Cor | Preto |
| 🔖 Placa | ABC1D23 |

## 💰 R$ 89.900,00
[🛒 Ver oferta no site](https://www.primeiramaosaga.com.br/gradedeofertas)
```

---

## Passo 2 — Interesse confirmado

**Cliente:** "Gostei do Civic preto, quero falar com um consultor"

**LLM apresenta as duas opções:**
1. [🛒 Ver oferta no site](https://www.primeiramaosaga.com.br/gradedeofertas)
2. Falar com consultor — "me informe seu nome e telefone"

**Cliente:** "Me chamo João Silva, telefone 62999990001"

---

## Passo 3 — Criação automática de lead

**LLM chama:** `buscar_veiculo(consulta="Honda Civic", nome_cliente="João Silva", telefone_cliente="62999990001", titulo_card="Honda Civic Touring 2021", loja_unidade="SN GO BURITI", plate="ABC1D23", modelYear="2021", km="32000", colorName="Preto", preco_formatado="R$ 89.900,00")`

**Sistema internamente:**
1. Detecta `nome_cliente` + `telefone_cliente` → aciona `_criar_lead_compra`
2. `POST /api/proposal/v1.0/18405` (Mobiauto CRM) → cria lead BUY → recebe `lead_id: 65849002`
3. `POST webhook/cliente_quer_comprar` (n8n) → notifica consultor da SN GO BURITI
4. Retorna `{ registrado: true, dealer_id: "18405", mensagem: "Lead criado..." }`

**LLM responde:**
> "Tudo certo, João! Um consultor Saga da loja SN GO BURITI entrará em contato em breve sobre o Honda Civic Touring 2021."

---

## Exemplo de Fluxo: Avaliação e Venda

### Passo 1 — Solicitação de avaliação

**Cliente:** "Quero saber quanto vale meu carro. Placa RUR9J56, tem 38 mil km"

**LLM chama:** `avaliar_veiculo(placa="RUR9J56", km="38000")`

**Sistema:**
1. Consulta FIPE pela placa → retorna dados técnicos do veículo
2. Envia payload para API Pricing Saga
3. Pré-renderiza `proposta_markdown` com valor da proposta

**LLM exibe:**
```
## 💰 Proposta de Compra — Saga Primeira Mão

| | |
|---|---|
| 🚗 Veículo | Toyota Yaris 2020 |
| 🔖 Placa | RUR9J56 |
| 📏 KM | 38.000 km |

### Valor oferecido pela Saga:
# R$ 52.400,00

Gostaria de prosseguir? Informe seu nome e telefone.
```

### Passo 2 — Confirmação e lead automático

**Cliente:** "Aceito. Sou Maria Souza, telefone 62988880002"

**LLM chama:** `avaliar_veiculo(placa="RUR9J56", km="38000", nome_cliente="Maria Souza", telefone_cliente="62988880002")`

**Sistema internamente:**
1. Re-executa FIPE + Pricing (mantém dados consistentes)
2. Detecta `nome_cliente` + `telefone_cliente` → aciona `_criar_lead_venda`
3. `POST /api/proposal/v1.0/{dealer_id}` (Mobiauto CRM) → cria lead SELL
4. `POST webhook/cliente_quer_vender` (n8n) → notifica consultor de avaliação
5. Retorna `proposta_markdown` + `lead: { registrado: true, ... }`

**LLM responde:**
> "Perfeito, Maria! Um consultor Saga entrará em contato em breve para falar sobre a venda do seu Toyota Yaris 2020."
