#!/bin/bash
#!/bin/bash

# Caminho para a virtualenv da raiz
VENV_DIR="../.venv"
# Caminho para a virtualenv da raiz
VENV_DIR="../.venv"

echo "🔍 Verificando virtualenv..."
if [ ! -d "$VENV_DIR" ]; then
    echo "📦 Criando virtualenv na raiz em $VENV_DIR..."
    python -m venv $VENV_DIR 
fi

echo "🚀 Ativando virtualenv da raiz..."
source "$VENV_DIR/Scripts/activate"
echo "🚀 Ativando virtualenv da raiz..."
source "$VENV_DIR/Scripts/activate"

echo "📦 Instalando mkdocs-material (se necessário)..."
python.exe -m pip install --upgrade pip
pip install mkdocs-material
pip install mkdocs-mermaid2-plugin

echo "🌐 Servindo site dos projetos em http://127.0.0.1:8001 ..."
mkdocs serve --dev-addr 127.0.0.1:8000