# CausalVerify Data Licensing Notes

This file clarifies the component-level licensing of the CausalVerify release
artifact. It is intentionally separate from the repository's code license.

## Code

Repository code is released under the MIT License, as specified in `LICENSE`.

## Synthetic DGP Data

The synthetic Experiment B scenario specifications, generated CSV datasets,
canonical-estimator summaries, and deterministic score tables may be released
under CC BY 4.0, subject to the terms of the release package.

## Model Outputs

Model outputs and scored summaries may be redistributed only where the relevant
provider terms permit redistribution. The frozen reviewer artifact includes
these outputs for auditability of the reported results.

## Published Paper PDFs

Published article PDFs used for Experiment A are not licensed by this
repository. They should not be included in the public CC BY data claim unless
redistribution rights have been confirmed for each PDF.

The public release should instead provide:

- bibliographic metadata,
- DOI/source URL where available,
- provenance and hash records,
- reconstructed RQ/DD/IC prompt fields, and
- consensus labels and audit summaries.

If PDFs are provided in a private artifact, they are
for review/audit only and are not part of the public reusable dataset license.

## Paper-Derived Context Fields

Experiment A structured fields (`research_question`, `data_description`,
`institutional_context`) are derived task contexts used for evaluation. They
should be distributed with provenance and should not be described as a license
grant over the underlying published articles.

## Recommended README Wording

Use "Synthetic data and scored artifacts: CC BY 4.0" rather than "all data:
CC BY 4.0" when original published PDFs or other third-party materials are
present in the working repository.
