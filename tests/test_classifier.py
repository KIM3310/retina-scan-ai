"""Tests for the retinal disease classifier.

Verifies that the heuristic classifier correctly identifies each synthetic
image type and produces well-formed ClassificationResult objects.
"""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from app.models.classifier import (
    DISEASE_DISPLAY_NAMES,
    ICD10_CODES,
    ClassificationResult,
    DiseaseLabel,
    RetinalClassifier,
)


@pytest.fixture
def classifier() -> RetinalClassifier:
    return RetinalClassifier(demo_mode=True)


# ── DiseaseLabel enum ─────────────────────────────────────────────────────────

class TestDiseaseLabel:
    def test_all_labels_present(self):
        labels = {lbl.value for lbl in DiseaseLabel}
        assert "normal" in labels
        assert "diabetic_retinopathy" in labels
        assert "glaucoma" in labels
        assert "amd" in labels
        assert "cataracts" in labels

    def test_label_count(self):
        assert len(DiseaseLabel) == 5

    def test_display_names_complete(self):
        for lbl in DiseaseLabel:
            assert lbl in DISEASE_DISPLAY_NAMES
            assert len(DISEASE_DISPLAY_NAMES[lbl]) > 0

    def test_icd10_codes_complete(self):
        for lbl in DiseaseLabel:
            assert lbl in ICD10_CODES
            assert len(ICD10_CODES[lbl]) > 0


# ── ClassificationResult dataclass ───────────────────────────────────────────

class TestClassificationResult:
    def test_post_init_sets_display_name(self):
        result = ClassificationResult(
            predicted_label=DiseaseLabel.NORMAL,
            confidence=0.9,
            probabilities={lbl.value: 0.2 for lbl in DiseaseLabel},
        )
        assert result.display_name == "Normal"

    def test_post_init_sets_icd10(self):
        result = ClassificationResult(
            predicted_label=DiseaseLabel.GLAUCOMA,
            confidence=0.8,
            probabilities={lbl.value: 0.2 for lbl in DiseaseLabel},
        )
        assert result.icd10_code == "H40.10X0"

    def test_urgent_review_when_disease_and_high_confidence(self):
        result = ClassificationResult(
            predicted_label=DiseaseLabel.DIABETIC_RETINOPATHY,
            confidence=0.85,
            probabilities={lbl.value: 0.2 for lbl in DiseaseLabel},
        )
        assert result.requires_urgent_review is True

    def test_no_urgent_review_for_normal(self):
        result = ClassificationResult(
            predicted_label=DiseaseLabel.NORMAL,
            confidence=0.99,
            probabilities={lbl.value: 0.2 for lbl in DiseaseLabel},
        )
        assert result.requires_urgent_review is False

    def test_no_urgent_review_low_confidence_disease(self):
        result = ClassificationResult(
            predicted_label=DiseaseLabel.AMD,
            confidence=0.5,
            probabilities={lbl.value: 0.2 for lbl in DiseaseLabel},
        )
        assert result.requires_urgent_review is False

    def test_to_dict_structure(self):
        result = ClassificationResult(
            predicted_label=DiseaseLabel.CATARACTS,
            confidence=0.75,
            probabilities={lbl.value: 0.2 for lbl in DiseaseLabel},
        )
        d = result.to_dict()
        assert "predicted_label" in d
        assert "display_name" in d
        assert "confidence" in d
        assert "probabilities" in d
        assert "icd10_code" in d
        assert "requires_urgent_review" in d

    def test_to_dict_confidence_rounded(self):
        result = ClassificationResult(
            predicted_label=DiseaseLabel.NORMAL,
            confidence=0.123456789,
            probabilities={lbl.value: 0.2 for lbl in DiseaseLabel},
        )
        d = result.to_dict()
        assert d["confidence"] == round(0.123456789, 4)


# ── RetinalClassifier initialization ─────────────────────────────────────────

class TestRetinalClassifierInit:
    def test_demo_mode_default(self):
        c = RetinalClassifier(demo_mode=True)
        assert c.demo_mode is True

    def test_no_model_path_falls_back_to_demo(self):
        c = RetinalClassifier(demo_mode=False, model_path=None)
        assert c.demo_mode is True

    def test_num_classes(self):
        c = RetinalClassifier(demo_mode=True)
        assert c.NUM_CLASSES == 5

    def test_labels_list(self):
        c = RetinalClassifier(demo_mode=True)
        assert len(c.LABELS) == 5

    def test_input_size(self):
        c = RetinalClassifier(demo_mode=True)
        assert c.INPUT_SIZE == (224, 224)

    def test_architecture_summary(self):
        c = RetinalClassifier(demo_mode=True)
        summary = c.get_model_architecture_summary()
        assert summary["architecture"] == "ResNet18"
        assert summary["num_classes"] == 5
        assert summary["mode"] == "demo_heuristic"
        assert len(summary["labels"]) == 5


# ── Heuristic classification correctness (CRITICAL tests) ────────────────────

