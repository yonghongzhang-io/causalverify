# CAUSAL-BENCH: 100-Paper Target Distribution

## Target: 100 papers across 5 domains, 4 methods, 3 difficulty levels

### Domain Distribution
| Domain | Papers | Rationale |
|--------|--------|-----------|
| Finance | 40 | Primary domain, existing 13 papers + 27 new |
| Labor Economics | 20 | DID-heavy, classic natural experiments |
| Development Economics | 15 | IV-heavy (rainfall, colonial origins) |
| Health Economics | 15 | RDD-heavy (Medicare, insurance cutoffs) |
| Education | 10 | IV + RDD (class size, school construction) |
| **Total** | **100** | |

### Method x Difficulty Distribution
| Method | Easy | Medium | Hard | Total |
|--------|------|--------|------|-------|
| DID | 10 | 10 | 8 | **28** |
| EVENT_STUDY | 8 | 8 | 9 | **25** |
| IV | 6 | 9 | 10 | **25** |
| RDD | 7 | 8 | 7 | **22** |
| **Total** | **31** | **35** | **34** | **100** |

### Existing Papers (13)
| ID | Authors | Domain | Method | Difficulty |
|----|---------|--------|--------|------------|
| 01 | Ivashina & Scharfstein (2010) | Finance | DID | Easy |
| 02 | Duchin & Sosyura (2014) | Finance | DID | Medium |
| 03 | Cornaggia et al. (2015) | Finance | DID | Hard |
| 04 | Bernanke & Kuttner (2005) | Finance | ES | Easy |
| 05 | Karpoff, Lee & Martin (2008) | Finance | ES | Medium |
| 06 | Ahern & Harford (2014) | Finance | ES | Hard |
| 07 | Greenstone, Mas & Nguyen (2020) | Finance | IV | Medium |
| 08 | Becker & Ivashina (2014) | Finance | IV | Hard |
| 09 | Cunat, Gine & Guadalupe (2012) | Finance | RDD | Easy |
| 10 | Fang, Tian & Tice (2014) | Finance | RDD | Medium |
| 11 | Masulis, Wang & Xie (2007) | Finance | ES | Hard |
| 12 | Moeller, Schlingemann & Stulz (2004) | Finance | ES | Hard |
| 13 | Harford (2005) | Finance | ES | Hard |

### New Papers (87) — Candidates by Batch

#### Batch 1: Cross-Domain Classics (papers 14-23)
| ID | Authors | Domain | Method | Diff | Journal |
|----|---------|--------|--------|------|---------|
| 14 | Card & Krueger (1994) | Labor | DID | Easy | AER |
| 15 | Dube, Lester & Reich (2010) | Labor | DID | Medium | REStat |
| 16 | Autor, Dorn & Hanson (2013) | Labor | DID | Hard | AER |
| 17 | Miguel, Satyanath & Sergenti (2004) | Development | IV | Easy | JPE |
| 18 | Acemoglu, Johnson & Robinson (2001) | Development | IV | Hard | AER |
| 19 | Card, Dobkin & Maestas (2008) | Health | RDD | Easy | QJE |
| 20 | Lee (2008) | Labor/Political | RDD | Medium | JoE |
| 21 | Angrist & Lavy (1999) | Education | IV/RDD | Medium | QJE |
| 22 | Duflo (2001) | Development | DID | Easy | AER |
| 23 | Jayaratne & Strahan (1996) | Finance | DID | Easy | QJE |

