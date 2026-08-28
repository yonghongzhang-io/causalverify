"""
Experiment B — Scenario & Synthetic Data Generator
====================================================
Creates 30 research scenario JSON files + synthetic CSV datasets.

Usage:
  python src/pipeline/generate_exp_b_scenarios.py
"""

import json
import numpy as np
import pandas as pd
from pathlib import Path

SCENARIOS_DIR = Path("experiments/exp_b/scenarios")
DATA_DIR      = Path("experiments/exp_b/data")
SCENARIOS_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

RNG = np.random.default_rng(42)


# ── DGP helpers ───────────────────────────────────────────────────────

def make_did(n_units=200, n_periods=8, treat_frac=0.5, effect=-0.3,
             treat_period=4, noise=0.5, panel_fe=True):
    """Standard 2×T DID panel.

    `treat_period` is the first treated period in the 1-indexed panel.
    When `panel_fe=True`, unit effects are fixed within unit across time.
    """
    units   = np.arange(n_units)
    treated = units < int(n_units * treat_frac)
    unit_fe = RNG.normal(0, 0.3, size=n_units) if panel_fe else np.zeros(n_units)
    rows = []
    for t in range(1, n_periods + 1):
        post = t >= treat_period
        for i in units:
            fe = unit_fe[i]
            y  = (0.5 * treated[i] + 0.4 * post
                  + effect * treated[i] * post
                  + fe + RNG.normal(0, noise))
            rows.append({"unit_id": i, "period": t,
                          "treated": int(treated[i]), "post": int(post),
                          "treat_x_post": int(treated[i] and post), "y": round(y, 4)})
    return pd.DataFrame(rows)


def make_event_study(n_stocks=80, window=(-10, 10), effect=-0.02, noise=0.015):
    """Market-model event study with [-10,+10] window."""
    rows = []
    for s in range(n_stocks):
        beta  = RNG.uniform(0.7, 1.4)
        alpha = RNG.normal(0, 0.001)
        for t in range(window[0], window[1] + 1):
            mkt_ret = RNG.normal(0.0003, 0.01)
            ar = effect if t >= 0 else 0.0
            ret = alpha + beta * mkt_ret + ar + RNG.normal(0, noise)
            rows.append({"stock_id": s, "event_day": t,
                          "ret": round(ret, 6), "mkt_ret": round(mkt_ret, 6),
                          "beta": round(beta, 4)})
    return pd.DataFrame(rows)


def make_iv(n=500, true_effect=0.4, first_stage=0.6, noise=0.3):
    """Simple IV: Z → X → Y with confounding."""
    z = RNG.binomial(1, 0.5, n)
    u = RNG.normal(0, 1, n)           # confounder
    x = first_stage * z + 0.5 * u + RNG.normal(0, 0.3, n)
    y = true_effect * x + 0.6 * u + RNG.normal(0, noise, n)
    return pd.DataFrame({"y": y.round(4), "x": x.round(4),
                          "z": z, "controls": RNG.normal(0, 1, n).round(4)})


def make_rdd(n=600, cutoff=0.5, effect=0.25, bandwidth=0.3, noise=0.15):
    """Sharp RDD around a cutoff."""
    x = RNG.uniform(0, 1, n)
    treated = (x >= cutoff).astype(int)
    y = (0.3 * x + effect * treated
         + RNG.normal(0, noise, n))
    return pd.DataFrame({"running_var": x.round(4), "treated": treated,
                          "y": y.round(4),
                          "near_cutoff": (np.abs(x - cutoff) <= bandwidth).astype(int)})


# ── Scenario definitions ──────────────────────────────────────────────

