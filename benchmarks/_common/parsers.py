"""Utilities for parsing confidence comments from wiki page content."""

import re
from dataclasses import dataclass
from typing import Optional, Dict, List, Tuple


@dataclass
class ConfidenceComment:
    """Represents a confidence comment found in wiki content."""
    confidence_level: str  # high, medium, low
    source_count: Optional[int] = None
    section: Optional[str] = None
    line_number: Optional[int] = None
    raw_text: str = ""

    @property
    def is_valid(self) -> bool:
        """Check if confidence level is valid."""
        return self.confidence_level in ["high", "medium", "low"]


class ConfidenceCommentParser:
    """Parse and validate confidence comments in wiki pages."""

    # Pattern: <!-- confidence: high|medium|low | source_count: N -->
    CONFIDENCE_PATTERN = re.compile(
        r"<!--\s*confidence:\s*(high|medium|low)(?:\s*\|\s*source_count:\s*(\d+))?\s*-->",
        re.IGNORECASE
    )

    @staticmethod
    def extract_confidence_comments(content: str) -> List[ConfidenceComment]:
        """Extract all confidence comments from page content."""
        comments = []

        for line_num, line in enumerate(content.split('\n'), 1):
            matches = ConfidenceCommentParser.CONFIDENCE_PATTERN.finditer(line)
            for match in matches:
                confidence_level = match.group(1).lower()
                source_count = int(match.group(2)) if match.group(2) else None

                comments.append(
                    ConfidenceComment(
                        confidence_level=confidence_level,
                        source_count=source_count,
                        line_number=line_num,
                        raw_text=match.group(0)
                    )
                )

        return comments

    @staticmethod
    def validate_confidence_comments(comments: List[ConfidenceComment]) -> Tuple[bool, List[str]]:
        """Validate a list of confidence comments."""
        errors = []

        for comment in comments:
            if not comment.is_valid:
                errors.append(f"Invalid confidence level: {comment.confidence_level}")

            if comment.source_count is not None:
                if comment.source_count < 0:
                    errors.append(f"Source count cannot be negative: {comment.source_count}")

                # Suggest confidence level based on source count
                if comment.source_count >= 3:
                    suggested = "high"
                elif comment.source_count >= 1:
                    suggested = "medium"
                else:
                    suggested = "low"

                if comment.confidence_level != suggested:
                    errors.append(
                        f"Confidence '{comment.confidence_level}' with {comment.source_count} sources "
                        f"should be '{suggested}' (high: 3+, medium: 1-2, low: 0)"
                    )

        return len(errors) == 0, errors

    @staticmethod
    def extract_section_confidence(content: str, section_name: str) -> Optional[ConfidenceComment]:
        """Extract confidence comment for a specific section."""
        # Find section header
        section_pattern = re.compile(rf"^##\s+{re.escape(section_name)}\s*$", re.MULTILINE)
        section_match = section_pattern.search(content)

        if not section_match:
            return None

        # Look for confidence comment after section header
        section_start = section_match.end()
        # Find next section or end of content
        next_section = re.search(r"^##\s+", content[section_start:], re.MULTILINE)
        section_end = section_start + next_section.start() if next_section else len(content)

        section_content = content[section_start:section_end]
        matches = list(ConfidenceCommentParser.CONFIDENCE_PATTERN.finditer(section_content))

        if matches:
            match = matches[0]  # First confidence comment in section
            return ConfidenceComment(
                confidence_level=match.group(1).lower(),
                source_count=int(match.group(2)) if match.group(2) else None,
                section=section_name,
                raw_text=match.group(0)
            )

        return None

    @staticmethod
    def get_required_sections_confidence(entity_type: str) -> Dict[str, bool]:
        """Get required sections that should have confidence comments for each entity type."""
        required = {
            "company": {
                "Pricing": True,  # Should have confidence comment
                "Funding & Financials": True,
                "Competitive Position": False,
                "Recent Developments": False,
            },
            "product": {
                "Pricing": True,
                "Target Market": False,
                "Competitive Alternatives": False,
                "Recent Developments": False,
            },
            "person": {
                "Public Statements": True,
                "Current Role": False,
                "Previous Roles": False,
            },
            "trend": {
                "Adoption Stage": False,
                "Implications": False,
                "Recent Developments": False,
            },
        }
        return required.get(entity_type, {})

    @staticmethod
    def validate_section_confidence(entity_type: str, content: str) -> Tuple[bool, List[str]]:
        """Validate that critical sections have confidence comments."""
        errors = []
        required_sections = ConfidenceCommentParser.get_required_sections_confidence(entity_type)

        for section_name, is_required in required_sections.items():
            confidence = ConfidenceCommentParser.extract_section_confidence(content, section_name)

            if is_required and not confidence:
                errors.append(f"Section '{section_name}' should have confidence comment")

            if confidence and not confidence.is_valid:
                errors.append(f"Section '{section_name}' has invalid confidence: {confidence.confidence_level}")

        return len(errors) == 0, errors


