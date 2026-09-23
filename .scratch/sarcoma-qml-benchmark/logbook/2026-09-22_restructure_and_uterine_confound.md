# Restructure and uterine-site confound, 2026-09-22

Two things happened this day: found a real confound in the clinical data, and cleaned
up the project's folder layout while checking the raw archive was still intact. Original
formal-voice wording is preserved in `_archive_2026-09-13_full_log_pre_split.md` if
needed.

## Should clinical columns be used as features? (the uterine-site confound)

Checked every clinical column against the label, using the `ICD_O_3_HISTOLOGY`-based
cohort (97 LMS, 58 DDLPS). This is just an in-sample majority-vote check, so treat the
numbers as optimistic, not a real cross-validated result. A few columns showed some
signal (`ICD_O_3_SITE` at 0.697, `ICD_10` at 0.703, `SEX` at 0.671, `PRIOR_DX` at 0.652),
everything else was around the always-guess-LMS baseline of 0.626, meaning no real
signal. The staging columns (AJCC stage, T/N/M, lymph node, weight) are 100% blank in
this cohort and unusable. Age overlaps heavily between the two groups.

The real finding: about 28 of the 97 LMS patients are from a uterine site (25 coded
`C55.9`, 3 more coded `C54.2` or `C54.9`), compared to zero of the 58 DDLPS patients.
Sex tracks this too, 65 of 97 LMS patients are female vs. 19 of 58 DDLPS. So tumor
location and sex partly separate the two classes on their own, which means an omics
model could end up picking up "uterine vs. non-uterine tissue" signal instead of real
LMS-vs-DDLPS tumor biology. The spec's claim that this pair has no confound doesn't
account for this.

Left three options open for the user to decide between: omics-only features, adding a
clinical-only baseline, or running a sensitivity check that excludes the uterine LMS
cases. (Update 2026-09-23: checked whether this confound actually explains the
marker-gene separation the project leans on. It doesn't, see the next file. The confound
is still real for other features and for clinical columns like sex, just not for the
core marker genes.)

## Project restructure and raw-archive integrity check

Set up the proper folder layout from the research guide: `logbook/`, `configs/`, `src/`,
`results/` split per experiment, `figures/`, `paper/`, `data/processed/`. Moved the main
project log from a `NOTES.md` file sitting inside the raw data folder into its proper
place in `logbook/`, since the raw folder should only hold data as received.

While doing that, re-ran the checksum verification and found three files failing: the
GDC manifest files for CNA, MAF, and RNA-seq. Traced it with git: someone changed just
the header line of each file (padding column names with spaces) in a commit from
2026-09-21, the data rows themselves are untouched. I didn't make that edit.

Decided to leave the three files as they are rather than restoring or re-checksumming
without checking with the owner first, since both fixes are easy and the original bytes
are recoverable either way. The impact is cosmetic, these files were only used for
patient-count cross-checks, not for modeling, but the archive is supposed to hold data
exactly as received, so this should get resolved one way or the other.

**Still open as of 2026-09-23**: this checksum mismatch hasn't been resolved yet, and
it's unrelated to the step 6 merge work, see the 2026-09-23 file.
