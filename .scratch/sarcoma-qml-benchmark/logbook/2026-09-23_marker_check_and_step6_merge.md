# Marker-gene check and Step 6 merge, 2026-09-23

Two things happened this day: checked whether the uterine-site confound from
2026-09-22 explains the project's core marker-gene finding, then resolved the
N=158-vs-163 cohort question and built the step 6 merge. Original formal-voice wording
is preserved in `_archive_2026-09-13_full_log_pre_split.md` if needed.

## Checking the marker-gene separation against the uterine confound

A PhD-advisor friend reviewed the project and said this LMS-vs-DDLPS task is probably
near-linearly separable using a handful of known marker genes, which would make a
quantum kernel unnecessary. Checked that claim against the real RSEM data, then checked
whether it holds up once you drop the 28 uterine-site LMS patients flagged in the
2026-09-22 addendum.

Computed the log2 expression gap and an honest 5-fold cross-validated accuracy (with the
threshold refit only on the training fold each time, averaged over 10 reshuffles) for
five genes: MYH11, MDM2, CDK4, DES, and ACTA2. On the full 155-patient cohort, accuracy
ranged from 0.752 (DES) to 0.936 (MDM2). After removing the 28 uterine LMS patients, the
numbers barely moved, within about 3 points either way, and a couple of the
smooth-muscle genes actually got slightly stronger, which is the opposite of what you'd
expect if the uterine confound were driving the separation.

Conclusion: this separation is real LMS-vs-DDLPS tumor biology (smooth-muscle lineage
vs. the 12q13-15 amplicon), not an artifact of tumor location. The friend's claim holds
up. Still worth noting the uterine confound is real for other things, like sex ratio or
any feature that isn't one of these specific marker genes, this check only clears those
five genes, not every possible feature.

## Step 6 merge

Before writing any merge code, ran a grilling session to make sure the cohort-definition
question from 2026-09-13 was actually settled and not just assumed. Went back to the raw
clinical file and queried `ICD_O_3_HISTOLOGY` directly rather than trusting any earlier
note, mine or otherwise.

Got 97 LMS and 58 DDLPS, 155 total, not the "158 (100+58)" figure that had been floating
around in the project notes. Traced why: the 100 actually comes from a different column
(`CANCER_TYPE_DETAILED`), which on its own gives 59 DDLPS, not 58. So "158" was never
what you'd get from querying one column, it was 100 from one column stitched to 58 from
another.

Also checked a few other things while in there: all 155 cohort patients map to exactly
one sample ID each, so no risk of a messy one-to-many join. Two patients are missing
from the RNA-seq file entirely and one from the CNA file, which matches what was already
flagged back in the 2026-09-13 addendum. The RSEM file has 13 rows with no gene symbol
at all and 7 genes that show up twice, six of which share the same Entrez ID too but
have genuinely different expression values per row, so it's a real duplicate-row quirk
in the source file, not a data error to just collapse away. CNA has a similar pattern
with more rows affected. And checked cBioPortal's own "sequenced samples" list against
the 20 cohort patients who have zero mutation records: all 20 are officially on that
sequenced list, which confirms these are real biological zeros, not samples that were
simply never sequenced.

Everything below was confirmed with the user during the grilling session, not decided
alone:

- Cohort is N=155 (97 LMS, 58 DDLPS) using `ICD_O_3_HISTOLOGY`. Both N=158 and N=163 are
  out for this phase. `CONTEXT.md` and `spec.md` got dated corrections in place rather
  than silent edits.
- Label: DDLPS is 1 (it's the minority class and PR-AUC is the primary metric, which is
  conventionally computed with the minority class as positive), LMS is 0.
- Output is four parquet files that all share one patient index: clinical labels,
  RNA-seq, CNA, and mutations, rather than one giant flat file with tens of thousands of
  columns. That matches how `curatedTCGAData` and `MultiAssayExperiment` structure the
  same kind of data, and keeps things simple when step 11 needs to filter genes per
  modality per fold later.
- The three patients missing a whole modality stay in the cohort as an all-missing row
  in that one table, with a flag column noting which modality they're missing, rather
  than getting dropped, since losing patients from an already-small cohort isn't
  something to do quietly.
- For the duplicate gene symbols: dropped the ones with no symbol at all, and for
  genuine duplicates, appended the Entrez ID to tell them apart, and where even that
  collided, added a simple counter, so no measured data gets silently thrown away.
- The clinical table also carries sex, age, tumor site, and the uterine-site flag, not
  just the label, since those are needed for the clinical-only baseline and
  uterine-sensitivity analyses already planned.
- The mutation matrix only includes genes that were actually mutated at least once in
  this specific cohort, since a gene that's never mutated here is just an all-zero
  column that would get filtered out later anyway.

Script: `src/step6_merge.py`. Output: `data/processed/clinical_labels.parquet`,
`rna_seq_log2.parquet`, `cna_gistic2.parquet`, `mutation_binary.parquet`.

After running it: the RNA-seq table came out to 155 patients by 20,518 genes, CNA to 155
by 25,128, mutations to 155 by 5,165, and the clinical table to 155 by 13 columns.
Checked afterward that all four tables have the patients in the same order, that exactly
two rows are fully missing in RNA-seq and one in CNA (matching what was expected, no
more and no fewer), that MDM2 shows up in both the RNA-seq and CNA columns, and that the
label split really is 97 to 58. None of the 17,393 mutation records got dropped as
non-relevant mutation types, they were all already the kind of mutation that counts.

What's still not done: an actual dedicated pass checking for missing data across the
finished merged tables, as its own check rather than a byproduct of building the merge.
That's the next thing to do, before moving on to per-fold feature selection.

Also still open and unrelated to this: the three GDC manifest checksum mismatches from
the 2026-09-22 entry, still unresolved.
