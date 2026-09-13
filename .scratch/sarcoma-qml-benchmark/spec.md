Status: ready-for-agent

# Sarcoma QML Benchmark — Project Spec & Data Acquisition Guide

Self-contained brief for continuing this work in a new chat. Source material: `Quantum_vs_DeepLearning_Sarcoma_Report...docx` (original protocol) plus a methodological review (`grilling` skill session) that resolved several open decisions in that protocol — those resolutions are already folded into this spec, not left as open questions.

## 1. Research question

Can quantum-enhanced feature representations (quantum kernels, variational quantum circuits) outgeneralize classical tabular deep learning on an ultra-sparse, high-dimensional multi-omics cancer classification task — specifically where the training cohort is too small (N < 200) for deep neural networks to avoid overfitting?

## 2. Scope decision (resolved)

This project is a **standalone phase**: a two-class sarcoma subtype classification task only. It does **not** currently include a sarcoma-vs-healthy-tissue task or a tumor-grade classification task — those were part of an earlier three-stage design (sarcoma-vs-not → subtype → grade) but are treated as separate future phases, not merged into this one. Reason: merging them multiplies the statistical testing surface without adding power to the central claim, and keeps this phase's question uncontaminated by unrelated confounds (batch effects for the healthy-tissue comparison; a different N and data source for grade).

## 3. Dataset & task definition

- **Source**: TCGA-SARC PanCancer Atlas (`sarc_tcga_pan_can_atlas_2018` on cBioPortal), N = 261 total annotated tumors.
- **Task**: binary classification, **Leiomyosarcoma (LMS, n=105)** vs. **Dedifferentiated Liposarcoma (DDLPS, n=58)** — total working cohort N = 163.
- **Why this pair**: molecularly clean, batch-effect-free separation (LMS: TP53/RB1/ATRX/PTEN alterations; DDLPS: pathognomonic 12q13-15 amplicon / MDM2, CDK4) with no confound from mixing tumor and normal tissue from different sources.
- **Class ratio**: ≈1.81:1 (LMS:DDLPS) — imbalanced enough that raw accuracy is not a valid metric.
- **Excluded from this phase**: UPS (n=51), MFS (n=25), SS (n=13), MPNST (n=9) — heterogeneous/too small for this comparison; SS and MPNST are candidate cohorts for a *separate* generalization check (see §7).

## 4. Modalities & preprocessing

- **Clinical/sample file (required — label source, not optional)**: `data_clinical_patient.txt` / `data_clinical_sample.txt` from cBioPortal. This is where the LMS-vs-DDLPS class label (y) comes from — none of the omics files carry it.
- **Cohort provenance (resolved 2026-09-13):** the spec's 105 LMS / 58 DDLPS traces to a 2016-01-28 GDAC Firehose clinical freeze (`histological_type` field), not to cBioPortal's current `SUBTYPE`/`ICD_O_3_HISTOLOGY`/`CANCER_TYPE_DETAILED` columns — none of which reproduce it standalone. All 163 patients are confirmed to exist in GDC with complete RNA-seq + Genotyping Array (CNA) + WXS (mutation) coverage. The gap: cBioPortal's `sarc_tcga_pan_can_atlas_2018` bundle (the files this pipeline downloads) is missing 5 of the 105 LMS patients (`TCGA-HS-A5N9`, `TCGA-IF-A4AK`, `TCGA-PC-A5DM`, `TCGA-PC-A5DP`, `TCGA-PT-A8TR`) entirely — present and complete in GDC, just not in this specific cBioPortal export. DDLPS's apparent 59-vs-58 mismatch is not a gap: one 2016-labeled DDLPS patient (`TCGA-MO-A47P`) was reclassified to a different liposarcoma subtype since then, and the spec's 58 already reflects that correction. **Open decision before step 6**: either work with N=158 (100+58, cBioPortal-only, zero extra engineering) or pull the 5 missing LMS patients' raw files directly from GDC and reprocess them to match cBioPortal's RSEM/GISTIC2 conventions to reach the full N=163. See the acquisition log's provenance addendum for detail.
- **RNA-seq**: RSEM normalized counts, transformed via `log2(RSEM + 1)`.
- **Copy-number (CNA)**: GISTIC2 thresholded calls (-2 deep deletion … +2 high amplification); missing segments default to diploid (0).
- **Somatic mutations**: MAF files pivoted into an N × G binary indicator matrix (1 = non-synonymous mutation).
- **Methylation (optional layer)**: Illumina 450k beta-values, <0.8% missing; impute with k-NN (k=5) **strictly inside training folds only** — never on the full dataset (leakage).
- **Dimensionality funnel to 8–16 features** (NISQ qubit ceiling), computed inside each CV fold:
  1. Unsupervised MAD filtering → top 1,000 highest-variance genes.
  2. Supervised ElasticNet/Lasso → top *d* ∈ {8, 16} driver genes (hard ceiling: 30).
  3. Min-max scale to [0, π] for quantum angle encoding.

