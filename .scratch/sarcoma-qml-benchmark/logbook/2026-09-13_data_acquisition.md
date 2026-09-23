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

## Entry — 2026-09-22: project restructure + raw-archive integrity check

DID:      Created the folder layout from the research guide (logbook/, configs/,
          src/, results/exp1_full_cohort, exp2_ablation, exp3_noise_sim, figures/,
          paper/, data/processed/). Moved this file from
          data/raw/2026-09-13_cbioportal/NOTES.md to
          logbook/2026-09-13_data_acquisition.md (raw archive should hold only
          data as received). Nothing else referenced NOTES.md by name.
SAW:      Re-ran `shasum -a 256 -c CHECKSUMS.sha256`. 5 data files OK.
          **3 files FAIL:** gdc_crosscheck/gdc_manifest_{cna,maf,rnaseq}.tsv.
          Cause traced with git: the versions committed on 2026-09-13
          (commit dec60cc) match CHECKSUMS.sha256 exactly. Commit fe2c63d
          (2026-09-21, "updated version with some data preprocessing")
          changed ONLY the header line of each file, padding column names
          with spaces. Data rows are unchanged (line counts identical;
          identical after stripping whitespace). I did not make this edit.
DECIDED:  Left the three files as they are — not restoring or re-checksumming
          without the owner's say-so. Both fixes are safe: original bytes are
          recoverable from dec60cc.
OPEN:     Restore the as-received manifests (keeps the archive honest) OR
          record the edit as a deliberate change and regenerate the checksums.
NOTE:     Impact is cosmetic (header whitespace only); the manifests were used
          only for patient-count cross-checks. But the archive rule is
          "exactly as received", so it should be resolved one way or the other.

## Entry — 2026-09-23: uterine-confound check on the MYH11/MDM2/CDK4 marker separation

GOAL:     A PhD-advisor friend's review said this LMS-vs-DDLPS task is likely
          near-linearly separable via a few known marker genes (log2 gaps
          4.0-7.0), making a quantum kernel unnecessary. Checked that claim
          against the real RSEM data, then checked whether it survives
          dropping the 28 uterine-site LMS patients flagged in the
          2026-09-22 uterine-confound addendum.
DID:      Computed log2(RSEM+1) median gap and honest 5-fold CV accuracy
          (threshold refit on train fold only, averaged over 10 reshuffles)
          for MYH11, MDM2, CDK4, DES, ACTA2 — first on the full 155-patient
          cohort, then again after removing the 28 uterine-site LMS (using
          ICD_O_3_SITE; cross-checked independently against the free-text
          TUMOR_TISSUE_SITE field on all 155 samples — the two agree exactly,
          0 discrepancies).
SAW:      Full cohort (97 LMS/58 DDLPS): MYH11 CV acc 0.848, MDM2 0.936,
          CDK4 0.905, DES 0.752, ACTA2 0.819.
          Non-uterine LMS only (69 LMS/58 DDLPS): MYH11 0.882, MDM2 0.907,
          CDK4 0.877, DES 0.790, ACTA2 0.859.
          Every gene's gap and CV accuracy is essentially unchanged (within
          ~3 points) after removing the uterine samples. MDM2/CDK4 stay
          strong (marker of the 12q amplicon, unrelated to tissue of
          origin); MYH11/DES/ACTA2 (smooth-muscle contractile genes) if
          anything get slightly STRONGER without the uterine samples, the
          opposite of what a pure site-confound would predict.
DECIDED:  The marker-gene separation is driven by real LMS-vs-DDLPS tumor
          biology (smooth-muscle lineage vs. 12q13-15 amplicon), not by the
          uterine-tissue-of-origin confound. The friend's claim about strong,
          near-linear separability holds up under this check.
