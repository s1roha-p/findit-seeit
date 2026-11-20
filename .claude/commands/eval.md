---
description: MAIN — run one evaluation by the protocol (dev or test split, frozen parameters, one immutable record).
---
Evaluation request: $ARGUMENTS (part letter, what is measured, split). If the split or the configuration is missing,
ask - do not guess.

Read `docs/project/EVALUATION_PROTOCOL.md` and the part's section of `docs/project/WORK_SPLIT.md`. Check that the
evaluation script exists under `eval/` and that the manifest it reads (`data/manifests/`) exists; never open the test
split with parameters that are still being tuned. Claim the device and files on `work/WORKBOARD.md`. Record the code
commit, environment, machine, dataset manifest and its sha256, configuration and every run (keep failed and partial
runs). Write one record per run under `work/results/` (never overwrite). Report the record ids, the numbers with n and
tier, what the evaluation does not show, and whether the result may go on a slide (E2 only).