## 5. Models in scope

**Core (required — do not cut under time pressure):**

| Model | Why it's required |
|---|---|
| Deep Tabular MLP | The classical **deep learning** comparator the paper's title claims to test against. Cutting this in favor of RBF-SVM would leave the flagship claim untested even in a "trimmed" run. |
| Projected Quantum Kernel (PQK-SVM) | Avoids the exponential-concentration failure mode of fidelity kernels as qubit count scales; primary QML kernel candidate. |
| Hybrid QNN / VQC | EfficientSU2 ansatz, 8 qubits, 2 entangling layers, 32 trainable params; parameter-shift + Adam optimization. |

**Optional / stretch (add only if time remains, in this order):**

1. RBF-SVM (secondary baseline — direct classical mathematical analog to the quantum kernels, useful but not a deep-learning stand-in).
2. TabNet, XGBoost.
3. Fidelity Quantum Kernel (FQK-SVM).
4. Experiment 3 (hardware-noise sensitivity — see §6, renamed).

## 6. Experiments in scope

1. **Experiment 1 — Full Cohort Benchmark**: all in-scope architectures across the full 163-patient cohort.
2. **Experiment 2 — Sample-Size Ablation**: downsample training folds to N_train ∈ {20, 40, 80, 130}; plot degradation curves to find where classical DL collapses vs. where quantum kernels hold margin stability. **Caveat**: at N_train=20 with the ~1.81:1 ratio, the minority class drops to ~7 cases — keep this point in the learning-curve plot (it's informative) but exclude it from any table reporting a point estimate or significance test; label it "descriptive only, underpowered."
3. **Experiment 3 — *Simulated* NISQ-Noise Sensitivity Analysis** *(renamed; stretch goal)*: Qiskit AerSimulator with thermal-relaxation/depolarizing noise parameters derived from published IBM Quantum Heron figures. **This is a simulation, not a hardware run** — every writeup of this experiment must state explicitly that no physical quantum hardware was used, since simulated noise models don't capture real crosstalk/correlated hardware errors.

## 7. Statistical methodology (resolved)

- **Metric hierarchy** (unchanged from original protocol, given class imbalance): PR-AUC (primary) → ROC-AUC → Balanced Accuracy → MCC.
- **Null hypothesis, stated before training begins**: H₀ = no significant PR-AUC difference between the best quantum model and the MLP. Commit to reporting a null result with equal weight to a positive one — the QML benchmarking literature has a documented pattern of claimed kernel advantages disappearing under fair classical baselines, so pre-committing to symmetric reporting guards against that bias.
- **One confirmatory test**: best quantum model vs. MLP on PR-AUC, pre-registered before data collection.
- **Everything else exploratory**: all other pairwise/metric comparisons get FDR correction, not treated as confirmatory findings.
- **Correlated-fold correction**: use a correlation-aware / variance-corrected significance test (e.g., a corrected resampled t-test) on the repeated 5×5 (50-fold) cross-validation output — naive paired Wilcoxon/DeLong tests understate variance when folds are correlated, inflating false positives.
- **Generalization check**: promoted from optional to required — after the primary LMS-vs-DDLPS result, re-run the best-performing pipeline on a secondary independent cohort (cBioPortal GBM or LAML) to check the result isn't an artifact of this one 163-patient cohort.

## 8. Step-by-step data acquisition & preprocessing

No special credentials needed for anything below — all open-access. Controlled-access dbGaP approval would only be required for raw BAM/germline VCF files, which this plan never touches.

1. **Confirm access.** cBioPortal bulk downloads, GDC open-access files, and UCSC Xena are all open-access. Nothing to request.
2. **Download from cBioPortal.** On the `sarc_tcga_pan_can_atlas_2018` study page → Download tab, get: `data_mrna_seq_v2_rsem.txt`, `data_cna.txt`, `data_mutations.txt`, `data_clinical_patient.txt`, `data_clinical_sample.txt`.
3. **Cross-check against GDC.** Independently pull the GDC Data Portal file manifest for TCGA-SARC, filtered to RNA-Seq, Genotyping Array (CNA), and MAF strategies. Compare case counts against cBioPortal's files — do not assume the two portals cover identical cases without checking.
4. **(Optional) GTEx healthy-tissue layer.** If a normal-tissue comparison is ever added in a later phase, separately download the TCGA-TARGET-GTEx Toil recompute matrix from UCSC Xena. Note it's normalized as `log2(TPM+0.001)` — a different pipeline from cBioPortal's RSEM — and keep it in its own file until step 8 below.
   - **Known fact**: TCGA-SARC has 24 Solid Tissue Normal samples (verified against the GDC API — the original protocol draft undercounted this as "<4"). Still too few/uneven for a standalone cancer-vs-normal training set, but usable as a small batch-effect-free validation check if this layer is added later.
5. **Archive raw downloads.** Store every file exactly as received, in a dated folder, before any editing. This is the first logbook entry and the reference point if anything downstream looks wrong.
6. **Merge into one working table.** Join the clinical, expression, CNA, and mutation files on patient barcode, restricted to the LMS-vs-DDLPS scope from §3 (not the six-subtype-plus-healthy scope — that's out of scope per §2).
7. **Verify missingness on the real table, not the assumed one.** Count actual non-missing values per candidate feature and per patient on the merged table; log the counts. Only impute or drop what the count shows is actually missing — the original protocol's "zero missing cells" claim has not been verified against this exact 163-patient subset, so confirm it rather than assuming it.
8. **(Optional) Harmonize GTEx units.** If step 4's data is used, reconcile gene identifiers (Ensembl vs. HGNC symbol) and expression units between cBioPortal/GDC and Xena TOIL before merging — RSEM and `log2(TPM)` are not the same scale and cannot be combined directly.
9. **Apply per-modality transforms**: `log2(RSEM+1)` for expression; GISTIC2 thresholded calls for CNA (missing → diploid/0); binary gene-level indicator matrix for somatic mutations.
10. **Do not carve out a separate held-out set.** *(Deviation from the original protocol.)* Rely on each cross-validation fold's own test partition as the honest per-fold evaluation instead of an additional single held-out split — at n=163 with only 58 minority-class cases, a second untouched split starves the minority class for negligible benefit, given the strict per-fold refitting in step 11.
11. **Per-fold feature selection, inside training folds only.** MAD filtering to the top 1,000 most variable genes, then ElasticNet/Lasso down to the final feature count (8–16, ceiling 30) — reselect independently per fold, never once on the full dataset.
12. **Per-fold scaling.** From the fold-specific feature set, branch into two scalers: standard/min-max scaling for the classical models (MLP, and TabNet/XGBoost/RBF-SVM if in scope), and min-max scaling to [0, π] for angle encoding into the quantum models (PQK-SVM, HQNN, and FQK-SVM if in scope). Fit both scalers only on the training fold.
13. **Fix and log random seeds** for every stochastic component: network initialization, variational circuit parameter initialization, cross-validation fold assignment.
14. **Log everything before training**: which features were selected per fold, how many values were imputed, which scaler produced which table. This is what makes results traceable later.
15. **Write the null hypothesis into the record** (§7) before training starts.
16. **Begin Experiment 1** (full-cohort benchmark) only once steps 1–15 are complete and logged.

*(A future grade-classification phase, if pursued, needs `data_clinical_sample.txt` from the `sarc_tcga_pub` study specifically — not `pan_can_atlas_2018` — for its `FNCLCC_GRADE` column, which is filled for all 239 sample rows there vs. mostly blank in the PanCancer Atlas file. Not required for the current phase; noted here so it isn't rediscovered from scratch later.)*

## 9. What NOT to change

Carried over from the original protocol, confirmed sound during review — don't second-guess these:
- Per-fold feature selection (already leakage-safe).
- The sample-size ablation design in Experiment 2 (exactly the learning-curve evidence a data-efficiency claim needs).
- The PR-AUC/MCC-led metric hierarchy given the class imbalance.
- Paired significance testing across repeated cross-validation as a *concept* (only the specific test statistic changes per §7).
