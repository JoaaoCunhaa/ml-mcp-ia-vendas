# 🔐 Estratégia de Permissões

A segurança e o acesso aos dados são gerenciados em diferentes níveis para garantir que os usuários vejam apenas as informações pertinentes.

## 1. Acesso aos Workspaces

As permissões nos workspaces são restritas à equipe de dados e aos validadores.

| Workspace | Grupo de Acesso | Nível de Permissão | Propósito | Solicitante | Autorizante |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **DEV** | `[Ex: GRP-Dados-BI-Devs]` | `Member / Contributor` | Permitir que desenvolvedores publiquem e editem conteúdo. | `[Ex: Tech Lead de Dados]` | `[Ex: Gerente de Dados]` |
| **HML** | `[Ex: GRP-Dados-BI-Devs]` | `Member` | Gerenciar a promoção de conteúdo para HML. | `[Ex: Tech Lead de Dados]` | `[Ex: Gerente de Dados]` |
| **HML** | `[Ex: GRP-Projeto-Validadores]`| `Viewer` | Permitir que os validadores testem os relatórios. | `[Ex: Product Owner]` | `[Ex: Gerente de Dados]` |
| **PRD** | `[Ex: GRP-Dados-BI-Admins]` | `Admin` | Gestão do ambiente de produção e permissões. | `[Ex: Tech Lead de Dados]` | `[Ex: Head de Dados]` |

## 2. Acesso ao Aplicativo (App)

O consumo dos relatórios pelos usuários finais é feito exclusivamente através do **Aplicativo do Power BI**, garantindo uma experiência de navegação controlada.

-   **Nome do App:** `[Nome do Projeto]`
-   **Link do App:** `[Link para o App publicado]`
-   **Audiências e Permissões:**
    -   **Audiência 1 (Ex: Diretoria):**
        -   **Grupo de Acesso:** `[Ex: GRP-Diretoria]`
        -   **Relatórios Visíveis:** Acesso a todos os relatórios.
    -   **Audiência 2 (Ex: Gerentes Regionais):**
        -   **Grupo de Acesso:** `[Ex: GRP-Gerentes-Regionais]`
        -   **Relatórios Visíveis:** Acesso apenas aos relatórios de performance regional.

## 3. Segurança em Nível de Linha (RLS)

Quando aplicável, a RLS é utilizada para restringir os dados que um usuário pode ver dentro de um mesmo relatório.

-   **Relatório(s) com RLS:** `[Nome do Relatório de Vendas]`
-   **Regras (Roles) Definidas no Modelo:**
    -   **Regra 1: `[Regional_Manager]`**
        -   **Lógica:** Filtra a tabela `fVendas` com base na região do gerente, cruzando o `USERPRINCIPALNAME()` com uma tabela de permissões (`dGerentes`).
        -   **Grupo de Acesso Mapeado:** `[Ex: GRP-Gerentes-Regionais]`