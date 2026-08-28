"""
Extend Exp B from 30 to 100 DGP scenarios.

Strategy:
  1. Programmatically define 70 new scenario *parameter sets* (method, effect, noise,
     sample size variations). These cover the same 4 methods with more variation.
  2. For the story text (research question + data description), use GPT-4o
     as a template filler given the method/parameters/direction.
  3. Generate synthetic CSV data for each new scenario using the existing DGP
     helpers in generate_exp_b_scenarios.py.
  4. Write scenario JSONs (compatible with existing scoring pipeline).
  5. The new scenarios are named s31 through s100.

The 70 new scenarios target:
  - DID:         20 new (currently 10)  → total 30
  - EVENT_STUDY: 16 new (currently 8)   → total 24
  - IV:          18 new (currently 6)   → total 24
  - RDD:         16 new (currently 6)   → total 22
Total: 100
"""

import csv
import json
import os
import random
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from src.pipeline.generate_exp_b_scenarios import (
    make_did, make_event_study, make_iv, make_rdd,
    SCENARIOS_DIR, DATA_DIR,
)

from dotenv import load_dotenv
load_dotenv()

# ── Reproducibility ────────────────────────────────────────────────────
RNG = np.random.default_rng(123)  # different seed from original generator

# ── Topic templates for variety ────────────────────────────────────────
# Each topic is a (domain, short_title, treatment_description, outcome_description)
# tuple that we fill into the story. 24+ topics for variety.

