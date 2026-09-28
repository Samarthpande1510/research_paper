"""
Second gene selection sweep. The first one (step11_gene_selection_cv.py) showed the spec's
top-1000 MAD filter drops MDM2 and CDK4, so this one varies that filter instead of the
ElasticNet settings.

Decisions applied (2026-09-23): ElasticNet fixed at C=0.1, l1_ratio=0.5; d run at both 8 and 16;
RNA-seq only; 5 splits x 10 repeats = 50 folds; the same 152 patients (those with RNA-seq, CNA
and mutations) so any later model sees identical patients.

Filter options: top 1000 / 3000 / 6500 genes by MAD, or no filter at all.
"""

import argparse
import hashlib
import json
import tempfile
import time
from pathlib import Path

import mlflow
import numpy as np
import pandas as pd
from sklearn.metrics import make_scorer, matthews_corrcoef
from sklearn.model_selection import ParameterGrid, RepeatedStratifiedKFold, cross_validate

from step11_gene_selection_cv import (
    MARKER_GENES, PROC_DIR, SEED, build_pipeline, configure_mlflow, git_state,
    mean_pairwise_jaccard, n_nonzero_coefs, selected_genes,
)

C = 0.1
L1_RATIO = 0.5
GRID = {"filter_k": [1000, 3000, 6500, None], "d": [8, 16]}


def load_common_cohort():
    clin = pd.read_parquet(PROC_DIR / "clinical_labels.parquet").set_index("patient_id", drop=False)
    rna = pd.read_parquet(PROC_DIR / "rna_seq_log2.parquet")
    keep = clin["has_rnaseq"].astype(bool) & clin["has_cna"].astype(bool)
    return rna.loc[keep], clin.loc[keep, "label"].astype(int)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-splits", type=int, default=5)
    parser.add_argument("--n-repeats", type=int, default=10)
    parser.add_argument("--run-name", default="filter_sweep_5x10")
    args = parser.parse_args()

    X_df, y = load_common_cohort()
    genes = X_df.columns.to_numpy()
    X = X_df.to_numpy(dtype=float)
    y_arr = y.to_numpy()
    print(f"patients: {len(y_arr)} (DDLPS positive: {int(y_arr.sum())}), genes: {X.shape[1]}", flush=True)

    cv = RepeatedStratifiedKFold(n_splits=args.n_splits, n_repeats=args.n_repeats, random_state=SEED)
    n_folds = args.n_splits * args.n_repeats
    scoring = {
        "pr_auc": "average_precision",
        "roc_auc": "roc_auc",
        "balanced_acc": "balanced_accuracy",
        "mcc": make_scorer(matthews_corrcoef),
    }

    uri = configure_mlflow("sarcoma_step11b_filter_sweep")
    print(f"tracking to: {uri}", flush=True)
    commit, dirty = git_state()
    data_hash = hashlib.sha256((PROC_DIR / "rna_seq_log2.parquet").read_bytes()).hexdigest()[:16]
    combos = list(ParameterGrid(GRID))
    rows = []

    with mlflow.start_run(run_name=args.run_name) as parent:
        mlflow.log_params({
            "seed": SEED, "n_splits": args.n_splits, "n_repeats": args.n_repeats,
            "n_folds": n_folds, "C": C, "l1_ratio": L1_RATIO, "n_patients": len(y_arr),
            "n_ddlps_positive": int(y_arr.sum()), "modality": "rna_seq_log2",
            "cohort": "has_rnaseq_and_has_cna", "n_combinations": len(combos),
            "grid": json.dumps(GRID),
        })
        mlflow.set_tags({"step": "11b", "git_commit": commit, "git_dirty": str(dirty),
                         "rna_parquet_sha256_16": data_hash})

        for i, params in enumerate(combos, 1):
            k = params["filter_k"]
            label = f"filter={'none' if k is None else k}_d={params['d']}"
            print(f"[{i}/{len(combos)}] {label}", flush=True)
            start = time.time()
            res = cross_validate(
                build_pipeline(C=C, l1_ratio=L1_RATIO, d=params["d"], filter_k=k),
                X, y_arr, cv=cv, scoring=scoring, return_estimator=True, n_jobs=-1,
            )
            seconds = time.time() - start
            fold_genes = [selected_genes(p, genes) for p in res["estimator"]]
            nonzero = [n_nonzero_coefs(p) for p in res["estimator"]]
            freq = pd.Series([g for s in fold_genes for g in s]).value_counts()
            survive = {
                m: float(np.mean([m in set(genes[p.named_steps["mad"].keep_]) for p in res["estimator"]]))
                for m in MARKER_GENES
            }

            with mlflow.start_run(run_name=label, nested=True):
                mlflow.log_params({"filter_k": "none" if k is None else k, "d": params["d"],
                                   "C": C, "l1_ratio": L1_RATIO})
                summary = {}
                for metric in scoring:
                    scores = res[f"test_{metric}"]
                    summary[f"{metric}_mean"] = float(scores.mean())
                    summary[f"{metric}_std"] = float(scores.std())
                    for step, val in enumerate(scores):
                        mlflow.log_metric(f"{metric}_fold", float(val), step=step)
                summary["n_nonzero_coefs_mean"] = float(np.mean(nonzero))
                summary["folds_with_fewer_nonzero_than_d"] = int(sum(n < params["d"] for n in nonzero))
                summary["selection_jaccard_mean"] = mean_pairwise_jaccard(fold_genes)
                summary["seconds"] = seconds
                for m in MARKER_GENES:
                    summary[f"marker_{m}_survives_filter_frac"] = survive[m]
                    summary[f"marker_{m}_selected_frac"] = float(freq.get(m, 0) / n_folds)
                mlflow.log_metrics(summary)

                with tempfile.TemporaryDirectory() as tmp:
                    (Path(tmp) / "selected_genes_per_fold.json").write_text(json.dumps(fold_genes))
                    freq.rename("times_selected").to_csv(Path(tmp) / "gene_selection_frequency.csv")
                    mlflow.log_artifacts(tmp)

            rows.append({"filter_k": "none" if k is None else k, "d": params["d"], **summary,
                         "top_genes": ", ".join(freq.index[:6])})

        table = pd.DataFrame(rows)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "combination_results.csv"
            table.to_csv(out, index=False)
            mlflow.log_artifact(str(out))
        print(f"\nparent run id: {parent.info.run_id}")

    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 40)
    print(table[["filter_k", "d", "pr_auc_mean", "pr_auc_std", "roc_auc_mean", "mcc_mean",
                 "n_nonzero_coefs_mean", "selection_jaccard_mean", "seconds"]].round(3).to_string(index=False))
    print()
    print(table[["filter_k", "d"] + [f"marker_{m}_survives_filter_frac" for m in MARKER_GENES[:2]]
                + [f"marker_{m}_selected_frac" for m in MARKER_GENES] + ["top_genes"]].round(2).to_string(index=False))
    table.to_csv(Path(PROC_DIR).parent.parent / "results" / "step11b_combination_results.csv", index=False)


if __name__ == "__main__":
    main()
