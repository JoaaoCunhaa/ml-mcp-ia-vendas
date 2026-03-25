# 📏 Medidas (DAX)

Este é o catálogo central de todas as medidas DAX criadas no modelo. A documentação clara das medidas é crucial para a manutenibilidade e o reuso.

## Medidas de Vendas

### Total Faturamento

-   **Tabela:** `fVendas`
-   **Descrição:** Calcula a soma total do faturamento, multiplicando a quantidade pelo valor de cada item.
-   **Expressão DAX:**
    ```dax
    Total Faturamento = SUMX(fVendas, fVendas[qtd_item] * fVendas[valor_item])
    ```

### Ticket Médio

-   **Tabela:** `fVendas`
-   **Descrição:** Calcula o valor médio por venda.
-   **Expressão DAX:**
    ```dax
    Ticket Médio =
    DIVIDE(
        [Total Faturamento],
        DISTINCTCOUNT(fVendas[id_venda])
    )
    ```

## Medidas de Tempo

### Faturamento Acumulado no Ano (YTD)

-   **Tabela:** `fVendas`
-   **Descrição:** Calcula o faturamento acumulado desde o início do ano até a data selecionada.
-   **Expressão DAX:**
    ```dax
    Faturamento YTD = TOTALYTD([Total Faturamento], dCalendario[Date])
    ```