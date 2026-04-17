"""Download and prepare the ODIR retinal disease dataset.

Dataset: ODIR-5K (Ocular Disease Intelligent Recognition)
Source: https://www.kaggle.com/datasets/andrewmvd/ocular-disease-recognition-odir5k
Classes: Normal, Diabetic Retinopathy, Glaucoma, Cataract, AMD

Usage:
    1. Download ODIR-5K from Kaggle (requires Kaggle account)
    2. Place the zip file in data/ directory
    3. Run: python scripts/download_data.py
"""

import shutil
from pathlib import Path

import pandas as pd
from PIL import Image
from tqdm import tqdm


DATA_DIR = Path("data/retina")
RAW_DIR = Path("data/raw")

CLASS_MAP = {
    "N": "Normal",
    "D": "Diabetic_Retinopathy",
    "G": "Glaucoma",
    "C": "Cataract",
    "A": "AMD",
}


def prepare_dataset(csv_path: str, images_dir: str) -> None:
    """Organize raw ODIR images into class subdirectories.

    Args:
        csv_path: Path to ODIR annotations CSV
        images_dir: Path to directory containing raw fundus images
    """
    df = pd.read_csv(csv_path)
    images_dir = Path(images_dir)

    for class_name in CLASS_MAP.values():
        (DATA_DIR / class_name).mkdir(parents=True, exist_ok=True)

    count = {v: 0 for v in CLASS_MAP.values()}

    for _, row in tqdm(df.iterrows(), total=len(df), desc="Organizing images"):
        labels = str(row.get("labels", row.get("diagnostic_keywords", "")))

        target_class = None
        for key, class_name in CLASS_MAP.items():
            if key in labels.split(",")[0]:
                target_class = class_name
                break

        if target_class is None:
            continue

        for col in ["Left-Fundus", "Right-Fundus", "filename", "image"]:
            if col in row and pd.notna(row[col]):
                src = images_dir / str(row[col])
                if src.exists():
                    dst = DATA_DIR / target_class / src.name
                    if not dst.exists():
                        shutil.copy2(src, dst)
                        count[target_class] += 1

    print("\nDataset prepared:")
    for class_name, n in count.items():
        print(f"  {class_name}: {n} images")
    print(f"  Total: {sum(count.values())} images")


def create_synthetic_dataset(n_per_class: int = 100) -> None:
    """Create a synthetic dataset for development and testing.

    Generates simple colored images for each class to verify
    the training pipeline before using real data.
    """
    colors = {
        "Normal": (120, 180, 120),
        "Diabetic_Retinopathy": (200, 100, 100),
        "Glaucoma": (100, 100, 200),
        "Cataract": (180, 180, 180),
        "AMD": (200, 180, 100),
    }

    for class_name, base_color in colors.items():
        class_dir = DATA_DIR / class_name
        class_dir.mkdir(parents=True, exist_ok=True)

        for i in range(n_per_class):
            import random
            r = max(0, min(255, base_color[0] + random.randint(-30, 30)))
            g = max(0, min(255, base_color[1] + random.randint(-30, 30)))
            b = max(0, min(255, base_color[2] + random.randint(-30, 30)))

            img = Image.new("RGB", (256, 256), (r, g, b))
            img.save(class_dir / f"synthetic_{i:04d}.png")

    print(f"Synthetic dataset created: {n_per_class} images per class, 5 classes")
    print(f"Location: {DATA_DIR}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--synthetic":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 100
        create_synthetic_dataset(n)
    elif len(sys.argv) == 3:
        prepare_dataset(sys.argv[1], sys.argv[2])
    else:
        print("Usage:")
        print("  Real data:      python scripts/download_data.py <csv_path> <images_dir>")
        print("  Synthetic data:  python scripts/download_data.py --synthetic [n_per_class]")
