import re

def normalizar_placa(placa: str) -> str:
    """Remove espaços, traços e garante que a placa esteja em maiúsculas."""
    if not placa:
        return ""
    return re.sub(r'[^A-Z0-9]', '', placa.upper().strip())

def formatar_moeda(valor) -> str:
    """Garante que o valor seja '0.00' para a API de precificação."""
    try:
        if isinstance(valor, str):
            valor = valor.replace("R$", "").replace(".", "").replace(",", ".").strip()
        return "{:.2f}".format(float(valor))
    except (ValueError, TypeError):
        return "0.00"

def extrair_lista_veiculos(data: dict) -> list:
    """Extrai a lista de veículos de dentro do JSON da Mobiauto."""
    if isinstance(data, list):
        return data
    chaves = ["imagem", "data", "items", "results", "vehicles"]
    for chave in chaves:
        lista = data.get(chave)
        if isinstance(lista, list):
            return lista
    return []