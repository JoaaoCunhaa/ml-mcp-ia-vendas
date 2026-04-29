# Visão Geral: MCP Primeira Mão Saga

Servidor **Model Context Protocol (MCP)** especializado no ecossistema de seminovos do programa **Primeira Mão** do **Grupo Saga**. Atua como ponte entre modelos de LLM (Claude, ChatGPT) e o estoque real das lojas, permitindo busca em linguagem natural, avaliação de veículos e registro de leads — tudo dentro do chat, sem sair da conversa.

---

## Objetivos

1. **Busca visual de veículos**: o cliente conversa com a IA e recebe um carrossel interativo com fotos, preços e botão de interesse — sem precisar navegar no site.
2. **Captura de lead no widget**: o cliente clica em "Tenho interesse" diretamente no card, informa nome e telefone, e o lead é registrado automaticamente no CRM Mobiauto + webhook n8n.
3. **Avaliação de troca em tempo real**: proposta automática de compra/troca via dados FIPE + API de precificação Saga, consultados pela placa sem perguntas adicionais ao cliente.
4. **Formulário de venda no widget**: após a avaliação, um formulário visual coleta nome e telefone do cliente que quer vender — sem que o consultor precise agir no chat.
5. **Notificação interna via webhook**: a cada lead criado, um POST é disparado para o n8n com dados completos do cliente e do veículo.

---

## Tools disponíveis

| Tool | Tipo | Descrição |
|---|---|---|
| `buscar_veiculos` | Compra | Retorna carrossel visual de veículos (widget ChatGPT Apps) |
| `registrar_interesse_compra` | Compra | Registra lead de compra no CRM + webhook |
| `avaliar_veiculo` | Venda | Calcula proposta de compra/troca via FIPE + Pricing |
| `exibir_formulario_venda` | Venda | Abre formulário visual de coleta de dados do vendedor |
| `registrar_interesse_venda` | Venda | Registra lead de venda no CRM + webhook (chamado pelo widget) |
| `buscar_veiculo` | Busca textual | Busca por ID/placa exata ou linguagem natural (retorno Markdown) |
| `estoque_total` | Busca textual | Lista geral de estoque por cidade (retorno Markdown) |
| `listar_lojas` | Informação | Lista todas as lojas Primeira Mão Saga com cidade/UF |
| `diagnostico_registro` | Debug | Testa integração com CRM Mobiauto |

---

## Widget ChatGPT Apps

A tool `buscar_veiculos` abre um **widget interativo** dentro do chat quando chamada via ChatGPT. O widget é composto de:

- **Carrossel horizontal** com scroll snap — mostra ~2 cards por vez, navegação com setas ←→
- **Card de veículo**: foto, marca, título, ano, km, preço formatado, loja, link para o site
- **Botão "Tenho interesse"**: expande um mini-formulário (nome + telefone) e chama `registrar_interesse_compra` via bridge MCP

A tool `exibir_formulario_venda` abre um **widget separado** (`ui://vehicle-sell`) com:
- Dados do veículo avaliado (marca, placa, km, proposta Saga)
- Formulário de nome + telefone
- Ao confirmar, chama `registrar_interesse_venda` via bridge MCP

Os dois widgets usam o mesmo JS/CSS mas recursos MCP distintos, evitando conflito de estado entre fluxos de compra e venda.

---

## Fonte de estoque

| Fonte | Prioridade | Quando usar |
|---|---|---|
| **Lambda AWS** (Athena) | Primária | `buscar_veiculos` — veículos ativos (`status = 1`) com imagem, preço, loja e link |
| **Mobiauto API** | Fallback (desabilitado) | Ativado apenas se `_LAMBDA_APENAS = False` |

A Lambda consulta as tabelas `modelled.pm_*` via AWS Athena. O filtro `d.status = 1` garante que apenas veículos disponíveis aparecem.

---

## Público-Alvo

| Perfil | Como usa |
|---|---|
| **Cliente final** | Busca veículos ou solicita avaliação via ChatGPT App; confirma interesse pelo widget sem sair do chat |
| **Consultor de vendas** | Recebe notificação automática do n8n com dados do cliente e do veículo quando um lead é gerado |
| **Equipe técnica** | Mantém a integração Lambda → Athena → Widget → CRM e evolui as tools |

---

## O que está fora do escopo

- Financiamento ou assinatura de contrato
- Histórico de negociações anteriores
- Gestão ou edição de estoque (somente leitura)
- Agendamento de visita à loja
