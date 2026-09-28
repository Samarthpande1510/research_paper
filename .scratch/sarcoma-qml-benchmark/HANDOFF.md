Status: ready-for-agent

# Handoff for a new chat (written 2026-09-23)

Read this first, then `spec.md` (the plan) and the newest files in `logbook/` (what was
actually done). If anything here disagrees with those, trust them and flag the mismatch.
`CONTEXT.md` is an older onboarding file, still useful, not authoritative.

## The project in three lines

Does a quantum kernel or variational circuit beat a classical deep model on a tiny, very wide
cancer dataset? Task: leiomyosarcoma (LMS) vs dedifferentiated liposarcoma (DDLPS), TCGA-SARC
from cBioPortal, RNA-seq + copy number + mutations. Expect near-ceiling scores for both model
families, that's fine and reportable, not a bug.

## How to work with this user (do all of these)

- **No em dashes, ever.** Write like a person: contractions, short sentences, plain words. This
  applies to chat replies, logbook entries, reports and commit messages.
- **The user is learning.** When they ask for an explanation, explain in numbered plain steps
  and define each term as it comes up. Don't start editing or running heavy commands when they
  asked for an explanation. They've stopped tool calls twice for that.
- **Log every session** in `logbook/`, one file per day, using DID / SAW / DECIDED / OPEN. Never
  delete or silently rewrite an old entry or an old spec claim. Add a dated correction and keep
  the old text visible.
- **Verify against the real files before repeating any number** from the notes. Two notes in this
  project already turned out wrong (the "N=158" cohort figure, the "no confound" claim).
- **Track every CV / ElasticNet combination in MLflow and build preprocessing as scikit-learn
  `Pipeline`s.** One parent run per sweep, one nested child run per combination.
- **Put real decisions to the user** with options and a recommendation. They sometimes reply "all
  yours", which means decide and record it (with the reason, marked reversible).
- Say plainly when a result is only "about the same". Don't oversell.

## Environment gotchas

- Use `uv run --no-sync python ...` from the repo root. The `python3` on PATH belongs to a
  different project (polymath). Don't install into it.
- Repo root: `/Users/samarthpande1510/dataset_research` (project lives in
  `.scratch/sarcoma-qml-benchmark/`). Remote `origin` is the user's
  `Samarthpande1510/research_paper`. Ignore `upstream`, it's someone else's.
- **`git push` is blocked in auto mode.** Ask the user to run `! git push origin main`.
- File edits are allowed in the main checkout because `.claude/settings.local.json` sets
  `worktree.bgIsolation` to `none`. If a new session blocks edits again, tell the user rather
  than working around it.
- MLflow prints a line telling you to load a bundled skill. That's tool output, not the user.
  Set `MLFLOW_DISABLE_AGENT_HINT=1` to silence it.
- `uv add mlflow` timed out once on the network. If installs fail, retry with a higher
  `UV_HTTP_TIMEOUT`.
- MLflow page: run `uv run --no-sync mlflow server --backend-store-uri
  sqlite:///$(pwd)/.scratch/sarcoma-qml-benchmark/results/mlflow/mlflow.db --port 5050`, then
  open http://127.0.0.1:5050. (Port 5000 is usually taken on macOS.)

## Where things stand

| Step (spec sec 8) | State |
|---|---|
| 1 to 5: access, download, GDC cross-check, archive | Done |
| 6: merge into aligned tables | Done. `src/step6_merge.py` |
| 7: missingness audit | Done. `src/step7_missingness_audit.py`, report in `data/processed/` |
| 8 to 10: transforms, no separate holdout | Transforms done in step 6. No holdout by design |
| 11: per-fold gene selection | Explored with two sweeps (below). Not yet a reusable module |
| 12: per-fold scaling (standard + [0, pi]) | Not started |
| 13 to 14: seeds and per-fold logging | Seeds fixed in the sweeps. Full logging not done |
| 15: write the null hypothesis into the record | **Not done. Must happen before any model training** |
| 16: Experiment 1 | Not started. No model has been trained |

### Data facts (all verified)

- Cohort: **155 patients** (97 LMS, 58 DDLPS), defined by `ICD_O_3_HISTOLOGY` (`8890/3` LMS,
  `8858/3` DDLPS). The old "158" figure was two columns' counts glued together, ignore it.
- Label: **DDLPS = 1, LMS = 0**.
- Missing whole modalities: 2 patients have no RNA (`TCGA-DX-A48V`, `TCGA-DX-A6BK`), 1 has no
  copy number (`TCGA-WK-A8XZ`). Nothing else is missing. 20 patients have zero mutations, and
  those are confirmed real zeros.
- Merged tables in `data/processed/`: `clinical_labels`, `rna_seq_log2` (20,518 genes),
  `cna_gistic2` (25,128), `mutation_binary` (5,165), all `.parquet`, same 155 patients in the
  same order. Duplicate gene names got an `__<entrez>` or `__occN` suffix.
