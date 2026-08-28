# A1 Paper-Native Gold Labeling Protocol

**Project**: CAUSAL-BENCH
**Protocol version**: v1.0
**Owner**: Yonghong Zhang (Universidad Autónoma de Madrid)
**Target**: 80 papers
**Expected duration**: 45–55 annotation hours over 2–3 weeks
**Deliverable**: `audit/human_gold/paper_native_labels.csv`

---

## 1. Purpose and Scope

This protocol governs the construction of the **paper-native gold subset**
used to anchor CAUSAL-BENCH's ground-truth labels. The subset serves
three roles:

1. **Anchor** for validating the 4-LLM majority-vote GT against expert
   judgment on original papers.
2. **Track A** in the dual-track GT design (Track B = current pipeline GT
   based on Phase 1 synthesis).
3. **Validation set** for the L3 rubric introduced in A5 (L3 judge
   requires κ ≥ 0.75 against this subset).

**Out of scope**:
- Contested-case adjudication for the full 261-paper corpus (already
  handled in Phase 2).
- Phase 1 synthesis fidelity rating (separate protocol, see C1).

---

## 2. Sampling Design

### 2.1 Target and Stratification

**Total sample**: 80 papers

**Primary stratification axis**: `method_family × difficulty`

| Method family | Difficulty: Easy | Difficulty: Hard | Row total |
|---|---|---|---|
| DID | 8 | 8 | 16 |
| Event Study | 8 | 8 | 16 |
| IV | 8 | 8 | 16 |
| RDD | 8 | 8 | 16 |
| Other | 8 | 8 | 16 |
| **Column total** | **40** | **40** | **80** |

**Secondary constraint**: `conclusion_direction` is **balanced within
cells** via post-hoc audit, not treated as a full factorial
stratification axis.

Rationale:
- A full 5 × 2 × 4 = 40-cell design at 80 papers would yield 2 per cell,
  statistically underpowered.
- Some `method × direction` combinations (e.g., RDD × mixed) may have
  fewer than 2 papers in the full corpus, making full factorial sampling
  infeasible.
- Direction balance is achievable at the 80-paper level: target ≥ 15
  papers per direction across the subset (audited post-sampling).

### 2.2 Difficulty Definition

Difficulty is operationalized via **Phase 2 consensus level** from
`audit/gt_aggregate_decisions.json`:

| Difficulty tier | Phase 2 consensus pattern | Interpretation |
|---|---|---|
| **Easy** | 4/4 or 3/4 agreement on both method AND direction | Unambiguous papers — useful to confirm pipeline reliability on clear cases |
| **Hard** | 2/2 tie on either axis, OR 2/1/1 with contested outcome, OR required Phase 2 human adjudication | Ambiguous papers — probe pipeline failures |

**Caveat to acknowledge in Methods**:

Difficulty here is measured by LLM-annotator disagreement, not an
independent human measure. This introduces a mild circularity (the
"hard" cases are partly defined by LLMs), but is acceptable because
(a) the labels we assign in this protocol are human-native and blind to
LLM votes, and (b) alternative difficulty proxies (paper length,
citation count) are weaker correlates of label ambiguity.

### 2.3 Sampling Procedure

Implemented in `sample_selection.py`. Key rules:

1. **Random seed fixed**: `SEED = 20260423` — recorded in the Methods
   section for reproducibility.
2. **Eligibility**: Papers where Phase 1 was successful
   (`source_type != "abstract_only"`) AND PDF is available.
3. **Fill order**: Cells with fewer eligible papers sampled first (avoid
   starvation).
4. **Fallback for undersized cells**: If any cell has fewer than 8
   eligible papers, document the shortfall and backfill from the
   nearest-population cell; flag the deviation.
5. **Direction audit**: After initial draw, compute direction
   distribution. If any direction < 15, swap up to 10% of papers from
   over-represented cells with under-represented direction.

### 2.4 Output Files

- `audit/human_gold/sample_manifest.csv` — 80 papers with `paper_id`,
  `difficulty_tier`, `pdf_path`.
