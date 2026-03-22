# Risk register

## High-priority risks

| Risk | Why it matters | Current mitigation |
|---|---|---|
| Synthetic-only evaluation | Can be misread as stronger evidence than it is | Explicit disclaimers in README, model card, validation artifact |
| Demo heuristic runtime | Deterministic and testable, but not clinically deployable | `demo_heuristic` mode disclosed in API and docs |
| Image quality variability | Poor-quality retinal photos can degrade outputs | preprocessing quality score + quality flags + monitoring |
| Over-interpretation by users | Medical outputs can invite overconfidence | report disclaimer + assistant disclaimer + portfolio-safe release gate |
| Missing dataset lineage | Hard to audit provenance and generalization | documented as a gap in validation plan |

## Medium-priority risks

| Risk | Why it matters | Current mitigation |
|---|---|---|
| No persistent monitoring backend | Runtime metrics reset on restart | positioned as lightweight demo monitor only |
| No drift ground truth loop | Hard to verify real degradation over time | monitoring endpoint limited to proxy signals |
| No formal access control | Sensitive deployment needs stronger auth | repo framed as engineering demo, not production deployment |
