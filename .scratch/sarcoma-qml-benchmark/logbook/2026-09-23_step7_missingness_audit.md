# Step 7 missingness audit, 2026-09-23

Goal: count what's actually missing in the four merged tables from step 6, instead of
trusting that the gaps we already knew about were the only ones. Audit only. Nothing
got imputed, dropped, or scaled, that happens per fold later.

Script: `src/step7_missingness_audit.py`. Output: `data/processed/step7_missingness_report.json`
and `data/processed/step7_per_patient_completeness.csv`.

## What I checked

- All four tables have the same 155 patients in the same order, and no duplicate column
  names.
- For each modality, which patients are fully missing, which are only partly missing, and
  how many patients are missing per gene.
- Whether the `has_rnaseq` and `has_cna` flags in the clinical table match what the data
  actually looks like.
- Whether the values are what they should be (CNA only -2 to 2, mutations only 0 or 1).
- How many columns never change at all, since those can't help predict anything.

## What I found

- Alignment is fine everywhere: 155 patients, same order, no duplicate columns. Shapes
  are RNA 20,518 genes, CNA 25,128, mutations 5,165.
- RNA: exactly 2 patients missing (`TCGA-DX-A48V`, `TCGA-DX-A6BK`), both fully missing,
  nobody partly missing. Every one of the 20,518 genes is missing for those same 2
  patients and nobody else, so the gap is uniform, which is what the merge design
  predicted.
- CNA: exactly 1 patient missing (`TCGA-WK-A8XZ`), same story, all 25,128 genes missing
  for just that patient.
- Mutations: no missing cells at all. 20 patients have zero mutations, which we already
  confirmed against cBioPortal's sequenced list are real zeros and not missing data.
- The clinical flags match the data exactly for both RNA and CNA.
- Values are all in range. CNA has only -2 to 2, mutations only 0 or 1, RNA runs from 0
  to about 21.6 after the log2 transform.
- Unexplained missingness: none. Everything missing traces back to the 3 patients we
  already knew about.

One new thing came up: 376 RNA genes (1.83%) have the same value for every patient in
the cohort, which is basically genes that aren't expressed at all here. No constant
columns in CNA or mutations. This isn't a problem, the MAD filtering in the per-fold
step will drop those anyway since they have zero spread, but it's worth knowing they're
in there.

## What this means for the next steps

The missing data is exactly the 3 whole-modality gaps we already knew about and nothing
else, so there's nothing to impute inside a modality. The only real question left is what
to do with those 3 patients when a model needs a modality they don't have. For RNA-based
models that would mean 153 usable patients instead of 155, and for CNA-based models 154.
That's a modeling decision for the per-fold steps, not something step 7 should settle.

## Open

- The 3 GDC manifest checksum mismatches from 2026-09-22 are still unresolved and
  unrelated to this.
- This entry lives in its own file because the worktree this ran in only had the older
  single-file logbook. When it gets merged back, the CONTEXT.md status table needs a line
  saying step 7 is done.
