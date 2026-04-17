# ADR 002: Grad-CAM as the interpretability substrate

- **Status**: Accepted
- **Date**: 2026-04-17

## Context

Clinical imaging AI systems require interpretability. The clinician must be able to ask "why did the model say DR?" and get a useful answer.

Candidates considered:
1. Grad-CAM (Selvaraju et al. 2017).
2. Grad-CAM++.
3. Integrated Gradients.
4. LIME.
5. SHAP.
6. Occlusion maps.
7. Attention rollout (for transformer models).
8. Counterfactual explanation (e.g., StyleGAN-based).

## Decision

**Grad-CAM** is the default interpretability layer. Grad-CAM++ is supported as an optional alternative. Other techniques are deferred.

## Consequences

### Positive

- **Runtime cost low**: Grad-CAM is a single backward pass; latency impact <100 ms per image on the target hardware. Inline with inference SLA.
- **Well-established in medical imaging**: peer-reviewed literature on Grad-CAM in retinal screening, chest X-ray, pathology. Clinicians familiar with heatmap overlays.
- **Straightforward implementation**: ResNet18's final conv layer is the natural hook. `src/gradcam.py` is ~100 LOC.
- **Produces intuitive output**: a smooth heatmap over the fundus image. Non-technical clinicians interpret it quickly.
- **Architecture-agnostic at the CNN level**: works for ResNet, EfficientNet, ConvNeXt with minor hook changes.

### Negative

- **Approximate, not causal**: Grad-CAM highlights activation patterns that correlate with the prediction; it doesn't causally explain.
- **Low spatial resolution**: the heatmap is at the last-conv-layer spatial resolution (typically 7×7 or 14×14), upsampled. Fine-grained lesion localization is poor.
- **Automation bias risk**: always-visible heatmaps anchor the clinician's attention.
- **Doesn't support transformer models cleanly**: future backbone switch (ViT) would require attention rollout, not Grad-CAM.

### Mitigations

- **Opt-in in the UI**: the Grad-CAM overlay is toggled by the clinician (`G` keyboard shortcut), not shown by default. See `clinical_ui/design-rationale.md`.
- **Disclaimer in the clinical UI**: "Heatmap shows where the model attended. Not a clinical explanation."
- **Pair with confidence distribution**: Grad-CAM is one signal; the full class probability distribution is another. Clinicians are trained to use both.
- **Document limitations clearly**: `governance/explainability-design.md` captures what Grad-CAM can and cannot tell you.
- **Keep alternatives open**: `src/gradcam.py` has a pluggable design; adding Integrated Gradients or SHAP is a module addition, not a rewrite.

## Alternatives considered

### Grad-CAM++

Refinement over Grad-CAM that improves spatial localization. Rejected as default because the improvement is modest for our backbone and the implementation is more complex. Supported as an optional method.

### Integrated Gradients

Stronger causal grounding than Grad-CAM. Rejected because:
- Computational cost: 20-50 forward passes per explanation (too slow for our latency target).
- Output is at pixel resolution (potentially noisy, harder to display as heatmap).

Deferred for offline batch explanations where latency is not constrained.

### LIME

Perturbation-based explanation. Rejected because:
- Computational cost: dozens of inference calls per explanation.
- Output stability depends on random sampling; repeat explanations may differ.

Not suitable for clinical-triage latency.

### SHAP

Similar issues to LIME at our image scale. Image-SHAP requires pixel segmentation; implementation complexity and latency are both high.

### Occlusion maps

Conceptually clean: systematically occlude regions and measure prediction change. Rejected because the required number of inference calls (hundreds per image) is incompatible with our latency budget.

### Counterfactual explanations

Strong interpretability: "the model predicts Normal if this lesion were not present." Current state of the art (StyleGAN-based) is research-grade; infrastructure cost is prohibitive for a prototype.

Deferred indefinitely.

### Attention rollout

Only applicable to transformer backbones. Not relevant given the ResNet18 decision in ADR 001.

## How this constrains future work

- **Backbone change to ViT** requires switching from Grad-CAM to attention rollout; rewrite `src/gradcam.py` as `src/interpretability/`.
- **Regulatory submission** will require validating that Grad-CAM outputs are stable and reproducible across versions. Add automated tests.
- **Clinical workflow study** should measure whether Grad-CAM opt-in actually gets used and whether it changes clinician accuracy.

## Implementation notes

- Grad-CAM hook: `src/gradcam.py` registers a forward hook on the final conv layer to capture activations and a backward hook to capture gradients.
- Heatmap is upsampled via bicubic interpolation to the input resolution.
- Heatmap is normalized to [0, 1] for consistent rendering.
- The clinical UI overlays the heatmap with alpha 0.5 and a sequential colormap (viridis by default; the UI offers colormap choice for accessibility).

## References

- Selvaraju et al., "Grad-CAM: Visual Explanations from Deep Networks via Gradient-based Localization" (ICCV 2017): https://arxiv.org/abs/1610.02391
- Arun et al., "Assessing the (Un)Trustworthiness of Saliency Maps for Localizing Abnormalities in Medical Imaging" (2021): https://arxiv.org/abs/2008.02766
- Adebayo et al., "Sanity Checks for Saliency Maps" (NeurIPS 2018): https://arxiv.org/abs/1810.03292
- `src/gradcam.py` — implementation.
- `governance/explainability-design.md` — user-facing documentation.
