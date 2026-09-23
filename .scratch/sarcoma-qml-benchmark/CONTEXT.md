Status: ready-for-agent

# Sarcoma QML Benchmark — Onboarding / New-Chat Context

Paste this whole file into a new chat (or point Claude at this path) to resume work with
full context. It is a pointer document, not the source of truth — the source of truth is
`spec.md` (the plan) and `logbook/` (the dated history of what was actually done and why).
If anything here conflicts with those two, trust them over this file and flag the mismatch.

## 1. What this project is, in one paragraph

Testing whether quantum-enhanced feature representations (quantum kernels, variational
circuits) outgeneralize classical deep learning on an ultra-small (N≈160), ultra-wide
(~20,000 genes) cancer classification task: Leiomyosarcoma (LMS) vs. Dedifferentiated
Liposarcoma (DDLPS), from the TCGA-SARC PanCancer Atlas. Full research question, scope,
models, experiments, and statistics are in `spec.md` — read that in full before doing
anything else.

## 2. Where things actually stand right now

Data acquisition (spec.md §8, steps 1–5) and the Step 6 merge are done (2026-09-23).
Step 7 onward (missingness verification on the merged table, per-fold pipeline,
training) have **not** started — no model has been run yet.

| Step | State |
|---|---|
| 1. Confirm access | Done |
| 2. Download from cBioPortal | Done, with one deviation (see §4 below) |
| 3. Cross-check against GDC | Done |
| 4. GTEx layer | Correctly skipped — out of scope for this phase |
| 5. Archive raw downloads | Done, but **3 files currently fail checksum** — see §5, open item 2 |
| 6. Merge into one working table | **Done 2026-09-23.** N=155 (97 LMS + 58 DDLPS), `DDLPS=1`/`LMS=0`. Output: `data/processed/{clinical_labels,rna_seq_log2,cna_gistic2,mutation_binary}.parquet`, one shared patient index (not one flat file — see logbook entry). Script: `src/step6_merge.py`. |
| 7. Verify missingness on real merged table | Partially done as a byproduct of step 6 (3 whole-modality gaps + 20 confirmed-zero mutation patients logged in `step6_merge_manifest.json`); a full step-7 pass over the merged table itself hasn't been run yet |
| 8–16 | Not started |

## 3. Folder layout (as of 2026-09-23)

```
sarcoma-qml-benchmark/
  spec.md                    THE PLAN. Read this first, in full. Edited in place with
                              dated inline notes when something is resolved — never
                              silently rewritten.
  CONTEXT.md                 This file. Onboarding only — not authoritative.
  logbook/
    2026-09-13_data_acquisition.md   The real history: every check run, every number
                                      found, every mistake made and corrected, dated.
                                      ~320 lines as of this writing. Read it, don't just
                                      skim §4 below — the reasoning is there.
  data/
    raw/2026-09-13_cbioportal/       Downloaded files, meant to be read-only. Has
                                      CHECKSUMS.sha256. See §5 open item 2 — 3 files in
                                      here currently fail their checksum.
    processed/                       Empty. Nothing generated yet.
  configs/                   Empty. One settings file per experiment run goes here later.
  src/                       Empty. No code written yet.
  results/
    exp1_full_cohort/        Empty
    exp2_ablation/           Empty
    exp3_noise_sim/          Empty
  figures/                   Empty
  paper/                     Empty
  research_paper_and_logbook_guide.pdf     How to write the paper, keep the logbook,
                                            store results. Read this for HOW to work.
  sarcoma_qml_data_and_methods_guide.pdf   Plain-language explanation of every data
                                            file/column and every QML/classical method
                                            in the plan. Read this for WHAT the data means.
```

## 4. Key resolved decisions (the "why", not just the "what")

These were hard-won — don't re-derive them from scratch, and don't second-guess them
without a new reason. Full detail is in the logbook.

