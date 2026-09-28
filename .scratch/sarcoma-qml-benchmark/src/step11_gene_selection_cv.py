"""
Steps 11-13 (spec.md sec 8), first pass: per-fold gene selection as one sklearn Pipeline,
with every ElasticNet x CV combination tracked in MLflow.

Pipeline, refit from scratch inside every training fold:
    MADFilter(top 1000) -> StandardScaler -> SelectFromModel(elastic-net logistic, top d)
    -> StandardScaler -> LogisticRegression (only there to score the selected genes)

The scores here tell us which selection settings pick stable, useful genes. They are not
the benchmark numbers: picking a setting by its CV score on the same folds is optimistic,
so the final quantum-vs-classical comparison needs the setting fixed first or nested CV.

Default input is RNA-seq only, so the 2 patients with no RNA are left out (153 of 155).
"""

import argparse
import os
import hashlib
import itertools
import json
import subprocess
import tempfile
from pathlib import Path

import mlflow
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.feature_selection import SelectFromModel
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import make_scorer, matthews_corrcoef
from sklearn.model_selection import ParameterGrid, RepeatedStratifiedKFold, cross_validate
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
PROC_DIR = ROOT / "data" / "processed"
MLFLOW_DIR = ROOT / "results" / "mlflow"

SEED = 42
MAD_TOP_K = 1000
MARKER_GENES = ["MDM2", "CDK4", "MYH11", "DES", "ACTA2"]

GRID = {
    "C": [0.03, 0.1, 0.3, 1.0],
    "l1_ratio": [0.2, 0.5, 0.8, 1.0],
    "d": [8, 16],
}


class MADFilter(BaseEstimator, TransformerMixin):
    """Keep the k columns with the largest median absolute deviation, learned on fit only."""

    def __init__(self, k=1000):
        self.k = k

    def fit(self, X, y=None):
        X = np.asarray(X, dtype=float)
        mad = np.median(np.abs(X - np.median(X, axis=0)), axis=0)
        self.keep_ = np.sort(np.argsort(mad)[::-1][: self.k])
        return self

    def transform(self, X):
        return np.asarray(X, dtype=float)[:, self.keep_]


def build_pipeline(C, l1_ratio, d, filter_k=MAD_TOP_K):
    elastic = LogisticRegression(
        l1_ratio=l1_ratio, C=C, solver="saga", class_weight="balanced",
        max_iter=5000, random_state=SEED,
    )
    return Pipeline([
        ("mad", MADFilter(k=filter_k)),
        ("pre_scale", StandardScaler()),
        ("select", SelectFromModel(elastic, max_features=d, threshold=-np.inf)),
        ("scale", StandardScaler()),
        ("clf", LogisticRegression(class_weight="balanced", max_iter=5000, random_state=SEED)),
    ])


def selected_genes(pipe, genes):
    kept = np.asarray(genes)[pipe.named_steps["mad"].keep_]
    return kept[pipe.named_steps["select"].get_support()].tolist()


def n_nonzero_coefs(pipe):
    return int((np.abs(pipe.named_steps["select"].estimator_.coef_) > 0).sum())


def mean_pairwise_jaccard(gene_sets):
    sets = [set(s) for s in gene_sets]
    scores = [len(a & b) / len(a | b) for a, b in itertools.combinations(sets, 2)]
    return float(np.mean(scores))


def load_inputs():
    clin = pd.read_parquet(PROC_DIR / "clinical_labels.parquet").set_index("patient_id", drop=False)
    rna = pd.read_parquet(PROC_DIR / "rna_seq_log2.parquet")
    keep = clin["has_rnaseq"].astype(bool)
    return rna.loc[keep], clin.loc[keep, "label"].astype(int)


def configure_mlflow(experiment_name):
    """Use MLFLOW_TRACKING_URI if set (e.g. a DagsHub repo), else the local sqlite store."""
    uri = os.environ.get("MLFLOW_TRACKING_URI")
    if uri is None:
        MLFLOW_DIR.mkdir(parents=True, exist_ok=True)
        uri = f"sqlite:///{MLFLOW_DIR / 'mlflow.db'}"
        mlflow.set_tracking_uri(uri)
        if mlflow.get_experiment_by_name(experiment_name) is None:
            mlflow.create_experiment(experiment_name, artifact_location=(MLFLOW_DIR / "artifacts").as_uri())
    else:
        mlflow.set_tracking_uri(uri)
    mlflow.set_experiment(experiment_name)
    return uri


