# Experiment A — Data Availability Assessment

## Overview

This document assesses the data availability for each of the 10 benchmark papers in Experiment A.
Each paper is classified into one of three replication tiers:

| Tier | Definition | Scoring implication |
|------|-----------|---------------------|
| **Full** | All core data publicly available; identification strategy fully replicable | Effect size proximity scored normally |
| **Partial** | ID strategy replicable; some outcome/control variables require proxy | Effect size scored with wider tolerance (within 10× instead of 5×) |
| **Proxy** | Core data behind paywall; replication uses proxy outcomes/instruments | Effect size proximity scored on direction + order-of-magnitude only |

---

## Summary Table

| Paper | Method | Difficulty | Replication Tier | Key Public Data | Key Missing Data | Workaround |
|-------|--------|-----------|-----------------|-----------------|-----------------|------------|
| 01 | DID | Easy | Proxy | FDIC Call Reports, yfinance | DealScan syndicated loans | Bank stock returns as proxy for lending capacity |
| 02 | DID | Medium | Partial | HMDA, Treasury TARP list, FDIC | DealScan, hand-collected TARP applications | HMDA mortgage risk analysis (main channel); skip syndicated loan channel |
| 03 | DID | Hard | Partial | PatentsView, Rice-Strahan index, FDIC | Compustat firm financials | SEC EDGAR for public firm financials; focus on patent-level outcomes |
| 04 | ES | Easy | **Full** | FRED (fed funds futures), yfinance, Fed website | — | Fully replicable with public data |
| 05 | ES | Medium | Partial | SEC AAERs, yfinance, DOJ releases | Pre-built enforcement timeline | Construct enforcement event timeline from AAERs (labor-intensive but doable) |
| 06 | ES | Hard | Proxy | BEA I-O tables, EDGAR 8-K filings | SDC Platinum M&A database | EDGAR 8-K for public M&A only; loses private deals |
| 07 | IV | Medium | **Full** | FFIEC CRA data, FDIC Call Reports, BLS QCEW | — | All core data publicly available |
| 08 | IV | Hard | Proxy | FRED SLOOS, EDGAR, yfinance | DealScan + FISD loan/bond data | Aggregate credit cycle test via SLOOS; firm-level ID not feasible without commercial data |
| 09 | RDD | Easy | Partial | EDGAR DEF 14A (proxy filings), yfinance | ISS Voting Analytics | Parse vote results from proxy filings (NLP pipeline) |
| 10 | RDD | Medium | Partial | PatentsView, EDGAR 13F, yfinance | CRSP (exact mkt cap ranks), Russell lists | Approximate rankings from yfinance; accept wider tolerance on cutoff precision |

---

## Detailed Assessment by Paper

### Paper 01 — Ivashina & Scharfstein (2010) · DID · Easy · PROXY

**What you need:** Syndicated loan volumes by bank × quarter, bank deposit-to-asset ratios, Lehman
bankruptcy date as treatment.

**What's public:**
- FDIC Call Reports (quarterly bank balance sheets including total loans, deposits, assets) — free via FFIEC CDR
- yfinance (bank stock prices for proxy approach)
- FRED (macro controls: fed funds rate, GDP, unemployment)

**What's not:**
- DealScan (Thomson Reuters): loan-level syndicated lending data. This is the core dataset in the original paper.

**Workaround:** Two options:
1. *Stock return proxy* (as in Pilot 2): group banks by wholesale funding intensity, compare stock CARs pre/post Lehman. Already validated in Pilot 2.
2. *Call Report proxy*: use aggregate loan growth from quarterly Call Reports. Coarser than loan-level but captures the same bank-level lending contraction.

**Recommendation:** Use both. The stock return proxy demonstrates pipeline functionality; the Call Report proxy gets closer to the actual variable of interest.

---

### Paper 02 — Duchin & Sosyura (2014) · DID · Medium · PARTIAL

**What you need:** TARP application approval/denial data, mortgage application characteristics (LTV, income), bank securities portfolio composition.

**What's public:**
- U.S. Treasury TARP Transaction Reports (complete recipient list with amounts and dates — free)
- HMDA mortgage data (individual mortgage applications with characteristics — free via FFIEC)
- FDIC Call Reports (bank balance sheets, securities holdings — free)
- Congressional committee membership records (for IV construction — public)

**What's not:**
- Hand-collected TARP application denial data (authors collected from SEC filings and press releases)
- DealScan syndicated loan data (for corporate lending analysis)

