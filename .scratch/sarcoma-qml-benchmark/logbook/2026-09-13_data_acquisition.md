# Data acquisition, 2026-09-13

First logbook entry (spec §8 step 5). Covers steps 1 through 5 of the acquisition plan,
plus a few same-day follow-ups after the initial download. Full original wording (before
the 2026-09-23 style pass) is preserved in `_archive_2026-09-13_full_log_pre_split.md`
if you ever need it.

## Step 1: confirm access

Checked whether we could actually reach the data: cBioPortal's REST API, the GitHub
datahub, and the GDC API all worked with no login needed. We don't need dbGaP
controlled-access approval either, since nothing in this plan touches raw BAM files or
germline VCFs.

## Step 2: download from cBioPortal

Pulled five files from the `sarc_tcga_pan_can_atlas_2018` study:

| File | Source | Bytes | SHA-256 |
|---|---|---|---|
| `data_clinical_patient.txt` | datahub GitHub (git-lfs) | 78,264 | `356d91b9…` |
| `data_clinical_sample.txt` | datahub GitHub (git-lfs) | 52,542 | `ef919038…` |
| `data_cna.txt` | datahub GitHub (git-lfs) | 14,653,216 | `448d3c48…` |
| `data_mrna_seq_v2_rsem.txt` | datahub GitHub (git-lfs) | 35,891,324 | `a7f3d922…` |
| `data_mutations_api.json` | cBioPortal REST API (substitute, see below) | 14,874,210 | `5adea7b4…` |

Full checksums in `CHECKSUMS.sha256`.

One thing worth calling out: `data_mutations.txt` wasn't actually available through the
datahub mirror. Its git-lfs pointer resolves to an object ID that GitHub's LFS API just
returns a 404 for, and I checked twice a few seconds apart to rule out a fluke.
Everything else downloaded fine, including the much bigger RSEM file, so this looks like
a gap with that one file specifically, not a broader access problem. Worked around it by
pulling the same mutation calls straight from the cBioPortal REST API instead (17,393
records across 234 samples), saved as `data_mutations_api.json`. It's the same
information, just row-by-row JSON instead of a MAF file, so whoever writes the step 6
merge needs to pivot this into a patient-by-gene binary matrix rather than parsing a MAF
directly. (Update: this is exactly what `src/step6_merge.py` does, see the 2026-09-23
entry.)

Also noticed 234 distinct samples in that file vs. 255 total samples in the study.
That's not necessarily a problem: a sample with zero mutations in this profile just
wouldn't produce any rows in the API response. (Update: confirmed 2026-09-23, see that
entry, all 20 cohort patients in this situation are real zeros, not missing data.)

## Step 3: cross-check against GDC

Compared case counts between GDC and cBioPortal for the TCGA-SARC project:

| Data type | GDC distinct cases | cBioPortal sample count |
|---|---|---|
| RNA-Seq | 259 | 253 (`mrnaRnaSeqV2SampleCount`) |
| Genotyping Array (CNA) | 261 | 253 (`cnaSampleCount`) |
| MAF (mutations) | 255 | 255 patients in `data_clinical_patient.txt` |
| All cases in project | 261 | 255 (`allSampleCount`, cBioPortal study API) |

GDC's total of 261 cases matches what the spec expects. The small per-modality gaps
(259-261 in GDC vs. 253 in cBioPortal) are expected: cBioPortal's PanCancer Atlas import
drops a handful of cases per platform for QC reasons, and that's a known, documented
difference between the two portals, not a mistake on either side. File-level GDC
manifests are saved under `gdc_crosscheck/` for anyone who wants to check specific gaps.

Bigger thing worth flagging: the `SUBTYPE` column in the clinical file only labels 83
patients as LMS and 46 as DDLPS, well short of the spec's 105/58. The `ICD_O_3_HISTOLOGY`
column tells a different story: code `8858/3` gives exactly 58 DDLPS patients, matching
the spec exactly, but code `8890/3` only gives 97 LMS, not 105. Don't use `SUBTYPE` for
the cohort definition. Use `ICD_O_3_HISTOLOGY`. (Update: this is exactly what the step 6
merge does, see the 2026-09-23 entry, the cohort landed at N=155.)

## Step 4: GTEx layer

Skipped, on purpose. This phase is LMS vs. DDLPS only, and GTEx is explicitly out of
scope until a later phase. Nothing downloaded for it.

## Step 5: archive

Everything above is sitting in `data/raw/2026-09-13_cbioportal/`, stored exactly as it
was received (the JSON substitute is clearly noted as a substitute, not disguised as a
MAF), with SHA-256 checksums recorded. This folder is the reference point if anything
downstream looks off later.

## Same-day addendum: does the cohort actually have complete data?

