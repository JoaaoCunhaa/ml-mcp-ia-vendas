# Regras de Negócio — MCP Primeira Mão Saga

---

## BR-001: Busca de veículo em 4 fases progressivas

- **ID:** `BR-001`
- **Descrição:** A busca por veículos nunca retorna vazio. Se nenhuma correspondência exata for encontrada, o sistema avança progressivamente por 4 fases até apresentar ao menos uma sugestão ou uma mensagem de fallback.
- **Tool impactada:** `buscar_veiculo`
- **Lógica:**
  - Fase 1: busca por ID exato ou placa (somente se o termo parece placa/ID)
  - Fase 2: todos os termos extraídos batem (AND semântico)
  - Fase 3: parte dos termos bate — ordenado por score decrescente (OR ranqueado)
  - Fase 4: nenhum termo bateu — retorna até 20 sugestões gerais; se estoque vazio, retorna mensagem de indisponibilidade

---

## BR-002: Dados técnicos do veículo vêm da FIPE — nunca do cliente

- **ID:** `BR-002`
- **Descrição:** Para avaliação de veículo, o LLM pede ao cliente apenas **placa** e **km**. Todos os dados técnicos (versão, carroceria, combustível, valor FIPE, código FIPE, ano) são obtidos automaticamente pela API FIPE via placa. O LLM **não deve perguntar** essas informações ao cliente.
- **Tool impactada:** `avaliar_veiculo`
- **Exceção:** `uf`, `cor` e `existe_zero_km` podem ser preenchidos se o cliente mencionar espontaneamente na conversa.

---

## BR-003: Lead de compra — duas opções sempre apresentadas

- **ID:** `BR-003`
- **Descrição:** Quando o cliente demonstrar interesse em comprar um veículo específico, o LLM deve obrigatoriamente apresentar duas opções:
  1. Link para o site Primeira Mão (`https://www.primeiramaosaga.com.br/gradedeofertas`)
  2. Falar com consultor — coletar nome e telefone e re-chamar a tool com esses dados para criação automática do lead
- **Tools impactadas:** `estoque_total`, `buscar_veiculo`
- **Lógica:** O lead é criado internamente pela função `_criar_lead_compra` — não existe tool separada para isso.

---

## BR-004: Lead de venda — CRM é a ação principal; site é fallback

- **ID:** `BR-004`
- **Descrição:** No fluxo de venda, o CRM Mobiauto é sempre a ação primária. O link do site (`url_venda`) só é apresentado como alternativa quando `lead.registrado = false`.
- **Tool impactada:** `avaliar_veiculo`
- **Lógica:** Quando `nome_cliente` e `telefone_cliente` são informados, `_criar_lead_venda` é chamado automaticamente. Se falhar, o LLM exibe o `fallback_url`.

---

## BR-005: Dealer ID resolvido pelo nome da loja ou UF

- **ID:** `BR-005`
- **Descrição:** Para criar um lead, o sistema precisa do `dealer_id` da loja. A resolução segue esta prioridade:
  1. Nome da loja (`loja_nome`) → match exato → match parcial no cadastro
  2. UF do cliente (`uf_fallback`) → primeiro dealer cadastrado na UF
  3. Primeira loja da lista (fallback final — garante que sempre haverá um dealer_id)
- **Implementação:** `MobiautoProposalService._dealer_por_nome` e `_dealer_por_uf`

---

## BR-006: Paginação automática de estoque

- **ID:** `BR-006`
- **Descrição:** O estoque é buscado em grupos de 3 lojas por página. Se uma página retornar zero veículos com imagem, o sistema avança automaticamente para a próxima, sem exigir nova chamada do LLM.
- **Tool impactada:** `estoque_total`
- **Limite:** Veículos sem imagem são descartados — garantia de qualidade visual no card.

---

## BR-007: Markdown pré-renderizado no servidor

- **ID:** `BR-007`
- **Descrição:** Cards de veículos e propostas de avaliação são renderizados em Markdown completo no servidor Python. O LLM exibe o campo `cards_markdown` ou `proposta_markdown` diretamente, sem montar templates ou inventar dados.
- **Impacto:** Garante consistência visual independente do modelo de LLM utilizado.
- **Campos protegidos:** O bloco `_meta` de `estoque_total` nunca deve ser exibido ao cliente.

---

## BR-008: Webhook aguardado antes do retorno ao LLM

- **ID:** `BR-008`
- **Descrição:** O POST para o webhook n8n é aguardado (await) antes de retornar a resposta ao LLM. Isso garante que o consultor seja notificado antes que o LLM confirme o registro ao cliente. Falha no webhook não bloqueia o retorno — é logada como warning.
- **Timeout webhook:** 10s
