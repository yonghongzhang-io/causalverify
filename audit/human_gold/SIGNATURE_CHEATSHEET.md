# Method Signature Cheat Sheet

Keep this open beside the PDF while labeling. Each method family's
required signatures MUST all be present for a high-confidence match.

---

## DID — Difference-in-Differences

**Required (all three):**
1. ≥ 2 groups: treated vs control (or staggered cohorts)
2. ≥ 2 time periods: pre vs post (or event time around staggered adoption)
3. Parallel-trends / common-trends / two-way fixed effects language

**Strong indicators:**
- `(Treated × Post)` interaction term in main regression
- Callaway-Sant'Anna, de Chaisemartin-D'Haultfœuille, Sun-Abraham
  estimators for staggered DID
- Event-study coefficient plot centered on treatment date

**Anti-indicators:**
- No explicit control group or control period
- Only cross-sectional variation

---

## EVENT_STUDY

**Required (all three):**
1. A discrete event with a sharp date (announcement, policy enactment,
   disaster, earnings release)
2. An event window, typically `[t−k, t+k]`, around that date
3. Outcome measured per period relative to event (dynamic coefficients or
   cumulative abnormal returns)

**Strong indicators:**
- "Abnormal returns" / "CARs" / "market model" language
- Dynamic plot with coefficients at each event-time lead/lag
- News / earnings / merger / policy announcement as treatment

**Boundary with DID:**
- Discrete event + treated/control split + parallel-trends language
  → code as **DID** (primary: DID, with event-study specification)
- Event applied to ALL units, identification via pre-event stability
  → code as **EVENT_STUDY**

---

## IV — Instrumental Variables

**Required (all three):**
1. Explicit instrument variable Z, distinct from treatment D
2. First-stage regression (D on Z) reported or described
3. Exclusion restriction discussed (Z affects Y only through D)

**Strong indicators:**
- 2SLS / GMM / LIML / Control Function terminology
- F-statistic or weak-instrument diagnostics
- Historical / geographic / lottery / judge-assignment /
  Bartik-style / shift-share instruments

**Anti-indicators:**
- IV mentioned only as robustness check → code primary method instead
- Heckman selection models → code as OTHER unless explicit IV framing

---

## RDD — Regression Discontinuity

**Required (all three):**
1. A running variable (score, age, date, distance, etc.)
2. A cutoff / threshold at which treatment assignment changes
3. Local continuity assumption invoked (potential outcomes continuous
   at cutoff)

**Strong indicators:**
- "Sharp RD" / "Fuzzy RD" terminology
- Bandwidth selection (Imbens-Kalyanaraman, Calonico-Cattaneo-Titiunik)
- McCrary density test / manipulation test
- Local polynomial estimation
- Discontinuity plot

**Anti-indicators:**
- Cutoff mentioned but treatment is continuous (use IV or DID)
- "Kink" design without formal RKD framing → code as OTHER

---

## OTHER

**Use when:**
- Cross-sectional OLS with no explicit causal identification
  (purely descriptive / predictive)
- Structural models (IO, industrial organization, dynamic discrete choice)
- Matching / synthetic control (if not combined with DID)
- Randomized experiments (rare in this corpus)
- Natural experiments that don't fit the above four families
- Identification strategy unclear even after reading method section

**Do NOT use OTHER just because the paper is hard to parse.** If any of
the four main families fits on signature match, use that family and
lower confidence instead.

---

# Direction Cheat Sheet

**positive** — main coefficient is positive AND statistically significant
  (p < 0.10 in published form) for the primary outcome.

**negative** — main coefficient is negative AND statistically significant
  for the primary outcome.

**mixed** — (a) effect sign varies across subgroups / time horizons the
  authors themselves emphasize, OR (b) main effect has one sign but an
  equally-emphasized secondary effect has the opposite sign.

**unclear** — main effect is statistically insignificant, OR the paper
  does not report a clear directional claim, OR the sign depends on
  specification in a way that precludes a single direction.

**Decision rule for ambiguity:**
1. Read abstract's final sentences first.
2. If ambiguous, read the conclusion section.
3. If still ambiguous, look at main results table, Column 1 or "baseline".
4. Never infer direction from your own causal intuition. Code what the
   paper CLAIMS, not what you think the truth is.

**Common pitfall:** heterogeneity like "effect is stronger for women /
small firms" is **positive**, not mixed, unless the heterogeneity
includes a sign flip authors emphasize.

---

# Confidence Cheat Sheet

**high** — signature fully matches; supporting sentence is explicit;
  no plausible alternative label.

**medium** — signature matches with minor ambiguity; supporting sentence
  requires mild interpretation.

**low** — signature partially matches; multiple labels plausible; or
  supporting sentence is absent/weak.

> Flagging `low` on method OR direction puts this paper on the candidate
> list for the blind re-label subset (§5.3 of protocol).

---

# Supporting Sentence Requirement

For every label (method AND direction):
1. Quote verbatim, with quotation marks, max 200 characters.
2. Preferred source order: abstract → introduction → conclusion →
   method section header sentence. Avoid deep technical appendix.
3. If no single sentence captures it cleanly, join two with `[...]`.
4. If no supporting sentence found in first 15 pages → **downgrade
   confidence to `low`** and flag for review.
