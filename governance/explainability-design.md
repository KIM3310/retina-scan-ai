# Explainability Design

## 1. Why Grad-CAM

Grad-CAM (Selvaraju et al. 2017) was chosen as the primary explainability mechanism for Retina Scan AI. The decision was driven by four factors:

1. **Faithfulness to the model** — Grad-CAM is computed from the same gradients and activations the network uses for its prediction. Unlike surrogate-model explanations (LIME, SHAP over pixels), it is not a post-hoc approximation. An unfaithful explanation is worse than no explanation because it invites false confidence.

2. **Visual overlay matches clinical workflow** — Clinicians read fundus photographs visually. A spatial heatmap shares the same modality as the work product. A tabular feature-attribution or a natural-language rationalisation would introduce a cognitive switch.

3. **Works on the ResNet18 backbone** — Grad-CAM was designed for CNN architectures with identifiable spatial feature maps; ResNet18's `layer4` output is a clean target. No architectural modification required.

4. **Well-studied in medical imaging** — A substantial body of literature characterises Grad-CAM's behaviour, successes, and failure modes in radiology and ophthalmology. Clinicians trained on GSPS-style overlays find it familiar.

Alternatives considered and rejected:

| Method | Why rejected |
|--------|--------------|
| Integrated Gradients | Produces pixel-level attributions that are noisy and hard for a radiologist to read over fundus anatomy |
| SHAP (DeepExplainer) | Computationally expensive at inference; pixel-level noisiness; requires baseline choice that is non-obvious for medical images |
| LIME | Surrogate model; unfaithful; unstable across segmentation choices |
| Anchors | Not well-suited to dense image classification |
| Attention weights (if transformer) | Not applicable to ResNet18; interpreting attention as explanation is itself contested |
| Counterfactual explanations (GAN-based) | Very heavy compute; generative models for medical imagery introduce their own safety concerns |

See [`../docs/adr/002-gradcam-interpretability.md`](../docs/adr/002-gradcam-interpretability.md) for the decision record.

## 2. What Grad-CAM communicates

### 2.1 What it does convey

- Regions whose activations most increased the model's score for the predicted class
- Approximate spatial attribution at the resolution of `layer4` feature maps (7×7 for 224×224 input), upsampled bilinearly

### 2.2 What it does **not** convey

- Ground-truth location of disease features — Grad-CAM shows what the model attended to, not what is actually present
- Severity of disease
- Confidence of the prediction — the heatmap's visual intensity does not correspond to confidence
- Causation — correlation at most
- Completeness — a region not highlighted is not necessarily free of disease
- Counterfactual reasoning — does not say "had this region been different, the prediction would change"

## 3. Known limitations of Grad-CAM in medical imaging

Clinicians using Grad-CAM must be aware of its failure modes, documented in the literature:

| Limitation | Implication for retinal imaging |
|-----------|--------------------------------|
| Class-discriminative but not lesion-specific | A heatmap for "DR" may point to anatomically informative regions (optic disc, macula) that are characteristic of *images where DR appears* rather than lesions themselves |
| Resolution limitation (7×7 upsampled) | Small lesions (microaneurysms) are not localised precisely; the heatmap smears |
| Sensitive to model capacity | Shallower networks produce coarser maps |
| Can localise to spurious features | Model may attend to a watermark, text overlay, or artefact; clinician interpretation of Grad-CAM must include checking for this |
| May be wrong when the prediction is wrong | A false-positive prediction produces a heatmap that justifies the wrong call; do not use Grad-CAM to confirm a suspect prediction |
| Does not distinguish relevant from confounding | If camera model correlates with disease prevalence in training data, the model may rely on camera-specific features, and the heatmap may point to characteristic image borders |
| Interpretation requires training | Naive users can read confirmatory stories into any heatmap |

These points are reflected in training for clinician users (see [`../docs/clinical/clinician-in-the-loop.md`](../docs/clinical/clinician-in-the-loop.md) §9).

## 4. How Grad-CAM is rendered

The heatmap is converted to a palette-coloured overlay (jet colour map) and rendered:

