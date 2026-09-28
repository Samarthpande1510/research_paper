# Filter sweep: does the gene filter matter?

Date: 2026-09-23. Script: `src/step11b_filter_sweep.py`. MLflow experiment
`sarcoma_step11b_filter_sweep`, run `filter_sweep_5x10` (id
`73073cd5412d42ab91370d0c70f44822`). This redoes the first sweep
(`step11_gene_selection_report.md`) with the problems from it fixed.

## The short version

1. **Accuracy barely changes.** Every filter setting scores PR-AUC between 0.970 and
   0.985, and the fold-to-fold wobble is 0.02 to 0.03. So by score alone you can't tell
   the filters apart.
2. **What changes is which genes get picked.** With the spec's top-1,000 filter, MDM2 and
   CDK4 never even reach the selection step. With no filter, MDM2 is picked in 100% of
   folds and CDK4 in 50% to 96%. Those are the genes your logbook expected.
3. **No filter costs about 100 times more compute** (roughly 6.5 minutes vs 4 seconds for
   50 folds), because the model searches 20,518 genes instead of 1,000.
4. Decision I'm making on your behalf (you said "all yours"): **use no filter.** Reasons
   below. It's easy to reverse.

## What changed from the first sweep

| Thing | First sweep | This sweep |
|---|---|---|
| Patients | 153 (had RNA) | **152** (have RNA, copy number and mutations, so every future model sees the same people) |
| What we varied | ElasticNet settings (32 combos) | **The gene filter** (4 options x 2 values of d = 8 combos) |
| ElasticNet settings | swept | fixed at `C=0.1`, `l1_ratio=0.5` |
| Folds | 50 | 50 (5 splits x 10 repeats), same random splits for every setting so comparisons are fair |

The 152 patients are 57 DDLPS and 95 LMS.

## Results

| Filter | d | PR-AUC | Wobble (std) | ROC-AUC | MCC | Time for 50 folds |
|---|---|---|---|---|---|---|
| top 1,000 by MAD (spec) | 8 | 0.979 | 0.027 | 0.986 | 0.873 | 5 s |
| top 3,000 | 8 | 0.977 | 0.027 | 0.987 | 0.890 | 13 s |
| top 6,500 | 8 | 0.979 | 0.028 | 0.988 | 0.891 | 49 s |
| none | 8 | 0.970 | 0.033 | 0.982 | 0.862 | 378 s |
| top 1,000 by MAD (spec) | 16 | 0.984 | 0.020 | 0.989 | 0.881 | 3 s |
| top 3,000 | 16 | 0.984 | 0.021 | 0.990 | 0.889 | 17 s |
| top 6,500 | 16 | 0.985 | 0.024 | 0.991 | 0.920 | 61 s |
| none | 16 | 0.981 | 0.027 | 0.989 | 0.897 | 397 s |

How to read it: the biggest gap is 0.015 (0.970 vs 0.985) and the wobble is about 0.025, so
all of these are close to tied. The one mild pattern is the same as last time: keeping 16
genes scores a bit higher than keeping 8. "No filter" has the lowest score at d = 8
(0.970), but that's still inside the wobble.

## Where MDM2 and CDK4 end up

"Survives" means the gene made it past the filter in that fold. "Picked" means the
elastic net then chose it as one of the final d genes.

| Filter | d | MDM2 survives | CDK4 survives | MDM2 picked | CDK4 picked |
|---|---|---|---|---|---|
| top 1,000 | 8 or 16 | 0% | 0% | 0% | 0% |
| top 3,000 | 8 or 16 | 0% | 0% | 0% | 0% |
| top 6,500 | 8 | 78% | 100% | 78% | 84% |
| top 6,500 | 16 | 78% | 100% | 78% | 100% |
| none | 8 | 100% | 100% | 100% | 50% |
| none | 16 | 100% | 100% | 100% | 96% |

MYH11, DES and ACTA2 are almost never picked in any setting. Other genes (TPM2 shows up
everywhere) seem to do the same job, but I haven't checked that.

Two things worth understanding:

- **Top 6,500 looks best but I chose that number by peeking.** MDM2 ranks 6,338 by MAD
  across all patients, so I picked 6,500 knowing that would just let it through. That's
  tuning the filter to a gene I already believed in. Even so, MDM2 only survives in 78% of
  folds, because its rank moves around a little depending on which patients are in the
  training set. It works, but it's not a principled setting.
- **CDK4 is picked only half the time at d = 8 with no filter.** MDM2 and CDK4 sit next to
  each other on chromosome 12 and are usually amplified together in DDLPS, so once the model
  has one it may not need the other. I haven't measured how correlated they are here, so
  treat that as a likely explanation, not a confirmed one.

## Decision: no filter

Why I'd go with it:
- It doesn't depend on any assumption about which genes matter, which keeps the gene
  selection honest.
- It finds the biology your project was built around (MDM2 in every fold).
- The accuracy difference is inside the noise.

What it costs:
- About 6.5 minutes per 50-fold run instead of a few seconds. That's fine for the final
  benchmark. It's slow if you sweep lots of settings.
- Slightly lower score at d = 8 (0.970 vs 0.979), which is inside the noise.

If you'd rather keep things fast, top 6,500 is the middle option, but I'd want you to
know it was picked by looking at where MDM2 ranks.

I've recorded this as a dated change to spec step 11 (the old wording is kept next to it).
You can flip it back.

## What I did not test

- Only one ElasticNet setting (`C=0.1`, `l1_ratio=0.5`). The first sweep showed these barely
  matter, but a filter change could shift that. Cheap to check if you want.
- A filter that uses the labels (keeps the genes that differ most between LMS and DDLPS,
  computed inside each fold). It's fast and wouldn't lose MDM2. Not run because it wasn't in
  the options you approved.
- Copy number and mutations. This is still RNA only.
- The scores are still slightly optimistic, because the same folds compared 8 settings.
  The final benchmark needs the settings fixed up front, which they now are.

## Where everything is

- MLflow: http://127.0.0.1:5050 (local, while the server runs). Experiment
  `sarcoma_step11b_filter_sweep`, run `filter_sweep_5x10`, 8 child runs with per-fold
  scores and the exact genes chosen in each fold.
- Table of all 8 settings: `results/step11b_combination_results.csv`.
- Nothing here has been sent to DagsHub yet. When you set the DagsHub variables, running
  the same script again logs there.
