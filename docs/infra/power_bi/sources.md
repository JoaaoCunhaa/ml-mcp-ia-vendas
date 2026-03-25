# 🔌 Fontes de Dados

Esta seção detalha as fontes de dados conectadas aos modelos semânticos (datasets) do Power BI e como a conexão é estabelecida.

## Conexão com o Data Lake (AWS Athena)

-   **Modelo Semântico:** `[Nome do Modelo Semântico]`
-   **Modo de Conexão:** `Import`
-   **Gateway de Dados:**
    -   **Necessário:** Sim
    -   **Nome do Cluster do Gateway:** `[Nome do cluster, ex: Gateway-Corporativo-BI]`
    -   **Fonte de Dados no Gateway:** A conexão é configurada no gateway com o nome `[Nome da Fonte no Gateway, ex: Conexao-Athena-Datalake]`.
-   **Método de Autenticação:**
    -   **Tipo:** `[Ex: Basic, OAuth2]`
    -   **Credenciais:** As credenciais (chave de acesso e chave secreta) para a conexão estão armazenadas no gateway e foram fornecidas pela equipe de Engenharia de Dados.

## Conexão com [Outra Fonte, ex: Planilha Online]

-   **Modelo Semântico:** `[Nome do Modelo Semântico]`
-   **Modo de Conexão:** `Import`
-   **Gateway de Dados:**
    -   **Necessário:** Não (Conexão nativa da nuvem)
-   **Método de Autenticação:**
    -   **Tipo:** `OAuth2 - Credenciais Organizacionais`
    -   **Credenciais:** A atualização utiliza as credenciais do usuário `[ex: bi-service-account@suaempresa.com]`, que possui acesso à planilha.