# Daily Labeling Checklist

Print this. Pin it next to your monitor. Every item exists for a reason
documented in `labeling_protocol.md` — don't skip, don't reorder.

---

## Before each session  (~3 min)

- [ ] Close anything that could leak Phase 2 labels or LLM votes:
      - `experiments/exp_a/papers/paper_XX.json` → **closed**
      - `sample_manifest_SEALED.csv` → **closed**
      - Any browser tab with a prior project-specific classifier output
- [ ] Open the three working files:
      - `paper_native_labels.csv` (write)
      - `session_log.csv`         (write)
      - `direction_edge_cases.md` (read-only reference)
- [ ] Add a new row to `session_log.csv`:
      - `start_time` = now
      - `blinding_confirmed` = YES (honest NO is better than dishonest YES)
      - `fatigue_level` entry = 1–5 (1 = fresh, 5 = exhausted)
- [ ] Set a paper target for this session: **4–6 papers**; never > 8.

---

## Per-paper procedure  (§5.1 — strict order)

The ordering exists to minimize anchoring. If you catch yourself reading
out of order, stop and restart the paper.

1. [ ] **Record per-paper start time** (mental clock is fine).
2. [ ] **Open `audit/pdfs/paper_XX.pdf` directly.** Not a browser tab
       that might surface Phase 2 metadata.
3. [ ] **Read the abstract in full.** Note the final sentences — that's
       where the directional claim usually lives.
4. [ ] **Write a 1-line preliminary guess on a scratchpad (NOT in CSV)**:
       tentative `method_family` + `direction`. Do not revisit until
       step 8.
5. [ ] **Read the method section** (typically §3 or §4 of the paper).
       Match against `labeling_protocol.md` §3.1 signatures.
6. [ ] **Read the primary results table** — caption + first column.
       Confirm direction sign and significance.
7. [ ] **Edge-case check**: does the paper fit D1–D6 in
       `direction_edge_cases.md`? If yes, apply the rule. If it's a new
       ambiguity, you'll add a Dxx entry after step 8.
8. [ ] **Commit to CSV**:
       - `label_row_id` (next integer)
       - `paper_id`
       - `annotator_id` = YH
       - `session_date`
       - `method_family` ∈ {DID, EVENT_STUDY, IV, RDD, OTHER}
       - `direction` ∈ {positive, negative, mixed, unclear}
       - `supporting_sentence_method` — verbatim quote, ≤ 200 chars
       - `supporting_sentence_direction` — verbatim quote, ≤ 200 chars
       - `confidence_method` (high/medium/low)
       - `confidence_direction` (high/medium/low)
       - `time_spent_minutes`
       - `is_blind_relabel` = False
       - `original_label_row_id` = -1
       - `notes` — edge-case rationale, alternative labels considered
9. [ ] **Compare to preliminary guess.** If different, note in `notes`
       which step changed your mind. (Pattern material for Gate 1 debrief.)
10. [ ] **If new edge case**, append an entry to the relevant file:
        - Method-family ambiguity → `rubric/method_edge_cases.md` (Mxx)
        - Direction ambiguity → `rubric/direction_edge_cases.md` (Dxx)
11. [ ] **Do not revise prior rows.** If you realize an earlier label
        was wrong, write to `needs_review.csv`. Fix in a dedicated pass.

**90-minute hard stop on a single paper**: set both confidences to `low`,
write `needs_discussion` in notes, move on. Come back in a dedicated
session.

---

## Between papers  (~30 sec)

- [ ] Stretch, sip water.
- [ ] Honest self-check: "Did I look at anything I wasn't supposed to?"
      If yes, log in session_log `notes`.
- [ ] If fatigue ≥ 4 **or** this was your 6th paper today: **stop**.
      Don't push to paper 7. Quality drops measurably past 6.

---

## After each session  (~5 min)

- [ ] Complete the session_log row:
      - `end_time`
      - `papers_labeled_this_session` = count
      - `interruptions` = rough count (phone, doorbell, etc.)
      - `fatigue_level` at end
      - `notes` — "paper_42 took 60 min, IV-vs-DID ambiguity" etc.
