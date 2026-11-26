# Conceptual architecture

[Português](../architecture.md) · [Home](../../README.en.md)

```mermaid
flowchart TD
    A[Import pages] --> B[Detect regions and recognize text]
    B --> C[Prepare masks and clean artwork]
    B --> D[Optional online translation: text and context]
    C --> E[Apply text and review]
    D --> E
    C -->|Clean only| F[Export files on the device]
    E --> F
    G[Account and license] -.->|App access| A
```

Visual processing and export take place on Windows. Online translation is a separate flow that receives the required text. Textual results and operational records may be kept to resume or recover work. Account and licensing services serve separate purposes. [Privacy Policy](https://komyst.com.br/privacidade.html).