#### Batch 2: Finance Expansion (papers 24-38)
| ID | Authors | Domain | Method | Diff | Journal |
|----|---------|--------|--------|------|---------|
| 24 | Rice & Strahan (2010) | Finance | DID | Easy | JF |
| 25 | Campello, Graham & Harvey (2010) | Finance | DID | Medium | JFE |
| 26 | Lemmon & Roberts (2010) | Finance | DID | Hard | JF |
| 27 | Savor & Wilson (2013) | Finance | ES | Easy | JFE |
| 28 | Huberman & Regev (2001) | Finance | ES | Easy | JF |
| 29 | Edmans (2011) | Finance | ES | Medium | JFE |
| 30 | Acharya & Johnson (2007) | Finance | ES | Hard | JF |
| 31 | Fisman (2001) | Finance/Dev | IV | Easy | AER |
| 32 | Benmelech & Frydman (2015) | Finance | IV | Hard | RFS |
| 33 | Fracassi & Tate (2012) | Finance | IV | Medium | JFE |
| 34 | Bernstein (2015) | Finance | IV | Medium | JF |
| 35 | Flammer (2015) | Finance | RDD | Easy | MS |
| 36 | Iliev (2010) | Finance | RDD | Easy | JF |
| 37 | Chernenko & Sunderam (2012) | Finance | DID | Hard | RFS |
| 38 | Keys, Mukherjee, Seru & Vig (2010) | Finance | RDD | Medium | QJE |

#### Batch 3: Labor Economics (papers 39-53)
| ID | Authors | Domain | Method | Diff | Journal |
|----|---------|--------|--------|------|---------|
| 39 | Katz & Krueger (1992) | Labor | DID | Easy | QJE |
| 40 | Autor (2003) | Labor | DID | Medium | QJE |
| 41 | Black (1999) | Labor | RDD | Easy | QJE |
| 42 | DiNardo & Lee (2004) | Labor | RDD | Medium | QJE |
| 43 | Mas (2006) | Labor | ES | Easy | AER |
| 44 | Mas & Moretti (2009) | Labor | ES | Medium | AER |
| 45 | Oreopoulos (2006) | Labor/Educ | IV | Medium | AER |
| 46 | Acemoglu & Angrist (2001) | Labor/Educ | IV | Hard | AER |
| 47 | Angrist & Evans (1998) | Labor | IV | Medium | AER |
| 48 | Bertrand & Mullainathan (2004) | Labor | DID/ES | Easy | AER |
| 49 | Krueger & Ashenfelter (1994) | Labor | IV | Easy | AER |
| 50 | Peri & Sparber (2009) | Labor | IV | Medium | AEJ |
| 51 | Dustmann, Schonberg & Stuhler (2017) | Labor | DID | Hard | AER |
| 52 | Clemens & Wither (2019) | Labor | DID | Medium | AEJ |
| 53 | Chetty, Friedman & Rockoff (2014) | Labor/Educ | ES | Hard | AER |

#### Batch 4: Development Economics (papers 54-65)
| ID | Authors | Domain | Method | Diff | Journal |
|----|---------|--------|--------|------|---------|
| 54 | Banerjee et al. (2015) | Development | DID | Easy | Science |
| 55 | Duflo & Hanna (2005) | Development | DID | Medium | AER |
| 56 | Nunn (2008) | Development | IV | Hard | QJE |
| 57 | Dell (2010) | Development | RDD | Hard | Ecma |
| 58 | Chattopadhyay & Duflo (2004) | Development | DID | Easy | QJE |
| 59 | Jayachandran & Lleras-Muney (2009) | Development | DID | Medium | QJE |
| 60 | Pande (2003) | Development | RDD | Medium | QJE |
| 61 | Nunn & Qian (2011) | Development | IV | Hard | AER |
| 62 | La Porta et al. (1998) | Development | IV | Medium | JPE |
| 63 | Burgess & Pande (2005) | Development | DID | Hard | AER |
| 64 | Mian & Khwaja (2005) | Development | IV | Medium | QJE |
| 65 | Ferraz & Finan (2008) | Development | RDD | Medium | AER |