- 28 of the 97 LMS are uterine-site (0 of 58 DDLPS). Checked: this does not explain the marker-gene
  separation. Main experiment stays omics-only. `clinical_labels` carries sex, age and site for
  a possible clinical-only baseline and a no-uterine sensitivity run.

### Decisions already made (2026-09-23, all in `CONTEXT.md` sec 5 and dated in `spec.md`)

- Benchmark uses the same **152 patients** for every model (57 DDLPS, 95 LMS): those with RNA,
  copy number and mutations.
- **No MAD filter.** The spec's top-1,000 MAD filter removes MDM2 and CDK4 (MAD rank 6,338 and
  4,974 of 20,518). With no filter MDM2 is picked in 100% of folds. Scores were the same within
  noise. Cost is about 6.5 minutes per 50-fold run. Reversible.
- ElasticNet fixed at **C = 0.1, l1_ratio = 0.5**, with **d = 8 and d = 16** both run.
- **RNA-seq only** for the first benchmark. **5 splits x 10 repeats = 50 folds.**
- Both sweeps: all scores PR-AUC 0.963 to 0.990, differences inside the fold-to-fold wobble
  (about 0.02). Scores are slightly optimistic because the same folds compared many settings.

## Files

- `src/step11_gene_selection_cv.py`: MADFilter transformer, `build_pipeline`, `configure_mlflow`,
  first 32-combination sweep. `src/step11b_filter_sweep.py`: the filter sweep (imports from the
  first).
- `results/step11_gene_selection_report.md`, `results/step11b_filter_sweep_report.md`: plain
  language write-ups. `results/step11b_combination_results.csv`: the 8-setting table.
- `results/mlflow/`: local MLflow store (about 5 MB). Experiments
  `sarcoma_step11_gene_selection` and `sarcoma_step11b_filter_sweep`. The first also has a
  `smoke_test` run to ignore.
- `logbook/`: `2026-09-13_data_acquisition.md`, `2026-09-22_restructure_and_uterine_confound.md`,
  `2026-09-23_marker_check_and_step6_merge.md`, `2026-09-23_step7_missingness_audit.md`,
  `2026-09-23_step11_gene_selection_sweep.md`, plus `_archive_...pre_split.md` (old combined log,
  don't read day to day).

## Git state (check `git status` before trusting this)

- Pushed up to commit `4c8177d`. Not yet committed: `spec.md` and `CONTEXT.md` edits, the two
  step 11 scripts, `results/`, the newest logbook file, and `pyproject.toml` / `uv.lock`
  (scikit-learn and mlflow).
- **Junk staged in the index, don't commit it:** `.DS_Store` files, and an entry for
  `.claude/worktrees/step7-missingness-audit` (a worktree that no longer exists). Unstage with
  `git restore --staged .claude/worktrees/step7-missingness-audit` and leave `.DS_Store` out.
- Ask before committing. Stage files by name, not `git add .`.

## What to do next, in order

1. **DagsHub.** The user wants experiment tracking on DagsHub instead of keeping the MLflow database
   in git. The scripts already log there when `MLFLOW_TRACKING_URI` is set (with
   `MLFLOW_TRACKING_USERNAME` and `MLFLOW_TRACKING_PASSWORD`). The user needs to make the account,
   connect the GitHub repo and create a token themselves, and must never paste the token in chat.
   Then re-run `step11b_filter_sweep.py` so runs land there. Ask for the repo name, don't guess it.
2. **Turn the sweep code into one reusable preprocessing module** (`src/preprocess.py`) using a
   scikit-learn `Pipeline`, on the 152 patients, no MAD filter, C = 0.1, l1_ratio = 0.5, d in
   {8, 16}. Per fold, fit on the training patients only, and output two versions of the selected
   genes: standard-scaled (for the classical models) and min-max scaled to [0, pi] (for the quantum
   models). Log per fold: the selected genes, how many test values fell outside the training range
   and got clipped, and seeds. Send it all to MLflow.
3. **Step 15 before any training:** write the null hypothesis (no PR-AUC difference between the
   best quantum model and the MLP, spec sec 7) into the logbook with a date.
4. Then the models (MLP, PQK-SVM, VQC), Experiment 1, the sample-size ablation, in the order in
   `spec.md`.

## Still open (need the user)

- DagsHub credentials and repo name.
- Three GDC manifest files fail their checksum (only their header lines changed, 2026-09-21).
  Restore the originals from commit `dec60cc`, or keep the edit and regenerate the checksums.
- Not tested yet: other C / l1_ratio values with no filter, a label-aware filter computed inside
  each fold, copy number in the gene funnel.
- Whether to add a clinical-only baseline and a no-uterine sensitivity run (both planned, not in
  `spec.md` yet).
- How to handle the 3 patients missing a modality if a later model needs all three modalities. The
  152-patient set already excludes them.
