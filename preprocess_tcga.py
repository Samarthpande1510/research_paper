import os
import pandas as pd
import numpy as np
#Barcode Standardization & Slicing,Tissue Type Filtering,Binary Diagnostic Label Encoding,#Pseudocount Offset & $\log_2$ Variance Stabilization and Matrix Re-orientation   (Transposition)& "C:/Users/Aarush/anaconda3/envs/quantum_lab/python.exe" preprocess_tcga.py
BASE_DIR = os.path.join(".scratch", "sarcoma-qml-benchmark", "data", "raw", "2026-09-13_cbioportal")
CLINICAL_FILE = os.path.join(BASE_DIR, "data_clinical_sample.txt")
EXPR_FILE = os.path.join(BASE_DIR, "data_mrna_seq_v2_rsem.txt")
print("=" * 60)
print("STAGE 1: EXTRACTING COHORT & SUBTYPE LABELS")
print("=" * 60)
df_clin = pd.read_csv(CLINICAL_FILE, sep="\t", comment="#")
df_clin.columns = [c.upper() for c in df_clin.columns]
sample_col = "SAMPLE_ID" if "SAMPLE_ID" in df_clin.columns else df_clin.columns[0]
subtype_candidates = [c for c in df_clin.columns if any(k in c for k in ["SUBTYPE", "HISTOLOGY", "CANCER_TYPE_DETAILED"])]
subtype_col = subtype_candidates[0]
print(f"Sample column:  {sample_col}")
print(f"Subtype column: {subtype_col}")
df_clin["CLEAN_BARCODE"] = df_clin[sample_col].astype(str).str.slice(0, 15)
df_clin = df_clin[df_clin["CLEAN_BARCODE"].str.endswith("-01")].copy()
def map_label(val):
    v = str(val).lower()
    if "leiomyo" in v:
        return 0
    elif "liposarcoma" in v and "dediff" in v:
        return 1
    return np.nan

df_clin["LABEL"] = df_clin[subtype_col].apply(map_label)
cohort = df_clin.dropna(subset=["LABEL"]).drop_duplicates(subset=["CLEAN_BARCODE"]).copy()
cohort["LABEL"] = cohort["LABEL"].astype(int)
lms_n = (cohort["LABEL"] == 0).sum()
ddlps_n = (cohort["LABEL"] == 1).sum()
print(f"\nCohort Subtype Breakdown:")
print(f"  • Class 0 (Leiomyosarcoma / LMS):         {lms_n}")
print(f"  • Class 1 (Dedifferentiated Liposarcoma): {ddlps_n}")
print(f"  • Total Binary Patients (N):              {len(cohort)}")

print("\n" + "=" * 60)
print("STAGE 2: ALIGNING RNA-SEQ EXPRESSION MATRIX")
print("=" * 60)
header = pd.read_csv(EXPR_FILE, sep="\t", nrows=1)
raw_cols = list(header.columns)
gene_col = raw_cols[0]
col_map = {c: c[:15] for c in raw_cols[1:] if c.startswith("TCGA")}
valid_cols = [raw for raw, clean in col_map.items() if clean in set(cohort["CLEAN_BARCODE"])]
print(f"Matching tumor samples found in RNA-seq: {len(valid_cols)} / {len(cohort)}")
cols_to_load = [gene_col] + valid_cols
df_expr = pd.read_csv(EXPR_FILE, sep="\t", usecols=cols_to_load)
df_expr = df_expr.dropna(subset=[gene_col]).drop_duplicates(subset=[gene_col]).set_index(gene_col)
df_expr = df_expr.rename(columns=col_map)
X = np.log2(df_expr + 1.0).T
cohort_idx = cohort.set_index("CLEAN_BARCODE")
y = cohort_idx.loc[X.index, "LABEL"].values

print(f"Aligned Matrix Shape: {X.shape[0]} patients × {X.shape[1]} genes")
print(f"Target Distribution: LMS (0) = {(y == 0).sum()}, DDLPS (1) = {(y == 1).sum()}")
os.makedirs("data_processed", exist_ok=True)
X.to_parquet(os.path.join("data_processed", "X_rnaseq_lms_ddlps.parquet"))
np.save(os.path.join("data_processed", "y_labels.npy"), y)
print("\nExported 'data_processed/X_rnaseq_lms_ddlps.parquet' and 'data_processed/y_labels.npy' successfully.")