TOPICS = {
    "DID": [
        ("health",  "Medicaid expansion",        "Medicaid coverage expansion in treated states", "log uninsured rate"),
        ("labor",   "Overtime pay rule change",  "overtime eligibility expansion", "log hours worked"),
        ("finance", "Dividend tax cut",          "2003 dividend tax cut exposure", "log dividend payout"),
        ("trade",   "China WTO accession",       "China's 2001 WTO accession exposure", "log manufacturing employment"),
        ("education","School funding reform",    "state school finance reform", "math test score (SD units)"),
        ("public",  "Smoking ban",               "indoor smoking ban in treated municipalities", "log hospital admissions for respiratory illness"),
        ("env",     "Carbon pricing",            "regional carbon price adoption", "log CO2 emissions per capita"),
        ("urban",   "Rent control expansion",    "rent control expansion in treated districts", "log rental prices"),
        ("devel",   "Microfinance rollout",      "microfinance branch entry", "household consumption log"),
        ("agri",    "Subsidy reform",            "crop insurance subsidy reform", "log acres planted"),
        ("health",  "ACA individual mandate",    "ACA individual mandate enforcement", "log insurance premiums"),
        ("labor",   "Paid leave mandate",        "state paid family leave law", "log labor force participation (women)"),
        ("finance", "Short sale ban",            "short selling ban on financial stocks", "log stock volatility"),
        ("trade",   "NAFTA tariff removal",      "NAFTA tariff elimination", "log bilateral trade flows"),
        ("educ",    "Class size reduction",      "class size cap policy", "reading score (SD units)"),
        ("public",  "Police hiring grant",       "COPS grant police hiring", "log violent crime rate"),
        ("env",     "Catalytic converter mandate","catalytic converter mandate", "log NOx emissions"),
        ("urban",   "Bus rapid transit",         "BRT corridor opening", "log commute time"),
        ("devel",   "Deworming program",         "mass deworming rollout", "school attendance rate"),
        ("agri",    "Fertilizer subsidy",        "input subsidy program", "log crop yields"),
    ],
    "EVENT_STUDY": [
        ("finance", "Earnings announcement",       "quarterly earnings announcement", "abnormal return"),
        ("finance", "M&A announcement",            "merger announcement", "CAR [-1,+1]"),
        ("finance", "Dividend initiation",         "dividend initiation announcement", "announcement-day CAR"),
        ("finance", "CEO turnover",                "unexpected CEO departure", "CAR around departure date"),
        ("finance", "Stock split",                 "stock split announcement", "announcement-window CAR"),
        ("finance", "Bond downgrade",              "bond credit rating downgrade", "equity CAR"),
        ("finance", "IPO lockup expiry",           "IPO lockup expiration", "CAR around lockup expiry"),
        ("finance", "Analyst upgrade",             "analyst buy recommendation", "1-day CAR"),
        ("finance", "Regulatory investigation",    "SEC investigation announcement", "CAR [-2,+2]"),
        ("finance", "Fed rate surprise (+)",       "unexpected dovish Fed announcement", "bank stock CAR"),
        ("finance", "Patent grant",                "pharmaceutical patent approval", "drug-company CAR"),
        ("finance", "Product recall",              "major product recall announcement", "CAR around recall"),
        ("health",  "Drug approval",               "FDA drug approval", "biotech CAR"),
        ("public",  "Election result",             "surprise electoral outcome", "industry-level CAR"),
        ("env",     "Emissions standard",          "new emissions standard announcement", "auto maker CAR"),
        ("trade",   "Tariff announcement",         "surprise tariff announcement", "exposed-industry CAR"),
    ],
    "IV": [
        ("health",  "Distance to hospital",         "distance to nearest hospital as IV for care intensity", "mortality"),
        ("educ",    "Compulsory schooling law",     "compulsory schooling year as IV for education", "log wages"),
        ("labor",   "Lottery draft",                "draft lottery number as IV for Vietnam service", "log earnings"),
        ("devel",   "Rainfall shock",               "rainfall variation as IV for income", "civil conflict"),
        ("finance", "Analyst mergers",              "broker merger as IV for analyst coverage", "firm investment"),
        ("health",  "Quarter of birth",             "quarter-of-birth as IV for education", "chronic disease"),
        ("labor",   "Immigration shock",            "historical settlement pattern as IV for immigrant inflow", "native wages"),
        ("public",  "Political turnover",           "close-election Democratic wins as IV for policy", "log public spending"),
        ("env",     "Wind direction",               "upwind pollution source as IV for exposure", "infant mortality"),
        ("devel",   "Mobile phone coverage",        "topographic suitability as IV for mobile adoption", "market prices"),
        ("urban",   "Highway construction",         "1947 highway plan as IV for road density", "population growth"),
        ("trade",   "Shipping cost",                "geographic distance as IV for trade", "log GDP per capita"),
        ("agri",    "Seed variety",                 "agroecological suitability as IV for new seed adoption", "farm income"),
        ("finance", "Index inclusion",              "S&P 500 inclusion as IV for ownership", "firm value"),
        ("educ",    "Peer ability",                 "assigned roommate ability as IV for peer quality", "GPA"),
        ("health",  "ER congestion",                "ambulance diversion as IV for hospital choice", "30-day mortality"),
        ("labor",   "Bartik shock",                 "Bartik shift-share as IV for local labor demand", "wages"),
        ("public",  "Police staffing",              "Cops grant lottery as IV for police count", "crime rate"),
    ],
    "RDD": [
        ("educ",    "Scholarship GPA cutoff",       "GPA threshold for merit scholarship", "college enrollment"),
        ("health",  "Medicare age 65",              "age-65 Medicare eligibility", "log hospital visits"),
        ("labor",   "Unemployment benefit cap",     "benefit eligibility age cutoff", "log earnings 2 years later"),
        ("public",  "Close-election incumbency",    "close-election vote-share cutoff", "reelection probability"),
        ("finance", "Credit score cutoff",          "credit score threshold for loan approval", "default rate"),
        ("educ",    "Test score admission cutoff",  "elite high school admission score cutoff", "SAT score"),
        ("health",  "Birth weight threshold",       "very-low-birth-weight classification threshold", "log neonatal mortality"),
        ("public",  "Poverty line eligibility",     "income threshold for welfare eligibility", "labor supply"),
        ("env",     "Wilderness designation",       "wilderness area boundary (elevation cutoff)", "deforestation"),
        ("urban",   "School district boundary",     "school district boundary effect", "log house prices"),
        ("labor",   "Minimum drinking age",         "age-21 drinking age cutoff", "alcohol consumption"),
        ("devel",   "Irrigation eligibility",       "land slope threshold for irrigation", "crop revenue"),
        ("educ",    "Grade retention cutoff",       "end-of-year test cutoff for grade retention", "future test scores"),
        ("finance", "Covenant violation threshold", "debt-to-asset covenant threshold", "log capex"),
        ("public",  "District population threshold","population threshold for second representative", "public spending per capita"),
        ("health",  "BMI obesity cutoff",           "BMI cutoff for obesity diagnosis", "log medication use"),
    ],
}


