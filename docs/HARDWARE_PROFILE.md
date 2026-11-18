# Perfil de hardware medido

Medição física em 08/11/2026, entre 13:04 e 13:13, fuso America/Manaus.
Este documento registra uma configuração testada e o consumo observado;
**não estabelece requisitos mínimos homologados**.

## Configuração de referência

| Componente | Configuração usada |
| --- | --- |
| Sistema | Windows 64 bits, Python 3.11 |
| CPU | AMD Ryzen 5 5600GT, 6 núcleos / 12 threads |
| RAM instalada | 32 GB, aproximadamente 31,37 GiB utilizáveis pelo Windows |
| GPU principal | AMD Radeon RX 6600, capacidade comercial de 8 GB |
| GPU integrada | AMD Radeon Graphics; também inventariada nos contadores |
| Execução | Qualidade, PDF, force ligado, tradução de SFX desligada |
| Motores observados | RapidOCR, Paddle isolado, LaMA/DirectML e FLUX/Vulkan |
| Workers de página efetivos | 1, conforme relatório final do pipeline |

Para uma ficha técnica pública, apresentar **32 GB de RAM e RX 6600 de 8 GB
como configuração de referência testada para este fluxo com FLUX**, sem chamar
esses valores de mínimo. Ainda falta validar máquinas com menos RAM/VRAM,
CPU-only e o fluxo sem reparo generativo em condições controladas.

## Consumo observado no capítulo de referência

Hero Killer, episódio 285: 65 páginas lógicas, processamento completo com saída
PDF e 65 imagens CLEAN + 65 traduzidas. O job terminou com **revisão necessária**;
a coleta de recursos não certifica a qualidade visual da tradução.

| Recurso da árvore do job | Pico amostrado | Mediana das amostras |
| --- | ---: | ---: |
| RAM residente, soma dos working sets dos processos | **8,40 GiB** | 3,55 GiB |
| Memória privada comprometida | **13,69 GiB** | 5,62 GiB |
| GPU: memória dedicada reportada pelo Windows | **4,70 GiB** | 2,75 GiB |
| GPU: memória compartilhada reportada pelo Windows | **4,49 GiB** | 0,21 GiB |

Memória comprometida não equivale a RAM física: parte pode estar paginada.
Memória compartilhada da GPU utiliza memória do sistema; **não somar 4,49 GiB
aos 8,40 GiB para inventar uma exigência adicional de RAM**. As métricas medem
coisas diferentes, com máximos que podem ocorrer em momentos distintos.
Somar RSS de processos também pode contar páginas compartilhadas entre eles;
esse número não é uma medição de memória física única proporcional.

Os valores de GPU são filtrados pelos PIDs do runner e descendentes. Não são
o uso total da placa por navegadores, desktop e outros aplicativos. Os 8 GB da
placa não significam que toda essa capacidade estava disponível exclusivamente
ao Komyst. A capacidade foi consultada por DXGI; `AdapterRAM` do inventário WMI
não foi usado para inferir capacidade de placas maiores.

CPU: pico amostrado de aproximadamente **67% da capacidade total dos 12
processadores lógicos**, calculado por diferença de tempo de CPU dos processos.
Contadores de motores GPU são independentes e sobrepostos; não há um percentual
único de GPU obtido pela soma deles. Um valor bruto fora de faixa (101) foi
preservado na evidência e não publicado como porcentagem válida de utilização.

## Tempo e armazenamento

| Medida | Resultado |
| --- | ---: |
| Job, início até término | **545,88 s — 9min06s** |
| Tempo interno do pipeline | 539,54 s — 8min59,5s |
| Download/coleta | 48,02 s |
| Preparação/split | 29,34 s |
| OCR inicial, parede | 33,57 s |
| Análise/classificação/sweep, parede | 149,28 s |
| Preflight de layout/limpeza, parede | 197,16 s |
| Chamadas/contabilidade de tradução registradas | 6,28 s |
| Pós-tradução, parede | 43,20 s |
| Geração do PDF | 2,64 s |
| Arquivos persistidos na pasta completa deste run | 621.066.624 bytes, aproximadamente 592,3 MiB |
| PDF deste run | 13.103.135 bytes, aproximadamente 12,5 MiB |