- **The 105 LMS / 58 DDLPS counts trace to a 2016-01-28 GDAC Firehose clinical freeze**,
  not to any current cBioPortal column and not to a published paper. Confirmed by
  downloading that exact file. Today's cBioPortal `sarc_tcga_pan_can_atlas_2018` bundle is
  missing 5 of the 105 LMS patients — they still exist in GDC with full data, just not in
  this specific cBioPortal export. DDLPS's 58 (not 59) is already correct — one patient
  was reclassified out of DDLPS since 2016, and the spec's 58 already reflects that.
- **`data_mutations.txt` doesn't exist in the datahub mirror** (GitHub LFS object 404,
  confirmed twice). Substituted with the equivalent data pulled live from the cBioPortal
  REST API (17,393 mutation records, 234 samples), saved as `data_mutations_api.json` —
  same information, different format (JSON rows, not a MAF flat file). Whoever writes the
  step-6 merge code needs to pivot this JSON into the N×G binary matrix, not parse a MAF.
- **The label comes from `ICD_O_3_HISTOLOGY`** in `data_clinical_patient.txt`
  (`8890/3`=LMS, `8858/3`=DDLPS), not from the `SUBTYPE` column (which is 26% blank) or
  from `CANCER_TYPE_DETAILED` in the sample file (a close but not identical alternative).
- **Uterine-tissue confound, checked and mostly cleared (2026-09-23).** 28 of 97 LMS
  patients are uterine-site (0 of 58 DDLPS are). This does NOT explain the strong
  separation from marker genes (MDM2, CDK4, MYH11, DES, ACTA2) — cross-validated
  single-gene accuracy is basically unchanged (within ~3 points) with those 28 excluded,
  and for the smooth-muscle genes it goes up slightly, the opposite of what a pure
  confound would predict. The uterine confound is still real for generic/non-marker
  features and for clinical columns like sex — it just doesn't explain the core biology.
- **Expect near-ceiling classical performance on Experiment 1.** MDM2 alone gets ~91–94%
  honest cross-validated accuracy as a single feature. This pair (LMS vs DDLPS) was
  deliberately chosen for clean molecular separation, so both quantum and classical
  models scoring very high is the expected, reportable outcome — not a failure of the
  comparison. Report it as such; don't chase a bigger gap that may not exist.
- **Clinical columns are mostly not useful as model features.** Of 38 columns in
  `data_clinical_patient.txt`, 7 are 100% blank in this cohort (staging fields), survival
  columns describe outcomes not tumor type, and the two columns with real signal (site,
  sex) are confound-shaped shortcuts, not tumor biology — see the uterine-confound point
  above. Decision: keep the main experiment omics-only; consider a clinical-only baseline
  and a no-uterine sensitivity run as secondary analyses (not yet added to spec.md).

## 5. Open decisions — need a human call before proceeding

1. **RESOLVED 2026-09-23: cohort is N=155, cBioPortal-only, not N=158.** The "N=158
   (100 LMS + 58 DDLPS)" figure below this line was never actually reproducible from the
   data: `100` comes from querying `CANCER_TYPE_DETAILED` (which gives 59 DDLPS, not 58),
   while `58` comes from querying `ICD_O_3_HISTOLOGY` (which gives 97 LMS, not 100) — two
   different columns' counts stitched together, never queried as one consistent filter.
   Re-verified directly against `data_clinical_patient.txt`: `ICD_O_3_HISTOLOGY` —
   §4's already-resolved label source — gives **97 LMS + 58 DDLPS = 155**. Decision: use
   N=155 for step 6. The N=163 (full spec, GDC-reprocessed) option is not being pursued
   for this phase. Original text preserved below, struck through in spirit but left
   visible per the "never silently rewrite" habit in §6.
   ~~N=158 (100 LMS + 58 DDLPS) uses only what's already downloaded, zero extra
   engineering. N=163 (105 + 58) matches the spec exactly but requires pulling 5 LMS
   patients' raw files from GDC and reprocessing them to match cBioPortal's RSEM/GISTIC2
   conventions — real harmonization work. This blocks step 6 (the merge) and hasn't been
   decided yet.~~