Someone asked whether the whole-study figure ("251 of 255 samples have complete
mutation, CNA, and expression data, 255 of 255 have methylation") still holds once you
restrict to just the 163 LMS/DDLPS patients, or whether that's an assumption riding on
the whole-study number. Checked it directly against the files already on disk.

The whole-study numbers checked out first (251 and 255, matching the official cBioPortal
sample lists). But restricting to the LMS/DDLPS cohort ran straight into the problem from
Step 3: there's no single column that gives exactly 105/58. Ran the completeness check
under both candidate definitions:

| Cohort definition | LMS n | DDLPS n | Combined n | 3-way-complete | Methylation |
|---|---|---|---|---|---|
| `CANCER_TYPE_DETAILED` (clinical_sample.txt) | 100 | 59 | 159 | 156 (98.1%) | 159 (100%) |
| `ICD_O_3_HISTOLOGY` (clinical_patient.txt) | 97 | 58 | 155 | 152 (98.1%) | 155 (100%) |

Both land around 98.1% complete, basically the same as the whole-study rate. The same
three samples are missing one modality under either definition: `TCGA-DX-A48V-01` and
`TCGA-DX-A6BK-01` are missing RNA-seq, and `TCGA-WK-A8XZ-01` is missing CNA. Neither
definition gets to 163.

## Correction: download status

Somewhere earlier in this project I said "nothing has been downloaded into a working
file yet." That wasn't true: the five files listed above were already on disk with
verified checksums before that message went out, and the completeness check above ran
against those files, not fresh API calls. Re-ran the checksum verification to be sure.
Everything still matched.

## Later same day: where did 105/58 actually come from?

Went looking for whatever source the spec's 105 LMS / 58 DDLPS numbers trace back to.
Checked three places, none of which reproduced it: the original 2017 Cell paper on
TCGA-SARC (206 total sarcomas, 80 LMS including 27 uterine, 50 DDLPS, a different N
entirely), GDC's clinical fields directly (closest hit was MPNST at exactly 9, nothing
for LMS or DDLPS), and a couple of published ML papers using this cohort (close but not
exact numbers). So the spec's figures didn't come from any of the obvious places.

(Correction added 2026-09-22: an earlier draft of this note said uterine LMS cases were
"out of scope for TCGA-SARC." That was wrong, they are in scope. See the
2026-09-22 file for the uterine-confound finding.)

Working guess at the time: adopt `ICD_O_3_HISTOLOGY` as the cohort definition (58 DDLPS
matches exactly, 97 LMS is the closest match to 105) and treat the cohort as N=155,
documenting the drop from 163 as something verified rather than assumed. Didn't decide
this alone since it changes every downstream sample-size number, including the
Experiment 2 ablation points that assume up to 130 training patients. Left it for the
user to weigh in on.

## Still later: found the source of 105/58

Traced it. The spec's numbers come from a 2016 GDAC Firehose clinical freeze, not a
paper (`Human__TCGA_SARC__MS__Clinical__Clinical__01_28_2016__BI__Clinical__Firehose.tsi`,
mirrored on LinkedOmics, downloaded to `publication_tables/firehose_clinical.tsi`, 262
columns = 261 patients, matching the spec's N exactly). Its `histological_type` column
gives 105 LMS, 59 dedifferentiated liposarcoma, and matches four of six subtypes in the
spec exactly.

Why DDLPS is 59 there but 58 in the spec and in today's cBioPortal data: one patient
(`TCGA-MO-A47P`) was classified as DDLPS in the 2016 freeze but has since been
reclassified to a different liposarcoma subtype in today's data. The spec's 58 already
reflects that correction, so nothing needs fixing there.

Why LMS is 100 in today's cBioPortal bundle but 105 in the 2016 freeze: five of those
105 patients (`TCGA-HS-A5N9`, `TCGA-IF-A4AK`, `TCGA-PC-A5DM`, `TCGA-PC-A5DP`,
`TCGA-PT-A8TR`) simply aren't in `sarc_tcga_pan_can_atlas_2018`'s clinical file at all.
Checked GDC directly and all five still exist there with full CNA, RNA-seq, and mutation
data, they just didn't make it into cBioPortal's specific import (probably an inclusion
filter cBioPortal applied at import time, not a real data problem with those five cases).

So the bottom line at the time: the spec's N=163 is real, grounded in actual public
data, every one of the 163 patients exists with full coverage in GDC. The open question
was where to get five of the LMS patients' data from: stick with N=158 using only what's
already downloaded (zero extra work), or pull those five patients' raw files from GDC
and reprocess them to match cBioPortal's conventions to reach the full 163 (real extra
engineering, matching TCGA's RSEM and GISTIC2 pipelines isn't trivial). Flagged for the
user rather than decided alone.

**Resolved 2026-09-23** (see `2026-09-23_marker_check_and_step6_merge.md`): went with
N=155, not N=158 or N=163. The "N=158 (100+58)" figure above turned out to not be
reproducible from any single column either, it mixed two different columns' counts.
`ICD_O_3_HISTOLOGY` alone gives 97 LMS, not 100.

## Next steps, as of this point in the project

Step 6 (the merge) was blocked on resolving the cohort-definition question above, not
just on choosing `ICD_O_3_HISTOLOGY` over `SUBTYPE`. Step 7 would follow once that was
settled. (Superseded: step 6 is done, see the 2026-09-23 file.)
