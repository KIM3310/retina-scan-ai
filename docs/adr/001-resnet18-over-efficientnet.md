# ADR 001: ResNet18 over EfficientNet for retinal classification

- **Status**: Accepted
- **Date**: 2026-04-17

## Context

Architectural choice for the retinal classification backbone. Candidates considered: ResNet18, ResNet50, EfficientNet-B0, EfficientNet-B3, ConvNeXt-Tiny, Vision Transformer (ViT-S).

Factors:
- Training dataset size: ODIR-5K is ~5,000 images. Small by deep-learning standards.
- Inference target: 300 ms per image on commodity GPU; sub-second on CPU.
- Explainability: must support Grad-CAM cleanly.
- Transfer learning availability: ImageNet-pretrained weights available for all candidates.
- Deployment: hospital servers are often CPU-only or modest GPU.

## Decision

Use **ResNet18** pretrained on ImageNet, fine-tuned end-to-end with a custom classification head.

## Consequences

### Positive

- **Small parameter count (~11M)**: fits in modest GPU VRAM; CPU inference under a second per image.
- **Stable training on small datasets**: ResNet18 has a long track record on 5K-50K-image datasets. Less risk of overfitting than ViT-S on a 5K dataset.
- **Grad-CAM works cleanly**: the last convolutional layer is well-defined; `src/gradcam.py` hooks into it without architectural acrobatics.
- **Broad tooling support**: ResNet18 weights ship with torchvision; no dependency footprint beyond torch + torchvision.
- **Fast to retrain**: a full epoch of ODIR-5K on a single T4 GPU completes in ~4 minutes. Enables rapid iteration.

### Negative

- **Lower ceiling**: on larger and cleaner datasets, EfficientNet-B3 and ConvNeXt-Tiny typically outperform ResNet18 by 1-3 AUC points on retinal classification tasks.
- **Older architecture**: ResNet18 is 2015-era. Modern architectures have better parameter efficiency.
- **Limited multi-scale reasoning**: ResNet18 has fewer feature pyramid levels than architectures like EfficientNet. For subtle micro-aneurysm detection, this may limit performance.

### Mitigations

- The model interface (`src/model.py`) is abstract: swapping backbones is a one-line change. Future retraining with EfficientNet-B3 or ConvNeXt-Tiny remains open.
- When dataset grows beyond 20K images, revisit: the ceiling advantage of larger models matters more with more data.
- Grad-CAM remains the interpretability substrate regardless of backbone; minor re-wiring needed for different architectures.

## Alternatives considered

### ResNet50

Rejected for this prototype: 25M parameters vs 11M; training time ~2.5x longer; marginal AUC improvement (~1 point) not worth the iteration-speed cost at prototype stage. Would revisit at production scale.

### EfficientNet-B0 / B3

Partially compelling: fewer parameters than ResNet50, better AUC than ResNet18 on ImageNet. Rejected because the pretrained-weights ecosystem and Grad-CAM tooling is slightly less mature than for ResNet. Would consider for a future iteration.

### ConvNeXt-Tiny

Competitive modern architecture. Rejected because: less established in medical imaging literature; limited published retinal-classification baselines; we're prioritizing "known-good" behavior over peak accuracy for a research prototype.

### Vision Transformer (ViT-S / DeiT-S)

Rejected: ViT typically requires more training data than ODIR-5K provides. Published studies show ViT underperforms CNNs on < 10K medical image datasets unless extensively pretrained on medical-specific data.

### Model ensembles

Explicitly deferred: ensembles improve AUC by 1-2 points at 3-5x inference cost. Not justified for a prototype where latency matters; would revisit for a production deployment with load-balanced inference servers.

## How this choice constrains future work

- **Dataset growth triggers architecture review**: at 20K+ training images, the gap between ResNet18 and modern architectures widens enough to matter. Add to roadmap to re-evaluate.
- **Multi-scale features may require backbone swap**: if analysis of model errors shows small-lesion misses, that points to the backbone limitation, not just training data.
- **Production deployment may prefer ONNX export**: ResNet18 has excellent ONNX coverage across runtimes; this is a secondary advantage.

## References

- ResNet paper: He et al., "Deep Residual Learning for Image Recognition" (CVPR 2016).
- EfficientNet paper: Tan & Le, "EfficientNet: Rethinking Model Scaling" (ICML 2019).
- Retinal classification benchmark (Rajpurkar et al. 2017): https://arxiv.org/abs/1711.05225
- `src/model.py` — implementation.
- `src/gradcam.py` — interpretability hook.