Tempos de subetapas se sobrepõem: não somar essa tabela para reconstruir o
total. O custo local do preflight não deve ser atribuído à API de tradução.
Os tempos incluem rede, serviços externos, modelos e a carga concorrente da
máquina; **9min06s não é promessa de desempenho por capítulo**.

O tamanho da saída não é o espaço necessário para instalar/operar o produto:
modelos, caches, temporários e paginação do Windows precisam de espaço adicional.

## Condições e limites da medição

- Job `f3de3bca6a8a479aa388b7a7c4fbff63`, run
  `0fd7358a-8c5a-469a-9ee7-f7fef965682d`, checkout local `cda3f902` com alterações
  não publicadas. Não representa validação de um instalador ou release.
- 182 amostras com intervalo nominal de dois segundos. A coleta começou em
  **3min04s de job** e pegou o FLUX e o fim da execução; não cobre a partida
  nem garante que não houve pico maior antes ou entre amostras.
- Escopo de RAM/CPU: runner e descendentes, incluindo Paddle e FLUX. UI,
  supervisor e monitor externo ficam fora. Carga global do sistema inclui todos.
- GPU obtida por contadores Windows WMI de memória por processo/adaptador;
  inventário de capacidade via DXGI. Nenhuma das 182 amostras falhou na coleta
  de GPU. Consultas duraram mediana de 0,11 s e máximo de 0,78 s; a medição
  não foi um benchmark isolado da instrumentação.
- Havia aplicativos pesados abertos. O sistema chegou a **100% de RAM** e
  aproximadamente **11 MiB disponíveis** em uma amostra. Isso limita a validade
  do tempo como benchmark e mostra que hardware instalado não é recurso livre.
- O Paddle foi efetivamente encerrado antes do FLUX neste job. Comparado ao
  job anterior interrompido, os picos observados caíram de 10,18 para 8,40 GiB
  residentes e de 22,21 para 13,69 GiB comprometidos. São execuções diferentes;
  não tratar a diferença como economia garantida para qualquer capítulo.

## Evidência e próximos ensaios

[Métricas agregadas em JSON](reports/data/job_f3de3bca_resources.json) e
[linha do tempo em CSV](reports/data/job_f3de3bca_resources.csv).
Logs e artefatos originais estão em `%LOCALAPPDATA%/Komyst`; os dados de
processos detalhados não foram incluídos na documentação pública.

Antes de anunciar mínimo de RAM/VRAM: repetir com captura desde o início,
máquina sem aplicativos pesados concorrentes, mesma entrada/configuração,
separando FLUX ligado/desligado; depois testar limites menores de hardware.
Não reduzir os gates de qualidade para apresentar um consumo menor.

## Perfis de hardware (`leve`, `equilibrado`, `qualidade`) e medições em 7 fontes (18/11/2026)

> **Estado:** seleção automática/manual de perfil **IMPLEMENTADA** (`komyst/runtime/hardware_profile.py`) e **MEDIDA** nos três perfis na máquina de referência (`AMD Ryzen 5 5600GT`, 31,37 GiB RAM, `AMD Radeon RX 6600` 8 GB, Windows 64 bits).
> **Limite importante (`EXTERNAL_GATE`):** a execução física num notebook fraco real (por exemplo 8 GB de RAM com GPU integrada, a partir do executável Windows compilado) **ainda não foi realizada**; os requisitos mínimos abaixo são **ESTIMADOS / NÃO HOMOLOGADOS** em hardware de entrada, baseados no consumo real medido da árvore do pipeline sob `HARDWARE_PROFILE=leve`.

### Os três perfis (`PROFILE_VALUES`)

