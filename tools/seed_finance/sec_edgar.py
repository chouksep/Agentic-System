"""SEC EDGAR HTTP client (Company Facts + Submissions + ticker master list).

Rate-limited to 8 req/s and uses a distinctive User-Agent per SEC guidance.
"""
from __future__ import annotations
