# Workflows n8n — MCP Primeira Mão Saga

## Tabela de Workflows

| Nome do Workflow | Gatilho | Propósito | Status |
|---|---|---|---|
| **cliente_quer_comprar** | Webhook POST | Recebe dados de lead de compra gerado pelo MCP e notifica consultor responsável | Ativo |
| **cliente_quer_vender** | Webhook POST | Recebe dados de lead de venda gerado pelo MCP e notifica consultor responsável | Ativo |

---

## Workflow 1: cliente_quer_comprar

**Endpoint:** `https://automatemaiawh.sagadatadriven.com.br/webhook/cliente_quer_comprar`

**Acionado por:** Tool `registrar_interesse_compra` em `main.py`, chamada pelo widget via bridge `window.openai.callTool`, após o cliente clicar em "Tenho interesse" e preencher nome e telefone no card do carrossel.

**Payload recebido:**

```json
{
  "lead_id":          "65849002",
  "nome_cliente":     "João Silva",
  "telefone_cliente": "62999990001",
  "email_cliente":    "joao@email.com",
  "titulo_card":      "Honda Civic Touring 2021",
  "veiculo_id":       "12345678",
  "preco_formatado":  "R$ 89.900,00",
  "loja_unidade":     "SN GO BURITI",
  "plate":            "ABC1D23",
  "modelYear":        "2021",
  "km":               "32000",
  "colorName":        "Preto",
  "dealer_id":        "18405"
}
```

**Propósito:** Notificar o consultor da loja `loja_unidade` que um cliente demonstrou interesse no veículo `titulo_card` e já tem lead registrado no CRM sob o id `lead_id`.

---

## Workflow 2: cliente_quer_vender

**Endpoint:** `https://automatemaiawh.sagadatadriven.com.br/webhook/cliente_quer_vender`

**Acionado por:** Tool `registrar_interesse_venda` em `main.py`, chamada pelo widget de venda via bridge `window.openai.callTool`, após o cliente preencher nome e telefone no formulário de avaliação e confirmar a proposta.

**Payload recebido:**

```json
{
  "lead_id":           "65848731",
  "nome_cliente":      "Maria Souza",
  "telefone_cliente":  "62988880002",
  "email_cliente":     "maria@email.com",
  "placa":             "TST1T23",
  "km":                "50000",
  "veiculo_descricao": "Honda Fit EX 2018",
  "valor_proposta":    "28500.00",
  "preco_formatado":   "R$ 28.500,00",
  "marca":             "Honda",
  "modelo":            "Fit",
  "ano_modelo":        "2018",
  "cor":               "Prata",
  "uf":                "GO",
  "dealer_id":         "18415"
}
```

**Propósito:** Notificar o consultor de avaliação que um cliente quer vender o veículo `veiculo_descricao` (placa `placa`) e a proposta da Saga é `preco_formatado`. O lead já está registrado no CRM.
