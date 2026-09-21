# Raw data acquisition log — 2026-09-13

First logbook entry (spec §8 step 5). Covers steps 1–5 of the acquisition plan.
Everything in this folder is archived exactly as received, before any editing.

## Step 1 — Confirm access

cBioPortal REST API, GitHub datahub, and the GDC API were all reachable with no
credentials. No dbGaP/controlled-access request needed — nothing here touches
raw BAM/germline VCF.

## Step 2 — Download from cBioPortal (study: `sarc_tcga_pan_can_atlas_2018`)

| File | Source | Bytes | SHA-256 |
|---|---|---|---|
| `data_clinical_patient.txt` | datahub GitHub (git-lfs) | 78,264 | `356d91b9…` |
| `data_clinical_sample.txt` | datahub GitHub (git-lfs) | 52,542 | `ef919038…` |
| `data_cna.txt` | datahub GitHub (git-lfs) | 14,653,216 | `448d3c48…` |
| `data_mrna_seq_v2_rsem.txt` | datahub GitHub (git-lfs) | 35,891,324 | `a7f3d922…` |
| `data_mutations_api.json` | cBioPortal REST API (substitute, see below) | 14,874,210 | `5adea7b4…` |

Full checksums in `CHECKSUMS.sha256`.

**Deviation — `data_mutations.txt` unavailable via the datahub mirror.** The
GitHub datahub repo's git-lfs pointer for `data_mutations.txt` resolves to oid
`0191ae40…` (32,315,099 bytes), but GitHub's LFS batch API returns `404 Object
does not exist on the server` for that oid — confirmed on two separate
requests a few seconds apart, so not a transient blip. The other four files
(including the larger RSEM file) resolved fine, so this looks like a gap
specific to that one LFS object in the mirror, not a general access problem.

Fallback: pulled the same mutation calls directly from the cBioPortal REST API
(`POST /api/molecular-profiles/sarc_tcga_pan_can_atlas_2018_mutations/mutations/fetch`,
`sampleListId=sarc_tcga_pan_can_atlas_2018_sequenced`, `projection=DETAILED`).
Returned 17,393 mutation records across 234 distinct sample IDs, saved as
`data_mutations_api.json`. This is row-equivalent DETAILED-projection JSON, not
the MAF flat file — whoever does the merge in step 6 will need to pivot this
JSON into the N×G binary indicator matrix instead of reading a MAF directly.
Fields present per record include `sampleId`, `patientId`, `gene.hugoGeneSymbol`,
`mutationType`, `proteinChange`, `variantType` — enough to build the same
indicator matrix the original plan called for.

Note the 234-distinct-sample count vs. 255 total samples in the study: not
necessarily a bug — a sample with zero called mutations in this profile
wouldn't produce any records in a per-mutation-row API response. Worth
confirming during step 7 (missingness verification) rather than assuming
either explanation.

## Step 3 — Cross-check against GDC (project: `TCGA-SARC`)

Distinct-case counts from the GDC API (`/cases` endpoint, `pagination.total`,
not the facet-bucket count which caps at 200):

| Data type | GDC distinct cases | cBioPortal sample count |
|---|---|---|
| RNA-Seq | 259 | 253 (`mrnaRnaSeqV2SampleCount`) |
| Genotyping Array (CNA) | 261 | 253 (`cnaSampleCount`) |
| MAF (mutations) | 255 | 255 patients in `data_clinical_patient.txt` |
| All cases in project | 261 | 255 (`allSampleCount`, cBioPortal study API) |

GDC's total of 261 cases matches the spec's stated N=261 total annotated
tumors. The small gaps between GDC's per-modality case counts and
cBioPortal's per-modality sample counts (259/261 vs. 253) are expected —
cBioPortal's PanCancer Atlas import excludes a handful of cases per platform
for QC reasons; this is a known, documented difference between the two
portals, not an error in either. File-level GDC manifests (not just counts)
saved under `gdc_crosscheck/` for anyone who wants to inspect specific
case-level gaps later.

**Worth flagging now, for step 6/7 later:** cBioPortal's `SUBTYPE` column in
`data_clinical_patient.txt` (a curated molecular-subtype field) only labels
83 patients `SARC_LMS` and 46 `SARC_DDLPS` — well short of the spec's
n=105/n=58. The `ICD_O_3_HISTOLOGY` column tells a different story: code
`8858/3` (dedifferentiated liposarcoma) gives exactly 58 patients, matching
the spec's DDLPS count exactly, but code `8890/3` (leiomyosarcoma, NOS) gives
97, not 105 — so LMS likely needs one or two additional histology codes (e.g.
an epithelioid/myxoid LMS variant code) folded in to reach the spec's count.
**Do not use the `SUBTYPE` column for the LMS-vs-DDLPS cohort definition in
step 6 — use `ICD_O_3_HISTOLOGY`, and confirm the exact code set that sums to
105 before finalizing the cohort.**

## Step 4 — GTEx healthy-tissue layer

Skipped. Per spec §2, this phase is LMS-vs-DDLPS only; the GTEx layer is
explicitly optional and scoped to a future phase. Nothing downloaded.

## Step 5 — Archive

This folder (`data/raw/2026-09-13_cbioportal/`) is the archive: every file
above is stored exactly as received (JSON substitute noted as such, not
disguised as the original MAF format), with SHA-256 checksums in
`CHECKSUMS.sha256`. This is the reference point for anything downstream that
looks wrong.

## Addendum — 2026-09-13, later same day: cohort-restricted completeness check

A follow-up question came in: does the whole-study "251/255 samples have
complete mutation+CNA+expression, 255/255 have methylation" figure actually
hold once restricted to just the 163 LMS+DDLPS patients, or is that an
assumption riding on the whole-study number? Checked directly against the
files already archived above (not re-downloaded — they were already here).

Confirmed the whole-study figures first (`sarc_tcga_pan_can_atlas_2018_3way_complete`
sample list = 251 samples; `..._methylation_all` = 255 samples — both match).

Restricting to the LMS+DDLPS cohort surfaced the open item flagged in the
Step 3 note above: **there is no single cBioPortal column that reproduces the
spec's exact 105/58 counts**, so the check was run under both candidate
definitions:

| Cohort definition | LMS n | DDLPS n | Combined n | 3-way-complete | Methylation |
|---|---|---|---|---|---|
| `CANCER_TYPE_DETAILED` (clinical_sample.txt) | 100 | 59 | 159 | 156 (98.1%) | 159 (100%) |
| `ICD_O_3_HISTOLOGY` (clinical_patient.txt) | 97 | 58 | 155 | 152 (98.1%) | 155 (100%) |

Both give ~98.1% — consistent with the whole-study rate, so the "likely most
of the 163 fall inside the complete group" assumption holds up under actual
checking rather than staying an assumption. The same 3 samples are missing
the full trio under either definition:

- `TCGA-DX-A48V-01` — has mutation + CNA, **missing RNA-seq**
- `TCGA-DX-A6BK-01` — has mutation + CNA, **missing RNA-seq**
- `TCGA-WK-A8XZ-01` — has mutation + RNA-seq, **missing CNA**

Neither definition reaches the spec's combined n=163 — this remains open
(see §4 of `spec.md`, now updated with the same caveat and a decision needed
before step 6 locks in the cohort).

## Correction — download status

An earlier message in this project claimed "nothing has been downloaded into
a working file yet." That's not accurate as of this log: the five files
listed at the top of this note (four raw cBioPortal files + the mutations
API substitute) were already on disk with verified checksums before that
message arrived, and the completeness check just above was run against those
on-disk files, not fresh API calls standing in for a download. Re-verified
via `shasum -a 256 -c CHECKSUMS.sha256` at the time of this addendum — all
files still present and unchanged.

## Addendum — 2026-09-13, later: hunt for the source of the spec's 105/58 counts

Went looking for the original publication's subtyping table to resolve the
cohort-definition gap above. Checked three candidate sources; none reproduce
the spec's 105 LMS / 58 DDLPS / 261-total breakdown:

1. **Cell 2017 TCGA-SARC paper** (Abeshouse et al., DOI
   10.1016/j.cell.2017.10.014, PMC5693358) — the original TCGA sarcoma
   genomics paper with expert-pathology-reviewed subtypes. States **206**
   total sarcomas: 80 LMS (53 soft-tissue + **27 uterine**), 50 DDLPS, 44 UPS,
   17 MFS, 10 SS, 5 MPNST. Smaller N than the PanCanAtlas's 261, so not the
   source of the spec's counts. (CORRECTION 2026-09-22: this line originally
   called the uterine LMS "out of scope for TCGA-SARC, which is soft-tissue
   only". That was wrong — uterine LMS ARE in TCGA-SARC. See the
   uterine-site confound addendum at the end of this file.)
2. **GDC clinical fields directly** (`diagnoses.primary_diagnosis`,
   `disease_type`) queried for all 261 TCGA-SARC cases. Closest hits:
   `disease_type = "Nerve Sheath Tumors"` = 9 (exact match to spec's MPNST),
   `primary_diagnosis = "Dedifferentiated liposarcoma"` = 51 (matches spec's
   **UPS** count, not DDLPS — likely coincidence, not a real correspondence).
   Nothing reproduces 105 LMS or 58 DDLPS together as a pair.
3. **Published ML papers on this same cohort** — an Annals of Oncology deep
   learning paper (Fahmy et al.) uses 240 TCGA-SARC patients across 5
   subtypes (no MPNST), no exact per-subtype counts surfaced. A different
   gene-signature paper cites "104 LMS" from TCGA — close to but not 105.

**Conclusion: the spec's 105/58 figures don't trace to any external source
found so far.** Combined with the on-disk cBioPortal data (which tops out at
100 LMS / 59 DDLPS under `CANCER_TYPE_DETAILED`, or 97 LMS / 58 DDLPS under
`ICD_O_3_HISTOLOGY`), the most defensible reading is that 105/58 was either
(a) from a source not yet located — possibly cited in the original
`.docx` protocol document itself, worth checking there directly, or (b) an
unverified figure that was carried through the original protocol without a
data check, which is exactly the kind of thing this acquisition phase exists
to catch.

**Recommendation, pending user decision:** adopt `ICD_O_3_HISTOLOGY` as the
cohort definition (58 DDLPS matches spec exactly; 97 LMS is the closest
single-field match to 105) and update the working cohort to **N=155**
(97+58), documenting the drop from the spec's planned 163 as a verified
correction rather than an assumption. Flagged to the user rather than
decided unilaterally, since it changes every downstream sample-size number
(including the Experiment 2 ablation points, which assume N up to 130).

## Addendum — 2026-09-13, later still: source of 105/58 found

Traced it. The spec's numbers come from a **legacy GDAC Firehose clinical
freeze dated 2016-01-28** (`Human__TCGA_SARC__MS__Clinical__Clinical__01_28_2016__BI__Clinical__Firehose.tsi`,
mirrored on LinkedOmics — downloaded to `publication_tables/firehose_clinical.tsi`,
262 columns = 261 patients, matching spec's N exactly). Its `histological_type`
row gives: **105 `leiomyosarcoma(lms)`**, 59 `dedifferentiatedliposarcoma`,
51 combined UPS variants (29+21+1), 25 `myxofibrosarcoma`, 9 MPNST, 10
synovial-sarcoma variants. Four of six subtypes (LMS, UPS, MFS, MPNST) match
the spec exactly. This is the source — not a paper, a Firehose data freeze.

**Why DDLPS reads 59 here but 58 in the spec and in today's cBioPortal data:**
patient `TCGA-MO-A47P` is `dedifferentiatedliposarcoma` in the 2016 Firehose
freeze but `ICD_O_3_HISTOLOGY = 8851/3` ("Liposarcoma, well differentiated")
in today's cBioPortal PanCanAtlas import — reclassified at some point between
2016 and now. The spec's 58 already reflects the *current, correct*
classification, not the stale 2016 one. No fix needed for DDLPS.

**Why LMS reads 100 in today's cBioPortal bundle but 105 in the 2016 freeze:**
5 of the 105 patients are simply absent from `sarc_tcga_pan_can_atlas_2018`'s
clinical file entirely — `TCGA-HS-A5N9`, `TCGA-IF-A4AK`, `TCGA-PC-A5DM`,
`TCGA-PC-A5DP`, `TCGA-PT-A8TR`. Checked GDC directly: **all 5 still exist**
there with Genotyping Array (CNA), RNA-Seq, and WXS (mutation source) files
available — they just didn't make it into cBioPortal's specific PanCanAtlas
bundle (likely a cBioPortal-side inclusion-criteria filter at import time, not
a data-quality issue with these 5 cases).

**Bottom line: the spec's N=163 (105 LMS + 58 DDLPS) is real and fully
grounded in public data — every one of the 163 patients exists with complete
core-modality coverage in GDC.** The only complication is *where* to get 5 of
the LMS patients' omics data from:

- **Option A — N=158, cBioPortal-only.** Use only what's already downloaded
  (100 LMS + 58 DDLPS). Zero extra engineering; already-harmonized RSEM/GISTIC2
  files. Deviates from spec's stated 163.
- **Option B — full N=163.** Pull the 5 missing LMS patients' RNA-seq,
  Genotyping Array, and WXS/MAF data directly from GDC and reprocess them to
  match cBioPortal's conventions (RSEM-normalized expression, GISTIC2
  thresholded calls) before merging with the other 158. Matches the spec
  exactly, but GDC's raw files for these are SNP6 CEL / harmonized STAR-Counts,
  not pre-processed RSEM/GISTIC2 — this is real harmonization work (running
  GISTIC2 and matching TCGA's RSEM pipeline), not a trivial file pull.

Not deciding this unilaterally — flagged to the user.

## Next (not started)

Step 6 (merge into one working table, LMS-vs-DDLPS scope only) is now
blocked on resolving the cohort-definition gap above, not just on picking
`ICD_O_3_HISTOLOGY` over `SUBTYPE` as previously noted. Step 7 (verify
missingness on the real merged table) follows once that's settled.

## Addendum — 2026-09-22: should data_clinical_patient.txt columns be features? (uterine-site confound)

Checked each clinical column against the label on the ICD_O_3_HISTOLOGY cohort
(97 LMS + 58 DDLPS = 155; in-sample majority-vote accuracy, so optimistic;
always-guess-LMS baseline = 0.626):

- `ICD_O_3_SITE` 0.697 (20 distinct values), `ICD_10` 0.703, `SEX` 0.671,
  `PRIOR_DX` 0.652. Everything else ~0.626 (no signal).
- AJCC stage / PATH_T/N/M / lymph-node / WEIGHT columns are **100% blank** in
  this cohort — unusable.
- AGE: LMS mean 58.9 (sd 11.4) vs DDLPS 63.6 (sd 12.9) — heavy overlap.

**Key finding — uterine confound.** By `ICD_O_3_SITE`, 25 LMS carry `C55.9`
(uterus NOS) and 3 more carry `C54.2`/`C54.9` (myometrium/corpus) — about 28 of
the 97 LMS are uterine, versus 0 of the 58 DDLPS. Site `C48.0` (retroperitoneum)
is 47 DDLPS vs 40 LMS. Sex tracks this: 65 of 97 LMS are female vs 19 of 58
DDLPS. So "where the tumor is" (and sex) partly separates the classes on its
own, and omics features could also pick up uterine-vs-non-uterine tissue-of-
origin signal instead of LMS-vs-DDLPS tumor biology. The spec's "no confound"
claim for this pair (§3) does not account for this.

Decision pending with user: (a) keep omics-only features (no clinical columns
as model inputs); (b) add a clinical-only baseline (site+sex+age) as a
shortcut floor; (c) run a sensitivity analysis excluding uterine-site LMS.
Site-code-based uterine counts should be confirmed against sample-level
`TUMOR_TISSUE_SITE` before relying on the exact number 28.
