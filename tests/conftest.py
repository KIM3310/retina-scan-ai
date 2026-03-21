"""Pytest fixtures and synthetic retinal image generators.

Generates synthetic fundus images that simulate the visual characteristics
of each disease category, enabling deterministic testing of the heuristic
classifier without requiring real patient data.

Image generation strategy (must match classifier heuristics in classifier.py):
- Normal:  orange-red uniform background (mean ~130, std ~25, R>G>B, min>30)
- DR:      dark microaneurysm dots on reddish background (very low min brightness)
- Glaucoma: large bright white optic disc center (center_mean>180, center_max>220)
- AMD:     bright yellow-white drusen deposits (high R+G relative to B, rg_ratio>2.8)
- Cataracts: hazy overall appearance (high mean >160, low std <50)
"""

from __future__ import annotations

import io

import numpy as np
import pytest
from PIL import Image

# ── Synthetic image size ──────────────────────────────────────────────────────
IMG_SIZE = (256, 256)
RNG_SEED = 42


def make_rng(seed: int = RNG_SEED) -> np.random.Generator:
    return np.random.default_rng(seed)


# ── Core synthetic image generators ──────────────────────────────────────────

def make_normal_fundus(size: tuple[int, int] = IMG_SIZE) -> Image.Image:
    """Normal fundus: uniform orange-red background with vessel-like lines.

    Heuristic targets:
    - mean_brightness: ~130  (100–160 range)
    - std_brightness: ~20    (< 45)
    - R > G > B
    - min_brightness > 30
    - center_mean < 180
    """
    rng = make_rng(1)
    h, w = size
    arr = np.zeros((h, w, 3), dtype=np.uint8)

    # Orange-red base
    arr[:, :, 0] = np.clip(rng.integers(140, 165, size=(h, w)), 0, 255)  # R
    arr[:, :, 1] = np.clip(rng.integers(80, 105, size=(h, w)), 0, 255)   # G
    arr[:, :, 2] = np.clip(rng.integers(55, 75, size=(h, w)), 0, 255)    # B

    # Add a few thin vessel-like dark lines (but not too dark — keep min > 30)
    for _ in range(6):
        x = rng.integers(20, w - 20)
        arr[10:h-10, x:x+2, :] = np.clip(arr[10:h-10, x:x+2, :] - 25, 35, 255)

    return Image.fromarray(arr, mode="RGB")


def make_diabetic_retinopathy_fundus(size: tuple[int, int] = IMG_SIZE) -> Image.Image:
    """DR fundus: dark microaneurysm spots + hemorrhages on reddish background.

    Heuristic targets:
    - min_brightness < 15 (very dark spots)
    - mean_r > mean_b (reddish)
    - std_brightness > 20
    """
    rng = make_rng(2)
    h, w = size
    arr = np.zeros((h, w, 3), dtype=np.uint8)

    # Reddish background
    arr[:, :, 0] = np.clip(rng.integers(130, 160, size=(h, w)), 0, 255)  # R
    arr[:, :, 1] = np.clip(rng.integers(65, 95, size=(h, w)), 0, 255)    # G
    arr[:, :, 2] = np.clip(rng.integers(45, 70, size=(h, w)), 0, 255)    # B

    # Dark microaneurysm dots — ensure at least some pixels go to near-black
    for _ in range(35):
        cy = rng.integers(20, h - 20)
        cx = rng.integers(20, w - 20)
        radius = rng.integers(3, 8)
        y_idx, x_idx = np.ogrid[:h, :w]
        mask = (y_idx - cy) ** 2 + (x_idx - cx) ** 2 <= radius ** 2
        arr[mask] = [5, 3, 3]  # near-black spots → min_brightness ≈ 3–5

    # Hemorrhage patches (dark red-brown)
    for _ in range(8):
        cy = rng.integers(30, h - 30)
        cx = rng.integers(30, w - 30)
        rr = rng.integers(8, 18)
        y_idx, x_idx = np.ogrid[:h, :w]
        mask = (y_idx - cy) ** 2 + (x_idx - cx) ** 2 <= rr ** 2
        arr[mask] = [60, 15, 10]

    return Image.fromarray(arr, mode="RGB")


def make_glaucoma_fundus(size: tuple[int, int] = IMG_SIZE) -> Image.Image:
    """Glaucoma fundus: large bright optic disc with high cup-to-disc ratio.

    Heuristic targets:
    - center_mean > 180
    - center_max > 220
    - std_brightness > 30 (contrast between center and periphery)
    """
    rng = make_rng(3)
    h, w = size
    arr = np.zeros((h, w, 3), dtype=np.uint8)

    # Dark-ish background (pinkish-orange retina)
    arr[:, :, 0] = np.clip(rng.integers(100, 130, size=(h, w)), 0, 255)
    arr[:, :, 1] = np.clip(rng.integers(55, 80, size=(h, w)), 0, 255)
    arr[:, :, 2] = np.clip(rng.integers(40, 65, size=(h, w)), 0, 255)

    # Large, very bright optic disc at center — covers ~30% of image
    cy, cx = h // 2, w // 2
    disc_radius = int(min(h, w) * 0.32)
    y_idx, x_idx = np.ogrid[:h, :w]
    disc_mask = (y_idx - cy) ** 2 + (x_idx - cx) ** 2 <= disc_radius ** 2
    arr[disc_mask] = [245, 245, 230]  # very bright white-yellow

    # Cup within disc (even brighter center)
    cup_radius = int(disc_radius * 0.85)
    cup_mask = (y_idx - cy) ** 2 + (x_idx - cx) ** 2 <= cup_radius ** 2
    arr[cup_mask] = [252, 252, 248]   # near-white

    return Image.fromarray(arr, mode="RGB")


