# 🧠 Modelo Semântico

O modelo semântico é a camada de negócios que traduz os dados brutos em termos e estruturas compreensíveis para os usuários finais. Esta seção documenta as decisões de design e as convenções adotadas.

## Estrutura e Design

-   **Metodologia:** O modelo foi desenhado seguindo a metodologia **Star Schema (Esquema Estrela)**.
-   **Tabelas Fato:** Contêm as métricas e eventos (ex: `fVendas`).
-   **Tabelas Dimensão:** Contêm os atributos descritivos (ex: `dProduto`, `dVendedor`).

## Convenções de Nomenclatura

-   **Tabelas:**
    -   Fatos: prefixo `f` (ex: `fVendas`).
    -   Dimensões: prefixo `d` (ex: `dProduto`).
-   **Colunas:**
    -   Nomes escritos por extenso e de forma clara (ex: `Nome do Produto` em vez de `nm_prod`).
    -   Colunas técnicas (chaves) devem ser ocultadas da visão do relatório.
-   **Medidas:**
    -   Nomes claros e diretos, sem prefixos (ex: `Total Faturamento`).
    -   Medidas devem ser agrupadas em tabelas dedicadas (ex: uma tabela em branco chamada `_Medidas`).

## Hierarquias

Liste as principais hierarquias criadas para facilitar a navegação (drill-down/drill-up).

-   **Hierarquia de Tempo:** Ano > Trimestre > Mês > Dia
-   **Hierarquia de Produto:** Categoria > Subcategoria > Nome do Produto