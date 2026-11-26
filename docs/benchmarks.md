# Benchmarks internos

[English](en/benchmarks.md) · [Início](../README.md)

Sete execuções de capítulos completos no Windows durante o desenvolvimento do Beta. Os IDs abaixo distinguem as execuções publicadas. Os capítulos usados no teste permanecem internos.

| Rodada | Data em 2026 | Origem → PT-BR | Páginas lógicas | Grupos detectados | Total (s) | Média (s/pág.) |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| B01 | 2026-11-18 | KO | 93 | 232 | 411,64 | 4,43 |
| B02 | 2026-11-17 | EN | 65 | 91 | 342,64 | 5,27 |
| B03 | 2026-11-22 | RU | 57 | 219 | 425,27 | 7,46 |
| B04 | 2026-11-18 | EN | 21 | 84 | 162,18 | 7,72 |
| B05 | 2026-11-13 | EN | 85 | 234 | 793,11 | 9,33 |
| B06 | 2026-11-23 | EN | 42 | 310 | 439,34 | 10,46 |
| B07 | 2026-11-19 | EN | 31 | 223 | 368,13 | 11,88 |

## Metodologia

- A média usa tempo total registrado dividido por páginas lógicas processadas. O pipeline pode reunir ou dividir os recortes baixados para formar a página lógica.
- Os relatórios registram processamento completo, Modo Rápido desligado, coleta sem cache de download, limpeza, tradução, diagramação e PDF. As datas usam o fuso de Manaus. Velocidade e latência da rede não foram medidas.
- Um ensaio separado documentou Ryzen 5 5600GT, 32 GB de RAM e Radeon RX 6600 de 8 GB. O hardware e o build exatos por rodada não estão confirmados. A configuração de referência não é requisito mínimo.
- A contagem de grupos descreve detecções do aplicativo. Cobertura precisaria de uma referência anotada. Precisão de OCR e tradução exige comparação textual e semântica. A limpeza e reconstrução exigem inspeção visual. A presença de um PDF, por si só, não certifica páginas nem substitui revisão.

[Benchmarks no site](https://komyst.com.br/benchmarks.html).