SCENARIOS = [

    # ── DID ── easy (3) ──────────────────────────────────────────────
    {
        "scenario_id": "s01", "method_family": "DID", "difficulty": "easy",
        "title": "COVID-19 lockdown effect on retail foot traffic",
        "research_question": (
            "Did COVID-19 lockdown orders (March 2020) reduce retail store foot traffic, "
            "and did stores in counties with stricter lockdowns experience larger declines "
            "compared to stores in counties with minimal restrictions?"
        ),
        "data_description": (
            "Panel data on 200 retail stores across 8 monthly periods (2019M10–2020M5). "
            "Variables: unit_id (store), period (1–8, treatment at period 4 = March 2020), "
            "treated (1 = county with strict lockdown, 0 = minimal restrictions), "
            "post (1 = post-March 2020), treat_x_post (interaction), "
            "y (log foot traffic index). "
            "Pre-period: 3 months. Post-period: 4 months."
        ),
        "dgp": {"type": "did", "effect": -0.30, "direction": "negative"},
        "ground_truth": {
            "identification_strategy": "DID — treated=strict-lockdown counties, control=minimal-restriction counties; shock=March 2020 lockdown",
            "conclusion_direction": "negative",
            "conclusion_detail": "Strict-lockdown stores show significantly lower foot traffic post-lockdown",
            "main_effect": "~30% decline in foot traffic for treated stores",
        },
    },
    {
        "scenario_id": "s02", "method_family": "DID", "difficulty": "easy",
        "title": "Minimum wage increase on restaurant employment",
        "research_question": (
            "Did a state-level minimum wage increase (period 4) reduce employment at "
            "fast-food restaurants in treated states compared to neighboring control states?"
        ),
        "data_description": (
            "Panel data on 200 fast-food restaurants across 8 quarters. "
            "Variables: unit_id, period (1–8), treated (1=minimum wage state), "
            "post (1=post-increase), treat_x_post, y (log full-time-equivalent employees). "
            "Treatment: minimum wage raised by $2/hr in period 4."
        ),
        "dgp": {"type": "did", "effect": -0.15, "direction": "negative"},
        "ground_truth": {
            "identification_strategy": "DID — treated=high-wage states, control=neighboring states; shock=minimum wage hike",
            "conclusion_direction": "negative",
            "conclusion_detail": "Modest employment decline in treated restaurants post minimum wage increase",
            "main_effect": "~15% reduction in employment",
        },
    },
    {
        "scenario_id": "s03", "method_family": "DID", "difficulty": "easy",
        "title": "School voucher program on student test scores",
        "research_question": (
            "Did introduction of a school voucher program (period 4) improve standardized "
            "test scores for students in treated school districts compared to control districts?"
        ),
        "data_description": (
            "Panel data on 200 school districts over 8 annual periods. "
            "Variables: unit_id, period, treated (1=voucher district), post, treat_x_post, "
            "y (standardized test score, mean-centered). Voucher program begins in period 4."
        ),
        "dgp": {"type": "did", "effect": 0.25, "direction": "positive"},
        "ground_truth": {
            "identification_strategy": "DID — treated=voucher districts, control=non-voucher; shock=program introduction",
            "conclusion_direction": "positive",
            "conclusion_detail": "Test scores increase significantly in voucher districts after program launch",
            "main_effect": "0.25 SD improvement in test scores",
        },
    },

    # ── DID ── medium (4) ────────────────────────────────────────────
    {
        "scenario_id": "s04", "method_family": "DID", "difficulty": "medium",
        "title": "TARP capital injection on bank risk-taking",
        "research_question": (
            "Did TARP capital injections (2008–2009) cause recipient banks to increase "
            "risk-taking (measured by non-performing loan ratio) compared to non-recipient banks?"
        ),
        "data_description": (
            "Panel data on 200 bank holding companies over 8 quarterly periods (2007Q3–2009Q2). "
            "Variables: unit_id (bank), period, treated (1=TARP recipient), post (1=post-TARP), "
            "treat_x_post, y (non-performing loan ratio). "
            "TARP recipients self-selected — use parallel pre-trends as identifying assumption."
        ),
        "dgp": {"type": "did", "effect": 0.20, "direction": "positive"},
        "ground_truth": {
            "identification_strategy": "DID — treated=TARP recipients, control=non-recipients; parallel pre-trends required",
            "conclusion_direction": "positive",
            "conclusion_detail": "TARP banks show higher NPL ratios post-injection, consistent with moral hazard",
            "main_effect": "20bp increase in NPL ratio for TARP banks",
        },
    },
    {
        "scenario_id": "s05", "method_family": "DID", "difficulty": "medium",
        "title": "Interstate banking deregulation on credit supply",
        "research_question": (
            "Did state-level interstate banking deregulation increase credit supply "
            "(total loans / assets) in deregulated states compared to regulated states?"
        ),
        "data_description": (
            "Panel data on 200 bank branches across 8 annual periods. "
            "Variables: unit_id, period, treated (1=state deregulated in period 4), "
            "post, treat_x_post, y (log loans-to-assets ratio). "
            "Deregulation timing varies across states — use the treated=1 group as those "
            "deregulating at period 4 exactly."
        ),
        "dgp": {"type": "did", "effect": 0.18, "direction": "positive"},
        "ground_truth": {
            "identification_strategy": "DID — treated=deregulated states, control=still-regulated; shock=deregulation date",
            "conclusion_direction": "positive",
            "conclusion_detail": "Credit supply increases significantly after deregulation",
            "main_effect": "18% increase in loans-to-assets",
        },
    },
    {
        "scenario_id": "s06", "method_family": "DID", "difficulty": "medium",
        "title": "Import tariff on domestic firm investment",
        "research_question": (
            "Did the 2018 steel/aluminum tariff increase capital investment at U.S. "
            "domestic steel producers (treated) compared to non-metals manufacturers (control)?"
        ),
        "data_description": (
            "Panel data on 200 manufacturing firms over 8 quarterly periods. "
            "Variables: unit_id, period, treated (1=steel/metals sector), post (1=post-2018Q1), "
            "treat_x_post, y (log capital expenditure). "
            "Tariff effective in period 4; control firms are in non-metals sectors."
        ),
        "dgp": {"type": "did", "effect": 0.22, "direction": "positive"},
        "ground_truth": {
            "identification_strategy": "DID — treated=protected sector firms, control=unaffected manufacturers",
            "conclusion_direction": "positive",
            "conclusion_detail": "Tariff-protected firms increase capex relative to non-protected peers",
            "main_effect": "22% higher investment in treated firms post-tariff",
        },
    },
    {
        "scenario_id": "s07", "method_family": "DID", "difficulty": "medium",
        "title": "Pollution regulation on plant total factor productivity",
        "research_question": (
            "Did tightened air quality regulations (period 4) reduce total factor productivity "
            "at high-emission manufacturing plants compared to low-emission plants?"
        ),
        "data_description": (
            "Panel data on 200 manufacturing plants over 8 annual periods. "
            "Variables: unit_id, period, treated (1=high-emission plant above regulatory threshold), "
            "post, treat_x_post, y (log TFP index). "
            "Regulation mandates emission reductions for plants above a pollution threshold."
        ),
        "dgp": {"type": "did", "effect": -0.12, "direction": "negative"},
        "ground_truth": {
            "identification_strategy": "DID — treated=above-threshold plants, control=below-threshold; shock=tighter regulation",
            "conclusion_direction": "negative",
            "conclusion_detail": "High-emission plants experience productivity decline after regulation tightening",
            "main_effect": "12% TFP reduction for above-threshold plants",
        },
    },

    # ── DID ── hard (3) ──────────────────────────────────────────────
    {
        "scenario_id": "s08", "method_family": "DID", "difficulty": "hard",
        "title": "Staggered fintech adoption on loan default rates",
        "research_question": (
            "Did adoption of algorithmic credit scoring (fintech) reduce loan default rates "
            "at banks, where banks adopted the technology at different points in time?"
        ),
        "data_description": (
            "Panel data on 200 banks over 8 quarterly periods. "
            "Variables: unit_id, period, treated (1=bank adopted fintech by period 4; "
            "staggered adoption is simplified here to a single cohort), "
            "post, treat_x_post, y (loan default rate). "
            "Note: in the real world this would require Callaway-Sant'Anna or Sun-Abraham "
            "estimators for staggered adoption."
        ),
        "dgp": {"type": "did", "effect": -0.25, "direction": "negative"},
        "ground_truth": {
            "identification_strategy": "Staggered DID (Callaway-Sant'Anna or Sun-Abraham) — cohort-specific ATTs; treatment=fintech adoption",
            "conclusion_direction": "negative",
            "conclusion_detail": "Fintech-adopting banks reduce default rates relative to non-adopters",
            "main_effect": "25bp reduction in default rate",
        },
    },
    {
        "scenario_id": "s09", "method_family": "DID", "difficulty": "hard",
        "title": "Heterogeneous treatment effects by firm size in DID",
        "research_question": (
            "Did a corporate tax cut (period 4) differentially affect investment for large vs. "
            "small firms, and can we identify heterogeneous treatment effects within a DID framework?"
        ),
        "data_description": (
            "Panel data on 200 firms (100 large, 100 small) over 8 annual periods. "
            "Variables: unit_id, period, treated (1=large firm, subject to larger tax cut), "
            "post, treat_x_post, y (log investment), size_group (large/small). "
            "Both groups experience tax cuts but large firms benefit more."
        ),
        "dgp": {"type": "did", "effect": 0.28, "direction": "positive"},
        "ground_truth": {
            "identification_strategy": "DID with heterogeneous effects — triple-diff or interaction terms for size groups",
            "conclusion_direction": "positive",
            "conclusion_detail": "Large firms increase investment more than small firms post tax cut",
            "main_effect": "28% higher investment growth for large firms",
        },
    },
    {
        "scenario_id": "s10", "method_family": "DID", "difficulty": "hard",
        "title": "Anticipation effects in DID: pre-announced policy",
        "research_question": (
            "A minimum capital requirement was announced in period 3 and effective in period 5. "
            "Do banks pre-emptively raise capital ratios before the effective date, "
            "creating anticipation effects that violate standard DID assumptions?"
        ),
        "data_description": (
            "Panel data on 200 banks over 8 quarterly periods. "
            "Variables: unit_id, period, treated (1=bank below capital threshold, must comply), "
            "post (1=period>=5), announce (1=period>=3), treat_x_post, treat_x_announce, "
            "y (tier-1 capital ratio). "
            "Announcement in period 3; effective date period 5."
        ),
        "dgp": {"type": "did", "effect": 0.35, "direction": "positive"},
        "ground_truth": {
            "identification_strategy": "DID with anticipation — must account for pre-announcement window; use period ≤2 as clean pre-period",
            "conclusion_direction": "positive",
            "conclusion_detail": "Constrained banks raise capital ratios both after announcement and after effective date",
            "main_effect": "35bp increase in tier-1 capital ratio",
        },
    },

    # ── EVENT STUDY ── easy (2) ───────────────────────────────────────
    {
        "scenario_id": "s11", "method_family": "EVENT_STUDY", "difficulty": "easy",
        "title": "Fed rate hike announcement on bank stock returns",
        "research_question": (
            "Do unexpected Federal Reserve interest rate hike announcements generate "
            "positive cumulative abnormal returns (CAR) for bank stocks in the [-1,+1] window?"
        ),
        "data_description": (
            "Event study data for 80 bank stocks around a single Fed rate hike event. "
            "Variables: stock_id, event_day (−10 to +10), ret (daily return), "
            "mkt_ret (S&P 500 return), beta (pre-estimated market model beta). "
            "Use days −10 to −2 as estimation window to compute expected returns; "
            "event window is [−1, +1]."
        ),
        "dgp": {"type": "event", "effect": -0.02, "direction": "negative"},
        "ground_truth": {
            "identification_strategy": "Event study — market model; estimation window [−10,−2]; event window [−1,+1]",
            "conclusion_direction": "negative",
            "conclusion_detail": "Bank stocks show negative CAR around the rate hike announcement",
            "main_effect": "CAR ≈ −2% in [−1,+1] window",
        },
    },
    {
        "scenario_id": "s12", "method_family": "EVENT_STUDY", "difficulty": "easy",
        "title": "Sudden CEO death and firm value",
        "research_question": (
            "Does the sudden, unexpected death of a CEO generate significant negative "
            "abnormal returns for the firm's stock in the [0,+1] event window?"
        ),
        "data_description": (
            "Event study data for 80 firms that experienced sudden CEO deaths. "
            "Variables: stock_id, event_day (−10 to +10), ret, mkt_ret, beta. "
            "Use estimation window [−10,−2] for market model. Event window [0,+1]."
        ),
        "dgp": {"type": "event", "effect": -0.025, "direction": "negative"},
        "ground_truth": {
            "identification_strategy": "Event study — market model AR; estimation [−10,−2]; event window [0,+1]",
            "conclusion_direction": "negative",
            "conclusion_detail": "Firms experience significant negative CAR on CEO death announcement",
            "main_effect": "CAR ≈ −2.5% in [0,+1]",
        },
    },

    # ── EVENT STUDY ── medium (3) ─────────────────────────────────────
    {
        "scenario_id": "s13", "method_family": "EVENT_STUDY", "difficulty": "medium",
        "title": "M&A announcement returns for acquirer firms",
        "research_question": (
            "Do acquirer firms experience negative cumulative abnormal returns around "
            "M&A announcement dates, consistent with the acquirer's curse hypothesis?"
        ),
        "data_description": (
            "Event study data for 80 acquiring firms. "
            "Variables: stock_id, event_day (−10 to +10), ret, mkt_ret, beta. "
            "Market model estimated on [−10,−2]. Event window [−1,+1]. "
            "Focus on whether acquirer CAR is significantly different from zero."
        ),
        "dgp": {"type": "event", "effect": -0.018, "direction": "negative"},
        "ground_truth": {
            "identification_strategy": "Event study with cross-sectional CAR regression; acquirer returns tested against zero",
            "conclusion_direction": "negative",
            "conclusion_detail": "Acquirers experience small negative CAR, consistent with overpayment hypothesis",
            "main_effect": "CAR ≈ −1.8%",
        },
    },
    {
        "scenario_id": "s14", "method_family": "EVENT_STUDY", "difficulty": "medium",
        "title": "Positive earnings surprise on stock returns",
        "research_question": (
            "Do firms with positive earnings surprises (actual EPS > consensus forecast) "
            "earn positive abnormal returns in the [0,+2] window around earnings announcements?"
        ),
        "data_description": (
            "Event study data for 80 firms with positive earnings surprises. "
            "Variables: stock_id, event_day (−10 to +10), ret, mkt_ret, beta. "
            "Market model estimated on [−10,−2]. Event window [0,+2]."
        ),
        "dgp": {"type": "event", "effect": 0.022, "direction": "positive"},
        "ground_truth": {
            "identification_strategy": "Event study — market model; positive surprise sample; event window [0,+2]",
            "conclusion_direction": "positive",
            "conclusion_detail": "Firms with positive earnings surprises earn significantly positive CAR",
            "main_effect": "CAR ≈ +2.2%",
        },
    },
    {
        "scenario_id": "s15", "method_family": "EVENT_STUDY", "difficulty": "medium",
        "title": "Election night surprise on financial sector stocks",
        "research_question": (
            "Did the unexpected election outcome generate abnormal returns for financial "
            "sector stocks in the [0,+3] post-election window?"
        ),
        "data_description": (
            "Event study data for 80 financial stocks. "
            "Variables: stock_id, event_day (−10 to +10), ret, mkt_ret, beta. "
            "Market model estimated on [−10,−2]. Event window [0,+3]. "
            "Election result announced on event day 0 (after market close, so [+1,+3] captures market reaction)."
        ),
        "dgp": {"type": "event", "effect": 0.03, "direction": "positive"},
        "ground_truth": {
            "identification_strategy": "Event study — political event; market model; focus on [+1,+3] for after-hours announcement",
            "conclusion_direction": "positive",
            "conclusion_detail": "Financial stocks earned positive abnormal returns after election surprise",
            "main_effect": "CAR ≈ +3.0%",
        },
    },

    # ── EVENT STUDY ── hard (3) ───────────────────────────────────────
    {
        "scenario_id": "s16", "method_family": "EVENT_STUDY", "difficulty": "hard",
        "title": "Supply chain disruption on auto manufacturer stocks",
        "research_question": (
            "Did a major semiconductor shortage announcement negatively affect auto manufacturer "
            "stocks, and do firms with higher chip dependency experience larger negative CARs?"
        ),
        "data_description": (
            "Event study data for 80 auto-related stocks. "
            "Variables: stock_id, event_day (−10 to +10), ret, mkt_ret, beta. "
            "Requires both time-series CAR calculation and cross-sectional regression of "
            "CAR on chip-dependency measure. Market model: [−10,−2]. Event window [0,+5]."
        ),
        "dgp": {"type": "event", "effect": -0.028, "direction": "negative"},
        "ground_truth": {
            "identification_strategy": "Event study + cross-sectional CAR regression on firm-level exposure variable",
            "conclusion_direction": "negative",
            "conclusion_detail": "Auto stocks decline; higher chip-dependency → larger CAR loss",
            "main_effect": "CAR ≈ −2.8%; cross-sectional gradient significant",
        },
    },
    {
        "scenario_id": "s17", "method_family": "EVENT_STUDY", "difficulty": "hard",
        "title": "Surprise regulatory fine on bank reputation and stock value",
        "research_question": (
            "Does a surprise regulatory fine announcement generate negative abnormal returns "
            "beyond the direct financial cost (fine amount / market cap), suggesting reputational damage?"
        ),
        "data_description": (
            "Event study data for 80 banks. "
            "Variables: stock_id, event_day (−10 to +10), ret, mkt_ret, beta, fine_ratio (fine/mktcap). "
            "Evaluate if CAR < −fine_ratio, implying reputational loss beyond the fine itself. "
            "Market model: [−10,−2]. Event window [−1,+1]."
        ),
        "dgp": {"type": "event", "effect": -0.035, "direction": "negative"},
        "ground_truth": {
            "identification_strategy": "Event study with CAR decomposition: financial cost vs. reputational component",
            "conclusion_direction": "negative",
            "conclusion_detail": "CAR exceeds fine/mktcap ratio, confirming reputational damage beyond monetary penalty",
            "main_effect": "CAR ≈ −3.5%; reputational component ≈ −1.5% above direct cost",
        },
    },
    {
        "scenario_id": "s18", "method_family": "EVENT_STUDY", "difficulty": "hard",
        "title": "Contaminated event window: confounding news during event period",
        "research_question": (
            "A firm announced both an acquisition AND an earnings beat on the same day. "
            "Can we decompose the market reaction to isolate the acquisition effect "
            "from the confounding earnings news?"
        ),
        "data_description": (
            "Event study data for 80 firms with simultaneous announcements. "
            "Variables: stock_id, event_day (−10 to +10), ret, mkt_ret, beta, eps_surprise. "
            "Challenge: earnings surprise on day 0 confounds acquisition announcement. "
            "Approach: partial out eps_surprise in the AR regression."
        ),
        "dgp": {"type": "event", "effect": -0.015, "direction": "negative"},
        "ground_truth": {
            "identification_strategy": "Event study with confound adjustment — regress AR on eps_surprise + acquisition dummy",
            "conclusion_direction": "negative",
            "conclusion_detail": "After controlling for earnings surprise, acquisition announcement generates negative AR",
            "main_effect": "Acquisition CAR ≈ −1.5% after earnings adjustment",
        },
    },

    # ── IV ── easy (2) ────────────────────────────────────────────────
    {
        "scenario_id": "s19", "method_family": "IV", "difficulty": "easy",
        "title": "Rainfall as IV for agricultural loan demand",
        "research_question": (
            "Does access to credit (loans per capita) improve agricultural output, "
            "using annual rainfall as an instrument for credit demand?"
        ),
        "data_description": (
            "Cross-sectional data on 500 farm households. "
            "Variables: y (log crop yield), x (log loans per capita), "
            "z (annual rainfall deviation from mean — instrument), "
            "controls (land size, soil quality index). "
            "First stage: rainfall → credit demand. Exclusion: rainfall affects yield only through credit."
        ),
        "dgp": {"type": "iv", "effect": 0.4, "direction": "positive"},
        "ground_truth": {
            "identification_strategy": "IV/2SLS — instrument: rainfall; first stage: rainfall → loans; exclusion restriction: rainfall ⊥ yield | credit",
            "conclusion_direction": "positive",
            "conclusion_detail": "Credit access significantly increases crop yields",
            "main_effect": "10% increase in credit → 4% yield increase (IV estimate)",
        },
    },
    {
        "scenario_id": "s20", "method_family": "IV", "difficulty": "easy",
        "title": "Distance to bank as IV for savings rate",
        "research_question": (
            "Does having a bank account increase household savings, using distance "
            "to the nearest bank branch as an instrument for account ownership?"
        ),
        "data_description": (
            "Cross-sectional data on 500 households. "
            "Variables: y (monthly savings in USD), x (has_account binary), "
            "z (distance to nearest branch in km — instrument), controls (income, education). "
            "First stage: distance → account ownership (negative). "
            "Exclusion: distance affects savings only through account ownership."
        ),
        "dgp": {"type": "iv", "effect": 0.4, "direction": "positive"},
        "ground_truth": {
            "identification_strategy": "IV/2SLS — instrument: branch distance; first stage: distance → account ownership (negative)",
            "conclusion_direction": "positive",
            "conclusion_detail": "Bank account ownership significantly increases savings",
            "main_effect": "Having an account increases monthly savings by ~40% (IV estimate)",
        },
    },

    # ── IV ── medium (2) ──────────────────────────────────────────────
    {
        "scenario_id": "s21", "method_family": "IV", "difficulty": "medium",
        "title": "Vietnam draft lottery as IV for military service on earnings",
        "research_question": (
            "Did military service reduce long-run civilian earnings, using Vietnam-era "
            "draft lottery numbers as an instrument for veteran status?"
        ),
        "data_description": (
            "Cross-sectional data on 500 men eligible for Vietnam-era draft. "
            "Variables: y (log annual earnings), x (veteran binary), "
            "z (draft lottery number, 1–365; low numbers = likely drafted), "
            "controls (age, education, race). "
            "IV: low draft number → more likely to serve → instrument for veteran status."
        ),
        "dgp": {"type": "iv", "effect": -0.15, "direction": "negative"},
        "ground_truth": {
            "identification_strategy": "IV/2SLS — instrument: draft lottery number; LATE for compliers (drafted but wouldn't have volunteered)",
            "conclusion_direction": "negative",
            "conclusion_detail": "Military service reduces earnings for complier veterans",
            "main_effect": "~15% earnings penalty for draft-induced veterans",
        },
    },
    {
        "scenario_id": "s22", "method_family": "IV", "difficulty": "medium",
        "title": "Bartik shift-share IV for local employment shock on wages",
        "research_question": (
            "Did local industry employment shocks increase wages, using a Bartik "
            "shift-share instrument (national industry growth × local industry shares) "
            "to instrument for local employment growth?"
        ),
        "data_description": (
            "Cross-sectional data on 500 local labor markets. "
            "Variables: y (log average wage change), x (log employment growth), "
            "z (Bartik instrument: sum of national growth rates × initial industry shares), "
            "controls (initial wage level, population). "
        ),
        "dgp": {"type": "iv", "effect": 0.4, "direction": "positive"},
        "ground_truth": {
            "identification_strategy": "IV/2SLS — Bartik shift-share instrument; identification from national (exogenous) shifts",
            "conclusion_direction": "positive",
            "conclusion_detail": "Employment growth driven by national shifts raises local wages",
            "main_effect": "10% employment growth → 4% wage increase (IV estimate)",
        },
    },

    # ── IV ── hard (2) ────────────────────────────────────────────────
    {
        "scenario_id": "s23", "method_family": "IV", "difficulty": "hard",
        "title": "Judge leniency as IV for incarceration on recidivism",
        "research_question": (
            "Does incarceration reduce or increase recidivism, using random assignment "
            "of criminal cases to lenient vs. strict judges as an instrument?"
        ),
        "data_description": (
            "Cross-sectional data on 500 criminal defendants. "
            "Variables: y (recidivism within 3 years, binary), x (incarcerated binary), "
            "z (judge leniency index — leave-one-out mean incarceration rate for judge), "
            "controls (offense type, prior record, age). "
            "Exclusion: judge assignment affects recidivism only through incarceration decision."
        ),
        "dgp": {"type": "iv", "effect": 0.4, "direction": "positive"},
        "ground_truth": {
            "identification_strategy": "IV/2SLS — judge leniency instrument; LATE for marginal defendants; test exclusion restriction carefully",
            "conclusion_direction": "positive",
            "conclusion_detail": "Incarceration increases recidivism for marginal defendants (criminogenic effect)",
            "main_effect": "Incarceration raises 3-year recidivism probability by ~15pp for compliers",
        },
    },
    {
        "scenario_id": "s24", "method_family": "IV", "difficulty": "hard",
        "title": "Oil price shocks as IV for inflation on investment",
        "research_question": (
            "Does inflation reduce corporate investment, using oil price shocks "
            "as an instrument for inflation to address the endogeneity of inflation "
            "with economic activity?"
        ),
        "data_description": (
            "Panel data on 500 firm-quarter observations. "
            "Variables: y (log investment), x (inflation rate), "
            "z (oil price change — instrument), controls (firm size, leverage, Q). "
            "Challenge: oil prices may directly affect investment beyond inflation channel "
            "(exclusion restriction is debatable)."
        ),
        "dgp": {"type": "iv", "effect": -0.3, "direction": "negative"},
        "ground_truth": {
            "identification_strategy": "IV/2SLS — oil price instrument; must defend exclusion restriction; test overidentification if multiple instruments",
            "conclusion_direction": "negative",
            "conclusion_detail": "Inflation reduces investment; exclusion restriction requires sector-level controls",
            "main_effect": "1pp inflation increase → 3% investment reduction (IV estimate)",
        },
    },

    # ── RDD ── easy (2) ───────────────────────────────────────────────
    {
        "scenario_id": "s25", "method_family": "RDD", "difficulty": "easy",
        "title": "Vote share cutoff and policy adoption",
        "research_question": (
            "Does winning a ballot initiative (vote share ≥ 50%) cause a discontinuous "
            "jump in municipal spending on the targeted policy?"
        ),
        "data_description": (
            "Cross-sectional data on 600 ballot initiatives. "
            "Variables: running_var (vote share, 0–1), treated (1 if vote_share ≥ 0.5), "
            "y (log municipal spending change), near_cutoff (|running_var − 0.5| ≤ 0.3). "
            "Sharp RDD: all initiatives above 50% are adopted."
        ),
        "dgp": {"type": "rdd", "effect": 0.25, "direction": "positive"},
        "ground_truth": {
            "identification_strategy": "Sharp RDD — cutoff = 50% vote share; local linear regression with optimal bandwidth",
            "conclusion_direction": "positive",
            "conclusion_detail": "Passing the initiative causes a discrete jump in targeted spending",
            "main_effect": "Winning increases spending by ~25%",
        },
    },
    {
        "scenario_id": "s26", "method_family": "RDD", "difficulty": "easy",
        "title": "Test score cutoff and college enrollment",
        "research_question": (
            "Does crossing a test score threshold for automatic college admission increase "
            "actual enrollment rates?"
        ),
        "data_description": (
            "Cross-sectional data on 600 high school graduates. "
            "Variables: running_var (standardized test score, 0–1; cutoff = 0.5), "
            "treated (1 if score ≥ cutoff), y (enrolled in college binary as continuous proxy), "
            "near_cutoff (within ±0.3 bandwidth). Sharp RDD."
        ),
        "dgp": {"type": "rdd", "effect": 0.25, "direction": "positive"},
        "ground_truth": {
            "identification_strategy": "Sharp RDD — test score cutoff; continuity of running variable required; McCrary density test",
            "conclusion_direction": "positive",
            "conclusion_detail": "Scoring above cutoff significantly increases college enrollment",
            "main_effect": "~25pp enrollment increase at cutoff",
        },
    },

    # ── RDD ── medium (2) ─────────────────────────────────────────────
    {
        "scenario_id": "s27", "method_family": "RDD", "difficulty": "medium",
        "title": "Income cutoff and subsidy program participation",
        "research_question": (
            "Does eligibility for a housing subsidy (income below threshold) increase "
            "housing expenditure, using income just below vs. just above the eligibility cutoff?"
        ),
        "data_description": (
            "Cross-sectional data on 600 households. "
            "Variables: running_var (income/threshold ratio, 0–1; cutoff = 0.5), "
            "treated (1 if income ≤ threshold i.e. running_var ≤ 0.5), "
            "y (housing expenditure share), near_cutoff. "
            "Must check for income manipulation at threshold (McCrary test)."
        ),
        "dgp": {"type": "rdd", "effect": 0.25, "direction": "positive"},
        "ground_truth": {
            "identification_strategy": "Sharp RDD — income cutoff; test for manipulation; local linear; optimal bandwidth (IK or CCT)",
            "conclusion_direction": "positive",
            "conclusion_detail": "Eligible households increase housing expenditure share",
            "main_effect": "~25pp increase in housing spend for eligible households",
        },
    },
    {
        "scenario_id": "s28", "method_family": "RDD", "difficulty": "medium",
        "title": "Asset size threshold and regulatory burden on bank profitability",
        "research_question": (
            "Does crossing the $10B asset threshold (triggering additional regulatory requirements) "
            "reduce bank profitability (ROA), using banks just above and below the threshold?"
        ),
        "data_description": (
            "Cross-sectional data on 600 bank holding companies. "
            "Variables: running_var (log assets / log $10B, centered at 1.0; cutoff = 0.5 in normalized units), "
            "treated (1 if assets > $10B), y (ROA), near_cutoff. "
            "Key concern: banks may strategically manage assets to stay below threshold."
        ),
        "dgp": {"type": "rdd", "effect": -0.25, "direction": "negative"},
        "ground_truth": {
            "identification_strategy": "Sharp RDD — asset threshold; test for bunching below $10B; local linear regression",
            "conclusion_direction": "negative",
            "conclusion_detail": "Banks just above threshold have lower ROA than just-below peers",
            "main_effect": "~25bp ROA reduction for above-threshold banks",
        },
    },

    # ── RDD ── hard (2) ───────────────────────────────────────────────
    {
        "scenario_id": "s29", "method_family": "RDD", "difficulty": "hard",
        "title": "Bandwidth sensitivity and RDD robustness checks",
        "research_question": (
            "Using the Russell 1000/2000 index reconstitution cutoff, does index membership "
            "affect institutional ownership, and is the RDD estimate robust to bandwidth choice?"
        ),
        "data_description": (
            "Cross-sectional data on 600 firms near the Russell 1000/2000 boundary. "
            "Variables: running_var (end-of-May market cap rank, normalized; cutoff = 0.5), "
            "treated (1 = Russell 2000 member i.e. just below cutoff), "
            "y (institutional ownership fraction), near_cutoff. "
            "Must test: bandwidth sensitivity, polynomial order sensitivity, placebo cutoffs."
        ),
        "dgp": {"type": "rdd", "effect": 0.25, "direction": "positive"},
        "ground_truth": {
            "identification_strategy": "Sharp RDD — rank cutoff; rdrobust with CCT bandwidth; donut-hole robustness; placebo cutoffs",
            "conclusion_direction": "positive",
            "conclusion_detail": "Russell 2000 membership increases institutional ownership; robust to bandwidth choice",
            "main_effect": "~25pp ownership increase at boundary",
        },
    },
    {
        "scenario_id": "s30", "method_family": "RDD", "difficulty": "hard",
        "title": "Fuzzy RDD: imperfect compliance with admission cutoff",
        "research_question": (
            "A scholarship program nominally requires GPA ≥ 3.0, but compliance is imperfect "
            "(some below-cutoff students receive exceptions, some above-cutoff decline). "
            "Using a fuzzy RDD, estimate the LATE of scholarship receipt on graduation rates."
        ),
        "data_description": (
            "Cross-sectional data on 600 students. "
            "Variables: running_var (GPA / 4.0, cutoff = 0.5 × 4.0 / 4.0 = 0.75 normalized to 0.5), "
            "z (1 if GPA ≥ cutoff — eligibility instrument), "
            "treated (1 = actually received scholarship — endogenous), "
            "y (graduated in 4 years binary as continuous proxy), near_cutoff. "
            "Fuzzy RDD: use cutoff crossing as instrument for actual scholarship receipt."
        ),
        "dgp": {"type": "rdd", "effect": 0.25, "direction": "positive"},
        "ground_truth": {
            "identification_strategy": "Fuzzy RDD — eligibility cutoff as IV for scholarship receipt; LATE = ITT / first-stage jump",
            "conclusion_direction": "positive",
            "conclusion_detail": "Scholarship receipt significantly improves graduation rates for compliers",
            "main_effect": "~25pp graduation rate increase (LATE via fuzzy RDD)",
        },
    },
]


