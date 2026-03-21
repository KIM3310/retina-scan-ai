"""Retinal fundus image preprocessing pipeline.

Implements standard preprocessing steps for fundus photography:
- CLAHE (Contrast Limited Adaptive Histogram Equalization)
- Green channel enhancement (vessels are most visible in green)
- Circular field-of-view masking
- Standardized resizing and normalization
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# Standard output size for model input
DEFAULT_OUTPUT_SIZE = (224, 224)

# CLAHE parameters
CLAHE_CLIP_LIMIT = 2.0
CLAHE_TILE_GRID_SIZE = (8, 8)


@dataclass
class PreprocessingResult:
    """Result of the retinal image preprocessing pipeline."""

    processed_image: Image.Image
    original_size: tuple[int, int]
    output_size: tuple[int, int]
    clahe_applied: bool
    vessel_enhanced: bool
    fov_masked: bool
    quality_score: float       # 0.0–1.0 image quality estimate
    quality_flags: list[str]   # Any quality issues detected

    def to_dict(self) -> dict:
        return {
            "original_size": list(self.original_size),
            "output_size": list(self.output_size),
            "clahe_applied": self.clahe_applied,
            "vessel_enhanced": self.vessel_enhanced,
            "fov_masked": self.fov_masked,
            "quality_score": round(self.quality_score, 4),
            "quality_flags": self.quality_flags,
        }


class RetinalPreprocessor:
    """Full preprocessing pipeline for retinal fundus images.

    Steps:
    1. Input validation and format normalization
    2. Green channel extraction for vessel enhancement
    3. CLAHE contrast enhancement
    4. Circular FOV masking
    5. Resize to model input size
    6. Image quality assessment
    """

    def __init__(
        self,
        output_size: tuple[int, int] = DEFAULT_OUTPUT_SIZE,
        apply_clahe: bool = True,
        apply_vessel_enhancement: bool = True,
        apply_fov_mask: bool = True,
        clahe_clip_limit: float = CLAHE_CLIP_LIMIT,
        clahe_tile_grid: tuple[int, int] = CLAHE_TILE_GRID_SIZE,
    ) -> None:
        self.output_size = output_size
        self.apply_clahe = apply_clahe
        self.apply_vessel_enhancement = apply_vessel_enhancement
        self.apply_fov_mask = apply_fov_mask
        self.clahe = cv2.createCLAHE(
            clipLimit=clahe_clip_limit,
            tileGridSize=clahe_tile_grid,
        )

    def process(self, image: Image.Image) -> PreprocessingResult:
        """Run the full preprocessing pipeline on a fundus image.

        Args:
            image: PIL Image of the retinal fundus.

        Returns:
            PreprocessingResult with processed image and pipeline metadata.
        """
        original_size = (image.width, image.height)
        quality_flags: list[str] = []

        # Ensure RGB
        img_rgb = image.convert("RGB")
        arr = np.array(img_rgb, dtype=np.uint8)

        # 1. Initial quality check
        quality_flags.extend(self._check_initial_quality(arr))

        # 2. Green channel vessel enhancement
        if self.apply_vessel_enhancement:
            arr = self._enhance_green_channel(arr)

        # 3. CLAHE contrast enhancement
        if self.apply_clahe:
            arr = self._apply_clahe(arr)

        # 4. Circular FOV mask
        if self.apply_fov_mask:
            arr = self._apply_fov_mask(arr)

        # 5. Resize to output size
        arr_resized = cv2.resize(arr, self.output_size, interpolation=cv2.INTER_LANCZOS4)

        # 6. Quality score
        quality_score = self._compute_quality_score(arr_resized, quality_flags)

        processed = Image.fromarray(arr_resized, mode="RGB")

        logger.debug(
            "Preprocessing complete: original=%s output=%s quality=%.3f flags=%s",
            original_size,
            self.output_size,
            quality_score,
            quality_flags,
        )

        return PreprocessingResult(
            processed_image=processed,
            original_size=original_size,
            output_size=self.output_size,
            clahe_applied=self.apply_clahe,
            vessel_enhanced=self.apply_vessel_enhancement,
            fov_masked=self.apply_fov_mask,
            quality_score=quality_score,
            quality_flags=quality_flags,
        )

    def _enhance_green_channel(self, arr: np.ndarray) -> np.ndarray:
        """Enhance retinal vessels via green channel weighting.

        The green channel provides the highest contrast for retinal vessels.
        We blend original image with green-channel-boosted version.
        """
        green = arr[:, :, 1].astype(np.float32)

        # Sharpen green channel with unsharp mask
        blurred = cv2.GaussianBlur(green, (0, 0), sigmaX=2.0)
        sharpened = cv2.addWeighted(green, 1.5, blurred, -0.5, 0)
        sharpened = np.clip(sharpened, 0, 255).astype(np.uint8)

        result = arr.copy()
        result[:, :, 1] = sharpened
        return result

    def _apply_clahe(self, arr: np.ndarray) -> np.ndarray:
        """Apply CLAHE to each channel in LAB color space."""
        lab = cv2.cvtColor(arr, cv2.COLOR_RGB2LAB)
        l_chan, a_chan, b_chan = cv2.split(lab)
        l_enhanced = self.clahe.apply(l_chan)
        lab_enhanced = cv2.merge([l_enhanced, a_chan, b_chan])
        return cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2RGB)

    def _apply_fov_mask(self, arr: np.ndarray) -> np.ndarray:
        """Apply circular field-of-view mask to remove non-retinal border."""
        h, w = arr.shape[:2]
        mask = np.zeros((h, w), dtype=np.uint8)
        center = (w // 2, h // 2)
        radius = int(min(w, h) * 0.47)
        cv2.circle(mask, center, radius, 255, thickness=-1)

        result = arr.copy()
        for c in range(3):
            result[:, :, c] = cv2.bitwise_and(arr[:, :, c], arr[:, :, c], mask=mask)
        return result

    def _check_initial_quality(self, arr: np.ndarray) -> list[str]:
        """Check for common fundus image quality issues."""
        flags: list[str] = []
        brightness = arr.mean()

        if brightness < 30:
            flags.append("underexposed")
        elif brightness > 220:
            flags.append("overexposed")

        if arr.std() < 10:
            flags.append("low_contrast")

        # Check for sufficient resolution
        h, w = arr.shape[:2]
        if h < 100 or w < 100:
            flags.append("low_resolution")

        return flags

    def _compute_quality_score(
        self, arr: np.ndarray, quality_flags: list[str]
    ) -> float:
        """Compute 0–1 quality score from image statistics."""
        base_score = 1.0

        # Penalize for quality flags
        penalty_map = {
            "underexposed": 0.3,
            "overexposed": 0.3,
            "low_contrast": 0.2,
            "low_resolution": 0.4,
        }
        for flag in quality_flags:
            base_score -= penalty_map.get(flag, 0.1)

        # Reward sharpness (Laplacian variance)
        gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
        laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        sharpness_bonus = min(laplacian_var / 500.0, 0.1)
        base_score += sharpness_bonus

        return float(np.clip(base_score, 0.0, 1.0))

    @staticmethod
    def extract_image_features(arr: np.ndarray) -> dict:
        """Extract quantitative image features for severity grading.

        Returns a dict of features usable by SeverityGrader.
        """
        gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
        h, w = gray.shape
        cy, cx = h // 2, w // 2
        margin = min(h, w) // 5

        center_region = gray[cy - margin:cy + margin, cx - margin:cx + margin]
        center_mean = float(center_region.mean())
        center_max = float(center_region.max())

        # Cup-to-disc ratio estimate from central bright region
        _, bright_mask = cv2.threshold(center_region, 200, 255, cv2.THRESH_BINARY)
        bright_pixels = int(bright_mask.sum() / 255)
        total_center = center_region.size
        cdr_estimate = float(bright_pixels / max(total_center, 1))

        # Dark spot count (microaneurysms proxy)
        _, dark_mask = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY_INV)
        dark_pixel_ratio = float(dark_mask.sum() / 255) / max(h * w, 1)

        # Overall brightness stats
        brightness = float(gray.mean())
        contrast = float(gray.std())

        return {
            "center_mean": center_mean,
            "center_max": center_max,
            "cup_disc_ratio": cdr_estimate,
            "dark_spot_ratio": dark_pixel_ratio,
            "mean_brightness": brightness,
            "contrast": contrast,
            "neovascularization_detected": False,  # requires deep model
            "extensive_hemorrhage": dark_pixel_ratio > 0.05,
            "geographic_atrophy": False,           # requires deep model
            "subretinal_fluid": False,             # requires deep model
            "lens_opacity_score": min(brightness / 255.0, 1.0) if brightness > 180 else 0.0,
        }

    def process_bytes(self, image_bytes: bytes) -> PreprocessingResult:
        """Convenience method: process image from raw bytes.

        Args:
            image_bytes: Raw image bytes (JPEG, PNG, etc.)

        Returns:
            PreprocessingResult
        """
        import io

        image = Image.open(io.BytesIO(image_bytes))
        return self.process(image)