- `audit/human_gold/sample_manifest_SEALED.csv` — Phase 2 labels for
  post-hoc comparison only.
- `audit/human_gold/sample_manifest.sha256` — hash for reproducibility
  verification.

**CRITICAL**: The annotator does **NOT** see `method_family_phase2` or
`direction_phase2` during labeling. These fields exist in the sealed
manifest for post-hoc comparison only. Blinding is enforced at the
tooling level (§4.2).

---

## 3. The Rubric

### 3.1 Method Family Signatures

A paper's `method_family` is assigned based on the **primary
identification strategy** used in the main results table. The signatures
below define what "primary identification strategy" means for each
class. These signatures are **shared with the A5 L3 rubric** — any
revision here must propagate to A5.

---

#### DID (Difference-in-Differences)

**Required signatures (all must be present)**:
1. ≥ 2 groups (treated vs control or multiple treated cohorts)
2. ≥ 2 time periods (pre vs post, or event time around staggered
   adoption)
3. Identification clause invoking parallel trends, common trends, or
   two-way fixed effects

**Strong indicators (presence raises confidence)**:
- `(Treated × Post)` interaction term in main regression
- Callaway-Sant'Anna, de Chaisemartin-D'Haultfœuille, Sun-Abraham
  estimators for staggered DID
- Event-study coefficients centered on treatment date (note: see Event
  Study below for boundary)

**Anti-indicators (presence lowers confidence)**:
- No explicit control group or control period
- Only cross-sectional variation

---

#### Event Study

**Required signatures**:
1. A **discrete event** with a sharp date (announcement, policy
   enactment, disaster, earnings release)
2. An **event window** (typically [t−k, t+k]) around that date
3. Outcome measured **per period relative to event** (dynamic
   coefficients or cumulative abnormal returns)

**Strong indicators**:
- "Abnormal returns" / "CARs" / "market model" language
  (finance-specific)
- Dynamic plot with coefficients at each event-time lead/lag
- News/earnings/merger/policy announcement as treatment

**Boundary with DID**:
- If there is a discrete event AND a treated/control split AND
  parallel-trends identification language → code as **DID with
  event-study specification** (primary: DID).
- If the event is applied to ALL units (no untreated control) and
  identification relies on pre-event stability → code as **Event Study**
  (primary: Event Study).

---

#### IV (Instrumental Variables)

**Required signatures**:
1. Explicit **instrument** variable Z, distinct from treatment D.
2. **First-stage** regression of D on Z reported or described.
3. **Exclusion restriction** discussed (Z affects Y only through D).

**Strong indicators**:
- 2SLS / GMM / LIML / Control Function terminology
- F-statistic or weak-instrument diagnostics
- Historical / geographic / lottery / judge-assignment / Bartik-style /
  shift-share instruments

**Anti-indicators**:
- IV mentioned only as robustness check (not primary identification) →
  code as primary method.
- Heckman selection models → code as **Other** unless explicit IV
  framing.

---

#### RDD (Regression Discontinuity)

**Required signatures**:
1. A **running variable** (score, age, date, distance, etc.).
2. A **cutoff/threshold** at which treatment assignment changes.
3. Local **continuity assumption** invoked (potential outcomes
   continuous at cutoff).

**Strong indicators**:
- "Sharp RD" / "Fuzzy RD" terminology
- Bandwidth selection (Imbens-Kalyanaraman,
  Calonico-Cattaneo-Titiunik)
- McCrary density test / manipulation test
- Local polynomial estimation
- Discontinuity plot

**Anti-indicators**:
- Cutoff mentioned but treatment is continuous (use IV or DID).
- "Kink" design without formal RKD framing → code as **Other**.

---

#### Other

**When to use**:
- Cross-sectional OLS with no explicit causal identification (purely
  descriptive / predictive).
- Structural models (IO, industrial organization, dynamic discrete
  choice).
- Matching / synthetic control (if not combined with DID).
- Randomized experiments (rare in this corpus).
- Natural experiments that don't fit the above four families.
- Papers where identification strategy is unclear even after reading
  method section.

