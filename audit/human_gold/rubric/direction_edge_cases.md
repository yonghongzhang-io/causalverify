# Direction Edge Cases

This file accumulates decisions for ambiguous `conclusion_direction` cases
encountered during labeling. Each entry should record: the paper, the
ambiguity, the decision taken, and the reasoning. Over time this becomes
the authoritative tie-breaker document.

---

## Pre-seeded cases from the protocol

These are the canonical decision patterns to reference before coding any
ambiguous case. When labeling produces a fresh edge case not covered
below, add it as a new section.

---

### Case D1 — Positive main effect, negative subgroup

**Pattern**: The main coefficient on the pooled sample is positive and
significant, but the paper emphasizes in the abstract or conclusion that
the effect flips sign for a specific subgroup (e.g., low-income firms,
women, developing countries).

**Decision rule**:
- If the subgroup finding is **equally emphasized** as the main finding in
  abstract or conclusion (co-headline): code as **mixed**.
- If the subgroup finding is a **qualifier or caveat** ("stronger for X",
  "driven primarily by Y"): code as **positive**.

**Test**: Read the last two sentences of the abstract. Does the author's
summary claim have one sign or two signs?

---

### Case D2 — Short-run vs. long-run flip

**Pattern**: Effect is positive in years 1–2, negative in years 3–5 (or
vice versa). Common in finance/macro papers with dynamic treatment
effects.

**Decision rule**:
- If authors frame the paper as "we study dynamic effects showing a
  reversal": code as **mixed**.
- If authors frame the paper around the short-run effect and treat the
  long-run as robustness: code to match the **short-run sign**.
- If authors frame the paper around the long-run/cumulative effect: code
  to match the **long-run sign**.

**Test**: Which time horizon appears in the paper's title, abstract
headline, or most-cited coefficient?

---

### Case D3 — Statistical significance borderline

**Pattern**: Main coefficient has the expected sign (positive or
negative) but p = 0.11 or confidence interval just includes zero.

**Decision rule**:
- If the **published version** reports it as a main result with hedged
  language ("suggestive evidence", "marginally significant"): code by
  sign. Many top finance journals publish results at p < 0.10.
- If the paper itself treats it as a null result ("we do not find
  significant effects"): code as **unclear**.
- Default threshold: p < 0.10 for the primary specification constitutes a
  directional finding. Stricter thresholds (p < 0.05) are not required
  unless the paper itself demands them.

---

### Case D4 — Multiple primary outcomes with different signs

**Pattern**: Paper studies, e.g., employment AND wages, finding positive
effect on one and negative on the other. Neither is plausibly a secondary
outcome.

**Decision rule**: Code as **mixed**. This is the prototypical
mixed-direction case. Supporting sentence should quote the abstract
phrase that presents both.

---

### Case D5 — Effect exists but authors disagree with its interpretation

**Pattern**: Authors find a significantly positive coefficient but argue
it reflects selection/measurement error rather than a true causal effect,
and conclude "no true causal effect."

**Decision rule**:
- Code based on what the paper **concludes**, not what the raw
  coefficient shows.
- If the conclusion says "our IV estimates show the naive OLS is biased;
  the true effect is near zero": code as **unclear** (or the IV's sign if
  significant).
- If the conclusion says "the positive coefficient is spurious": code as
  **unclear**.
- Rationale: the benchmark tests whether LLMs recover the paper's claim,
  not raw regression output.

---

### Case D6 — Mechanism / channel papers

**Pattern**: Paper's primary contribution is identifying a mechanism
(e.g., "effect of credit on investment operates through firm balance
sheets"). The direct treatment effect may be secondary.

**Decision rule**:
- Identify the **primary relationship** the paper seeks to estimate. This
  is usually described in the research question / abstract's "we ask"
  sentence.
- Code the direction of that primary relationship, not the mechanism
  test.

---

## New cases discovered during labeling

*Append below. Template:*

### Case D?? — [short description]

**Paper**: `paper_XX` (title in quotes if useful)

**Pattern**: [what makes this ambiguous]

**Decision**: coded as [positive/negative/mixed/unclear]

**Reasoning**: [1–3 sentence justification]

**Related cases**: [reference prior Dxx if applicable]

---
