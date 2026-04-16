# ci-wiki — Competitive Intelligence Wiki

> An agentic knowledge base that ingests raw sources and compiles them into a structured, auditable wiki — powered by Claude via Databricks.

Inspired by [Andrej Karpathy's LLM Wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f): instead of searching documents at query time (RAG), a Claude agent reads your raw sources once and writes structured Markdown wiki pages. The compiled knowledge is human-readable, version-controlled, and queryable without re-reading raw sources.

---

## What It Does

ci-wiki acts as an always-on competitive intelligence analyst. You feed it sources — earnings call transcripts, blog posts, product announcements, SEC filings, research papers — and it compiles them into a structured wiki. Each page is a living document, updated incrementally as new sources arrive.

```
sources/                         wiki/
  earnings_q4.pdf   →  agent  →    companies/openai.md
  blog_post.html              →    products/gpt-4o.md
  techcrunch.com              →    people/sam-altman.md
  arxiv_paper.md              →    trends/llm-commoditization.md
                              →    index.md
```

When you ask a question, the agent reads from pre-compiled wiki pages — not raw source chunks. Answers are fast, traceable, and consistent across questions.

---

## Architecture

```
raw sources (URLs, PDFs, Markdown files)
        │
        ▼
  [ python main.py ingest ]
        │
        ▼
  ┌────────────────────────────────────────────┐
  │  LLM Agent (Claude Sonnet 4.6 / Databricks) │
  │                                            │
  │  Tools:  search_wiki   → find existing pages
  │          read_wiki_page → get current content
  │          write_wiki_page → upsert compiled page
  │          list_wiki_pages → verify output
  │                                            │
  │  Schema: schema/wiki_schema.md             │
  │  (entity types, templates, update rules)   │
  └────────────────────────────────────────────┘
        │
        ├──► wiki/companies/    openai.md · anthropic.md · google-deepmind.md
        ├──► wiki/products/     gpt-4o.md · claude.md · gemini.md
        ├──► wiki/people/       sam-altman.md · dario-amodei.md · demis-hassabis.md
        ├──► wiki/trends/       generative-ai-rise.md · reasoning-models.md
        └──► wiki/index.md      (auto-generated, cross-references resolved)

  [ python main.py query "..." ] ──BM25──► wiki pages ──► synthesised answer
```

**Entity types**: `company` · `product` · `person` · `trend` — each with a typed frontmatter schema enforced by the agent's operating instructions.

**Cross-references**: pages link each other with `[[company:openai]]`, `[[person:sam-altman]]` syntax; `python main.py index` resolves these to relative Markdown links.

**Conflict handling**: the agent never deletes existing content. Outdated claims are marked `[STALE as of YYYY-MM-DD]`; contradictions between sources are flagged inline as `[CONFLICT]`.

**Confidence scoring**: factual sections (pricing, funding) carry `<!-- confidence: high|medium|low | source_count: N -->` annotations.

**Source tracking**: every fact is traceable — each wiki page's frontmatter lists the source URIs that contributed to it. The SQLite DB (`data/ci_wiki.db`) records which sources have been ingested, preventing duplicate processing.

---

## Why Not RAG?

| | RAG | ci-wiki |
|---|---|---|
| **When synthesis happens** | At query time (every time) | At ingest time (once per source) |
| **Knowledge format** | Raw text chunks | Structured Markdown pages |
| **Cross-entity synthesis** | Implicit, unreliable | Explicit: pages cross-reference each other |
| **Contradiction handling** | Silently coexists | Flagged inline as `[CONFLICT]` |
| **Auditability** | Which chunks were used? | Open `wiki/companies/openai.md` |
| **Query latency** | High (retrieval + synthesis) | Low (read pre-compiled pages) |
| **Staleness signal** | None | `python main.py lint` flags stale pages |
| **Version control** | Opaque embeddings | Plain Markdown — `git diff` shows changes |

The trade-off: ingesting a new source costs tokens upfront. In return, every query is fast, every answer traces back to a specific wiki page, and the compiled knowledge is human-readable and version-controlled.

---

## Setup

**Requirements**: Python 3.10+

```bash
git clone https://github.com/chouksep/Agentic-System.git
cd Agentic-System
pip install -r requirements.txt
```

### Credentials — choose one backend

**Option A — Anthropic API (simpler for local use)**

Set your API key and ci-wiki will call Claude directly:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

The model defaults to `claude-sonnet-4-5`. Override in `config.yaml` if needed.

**Option B — Databricks Model Serving**

Requires a Databricks workspace with Claude model serving enabled. Configure `~/.databrickscfg`:

```ini
[DEFAULT]
host  = https://<your-workspace>.cloud.databricks.com
token = dapiXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

The Databricks SDK reads this file automatically. Alternatively, set `DATABRICKS_HOST` and `DATABRICKS_TOKEN` environment variables.

See `.env.example` for all available environment variables.

### Optional: `config.yaml`

Place a `config.yaml` at the repo root to override defaults:

```yaml
model: databricks-claude-sonnet-4-6   # default
max_tokens: 8192
max_context_pages: 5                  # pages loaded per query
bm25_top_k: 8                         # candidate pages for retrieval
rate_limit_rpm: 50
rate_limit_tpm: 40000
```

---

## CLI Reference

```bash
# Ingest a single source (URL or local file)
python main.py ingest --source https://techcrunch.com/2025/01/openai-raises/
python main.py ingest --source ./data/q4_earnings_transcript.pdf

# Ingest all pending sources registered in the database
python main.py ingest --all

# Query the compiled wiki
python main.py query "What is OpenAI's current revenue run rate?"
python main.py query "Compare Claude and GPT-4o on pricing" --save   # saves to wiki/queries/

# Quality checks
python main.py lint              # structural + LLM semantic checks
python main.py lint --dry-run    # report issues, no changes
python main.py lint --no-llm     # fast structural checks only

# Housekeeping
python main.py status            # source counts, page counts, last ingest time
python main.py index             # rebuild wiki/index.md with resolved cross-references

# Override model for a single run
python main.py --model claude-opus-4-6 query "Deep-dive on Anthropic's funding history"
```

---

## Example Queries

**Funding & financials**
```bash
python main.py query "Which AI labs have raised over $1B in the last 12 months, and at what valuations?"
python main.py query "What does OpenAI's revenue trajectory suggest about its path to profitability?"
```

**Product & pricing**
```bash
python main.py query "What are the key capability differences between Gemini Ultra, Claude Opus, and GPT-4o?"
python main.py query "Which foundation model providers have cut API prices in the past 6 months, and by how much?"
```

**Leadership & strategy**
```bash
python main.py query "Summarise Sam Altman's public statements on AGI timelines and OpenAI's commercialisation strategy"
python main.py query "How have Dario Amodei's views on AI safety shaped Anthropic's product decisions?"
```

**Market dynamics**
```bash
python main.py query "Which companies are most exposed to commoditisation of foundation models?"
python main.py query "What enterprise verticals are OpenAI, Anthropic, and Cohere competing most directly in?"
python main.py query "Identify any contradictions across tracked sources about GPT-4o's performance on coding benchmarks"
```

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| LLM | Claude Sonnet 4.6 (`databricks-claude-sonnet-4-6`) |
| LLM access | [Databricks SDK](https://github.com/databricks/databricks-sdk-py) — Claude served via Databricks Model Serving |
| Retrieval | BM25 keyword search over compiled wiki pages |
| Source tracking | SQLite (`data/ci_wiki.db`) |
| Page format | Markdown with YAML frontmatter |
| Python | 3.10+ |

---

## Project Structure

```
ci_wiki/
  config.py          Config dataclass — env vars + config.yaml
  db.py              SQLite source registry and ingest log
  llm/
    client.py        Databricks SDK wrapper for Claude
    tools.py         Agent tool definitions (read/write/search wiki)
  ops/
    ingest.py        Ingest pipeline: fetch source → agent → write wiki pages
    query.py         Query pipeline: BM25 retrieval → LLM synthesis
    lint.py          Quality checks: structure + optional semantic LLM pass
  wiki/
    page.py          Read/write wiki pages with frontmatter parsing
    index.py         Rebuild index.md with cross-reference resolution
schema/
  wiki_schema.md     Agent operating instructions: entity types, templates, update rules
sources/             Register raw sources here (URLs + local files)
wiki/                Compiled output: companies/ products/ people/ trends/ index.md
data/
  ci_wiki.db         SQLite: source registry, ingest log
main.py              CLI entry point
```

---

## GitHub Actions

A `workflow_dispatch` workflow is included at `.github/workflows/` for running ingest and query operations from the Actions UI — useful for scheduled ingestion pipelines or headless CI environments (see also the `Makefile` for convenience targets).

---

## Credits

Inspired by [Andrej Karpathy's LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) — the idea that an LLM agent should pre-compile knowledge into a structured, human-readable wiki rather than doing retrieval at query time.

---

## Security

- **Credentials**: ci-wiki reads Databricks credentials from `~/.databrickscfg` or the `DATABRICKS_HOST` / `DATABRICKS_TOKEN` environment variables. Never commit secrets to git — `.env` and `config.yaml` are listed in `.gitignore`.
- **URL ingestion**: Only ingest URLs from trusted sources. The fetcher blocks private, loopback, link-local, and reserved IP ranges at DNS-resolution time to mitigate SSRF. No domain allowlist is enforced beyond that.
- **Wiki content**: Pages are stored as plain Markdown in `wiki/`. If the wiki contains sensitive competitive intelligence, keep the repository **private**.
- **Reporting vulnerabilities**: See [SECURITY.md](SECURITY.md) — please do not open a public issue for security concerns.

---

## License

MIT — see [LICENSE](LICENSE).