def generate_story_llm(method: str, topic: tuple, effect: float, direction: str,
                       n: int, difficulty: str) -> dict:
    """Use GPT-4o to generate research_question + data_description from a template."""
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    domain, title_hint, treatment_desc, outcome_desc = topic

    system_msg = """You are writing a research scenario for an LLM benchmark. Output strict JSON with keys:
  title (short sentence),
  research_question (2-3 sentences),
  data_description (2-3 sentences, describing column names and sample size),
  id_strategy (one line),
  conclusion_detail (one sentence),
  main_effect (rough magnitude).

Do NOT mention the method family name (DID, event study, IV, RDD) in research_question or data_description — those should describe the scientific question and data only. The method is implicit in the setup.

Column names MUST match what would be present in the synthetic data (for DID: unit_id, period, treated, post, treat_x_post, y; for event study: stock_id, event_day, ret, mkt_ret, beta; for IV: y, x, z, controls; for RDD: running_var, treated, y, near_cutoff)."""

    user_msg = f"""Write a research scenario with these parameters:

Method family: {method}
Domain: {domain}
Hint: {title_hint}
Treatment: {treatment_desc}
Outcome: {outcome_desc}
Expected direction: {direction}
True effect size: {effect}
Sample size: {n}
Difficulty: {difficulty}

The scenario should describe a plausible research question and data setup that would require the given method family to identify the causal effect."""

    resp = client.chat.completions.create(
        model="gpt-4o",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
        max_tokens=600,
        temperature=0.4,
    )
    return json.loads(resp.choices[0].message.content)


def build_scenario(sid: str, method: str, topic: tuple, effect: float,
                   difficulty: str) -> dict:
    """Build one full scenario (JSON + ground truth + DGP params)."""
    direction = "positive" if effect > 0 else "negative"

    # Choose sample size based on difficulty
    if method == "DID":
        n_units = {"easy": 200, "medium": 150, "hard": 100}[difficulty]
        n_periods = {"easy": 8, "medium": 8, "hard": 10}[difficulty]
        noise = {"easy": 0.4, "medium": 0.5, "hard": 0.7}[difficulty]
    elif method == "EVENT_STUDY":
        n_stocks = {"easy": 100, "medium": 80, "hard": 60}[difficulty]
        noise = {"easy": 0.012, "medium": 0.015, "hard": 0.02}[difficulty]
    elif method == "IV":
        n = {"easy": 500, "medium": 400, "hard": 300}[difficulty]
        noise = {"easy": 0.25, "medium": 0.3, "hard": 0.4}[difficulty]
    elif method == "RDD":
        n = {"easy": 600, "medium": 500, "hard": 400}[difficulty]
        noise = {"easy": 0.12, "medium": 0.15, "hard": 0.2}[difficulty]

    # Generate story via LLM
    if method == "DID":
        story_n = n_units
    elif method == "EVENT_STUDY":
        story_n = n_stocks
    else:
        story_n = n
    story = generate_story_llm(method, topic, effect, direction, story_n, difficulty)

    # Assemble full scenario
    scenario = {
        "scenario_id": sid,
        "method_family": method,
        "difficulty": difficulty,
        "title": story.get("title", f"{method} scenario {sid}"),
        "research_question": story["research_question"],
        "data_description": story["data_description"],
        "ground_truth": {
            "identification_strategy": story.get("id_strategy",
                f"{method} — leveraging {topic[2]}"),
            "conclusion_direction": direction,
            "conclusion_detail": story.get("conclusion_detail", ""),
            "main_effect": story.get("main_effect", f"effect ≈ {effect}"),
        },
        "dgp_truth": {
            "type": method.lower().replace("event_study", "event"),
            "effect": effect,
            "direction": direction,
        },
        # DGP params (used to generate data)
        "_dgp_params": {
            "method": method,
            "effect": effect,
            **({"n_units": n_units, "n_periods": n_periods, "noise": noise}
               if method == "DID" else {}),
            **({"n_stocks": n_stocks, "noise": noise}
               if method == "EVENT_STUDY" else {}),
            **({"n": n, "noise": noise}
               if method in ("IV", "RDD") else {}),
        },
    }
    return scenario


def generate_data_for(params: dict) -> pd.DataFrame:
    """Dispatch to the right DGP helper based on params['method']."""
    method = params["method"]
    if method == "DID":
        return make_did(
            n_units=params["n_units"],
            n_periods=params["n_periods"],
            effect=params["effect"],
            noise=params["noise"],
        )
    if method == "EVENT_STUDY":
        return make_event_study(
            n_stocks=params["n_stocks"],
            effect=params["effect"],
            noise=params["noise"],
        )
    if method == "IV":
        return make_iv(
            n=params["n"],
            true_effect=params["effect"],
            noise=params["noise"],
        )
    if method == "RDD":
        return make_rdd(
            n=params["n"],
            effect=abs(params["effect"]),  # sign handled separately
            noise=params["noise"],
        )
    raise ValueError(f"Unknown method: {method}")