| Perfil | Escolha automática (`ram_total_gb` / `gpu_vram_gb`) | Defaults aplicados (quando não sobrescritos no ambiente) |
|---|---|---|
| `leve` | RAM < 12 GB, VRAM < 3,5 GB ou medição indisponível | `PIPELINE_PAGE_WORKERS=1`, `OCR_RESIDUAL_SWEEP_MODE=off`, `CLEAN_COMPARE_FILLS=0`, `CLEAN_SURFACE_FILL=0`, `FONT_RASTER_MATCH=0`, `LAMA_MAX_INFER_SIDE=576`, `ADVANCED_ART_INPAINTING=1` |
| `equilibrado` | RAM ≥ 12 GB e VRAM ≥ 3,5 GB | `PIPELINE_PAGE_WORKERS=2`, `OCR_RESIDUAL_SWEEP_MODE=always`, `CLEAN_COMPARE_FILLS=1`, `LAMA_MAX_INFER_SIDE=768`, `ADVANCED_ART_INPAINTING=1` |
| `qualidade` | RAM ≥ 24 GB e VRAM ≥ 7,5 GB | `PIPELINE_PAGE_WORKERS=auto` (limitado por megapixels: ≤ 2 em ≥ 6 MP, 1 em ≥ 10 MP), `OCR_RESIDUAL_SWEEP_MODE=always` (executado apenas quando o idioma de origem é inglês), `CLEAN_COMPARE_FILLS=1`, `LAMA_MAX_INFER_SIDE=896`, `ADVANCED_ART_INPAINTING=1` |

Valores detalhados por variável: [`CONFIGURATION.md`](CONFIGURATION.md). O FLUX (`GENERATIVE_INPAINT_ENABLED`) nunca é ligado por perfil.

### Como o perfil é escolhido

1. `HARDWARE_PROFILE=leve|equilibrado|qualidade` força o perfil manualmente (em `.env` ou `.env.local`, reiniciando o worker).
2. `HARDWARE_PROFILE=auto` (padrão) detecta RAM (`psutil`) e VRAM dedicada (`nvidia-smi`, registro de vídeo Windows de 64 bits `HardwareInformation.qwMemorySize`, ou fallback WMI); sem medição, degrada de forma conservadora para `leve`. Placas de 8 GB reportam ~7,98 GiB e placas de 4 GB reportam ~3,99 GiB, por isso os cortes são `7,5` e `3,5`.
3. Qualquer variável explícita já presente no ambiente ou no `.env` / `.env.local` (por exemplo `PIPELINE_PAGE_WORKERS`) prevalece sobre o default do perfil e é registrada em `overridden_by_env`.

O perfil efetivo e o motivo aparecem no log do job (`HARDWARE_PROFILE ...`) e em `timing_report.json` (`hardware_profile`).

### Medições físicas por fonte, idioma e perfil (18/11/2026 — `Forçar reprocessamento=ON`, sem cache)

Todas as execuções abaixo rodaram de ponta a ponta pelo worker real autenticado (`komyst_backend` / DeepL, modo `Qualidade`, `TRANSLATE_SFX=False`, `Manter arquivos de trabalho=ON`) na máquina de referência. A coluna de VRAM dedicada (`resource_report.json`, contadores Windows PDH `\GPU Adapter Memory(*)\Dedicated Usage`) reflete o uso dedicado total do adaptador durante o job (incluindo desktop/navegador abertos na sessão):

| Fonte | Idioma | Perfil | Job ID | Págs lógicas | Tempo total (pipeline s/ download) | RSS pipeline médio / pico | RSS filhos pico | VRAM adaptador média / pico | Fidelidade semântica / Clean | Classificação |
|---|---|---|---|---:|---:|---:|---:|---:|---|---|
| Naver Webtoon | Coreano (`ko`) | `qualidade` | `e85b4482dfe64e028007ea5b0f319768` | 96 (117 tiras) | **519,6 s** (459,6 s) | 1 749,4 / **3 236,0 MB** | 768,9 MB | 6 729,0 / 7 855,9 MB | 202/202 `semantic_clean`, 0 resíduos | **MEDIDO** |
| WEBTOON | Espanhol (`es`) | `qualidade` | `92166c0cdb5f42b88feae619b3f601d1` | 62 (120 tiras) | **346,4 s** (**295,0 s**) | 1 452,2 / **2 890,2 MB** | 812,1 MB | 5 559,2 / 6 460,5 MB | 86/86 `semantic_clean` (83 renderizados) | **MEDIDO** |
| MangaDex | Japonês (`ja`) | `qualidade` | `db424ecfedb441b297caf8285bf7e881` | 20 (`4093×2894`, 11,85 MP) | **828,8 s** (vs 1 249,3 s base, **-420,5 s**) | 3 161,8 / **5 755,3 MB** (vs 8 170 MB base) | **0,0 MB** | 6 844,2 / 7 484,8 MB | 122/122 `semantic_clean`, 0 rejeitados | **MEDIDO** |
| Comix | Inglês (`en`) | `qualidade` | `7df154c7f6b04011bbe2dbe113660de1` | 20 | **556,7 s** (pré-otimização de gap re-OCR) | 2 070,9 / **3 284,1 MB** | 1 395,2 MB | 6 367,4 / 7 251,6 MB | 141/145 renderizados, 22 SFX preservados | **MEDIDO** |
| Tapas | Inglês (`en`) | `qualidade` | `05d4a3faeb0a41ceb52089284533e46a` | 45 | **276,7 s** (**4min36s**) | 1 578,3 / **2 565,8 MB** | 1 372,4 MB | 5 718,2 / 6 638,2 MB | 42/42 `semantic_clean`, 16 SFX preservados | **MEDIDO** |
| INKR | Inglês (`en`) | `qualidade` | `ac96d2269b5e438ea40ecf5070124b88` | 31 | **682,0 s** (159 balões densos) | 1 522,9 / **2 271,9 MB** | 1 414,7 MB | 6 092,8 / 6 484,3 MB | 154/159 `semantic_clean`, 150 renderizados | **MEDIDO** |
| Vortex Scans | Inglês (`en`) | **`leve`** | `e806d99d4d594de8a8787f167c5ac642` | 21 | **162,2 s** (**2min42s**) | **1 130,7 / 2 060,9 MB** | **0,0 MB** | **5 299,2 / 5 648,4 MB** | 43/45 `semantic_clean`, 42/43 `clean` | **MEDIDO** |