- [ ] Save CSVs. Commit to git if versioning locally.
- [ ] Update running total: **___ / 80 labeled**.

---

## Weekly recap  (Sundays, ~15 min)

- [ ] Count papers labeled this week.
- [ ] Skim the `notes` column of the CSV for patterns:
      - Recurring direction ambiguity → add case to
        `direction_edge_cases.md`.
      - Recurring method ambiguity → seed the relevant
        `<family>_examples.md` in `rubric/`.
- [ ] Any protocol ambiguity surfaced? Draft the entry in `amendments.md`
      **now**, while fresh. Minor clarifications don't need immediate
      re-labeling, but memory fades fast.
- [ ] Pace check: on track for 4–5 weeks at current rate?

---

## Milestone triggers

### After paper #20

- [ ] **STOP. Do not start paper 21.**
- [ ] Run the audit:
      ```
      python audit_labels.py \
          --labels paper_native_labels.csv \
          --sealed-manifest sample_manifest_SEALED.csv \
          --out-dir .
      ```
      Passing `--sealed-manifest` is safe: the script only uses it for
      aggregate cell-count stats, never surfaces per-paper Phase 2 labels.
- [ ] Fix any ERRORS (exit 2) before continuing. Warnings (exit 1) —
      log them; address at Gate 1 debrief.
- [ ] Record `paper_20_completed_date` = YYYY-MM-DD in session_log.
- [ ] Calendar reminder: **earliest re-label date = +7 days**.

### At paper #20 + 7 days (Gate 1)

- [ ] Sample the re-label subset:
      ```
      python compute_reliability.py --sample \
          --labels paper_native_labels.csv \
          --n-initial 20 --n-relabel 4 --seed 20260501
      ```
- [ ] Record the 4 paper IDs. **Do NOT look at their original labels.**
- [ ] Re-label those 4 papers from scratch — same per-paper procedure,
      but:
      - `is_blind_relabel` = True
      - `original_label_row_id` = the first-pass row's id
- [ ] Compute κ:
      ```
      python compute_reliability.py --evaluate \
          --labels paper_native_labels.csv
      ```

**PASS** (method κ ≥ 0.80 **and** direction κ ≥ 0.70):

- [ ] Log κ values + date in session_log `notes`.
- [ ] Proceed to papers 21–80.

**FAIL** on either axis:

- [ ] Do NOT start paper 21.
- [ ] Re-read protocol §3.1 and §3.2.
- [ ] Examine the disagreed papers; identify what drove the flip.
- [ ] Update `direction_edge_cases.md` or the `<family>_examples.md`
      files in `rubric/`.
- [ ] Record the clarification in `amendments.md` (v1.0 → v1.1).
- [ ] Re-sample 4 new papers from the first 20 with a different seed.
- [ ] Re-run the κ evaluation. Only proceed on a pass.
- [ ] If κ is close to threshold: consider expanding re-label n from 4
      to 8 (`--n-relabel 8`) for a tighter estimate.

### After paper #80

- [ ] Final `audit_labels.py` run — all ERRORS must be zero.
- [ ] Row count check: 80 first-pass + 4 re-label + any Gate 1 retries =
      **≥ 84 rows**.
- [ ] **Only now** open `sample_manifest_SEALED.csv` to start A2/A3/A5
      downstream analysis.
- [ ] Walk through the §11 success checklist in the protocol — every box.

---

## Red flags — stop and think

- **Preliminary-guess flip rate > 30%** after reading method section.
  → Abstracts in this corpus may be misleading. Note pattern in
  `amendments.md`.
- **Five "low" confidences in a row** in the same cell. → Rubric may not
  fit that method family. Review §3.1 signatures; consider adding
  `<family>_examples.md`.
- **You're tempted** to open the SEALED manifest, the Phase 2 JSON, or
  ask an LLM "what method does paper X use." → Stop. Rest. This is the
  moment a 47-hour effort gets compromised.
- **Fatigue = 5 two sessions in a row.** → Reduce session target; take
  a full day off.

---

**End of checklist.**