OPEN:     Uterine confound is still real for OTHER things (sex ratio, and
          any feature that isn't a well-known tumor-lineage marker) — this
          check only clears MYH11/MDM2/CDK4/DES/ACTA2 specifically, not the
          general claim that clinical columns are confound-free.

## Entry — 2026-09-23: Step 6 merge (grilled, then built)

GOAL:     Resolve the N=158-vs-163 open decision blocking step 6, then merge
          clinical + RNA-seq + CNA + mutation data into a working dataset.
DID:      Ran a grilling session (grilling + domain-modeling skills) before
          writing any code. Independently re-verified the cohort-definition
          claim in CONTEXT.md §4 against the raw files rather than trusting
          either note: queried ICD_O_3_HISTOLOGY (8890/3=LMS, 8858/3=DDLPS)
          directly against data_clinical_patient.txt.
SAW:      ICD_O_3_HISTOLOGY gives 97 LMS + 58 DDLPS = 155, not the "158
          (100+58)" figure in CONTEXT.md §5. Traced why: 100 comes from
          CANCER_TYPE_DETAILED (a different column, which itself gives 59
          DDLPS, not 58) — "158" was never the output of querying one column,
          it was 100 from one column glued to 58 from another. Also checked:
          all 155 cohort patients have exactly one SAMPLE_ID (no 1:many
          join risk); 2 are missing from the RNA-seq file entirely, 1 from
          the CNA file (matches the 3 patients already flagged in the
          2026-09-13 addendum above); RSEM has 13 no-symbol gene rows and 7
          duplicate-symbol rows (6 of which share the same Entrez_Gene_Id
          too, with genuinely different expression values per row — a real
          duplicate-row quirk in the source file, not a data error); CNA has
          a similar duplicate pattern (79 rows). Dispatched a background
          check against cBioPortal's own sarc_tcga_pan_can_atlas_2018_sequenced
          sample list: all 20 of the cohort's zero-mutation-record patients
          are on that list, confirming they are real biological zeros, not
          samples missing from the mutation profile.
DECIDED:  (all confirmed with the user during grilling, not decided
          unilaterally)
          - Cohort = N=155 (97 LMS + 58 DDLPS) via ICD_O_3_HISTOLOGY. N=158
            and N=163 both rejected for this phase. CONTEXT.md §5 and
            spec.md §4 updated in place with dated corrections (original
            text preserved, not deleted).
          - label: DDLPS=1 (minority/positive, matches PR-AUC-primary
            convention), LMS=0.
          - Output shape: four parquet files sharing one patient_id index
            (clinical_labels, rna_seq_log2, cna_gistic2, mutation_binary)
            rather than one ~45k-column flat file — matches the
            curatedTCGAData/MultiAssayExperiment reference pattern, and
            keeps per-modality slicing cheap for step 11's per-fold MAD
            filtering later.
          - The 3 whole-modality-missing patients are kept (not dropped) as
            all-NaN rows in that modality's table, with has_rnaseq/has_cna
            boolean flags on the clinical table — an N=155 cohort can't
            afford to silently lose patients.
          - Gene dedup: drop the null-symbol rows; disambiguate true
            duplicate symbols with an Entrez_Gene_Id suffix, and where that
            still collides (the 6 same-symbol-same-Entrez RSEM rows) an
            occurrence-counter suffix — never silently collapse two rows
            with different measured values into one.
          - clinical_labels carries SEX/AGE/ICD_O_3_SITE/TUMOR_TISSUE_SITE/
            CANCER_TYPE_DETAILED/is_uterine_site, not just the label — needed
            for the clinical-only baseline and no-uterine sensitivity run
            already planned in CONTEXT.md §4.
          - Mutation binary matrix restricted to the 5,165 genes mutated at
            least once within this 155-cohort (not the whole-study gene
            universe) — an always-zero column for this cohort is
            uninformative and would be dropped by MAD filtering anyway.
SAW (run output): rna_seq_log2 (155, 20518), cna_gistic2 (155, 25128),
          mutation_binary (155, 5165), clinical_labels (155, 13). Verified
          after writing: all 4 tables share identical patient row order;
          exactly 2 all-NaN rows in rna_seq_log2 and 1 in cna_gistic2
          (matching the flagged missing patients, no more no fewer); MDM2
          present in both rna_seq_log2 and cna_gistic2 columns; label
          balance 97/58 as expected. 0 mutation records dropped as
          non-nonsynonymous (all 17,393 records were already one of the
          nonsynonymous MAF categories).
NOT DONE: A full step-7 "count what's actually missing on the real merged
          table" pass, as its own explicit check (the gaps above were found
          as a byproduct of building step 6, not as a dedicated step-7 pass
          over the four output tables). Do this before step 8 (transforms —
          already applied for RNA/CNA during the merge, so mostly this means
          re-confirming nothing else is silently missing) or step 11
          (per-fold feature selection).
