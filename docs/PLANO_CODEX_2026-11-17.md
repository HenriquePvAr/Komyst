# Plano de execução para o Codex — até o Claude voltar

Base: `dev` = `main` = `f2eb40a`. Leia este arquivo inteiro antes de começar. Faça as tarefas
**na ordem**, uma por vez. Terminou uma → relatório → próxima.

---

## 0. Regras — valem para TODAS as tarefas

**Se você quebrar uma regra destas, a tarefa está errada, mesmo com testes passando.**

1. **Proibido editar `komyst/ocr/ocr_balloon.py`.** Nenhuma linha. Nem limite, nem comentário.
2. **Proibido mudar qualquer número de limite/threshold** em qualquer arquivo.
3. **Proibido apagar** qualquer coisa em `C:\Users\henri\Komyst\output\` ou `C:\Users\henri\Komyst\runtime\`.
4. **Proibido `git push`.** Commit só local, no `dev`. O Claude revisa e sobe depois.
5. **Proibido `Co-Authored-By`** em commit.
6. **Proibido ler `.env` / `.env.local`.** Proibido escrever chave, token, senha ou cookie em qualquer lugar.
7. **Proibido rodar tradução paga** (iniciar capítulo no app). As tarefas abaixo não precisam disso.
8. **Proibido lista de palavras, nomes de séries, nomes de sites fixos em regra de OCR/limpeza** ("nada hardcoded").
9. Testes: `python -m pytest -q -p no:cacheprovider <arquivo>`. Nunca rode duas suítes ao mesmo tempo.
10. **Na dúvida, pare e escreva a dúvida no relatório.** Não invente solução.

Relatório de cada tarefa (no chat, curto):
```
TAREFA: <n>
FEITO: <o que mudou, arquivos>
PROVA: <comando rodado + resultado; caminho de imagem/arquivo de evidência>
NÃO FEITO / DÚVIDAS: <...>
COMMIT LOCAL: <sha ou "nenhum">
```

---

## Tarefa 1 — Medir OCR em espanhol (SÓ MEDIR, sem mudar código)

**Objetivo:** descobrir se o PP-OCRv6 tiny lê espanhol melhor/mais rápido que o modelo padrão.

1. Crie a pasta `C:\Users\henri\Komyst\codex_eval\` (fora do repositório).
2. Imagens de teste: use as da pasta `C:\Users\henri\AppData\Local\Temp\claude\f85c4ed4952032d5\a1bb5bb1-bdcd-476f-99b6-9de5e761b13e\scratchpad\dl_wt_es\` (capítulo da WEBTOON em espanhol já baixado). **Se a pasta não existir, PARE a tarefa 1** e diga isso no relatório.
3. Escreva um script em `codex_eval\es_cmp.py` que, para cada imagem:
   - roda o modelo padrão: `from rapidocr_onnxruntime import RapidOCR; RapidOCR()(img, use_cls=False)`;
   - roda o v6 tiny: `from komyst.ocr import rapidocr_profiles as rp; rp.RapidOCRProfileEngine(rp.profile_for("en", "ppocrv6_tiny"), use_dml=False)(img)`;
   - mede o tempo de cada um e guarda os textos lidos.
4. Gere `codex_eval\es_resultado.md` com: tempo total de cada modelo, nº de palavras, e uma tabela com 10 frases lado a lado (padrão × v6 tiny), marcando acentos (á é í ó ú ñ ¿ ¡) certos/errados.
5. **Não mude nada no repositório.** Sem commit.

**Pronto quando:** `es_resultado.md` existe e responde "qual lê melhor e qual é mais rápido".

---

## Tarefa 2 — Listar erros de espaço do OCR inglês (SÓ LISTAR, sem corrigir)

**Contexto:** o v6 tiny às vezes põe espaço onde não deve (`ANOTHER` → `A NOT HER`).

1. Pasta do run REF-A: `C:\Users\henri\Komyst\output\hero_killer_episode_285\ebb5a33d-6a71-400b-b0be-b8b5c3cdb7a0\`.
2. Leia `progress.json` → `pages[*].debug_data.items[*].clean_text` (só leitura).
3. Para cada texto, encontre sequências de 2–3 tokens curtos que, **juntos**, formam uma palavra inglesa que existe em `komyst.review.region_taxonomy.is_english_word` (ex.: `A NOT HER` → `ANOTHER`).
4. Salve em `C:\Users\henri\Komyst\codex_eval\espacos_ref_a.md`: página, texto original, junção candidata, e se a junção está **certa** ou **errada** (olhe a imagem `smart_input_pages\page_NNN.png` para decidir).
5. Conte quantos casos certos × errados. **Não corrija nada no código.** Sem commit.

**Pronto quando:** a lista existe com a contagem certos × errados.

---

## Tarefa 3 — Fonte GlobalComix (investigar; só implementar se for simples)

**Objetivo:** saber se dá para baixar capítulos **gratuitos** do GlobalComix.

1. Leia como as fontes existentes funcionam: `komyst/download/sources/chapter_source.py` — classes `TapasAdapter` e `InkrAdapter` (linhas ~866–1000) e a tupla `ADAPTERS` (linha ~1598). Testes: `tests/test_new_chapter_sources.py`, `tests/test_sources_tab.py`.
2. Escolha **um** capítulo gratuito público do GlobalComix e veja como as imagens chegam (HTML/JSON público, sem login).
3. **PARE e só relate** se qualquer uma for verdade: precisa de login, imagens criptografadas/embaralhadas, bloqueio anti-bot que exige navegador, termos de uso proibindo download. Relatório: o que encontrou e por quê parou.
4. Se for simples (JSON/HTML público com URLs diretas das imagens):
   - crie `GlobalComixAdapter` seguindo o padrão do `TapasAdapter` (mesmos métodos, `allowed_hosts`/`resource_hosts` só com os domínios do GlobalComix);
   - **só capítulos gratuitos**; capítulo pago → erro claro, nunca tentar contornar;
   - testes **offline** em `tests/test_new_chapter_sources.py` com HTML/JSON de exemplo salvo no teste (sem internet nos testes);
   - **não** adicione à aba Fontes da UI nem ao `ADAPTERS` ainda — o Claude decide;
   - rode `python -m pytest -q -p no:cacheprovider tests/test_new_chapter_sources.py tests/test_sources_tab.py`;
   - commit local: `feat(sources): GlobalComix adapter for free chapters (not wired)`.

**Pronto quando:** ou relatório de "não dá, porque X", ou adapter + testes passando + commit local.

---

## Quando acabar as 3 tarefas

**Pare.** Não pegue outras coisas do `docs/HANDOFF_2026-11-17.md`. Os itens restantes de lá
(limpeza, velocidade, nomes, legendas, SFX) **ficam para o Claude**, porque exigem mexer em
`ocr_balloon.py` e conferir imagem por imagem.