- As a viewable image alongside the original (via the API's `/gradcam` endpoint)
- As a Grayscale Softcopy Presentation State (GSPS) object for PACS integration — viewer software renders it as a toggleable overlay

In the GSPS form, the overlay can be turned on and off without modifying the underlying fundus pixels, preserving the clinician's primary view of the raw image.

## 5. Overlay colour and contrast

Colour choice matters clinically:
- **Jet** colour map is used in the API visualisation for consistency with scientific imaging conventions
- **Configurable palettes** (viridis, inferno) are offered as alternatives — relevant for clinicians with colour-vision deficiency
- Overlay opacity is adjustable in the UI; default 40%
- No red-green-only encoding so that standard deficiencies do not prevent interpretation

## 6. What clinicians see vs. what the model computes

The model computes, for each image:
- 5 class logits
- 5 calibrated probabilities
- One Grad-CAM heatmap for the top-1 class

The UI surfaces:
- All 5 probabilities as a bar chart
- Top-1 class and calibrated confidence
- Grad-CAM heatmap (toggleable)
- Image quality indicator
- Model version

The UI does **not** surface:
- Raw logits (meaningless to users; confusing)
- Gradient values
- Internal feature maps
- Alternative explanations for non-top-1 classes (considered, deferred — would be a UI clutter risk)

## 7. Grad-CAM computation details

Reference implementation in [`../src/gradcam.py`](../src/gradcam.py) hooks `backbone.layer4`.

```
Given input image x:
1. Forward pass → logits y
2. Target class c (top-1 by default; selectable via API)
3. Zero gradients
4. Backward on y_c
5. Activations A^k from layer4 forward hook
6. Gradients ∂y_c/∂A^k from layer4 backward hook
7. α^k = global average pool of gradients per channel
8. L^c = ReLU(Σ_k α^k · A^k)
9. Upsample bilinearly to input resolution
10. Min-max normalise to [0, 1]
```

## 8. Explainability for failures

When the model is wrong, Grad-CAM still produces a map. We specifically **do not** present the heatmap as evidence of correctness. The UI text for a high-confidence prediction explicitly reminds the user:

> "The heatmap indicates regions that influenced this prediction. A confident prediction may still be wrong; review the image for pathology the model may have missed."

## 9. Relationship to uncertainty

Grad-CAM is a **spatial explanation**. Uncertainty is communicated separately:

- Calibrated confidence on top-1
- Entropy of the full probability distribution (surfaced as a secondary indicator in detailed view)
- Out-of-distribution score (flag, not a number)

Conformal prediction is a future consideration — producing a prediction set with guaranteed coverage. Not in v1.0.

## 10. Audit of explanations

The Grad-CAM heatmap is a reproducible deterministic output given the same weights and input. The SHA-256 of the generated overlay is recorded in the audit log per inference, enabling post-hoc verification that the overlay shown to a clinician matches what was logged.

## 11. What changes if the backbone changes

If a future release changes the backbone (ResNet18 → another CNN), Grad-CAM target layer re-selection is required. If a transformer-based backbone is adopted, a different explanation method (attention rollout; Grad-CAM-like for ViTs) is required. A backbone change is a Tier B change per change control.

## 12. Communicating to patients

Patient-facing information about AI-assisted reading (per DPIA consent text) does **not** currently include the Grad-CAM image. Patients receive the clinician's diagnosis and plan, which may incorporate AI-assisted reading. Direct display of Grad-CAM to patients is not recommended in v1.0 because:

- Heatmaps without clinical training risk misinterpretation
- Patients may seek to challenge a reading based on an overlay they cannot interpret
- Communication should remain mediated by the clinician

## 13. Review cadence

Explainability design is reviewed:
- On every major model release
- If new literature identifies new failure modes for Grad-CAM
- On site feedback that heatmaps are unhelpful or misleading
- Annually

## 14. References

- Selvaraju, R. R. et al. (2017). *Grad-CAM: Visual Explanations from Deep Networks via Gradient-based Localization.* ICCV.
- Adebayo, J. et al. (2018). *Sanity Checks for Saliency Maps.* NeurIPS. (Cautions against over-trusting saliency)
- Rudin, C. (2019). *Stop Explaining Black Box Models and Use Interpretable Models Instead.* Nature Machine Intelligence.
- Kim, B. et al. (2018). *Interpretability Beyond Feature Attribution: Quantitative Testing with Concept Activation Vectors.* ICML.
- Arun, N. T. et al. (2021). *Assessing the Trustworthiness of Saliency Maps for Localizing Abnormalities in Medical Imaging.* Radiology: AI.
