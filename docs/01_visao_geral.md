# Visão Geral — MCP Primeira Mão Saga

Servidor **Model Context Protocol (MCP)** especializado no ecossistema de seminovos do programa **Primeira Mão** do **Grupo Saga**. Atua como ponte entre o ChatGPT e os sistemas internos do Grupo Saga: estoque real, CRM de leads, FIPE e precificação — tudo dentro da conversa, sem sair do chat.

---

## O que resolve

| Problema | Solução |
|---|---|
| Cliente pergunta sobre seminovos e recebe só texto | Widget visual com fotos, preços e botão de interesse |
| Consultor não sabe que o cliente demonstrou interesse | Lead criado no CRM + notificação automática via n8n |
| Cliente quer saber quanto receberia pelo seu carro | Avaliação com FIPE real + modelo interno de precificação |
| Cliente quer vender mas não sabe com quem falar | Formulário no chat; consultor é notificado automaticamente |

---

## Como funciona — visão do cliente

### Fluxo de compra

1. O cliente conversa com o ChatGPT e pede veículos disponíveis  
   *"Quero ver HRVs disponíveis em Goiânia"*

2. O sistema busca no estoque real e exibe um **carrossel visual** com fotos, preço, ano, KM e loja.

3. O cliente clica em **"Tenho interesse"** — o formulário aparece em todos os cards simultaneamente.

4. Preenche nome e telefone no card do veículo desejado e clica em enviar.

5. Um consultor da loja correspondente recebe a notificação e entra em contato.

### Fluxo de venda / avaliação

1. O cliente diz que quer vender seu carro  
   *"Quanto a Saga pagaria no meu Civic 2019 placa ABC1D23, 55.000 km?"*

2. O sistema consulta a tabela FIPE pela placa e calcula uma proposta com o modelo interno de precificação.

3. O **formulário de avaliação** aparece com o veículo e o valor da proposta já preenchidos. O cliente informa nome e telefone e confirma.

4. Um consultor de avaliação recebe notificação com todos os detalhes do veículo e da proposta.

---

## Como funciona — visão do consultor

O consultor recebe via **n8n** uma notificação contendo:

**Para compra:**
- Nome e telefone do cliente
- Veículo de interesse (modelo, ano, KM, cor, placa)
- Preço e loja
- ID do lead já criado no CRM Mobiauto

**Para venda:**
- Nome e telefone do cliente
- Placa, KM e descrição do veículo
- Valor da proposta calculada
- ID do lead criado no CRM

O lead já está registrado no Mobiauto quando o consultor recebe a notificação — sem cadastro manual.

---

## Ferramentas disponíveis (tools)

| Tool | O que faz | Usa widget? |
|---|---|---|
| `buscar_veiculos` | Busca estoque com filtros e exibe carrossel visual | Sim (compra) |
| `registrar_interesse_compra` | Registra lead de compra a partir dos dados do widget | Via widget |
| `avaliar_veiculo` | Consulta FIPE e calcula proposta de compra do carro do cliente | Não |
| `exibir_formulario_venda` | Exibe formulário de contato após avaliação | Sim (venda) |
| `registrar_interesse_venda` | Registra lead de venda a partir do formulário | Via widget |
| `buscar_veiculo` | Busca textual por modelo, placa ou ID | Não |
| `estoque_total` | Lista estoque geral de uma cidade em texto | Não |
| `listar_lojas` | Lista todas as lojas Primeira Mão | Não |
| `diagnostico_registro` | Testa conectividade com o CRM (uso interno) | Não |

---

## Fonte de dados de estoque

**Primária:** AWS Lambda que consulta o AWS Athena sobre as tabelas `modelled.pm_*`. Retorna veículos `status = 1` (disponíveis) com imagem associada.

**Fallback:** API Mobiauto de estoque — acionada automaticamente se a Lambda estiver indisponível.

---

## Infraestrutura resumida

```
Cliente no ChatGPT
       ↓
   MCP Server (FastMCP 3.2.2, Python 3.13, SSE porta 8000)
       ├── Estoque → Lambda AWS → Athena (modelled.pm_*)
       ├── Widget → iframe ChatGPT (carrossel ou formulário)
       ├── CRM → Mobiauto (leads de compra e venda)
       ├── FIPE → API interna Saga
       ├── Precificação → API interna Saga
       └── Notificação → Webhooks n8n → consultor
```

Exposto em produção via Traefik em `mcp-primeiramao.sagadatadriven.com.br` com TLS automático (Let's Encrypt).

---

## Escopo — o que o sistema NÃO faz

- Não negocia preço
- Não agenda visitas
- Não acessa dados de financiamento
- Não mantém histórico entre sessões diferentes
- Não envia mensagens WhatsApp diretamente (isso é responsabilidade do n8n)
- Não gerencia o CRM além da criação do lead inicial

---

## Responsável técnico

João Cunha — joao.clara@gruposaga.com.br