#### Batch 5: Health Economics (papers 66-78)
| ID | Authors | Domain | Method | Diff | Journal |
|----|---------|--------|--------|------|---------|
| 66 | Finkelstein (2007) | Health | DID | Hard | QJE |
| 67 | Finkelstein et al. (2012) | Health | IV | Medium | QJE |
| 68 | Baicker et al. (2013) | Health | IV | Medium | NEJM |
| 69 | Anderson (2018) | Health | RDD | Easy | AER |
| 70 | Almond, Doyle & Kowalski (2010) | Health | RDD | Hard | QJE |
| 71 | Currie & Walker (2011) | Health | DID | Medium | AER |
| 72 | Duggan (2000) | Health | DID | Easy | JPE |
| 73 | Kolstad & Kowalski (2012) | Health | DID | Medium | AER |
| 74 | Doyle (2007) | Health | IV | Hard | JPE |
| 75 | Card, Dobkin & Maestas (2009) | Health | RDD | Medium | AER |
| 76 | Almond et al. (2005) | Health | DID | Easy | QJE |
| 77 | Chay & Greenstone (2003) | Health/Env | RDD | Hard | JPE |
| 78 | Evans & Garthwaite (2014) | Health | DID | Medium | AEJ |

#### Batch 6: Education (papers 79-88)
| ID | Authors | Domain | Method | Diff | Journal |
|----|---------|--------|--------|------|---------|
| 79 | Krueger (1999) | Education | ES/DID | Easy | QJE |
| 80 | Chetty et al. (2011) | Education | ES | Medium | QJE |
| 81 | Jacob & Lefgren (2004) | Education | RDD | Easy | REStat |
| 82 | Abdulkadiroglu et al. (2011) | Education | RDD | Medium | Ecma |
| 83 | Hoxby (2000) | Education | IV | Hard | AER |
| 84 | Deming (2011) | Education | IV | Medium | AEJ |
| 85 | Pop-Eleches & Urquiola (2013) | Education | RDD | Hard | AER |
| 86 | Dale & Krueger (2002) | Education | IV | Medium | QJE |
| 87 | Bettinger et al. (2012) | Education | DID | Easy | AER |
| 88 | Angrist, Lavy & Schlosser (2010) | Education | IV | Hard | QJE |

#### Batch 7: Additional Finance/Cross-domain (papers 89-100)
| ID | Authors | Domain | Method | Diff | Journal |
|----|---------|--------|--------|------|---------|
| 89 | Gormley & Matsa (2011) | Finance | DID | Medium | JF |
| 90 | Giroud & Mueller (2010) | Finance | DID | Hard | JF |
| 91 | Shue & Townsend (2017) | Finance | ES | Medium | JF |
| 92 | MacKinlay (1997) | Finance | ES | Easy | JEL |
| 93 | Kleven et al. (2014) | Labor/Public | RDD | Hard | QJE |
| 94 | Chetty, Looney & Kroft (2009) | Public | ES | Easy | AER |
| 95 | Cellini, Ferreira & Rothstein (2010) | Education | RDD | Hard | QJE |
| 96 | Mian & Sufi (2009) | Finance | IV | Hard | QJE |
| 97 | Bleakley (2007) | Development | DID | Hard | QJE |
| 98 | Evans & Schwab (1995) | Education | IV | Hard | AER |
| 99 | Dahl & Lochner (2012) | Labor | IV | Hard | AER |
| 100 | Donaldson (2018) | Development | DID | Medium | AER |

---

## Production Pipeline

### Step 1: JSON Generation (Week 1-2)
- Batch 1 (papers 14-23): 10 cross-domain classics — highest priority
- Batch 2-7: remaining papers in order

### Step 2: API Runs (ongoing as JSONs complete)
- 100 papers x 4 models = 400 API calls
- Automated via run_exp_a.py

### Step 3: Scoring (after all outputs generated)
- LLM-as-Rater: 3 LLMs score all 400 outputs → Fleiss' κ
- Human validation: stratified sample of 30 outputs → Cohen's κ vs LLM raters

### Step 4: Analysis
- Bootstrap 95% CI for all pass rates
- Fisher exact test for DID-preference bias
- McNemar test for RID ON vs OFF
- Cross-domain generalizability analysis