class TestHeuristicClassification:
    """Verify the heuristic correctly classifies each synthetic image type."""

    def test_classify_normal(self, classifier, normal_image):
        result = classifier.classify(normal_image)
        assert result.predicted_label == DiseaseLabel.NORMAL, (
            f"Expected NORMAL, got {result.predicted_label.value} "
            f"(conf={result.confidence:.2f}, probs={result.probabilities})"
        )
        assert result.confidence > 0.3

    def test_classify_diabetic_retinopathy(self, classifier, dr_image):
        result = classifier.classify(dr_image)
        assert result.predicted_label == DiseaseLabel.DIABETIC_RETINOPATHY, (
            f"Expected DR, got {result.predicted_label.value} "
            f"(conf={result.confidence:.2f}, probs={result.probabilities})"
        )
        assert result.confidence > 0.3

    def test_classify_glaucoma(self, classifier, glaucoma_image):
        result = classifier.classify(glaucoma_image)
        assert result.predicted_label == DiseaseLabel.GLAUCOMA, (
            f"Expected GLAUCOMA, got {result.predicted_label.value} "
            f"(conf={result.confidence:.2f}, probs={result.probabilities})"
        )
        assert result.confidence > 0.3

    def test_classify_amd(self, classifier, amd_image):
        result = classifier.classify(amd_image)
        assert result.predicted_label == DiseaseLabel.AMD, (
            f"Expected AMD, got {result.predicted_label.value} "
            f"(conf={result.confidence:.2f}, probs={result.probabilities})"
        )
        assert result.confidence > 0.3

    def test_classify_cataracts(self, classifier, cataracts_image):
        result = classifier.classify(cataracts_image)
        assert result.predicted_label == DiseaseLabel.CATARACTS, (
            f"Expected CATARACTS, got {result.predicted_label.value} "
            f"(conf={result.confidence:.2f}, probs={result.probabilities})"
        )
        assert result.confidence > 0.3

    def test_all_synthetic_images_classified_correctly(self, classifier, all_synthetic_images):
        """Ensure all 5 disease categories are classified correctly."""
        expected = {
            "normal": DiseaseLabel.NORMAL,
            "diabetic_retinopathy": DiseaseLabel.DIABETIC_RETINOPATHY,
            "glaucoma": DiseaseLabel.GLAUCOMA,
            "amd": DiseaseLabel.AMD,
            "cataracts": DiseaseLabel.CATARACTS,
        }
        for name, image in all_synthetic_images.items():
            result = classifier.classify(image)
            assert result.predicted_label == expected[name], (
                f"Image '{name}': expected {expected[name].value}, "
                f"got {result.predicted_label.value} (conf={result.confidence:.2f})"
            )


# ── Result validity ───────────────────────────────────────────────────────────

class TestClassificationResultValidity:
    def test_probabilities_sum_to_one(self, classifier, normal_image):
        result = classifier.classify(normal_image)
        total = sum(result.probabilities.values())
        assert abs(total - 1.0) < 0.01

    def test_probabilities_all_non_negative(self, classifier, dr_image):
        result = classifier.classify(dr_image)
        for v in result.probabilities.values():
            assert v >= 0.0

    def test_confidence_between_0_and_1(self, classifier, glaucoma_image):
        result = classifier.classify(glaucoma_image)
        assert 0.0 <= result.confidence <= 1.0

    def test_probabilities_have_all_labels(self, classifier, amd_image):
        result = classifier.classify(amd_image)
        for lbl in DiseaseLabel:
            assert lbl.value in result.probabilities

    def test_confidence_matches_max_probability(self, classifier, cataracts_image):
        result = classifier.classify(cataracts_image)
        max_prob = max(result.probabilities.values())
        assert abs(result.confidence - max_prob) < 0.001


# ── Batch classification ──────────────────────────────────────────────────────

class TestBatchClassification:
    def test_batch_returns_correct_count(self, classifier, all_synthetic_images):
        images = list(all_synthetic_images.values())
        results = classifier.classify_batch(images)
        assert len(results) == len(images)

    def test_batch_all_valid_results(self, classifier, all_synthetic_images):
        images = list(all_synthetic_images.values())
        results = classifier.classify_batch(images)
        for r in results:
            assert isinstance(r, ClassificationResult)
            assert 0.0 <= r.confidence <= 1.0

    def test_batch_empty_list(self, classifier):
        results = classifier.classify_batch([])
        assert results == []


# ── Edge cases ────────────────────────────────────────────────────────────────

class TestClassifierEdgeCases:
    def test_small_image(self, classifier, small_image):
        result = classifier.classify(small_image)
        assert isinstance(result, ClassificationResult)

    def test_grayscale_image_converted(self, classifier):
        gray = Image.fromarray(np.full((256, 256), 128, dtype=np.uint8), mode="L")
        result = classifier.classify(gray)
        assert isinstance(result, ClassificationResult)

    def test_large_image(self, classifier):
        large = Image.fromarray(
            np.random.randint(100, 200, (1024, 1024, 3), dtype=np.uint8), mode="RGB"
        )
        result = classifier.classify(large)
        assert isinstance(result, ClassificationResult)

    def test_overexposed_image_classified(self, classifier, overexposed_image):
        result = classifier.classify(overexposed_image)
        assert isinstance(result, ClassificationResult)

    def test_underexposed_image_classified(self, classifier, underexposed_image):
        result = classifier.classify(underexposed_image)
        assert isinstance(result, ClassificationResult)
