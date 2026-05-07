# 🛠️ Guia de Instalação — Skill `fact-check`

> **Tempo total:** ~5 minutos
> **Pré-requisito:** Python 3.9+ instalado (rode `python3 --version` para conferir)

---

## 📋 Visão geral em 3 passos

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  1. INSTALAR    │ ──▶ │  2. TESTAR      │ ──▶ │  3. USAR        │
│  dependências   │     │  smoke test     │     │  no Claude Code │
│  (~2 min)       │     │  (~30 seg)      │     │  (qualquer hora)│
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

A skill já está em `~/.claude/skills/fact-check/` — só falta instalar as dependências Python.

---

## 1️⃣ Instalar dependências Python

Abra o terminal e rode:

```bash
pip install -r ~/.claude/skills/fact-check/requirements.txt
```

✅ **Pronto.** Isso instala 5 pacotes:
- `python-docx` → ler arquivos Word
- `python-pptx` → ler PowerPoint
- `pdfplumber` → ler PDF (texto)
- `pytesseract` + `pdf2image` → OCR para PDFs digitalizados

> **💡 Dica:** se você usa `pip3` em vez de `pip`, troque o comando: `pip3 install -r ...`

---

## 2️⃣ (Opcional) Instalar OCR para PDFs digitalizados

**Pule este passo** se você só vai testar com `.docx`, `.pptx` ou PDFs nativos (não digitalizados).

Instale só se for auditar PDFs escaneados (imagem, sem texto extraível):

### macOS
```bash
brew install tesseract poppler
```

### Linux (Debian/Ubuntu)
```bash
sudo apt install tesseract-ocr poppler-utils
```

### Windows
Baixe o instalador em [https://github.com/UB-Mannheim/tesseract/wiki](https://github.com/UB-Mannheim/tesseract/wiki) e adicione ao PATH.

---

## 3️⃣ Teste rápido (smoke test)

Cole esse comando no terminal — ele usa o fixture já incluído:

```bash
python3 ~/.claude/skills/fact-check/scripts/extract_claims.py \
  ~/.claude/skills/fact-check/fixtures/sample-ingest.json
```

### ✅ Resultado esperado

Você deve ver um JSON com **5 candidates** identificados — algo como:

```
{
  "source": "fixtures/sample-deck.docx",
  "language": "pt",
  "candidates": [
    { "id": "c-001", ..., "declared_source_hint": "IBGE" },
    { "id": "c-002", ..., "declared_source_hint": "SUSEP" },
    { "id": "c-003", ..., "candidate_kind": "date_event" },
    { "id": "c-004", ..., "declared_source_hint": "McKinsey" },
    { "id": "c-005", ..., "candidate_kind": "numeric" }
  ],
  "candidate_count": 5
}
```

Se aparecer isso, **a skill está instalada e funcionando**. 🎉

---

## 4️⃣ Como usar no Claude Code

A skill **dispara automaticamente** quando você pede para verificar um documento. Não precisa de comando especial.

### 📝 Exemplos de prompts que ativam a skill

| O que digitar | O que acontece |
|---|---|
| `Audita esse deck pra mim: ~/Downloads/deck-board.pptx` | Roda fact-check completo |
| `Verifica os números desse memo: /caminho/memo.docx` | Idem |
| `Check the citations in this PDF: ~/strategy.pdf` | Idem (output bilíngue) |
| `Pode dar uma olhada nesse blog? https://exemplo.com/post` | Audita URL |
| `Audita esse deck mas é CONFIDENCIAL — modo offline` | Roda sem busca web |

### 🚫 Prompts que NÃO ativam (corretamente)

- `Resume esse documento em 3 bullets` → é resumo, não auditoria
- `Reescreve esse parágrafo` → é edição
- `Cria um deck novo sobre X` → é criação

---

## 📂 O que você recebe de output

Cada execução gera 2 arquivos em `/tmp/fact-check/`:

- **`report.md`** — relatório bilíngue PT/EN para você ler (sumário, alertas críticos, tabela completa)
- **`report.json`** — mesmo conteúdo em formato estruturado, pra integrar em pipelines

```
┌──────────────────────────────────────┐
│  report.md                           │
│  ────────────────────                │
│  📊 Sumário executivo                 │
│     ✅ Confirmados: 1                 │
│     🔴 Contraditórios: 2  ◀── ATENÇÃO │
│     🔒 Inacessíveis: 1                │
│     ⚫ Não verificáveis: 1             │
│                                      │
│  🚨 Alertas críticos                  │
│     [detalhes dos contraditórios]    │
│                                      │
│  📋 Tabela completa                   │
│     [todos os claims com veredicto]  │
│                                      │
│  📌 Metodologia                       │
└──────────────────────────────────────┘
```

---

## 🧯 Troubleshooting

### `command not found: pip`
Use `pip3` em vez de `pip`. Se não tiver, instale Python 3 primeiro.

### `ModuleNotFoundError: No module named 'docx'`
A instalação não rodou. Re-execute:
```bash
pip3 install -r ~/.claude/skills/fact-check/requirements.txt
```

### `TesseractNotFoundError`
Você está auditando um PDF digitalizado mas não instalou o Tesseract. Veja o passo 2️⃣ acima.

### A skill não dispara quando peço para auditar
Verifique se o prompt contém uma palavra-chave clara: "audita", "verifica", "fact-check", "valida fontes", "double-check". Se ainda assim não disparar, peça explicitamente: `Use a skill fact-check para auditar este documento: <caminho>`.

### O Claude diz que não acha o arquivo
Use **caminho absoluto** (começando com `/` ou `~/`), não relativo. Exemplo: `~/Downloads/deck.pdf`, não `deck.pdf`.

---

## ⚙️ Configuração avançada (opcional)

Se quiser mudar o comportamento padrão, copie o template de config:

```bash
cp ~/.claude/skills/fact-check/config.yaml.example \
   ~/.claude/skills/fact-check/config.yaml
```

Edite `config.yaml` para mudar modo (online/offline), cap de claims, idioma do output, etc. **A maioria dos usuários não precisa disso** — os defaults funcionam.

---

## 🎯 Próximo passo

Pegue um `.docx`, `.pptx`, `.pdf` ou URL real que você queira auditar e digite no Claude Code:

```
Audita esse material: <caminho_do_arquivo>
```

Pronto. Boa auditoria! 🚀
