# Leakage Scan Summary

Scanned: 100 scenarios

## Aggregate

- Critical leaks (method name literally appears): **21/100** (21.0%)
- Any leaks (incl. weak structural hints): **47/100** (47.0%)

## Per-method critical leak rates

| Method | Critical Leaks | Any Leaks |
|---|---:|---:|
| DID | 0/30 (0%) | 1/30 (3%) |
| EVENT_STUDY | 8/24 (33%) | 20/24 (83%) |
| IV | 13/24 (54%) | 23/24 (96%) |
| RDD | 0/22 (0%) | 3/22 (14%) |

## Scenarios with Critical Leaks (need manual review)


### s11 (EVENT_STUDY)
- Pattern: `\bevent[- ]study\b`
  Snippet: `...tocks in the [-1,+1] window?

event study data for 80 bank stocks aroun...`

### s12 (EVENT_STUDY)
- Pattern: `\bevent[- ]study\b`
  Snippet: `...in the [0,+1] event window?

event study data for 80 firms that experi...`

### s13 (EVENT_STUDY)
- Pattern: `\bevent[- ]study\b`
  Snippet: `...acquirer's curse hypothesis?

event study data for 80 acquiring firms....`

### s14 (EVENT_STUDY)
- Pattern: `\bevent[- ]study\b`
  Snippet: `...ound earnings announcements?

event study data for 80 firms with positi...`

### s15 (EVENT_STUDY)
- Pattern: `\bevent[- ]study\b`
  Snippet: `...[0,+3] post-election window?

event study data for 80 financial stocks....`

### s16 (EVENT_STUDY)
- Pattern: `\bevent[- ]study\b`
  Snippet: `...rience larger negative cars?

event study data for 80 auto-related stoc...`

### s17 (EVENT_STUDY)
- Pattern: `\bevent[- ]study\b`
  Snippet: `...gesting reputational damage?

event study data for 80 banks. variables:...`

### s18 (EVENT_STUDY)
- Pattern: `\bevent[- ]study\b`
  Snippet: `...e confounding earnings news?

event study data for 80 firms with simult...`

### s68 (IV)
- Pattern: `\binstrumental\s+variable\b`
  Snippet: `...y schooling year serves as an instrumental variable for education....`

### s69 (IV)
- Pattern: `\binstrumental\s+variable\b`
  Snippet: `...he draft lottery number as an instrumental variable for actual service.

the data...`

### s70 (IV)
- Pattern: `\binstrumental\s+variable\b`
  Snippet: `...ions? by using rainfall as an instrumental variable, we aim to isolate the causal...`
- Pattern: `\binstrumental\s+variable\b`
  Snippet: `...infall variation serves as an instrumental variable for income, allowing us to as...`

### s71 (IV)
- Pattern: `\binstrumental\s+variable\b`
  Snippet: `...he broker merger serves as an instrumental variable for analyst coverage....`

### s72 (IV)
- Pattern: `\binstrumental\s+variable\b`
  Snippet: `...using quarter-of-birth as an instrumental variable to address potential endogene...`

### s73 (IV)
- Pattern: `\binstrumental\s+variable\b`
  Snippet: `...cal settlement patterns as an instrumental variable to address potential endogene...`

### s75 (IV)
- Pattern: `\binstrumental\s+variable\b`
  Snippet: `...by using wind direction as an instrumental variable, we aim to isolate the causal...`

### s76 (IV)
- Pattern: `\binstrumental\s+variable\b`
  Snippet: `...phic suitability serves as an instrumental variable for mobile adoption....`

### s77 (IV)
- Pattern: `\binstrumental\s+variable\b`
  Snippet: `...47 highway plan be used as an instrumental variable to assess the causal effect o...`
- Pattern: `\binstrumental\s+variable\b`
  Snippet: `..., the 1947 highway plan as an instrumental variable (z), and other control variab...`

### s78 (IV)
- Pattern: `\binstrumental\s+variable\b`
  Snippet: `...ing geographic distance as an instrumental variable for trade volume.

the datase...`

### s79 (IV)
- Pattern: `\binstrumental\s+variable\b`
  Snippet: `...l suitability can serve as an instrumental variable to isolate the causal effect...`

### s80 (IV)
- Pattern: `\binstrumental\s+variable\b`
  Snippet: `..., using index inclusion as an instrumental variable.

the dataset includes 300 fi...`

### s84 (IV)
- Pattern: `\binstrumental\s+variable\b`
  Snippet: `...se a cops grant lottery as an instrumental variable for police staffing levels....`

## Interpretation

🚨 **21 scenarios have critical leaks (21.0%).** This is a systematic problem. All L3 results on Exp B must be re-evaluated after cleaning the scenarios.