#  Regras de Negócio de Analytics

Este documento é o catálogo central para todas as regras de negócio e definições que governam as métricas e os KPIs apresentados nos relatórios de Power BI. Manter este documento atualizado é crucial para a consistência dos dados.

---
## Regra 1: Definição de "Cliente Ativo"

-   **ID da Regra:** `BR-AN-001`
-   **DATA SOLICATAÇÃO:** '2025-09-31'
-   **Regra Ativa:** True
-   **Solicitante:** [Ex: Diretoria de Vendas]
-   **Descrição:** Um cliente é considerado **"Ativo"** se ele realizou pelo menos uma compra nos últimos **90 dias** a partir da data atual.
-   **Impacto:**
    -   **Medidas Afetadas:** `[Qtd Clientes Ativos]`, `[Taxa de Retenção]`
    -   **Relatórios Afetados:** `[Dashboard de Vendas]`, `[Relatório de Performance do Vendedor]`
-   **Lógica de Implementação (DAX):**
    A lógica é implementada na medida `[Qtd Clientes Ativos]`. Ela conta os clientes distintos da `fVendas` onde a data da venda está dentro do intervalo definido.
    ```dax
    Qtd Clientes Ativos = 
    CALCULATE(
        DISTINCTCOUNT(fVendas[id_cliente]),
        DATESINPERIOD(
            dCalendario[Date],
            MAX(dCalendario[Date]),
            -90,
            DAY
        )
    )
    ```

---
## Regra 2: Classificação de Oportunidade (Porte)

-   **ID da Regra:** `BR-AN-002`
-   **DATA SOLICATAÇÃO:** '2025-09-31'
-   **Regra Ativa:** True
-   **Solicitante:** [Ex: Gerência de Produto]
-   **Descrição:** As oportunidades de negócio são classificadas por porte com base no seu valor total.
    -   **Pequena:** Valor < $10,000
    -   **Média:** Valor entre $10,000 e $50,000
    -   **Grande:** Valor > $50,000
-   **Impacto:**
    -   **Colunas Afetadas:** Coluna calculada `[Porte da Oportunidade]` na tabela `fOportunidades`.
    -   **Relatórios Afetados:** Todos os relatórios de funil de vendas.
-   **Lógica de Implementação (DAX ou Power Query):**
    A regra é implementada como uma coluna calculada na tabela `fOportunidades`.
    ```dax
    Porte da Oportunidade = 
    SWITCH(
        TRUE(),
        fOportunidades[Valor] < 10000, "Pequena",
        fOportunidades[Valor] <= 50000, "Média",
        "Grande"
    )
    ```