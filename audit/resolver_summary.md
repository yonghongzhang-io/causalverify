# Strict Paper Resolver — Audit Report

Resolved 262 Exp A papers against OpenAlex using 3-gate strict matching (title Jaccard ≥0.7 + author surname overlap + journal match) and a citation plausibility check.

## Summary

| Status | Count | % |
|---|---:|---:|
| **resolved** | 119 | 45.4% |
| **weak_match** | 136 | 51.9% |
| **ambiguous** | 7 | 2.7% |
| **not_found** | 0 | 0.0% |
| **error** | 0 | 0.0% |

### Status Meanings

- **resolved**: all 3 gates passed + citation count reasonable
- **weak_match**: 2/3 gates passed OR citation count unusually low
- **ambiguous**: ≤1/3 gates passed; best match is unreliable
- **not_found**: OpenAlex returned no candidates
- **error**: API/network failure

## Problematic Papers (143)

| paper_id | method | status | notes |
|---|---|---|---|
| paper_01 | DID | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_02 | DID | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_03 | DID | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_05 | EVENT_STUDY | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_07 | IV | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_100 | DID | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_102 | EVENT_STUDY | ambiguous | Only 1/3 gates pass |
| paper_104 | IV | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_105 | IV | ambiguous | Only 1/3 gates pass |
| paper_107 | RDD | ambiguous | Only 0/3 gates pass |
| paper_111 | DID | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_113 | IV | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_114 | IV | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_115 | IV | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_116 | RDD | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_117 | RDD | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_120 | DID | ambiguous | Only 1/3 gates pass |
| paper_123 | IV | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_128 | DID | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_130 | DID | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_131 | EVENT_STUDY | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_132 | EVENT_STUDY | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_134 | IV | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_137 | RDD | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_139 | DID | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_140 | EVENT_STUDY | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_141 | EVENT_STUDY | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_142 | EVENT_STUDY | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_143 | IV | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_144 | IV | ambiguous | Only 1/3 gates pass |
| paper_145 | IV | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_146 | IV | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_147 | RDD | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_148 | DID | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_15 | DID | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_150 | EVENT_STUDY | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_151 | IV | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_154 | RDD | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_155 | DID | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_156 | DID | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_160 | IV | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_161 | RDD | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_163 | RDD | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_165 | DID | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_166 | DID | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_167 | DID | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_168 | EVENT_STUDY | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_169 | IV | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_172 | IV | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_173 | RDD | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_174 | DID | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_175 | DID | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_176 | EVENT_STUDY | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_177 | EVENT_STUDY | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_178 | EVENT_STUDY | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_179 | EVENT_STUDY | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_184 | RDD | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_185 | RDD | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_186 | DID | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_187 | DID | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_188 | DID | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_189 | EVENT_STUDY | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_19 | RDD | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_190 | EVENT_STUDY | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_191 | EVENT_STUDY | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_192 | IV | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_194 | IV | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_195 | RDD | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_196 | DID | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_197 | DID | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_199 | EVENT_STUDY | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_204 | DID | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_206 | EVENT_STUDY | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_207 | EVENT_STUDY | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_209 | RDD | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_210 | RDD | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_214 | EVENT_STUDY | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_215 | IV | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_219 | DID | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_220 | EVENT_STUDY | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_221 | EVENT_STUDY | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_222 | EVENT_STUDY | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_224 | IV | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_225 | RDD | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_226 | RDD | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_227 | DID | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_228 | DID | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_230 | DID | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_232 | DID | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_233 | EVENT_STUDY | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_235 | EVENT_STUDY | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_236 | EVENT_STUDY | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_239 | EVENT_STUDY | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_241 | EVENT_STUDY | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_245 | IV | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_246 | IV | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_247 | IV | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_248 | IV | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_249 | IV | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_250 | IV | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_252 | IV | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_253 | RDD | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_254 | RDD | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_256 | RDD | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_258 | RDD | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_259 | RDD | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_26 | DID | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_260 | RDD | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_261 | RDD | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_262 | RDD | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_27 | EVENT_STUDY | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_30 | EVENT_STUDY | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_37 | DID | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_38 | IV | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_39 | DID | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_40 | EVENT_STUDY | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_43 | IV | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_47 | IV | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_48 | IV | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_50 | DID | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_51 | IV | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_52 | RDD | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_55 | IV | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_56 | DID | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_57 | RDD | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_58 | DID | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_59 | DID | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_60 | DID | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_64 | EVENT_STUDY | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_72 | DID | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_73 | DID | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_74 | DID | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_76 | EVENT_STUDY | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_77 | EVENT_STUDY | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_80 | IV | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_82 | IV | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_84 | RDD | ambiguous | Only 1/3 gates pass |
| paper_85 | RDD | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_86 | RDD | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_87 | DID | ambiguous | Only 0/3 gates pass |
| paper_91 | EVENT_STUDY | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_98 | DID | weak_match | 2/3 gates pass, citation_reasonable=True |
| paper_99 | DID | weak_match | 2/3 gates pass, citation_reasonable=True |

## Interpretation

🚨 **Only 45% resolved.** The Exp A dataset has significant metadata quality issues. Strongly recommend a manual audit pass before publication.