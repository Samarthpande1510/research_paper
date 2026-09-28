# Step 11 gene selection sweep, 2026-09-23

Goal: try the gene selection funnel from spec step 11 as one scikit-learn Pipeline, and
track every ElasticNet and CV combination in MLflow so nothing gets lost.

Script: `src/step11_gene_selection_cv.py`. Report with the full explanation and tables:
`results/step11_gene_selection_report.md`. MLflow experiment `sarcoma_step11_gene_selection`,
run `full_5x10` (id `0296fe19fd674649b655c8f9859abe57`), store in `results/mlflow/`.

## What I did

RNA-seq only, so 153 patients (the 2 with no RNA are left out). 5-fold CV repeated 10
times, 50 folds. Pipeline inside every fold: MAD filter to 1,000 genes, scale, elastic
net logistic regression keeping the top d genes, scale, then a plain logistic regression
to score them. Swept C (0.03 to 1.0), l1_ratio (0.2 to 1.0) and d (8, 16), 32 combinations.
Added scikit-learn and mlflow to `pyproject.toml`.

## What I saw

- PR-AUC runs from 0.963 to 0.990 across all 32. The top settings are within 0.003 of each
  other and the fold-to-fold std is about 0.016, so there's no real winner. d = 16 beats
  d = 8 by about 0.007 on average.
- 4 settings can't find d genes with weight (strict C plus heavy Lasso), so the pipeline
  fills the gap with zero-weight genes in alphabetical order. Their top genes are all ABCA/ABCB.
  Their scores and Jaccard values look fine but shouldn't be trusted.
- Typical Jaccard between folds is 0.34 for the 28 healthy settings, so the selected genes
  vary a lot fold to fold.
- MDM2 and CDK4 are never selected. Checked why: they rank 6,338 and 4,974 by MAD (out of
  20,518) so the top-1,000 MAD filter drops them before selection starts. MYH11 (rank 3)
  and DES (rank 84) survive but are almost never picked. Ordinary standard deviation
  wouldn't keep MDM2 or CDK4 either (ranks 1,431 and 1,634).

## Decided

Nothing final. I did not change the MAD filter, since it's what spec step 11 says.

## Open

- Keep the MAD filter as is, use a much bigger k, or skip it? This is a spec change so it's
  the user's call.
- Which settings to carry forward. Suggested d = 16, C around 0.1 to 0.3, l1_ratio around
  0.5 to 0.8, excluding the 4 broken ones.
- RNA only, or bring CNA and mutations into the funnel too.
- The spec says "5x5 (50-fold)" which doesn't add up. I used 5 splits x 10 repeats = 50.
- These scores are a bit optimistic because the same folds were used to compare 32
  settings. The real benchmark needs the setting fixed first or nested CV.
- There's a `smoke_test` run in MLflow from a 1-repeat check. Ignore it.
- Nothing from today's modeling work is committed yet.

## Second sweep, same day: varying the filter

The user looked at the first sweep's open decisions and said to go with my recommendations
(except commit/tracking, they want DagsHub for that), and to run the sweep again because the
first one wasn't right. What I decided from that, all now dated in `spec.md` and
`CONTEXT.md` sec 5:

- ElasticNet fixed at C=0.1, l1_ratio=0.5, d run at both 8 and 16.
- RNA-seq only, 5 splits x 10 repeats = 50 folds.
- Same 152 patients for every model (57 DDLPS, 95 LMS), the ones with RNA-seq, copy number
  and mutations.
- Test the filter instead of the ElasticNet settings: top 1,000 / 3,000 / 6,500 by MAD, or
  no filter.

Script: `src/step11b_filter_sweep.py`. Report: `results/step11b_filter_sweep_report.md`.
MLflow experiment `sarcoma_step11b_filter_sweep`, run `filter_sweep_5x10` (id
`73073cd5412d42ab91370d0c70f44822`).

What I saw:
- PR-AUC is 0.970 to 0.985 in every setting with a wobble of 0.02 to 0.03, so scores can't
  separate the filters.
- MDM2 and CDK4 never survive the top 1,000 or top 3,000 filters. At top 6,500 MDM2 survives
  in 78% of folds. With no filter MDM2 is picked in 100% of folds and CDK4 in 50% (d=8) to 96%
  (d=16).
- No filter takes about 6.5 minutes for 50 folds vs 3 to 5 seconds for top 1,000.
- I picked 6,500 knowing MDM2 ranks 6,338, so that setting is tuned by peeking. Worth
  remembering when comparing it.

Decided (delegated to me by the user, reversible): drop the MAD filter and let the elastic
net see all genes. Reason: no dependence on which genes I believe matter, it finds MDM2
every time, and the score difference is inside the noise.

Open:
- DagsHub. The scripts log to DagsHub if MLFLOW_TRACKING_URI is set (plus username and token
  env vars). Waiting on the user's account, repo connection and token.
- Not tested: other ElasticNet settings with no filter, a label-aware filter computed inside
  each fold, copy number in the funnel.
- Nothing committed yet.
