"""
Step 6 (spec.md sec 8): merge clinical labels, RNA-seq, CNA, and mutation data
into one patient-aligned working dataset for the LMS-vs-DDLPS cohort.

Decisions locked in during the 2026-09-23 grilling session (see CONTEXT.md sec 5
and the dated logbook entry for this run):

- Cohort = N=155 (97 LMS + 58 DDLPS), defined by ICD_O_3_HISTOLOGY in
  data_clinical_patient.txt (8890/3=LMS, 8858/3=DDLPS). Not N=158/163.
- label: DDLPS=1 (minority), LMS=0 (majority) -- PR-AUC is primary metric and
  is conventionally computed with the minority class as positive.
- Output shape: separate per-modality tables sharing one patient_id index
  (curatedTCGAData/MultiAssayExperiment pattern), not one ~45k-column flat file.
- The 3 patients missing a whole modality (2 missing RNA-seq, 1 missing CNA)
  are kept, not dropped, as NaN rows with has_rnaseq/has_cna boolean flags.
- Duplicate/missing Hugo_Symbol rows: null-symbol rows dropped; true duplicate
  symbols disambiguated with an Entrez ID suffix rather than silently collapsed.
- Mutation matrix restricted to genes mutated >=1x within this 155-patient
  cohort (not the whole-study gene universe) -- an all-zero column is
  uninformative for this cohort and would be dropped by MAD filtering anyway.
- The 20 patients with zero mutation JSON records were checked against
  cBioPortal's official sarc_tcga_pan_can_atlas_2018_sequenced sample list:
  all 20 are on it, so these are confirmed real zeros, not missing data.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw" / "2026-09-13_cbioportal"
OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "processed"

LMS_HISTOLOGY_CODE = "8890/3"
DDLPS_HISTOLOGY_CODE = "8858/3"

NONSYNONYMOUS_TYPES = {
    "Missense_Mutation", "Nonsense_Mutation", "Nonstop_Mutation",
    "Frame_Shift_Del", "Frame_Shift_Ins", "In_Frame_Del", "In_Frame_Ins",
    "Splice_Site", "Splice_Region", "Translation_Start_Site",
}


def load_cohort() -> pd.DataFrame:
    """Build the 155-patient cohort table: patient_id, sample_id, label, canonical_label,
    plus clinical covariates needed for the planned secondary analyses (uterine
    sensitivity run, clinical-only baseline)."""
    pat = pd.read_csv(RAW_DIR / "data_clinical_patient.txt", sep="\t", comment="#")
    samp = pd.read_csv(RAW_DIR / "data_clinical_sample.txt", sep="\t", comment="#")

    is_lms = pat["ICD_O_3_HISTOLOGY"] == LMS_HISTOLOGY_CODE
    is_ddlps = pat["ICD_O_3_HISTOLOGY"] == DDLPS_HISTOLOGY_CODE
    cohort_pat = pat.loc[is_lms | is_ddlps, [
        "PATIENT_ID", "ICD_O_3_HISTOLOGY", "ICD_O_3_SITE", "SEX", "AGE",
    ]].copy()
    cohort_pat["canonical_label"] = np.where(
        cohort_pat["ICD_O_3_HISTOLOGY"] == LMS_HISTOLOGY_CODE, "LMS", "DDLPS"
    )
    cohort_pat["label"] = (cohort_pat["canonical_label"] == "DDLPS").astype(int)

    samp_cols = samp[["PATIENT_ID", "SAMPLE_ID", "CANCER_TYPE_DETAILED", "TUMOR_TISSUE_SITE"]]
    cohort = cohort_pat.merge(samp_cols, on="PATIENT_ID", how="left")

    n_dupe_samples = cohort["PATIENT_ID"].duplicated().sum()
    if n_dupe_samples:
        raise ValueError(
            f"{n_dupe_samples} cohort patients have >1 sample row -- "
            "step 6 assumed a 1:1 patient:sample mapping; re-check before proceeding."
        )

    uterine_sites = {"C55.9", "C54.2", "C54.9"}
    cohort["is_uterine_site"] = cohort["ICD_O_3_SITE"].isin(uterine_sites)

    cohort = cohort.rename(columns={"PATIENT_ID": "patient_id", "SAMPLE_ID": "sample_id"})
    cohort = cohort.set_index("patient_id", drop=False).sort_index()
    return cohort


def dedupe_gene_columns(wide_df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """wide_df: rows=genes (Hugo_Symbol, Entrez_Gene_Id, <sample columns...>).
    Drops rows with no Hugo_Symbol; disambiguates true duplicate symbols by
    suffixing the Entrez_Gene_Id rather than silently collapsing them."""
    log = {}
    n_before = len(wide_df)
    wide_df = wide_df.dropna(subset=["Hugo_Symbol"]).copy()
    log["dropped_null_symbol_rows"] = n_before - len(wide_df)

    dupe_mask = wide_df["Hugo_Symbol"].duplicated(keep=False)
    log["duplicate_symbol_rows_disambiguated"] = int(dupe_mask.sum())
    wide_df.loc[dupe_mask, "Hugo_Symbol"] = (
        wide_df.loc[dupe_mask, "Hugo_Symbol"] + "__" + wide_df.loc[dupe_mask, "Entrez_Gene_Id"].astype(str)
    )
    # Some rows share both Hugo_Symbol AND Entrez_Gene_Id (same gene ID, genuinely
    # different measured values -- a real duplicate-row quirk in the source file,
    # not a data error to silently collapse). Entrez suffixing alone doesn't
    # disambiguate these; add an occurrence counter as a second pass.
    still_dupe = wide_df["Hugo_Symbol"].duplicated(keep=False)
    log["duplicate_symbol_and_entrez_rows_disambiguated_by_occurrence"] = int(still_dupe.sum())
    if still_dupe.any():
        occ = wide_df.groupby("Hugo_Symbol").cumcount() + 1
        wide_df.loc[still_dupe, "Hugo_Symbol"] = (
            wide_df.loc[still_dupe, "Hugo_Symbol"] + "__occ" + occ[still_dupe].astype(str)
        )
    assert wide_df["Hugo_Symbol"].is_unique, "gene symbol dedup failed to produce unique columns"
    return wide_df, log


def build_omics_matrix(
    raw_file: str, cohort: pd.DataFrame, log2_transform: bool, fillna_zero_within_sample: bool
) -> tuple[pd.DataFrame, dict]:
    """Load a gene-rows x sample-columns cBioPortal file, restrict to cohort samples,
    dedupe genes, transpose to patient-rows x gene-columns, reindex to the full
    155-patient cohort (patients absent from the file become an all-NaN row)."""
    raw = pd.read_csv(RAW_DIR / raw_file, sep="\t")
    raw, dedupe_log = dedupe_gene_columns(raw)

    sample_to_patient = cohort.set_index("sample_id")["patient_id"]
    present_samples = [s for s in cohort["sample_id"] if s in raw.columns]
    missing_samples = sorted(set(cohort["sample_id"]) - set(present_samples))

    mat = raw.set_index("Hugo_Symbol")[present_samples]
    mat = mat.T
    mat.index = mat.index.map(sample_to_patient)
    mat.index.name = "patient_id"

    if fillna_zero_within_sample:
        n_within_sample_nan = int(mat.isna().sum().sum())
        mat = mat.fillna(0.0)
    else:
        n_within_sample_nan = int(mat.isna().sum().sum())

    if log2_transform:
        mat = np.log2(mat.astype(float) + 1.0)

    mat = mat.reindex(cohort["patient_id"])

    modality_log = {
        **dedupe_log,
        "n_genes_final": mat.shape[1],
        "patients_missing_this_modality": missing_samples,
        "within_sample_missing_values_filled_zero" if fillna_zero_within_sample else "within_sample_missing_values_left_nan": n_within_sample_nan,
    }
    return mat, modality_log


def build_mutation_matrix(cohort: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    with open(RAW_DIR / "data_mutations_api.json") as f:
        records = json.load(f)

    n_total = len(records)
    records = [r for r in records if r.get("mutationType") in NONSYNONYMOUS_TYPES]
    n_dropped_non_nonsynonymous = n_total - len(records)

    cohort_sample_ids = set(cohort["sample_id"])
    df = pd.DataFrame.from_records(
        [
            {"sample_id": r["sampleId"], "gene": r["gene"]["hugoGeneSymbol"]}
            for r in records
            if r["sampleId"] in cohort_sample_ids
        ]
    )

    sample_to_patient = cohort.set_index("sample_id")["patient_id"]
    df["patient_id"] = df["sample_id"].map(sample_to_patient)

    mat = pd.crosstab(df["patient_id"], df["gene"]).clip(upper=1)
    mat = mat.reindex(cohort["patient_id"]).fillna(0).astype(int)

    n_zero_record_patients = int((mat.sum(axis=1) == 0).sum())

    modality_log = {
        "mutation_records_total": n_total,
        "mutation_records_dropped_non_nonsynonymous": n_dropped_non_nonsynonymous,
        "n_genes_final": mat.shape[1],
        "patients_with_zero_mutation_records": n_zero_record_patients,
        "note": (
            "All zero-mutation-record patients verified 2026-09-23 against "
            "cBioPortal's sarc_tcga_pan_can_atlas_2018_sequenced sample list -- "
            "confirmed sequenced, so these are real biological zeros, not missing data."
        ),
    }
    return mat, modality_log


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {}

    cohort = load_cohort()
    manifest["cohort"] = {
        "n_total": len(cohort),
        "n_lms": int((cohort["canonical_label"] == "LMS").sum()),
        "n_ddlps": int((cohort["canonical_label"] == "DDLPS").sum()),
        "label_encoding": "DDLPS=1 (minority/positive), LMS=0 (majority)",
        "n_uterine_site_lms": int(cohort.loc[cohort["canonical_label"] == "LMS", "is_uterine_site"].sum()),
    }

    rna, rna_log = build_omics_matrix(
        "data_mrna_seq_v2_rsem.txt", cohort, log2_transform=True, fillna_zero_within_sample=False
    )
    manifest["rna_seq"] = rna_log

    cna, cna_log = build_omics_matrix(
        "data_cna.txt", cohort, log2_transform=False, fillna_zero_within_sample=True
    )
    manifest["cna"] = cna_log

    mut, mut_log = build_mutation_matrix(cohort)
    manifest["mutation"] = mut_log

    cohort["has_rnaseq"] = cohort["patient_id"].isin(rna.dropna(how="all").index)
    cohort["has_cna"] = cohort["patient_id"].isin(cna.dropna(how="all").index)
    manifest["missing_modality_patients"] = {
        "missing_rnaseq": cohort.loc[~cohort["has_rnaseq"], "patient_id"].tolist(),
        "missing_cna": cohort.loc[~cohort["has_cna"], "patient_id"].tolist(),
    }

    clinical_cols = [
        "patient_id", "sample_id", "canonical_label", "label",
        "ICD_O_3_HISTOLOGY", "ICD_O_3_SITE", "is_uterine_site",
        "SEX", "AGE", "CANCER_TYPE_DETAILED", "TUMOR_TISSUE_SITE",
        "has_rnaseq", "has_cna",
    ]
    clinical = cohort[clinical_cols].reset_index(drop=True)

    clinical.to_parquet(OUT_DIR / "clinical_labels.parquet", index=False)
    rna.to_parquet(OUT_DIR / "rna_seq_log2.parquet")
    cna.to_parquet(OUT_DIR / "cna_gistic2.parquet")
    mut.to_parquet(OUT_DIR / "mutation_binary.parquet")

    with open(OUT_DIR / "step6_merge_manifest.json", "w") as f:
        json.dump(manifest, f, indent=2, default=str)

    print(json.dumps(manifest, indent=2, default=str))
    print(f"\nWrote 4 parquet files + manifest to {OUT_DIR}")


if __name__ == "__main__":
    main()
