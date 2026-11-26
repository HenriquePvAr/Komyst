# Arquitetura conceitual

[English](en/architecture.md) · [Início](../README.md)

```mermaid
flowchart TD
    A[Importar páginas] --> B[Detectar regiões e reconhecer texto]
    B --> C[Preparar máscaras e limpar a arte]
    B --> D[Tradução online opcional: texto e contexto]
    C --> E[Aplicar o texto e revisar]
    D --> E
    C -->|Apenas Clean| F[Exportar arquivos no dispositivo]
    E --> F
    G[Conta e licença] -.->|Acesso ao aplicativo| A
```

O processamento visual e a exportação ocorrem no Windows. A tradução online é um fluxo separado que recebe o conteúdo textual necessário. Resultados textuais e informações operacionais podem ser mantidos para retomada e recuperação. Conta e licenciamento têm finalidades próprias. [Política de Privacidade](https://komyst.com.br/privacidade.html).
