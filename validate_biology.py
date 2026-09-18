import os
import pandas as pd
import numpy as np
# Loading the processed data
X = pd.read_parquet(os.path.join("data_processed", "X_rnaseq_lms_ddlps.parquet"))
y = np.load(os.path.join("data_processed", "y_labels.npy"))
print("=" * 60)
print("BIOLOGICAL SIGNAL VALIDATION")
print("=" * 60)
genes_to_check = ["MDM2", "CDK4", "ACTA2", "MYH11"]
present_genes = [g for g in genes_to_check if g in X.columns]
for gene in present_genes:
    lms_expr = X.loc[y == 0, gene].mean()
    ddlps_expr = X.loc[y == 1, gene].mean()
    fold_diff = ddlps_expr - lms_expr
    expected = "Higher in DDLPS (Class 1)" if gene in ["MDM2", "CDK4"] else "Higher in LMS (Class 0)"   
    print(f"Gene: {gene:<8} | Expected: {expected}")
    print(f"  • LMS Mean (log2):   {lms_expr:.3f}")
    print(f"  • DDLPS Mean (log2): {ddlps_expr:.3f}")
    valid = (fold_diff > 0) if gene in ["MDM2", "CDK4"] else (fold_diff < 0)
    print(f"  • Signal Direction:  {'✅ Valid' if valid else '❌ Warning'}\n")