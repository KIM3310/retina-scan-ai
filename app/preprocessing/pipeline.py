"""Retinal fundus image preprocessing pipeline.

Implements standard preprocessing steps for fundus photography:
- CLAHE (Contrast Limited Adaptive Histogram Equalization)
- Green channel extraction and enhancement (vessels are most visible in green)
- Optic disc detection and localization heuristic
- Circular field-of-view masking
- Image quality assessment (blur detection, exposure check)
- Standardized resizing and normalization
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# Standard output size for model input
DEFAULT_OUTPUT_SIZE = (224, 224)

# CLAHE parameters
CLAHE_CLIP_LIMIT = 2.0
CLAHE_TILE_GRID_SIZE = (8, 8)

# Blur detection threshold (Laplacian variance below this = blurry)
BLUR_THRESHOLD = 50.0

# Optic disc detection parameters
OD_BRIGHT_PERCENTILE = 98  # percentile for bright region detection


@dataclass
class OpticDiscResult:
    """Result of optic disc localization heuristic."""

    detected: bool
    center_x: int | None = None   # pixel x in output image
    center_y: int | None = None   # pixel y in output image
    radius_estimate: int | None = None  # estimated disc radius in pixels
    confidence: float = 0.0       # 0.0–1.0 detection confidence

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "detected": self.detected,
            "center_x": self.center_x,
            "center_y": self.center_y,
            "radius_estimate": self.radius_estimate,
            "confidence": round(self.confidence, 4),
        }


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
    optic_disc: OpticDiscResult | None = field(default=None)

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        result = {
            "original_size": list(self.original_size),
            "output_size": list(self.output_size),
            "clahe_applied": self.clahe_applied,
            "vessel_enhanced": self.vessel_enhanced,
            "fov_masked": self.fov_masked,
            "quality_score": round(self.quality_score, 4),
            "quality_flags": self.quality_flags,
        }
        if self.optic_disc is not None:
            result["optic_disc"] = self.optic_disc.to_dict()
        return result


class RetinalPreprocessor:
    """Full preprocessing pipeline for retinal fundus images.

    Steps:
    1. Input validation and format normalization
    2. Green channel extraction for vessel enhancement
    3. CLAHE contrast enhancement
    4. Optic disc detection/localization
    5. Circular FOV masking
    6. Resize to model input size
    7. Image quality assessment (blur, exposure, resolution)
    """

    def __init__(
        self,
        output_size: tuple[int, int] = DEFAULT_OUTPUT_SIZE,
        apply_clahe: bool = True,
        apply_vessel_enhancement: bool = True,
        apply_fov_mask: bool = True,
        detect_optic_disc: bool = True,
        clahe_clip_limit: float = CLAHE_CLIP_LIMIT,
        clahe_tile_grid: tuple[int, int] = CLAHE_TILE_GRID_SIZE,
    ) -> None:
        """Initialize the preprocessing pipeline.

        Args:
            output_size: Target (width, height) for model input.
            apply_clahe: Whether to apply CLAHE contrast enhancement.
            apply_vessel_enhancement: Whether to boost green channel for vessels.
            apply_fov_mask: Whether to apply circular FOV masking.
            detect_optic_disc: Whether to run optic disc localization.
            clahe_clip_limit: CLAHE clip limit parameter.
            clahe_tile_grid: CLAHE tile grid size.
        """
        self.output_size = output_size
        self.apply_clahe = apply_clahe
        self.apply_vessel_enhancement = apply_vessel_enhancement
        self.apply_fov_mask = apply_fov_mask
        self.detect_optic_disc = detect_optic_disc
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

        # 1. Initial quality check (exposure, resolution, blur)
        quality_flags.extend(self._check_initial_quality(arr))

        # 2. Green channel vessel enhancement
        if self.apply_vessel_enhancement:
            arr = self._enhance_green_channel(arr)

        # 3. CLAHE contrast enhancement
        if self.apply_clahe:
            arr = self._apply_clahe(arr)

        # 4. Optic disc detection (before FOV mask for better signal)
        optic_disc: OpticDiscResult | None = None
        if self.detect_optic_disc:
            optic_disc = self._detect_optic_disc(arr)

        # 5. Circular FOV mask
        if self.apply_fov_mask:
            arr = self._apply_fov_mask(arr)

        # 6. Resize to output size
        arr_resized = cv2.resize(arr, self.output_size, interpolation=cv2.INTER_LANCZOS4)

        # 7. Quality score
        quality_score = self._compute_quality_score(arr_resized, quality_flags)

        processed = Image.fromarray(arr_resized, mode="RGB")

        logger.debug(
            "Preprocessing complete: original=%s output=%s quality=%.3f flags=%s od_detected=%s",
            original_size,
            self.output_size,
            quality_score,
            quality_flags,
            optic_disc.detected if optic_disc else False,
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
            optic_disc=optic_disc,
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

    def _detect_optic_disc(self, arr: np.ndarray) -> OpticDiscResult:
        """Localize the optic disc using bright-region heuristic.

        The optic disc is the brightest compact region in a fundus image.
        We threshold the top bright percentile, find the largest contiguous
        bright blob, and return its centroid and estimated radius.

        Args:
            arr: RGB uint8 array (H x W x 3).

        Returns:
            OpticDiscResult with detected flag and location estimate.
        """
        gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
        h, w = gray.shape

        # Use green channel for better vessel/disc contrast
        green = arr[:, :, 1]

        # Threshold at high percentile to isolate brightest region
        threshold = float(np.percentile(green, OD_BRIGHT_PERCENTILE))
        if threshold < 150:
            # Image too dark for reliable detection
            return OpticDiscResult(detected=False, confidence=0.0)

        _, bright_mask = cv2.threshold(green, int(threshold * 0.85), 255, cv2.THRESH_BINARY)

        # Morphological closing to fill gaps in disc region
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
        bright_mask = cv2.morphologyEx(bright_mask, cv2.MORPH_CLOSE, kernel)

        # Find contours and select the largest compact bright region
        contours, _ = cv2.findContours(bright_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            return OpticDiscResult(detected=False, confidence=0.0)

        # Pick largest contour by area
        largest = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(largest)

        if area < 50:
            return OpticDiscResult(detected=False, confidence=0.0)

        # Compute centroid and radius estimate
        M = cv2.moments(largest)
        if M["m00"] == 0:
            return OpticDiscResult(detected=False, confidence=0.0)

        cx = int(M["m10"] / M["m00"])
        cy = int(M["m01"] / M["m00"])
        radius_est = int(np.sqrt(area / np.pi))

        # Confidence: disc area as fraction of expected disc area range
        # A normal disc covers ~2–8% of the image area
        image_area = h * w
        disc_fraction = area / image_area
        if 0.01 <= disc_fraction <= 0.15:
            confidence = min(1.0, disc_fraction / 0.05)
        else:
            confidence = max(0.0, 0.5 - abs(disc_fraction - 0.05) * 5)

        logger.debug(
            "Optic disc detected: center=(%d,%d) radius=%d confidence=%.3f",
            cx, cy, radius_est, confidence,
        )

        return OpticDiscResult(
            detected=True,
            center_x=cx,
            center_y=cy,
            radius_estimate=radius_est,
            confidence=float(confidence),
        )

    def _check_initial_quality(self, arr: np.ndarray) -> list[str]:
        """Check for common fundus image quality issues.

        Checks performed:
        - Exposure (underexposed / overexposed)
        - Contrast (low contrast)
        - Resolution (minimum pixel dimensions)
        - Sharpness / blur (Laplacian variance)

        Args:
            arr: RGB uint8 array.

        Returns:
            List of quality flag strings for detected issues.
        """
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

        # Blur detection via Laplacian variance
        gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
        laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        if laplacian_var < BLUR_THRESHOLD:
            flags.append("blurry")

        return flags

    def _compute_quality_score(
        self, arr: np.ndarray, quality_flags: list[str]
    ) -> float:
        """Compute 0–1 quality score from image statistics.

        Args:
            arr: Processed RGB uint8 array at output resolution.
            quality_flags: List of detected quality issues.

        Returns:
            Float in [0.0, 1.0] where 1.0 = highest quality.
        """
        base_score = 1.0

        # Penalize for quality flags
        penalty_map = {
            "underexposed": 0.3,
            "overexposed": 0.3,
            "low_contrast": 0.2,
            "low_resolution": 0.4,
            "blurry": 0.25,
        }
        for flag in quality_flags:
            base_score -= penalty_map.get(flag, 0.1)

        # Reward sharpness (Laplacian variance) — bonus up to 0.1
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
