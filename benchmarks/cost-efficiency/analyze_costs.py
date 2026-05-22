"""Cost efficiency analysis for ci-wiki operations."""

import re
import json
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional
from datetime import datetime


@dataclass
class OperationCost:
    """Cost metrics for a single operation."""
    operation_type: str  # 'ingest' or 'query'
    date: str
    source: Optional[str]  # URL or file name
    tokens_used: int
    pages_created: int
    pages_updated: int
    errors: int
    duration_seconds: Optional[float] = None

    @property
    def cost_per_page(self) -> float:
        """Cost per page created or updated."""
        total_pages = self.pages_created + self.pages_updated
        if total_pages == 0:
            return 0.0
        return self.tokens_used / total_pages

    @property
    def tokens_per_error(self) -> float:
        """Tokens wasted on errors."""
        if self.errors == 0:
            return 0.0
        return self.tokens_used / self.errors


@dataclass
class CostSummary:
    """Summary of costs across multiple operations."""
    total_tokens: int
    total_operations: int
    average_tokens_per_operation: float
    total_pages_created: int
    total_pages_updated: int
    total_errors: int
    cost_by_operation_type: Dict[str, int]
    tokens_by_operation_type: Dict[str, int]
    error_rate: float


class CostAnalyzer:
    """Analyze costs from ci-wiki operation logs."""

    # Token costs (approximate pricing as of 2026)
    TOKEN_COST_PER_1K = {
        "claude-sonnet": 0.003,  # Input tokens
        "databricks": 0.001,  # Estimated
    }

    def __init__(self, log_file_path: str):
        """Initialize analyzer with log file."""
        self.log_path = Path(log_file_path)
        self.operations: List[OperationCost] = []
        self._parse_log()

    def _parse_log(self):
        """Parse operation log from markdown file."""
        if not self.log_path.exists():
            print(f"Log file not found: {self.log_path}")
            return

        with open(self.log_path) as f:
            content = f.read()

        # Parse entries: split by headers (## TIMESTAMP — TYPE)
        entries = re.split(r"^## ", content, flags=re.MULTILINE)[1:]

        for entry in entries:
            lines = entry.strip().split("\n")
            header = lines[0]  # e.g., "2026-04-14T22:42:24Z — Ingest"

            # Extract date and operation type
            match = re.match(r"(\d{4}-\d{2}-\d{2}T[\d:Z]+)\s*—\s*(Ingest|Query)", header)
            if not match:
                continue

            date_str, op_type = match.groups()
            op_type = op_type.lower()

            # Parse the content lines
            source = None
            tokens = 0
            created = 0
            updated = 0

            for line in lines[1:]:
                if "Tokens used:" in line:
                    tokens_match = re.search(r"(\d+)", line.replace(",", ""))
                    if tokens_match:
                        tokens = int(tokens_match.group(1))
                elif "Source:" in line:
                    source = line.split("Source:")[1].strip()
                elif "Pages created:" in line:
                    # e.g., "Pages created: openai, sam-altman, greg-brockman..."
                    created_str = line.split("Pages created:")[1].split("Pages updated:")[0].strip()
                    created = len([x.strip() for x in created_str.split(",") if x.strip()])
                    if "Pages updated:" in line:
                        updated_str = line.split("Pages updated:")[1].strip()
                        updated = len([x.strip() for x in updated_str.split(",") if x.strip()])
                elif "Pages updated:" in line and "Pages created:" not in line:
                    updated_str = line.split("Pages updated:")[1].strip()
                    updated = len([x.strip() for x in updated_str.split(",") if x.strip()])
                elif "Notes:" in line:
                    source = line.split("Notes:")[1].strip()

            if tokens > 0:  # Only add if we found tokens
                self.operations.append(
                    OperationCost(
                        operation_type=op_type,
                        date=date_str,
                        source=source or f"{op_type}@{date_str}",
                        tokens_used=tokens,
                        pages_created=created,
                        pages_updated=updated,
                        errors=0,
                    )
                )

    def analyze(self) -> CostSummary:
        """Generate cost analysis summary."""
        if not self.operations:
            return CostSummary(
                total_tokens=0,
                total_operations=0,
                average_tokens_per_operation=0,
                total_pages_created=0,
                total_pages_updated=0,
                total_errors=0,
                cost_by_operation_type={},
                tokens_by_operation_type={},
                error_rate=0.0,
            )

        total_tokens = sum(op.tokens_used for op in self.operations)
        total_operations = len(self.operations)
        total_pages_created = sum(op.pages_created for op in self.operations)
        total_pages_updated = sum(op.pages_updated for op in self.operations)
        total_errors = sum(op.errors for op in self.operations)

        cost_by_type = {}
        tokens_by_type = {}
        for op_type in ["ingest", "query"]:
            ops = [op for op in self.operations if op.operation_type == op_type]
            tokens = sum(op.tokens_used for op in ops)
            cost_by_type[op_type] = len(ops)
            tokens_by_type[op_type] = tokens

        error_rate = (
            (total_errors / total_operations * 100)
            if total_operations > 0
            else 0.0
        )

        return CostSummary(
            total_tokens=total_tokens,
            total_operations=total_operations,
            average_tokens_per_operation=(
                total_tokens / total_operations if total_operations > 0 else 0
            ),
            total_pages_created=total_pages_created,
            total_pages_updated=total_pages_updated,
            total_errors=total_errors,
            cost_by_operation_type=cost_by_type,
            tokens_by_operation_type=tokens_by_type,
            error_rate=error_rate,
        )

    def estimate_cost_usd(self, provider: str = "claude-sonnet") -> float:
        """Estimate total cost in USD."""
        if provider not in self.TOKEN_COST_PER_1K:
            raise ValueError(f"Unknown provider: {provider}")

        total_tokens = sum(op.tokens_used for op in self.operations)
        cost_per_token = self.TOKEN_COST_PER_1K[provider] / 1000
        return total_tokens * cost_per_token

    def cost_per_page(self) -> float:
        """Calculate average cost per page created/updated."""
        total_pages = sum(
            op.pages_created + op.pages_updated for op in self.operations
        )
        if total_pages == 0:
            return 0.0
        total_tokens = sum(op.tokens_used for op in self.operations)
        return total_tokens / total_pages

    def cost_per_query(self) -> float:
        """Calculate average cost per query."""
        query_ops = [op for op in self.operations if op.operation_type == "query"]
        if not query_ops:
            return 0.0
        return sum(op.tokens_used for op in query_ops) / len(query_ops)

    def cost_per_ingest(self) -> float:
        """Calculate average cost per ingest operation."""
        ingest_ops = [op for op in self.operations if op.operation_type == "ingest"]
        if not ingest_ops:
            return 0.0
        return sum(op.tokens_used for op in ingest_ops) / len(ingest_ops)

    def generate_report(self, provider: str = "claude-sonnet") -> Dict:
        """Generate a comprehensive cost report."""
        summary = self.analyze()

        return {
            "summary": asdict(summary),
            "costs": {
                "total_tokens": summary.total_tokens,
                "estimated_cost_usd": self.estimate_cost_usd(provider),
                "cost_per_page": self.cost_per_page(),
                "cost_per_query": self.cost_per_query(),
                "cost_per_ingest": self.cost_per_ingest(),
            },
            "efficiency": {
                "pages_per_token": (
                    (summary.total_pages_created + summary.total_pages_updated)
                    / summary.total_tokens
                    if summary.total_tokens > 0
                    else 0
                ),
                "error_rate": summary.error_rate,
            },
            "breakdown": {
                "operations": [asdict(op) for op in self.operations],
            },
        }


