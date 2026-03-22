# Synthetic validation summary

- **Tier:** engineering_synthetic
- **Clinical validation:** not performed
- **Accuracy (synthetic suite):** 100.00%
- **Cases:** 15 / 15
- **Low-quality cases observed:** 0

## Limitations

- Uses synthetic images only; results are not representative of clinical performance.
- Current runtime default is demo_heuristic rather than a trained, locked clinical model.
- No sensitivity, specificity, AUROC, external validation, or subgroup analysis claims are made here.

## Recommended next steps

- Evaluate trained weights on a representative held-out retinal dataset.
- Add dataset lineage, threshold studies, and subgroup checks before any real-world deployment discussion.
- Keep engineering validation clearly separated from regulatory or clinical validation language.