class SourceListParser:
    """Parse and validate the sources: list in frontmatter."""

    @staticmethod
    def extract_sources(frontmatter_sources: str) -> List[str]:
        """Extract sources from frontmatter list.

        Expected format:
        sources:
        - "https://example.com/1"
        - "https://example.com/2"
        """
        if not frontmatter_sources or frontmatter_sources.strip() == "null":
            return []

        # Handle various list formats
        sources = []
        for line in frontmatter_sources.split('\n'):
            line = line.strip()
            if line.startswith('-'):
                # Remove leading dash and quotes
                source = line[1:].strip().strip('"\'')
                if source:
                    sources.append(source)

        return sources

    @staticmethod
    def validate_sources(sources: List[str]) -> Tuple[bool, List[str]]:
        """Validate source list."""
        errors = []

        # Check for duplicates
        seen = set()
        for source in sources:
            if source in seen:
                errors.append(f"Duplicate source: {source}")
            seen.add(source)

        # Check for valid URLs
        url_pattern = re.compile(r'^https?://')
        for source in sources:
            if not url_pattern.match(source):
                errors.append(f"Invalid URL format: {source}")

        # Check for minimum sources in high-confidence claims
        # (This would need context from the page's confidence comments)

        return len(errors) == 0, errors


class CrossReferenceParser:
    """Parse and validate cross-references in wiki content."""

    # Pattern: [[type:slug]]
    CROSSREF_PATTERN = re.compile(r"\[\[([a-z]+):([a-z0-9-]+)\]\]")

    @dataclass
    class CrossReference:
        """Represents a cross-reference in wiki content."""
        ref_type: str  # company, product, person, trend
        ref_slug: str
        line_number: Optional[int] = None
        is_valid: bool = True

    @staticmethod
    def extract_references(content: str) -> List['CrossReferenceParser.CrossReference']:
        """Extract all cross-references from content."""
        references = []

        for line_num, line in enumerate(content.split('\n'), 1):
            matches = CrossReferenceParser.CROSSREF_PATTERN.finditer(line)
            for match in matches:
                ref_type = match.group(1)
                ref_slug = match.group(2)

                is_valid = ref_type in ["company", "product", "person", "trend"]

                references.append(
                    CrossReferenceParser.CrossReference(
                        ref_type=ref_type,
                        ref_slug=ref_slug,
                        line_number=line_num,
                        is_valid=is_valid
                    )
                )

        return references

    @staticmethod
    def validate_reference_syntax(references: List['CrossReferenceParser.CrossReference']) -> Tuple[bool, List[str]]:
        """Validate cross-reference syntax and types."""
        errors = []

        for ref in references:
            if not ref.is_valid:
                errors.append(
                    f"Invalid cross-reference type '{ref.ref_type}' at line {ref.line_number}. "
                    f"Must be one of: company, product, person, trend"
                )

            # Check slug format (kebab-case)
            if not re.match(r"^[a-z0-9-]+$", ref.ref_slug):
                errors.append(
                    f"Invalid slug format '{ref.ref_slug}' at line {ref.line_number}. "
                    f"Must be lowercase with hyphens only."
                )

        return len(errors) == 0, errors

    @staticmethod
    def detect_duplicates(references: List['CrossReferenceParser.CrossReference']) -> List[str]:
        """Detect duplicate cross-references."""
        seen = {}
        duplicates = []

        for ref in references:
            key = f"{ref.ref_type}:{ref.ref_slug}"
            if key in seen:
                duplicates.append(
                    f"Duplicate reference to {key} (first at line {seen[key]}, also at line {ref.line_number})"
                )
            else:
                seen[key] = ref.line_number

        return duplicates
