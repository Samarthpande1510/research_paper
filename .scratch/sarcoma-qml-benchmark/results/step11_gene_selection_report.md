# Gene selection sweep: what we ran and what it showed

Date: 2026-09-23. Script: `src/step11_gene_selection_cv.py`. Tracked in MLflow (experiment
`sarcoma_step11_gene_selection`, full run named `full_5x10`, run id
`0296fe19fd674649b655c8f9859abe57`).

This is the first real output of the modeling side of the project. It is not the
quantum-vs-classical benchmark yet. It answers a smaller, earlier question: when we shrink
20,518 genes down to 8 or 16, does the way we do the shrinking matter, and are the picks
any good?

## The short version

1. Every setting we tried works well. PR-AUC (our main score) ranges from 0.963 to 0.990.
   That's the near-ceiling result your spec warned about, since LMS and DDLPS are easy to
   tell apart.
2. Because everything scores so high, most differences between settings are smaller than
   the normal wobble from fold to fold. There's no meaningful "winner" among the top
   settings.
3. Four settings are broken in a specific way (they can't find enough genes and fill the
   gap with arbitrary ones). Ignore them.
4. **The biggest finding: the MAD filter throws away MDM2 and CDK4**, the two genes your
   logbook showed separate the classes best on their own. That's a decision for you, see
   "What to decide next".
5. The genes picked change a lot from fold to fold. That's normal when many genes carry
   the same signal, but it means we shouldn't treat any single selected gene as "the"
   answer.

## What we actually did

We used 153 patients (the 2 with no RNA-seq are left out, since this run only uses gene
expression). For each test, the computer splits the patients into 5 groups, trains on 4
and tests on the held-out 1, then rotates through all 5. We repeated that whole thing 10
times with different random splits. That gives **50 folds** per setting.

Inside every one of those 50 folds, using only that fold's training patients, a scikit-learn
`Pipeline` does these steps in order:

1. **MAD filter:** keep the 1,000 genes that vary the most across patients.
2. **Scale** those genes so they're comparable.
3. **Elastic net selection:** fit a logistic regression with an elastic net penalty and
   keep the top `d` genes by weight (d is 8 or 16).
4. **Scale** the chosen genes again.
5. **Score** them with a plain logistic regression on the held-out patients.

Doing all of this inside each fold is the whole point. If we picked genes using all the
patients first, the test patients would have secretly helped choose the genes and the
scores would look better than they really are.

The settings we swept (every combination, 4 x 4 x 2 = 32 of them):

| Setting | Values | What it does |
|---|---|---|
| `C` | 0.03, 0.1, 0.3, 1.0 | How strict the penalty is. Small C means strict: fewer genes get any weight at all. |
| `l1_ratio` | 0.2, 0.5, 0.8, 1.0 | Mix inside the elastic net. 1.0 is pure Lasso (aggressively drops genes). Lower values are gentler and let similar genes share weight. |
| `d` | 8, 16 | How many genes we keep at the end. |

## How to read the numbers

- **PR-AUC** (main score, 0 to 1, higher is better): how well the model ranks the true
  DDLPS patients above the LMS ones, weighted toward not missing the smaller class.
  Random guessing would land near the DDLPS share of the data, a perfect model gets 1.0.
- **ROC-AUC:** a similar ranking score. Less strict about the smaller class.
- **Balanced accuracy:** the average of "how many DDLPS did we catch" and "how many LMS did
  we catch", so the bigger class can't hide mistakes.
- **MCC:** one number from -1 to 1 that punishes any kind of mistake, useful when classes
  are uneven.
- **`pr_auc_std`:** how much the score bounced around across the 50 folds. This is your
  yardstick for "is this difference real?". If two settings differ by less than this, treat
  them as tied.
- **Non-zero coefficients:** how many genes the elastic net gave any weight to. If this is
  smaller than `d`, the pipeline had to fill the gap with genes that have zero weight.
- **Jaccard:** how similar the selected gene lists are between folds. 1.0 means every fold
  picked the identical genes, 0 means no overlap at all.

## Results

Best five settings by PR-AUC:

| C | l1_ratio | d | PR-AUC | Std across folds | Balanced acc | MCC |
|---|---|---|---|---|---|---|
| 0.03 | 0.2 | 16 | 0.990 | 0.016 | 0.951 | 0.898 |
| 0.10 | 0.5 | 16 | 0.988 | 0.015 | 0.949 | 0.894 |
| 0.10 | 1.0 | 16 | 0.987 | 0.016 | 0.946 | 0.889 |
| 0.30 | 0.8 | 16 | 0.987 | 0.016 | 0.946 | 0.888 |
| 0.10 | 0.8 | 16 | 0.987 | 0.017 | 0.944 | 0.884 |

The gap between first and fifth place is 0.003. The fold-to-fold wobble is about 0.016.
That's five times bigger, so these are effectively tied. (The third row is one of the
broken settings, see below.)

Average PR-AUC when you group the results by one setting:

| Group | Average PR-AUC |
|---|---|
| d = 8 | 0.979 |
| d = 16 | 0.986 |
| C = 0.03 / 0.1 / 0.3 / 1.0 | 0.983 / 0.984 / 0.983 / 0.980 |
| l1_ratio = 0.2 / 0.5 / 0.8 / 1.0 | 0.980 / 0.982 / 0.983 / 0.984 |