**When NOT to use**:
- Do not default to "Other" because the paper is hard to parse. If any
  of the four main families fits on signature match, use that family and
  lower confidence instead.

---

### 3.2 Conclusion Direction

`conclusion_direction` captures the sign of the **main reported
treatment effect** on the **primary outcome of interest**.

| Label | Rule |
|---|---|
| **positive** | Main coefficient is positive AND statistically significant (p < 0.10 threshold in published form) for the primary outcome |
| **negative** | Main coefficient is negative AND statistically significant for the primary outcome |
| **mixed** | (a) Effect sign varies across subgroups or time horizons the authors themselves emphasize, OR (b) main effect has one sign but an equally-emphasized secondary effect has the opposite sign |
| **unclear** | Main effect is statistically insignificant, OR the paper does not report a clear directional claim, OR the sign depends on specification in a way that precludes a single direction |

**Decision rule for ambiguity**:

1. **Read the abstract's final sentence(s) first.** Authors usually
   summarize their directional claim there.
2. **If abstract is ambiguous, read the conclusion section.** Look for
   phrases like "we find that X causes an increase in Y" or "our results
   suggest no effect."
3. **If still ambiguous, look at the main results table.** The primary
   specification (usually Column 1 or labeled "baseline") determines
   direction.
4. **Never infer direction from one's own causal intuition.** Code what
   the paper claims, not what you think the truth is.

