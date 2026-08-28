# Exp B scenarios — task-facing release

Each `sNN.json` here contains only the fields a model is shown when it is
asked to solve the scenario:

    scenario_id, method_family, difficulty, title,
    research_question, data_description, data_file

The following fields exist in the internal scenario definitions and are
**deliberately withheld from this repository**, because they are the
quantities the benchmark scores against:

| field | why withheld |
|---|---|
| `ground_truth` | identification strategy, conclusion direction and detail, main effect |
| `dgp_truth` | generator type, effect magnitude, sign |
| `design_note` | states the intended direction for prior-override scenarios |
| `verified_empirical_car` | realised effect in the generated data |
| `_fix_notes` | records sign corrections applied to the generator |

`data_file` names the realised CSV for the scenario. Those CSVs are released
separately (see the repository README) and are not tracked in git.

Publishing the task statement without the target is what keeps the benchmark
usable for blind evaluation. Scoring is performed against the withheld fields
on the scoring side.
