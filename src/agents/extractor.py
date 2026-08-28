"""
Agent 3 — Ground Truth Extractor (SKELETON / Paper 2 infrastructure)
=====================================================================

Status: SKELETON — depends on Fetcher being implemented first.

Purpose
-------
Given a paper's PDF, use a layered extraction pipeline to produce
structured ground-truth fields (method_family, main_coefficient,
standard_error, etc.) with per-field source attribution and confidence.

This replaces v10/v11's current approach, which feeds GPT-4o only the
paper's title + author + year + direction, and asks it to invent
`main_effect: "β = -0.23"`. That value is NOT in the paper's text.

Extraction strategy (two phases)
---------------------------------
  Phase 1 — Structural parsing (no LLM)
    * PyMuPDF / pdfplumber to extract:
        - Sectioned text (abstract, introduction, data, method, results)
        - Tables with headers/rows
        - References

  Phase 2 — Targeted LLM queries (Claude Opus, temperature=0, JSON mode)
    * Q1: method_family classification (from abstract + section 1)
    * Q2: main table identification (which table has the key coefficient?)
    * Q3: coefficient extraction (from the identified table)
    * Q4: data sources list (from data section)

Output format
-------------
Each extracted field gets:
    value:             the extracted datum
    source:            'abstract' | 'table' | 'section' | 'inferred'
    source_detail:     specific reference (e.g., "Table 3, Column 2")
    confidence:        'high' | 'medium' | 'low'
    evidence_text:     verbatim snippet supporting the extraction

Quality gates
-------------
  - method_family confidence must be ≥ 'medium' or flag for human review
  - main_coefficient must have source='table' (not 'inferred') or flag
  - coefficient value must be in plausible range (|β| < 5 typically)

Not yet implemented
-------------------
  * PDF parsing (needs PyMuPDF / pdfplumber + table extraction)
  * LLM query orchestration with JSON-mode structured output
  * Table structure detection heuristics
  * Evidence-snippet alignment

Reason for delaying
-------------------
Extractor depends on Fetcher (needs PDFs), and robust PDF table
extraction is itself a multi-week project. Left for Paper 2.

What IS in this file: the schema and interface. If Fetcher+PDF-parsing
were implemented, this file's extract() function could be filled in
incrementally.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Literal


# ── Schema: every extracted field carries provenance ──────────────

@dataclass
class ExtractedField:
    """An extracted datum with source attribution."""
    value: object
    source: Literal['abstract', 'section', 'table', 'references',
                    'inferred_from_abstract', 'inferred_from_context']
    source_detail: str        # e.g., "Table 3, Column 2" or "Abstract, sentence 2"
    confidence: Literal['high', 'medium', 'low']
    evidence_text: str        # verbatim quote for verification
    extraction_method: str    # 'regex', 'llm_structured', 'llm_classify'


@dataclass
class ExtractedPaperGroundTruth:
    """Per-paper extracted ground truth; each field independent."""
    paper_id: str
    extraction_status: Literal['complete', 'partial', 'failed']

    method_family: Optional[ExtractedField] = None
    main_coefficient: Optional[ExtractedField] = None
    main_coefficient_se: Optional[ExtractedField] = None
    direction: Optional[ExtractedField] = None
    identification_strategy_description: Optional[ExtractedField] = None
    sample_period: Optional[ExtractedField] = None
    data_sources: Optional[ExtractedField] = None
    key_robustness_checks: Optional[ExtractedField] = None

    extraction_errors: list = field(default_factory=list)
    pdf_sha256: Optional[str] = None
    extracted_at: Optional[str] = None


# ── Main extraction function (stub) ───────────────────────────────

async def extract_from_pdf(pdf_bytes: bytes, paper_id: str,
                            metadata_hint: dict) -> ExtractedPaperGroundTruth:
    """Extract structured ground truth from a paper PDF.

    Currently stubbed. Real implementation would:

    1. Parse PDF with pdfplumber:
        sections = parse_sections(pdf_bytes)
        tables = parse_tables(pdf_bytes)

    2. Classify method family from abstract+intro:
        method = await llm_classify(
            text=sections['abstract'] + sections['introduction'][:2000],
            schema=MethodFamilyEnum,
            model='claude-opus-4-7',
            temperature=0
        )

    3. Identify main regression table:
        main_table = identify_main_table(tables, method.value)
        # Heuristics: table with 'treatment', 'DID', etc. in headers

    4. Extract coefficient from table (JSON-mode LLM):
        coef_extract = await llm_extract_structured(
            prompt=f"Here is Table {main_table.number}:\\n{main_table.to_markdown()}\\n"
                   f"Find the main treatment effect coefficient...",
            schema=CoefficientExtraction,
            model='claude-opus-4-7',
            temperature=0
        )

    5. Return ExtractedPaperGroundTruth with provenance.
    """
    raise NotImplementedError("Extractor is a skeleton; implement PDF parsing first")


def main():
    print("Extractor agent: SKELETON — see header for implementation plan.")
    print("")
    print("Depends on:")
    print("  - Fetcher (Agent 2) to obtain PDFs")
    print("  - PDF parsing library (PyMuPDF or pdfplumber)")
    print("  - LLM structured-output API (Claude Opus JSON mode)")
    print("")
    print("Schema defined: ExtractedPaperGroundTruth")
    print("Every field carries (value, source, source_detail, confidence, evidence_text)")
    print("")
    print("Left for Paper 2 timeline (2-3 weeks of focused work).")


if __name__ == "__main__":
    main()