OPEN:     Open decision #2 from CONTEXT.md §5 (3 GDC manifest checksum
          mismatches) is untouched — independent of step 6, still pending.

---

## Style pass, 2026-09-23: same entries, rewritten in plain language

Nothing above this line was touched. The content of every entry got a bit
formal and dash-heavy over time (partly my own doing), so here's the same
information, entry by entry, in a more normal writing voice. No facts,
numbers, or decisions changed, just how it's written.

**Step 1: Confirm access.** Checked whether we could actually reach the
data: cBioPortal's REST API, the GitHub datahub, and the GDC API all worked
with no login needed. We don't need dbGaP controlled-access approval either,
since nothing in this plan touches raw BAM files or germline VCFs.

**Step 2: Download from cBioPortal.** Pulled five files from the
`sarc_tcga_pan_can_atlas_2018` study: the two clinical files, the CNA file,
the RSEM expression file, and a mutations file. Sizes and checksums are in
the table above and in `CHECKSUMS.sha256`.

One thing worth calling out: `data_mutations.txt` wasn't actually available
through the datahub mirror. Its git-lfs pointer resolves to an object ID that
GitHub's LFS API just returns a 404 for, and I checked twice a few seconds
apart to rule out a fluke. Everything else downloaded fine, including the
much bigger RSEM file, so this looks like a gap with that one file
specifically, not a broader access problem. I worked around it by pulling
the same mutation calls straight from the cBioPortal REST API instead
(17,393 records across 234 samples), saved as `data_mutations_api.json`.
It's the same information, just row-by-row JSON instead of a MAF file, so
whoever writes the step 6 merge needs to pivot this into a patient-by-gene
binary matrix rather than parsing a MAF directly.

Also noticed 234 distinct samples in that file vs. 255 total samples in the
study. That's not necessarily a problem: a sample with zero mutations in
this profile just wouldn't produce any rows in the API response. Worth
confirming later rather than assuming either way.

**Step 3: Cross-check against GDC.** Compared case counts between GDC and
cBioPortal for the TCGA-SARC project (table above). GDC's total of 261 cases
matches what the spec expects. The small per-modality gaps (259-261 in GDC
vs. 253 in cBioPortal) are expected: cBioPortal's PanCancer Atlas import
drops a handful of cases per platform for QC reasons, and that's a known,
documented difference between the two portals, not a mistake on either side.

Bigger thing worth flagging: the `SUBTYPE` column in the clinical file only
labels 83 patients as LMS and 46 as DDLPS, well short of the spec's
105/58. The `ICD_O_3_HISTOLOGY` column tells a different story: code
`8858/3` gives exactly 58 DDLPS patients, matching the spec exactly, but
code `8890/3` only gives 97 LMS, not 105. So LMS probably needs another
histology code or two folded in to hit 105. Bottom line: don't use `SUBTYPE`
for the cohort definition. Use `ICD_O_3_HISTOLOGY`, and figure out the exact
code set that adds up to 105 before locking the cohort in.

**Step 4: GTEx layer.** Skipped, on purpose. This phase is LMS vs. DDLPS
only, and GTEx is explicitly out of scope until a later phase. Nothing
downloaded for it.

**Step 5: Archive.** Everything above is sitting in
`data/raw/2026-09-13_cbioportal/`, stored exactly as it was received (the
JSON substitute is clearly noted as a substitute, not disguised as a MAF),
with SHA-256 checksums recorded. This folder is the reference point if
anything downstream looks off later.

