"""FastAPI inference server for retinal disease classification."""

import io
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from PIL import Image

from src.config import CLASS_LABELS
from src.gradcam import visualize_gradcam
from src.inference import RetinalPredictor

app = FastAPI(
    title="Retina Scan AI",
    description="Retinal disease classification API using ResNet18 transfer learning",
    version="0.1.0",
)

CHECKPOINT_PATH = Path("checkpoints/best_model.pth")
predictor: RetinalPredictor | None = None


def get_predictor() -> RetinalPredictor:
    global predictor
    if predictor is None:
        if not CHECKPOINT_PATH.exists():
            raise HTTPException(status_code=503, detail="Model checkpoint not found. Train the model first.")
        predictor = RetinalPredictor(CHECKPOINT_PATH)
    return predictor


@app.get("/health")
def health() -> dict:
    return {"status": "healthy", "model_loaded": predictor is not None}


@app.get("/classes")
def get_classes() -> dict:
    return {"classes": CLASS_LABELS}


@app.post("/predict")
async def predict(file: UploadFile = File(...)) -> dict:
    """Classify a retinal fundus image.

    Upload a retinal image and receive disease classification
    with confidence scores for all classes.
    """
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    contents = await file.read()
    image = Image.open(io.BytesIO(contents)).convert("RGB")

    pred = get_predictor()
    result = pred.predict(image)
    result["filename"] = file.filename

    return result


@app.post("/gradcam")
async def gradcam(file: UploadFile = File(...)) -> FileResponse:
    """Generate Grad-CAM heatmap for model interpretability.

    Upload a retinal image and receive a visualization showing
    which regions the model focuses on for its prediction.
    """
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    contents = await file.read()
    tmp_path = Path("outputs/tmp_upload.png")
    tmp_path.parent.mkdir(parents=True, exist_ok=True)
    with open(tmp_path, "wb") as f:
        f.write(contents)

    output_path = Path("outputs/gradcam_result.png")
    visualize_gradcam(tmp_path, CHECKPOINT_PATH, output_path)
    tmp_path.unlink(missing_ok=True)

    return FileResponse(output_path, media_type="image/png")