# ── Data generation ───────────────────────────────────────────────────

def generate_data(scenario: dict) -> pd.DataFrame:
    dgp = scenario["dgp"]
    dtype = dgp["type"]
    effect = dgp["effect"]

    if dtype == "did":
        return make_did(effect=effect)
    elif dtype == "event":
        return make_event_study(effect=effect)
    elif dtype == "iv":
        return make_iv(true_effect=effect)
    elif dtype == "rdd":
        sign = 1 if effect > 0 else -1
        return make_rdd(effect=sign * 0.25)
    else:
        raise ValueError(f"Unknown DGP type: {dtype}")


# ── Main ──────────────────────────────────────────────────────────────

def main():
    print(f"Generating {len(SCENARIOS)} scenarios...")
    for sc in SCENARIOS:
        sid = sc["scenario_id"]

        # Save scenario JSON (without dgp internals)
        sc_out = {k: v for k, v in sc.items() if k != "dgp"}
        sc_out["data_file"] = f"experiments/exp_b/data/{sid}_data.csv"
        out_path = SCENARIOS_DIR / f"{sid}.json"
        out_path.write_text(json.dumps(sc_out, indent=2, ensure_ascii=False))

        # Generate and save synthetic data
        df = generate_data(sc)
        data_path = DATA_DIR / f"{sid}_data.csv"
        df.to_csv(data_path, index=False)

        print(f"  {sid} | {sc['method_family']:<12} | {sc['difficulty']:<8} | "
              f"{len(df)} rows → {data_path.name}")

    print(f"\nDone. Scenarios: {SCENARIOS_DIR}  Data: {DATA_DIR}")


if __name__ == "__main__":
    main()
