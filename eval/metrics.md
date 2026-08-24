# Offscript measured results

Targets are copied from PROJECT.md. The measured column stays blank until the
40 item eval set is complete and `python eval/run_eval.py` is run against a
real `predict()`, not the stub.

Do not fill this in by hand from a partial dataset. Paste the table that
`run_eval.py` prints.

Never paste a measured value without its `n`. The harness prints the sample
count next to every metric for exactly this reason.

## Headline

| metric | target | measured | n | verdict |
|--------|--------|----------|---|---------|
| Recall on scam | above 0.90 | | | |
| False positive rate on legitimate | below 0.10 | | | |
| Stage accuracy | above 0.70 | | | |
| Next stage prediction accuracy | above 0.60 | | | |

## Supporting

| metric | measured | n |
|--------|----------|---|
| Precision on scam | | |
| Script identification accuracy | | |
| Per turn stage accuracy | | |
| Verifier coverage, verifiable in principle | | |
| Verifier coverage, machine resolvable offline | | |

Quote the machine resolvable number, not the in principle one. The gap between
them is the part settled by background knowledge rather than by a check that
runs offline, and a judge who asks how the check works will find that gap.

## Annotation quality

From `python eval/agreement.py <dir_a> <dir_b>` on the double annotated 10
percent. Not a model metric — a dataset metric, and the one that makes every
number above mean something.

| metric | target | measured | n |
|--------|--------|----------|---|
| Cohen's kappa on stage labels | above 0.70 | | |
| Percent agreement | | | |

## Run log

One row per eval run on the day. Keep every run, including the bad ones, so we
can show the judges that the final number was not cherry picked.

| run | time | dataset size | recall | fpr | stage acc | next stage acc (n) | what changed |
|-----|------|--------------|--------|-----|-----------|--------------------|--------------|
| 0 | pre event | 3 | 0.00 | 0.00 | 0.00 | 0.00 (n=1) | stub predict(), harness smoke test only |
| 1 | pre event | 3 | 0.00 | 0.00 | 0.00 | 0.00 (n=2) | harness side truncation, every scam record now contributes a next stage |
| 2 | pre event | 3 | 0.00 | 0.00 | 0.00 | 0.00 (n=2) | three state verdicts, verifier coverage 0.79 (n=14) added |
| 3 | pre event | 3 | 0.00 | 0.00 | 0.00 | 0.00 (n=2) | coverage split in two, in principle 0.79 vs machine resolvable 0.36 (n=14) |
