# Template de Projeto

Este repositório é um esqueleto para projetos de dados.

## Estrutura

- `.github/` — Workflows do GitHub Actions
  - `workflows/` — pipelines de deploy
- `data/` — arquivos de dados
  - `raw/` — dados brutos
  - `processed/` — dados tratados
  - `external/` — fontes externas
- `docs/` — documentação global do projeto MKDOCS
  - `bi/` — governança e onboarding BI ([ver docs/bi/README.md](docs/bi/README.md))
  - `n8n/` — referência/link para docs do n8n ([ver docs/n8n/README.md](docs/n8n/README.md))
- `infra/` — infraestrutura como código e automação
  - `cloudformation/` — templates CloudFormation
  - `terraform/` — templates Terraform
  - `n8n/` — stacks Swarm/Traefik para n8n ([ver infra/n8n/README.md](infra/n8n/README.md))
  - `powerbi/` — pipelines CI/CD, ARM/Bicep de workspaces ([ver infra/powerbi/README.md](infra/powerbi/README.md))
- `notebooks/` — notebooks Jupyter
  - `exploratory/` — estudos exploratórios
  - `production/` — notebooks de produção
- `scripts/` — automações genéricas (deploy, etc.)
- `src/` — código-fonte principal
  - `common/` — utilitários compartilhados
  - `glue/` — códigos e configs AWS Glue
  - `lambdas/` — funções AWS Lambda
  - `python/` — módulos auxiliares
- `tests/` — testes unitários e integração

- `n8n/` — automações, fluxos, credenciais e documentação do n8n
  - `flows/` — exports .json de workflows
  - `credentials/` — placeholders de credenciais (sem secrets)
  - `docker/` — docker-compose, stacks ([ver n8n/docker/README.md](n8n/docker/README.md))
  - `scripts/` — utilitários n8n-specific
  - `tests/` — e2e de fluxos
  - `docs/` — guias, naming, README ([ver n8n/docs/README.md](n8n/docs/README.md))
- `bi/` — projetos e padrões de Business Intelligence (Power BI)
  - `powerbi/`
    - `projects/` — 1 pasta = 1 projeto PBIP
      - `meu-dashboard/` — exemplo de projeto PBIP
        - `meu-dashboard.pbip`
        - `report/`, `dataset/`, `metadata/`, `README.md`
    - `templates/` — arquivos .pbit
    - `dataflows/` — exports JSON
    - `scripts/` — CLI/REST/pbi-tools
    - `tests/` — validação DAX/linters
    - `docs/` — style-guide, convenções ([ver bi/powerbi/docs/README.md](bi/powerbi/docs/README.md))
  - `standards/` — diretrizes globais BI ([ver bi/standards/README.md](bi/standards/README.md))

Arquivos adicionais:

Arquivos adicionais:

- `requirements.txt` – dependências do projeto
- `LICENSE` – licença de uso

## .gitignore

O arquivo `.gitignore` evita que alguns caminhos sejam versionados:

```
.venv
.github
.env
```

`.venv` é o ambiente virtual local, `.github` pode conter configurações específicas de workflows e `.env` armazena variáveis de ambiente locais.

## Documentação (MkDocs)
A pasta docs/ contém um site de documentação construído com MkDocs e o tema Material for MkDocs. Para visualizar e editar a documentação localmente, siga os passos abaixo.

Pré-requisitos
Python 3.9+

Git

Como Rodar Localmente
Para facilitar o processo, você pode usar um script que prepara o ambiente e inicia o servidor da documentação.

Crie o script: Salve o conteúdo abaixo em um arquivo chamado run_docs.sh dentro da pasta do seu repo.

# Bash

#!/bin/bash

### Define o caminho para a virtualenv na raiz do projeto
VENV_DIR="../.venv"

echo "🔍 Verificando ambiente virtual..."
if [ ! -d "$VENV_DIR" ]; then
    echo "📦 Criando ambiente virtual em $VENV_DIR..."
    python -m venv $VENV_DIR 
fi

echo "🚀 Ativando ambiente virtual..."
### O caminho de ativação pode variar entre Windows (Scripts) e Linux/macOS (bin)
source "$VENV_DIR/Scripts/activate"

echo "📦 Instalando/Atualizando dependências..."
pip install --upgrade pip
pip install mkdocs-material mkdocs-mermaid2-plugin

echo "🌐 Servindo a documentação em http://127.0.0.1:8000 ..."
mkdocs serve --dev-addr 127.0.0.1:8000
Execute o script a partir da pasta docs/:


# Rode o script
./start_local.sh

Após a execução, a documentação estará disponível no seu navegador no endereço http://127.0.0.1:8000. O site será atualizado automaticamente sempre que você salvar uma alteração nos arquivos .md.