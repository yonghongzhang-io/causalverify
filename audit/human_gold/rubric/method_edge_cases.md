# Method Family Edge Cases

This file accumulates decisions for ambiguous `method_family` cases
encountered during labeling. Mirrors the structure of
`direction_edge_cases.md`. Each entry records: the paper, the
ambiguity, the decision taken, and the reasoning. Over time this
becomes the authoritative tie-breaker for method-family disputes.

Labels in this corpus come from protocol §3.1 signatures. This file
covers cases where those signatures do not cleanly produce a single
answer.

---

## Pre-seeded cases

These are the decision patterns to reference before coding any
ambiguous method case. When labeling produces a fresh edge case not
covered below, add it as a new section.

---

### Case M1 — Paper uses one of the four families as a DATA-COLLECTION step, but the primary methodological contribution is a DIFFERENT framework built on top

**Example paper**: paper_05 (Karpoff, Lee & Martin 2008, "The Cost to
Firms of Cooking the Books"). The paper measures total market losses
around SEC enforcement announcements using an **event-study** (CARs over
[-1, +1] window), then **decomposes** the total into direct fines,
legal costs, and a residual attributed to reputational damage. The
event-study is an upstream data-collection step; the novel contribution
is the decomposition framework.

**Pattern**: Paper clearly uses DID / ES / IV / RDD to produce its
quantitative inputs, but the main contribution — the object the
headline table reports — is something else (decomposition,
counterfactual accounting, welfare calculation, structural calibration
fed by the causal estimate, etc.).

**Decision rule**:

1. **Look at the headline / main results table.** What are the rows and
   columns actually labeled?
   - If headline table reports the causal estimate itself
     (CAR, β, RD treatment effect, LATE): code the four-family method.
   - If headline table reports the downstream decomposition
     (share of total attributable to reputation, welfare gain, etc.):
     code as **OTHER**.

2. **If the headline table mixes both** (some columns are causal
   estimates, others are decompositions): code the four-family method
   with `confidence = medium` and note in `notes` that the primary
   contribution is the decomposition / downstream framework.

3. **Always record the decomposition or downstream framework in
   `notes`.** Future analysts re-reading the CSV need to see that the
   paper's scientific contribution extends beyond the method family
   label.

**Why not auto-default to OTHER**: protocol §3.1 explicitly warns
against defaulting to OTHER when a signature matches. A paper that
successfully applies event-study to collect its measurements deserves
to be labeled as using event-study, even if the event-study is not the
novel part.

**Supporting sentence for method**: quote the sentence that names the
data-collection technique, not the decomposition claim. E.g., for
paper_05: *"We measure market-adjusted abnormal returns around the
first public revelation of the misconduct."*

**Notes field should include**: *"Primary contribution is a
decomposition / counterfactual / welfare / structural framework (see
Table X). Event-study is the measurement step."*

---

## Template for future cases

### Case M?? — [short description]

**Example paper**: `paper_XX` (title in quotes if useful)

**Pattern**: [what makes this ambiguous]

**Decision**: coded as [DID / EVENT_STUDY / IV / RDD / OTHER]

**Reasoning**: [1–3 sentence justification]

**Related cases**: [reference prior Mxx if applicable]

---