**Addendum, later the same day: does the cohort actually have complete
data?** Someone asked whether the whole-study figure ("251 of 255 samples
have complete mutation, CNA, and expression data, 255 of 255 have
methylation") still holds once you restrict to just the 163 LMS/DDLPS
patients, or whether that's an assumption riding on the whole-study number.
Checked it directly against the files already on disk.

The whole-study numbers checked out first (251 and 255, matching the
official cBioPortal sample lists). But restricting to the LMS/DDLPS cohort
ran straight into the same problem from Step 3: there's no single column
that gives exactly 105/58. So I ran the completeness check under both
candidate definitions (table above). Both land around 98.1% complete, which
is basically the same as the whole-study rate, so the "most of these 163
patients are probably fine" assumption holds up once you actually check it.
The same three samples are missing one modality under either definition:
`TCGA-DX-A48V-01` and `TCGA-DX-A6BK-01` are missing RNA-seq, and
`TCGA-WK-A8XZ-01` is missing CNA. Neither definition gets to 163, so that
part's still open.

**Correction: download status.** Somewhere earlier in this project I said
"nothing has been downloaded into a working file yet." That wasn't true:
the five files listed above were already on disk with verified checksums
before that message went out, and the completeness check above ran against
those files, not fresh API calls. Re-ran the checksum verification to be
sure. Everything still matches.

**Addendum, later still: where did 105/58 actually come from?** Went
looking for whatever source the spec's 105 LMS / 58 DDLPS numbers trace
back to. Checked three places, none of which reproduced it: the original
2017 Cell paper on TCGA-SARC (206 total sarcomas, 80 LMS including 27
uterine, 50 DDLPS, different N entirely), GDC's clinical fields directly
(closest hit was MPNST at exactly 9, nothing for LMS or DDLPS), and a
couple of published ML papers using this cohort (close but not exact
numbers). So the spec's figures didn't come from any of the obvious places.
(Correction added 2026-09-22: this section originally said uterine LMS
cases were "out of scope for TCGA-SARC." That was wrong, they are in
scope. See the uterine-confound note further down.)

My working guess at the time: adopt `ICD_O_3_HISTOLOGY` as the cohort
definition (58 DDLPS matches exactly, 97 LMS is the closest match to 105)
and treat the cohort as N=155, documenting the drop from 163 as something
we verified rather than something we assumed. Didn't decide this on my own
since it changes every downstream sample-size number, including the
Experiment 2 ablation points that assume up to 130 training patients. Left
it for the user to weigh in on.

**Addendum, still later: found it.** Traced the 105/58 numbers to a 2016
GDAC Firehose clinical freeze, not a paper. That file's `histological_type`
column gives 105 LMS, 59 dedifferentiated liposarcoma, and matches four of
six subtypes in the spec exactly. So this is the real source.

Why DDLPS is 59 there but 58 in the spec and in today's cBioPortal data:
one patient (`TCGA-MO-A47P`) was classified as DDLPS in the 2016 freeze but
has since been reclassified to a different liposarcoma subtype in today's
data. The spec's 58 already reflects that correction, so nothing needs
fixing there.

Why LMS is 100 in today's cBioPortal bundle but 105 in the 2016 freeze: five
of those 105 patients simply aren't in `sarc_tcga_pan_can_atlas_2018`'s
clinical file at all. Checked GDC directly and all five still exist there
with full CNA, RNA-seq, and mutation data, they just didn't make it into
cBioPortal's specific import (probably an inclusion filter cBioPortal
applied at import time, not a real data problem with those five cases).

So the bottom line: the spec's N=163 is real, grounded in actual public
data, every one of the 163 patients exists with full coverage in GDC. The
only question is where to get five of the LMS patients' data from. Option A
is to stick with N=158 using only what's already downloaded, no extra work.
Option B is to pull those five patients' raw files from GDC and reprocess
them to match cBioPortal's conventions, which gets you to the full 163 but
is real extra engineering (matching TCGA's RSEM and GISTIC2 pipelines isn't
trivial). Didn't decide this myself, flagged it for the user.

