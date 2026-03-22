"""Generate engineering-validation artifacts for Retina-Scan-AI.

These artifacts are synthetic/offline and support engineering review only.
They are not clinical validation claims.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import numpy as np
from PIL import Image

from app.models.classifier import DISEASE_DISPLAY_NAMES, DiseaseLabel, RetinalClassifier
from app.preprocessing.pipeline import RetinalPreprocessor
from tests.conftest import (
    make_amd_fundus,
    make_cataracts_fundus,
    make_diabetic_retinopathy_fundus,
    make_glaucoma_fundus,
    make_normal_fundus,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS_DIR = REPO_ROOT / "evals" / "artifacts"
JSON_OUTPUT_PATH = ARTIFACTS_DIR / "synthetic_validation_summary.json"
MARKDOWN_OUTPUT_PATH = ARTIFACTS_DIR / "synthetic_validation_summary.md"

CASE_BUILDERS: dict[DiseaseLabel, Callable[[], Image.Image]] = {
    DiseaseLabel.NORMAL: make_normal_fundus,
    DiseaseLabel.DIABETIC_RETINOPATHY: make_diabetic_retinopathy_fundus,
    DiseaseLabel.GLAUCOMA: make_glaucoma_fundus,
    DiseaseLabel.AMD: make_amd_fundus,
    DiseaseLabel.CATARACTS: make_cataracts_fundus,
}


def _dim_image(image: Image.Image, factor: float) -> Image.Image:
    arr = np.array(image.convert("RGB"), dtype=np.float32)
    arr = np.clip(arr * factor, 0, 255).astype(np.uint8)
    return Image.fromarray(arr, mode="RGB")


def _haze_image(image: Image.Image, offset: int) -> Image.Image:
    arr = np.array(image.convert("RGB"), dtype=np.int16)
    arr = np.clip(arr + offset, 0, 255).astype(np.uint8)
    return Image.fromarray(arr, mode="RGB")


def _case_variants(builder: Callable[[], Image.Image]) -> list[Image.Image]:
    base = builder()
    return [
        base,
        _dim_image(base, 0.92),
        _haze_image(base, 8),
    ]


def build_validation_artifact() -> dict:
    """Build the bundled synthetic engineering-validation summary."""
    classifier = RetinalClassifier(demo_mode=True, generate_attention_maps=True)
    preprocessor = RetinalPreprocessor()

    labels = [label.value for label in DiseaseLabel]
    confusion_matrix = {expected: dict.fromkeys(labels, 0) for expected in labels}
    per_class: list[dict] = []
    total_cases = 0
    correct_predictions = 0
    low_quality_cases = 0

    for label, builder in CASE_BUILDERS.items():
        class_total = 0
        class_correct = 0
        confidences: list[float] = []

        for image in _case_variants(builder):
            prep = preprocessor.process(image)
            result = classifier.classify(prep.processed_image)

            total_cases += 1
            class_total += 1
            confidences.append(result.confidence)
            confusion_matrix[label.value][result.predicted_label.value] += 1

            if prep.quality_score < 0.55 or prep.quality_flags:
                low_quality_cases += 1
            if result.predicted_label == label:
                correct_predictions += 1
                class_correct += 1

        per_class.append(
            {
                "label": label.value,
                "display_name": DISEASE_DISPLAY_NAMES[label],
                "cases": class_total,
                "correct": class_correct,
                "accuracy": round(class_correct / class_total, 4),
                "avg_confidence": round(sum(confidences) / len(confidences), 4),
            }
        )

    return {
        "artifact_version": "2026-03-21-medical-ai-ops",
        "evaluation_tier": "engineering_synthetic",
        "status": "portfolio_validation_only",
        "clinical_validation": "not_performed",
        "model": classifier.get_model_architecture_summary(),
        "dataset": {
            "name": "synthetic_retinal_demo_suite",
            "total_cases": total_cases,
            "variants_per_class": 3,
            "description": (
                "Programmatically generated retinal demo images used for offline "
                "engineering validation of the demo_heuristic runtime."
            ),
        },
        "summary": {
            "correct_predictions": correct_predictions,
            "total_cases": total_cases,
            "accuracy": round(correct_predictions / total_cases, 4),
            "low_quality_cases": low_quality_cases,
            "low_quality_rate": round(low_quality_cases / total_cases, 4),
        },
        "per_class": per_class,
        "confusion_matrix": confusion_matrix,
        "limitations": [
            "Uses synthetic images only; results are not representative of clinical performance.",
            "Current runtime default is demo_heuristic rather than a trained, locked clinical model.",
            "No sensitivity, specificity, AUROC, external validation, or subgroup analysis claims are made here.",
        ],
        "recommended_next_steps": [
            "Evaluate trained weights on a representative held-out retinal dataset.",
            "Add dataset lineage, threshold studies, and subgroup checks before any real-world deployment discussion.",
            "Keep engineering validation clearly separated from regulatory or clinical validation language.",
        ],
    }


def _to_markdown(payload: dict) -> str:
    summary = payload["summary"]
    lines = [
        "# Synthetic validation summary",
        "",
        "- **Tier:** engineering_synthetic",
        "- **Clinical validation:** not performed",
        f"- **Accuracy (synthetic suite):** {summary['accuracy']:.2%}",
        f"- **Cases:** {summary['correct_predictions']} / {summary['total_cases']}",
        f"- **Low-quality cases observed:** {summary['low_quality_cases']}",
        "",
        "## Limitations",
        "",
    ]
    lines.extend([f"- {item}" for item in payload["limitations"]])
    lines.extend(
        [
            "",
            "## Recommended next steps",
            "",
        ]
    )
    lines.extend([f"- {item}" for item in payload["recommended_next_steps"]])
    return "\n".join(lines) + "\n"


def main() -> None:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    payload = build_validation_artifact()
    JSON_OUTPUT_PATH.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    MARKDOWN_OUTPUT_PATH.write_text(_to_markdown(payload), encoding="utf-8")
    print(f"Wrote {JSON_OUTPUT_PATH.relative_to(REPO_ROOT)}")
    print(f"Wrote {MARKDOWN_OUTPUT_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