# ── Plan the 70 new scenarios ──────────────────────────────────────────

# Distribution: DID 20, ES 16, IV 18, RDD 16 = 70 (adding to existing 30)
# Each with a mix of difficulty and effect sizes (positive + negative)

NEW_SCENARIOS_PLAN = []

# DID: 20 new → 7 easy, 7 medium, 6 hard; mix signs
did_effects = [
    # easy
    -0.30, 0.25, -0.20, 0.18, -0.35, 0.22, -0.15,
    # medium
    -0.20, 0.15, 0.30, -0.10, 0.20, -0.25, 0.12,
    # hard
    -0.12, 0.08, -0.18, 0.10, -0.15, 0.25,
]
for i, effect in enumerate(did_effects):
    if i < 7:
        diff = "easy"
    elif i < 14:
        diff = "medium"
    else:
        diff = "hard"
    NEW_SCENARIOS_PLAN.append(("DID", TOPICS["DID"][i], effect, diff))

# EVENT_STUDY: 16 new → 5 easy, 6 medium, 5 hard
es_effects = [
    -0.02, 0.025, -0.03, 0.018, -0.028,
    0.022, -0.015, -0.025, 0.03, -0.02, 0.018,
    -0.018, 0.015, -0.022, 0.028, -0.012,
]
for i, effect in enumerate(es_effects):
    if i < 5:
        diff = "easy"
    elif i < 11:
        diff = "medium"
    else:
        diff = "hard"
    NEW_SCENARIOS_PLAN.append(("EVENT_STUDY", TOPICS["EVENT_STUDY"][i], effect, diff))

# IV: 18 new → 6 easy, 6 medium, 6 hard
iv_effects = [
    0.4, -0.35, 0.3, -0.25, 0.45, -0.4,
    0.35, -0.3, 0.25, -0.2, 0.5, -0.45,
    0.2, -0.15, 0.3, -0.25, 0.15, -0.35,
]
for i, effect in enumerate(iv_effects):
    if i < 6:
        diff = "easy"
    elif i < 12:
        diff = "medium"
    else:
        diff = "hard"
    NEW_SCENARIOS_PLAN.append(("IV", TOPICS["IV"][i], effect, diff))

# RDD: 16 new → 5 easy, 6 medium, 5 hard
rdd_effects = [
    0.25, -0.20, 0.30, -0.15, 0.22,
    -0.25, 0.18, -0.30, 0.20, -0.22, 0.28,
    0.15, -0.18, 0.12, -0.25, 0.22,
]
for i, effect in enumerate(rdd_effects):
    if i < 5:
        diff = "easy"
    elif i < 11:
        diff = "medium"
    else:
        diff = "hard"
    NEW_SCENARIOS_PLAN.append(("RDD", TOPICS["RDD"][i], effect, diff))

assert len(NEW_SCENARIOS_PLAN) == 70, f"Expected 70, got {len(NEW_SCENARIOS_PLAN)}"


def main():
    print(f"Generating {len(NEW_SCENARIOS_PLAN)} new scenarios (s31..s100)...",
          flush=True)
    for i, (method, topic, effect, diff) in enumerate(NEW_SCENARIOS_PLAN):
        sid = f"s{31 + i}"
        json_path = SCENARIOS_DIR / f"{sid}.json"
        if json_path.exists():
            print(f"  [SKIP] {sid} already exists", flush=True)
            continue
        try:
            scenario = build_scenario(sid, method, topic, effect, diff)
        except Exception as e:
            print(f"  [ERR] {sid}: {e}", flush=True)
            continue

        # Save JSON (drop _dgp_params for public JSON, but we need them for data gen)
        public = {k: v for k, v in scenario.items() if k != "_dgp_params"}
        public["data_file"] = f"experiments/exp_b/data/{sid}_data.csv"
        json_path.write_text(json.dumps(public, indent=2, ensure_ascii=False))

        # Generate and save synthetic data
        df = generate_data_for(scenario["_dgp_params"])
        data_path = DATA_DIR / f"{sid}_data.csv"
        df.to_csv(data_path, index=False)

        print(f"  [OK  ] {sid} | {method:<11} | {diff:<6} | "
              f"effect={effect:+.3f} | {len(df)} rows", flush=True)

    print(f"\nDone. Total scenarios: {len(list(SCENARIOS_DIR.glob('s*.json')))}")


if __name__ == "__main__":
    main()
