# Difficulty Distribution — Justification Paragraph for Paper

Insert in Section 4.1 (Experiment A: Design), after the paper selection table.

---

## Draft Paragraph

Our benchmark comprises 10 papers spanning four method families (DID, Event
Study, IV, RDD) at varying difficulty levels. We note that the difficulty
distribution is intentionally unbalanced: IV includes no "easy" paper, and
RDD includes no "hard" paper. This reflects the empirical landscape of
published financial research rather than arbitrary assignment.

Instrumental variable designs in finance inherently require the researcher to
identify a valid instrument, argue for the exclusion restriction, and verify
first-stage strength — a set of tasks that has no trivially easy instantiation
in observational settings. Even the more accessible IV applications (such as
Bartik-style shift-share instruments in Paper 07) require constructing the
exposure weights and defending their exogeneity, placing them at "medium"
difficulty at minimum. Including an artificially simplified IV scenario would
compromise ecological validity.

Conversely, regression discontinuity designs in finance rely on institutionally
determined thresholds (vote margins, index inclusion cutoffs, regulatory
size thresholds) that constrain the available design space. The number of
published RDD papers in top finance journals using truly novel or complex
identification is limited. Our two RDD papers — shareholder vote thresholds
(Paper 09, easy) and Russell index reconstitution (Paper 10, medium) —
represent the most widely cited applications. Adding a "hard" RDD would
require either a less established paper (weakening the ground truth anchor)
or an artificially complex scenario (reducing ecological validity).

Importantly, the difficulty gradient within each method family is calibrated
to the complexity of institutional knowledge required, not to the statistical
methodology per se. An "easy" DID (Ivashina & Scharfstein: clear treatment
group, single event date, standard parallel trends) differs from a "hard" DID
(Cornaggia et al.: staggered state-level treatment, innovation outcome with
long lags, external finance dependence interaction) primarily in the depth of
institutional understanding needed — precisely the dimension where we expect
AI systems to struggle at Layer 3.

We report method-family and difficulty-level breakdowns of funnel pass rates
separately (Table X) to ensure that this distributional imbalance does not
confound cross-method comparisons.

---

## Alternative: Shorter Version (for space-constrained submission)

The difficulty distribution across method families is intentionally unbalanced:
IV includes no "easy" paper and RDD includes no "hard" paper. This reflects
the ecological distribution of published designs — IV inherently requires
instrument validity arguments that preclude trivially easy instantiation,
while the finite set of institutionally determined discontinuities in finance
limits RDD complexity. We report method-family breakdowns separately
(Table X) to prevent this imbalance from confounding cross-method comparisons.