The only pattern that stands out is that keeping 16 genes beats keeping 8, by about 0.007
on average, and the worst results (0.963, 0.971) all have d = 8 with a gentle elastic net
mix and a weak penalty. Everything else is within noise. Also, only 8 or 16 genes is
already enough to reach 0.98+, which supports the idea that this task is easy.

## Things that went wrong or need care

**1. Four settings can't find enough genes.** With a strict penalty (small C) and heavy
Lasso mixing, the model gives weight to only about 5 to 11 genes in most folds, but we
asked for 8 or 16. When that happens the pipeline fills the rest with zero-weight genes
in whatever order they sit in the table, which is alphabetical. You can see it in the
output: the "top genes" for these settings are ABCA6, ABCA8, ABCB5, ABCC8, all starting
with the letters A and B. Affected settings (number of folds out of 50 that came up
short):

| C | l1_ratio | d | Short folds |
|---|---|---|---|
| 0.03 | 1.0 | 16 | 50 |
| 0.03 | 0.8 | 16 | 50 |
| 0.03 | 1.0 | 8 | 49 |
| 0.10 | 1.0 | 16 | 21 |

Their scores still look fine, which is misleading. Three of them have high Jaccard values
(0.52 to 0.70) and the odd "ACTA2 was picked 46% of the time" for one of them are both side effects
of that alphabetical filling, not real signal. I'd drop these four from consideration.

**2. Selected genes differ between folds.** For the 28 healthy settings, the typical
(median) Jaccard is 0.34 (range 0.28 to 0.55). Two folds share roughly a third of their genes. With
thousands of genes that rise and fall together, the model can swap one for another and
score the same. It's a reason not to over-interpret any single gene in the list.

**3. These scores are a bit optimistic.** We compared 32 settings using the same folds
that produced the scores. Picking the top one then quoting its score flatters it slightly.
For the real benchmark, either fix the settings before looking, or use nested
cross-validation.

**4. Small sample.** 153 patients, so the fold-to-fold wobble is real and won't shrink
much.

## The MDM2 and CDK4 finding

Your logbook found that MDM2 alone separates LMS from DDLPS at about 91 to 94%, and CDK4 at
about 88 to 91%. These are the genes in the 12q amplicon that defines DDLPS. Our sweep
picked MDM2 in **0%** of folds in every setting, and CDK4 the same.

The reason is the first step, the MAD filter. I checked where each gene ranks out of
20,518 (using all patients, purely as a diagnostic, nothing was selected from this):

| Gene | MAD rank | Needed to survive |
|---|---|---|
| MDM2 | 6,338 | top 1,000 |
| CDK4 | 4,974 | top 1,000 |
| MYH11 | 3 | passes |
| DES | 84 | passes |
| ACTA2 | 1,016 | just misses |

MAD stands for median absolute deviation. It measures spread around the middle patient.
DDLPS is only about 38% of patients, and when a minority group has a high value, the
middle patient still sits in the big low group, so the spread looks small. MAD is designed
to ignore exactly this kind of minority, which is a problem here because the minority
is the signal. Ranking by ordinary standard deviation doesn't rescue them either (MDM2
lands at 1,431 and CDK4 at 1,634).

MYH11 and DES do survive the filter but are almost never chosen. That's most likely
because other genes (TPM2 and similar) carry the same information and the elastic net
picks among lookalikes. I haven't verified that.

The genes that got picked most often across settings (TPM2, SPATA18, PLAC9, SLC19A3, DKK1,
ABCA8, CARMN) are not markers we planned around. I haven't checked their biology, so I
can't say what they mean. Since the scores are so high anyway, the practical effect on
accuracy is small, but it does mean the gene list we'd feed to the quantum models isn't the
one the biology story predicts.

## What to decide next

1. **Keep the MAD filter as the spec says, or change it?** Options: keep it and accept that
   MDM2/CDK4 are dropped, raise the number of genes it keeps (a much larger k), or skip
   the unsupervised filter and let the elastic net see more genes. This is a change to
   your spec, so it's your call.
2. **Which settings to carry forward.** I'd suggest `d = 16` with a moderate penalty
   (`C` around 0.1 to 0.3) and `l1_ratio` around 0.5 to 0.8, excluding the four broken
   ones. Nothing here proves those are better than their neighbors.
3. **RNA only, or add CNA and mutations to the funnel.** This run is RNA only. CNA might
   pick up the 12q amplicon directly, which is worth trying given the MDM2 result.
4. **Fix the fold count.** The spec says "5x5 (50-fold)", which doesn't add up (5x5 is 25).
   I used 5 splits x 10 repeats = 50. Tell me if you meant 5x5 = 25.

## Where everything is

- MLflow page: http://127.0.0.1:5050 (only works on your machine while the server runs).
  Open the experiment `sarcoma_step11_gene_selection`, then the run `full_5x10`. Click
  into any of its 32 child runs to see that setting's per-fold scores and the exact genes
  it chose in each fold.
- To start the page again later, from the repo root:
  `uv run mlflow server --backend-store-uri sqlite:///$(pwd)/.scratch/sarcoma-qml-benchmark/results/mlflow/mlflow.db --port 5050`
- Data behind MLflow: `results/mlflow/` (database plus artifacts). Full table of all 32
  settings: the `combination_results.csv` artifact on the parent run.
- There's also an older, smaller test run called `smoke_test` (1 repeat, 5 folds) in the
  same experiment. Ignore it, it was a check that the code worked.
