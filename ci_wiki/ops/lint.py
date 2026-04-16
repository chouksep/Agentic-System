"""Lint operation: static checks + LLM semantic checks for wiki quality."""
from __future__ import annotations

from datetime import datetime, timedelta, UTC

from ci_wiki.config import Config
from ci_wiki.db import Database
from ci_wiki.llm.client import LLMClient
from ci_wiki.llm.prompts import build_lint_system_prompt, build_lint_user_prompt, load_schema
from ci_wiki.llm.tools import LINT_TOOLS, ToolDispatcher
from ci_wiki.models import LintIssue, LogEntry
from ci_wiki.wiki.index import WikiIndex
from ci_wiki.wiki.page import WikiPageIO
from ci_wiki.wiki.search import WikiSearch

_REQUIRED_COMPANY_SECTIONS = ["## Pricing", "## Funding", "## Competitive Position"]
_STALE_DAYS = 90
_LLM_BATCH_SIZE = 4


class LintOp:
    def __init__(
        self,
        config: Config,
        db: Database,
        llm: LLMClient,
        page_io: WikiPageIO,
        index: WikiIndex,
    ) -> None:
        self._config = config
        self._db = db
        self._llm = llm
        self._page_io = page_io
        self._index = index

    def run(self, dry_run: bool = False, llm_check: bool = True) -> list[LintIssue]:
        """Run all lint checks. Returns list of issues found."""
        issues: list[LintIssue] = []

        print("Phase 1: Static checks...")
        issues += self._find_broken_xrefs()
        issues += self._find_stale_pages()
        issues += self._find_orphaned_pages()
        issues += self._find_missing_sections()

        if llm_check:
            print("Phase 2: LLM semantic checks...")
            issues += self._run_llm_lint(dry_run=dry_run)

        self._print_report(issues)

        if not dry_run:
            self._index.append_log(
                LogEntry(
                    operation="Lint",
                    timestamp=datetime.now(UTC).replace(tzinfo=None),
                    notes=f"{len(issues)} issues found",
                )
            )
            self._index.rebuild()

        return issues

    def _find_broken_xrefs(self) -> list[LintIssue]:
        broken = self._index.find_broken_xrefs()
        return [
            LintIssue(
                severity="error",
                page_slug=page_slug,
                issue_type="missing_xref",
                description=f"Broken cross-reference: {ref}",
            )
            for page_slug, ref in broken
        ]

    def _find_stale_pages(self) -> list[LintIssue]:
        issues = []
        cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=_STALE_DAYS)
        for page in self._page_io.read_all():
            if page.last_updated and page.last_updated < cutoff:
                age_days = (datetime.now(UTC).replace(tzinfo=None) - page.last_updated).days
                issues.append(
                    LintIssue(
                        severity="warning",
                        page_slug=page.slug,
                        issue_type="stale",
                        description=f"Page not updated in {age_days} days (last: {page.last_updated.date()})",
                    )
                )
        return issues

    def _find_orphaned_pages(self) -> list[LintIssue]:
        """Find pages on disk not tracked in the DB."""
        issues = []
        db_slugs = set(self._db.get_all_slugs())
        for page in self._page_io.read_all():
            if page.slug not in db_slugs:
                issues.append(
                    LintIssue(
                        severity="info",
                        page_slug=page.slug,
                        issue_type="orphan",
                        description="Page exists on disk but is not tracked in the database",
                    )
                )
        return issues

    def _find_missing_sections(self) -> list[LintIssue]:
        issues = []
        for page in self._page_io.read_all("company"):
            for section in _REQUIRED_COMPANY_SECTIONS:
                if section not in page.body:
                    issues.append(
                        LintIssue(
                            severity="warning",
                            page_slug=page.slug,
                            issue_type="missing_section",
                            description=f"Company page missing required section: {section}",
                        )
                    )
        return issues

    def _run_llm_lint(self, dry_run: bool = False) -> list[LintIssue]:
        issues: list[LintIssue] = []
        schema = load_schema(self._config.schema_file)
        system = build_lint_system_prompt(schema)

        # Group pages into batches by company (company + its products + its people)
        all_pages = self._page_io.read_all()
        company_pages = [p for p in all_pages if p.page_type == "company"]
        other_pages = [p for p in all_pages if p.page_type != "company"]

        batches: list[list[dict]] = []

        for company in company_pages:
            batch = [{"slug": company.slug, "page_type": "company", "content": company.body}]
            company_slug = company.slug
            # Add related products and people
            for page in other_pages:
                related = (
                    page.frontmatter.get("company") == company_slug
                    or company_slug in page.body
                )
                if related and len(batch) < _LLM_BATCH_SIZE:
                    batch.append({"slug": page.slug, "page_type": page.page_type, "content": page.body})
            batches.append(batch)

        # Remaining pages not associated with any company
        covered = {item["slug"] for b in batches for item in b}
        remaining = [
            {"slug": p.slug, "page_type": p.page_type, "content": p.body}
            for p in other_pages
            if p.slug not in covered
        ]
        for i in range(0, len(remaining), _LLM_BATCH_SIZE):
            batches.append(remaining[i : i + _LLM_BATCH_SIZE])

        for batch in batches:
            if not batch:
                continue
            batch_issues = self._lint_batch(system, batch, dry_run)
            issues.extend(batch_issues)

        return issues

    def _lint_batch(
        self, system: str, page_contents: list[dict], dry_run: bool
    ) -> list[LintIssue]:
        user_msg = build_lint_user_prompt(page_contents)

        pages = self._page_io.read_all()
        search = WikiSearch(pages)
        search.build_index()

        dispatcher = ToolDispatcher(self._page_io, search)
        _, tokens = self._llm.complete_with_tools(
            system=system,
            initial_user_message=user_msg,
            tools=LINT_TOOLS,
            dispatcher=dispatcher,
            use_thinking=True,
        )

        issues = []
        for c in dispatcher.contradictions:
            issues.append(
                LintIssue(
                    severity="error",
                    page_slug=c["page_a"],
                    issue_type="contradiction",
                    description=(
                        f"Contradiction with [[{c['page_b']}]]: {c['description']}"
                    ),
                    auto_fixed=False,
                )
            )

        return issues

    def _print_report(self, issues: list[LintIssue]) -> None:
        if not issues:
            print("Lint passed: no issues found.")
            return

        by_severity = {"error": [], "warning": [], "info": []}
        for issue in issues:
            by_severity.get(issue.severity, by_severity["info"]).append(issue)

        print(f"\nLint Report: {len(issues)} issue(s) found")
        print(f"  ERRORS   ({len(by_severity['error'])})")
        for i in by_severity["error"]:
            print(f"    [{i.issue_type}] {i.page_slug}: {i.description}")
        print(f"  WARNINGS ({len(by_severity['warning'])})")
        for i in by_severity["warning"]:
            print(f"    [{i.issue_type}] {i.page_slug}: {i.description}")
        print(f"  INFO     ({len(by_severity['info'])})")
        for i in by_severity["info"]:
            print(f"    [{i.issue_type}] {i.page_slug}: {i.description}")
