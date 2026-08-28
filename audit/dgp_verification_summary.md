# DGP Ground Truth Verification

Ran canonical regressions on 100 Exp B scenarios.
Tolerance: relative error < **10%**

## Aggregate

- VERIFIED:  42/100 (42.0%)
- FLAGGED:   58/100 (58.0%)
- ERROR:     0/100 (0.0%)
- Mean relative error:   0.254
- Median relative error: 0.143

## Per-method breakdown

| Method | VERIFIED | FLAGGED | ERROR | Total |
|---|---:|---:|---:|---:|
| DID | 4 | 26 | 0 | 30 |
| EVENT_STUDY | 24 | 0 | 0 | 24 |
| IV | 1 | 23 | 0 | 24 |
| RDD | 13 | 9 | 0 | 22 |

## Flagged / errored scenarios

- **s01** (DID): true=-0.300; est=-0.239, rel_err=0.204
- **s02** (DID): true=-0.150; est=-0.188, rel_err=0.250
- **s03** (DID): true=+0.250; est=+0.285, rel_err=0.138
- **s04** (DID): true=+0.200; est=+0.106, rel_err=0.471
- **s05** (DID): true=+0.180; est=+0.263, rel_err=0.461
- **s06** (DID): true=+0.220; est=+0.249, rel_err=0.133
- **s07** (DID): true=-0.120; est=-0.159, rel_err=0.329
- **s08** (DID): true=-0.250; est=-0.305, rel_err=0.220
- **s19** (IV): true=+0.400; est=+0.218, rel_err=0.456
- **s20** (IV): true=+0.400; est=+0.497, rel_err=0.242
- **s21** (IV): true=-0.150; est=-0.209, rel_err=0.393
- **s22** (IV): true=+0.400; est=+0.457, rel_err=0.142
- **s23** (IV): true=+0.400; est=+0.194, rel_err=0.516
- **s24** (IV): true=-0.300; est=-0.233, rel_err=0.223
- **s31** (DID): true=-0.300; est=-0.251, rel_err=0.162
- **s32** (DID): true=+0.250; est=+0.311, rel_err=0.244
- **s33** (DID): true=-0.200; est=-0.279, rel_err=0.396
- **s34** (DID): true=+0.180; est=+0.154, rel_err=0.145
- **s35** (DID): true=-0.350; est=-0.291, rel_err=0.170
- **s37** (DID): true=-0.150; est=-0.181, rel_err=0.206
- **s38** (DID): true=-0.200; est=-0.161, rel_err=0.194
- **s39** (DID): true=+0.150; est=+0.197, rel_err=0.315
- **s40** (DID): true=+0.300; est=+0.413, rel_err=0.376
- **s41** (DID): true=-0.100; est=-0.085, rel_err=0.153
- **s43** (DID): true=-0.250; est=-0.188, rel_err=0.247
- **s44** (DID): true=+0.120; est=+0.143, rel_err=0.194
- **s45** (DID): true=-0.120; est=-0.279, rel_err=1.322
- **s46** (DID): true=+0.080; est=-0.179, rel_err=3.237
- **s47** (DID): true=-0.180; est=-0.252, rel_err=0.400
- **s48** (DID): true=+0.100; est=+0.311, rel_err=2.114
- **s49** (DID): true=-0.150; est=-0.031, rel_err=0.796
- **s50** (DID): true=+0.250; est=+0.406, rel_err=0.625
- **s67** (IV): true=+0.400; est=+0.487, rel_err=0.218
- **s68** (IV): true=-0.350; est=-0.435, rel_err=0.242
- **s69** (IV): true=+0.300; est=+0.405, rel_err=0.351
- **s70** (IV): true=-0.250; est=-0.292, rel_err=0.170
- **s71** (IV): true=+0.450; est=+0.512, rel_err=0.137
- **s72** (IV): true=-0.400; est=-0.469, rel_err=0.173
- **s73** (IV): true=+0.350; est=+0.412, rel_err=0.178
- **s74** (IV): true=-0.300; est=-0.154, rel_err=0.487
- **s75** (IV): true=+0.250; est=+0.450, rel_err=0.799
- **s77** (IV): true=+0.500; est=+0.637, rel_err=0.275
- **s78** (IV): true=-0.450; est=-0.314, rel_err=0.302
- **s79** (IV): true=+0.200; est=+0.229, rel_err=0.146
- **s80** (IV): true=-0.150; est=-0.303, rel_err=1.020
- **s81** (IV): true=+0.300; est=+0.388, rel_err=0.292
- **s82** (IV): true=-0.250; est=+0.004, rel_err=1.014
- **s83** (IV): true=+0.150; est=+0.213, rel_err=0.419
- **s84** (IV): true=-0.350; est=-0.189, rel_err=0.460
- **s88** (RDD): true=+0.150; est=+0.128, rel_err=0.149
- **s90** (RDD): true=+0.250; est=+0.225, rel_err=0.101
- **s91** (RDD): true=+0.180; est=+0.146, rel_err=0.188
- **s93** (RDD): true=+0.200; est=+0.177, rel_err=0.114
- **s94** (RDD): true=+0.220; est=+0.264, rel_err=0.200
- **s95** (RDD): true=+0.280; est=+0.317, rel_err=0.131
- **s96** (RDD): true=+0.150; est=+0.191, rel_err=0.276
- **s97** (RDD): true=+0.180; est=+0.205, rel_err=0.138
- **s98** (RDD): true=+0.120; est=+0.057, rel_err=0.525

## Interpretation

🚨 **DGP verification largely failed.** Canonical regressions cannot recover the stated β* in most scenarios. The ground truth layer needs substantial repair before L2b+ claims can be defended.