def make_amd_fundus(size: tuple[int, int] = IMG_SIZE) -> Image.Image:
    """AMD fundus: bright yellow drusen deposits in macular region.

    Heuristic targets:
    - rg_ratio = (mean_R + mean_G) / mean_B > 2.8
    - mean_brightness > 130
    - std_brightness > 25
    """
    rng = make_rng(4)
    h, w = size
    arr = np.zeros((h, w, 3), dtype=np.uint8)

    # Moderate orange background
    arr[:, :, 0] = np.clip(rng.integers(120, 145, size=(h, w)), 0, 255)  # R
    arr[:, :, 1] = np.clip(rng.integers(100, 125, size=(h, w)), 0, 255)  # G
    arr[:, :, 2] = np.clip(rng.integers(30, 50, size=(h, w)), 0, 255)    # B (kept low)

    # Dense drusen deposits — bright yellow (high R, high G, low B)
    cy, cx = h // 2, w // 2
    for _i in range(60):
        dy = rng.integers(-h // 3, h // 3)
        dx = rng.integers(-w // 3, w // 3)
        cy2, cx2 = cy + dy, cx + dx
        r = rng.integers(6, 18)
        y_idx, x_idx = np.ogrid[:h, :w]
        mask = (y_idx - cy2) ** 2 + (x_idx - cx2) ** 2 <= r ** 2
        arr[mask] = [240, 230, 40]   # bright yellow (R≈240, G≈230, B≈40 → high rg_ratio)

    return Image.fromarray(arr, mode="RGB")


def make_cataracts_fundus(size: tuple[int, int] = IMG_SIZE) -> Image.Image:
    """Cataracts fundus: overall hazy/washed-out appearance.

    Heuristic targets:
    - mean_brightness > 160
    - std_brightness < 50
    """
    rng = make_rng(5)
    h, w = size

    # High uniform brightness, low contrast — simulate lens haze
    base_r = rng.integers(175, 200, size=(h, w)).astype(np.float32)
    base_g = rng.integers(155, 180, size=(h, w)).astype(np.float32)
    base_b = rng.integers(145, 165, size=(h, w)).astype(np.float32)

    # Very slight variation (low std)
    noise = rng.normal(0, 8, size=(h, w)).astype(np.float32)
    arr = np.stack([
        np.clip(base_r + noise, 150, 215),
        np.clip(base_g + noise, 135, 195),
        np.clip(base_b + noise, 125, 180),
    ], axis=2).astype(np.uint8)

    return Image.fromarray(arr, mode="RGB")


# ── Pytest fixtures ───────────────────────────────────────────────────────────

@pytest.fixture
def normal_image() -> Image.Image:
    return make_normal_fundus()


@pytest.fixture
def dr_image() -> Image.Image:
    return make_diabetic_retinopathy_fundus()


@pytest.fixture
def glaucoma_image() -> Image.Image:
    return make_glaucoma_fundus()


@pytest.fixture
def amd_image() -> Image.Image:
    return make_amd_fundus()


@pytest.fixture
def cataracts_image() -> Image.Image:
    return make_cataracts_fundus()


@pytest.fixture
def all_synthetic_images() -> dict[str, Image.Image]:
    return {
        "normal": make_normal_fundus(),
        "diabetic_retinopathy": make_diabetic_retinopathy_fundus(),
        "glaucoma": make_glaucoma_fundus(),
        "amd": make_amd_fundus(),
        "cataracts": make_cataracts_fundus(),
    }


@pytest.fixture
def image_bytes_jpeg(normal_image: Image.Image) -> bytes:
    buf = io.BytesIO()
    normal_image.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture
def image_bytes_png(dr_image: Image.Image) -> bytes:
    buf = io.BytesIO()
    dr_image.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def small_image() -> Image.Image:
    """50x50 tiny image for edge case testing."""
    arr = np.full((50, 50, 3), 128, dtype=np.uint8)
    return Image.fromarray(arr, mode="RGB")


@pytest.fixture
def overexposed_image() -> Image.Image:
    """Severely overexposed (near-white) fundus image."""
    arr = np.full((256, 256, 3), 250, dtype=np.uint8)
    return Image.fromarray(arr, mode="RGB")


@pytest.fixture
def underexposed_image() -> Image.Image:
    """Severely underexposed (near-black) fundus image."""
    arr = np.full((256, 256, 3), 10, dtype=np.uint8)
    return Image.fromarray(arr, mode="RGB")