def main():
    """Example usage of cost analyzer."""
    log_file = Path(__file__).parent.parent.parent / "wiki" / "log.md"

    if not log_file.exists():
        print(f"Log file not found: {log_file}")
        print("Creating example analysis...")
        analyzer = CostAnalyzer(str(log_file))
    else:
        analyzer = CostAnalyzer(str(log_file))

    report = analyzer.generate_report()

    print("=" * 60)
    print("COST EFFICIENCY ANALYSIS REPORT")
    print("=" * 60)
    print(f"\nTotal Operations: {report['summary']['total_operations']}")
    print(f"Total Tokens: {report['summary']['total_tokens']:,}")
    print(
        f"Estimated Cost (Claude Sonnet): ${report['costs']['estimated_cost_usd']:.4f}"
    )
    print(
        f"\nAverage Cost per Page: {report['costs']['cost_per_page']:.2f} tokens"
    )
    print(f"Average Cost per Query: {report['costs']['cost_per_query']:.2f} tokens")
    print(f"Average Cost per Ingest: {report['costs']['cost_per_ingest']:.2f} tokens")
    print(f"\nPages Created: {report['summary']['total_pages_created']}")
    print(f"Pages Updated: {report['summary']['total_pages_updated']}")
    print(f"Error Rate: {report['summary']['error_rate']:.2f}%")

    # Save report
    report_file = Path(__file__).parent / "report.json"
    with open(report_file, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nReport saved to: {report_file}")


if __name__ == "__main__":
    main()