*(Histórico comparativo anterior de 13/11/2026 no capítulo de referência de 65 páginas lógicas sem monitoramento PDH de VRAM: `equilibrado` = 338 s / 2 777 MB RSS; `qualidade` = 308 s / 2 743 MB RSS.)*

### Orientação de hardware para notebooks mais fracos vs. recomendado

| Faixa | Perfil indicado | Especificação orientativa | Estado de validação |
|---|---|---|---|
| **Notebook de entrada / fraco (alvo de teste)** | `HARDWARE_PROFILE=leve` (automático quando RAM < 12 GB ou VRAM dedicada < 3,5 GB) | Windows 10/11 64 bits · CPU x64 4 núcleos / 8 threads · **8 GB de RAM** com SSD (paginação ativa e navegadores pesados fechados; o pipeline mediu **1,13 GB médio / 2,06 GB pico RSS** e **0 MB** de processos filhos de varredura) · GPU integrada DirectX 12 / DirectML ou fallback CPU (mais lento) · ~5 GB livres em disco | **ESTIMADO / `EXTERNAL_GATE`** (falta compilar o `.exe` Windows e medir fisicamente no notebook fraco) |
| **Intermediário** | `HARDWARE_PROFILE=equilibrado` | Windows 10/11 64 bits · CPU 6 núcleos · **12–16 GB de RAM** · GPU dedicada DirectML com **≥ 4 GB de VRAM** (`LAMA_MAX_INFER_SIDE=768`) · ~8 GB livres em disco | **MEDIDO** em software na máquina de referência; **NÃO HOMOLOGADO** em GPU física de 4 GB |
| **Recomendado / Referência** | `HARDWARE_PROFILE=qualidade` (`auto`) | Windows 10/11 64 bits · CPU 6 núcleos / 12 threads · **16–32 GB de RAM** (24+ GB ativa `qualidade` automaticamente) · GPU dedicada DirectML com **≥ 8 GB de VRAM** (`LAMA_MAX_INFER_SIDE=896`) · ~10 GB livres em disco | **MEDIDO / `PHYSICALLY_VERIFIED`** em 32 GB RAM + RX 6600 8 GB |

- **Para testar em um notebook mais fraco:** garanta `HARDWARE_PROFILE=auto` (que seleciona `leve` automaticamente abaixo de 12 GB de RAM ou 3,5 GB de VRAM dedicada) ou fixe `HARDWARE_PROFILE=leve` e remova overrides manuais como `PIPELINE_PAGE_WORKERS=2` no `.env` para que `PIPELINE_PAGE_WORKERS=1` entre em vigor (no job `e806d99d`, o `.env` local da máquina de desenvolvimento continha `PIPELINE_PAGE_WORKERS=2`, registrado em `overridden_by_env`; com `PIPELINE_PAGE_WORKERS=1`, o pico de RSS tende a ser ainda menor).