**Common pitfall**: Papers often present a positive main effect with
heterogeneity ("effect is stronger for women / small firms / developing
countries"). This is **positive**, not **mixed**, unless the
heterogeneity includes a sign flip that the authors emphasize.

---

### 3.3 Supporting Sentence Requirement

For every label (method and direction), the annotator **must quote a
supporting sentence from the paper** into the CSV. Rules:

1. Quote verbatim, with quotation marks, max 200 characters.
2. Preferred source order: (a) abstract, (b) introduction,
   (c) conclusion, (d) method section header sentence. Avoid deep in the
   technical appendix.
3. If no single sentence captures the method/direction cleanly, quote
   two sentences joined by `[...]`.
4. If no supporting sentence can be found within the first 15 pages of
   the paper, **downgrade confidence to "low"** and flag for review.

---

### 3.4 Confidence Self-Rating

| Confidence | When to assign |
|---|---|
| **high** | Signature fully matches; supporting sentence is explicit; no plausible alternative label |
| **medium** | Signature matches with minor ambiguity; supporting sentence requires mild interpretation |
| **low** | Signature partially matches; multiple labels plausible; or supporting sentence is absent/weak |

Papers with `low` confidence on either method or direction become
candidates for the blind re-label subset (see §5.3).

---

## 4. Annotation Environment

### 4.1 Directory Layout

```
audit/human_gold/
├── labeling_protocol.md              # this file
├── sample_selection.py               # 80-paper sampler
├── sample_manifest.csv               # output: 80 paper IDs + metadata
├── sample_manifest.sha256            # hash of manifest
├── paper_native_labels.csv           # PRIMARY OUTPUT
├── blind_relabel_subset.csv          # subset re-labeled after ≥ 7 days
├── session_log.csv                   # per-session notes
├── compute_reliability.py            # intra-rater κ
├── audit_labels.py                   # distribution / coverage audit
├── rubric/                           # extended examples (optional)
│   ├── did_examples.md
│   ├── event_study_examples.md
│   ├── iv_examples.md
│   ├── rdd_examples.md
│   └── direction_edge_cases.md
└── pdfs_workdir/                     # symlinks to audit/pdfs/ for 80 papers
```

### 4.2 Blinding Enforcement

The annotator must **not** see the Phase 2 labels or LLM votes while
labeling. Enforcement:

1. **Sample manifest columns are split**: `sample_manifest.csv` contains
   only `paper_id`, `difficulty_tier`, `pdf_path`. The Phase 2 labels
   (`method_family_phase2`, `direction_phase2`) live in a **separate
   sealed file** (`sample_manifest_SEALED.csv`) not opened until
   post-labeling analysis.
2. **Labeling workflow uses only the PDF.** Open
   `audit/pdfs/paper_XX.pdf` directly. Do not open
   `experiments/exp_a/papers/paper_XX.json` (which contains Phase 2
   labels).
3. **No LLM assistance during labeling.** Do not paste the paper into
   Claude/GPT and ask for the method. Rubric + PDF + your own judgment
   only. Use of LLMs for translation (e.g., if the paper is in Chinese)
   is permitted; use for classification is not.
4. **Self-check before each session**: the log CSV has a
   `blinding_confirmed` column; set it to `YES` before labeling any paper
   in that session. An honest NO here is better than a dishonest YES.

### 4.3 Time Budget per Paper

- **Easy cases**: 20–30 minutes per paper (abstract + method section +
  primary results table).
- **Hard cases**: 40–60 minutes per paper (above + robustness discussion
  + appendix if needed).
- **Hard limit**: If any single paper takes more than 90 minutes, stop,
  flag `needs_discussion`, and move on. Return to it in a dedicated
  session.

Expected total: 80 × 35 avg = **~47 hours**, consistent with the 45–55
hour estimate.

---

## 5. Annotation Workflow

### 5.1 Per-Paper Procedure

For each paper in the manifest, execute these steps in order. **Do not
reorder.** The order is designed to minimize anchoring.

1. **Record start time.** Write `start_time` in session log.
2. **Read abstract in full.** Do not skim. Note any directional claim in
   the final sentences.
3. **Form a preliminary hypothesis.** Before reading further, write a
   1-line tentative guess for `method_family` and `direction` in a
   **private scratchpad** (not in the CSV). This is for later
   meta-reflection — if you frequently flip your guess after reading the
   method section, it may indicate the abstract is misleading.
4. **Read the method section** (typically §3 or §4). Locate the
   identification strategy paragraph. Match signatures from §3.1.
5. **Read the primary results table caption and first column.** Confirm
   direction against the coefficient.
6. **Commit labels to CSV.** Write:
   - `method_family` (one of: DID, Event Study, IV, RDD, Other)
   - `direction` (one of: positive, negative, mixed, unclear)
   - `supporting_sentence_method` (≤ 200 chars, verbatim quote)
   - `supporting_sentence_direction` (≤ 200 chars, verbatim quote)
   - `confidence_method` (high / medium / low)
   - `confidence_direction` (high / medium / low)
   - `notes` (free text, optional; use for edge cases, alternative labels
     considered)
   - `end_time` → auto-computed `time_spent_minutes`
7. **Do not revise previous papers.** Once committed, move on. If you
   later realize a prior label was wrong, add a row to `needs_review.csv`
   instead of editing the original. Revisions happen in a dedicated
   review pass, not ad hoc.

### 5.2 Session Structure

**Recommended daily target**:
- Per session: **4–6 papers** (roughly 2–3 hours with breaks).
- Per week: **15–20 papers** (3–4 sessions).
- Total completion: **4–5 weeks** sustainable, 3 weeks intensive.

**Never exceed 8 papers in a single session.** Annotation fatigue
degrades label quality measurably after ~6 papers. The last paper of a
long session is a known failure mode.

### 5.3 Blind Re-label Subset (for κ)

**Purpose**: Establish intra-rater test-retest reliability. Gate 1
requires κ ≥ 0.80.

**Schedule**:

| Milestone | Action |
|---|---|
| After first 20 papers labeled | Stop labeling. Wait ≥ 7 calendar days (log the dates). |
| Day 7+ | Randomly sample 4 papers (20% of the first 20) using `compute_reliability.py --sample`. |
| Re-label session | Re-label these 4 papers **without looking at original labels**. Use a fresh CSV row with `is_blind_relabel = True` and `original_label_row_id` pointing to the first-pass entry. |
| After re-label | Run `compute_reliability.py --evaluate`. Computes Cohen's κ for method_family and direction separately. |

**Note on sample size**: 4 papers is a small κ-sample and the resulting
κ has wide confidence intervals. This is acceptable for a Gate check
(pass/fail) but should not be reported as a precise reliability estimate
in the paper. For a tighter estimate, increase the re-label subset to 8
papers (40%) after the first 20, at the cost of additional time.

**Gate 1 criteria**:

- **Primary**: Intra-rater κ ≥ 0.80 on method_family on the 4-paper
  subset.
- **Secondary**: Intra-rater κ ≥ 0.70 on direction (lower bar
  acceptable; direction is known to be harder).
- **If either fails**:
  1. Re-read rubric §3.1 and §3.2.
  2. Discuss the 4 papers with a co-author or advisor (if available).
  3. Revise rubric with concrete examples in `rubric/`.
  4. Re-label a new random 4-paper subset from the first 20.
  5. Proceed to papers 21–80 only after passing.

**If no human co-annotator is available**:

- Report the limitation transparently in Methods: "A single annotator
  (the first author) produced paper-native gold labels. Intra-rater
  reliability was established via blind re-labeling after a ≥ 7-day
  interval."
- Treat intra-rater κ as the **operational reliability floor**, not
  inter-rater gold.
- **Optional bonus**: if any co-author can label even 10 papers
  independently, compute and report inter-rater κ on that small overlap.

---

## 6. Edge Cases and Common Failure Modes

Document decisions for these cases in `rubric/edge_cases.md`. Recurring
patterns:

**E1. Paper uses multiple methods**
- Rule: Code the method of the **main results table**, not robustness
  checks.
- Example: A paper whose baseline is DID but which adds IV as robustness
  → code as **DID**.

**E2. Method is in appendix only**
- Rule: If the method section (main body) does not clearly state the
  identification strategy, but the appendix does, still code based on
  the appendix.
- Downgrade confidence to `medium` or `low` and note
  "method-in-appendix" in `notes`.

**E3. Paper has two equally-weighted outcomes with different
directions**
- Rule: Code as `mixed`. Supporting sentence should quote the mixed
  framing.

**E4. Paper concludes "no significant effect"**
- Rule: Code as `unclear`. Null results are unclear, not "negative"
  (negative = significantly negative).

**E5. Paper's main result is positive but uses hedged language
("suggests", "consistent with")**
- Rule: Hedging is an author style choice, not a directional modifier.
  Code based on the coefficient sign and significance, not the prose
  tone.

**E6. Paper cannot be mapped to any of DID/ES/IV/RDD without stretching**
- Rule: Code as **Other**. Better to have an honest "Other" than a
  forced fit.
- Flag in `notes` what the paper actually uses (e.g., "structural DSGE
  model", "matching only").

**E7. Chinese-language paper**
- Rule: Use LLM for translation of key paragraphs if needed. Do **NOT**
  use LLM to classify the method. Your judgment on the translated text
  only.

**E8. Working paper version vs. published version differs**
- Rule: Use whichever version is in `audit/pdfs/paper_XX.pdf`. Note
  version details in `notes` if relevant.

---

## 7. Output CSV Schema

File: `audit/human_gold/paper_native_labels.csv`

| Column | Type | Description |
|---|---|---|
| `label_row_id` | int | Sequential ID, starting at 1 |
| `paper_id` | str | e.g., `paper_042` |
| `annotator_id` | str | `YH` for Yonghong Zhang; extend if co-annotators added |
| `session_date` | date (ISO 8601) | e.g., `2026-04-24` |
| `method_family` | enum | DID / Event Study / IV / RDD / Other |
| `direction` | enum | positive / negative / mixed / unclear |
| `supporting_sentence_method` | str (≤ 200) | Verbatim quote |
| `supporting_sentence_direction` | str (≤ 200) | Verbatim quote |
| `confidence_method` | enum | high / medium / low |
| `confidence_direction` | enum | high / medium / low |
| `time_spent_minutes` | int | Wall-clock minutes for this paper |
| `is_blind_relabel` | bool | True only for §5.3 re-label rows |
| `original_label_row_id` | int | For re-labels: points to first-pass row; else -1 |
| `notes` | str | Free text; edge cases, alternative labels considered |

**Validation constraints**:
- Every row must have non-empty supporting sentences.
- `method_family` ∈ {DID, Event Study, IV, RDD, Other} exactly
  (case-sensitive).
- `direction` ∈ {positive, negative, mixed, unclear} exactly.
- `time_spent_minutes` ∈ [5, 90]; outside this range → flag for review.
- Re-label rows: `original_label_row_id` must point to an existing
  `label_row_id` with `is_blind_relabel = False`.

Enforced by `audit_labels.py --validate`.

---

## 8. Quality Audit Checklist

Run `audit_labels.py` after every ~20 labeled papers. The script checks:

- **Cell fill**: each `method × difficulty` cell has ≥ 75% of its target
  8 papers.
- **Direction distribution**: min direction count ≥ 15 (after 80
  papers); flag earlier if heavy skew.
- **Confidence distribution**: flag if > 40% of labels are `high`
  (likely over-confident) or < 20% are `high` (likely under-confident).
- **Time distribution**: flag outliers outside [mean ± 2σ].
- **Supporting sentence quality**: regex check for minimum length
  (≥ 30 chars), quotation marks, no empty strings.
- **Schema validity**: enums match allowed values, types are correct.

Audit output is written to
`audit/human_gold/audit_report_YYYYMMDD.md`.

---

## 9. Integration with Downstream Analysis

After reaching 80 labeled papers + passing Gate 1:

### 9.1 A2 GT Leave-One-Model-Out

- Unblind `sample_manifest_SEALED.csv`.
- For each of 4 LOO GT variants (drop Claude / GPT-4o / Kimi / Gemini):
  - Recompute majority vote on original 261 corpus.
  - New tie cases that fall within the 80-paper gold subset → use
    `paper_native_labels.csv` as tiebreaker.
  - New tie cases outside the 80-paper subset → flag as
    `insufficient_coverage`; exclude from LOO analysis for those papers.

### 9.2 A3 Dual-track Comparison

- On the 80-paper subset, compute three label columns:
  1. `label_paper_native` (from this protocol).
  2. `label_pipeline_gt` (from `audit/gt_aggregate_decisions.json`,
     restricted to these 80).
  3. `label_paper_native_llm` (4-LLM vote re-run with original PDF text
     as input, not synthesis — requires ~$15 of API).
- Compute pairwise Cohen's κ.
- Drift attribution: `κ(paper_native, pipeline_gt) < κ(paper_native,
  paper_native_llm)` indicates synthesis-introduced drift dominates;
  opposite indicates LLM-vs-human drift dominates.

### 9.3 A5 L3 Rubric Validation

- The L3 judge LLM is evaluated against `paper_native_labels.csv`'s
  `method_family` column.
- Requirement: κ ≥ 0.75 for the judge to be used in downstream scoring.

---

## 10. Protocol Amendments

This protocol is versioned. Any change after labeling begins must:

1. Increment version (v1.0 → v1.1 for minor clarifications; v1.0 → v2.0
   for rubric changes affecting prior labels).
2. Record amendment in `amendments.md` with date, reason, and affected
   papers.
3. For v2.0+ changes: re-label all prior-affected papers.

Minor clarifications (rubric examples, typos) do not require
re-labeling.

---

## 11. What Success Looks Like

At the end of this protocol's execution, the annotator will have:

- [ ] `paper_native_labels.csv` with 80 rows + 4 re-label rows = 84 rows
      total.
- [ ] Intra-rater κ ≥ 0.80 (method) and ≥ 0.70 (direction) documented.
- [ ] Passed all checks in `audit_labels.py --validate`.
- [ ] `session_log.csv` with full provenance: dates, time spent,
      blinding confirmations.
- [ ] Any deviations from protocol documented in `amendments.md`.
- [ ] Sealed file `sample_manifest_SEALED.csv` opened only after
      completion.

This artifact becomes the foundation for A2, A3, and A5, and is cited in
Methods §Ground Truth Construction.

---

**End of Protocol v1.0**
