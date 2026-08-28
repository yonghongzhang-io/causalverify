# Abstract Fidelity Summary (Step B)

**Model judge**: claude-opus-4-7
**Papers judged**: 213 / 262

## Distribution

| Verdict | Count | % of judged |
|---|---:|---:|
| faithful | 103 | 48.4% |
| partial | 86 | 40.4% |
| diverges | 24 | 11.3% |

## Non-judged

| Reason | Count |
|---|---:|
| no_real_abstract | 48 |
| error | 1 |

## Decision guide

- Faithful rate: **48.4%**
- 
- 
- 🔴 < 70%: full regeneration + re-run experiments recommended

## Sample discrepancies (top 10)

- **paper_07** (partial): Benchmark context emphasizes bank balance sheet deterioration (MBS/construction loan exposure) as the instrument, but abstract describes using pre-crisis bank market shares combined with estimated bank supply shifts; Benchmark frames the paper narrowly around identification challenge; abstract's main contribution is estimating real economy effects (employment) and finding economically small effects, plus placebo test in normal times (1997-2007); Benchmark omits the county-level geographic design, small business loan focus, and the LBD microdata employment analysis; Benchmark fabricates specific details about MBS/construction loan exposure not mentioned in the abstract
- **paper_10** (partial): Benchmark context specifies Russell 1000/2000 index reconstitution as the identification strategy, but the abstract only mentions 'regulatory changes' as the source of exogenous variation in liquidity; Benchmark frames higher institutional ownership as a channel for liquidity, while the paper identifies passive/non-monitoring institutional investors as a mechanism through which liquidity impedes innovation; Benchmark omits the takeover exposure mechanism mentioned in the abstract
- **paper_14** (partial): The OpenAlex entry is for the 2000 Reply paper (re-examining with payroll data), but the institutional_context describes the original 1994 Card-Krueger study setup without noting the reply/reanalysis context
- **paper_16** (partial): Names the identification strategy ('shift-share/Bartik-style') which the instructions say should not be named; Specifies exact list of comparison high-income countries not mentioned in the abstract; Includes specific employment statistics (17.3M to 11.5M) not in the abstract; Omits the abstract's key finding on transfer/benefit payments rising in trade-exposed areas
- **paper_19** (partial): B focuses narrowly on acute care hospital admissions, while A emphasizes heterogeneous effects across service types (routine visits vs. expensive procedures); B omits the key finding about differential gains across socioeconomic groups and the role of supplementary coverage; B frames it primarily as uninsured-to-insured transition, missing A's point that previously insured gain more for expensive procedures due to Medicare's supplementary generosity
- **paper_24** (partial): Benchmark specifies Riegle-Neal Act 1994 and Rice-Strahan index, which are not mentioned in the abstract; Benchmark emphasizes exogeneity/identification framing not present in the abstract; Benchmark omits the paper's main findings on interest rates (80-100 bps lower) and the null effect on loan amounts
- **paper_26** (diverges): Benchmark describes debt covenant violations as the credit supply shock; actual paper uses Drexel collapse, FIRREA, and insurance regulations; Benchmark implies regression discontinuity around covenant thresholds; actual paper uses difference-in-differences; Benchmark focuses on individual firm covenant violations; actual paper studies market-wide contraction in below-investment-grade credit; Benchmark omits the paper's main finding about near one-for-one decline in investment with debt issuances and stable leverage ratios
- **paper_27** (partial): Benchmark frames the paper as a conditional CAPM beta-return test; actual abstract focuses on average returns, Sharpe ratios, and risk premium earned on announcement days, not specifically on the beta-return relationship; Abstract emphasizes the magnitude of the equity risk premium earned on announcement days (60%+) and lower risk-free rates; benchmark omits these specific findings; Benchmark adds framing about idiosyncratic/liquidity factors on non-announcement days not present in the abstract
- **paper_34** (partial): Benchmark frames the study as a sharp RDD around the $75M threshold, but the abstract describes a natural quasi-experiment exploiting delayed compliance, not an RDD; Benchmark omits the foreign-firm $700M threshold for auditor attestation delay; Benchmark omits the paper's main findings (conservative earnings, real costs, reduced market value for small firms); Benchmark adds specific cost estimates ($1-3M) not mentioned in the abstract
- **paper_39** (diverges): Benchmark fabricates a Germany early-1990s empirical setting; the actual paper is a conceptual/theoretical synthesis classifying the literature; Benchmark invents a 3 million immigrant shock and dispersal policy not mentioned in the abstract; Benchmark omits the paper's actual contributions: canonical model framework, heterogeneous labor supply elasticities, and immigrant downgrading; Benchmark mischaracterizes the area vs skill-cell distinction instead of the paper's three-group classification and total vs relative effects argument