2. **3 GDC manifest files fail their checksum.** `gdc_crosscheck/gdc_manifest_{cna,maf,rnaseq}.tsv`
   were edited (header whitespace only, confirmed via git diff against the original commit —
   data rows are untouched) by something other than this session, in a commit dated
   2026-09-21. Two ways to resolve: restore the original bytes, or keep the edit and
   regenerate the checksums. Not yet decided. Cosmetic either way — these files are only
   used for patient-count cross-checks, not modeling.

## 6. Working habits to keep — do not skip these

Full reasoning for each is in `research_paper_and_logbook_guide.pdf`. Short version:

- **Logbook, not memory.** Every session that changes something or finds something, add a
  dated entry to a file in `logbook/` — goal, what you did, the actual numbers you saw,
  the decision and why, problems, open questions, next step. Write it the same session.
- **Never delete or silently rewrite a past logbook entry or a past spec.md claim.** If a
  past claim turns out wrong (this has already happened twice — see §7), add a new dated
  correction next to it and leave the old text visible. This is not optional politeness —
  it's what makes the record trustworthy later.
- **Verify against real data before asserting.** Every major finding in this project so
  far came from actually running a check against the files on disk (or a live API), not
  from recalling a paper or trusting a claim secondhand — including a senior/PhD friend's
  claim in this same project, which got checked and mostly held up, but only because it
  was checked rather than accepted.
- **Never overwrite a results run.** One dated, never-reused folder per run under
  `results/`, holding config + seeds + git commit + per-fold metrics + per-patient
  predictions. Raw data in `data/raw/` is read-only; work happens on copies.
- **Pre-register, don't rationalize after the fact.** The spec's null hypothesis (§7) is
  written down before training starts and doesn't get quietly swapped for a more exciting
  claim if the first result looks unexciting. If the scope of the paper's contribution
  changes (e.g. shifting emphasis to circuit design because accuracy saturates), that
  decision gets written into spec.md now, with a reason — not decided silently after
  seeing disappointing numbers.

## 7. Mistakes already made in this project — don't repeat them

Listed so a new session doesn't have to rediscover them the hard way:

- Wrongly claimed uterine LMS were "out of scope for TCGA-SARC" — they are in scope; this
  was corrected in the logbook with a dated note, not silently fixed.
- Wrongly claimed "nothing has been downloaded" when 5 files were already archived on
  disk with verified checksums — corrected the same way.
- Wrongly claimed "all sources are open access, no credentials needed" as a blanket
  statement — true for the cBioPortal files actually downloaded, but GDC's own file
  manifests show most GDC files (mutations, RNA-seq, CNA) are `controlled` access, not
  `open`. Only checked file *lists*, never downloaded the GDC files themselves.

## 8. Reference material already gathered

Two reading lists exist in this chat's history (not yet saved as files) covering:
data-leakage/CV methodology papers, classical tabular-ML baselines, quantum kernel theory
(Schuld & Killoran, Huang, Thanasilp, Bowles et al., bandwidth papers), and evaluation
statistics (Nadeau & Bengio corrected t-test, PR-AUC vs ROC, MCC). Ask for them again if
starting fresh and they aren't in the new chat's context — they were all verified against
live search results, not recalled from training data.

## 9. Suggested next step

Open decision #1 in §5 (N=158 vs N=163) is resolved — N=155, step 6 is done (see §2).
Next: run a full step-7 missingness pass over the merged parquet tables in
`data/processed/` (the per-modality gaps are already logged, but the general "count
what's actually missing, don't assume" check from spec.md step 7 hasn't been run against
the merged table as its own artifact yet). Open decision #2 in §5 (checksum mismatch on
3 GDC manifest files) is still unresolved and independent of this.
