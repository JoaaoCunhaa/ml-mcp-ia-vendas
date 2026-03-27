# 📖 Visão Geral: MCP Primeira Mão Saga

O projeto consiste em um servidor **Model Context Protocol (MCP)** especializado no ecossistema de veículos **seminovos** do programa **Primeira Mão** do **Grupo Saga**. Ele atua como uma ponte de dados em tempo real para que modelos de LLM (como ChatGPT e Claude) permitam que clientes finais e vendedores interajam com o inventário de seminovos via linguagem natural.

## Sumário
- [Objetivos](#objetivos)  
- [Escopo](#escopo)  
- [Público-Alvo](#público-alvo)

---

## Objetivos

O projeto **MCP Primeira Mão** tem como objetivo:

1. **Interação Natural com o Cliente**: Permitir que clientes finais busquem veículos seminovos através de **ChatGPT Apps**, conversando com a IA para filtrar modelos, preços e condições de forma consultiva.
2. **Exposição Estratégica do Inventário**: Disponibilizar o estoque do selo "Primeira Mão" de forma dinâmica, superando a rigidez dos filtros de busca tradicionais de sites e portais.
3. **Facilitação da Jornada de Compra**: Oferecer dados técnicos, fotos reais via integração Mobiauto e valores de Tabela FIPE instantaneamente para acelerar a decisão de compra.

## Escopo

- **Busca Semântica de Seminovos**: Implementação de ferramentas (`tools`) para listar, filtrar e pesquisar o estoque consolidado de todas as unidades seminovos do Grupo Saga.
- **Dossiê do Veículo**: Recuperação de detalhes profundos (opcionais, quilometragem, histórico e fotos) para exibição rica dentro da interface do chat.
- **Avaliação de Troca**: Motor de cálculo integrado à API de precificação para que o cliente receba uma estimativa de avaliação do seu veículo usado ao negociar um "Primeira Mão".
- **Infraestrutura Híbrida**: Suporte a transporte via **stdio** (para uso em instâncias locais/inspetor) e **SSE** (para integração com aplicações web e Custom GPTs).
- **Validação de Dados**: Normalização rigorosa de placas e valores monetários para garantir a integridade das informações apresentadas ao cliente.

## Público-Alvo

- **Clientes Finais**: Usuários que buscam uma experiência de compra moderna e personalizada através de assistentes de IA.
- **Equipe de Vendas (SDRs/Consultores)**: Utilização do MCP como ferramenta de apoio rápido para identificar e enviar opções de veículos que dão "match" com o perfil do lead.
- **Desenvolvedores e Inovação**: Equipe técnica focada em manter a conectividade entre os sistemas core da Saga (Mobiauto/Postgres) e as novas interfaces de inteligência artificial.