**Next steps, as of that point.** Step 6 (the merge) was blocked on
resolving the cohort-definition question above, not just on choosing
`ICD_O_3_HISTOLOGY` over `SUBTYPE`. Step 7 would follow once that was
settled.

**Addendum, 2026-09-22: should clinical columns be used as features? (the
uterine-site confound).** Checked every clinical column against the label,
using the ICD_O_3_HISTOLOGY-based cohort (97 LMS, 58 DDLPS). This is just an
in-sample majority-vote check, so treat the numbers as optimistic, not a
real cross-validated result. A few columns showed some signal
(`ICD_O_3_SITE` at 0.697, `ICD_10` at 0.703, `SEX` at 0.671, `PRIOR_DX` at
0.652), everything else was around the always-guess-LMS baseline of 0.626,
meaning no real signal. The staging columns (AJCC stage, T/N/M, lymph node,
weight) are 100% blank in this cohort and unusable. Age overlaps heavily
between the two groups.

The real finding here: about 28 of the 97 LMS patients are from a uterine
site (25 coded `C55.9`, 3 more coded `C54.2` or `C54.9`), compared to zero
of the 58 DDLPS patients. Sex tracks this too, 65 of 97 LMS patients are
female vs. 19 of 58 DDLPS. So tumor location and sex partly separate the two
classes on their own, which means an omics model could end up picking up
"uterine vs. non-uterine tissue" signal instead of real LMS-vs-DDLPS tumor
biology. The spec's claim that this pair has no confound doesn't account
for this. Left three options open for the user to decide between: omics-only
features, adding a clinical-only baseline, or running a sensitivity check
that excludes the uterine LMS cases.

**Entry, 2026-09-22: project restructure and archive integrity check.**
Set up the proper folder layout from the research guide (logbook, configs,
src, results per experiment, figures, paper, processed data) and moved this
log from a NOTES.md file sitting inside the raw data folder into its proper
place in `logbook/`, since the raw folder should only hold data as received.
While doing that, re-ran the checksum verification and found three files
failing: the GDC manifest files for CNA, MAF, and RNA-seq. Traced it with
git: someone changed just the header line of each file (padding column
names with spaces) in a commit from 2026-09-21, the data rows themselves are
untouched. I didn't make that edit. Left the three files as they are rather
than restoring or re-checksumming without checking with the owner first,
since both fixes are easy and the original bytes are recoverable either way.
The impact is cosmetic since these files were only used for patient-count
cross-checks, not for modeling, but the archive is supposed to hold data
exactly as received, so this should get resolved one way or the other.

**Entry, 2026-09-23: checking the marker-gene separation against the
uterine confound.** A PhD-advisor friend reviewed the project and said this
LMS-vs-DDLPS task is probably near-linearly separable using a handful of
known marker genes, which would make a quantum kernel unnecessary. Checked
that claim against the real RSEM data, then checked whether it holds up
once you drop the 28 uterine-site LMS patients flagged above.

Computed the log2 expression gap and an honest 5-fold cross-validated
accuracy (with the threshold refit only on the training fold each time,
averaged over 10 reshuffles) for five genes: MYH11, MDM2, CDK4, DES, and
ACTA2. On the full 155-patient cohort, accuracy ranged from 0.752 (DES) to
0.936 (MDM2). After removing the 28 uterine LMS patients, the numbers barely
moved, within about 3 points either way, and a couple of the smooth-muscle
genes actually got slightly stronger, which is the opposite of what you'd
expect if the uterine confound were driving the separation. So the
conclusion is that this separation is real LMS-vs-DDLPS tumor biology
(smooth-muscle lineage vs. the 12q13-15 amplicon), not an artifact of tumor
location. The friend's claim holds up. Still worth noting the uterine
confound is real for other things, like sex ratio or any feature that isn't
one of these specific marker genes, this check only clears those five genes,
not every possible feature.

