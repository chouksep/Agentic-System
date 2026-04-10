.DEFAULT_GOAL := help

# ─── Setup ────────────────────────────────────────────────────────────────────

install: ## Install package and dependencies
	pip install -e ".[dev]"

test: ## Run the full test suite
	python -m pytest tests/ -v

# ─── Demo: AI Competitive Intelligence ────────────────────────────────────────

ingest-demo: ## Ingest 3 starter AI company pages (requires ANTHROPIC_API_KEY)
	python main.py ingest --source https://openai.com/api/pricing
	python main.py ingest --source https://www.anthropic.com/pricing
	python main.py ingest --source https://mistral.ai/technology/

query-demo: ## Ask a sample competitive intelligence question
	python main.py query "Compare GPT-4o and Claude pricing. Which is cheaper for high-volume API use?"

# ─── Core Commands ────────────────────────────────────────────────────────────

ingest: ## Ingest a single URL or file: make ingest SOURCE=https://example.com
	python main.py ingest --source $(SOURCE)

ingest-all: ## Ingest all pending sources in the sources/ directory
	python main.py ingest --all

query: ## Ask a question: make query Q="What is OpenAI's pricing?"
	python main.py query "$(Q)"

query-save: ## Ask a question and save the answer to the wiki
	python main.py query "$(Q)" --save

lint: ## Check wiki quality (LLM + static checks)
	python main.py lint

lint-fast: ## Check wiki quality (static checks only, no API calls)
	python main.py lint --dry-run --no-llm

status: ## Show wiki and source statistics
	python main.py status

index: ## Rebuild wiki/index.md
	python main.py index

# ─── Exploration ──────────────────────────────────────────────────────────────

show-wiki: ## Display the current wiki index
	@cat wiki/index.md 2>/dev/null || echo "Wiki is empty. Run 'make ingest-demo' first."

show-log: ## Show the ingest audit log
	@cat wiki/log.md 2>/dev/null || echo "No log yet."

show-companies: ## List all company pages
	@ls wiki/companies/*.md 2>/dev/null | xargs -I{} basename {} .md || echo "No companies yet."

show-products: ## List all product pages
	@ls wiki/products/*.md 2>/dev/null | xargs -I{} basename {} .md || echo "No products yet."

# ─── Maintenance ──────────────────────────────────────────────────────────────

clean-wiki: ## Remove all generated wiki pages (IRREVERSIBLE)
	@echo "This will delete all wiki pages. Press Ctrl+C to cancel, Enter to continue."
	@read _
	rm -f wiki/companies/*.md wiki/products/*.md wiki/people/*.md wiki/trends/*.md
	rm -f wiki/index.md wiki/log.md
	rm -f data/ci_wiki.db
	@echo "Wiki cleared."

# ─── Help ─────────────────────────────────────────────────────────────────────

help: ## Show this help message
	@echo ""
	@echo "ci-wiki — Competitive Intelligence Wiki"
	@echo ""
	@echo "Usage: make <target>"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Examples:"
	@echo "  make ingest SOURCE=https://openai.com/api/pricing"
	@echo "  make query Q=\"What is Anthropic's pricing for Claude?\""
	@echo ""

.PHONY: install test ingest-demo query-demo ingest ingest-all query query-save \
        lint lint-fast status index show-wiki show-log show-companies show-products \
        clean-wiki help
