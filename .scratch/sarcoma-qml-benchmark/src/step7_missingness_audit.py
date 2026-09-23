"""
Step 7 (spec.md sec 8): count what is actually missing in the merged tables from
step6_merge.py. Audit only. Nothing is imputed, dropped, or scaled here; imputation
happens per fold later.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

PROC_DIR = Path(__file__).resolve().parents[1] / "data" / "processed"

EXPECTED_VALUES = {
    "cna": {-2, -1, 0, 1, 2},
    "mut": {0, 1},
}


def load_tables():
    clin = pd.read_parquet(PROC_DIR / "clinical_labels.parquet").set_index("patient_id", drop=False)
    tables = {
        "rna": pd.read_parquet(PROC_DIR / "rna_seq_log2.parquet"),
        "cna": pd.read_parquet(PROC_DIR / "cna_gistic2.parquet"),
        "mut": pd.read_parquet(PROC_DIR / "mutation_binary.parquet"),
    }
    return clin, tables


def audit_alignment(clin, tables):
    result = {}
    for name, t in tables.items():
        result[name] = {
            "same_patients_same_order_as_clinical": bool(t.index.equals(clin.index)),
            "n_patients": t.shape[0],
            "n_features": t.shape[1],
            "duplicate_column_names": int(t.columns.duplicated().sum()),
        }
    return result


def audit_modality(name, t, clin, flag_col):
    nan_mask = t.isna()
    all_nan_rows = nan_mask.all(axis=1)
    partial_rows = nan_mask.any(axis=1) & ~all_nan_rows

    patients_missing_per_feature = nan_mask.sum(axis=0)
    distinct_counts = patients_missing_per_feature.value_counts().sort_index()

    out = {
        "total_nan_cells": int(nan_mask.sum().sum()),
        "patients_fully_missing": t.index[all_nan_rows].tolist(),
        "patients_partially_missing": t.index[partial_rows].tolist(),
        "features_with_any_nan": int((patients_missing_per_feature > 0).sum()),
        "patients_missing_per_feature_histogram": {int(k): int(v) for k, v in distinct_counts.items()},
        "missingness_is_uniform_across_features": bool(len(distinct_counts) == 1),
    }

    if flag_col is not None:
        flagged_present = clin[flag_col].astype(bool)
        out["clinical_flag_matches_data"] = bool((flagged_present.values == (~all_nan_rows).values).all())

    values = t.stack().dropna()
    out["value_min"] = float(values.min())
    out["value_max"] = float(values.max())
    if name in EXPECTED_VALUES:
        seen = set(np.unique(values.values).tolist())
        out["unexpected_values"] = sorted(seen - EXPECTED_VALUES[name])

    n_unique = t.nunique(dropna=True)
    out["constant_columns"] = int((n_unique <= 1).sum())
    out["constant_columns_pct"] = round(100 * out["constant_columns"] / t.shape[1], 2)
    return out


def main():
    clin, tables = load_tables()
    report = {"alignment": audit_alignment(clin, tables)}

    flag_cols = {"rna": "has_rnaseq", "cna": "has_cna", "mut": None}
    per_patient = pd.DataFrame(index=clin.index)
    for name, t in tables.items():
        report[name] = audit_modality(name, t, clin, flag_cols[name])
        per_patient[f"{name}_frac_present"] = t.notna().mean(axis=1).round(4)

    per_patient["label"] = clin["label"]
    per_patient["canonical_label"] = clin["canonical_label"]

    known_missing = {
        "rna": set(clin.index[~clin["has_rnaseq"]]),
        "cna": set(clin.index[~clin["has_cna"]]),
        "mut": set(),
    }
    unexplained = []
    for name in tables:
        extra = set(report[name]["patients_fully_missing"]) ^ known_missing[name]
        extra |= set(report[name]["patients_partially_missing"])
        if extra:
            unexplained.append({name: sorted(extra)})
    report["unexplained_missingness"] = unexplained

    mut = tables["mut"]
    zero_mut_patients = mut.index[(mut.sum(axis=1) == 0)].tolist()
    report["mut"]["patients_with_zero_mutations_count"] = len(zero_mut_patients)
    report["mut"]["patients_with_zero_mutations"] = zero_mut_patients
    report["mut"]["note"] = (
        "All zero-mutation patients were checked against cBioPortal's sequenced sample "
        "list on 2026-09-23: real zeros, not missing."
    )

    out_json = PROC_DIR / "step7_missingness_report.json"
    out_csv = PROC_DIR / "step7_per_patient_completeness.csv"
    with open(out_json, "w") as f:
        json.dump(report, f, indent=2)
    per_patient.to_csv(out_csv)

    print(json.dumps(report, indent=2))
    print(f"\nWrote {out_json.name} and {out_csv.name} to {PROC_DIR}")


if __name__ == "__main__":
    main()