**Entry, 2026-09-23: the Step 6 merge.** Before writing any merge code, ran
a grilling session to make sure the cohort-definition question from earlier
was actually settled and not just assumed. Went back to the raw clinical
file and queried `ICD_O_3_HISTOLOGY` directly rather than trusting any
earlier note, mine or otherwise.

Got 97 LMS and 58 DDLPS, 155 total, not the "158 (100+58)" figure that had
been floating around in the project notes. Traced why: the 100 actually
comes from a different column (`CANCER_TYPE_DETAILED`), which on its own
gives 59 DDLPS, not 58. So "158" was never what you'd get from querying one
column, it was 100 from one column stitched to 58 from another. Also
checked a few other things while I was in there: all 155 cohort patients
map to exactly one sample ID each, so no risk of a messy one-to-many join.
Two patients are missing from the RNA-seq file entirely and one from the
CNA file, which matches what was already flagged back in the September 13
addendum. The RSEM file has 13 rows with no gene symbol at all and 7 genes
that show up twice, six of which share the same Entrez ID too but have
genuinely different expression values per row, so it's a real duplicate-row
quirk in the source file, not a data error to just collapse away. CNA has a
similar pattern with more rows affected. And I checked cBioPortal's own
"sequenced samples" list against the 20 cohort patients who have zero
mutation records: all 20 are officially on that sequenced list, which
confirms these are real biological zeros, not samples that were simply
never sequenced.

Everything below was confirmed with the user during the grilling session,
not decided on my own. The cohort is N=155 (97 LMS, 58 DDLPS) using
`ICD_O_3_HISTOLOGY`. Both N=158 and N=163 are out for this phase, and
`CONTEXT.md` and `spec.md` got dated corrections in place rather than
silent edits. DDLPS is labeled 1 (it's the minority class and PR-AUC is the
primary metric, which is conventionally computed with the minority class as
positive), LMS is labeled 0. The output is four parquet files that all
share one patient index, clinical labels, RNA-seq, CNA, and mutations,
rather than one giant flat file with tens of thousands of columns. That
matches how `curatedTCGAData` and `MultiAssayExperiment` structure the same
kind of data, and keeps things simple when step 11 needs to filter genes
per modality per fold later. The three patients missing a whole modality
stay in the cohort as an all-missing row in that one table, with a flag
column noting which modality they're missing, rather than getting dropped,
since losing patients from an already-small cohort isn't something to do
quietly. For the duplicate gene symbols, dropped the ones with no symbol at
all, and for genuine duplicates, appended the Entrez ID to tell them apart,
and where even that collided, added a simple counter, so no measured data
gets silently thrown away. The clinical table also carries sex, age, tumor
site, and the uterine-site flag, not just the label, since those are needed
for the clinical-only baseline and uterine-sensitivity analyses already
planned. And the mutation matrix only includes genes that were actually
mutated at least once in this specific cohort, since a gene that's never
mutated here is just an all-zero column that would get filtered out later
anyway.

After running it: the RNA-seq table came out to 155 patients by 20,518
genes, CNA to 155 by 25,128, mutations to 155 by 5,165, and the clinical
table to 155 by 13 columns. Checked afterward that all four tables have the
patients in the same order, that exactly two rows are fully missing in
RNA-seq and one in CNA (matching what was expected, no more and no fewer),
that MDM2 shows up in both the RNA-seq and CNA columns, and that the label
split really is 97 to 58. None of the 17,393 mutation records got dropped
as non-relevant mutation types, they were all already the kind of mutation
that counts.

What's still not done: an actual dedicated pass checking for missing data
across the finished merged tables. The gaps found above came up as a
byproduct of building the merge, not from a deliberate check of the four
output files on their own terms. That's the next thing to do, before moving
on to per-fold feature selection. Also still open and unrelated to any of
this: the three GDC manifest files with mismatched checksums from the
September 22 entry, still unresolved.
