"""Tests for the retinal image preprocessing pipeline."""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from app.preprocessing.pipeline import RetinalPreprocessor


@pytest.fixture
def preprocessor() -> RetinalPreprocessor:
    return RetinalPreprocessor()


@pytest.fixture
def preprocessor_no_clahe() -> RetinalPreprocessor:
    return RetinalPreprocessor(apply_clahe=False)


@pytest.fixture
def preprocessor_minimal() -> RetinalPreprocessor:
    return RetinalPreprocessor(
        apply_clahe=False,
        apply_vessel_enhancement=False,
        apply_fov_mask=False,
    )


@pytest.fixture
def sample_rgb_image() -> Image.Image:
    arr = np.random.randint(50, 200, (256, 256, 3), dtype=np.uint8)
    return Image.fromarray(arr, mode="RGB")


# ── PreprocessingResult dataclass ─────────────────────────────────────────────

class TestPreprocessingResult:
    def test_to_dict_keys(self, preprocessor, sample_rgb_image):
        result = preprocessor.process(sample_rgb_image)
        d = result.to_dict()
        expected_keys = {
            "original_size", "output_size", "clahe_applied",
            "vessel_enhanced", "fov_masked", "quality_score", "quality_flags"
        }
        assert expected_keys.issubset(set(d.keys()))

    def test_output_is_pil_image(self, preprocessor, sample_rgb_image):
        result = preprocessor.process(sample_rgb_image)
        assert isinstance(result.processed_image, Image.Image)

    def test_output_size_correct(self, preprocessor, sample_rgb_image):
        result = preprocessor.process(sample_rgb_image)
        assert result.processed_image.size == (224, 224)

    def test_output_size_custom(self, sample_rgb_image):
        p = RetinalPreprocessor(output_size=(128, 128))
        result = p.process(sample_rgb_image)
        assert result.processed_image.size == (128, 128)

    def test_original_size_recorded(self, preprocessor, sample_rgb_image):
        result = preprocessor.process(sample_rgb_image)
        assert result.original_size == (256, 256)

    def test_quality_score_in_range(self, preprocessor, sample_rgb_image):
        result = preprocessor.process(sample_rgb_image)
        assert 0.0 <= result.quality_score <= 1.0

    def test_quality_flags_is_list(self, preprocessor, sample_rgb_image):
        result = preprocessor.process(sample_rgb_image)
        assert isinstance(result.quality_flags, list)


# ── Pipeline stages ───────────────────────────────────────────────────────────

class TestPipelineStages:
    def test_clahe_applied_flag(self, preprocessor, sample_rgb_image):
        result = preprocessor.process(sample_rgb_image)
        assert result.clahe_applied is True

    def test_clahe_not_applied_flag(self, preprocessor_no_clahe, sample_rgb_image):
        result = preprocessor_no_clahe.process(sample_rgb_image)
        assert result.clahe_applied is False

    def test_vessel_enhancement_flag(self, preprocessor, sample_rgb_image):
        result = preprocessor.process(sample_rgb_image)
        assert result.vessel_enhanced is True

    def test_fov_mask_flag(self, preprocessor, sample_rgb_image):
        result = preprocessor.process(sample_rgb_image)
        assert result.fov_masked is True

    def test_minimal_pipeline_no_flags(self, preprocessor_minimal, sample_rgb_image):
        result = preprocessor_minimal.process(sample_rgb_image)
        assert result.clahe_applied is False
        assert result.vessel_enhanced is False
        assert result.fov_masked is False

    def test_fov_mask_creates_black_corners(self, preprocessor, sample_rgb_image):
        """After FOV masking, corners should be black."""
        result = preprocessor.process(sample_rgb_image)
        arr = np.array(result.processed_image)
        # Top-left corner should be masked (black)
        corner = arr[0:10, 0:10, :]
        assert corner.mean() < 10.0


# ── Quality detection ─────────────────────────────────────────────────────────

