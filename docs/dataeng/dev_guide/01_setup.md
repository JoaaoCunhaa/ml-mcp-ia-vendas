# 💻 Setup do Ambiente

Este guia descreve como configurar seu ambiente de desenvolvimento local para contribuir com o projeto.

## Pré-requisitos

-   Git
-   Python 3.9+ e Pip
-   Docker
-   AWS CLI (configurado com credenciais de acesso)

## Passos para Configuração

1.  **Clone o Repositório:**
    ```bash
    git clone [https://docs.github.com/pt/repositories/creating-and-managing-repositories/about-repositories](https://docs.github.com/pt/repositories/creating-and-managing-repositories/about-repositories)
    cd [nome-do-repositorio]
    ```

2.  **Crie e Ative um Ambiente Virtual:**
    ```bash
    python -m venv .venv
    source .venv/bin/activate
    ```

3.  **Instale as Dependências:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure as Variáveis de Ambiente:**
    -   Copie o arquivo de exemplo: `cp .env.example .env`
    -   Edite o arquivo `.env` com os valores para o seu ambiente de desenvolvimento. Este arquivo **não é versionado**.

    ```bash
    # .env
    ENV=dev
    AWS_REGION=us-east-1
    RAW_BUCKET=meu-bucket-raw-dev
    ```