**Workaround:** The mortgage risk-taking analysis (the paper's most novel finding) is fully replicable with public HMDA + Treasury TARP data. The syndicated loan analysis can be dropped or proxied. For the TARP denial group, use the published list of 208 banks that publicly announced non-application (documented by authors and cited in subsequent papers).

**Recommendation:** Focus replication on the mortgage risk-taking channel (HMDA data). This is the paper's headline result and is fully replicable.

---

### Paper 03 — Cornaggia et al. (2015) · DID · Hard · PARTIAL

**What you need:** State-level banking deregulation dates (Rice-Strahan index), firm-level patent counts, firm financials for external finance dependence classification.

**What's public:**
- Rice-Strahan deregulation index (published in their 2010 JF paper, widely reproduced in appendix tables)
- USPTO PatentsView (patent counts, citations, assignee info — free)
- SEC EDGAR (10-K filings for public firm financials — free)
- FDIC Summary of Deposits (state-level banking concentration — free)
- FRED/BEA (state GDP, employment — free)

**What's not:**
- Compustat (comprehensive firm financials with consistent formatting — commercial)

**Workaround:** Parse firm financials from EDGAR 10-K filings (feasible for large sample with some NLP). Alternatively, use industry-level external finance dependence (Rajan-Zingales 1998) which is a fixed industry classification, not firm-varying.

**Recommendation:** This paper is an excellent test of whether an AI system can handle staggered DID with an institutional knowledge requirement (understanding IBBEA and state-specific deregulation). The data challenge is moderate.

---

### Paper 04 — Bernanke & Kuttner (2005) · Event Study · Easy · FULL

**What you need:** FOMC announcement dates and rate decisions, fed funds futures for surprise decomposition, stock index returns.

**What's public:**
- Federal Reserve website (FOMC dates, rate decisions, minutes — free)
- FRED (federal funds rate, 30-day fed funds futures — free)
- yfinance (S&P 500, sector ETF returns — free)
- Published monetary policy surprise series (Nakamura-Steinsson 2018; Jarocinski-Karadi — available on authors' websites)

**What's not:**
- Nothing essential. Intraday tick data would improve precision but daily data is sufficient for the main result.

**Recommendation:** Fully replicable. This should be the easiest paper for an AI system to handle. Failure here would indicate problems at L1/L2, not L3.

---

### Paper 05 — Karpoff, Lee & Martin (2008) · Event Study · Medium · PARTIAL

**What you need:** SEC enforcement actions with precise event timelines, stock returns around enforcement milestones, penalty amounts.

**What's public:**
- SEC AAER database (complete list of enforcement releases — free at sec.gov)
- SEC litigation releases and administrative proceedings (free via EDGAR)
- DOJ press releases for criminal enforcement (free)
- yfinance (firm stock returns — free)

**What's not:**
- Pre-built enforcement event timeline (mapping each case to initial disclosure, investigation, charges, settlement dates). This is the paper's main data contribution and required extensive manual collection.

**Workaround:** For a subset of cases (post-2000), the timeline can be constructed from AAER text + press releases + 8-K filings. The Dechow et al. restatement database (publicly available) provides an alternative sample with similar structure.

**Recommendation:** Partially replicable. The event study methodology is standard; the challenge is constructing the event timeline. An AI system that correctly identifies the multi-event structure (rather than treating it as a single-event study) demonstrates L3 competence.

---

### Paper 06 — Ahern & Harford (2014) · Event Study · Hard · PROXY

**What you need:** Comprehensive M&A deal counts by industry-year, BEA input-output tables, exogenous deregulation event dates.

**What's public:**
- BEA Input-Output tables (detailed industry-by-industry commodity flows — free)
- SEC EDGAR 8-K filings (M&A announcements for public companies — free)
- Academic literature documenting deregulation events (free)
- FRED (macro controls — free)

**What's not:**
- SDC Platinum (comprehensive M&A deal database including private deals — commercial, Refinitiv)

**Workaround:** Construct industry-level public M&A counts from EDGAR 8-K filings. This misses private transactions (potentially 50%+ of deals) but preserves the network propagation structure. Alternatively, use a simplified version focusing on the 48 Fama-French industries with publicly observable deal activity.

**Recommendation:** This is the most data-constrained paper. The identification challenge (network propagation of merger shocks) is conceptually complex, making it an excellent test of L3 even with proxy data. Expect the AI system to struggle with constructing the industry-network exposure measure.

---

### Paper 07 — Greenstone, Mas & Nguyen (2020) · IV · Medium · FULL

**What you need:** County-level small business lending (CRA data), bank balance sheets (Call Reports), county employment data, pre-crisis bank-county lending shares.

**What's public:**
- FFIEC CRA Disclosure Data (small business lending by bank-county — free)
- FDIC Call Reports (bank balance sheets including real estate exposure — free)
- BLS QCEW / Census County Business Patterns (county employment — free)
- FDIC Summary of Deposits (bank-county presence — free)
- FRED (macro controls — free)

**What's not:**
- Nothing essential. All core data sources are publicly available.

**Workaround:** None needed. This paper is fully replicable with public data.

**Recommendation:** Excellent IV benchmark. The Bartik (shift-share) instrument construction is well-documented and the data is free. The challenge for an AI system is understanding the exclusion restriction and correctly constructing the exposure-weighted instrument. This tests L3 identification knowledge, not data access.

---

### Paper 08 — Becker & Ivashina (2014) · IV · Hard · PROXY

**What you need:** Firm-level bank loan issuance, firm-level bond issuance, firm financials, business cycle indicators.

**What's public:**
- FRED SLOOS (Senior Loan Officer Survey — aggregate credit conditions — free)
- SEC EDGAR (bond prospectuses via 424B filings; firm financials via 10-K — free)
- FRED (NBER recession dates, credit spreads — free)
- yfinance (firm stock prices, market cap — free)

**What's not:**
- DealScan (firm-level syndicated loan data — commercial)
- FISD / Mergent (bond-level issuance data — commercial)

**Workaround:** Test the aggregate credit supply cycle hypothesis using SLOOS data + aggregate bond issuance (from SIFMA, free). For firm-level proxy: use EDGAR bond filings and approximate bank loan activity from Call Report aggregates. The revealed-preference identification (loan-bond substitution) requires observing both sources simultaneously at the firm level, which is very difficult without commercial data.

**Recommendation:** This is the hardest paper in the benchmark, both conceptually (credit supply vs. demand is a deep identification problem) and practically (data requirements). An AI system that correctly identifies the loan-bond substitution logic, even if it cannot fully implement it, demonstrates strong L3 understanding. Score effect size on direction + order of magnitude only.

---

### Paper 09 — Cuñat, Giné & Guadalupe (2012) · RDD · Easy · PARTIAL

**What you need:** Shareholder proposal vote results (vote share around 50% threshold), annual meeting dates, stock returns around meeting dates.

**What's public:**
- SEC EDGAR DEF 14A proxy filings (contain vote results — free)
- yfinance (stock returns — free)
- Annual meeting date calendars (extractable from proxy filings)

**What's not:**
- ISS Voting Analytics database (structured shareholder proposal data with vote counts — commercial)

**Workaround:** Parse vote results from DEF 14A filings using NLP. This is labor-intensive but feasible for a focused sample (governance proposals only). Many academic datasets of shareholder proposals have been published (e.g., Ertimur, Ferri & Stubben). Alternatively, use the ISS dataset if available at the user's institution.

**Recommendation:** The RDD design is textbook-clean. An AI system should identify: (1) the running variable (vote share), (2) the cutoff (50%), (3) the McCrary density test requirement, and (4) the appropriate bandwidth selection. Failure to identify any of these elements is an L3 failure. Data construction is secondary.

---

### Paper 10 — Fang, Tian & Tice (2014) · RDD · Medium · PARTIAL

**What you need:** Russell 1000/2000 index assignments, firm market capitalization ranks, institutional ownership (13F), stock liquidity measures, patent data.

**What's public:**
- SEC EDGAR 13F filings (institutional ownership — free)
- USPTO PatentsView (patents — free)
- yfinance (market cap, stock prices, volume, bid-ask proxy — free)
- FTSE Russell methodology documents (describe reconstitution rules — public)

**What's not:**
- CRSP (precise historical market cap for exact ranking at end-of-May — commercial)
- Official Russell constituent lists (proprietary, FTSE Russell)

**Workaround:** Approximate end-of-May market cap rankings from yfinance historical data. Accept some noise in cutoff assignment. Use the pre-2007 sample to avoid banding methodology complications. The fuzzy RDD structure (Russell 2000 assignment → institutional ownership → liquidity → innovation) can be tested even with approximate rankings.

**Recommendation:** Harder than Paper 09 because: (1) fuzzy RDD requires understanding the two-stage structure, (2) the running variable is a rank, not a continuous measure, (3) Russell's proprietary adjustments add noise. An AI system must correctly identify the liquidity channel mechanism, not just mechanically run an RDD on patents.

---

## Aggregate Assessment

**Papers with full public data replicability (2/10):**
- Paper 04 (Bernanke-Kuttner): Event study, easy
- Paper 07 (Greenstone-Mas-Nguyen): IV, medium

**Papers with partial replicability (5/10):**
- Paper 02 (Duchin-Sosyura): Main mortgage channel replicable
- Paper 03 (Cornaggia et al.): Patent outcomes + deregulation dates public
- Paper 05 (Karpoff et al.): AAERs public but timeline construction needed
- Paper 09 (Cuñat et al.): Vote data extractable from EDGAR
- Paper 10 (Fang et al.): Approximate rankings feasible

**Papers requiring proxy replication (3/10):**
- Paper 01 (Ivashina-Scharfstein): DealScan core data commercial
- Paper 06 (Ahern-Harford): SDC M&A database commercial
- Paper 08 (Becker-Ivashina): DealScan + FISD both commercial

**Implication for scoring:** Experiment A scoring must account for replication tier. Papers in the "proxy" tier should be scored on identification strategy match and conclusion direction, with relaxed effect size criteria. This should be documented in the paper's methodology section.