class TestQualityDetection:
    def test_underexposed_flagged(self, preprocessor, underexposed_image):
        result = preprocessor.process(underexposed_image)
        assert "underexposed" in result.quality_flags

    def test_overexposed_flagged(self, preprocessor, overexposed_image):
        result = preprocessor.process(overexposed_image)
        assert "overexposed" in result.quality_flags

    def test_normal_image_no_exposure_flags(self, preprocessor, normal_image):
        result = preprocessor.process(normal_image)
        assert "underexposed" not in result.quality_flags
        assert "overexposed" not in result.quality_flags

    def test_low_resolution_flagged(self, preprocessor, small_image):
        result = preprocessor.process(small_image)
        assert "low_resolution" in result.quality_flags

    def test_underexposed_has_lower_quality_score(self, preprocessor, underexposed_image, normal_image):
        under_result = preprocessor.process(underexposed_image)
        normal_result = preprocessor.process(normal_image)
        assert under_result.quality_score < normal_result.quality_score


# ── Image format handling ─────────────────────────────────────────────────────

class TestImageFormatHandling:
    def test_grayscale_converted(self, preprocessor):
        gray = Image.fromarray(np.full((256, 256), 128, dtype=np.uint8), mode="L")
        result = preprocessor.process(gray)
        assert result.processed_image.mode == "RGB"

    def test_rgba_image(self, preprocessor):
        rgba = Image.fromarray(np.full((256, 256, 4), 128, dtype=np.uint8), mode="RGBA")
        result = preprocessor.process(rgba)
        assert isinstance(result.processed_image, Image.Image)

    def test_process_bytes_jpeg(self, preprocessor, image_bytes_jpeg):
        result = preprocessor.process_bytes(image_bytes_jpeg)
        assert isinstance(result.processed_image, Image.Image)
        assert result.output_size == (224, 224)

    def test_process_bytes_png(self, preprocessor, image_bytes_png):
        result = preprocessor.process_bytes(image_bytes_png)
        assert isinstance(result.processed_image, Image.Image)


# ── Feature extraction ────────────────────────────────────────────────────────

class TestFeatureExtraction:
    def test_extract_features_keys(self, sample_rgb_image):
        arr = np.array(sample_rgb_image)
        features = RetinalPreprocessor.extract_image_features(arr)
        expected_keys = {
            "center_mean", "center_max", "cup_disc_ratio",
            "dark_spot_ratio", "mean_brightness", "contrast",
            "neovascularization_detected", "extensive_hemorrhage",
            "geographic_atrophy", "subretinal_fluid", "lens_opacity_score",
        }
        assert expected_keys.issubset(set(features.keys()))

    def test_cup_disc_ratio_in_range(self, glaucoma_image):
        arr = np.array(glaucoma_image.resize((224, 224)))
        features = RetinalPreprocessor.extract_image_features(arr)
        assert 0.0 <= features["cup_disc_ratio"] <= 1.0

    def test_dark_spot_ratio_non_negative(self, dr_image):
        arr = np.array(dr_image.resize((224, 224)))
        features = RetinalPreprocessor.extract_image_features(arr)
        assert features["dark_spot_ratio"] >= 0.0

    def test_glaucoma_has_high_center_mean(self, glaucoma_image):
        arr = np.array(glaucoma_image.resize((224, 224)))
        features = RetinalPreprocessor.extract_image_features(arr)
        assert features["center_mean"] > 150  # bright optic disc

    def test_dr_has_some_dark_spots(self, dr_image):
        arr = np.array(dr_image.resize((224, 224)))
        features = RetinalPreprocessor.extract_image_features(arr)
        assert features["dark_spot_ratio"] > 0.0

    def test_lens_opacity_score_in_range(self, cataracts_image):
        arr = np.array(cataracts_image.resize((224, 224)))
        features = RetinalPreprocessor.extract_image_features(arr)
        assert 0.0 <= features["lens_opacity_score"] <= 1.0