def git_state():
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip())
        return commit, dirty
    except Exception:
        return "unknown", None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-splits", type=int, default=5)
    parser.add_argument("--n-repeats", type=int, default=10)
    parser.add_argument("--run-name", default=None)
    args = parser.parse_args()

    X_df, y = load_inputs()
    genes = X_df.columns.to_numpy()
    X = X_df.to_numpy(dtype=float)
    y_arr = y.to_numpy()

    cv = RepeatedStratifiedKFold(n_splits=args.n_splits, n_repeats=args.n_repeats, random_state=SEED)
    n_folds = args.n_splits * args.n_repeats
    scoring = {
        "pr_auc": "average_precision",
        "roc_auc": "roc_auc",
        "balanced_acc": "balanced_accuracy",
        "mcc": make_scorer(matthews_corrcoef),
    }

    configure_mlflow("sarcoma_step11_gene_selection")

    commit, dirty = git_state()
    data_hash = hashlib.sha256((PROC_DIR / "rna_seq_log2.parquet").read_bytes()).hexdigest()[:16]
    combos = list(ParameterGrid(GRID))
    rows = []

    with mlflow.start_run(run_name=args.run_name or "sweep") as parent:
        mlflow.log_params({
            "seed": SEED, "n_splits": args.n_splits, "n_repeats": args.n_repeats,
            "n_folds": n_folds, "mad_top_k": MAD_TOP_K, "n_patients": len(y_arr),
            "n_ddlps_positive": int(y_arr.sum()), "modality": "rna_seq_log2",
            "n_combinations": len(combos), "grid": json.dumps(GRID),
        })
        mlflow.set_tags({"step": "11", "git_commit": commit, "git_dirty": str(dirty),
                         "rna_parquet_sha256_16": data_hash})

        for i, params in enumerate(combos, 1):
            label = f"C={params['C']}_l1={params['l1_ratio']}_d={params['d']}"
            print(f"[{i}/{len(combos)}] {label}", flush=True)
            res = cross_validate(
                build_pipeline(**params), X, y_arr, cv=cv, scoring=scoring,
                return_estimator=True, n_jobs=-1,
            )
            fold_genes = [selected_genes(p, genes) for p in res["estimator"]]
            nonzero = [n_nonzero_coefs(p) for p in res["estimator"]]
            freq = pd.Series([g for s in fold_genes for g in s]).value_counts()
            jaccard = mean_pairwise_jaccard(fold_genes)

            with mlflow.start_run(run_name=label, nested=True):
                mlflow.log_params(params)
                summary = {}
                for metric in scoring:
                    scores = res[f"test_{metric}"]
                    summary[f"{metric}_mean"] = float(scores.mean())
                    summary[f"{metric}_std"] = float(scores.std())
                    for step, val in enumerate(scores):
                        mlflow.log_metric(f"{metric}_fold", float(val), step=step)
                summary["n_nonzero_coefs_mean"] = float(np.mean(nonzero))
                summary["n_nonzero_coefs_min"] = int(np.min(nonzero))
                summary["folds_with_fewer_nonzero_than_d"] = int(sum(n < params["d"] for n in nonzero))
                summary["selection_jaccard_mean"] = jaccard
                for m in MARKER_GENES:
                    summary[f"marker_{m}_selected_frac"] = float(freq.get(m, 0) / n_folds)
                mlflow.log_metrics(summary)

                with tempfile.TemporaryDirectory() as tmp:
                    (Path(tmp) / "selected_genes_per_fold.json").write_text(json.dumps(fold_genes))
                    freq.rename("times_selected").to_csv(Path(tmp) / "gene_selection_frequency.csv")
                    mlflow.log_artifacts(tmp)

            rows.append({**params, **summary, "top_genes": ", ".join(freq.index[:5])})

        table = pd.DataFrame(rows).sort_values("pr_auc_mean", ascending=False)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "combination_results.csv"
            table.to_csv(out, index=False)
            mlflow.log_artifact(str(out))
        print(f"\nparent run id: {parent.info.run_id}")

    show = ["C", "l1_ratio", "d", "pr_auc_mean", "pr_auc_std", "roc_auc_mean", "mcc_mean",
            "n_nonzero_coefs_mean", "folds_with_fewer_nonzero_than_d", "selection_jaccard_mean", "top_genes"]
    print(table[show].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
