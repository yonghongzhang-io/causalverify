"""
Agent 4 — Cross-Source Validator (SKELETON / Paper 2 infrastructure)
=====================================================================

Status: SKELETON — depends on Extractor being implemented first.

Purpose
-------
When extracting ground truth, any single source can be wrong. This agent
cross-checks extracted fields against independent sources to produce
a confidence-adjusted, reconciled ground truth.

Triangulation sources
---------------------
For each field, check consistency across:
  (1) PDF extraction (Agent 3 output) — primary
  (2) OpenAlex metadata               — secondary (for year/authors/venue)
  (3) CrossRef record                 — tertiary (authoritative DOI)
  (4) Existing v10/v11 JSON           — control (what was there before?)
  (5) Manual annotation (if present)  — ground truth override

Validation rules
----------------
  method_family:
    - PDF says 'DID', OpenAlex keywords include 'difference-in-differences' → consistent
    - PDF says 'DID', existing v11 JSON says 'IV' → CONFLICT, flag for human review

  main_coefficient:
    - PDF extract says β=-0.357 (from Table 3)
    - Existing v11 says main_effect 'β = -0.23' (GPT-4o-inferred)
    - PDF value has explicit source=table → trust PDF; flag v11 for update

  publication_year, authors, journal:
    - Must match across OpenAlex + CrossRef + PDF title page (within tolerance)

Output
------
  ValidationReport per paper with:
    - per-field consistency score
    - list of conflicts (source_a_value != source_b_value)
    - overall_status: 'validated' | 'needs_review' | 'conflict'
    - recommendations: e.g., 'update v11 main_effect to PDF-extracted value'

Not yet implemented
-------------------
  * Field-by-field comparison logic
  * Conflict resolution heuristics
  * Human-review queue generation

Reason for delaying
-------------------
Validator is meaningful only when Extractor produces real data from PDFs.
Left for Paper 2.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional


@dataclass
class FieldComparison:
    field_name: str
    values_by_source: dict   # {'pdf': ..., 'openalex': ..., 'v11': ...}
    consistent: bool
    best_value: object
    best_source: str
    notes: str = ""


@dataclass
class ValidationReport:
    paper_id: str
    field_comparisons: list = field(default_factory=list)
    n_fields_checked: int = 0
    n_consistent: int = 0
    n_conflicts: int = 0
    overall_status: Literal['validated', 'needs_review', 'conflict'] = 'needs_review'
    recommendations: list = field(default_factory=list)


# ── Comparison helpers ─────────────────────────────────────────────

def compare_method_family(sources: dict) -> FieldComparison:
    """Compare method_family across sources.

    sources: {'pdf': 'DID', 'openalex_keywords': ['difference-in-differences', ...], 'v11': 'DID'}
    """
    # TODO: implement
    pass


def compare_main_coefficient(sources: dict) -> FieldComparison:
    """Compare coefficient values; flag GPT-4o-inferred vs. PDF-extracted."""
    # TODO: implement
    pass


def compare_metadata(sources: dict, field_name: str) -> FieldComparison:
    """Generic metadata comparison: year, authors, journal, etc."""
    # TODO: implement
    pass


# ── Main validation function ───────────────────────────────────────

async def validate_paper(paper_id: str,
                          pdf_extracted,     # ExtractedPaperGroundTruth
                          openalex_meta,     # dict
                          crossref_meta,     # dict
                          existing_v11) -> ValidationReport:
    """Produce a validation report with per-field consistency checks.

    Real implementation would:

    1. For each field in ExtractedPaperGroundTruth:
        - Gather values from all available sources
        - Call the appropriate comparator
        - Record the comparison

    2. Aggregate:
        - If all fields consistent (or only minor differences):
            overall_status = 'validated'
        - If ≥1 field has major conflict:
            overall_status = 'conflict'
            add recommendation to reconcile

    3. Generate recommendations:
        - "Update v11 JSON main_effect from 'β = -0.23' to '−0.357' (source: Table 3)"
        - "Verify author list: v11 has 'Ivashina & Scharfstein' but OpenAlex shows ..."
    """
    raise NotImplementedError("Validator is a skeleton; implement Extractor first")


def main():
    print("Validator agent: SKELETON.")
    print("")
    print("Depends on Extractor output + OpenAlex + CrossRef data.")
    print("")
    print("Key outputs:")
    print("  - Per-field consistency scores across 3-5 sources")
    print("  - Conflict flag when PDF disagrees with existing JSON")
    print("  - Recommendations for ground-truth updates")
    print("")
    print("Left for Paper 2 timeline.")


if __name__ == "__main__":
    main()
