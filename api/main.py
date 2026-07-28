"""FastAPI inference server for retinal disease classification."""

import asyncio
import io
import os
import shutil
import tempfile
import threading
from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import TypeVar

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from PIL import Image, UnidentifiedImageError
from starlette.background import BackgroundTask
from starlette.types import ASGIApp, Receive, Scope, Send

from src.config import CLASS_LABELS
from src.gradcam import visualize_gradcam
from src.inference import RetinalPredictor

T = TypeVar("T")


class UploadBodyLimitMiddleware:
    """Reject oversized inference uploads before multipart parsing."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or scope.get("method") != "POST"
            or scope.get("path") not in {"/predict", "/gradcam"}
        ):
            await self.app(scope, receive, send)
            return

        max_body_bytes = MAX_UPLOAD_BYTES + MULTIPART_OVERHEAD_BYTES
        headers = dict(scope.get("headers", []))
        content_length = headers.get(b"content-length")
        if content_length is not None:
            try:
                if int(content_length) > max_body_bytes:
                    await self._reject(scope, receive, send)
                    return
            except ValueError:
                pass

        received_bytes = 0

        async def limited_receive():
            nonlocal received_bytes
            message = await receive()
            if message["type"] == "http.request":
                received_bytes += len(message.get("body", b""))
                if received_bytes > max_body_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail="Request body exceeds the image upload limit",
                    )
            return message

        await self.app(scope, limited_receive, send)

    @staticmethod
    async def _reject(scope: Scope, receive: Receive, send: Send) -> None:
        response = JSONResponse(
            status_code=413,
            content={"detail": "Request body exceeds the image upload limit"},
        )
        await response(scope, receive, send)


app = FastAPI(
    title="Retina Scan AI",
    description="Retinal disease classification API using ResNet18 transfer learning",
    version="0.1.0",
)

CHECKPOINT_PATH = Path("checkpoints/best_model.pth")
MAX_UPLOAD_BYTES = int(os.getenv("RETINA_MAX_UPLOAD_BYTES", str(16 * 1024 * 1024)))
MULTIPART_OVERHEAD_BYTES = 64 * 1024
MAX_IMAGE_PIXELS = int(os.getenv("RETINA_MAX_IMAGE_PIXELS", "50000000"))
MAX_CONCURRENT_INFERENCES = int(os.getenv("RETINA_MAX_CONCURRENT_INFERENCES", "1"))

if min(MAX_UPLOAD_BYTES, MAX_IMAGE_PIXELS, MAX_CONCURRENT_INFERENCES) < 1:
    raise RuntimeError("Retina API resource limits must be positive integers")

predictor: RetinalPredictor | None = None
_predictor_lock = threading.Lock()
_inference_slots = threading.BoundedSemaphore(MAX_CONCURRENT_INFERENCES)
app.add_middleware(UploadBodyLimitMiddleware)


def get_predictor() -> RetinalPredictor:
    global predictor
    if predictor is not None:
        return predictor

    with _predictor_lock:
        if predictor is None:
            if not CHECKPOINT_PATH.exists():
                raise HTTPException(
                    status_code=503, detail="Model checkpoint not found. Train the model first."
                )
            predictor = RetinalPredictor(CHECKPOINT_PATH)

    return predictor


async def _read_upload(file: UploadFile) -> bytes:
    try:
        if file.size is not None and file.size > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"Image exceeds the {MAX_UPLOAD_BYTES}-byte upload limit",
            )
        contents = await file.read(MAX_UPLOAD_BYTES + 1)
    finally:
        await file.close()

    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Image exceeds the {MAX_UPLOAD_BYTES}-byte upload limit",
        )
    if not contents:
        raise HTTPException(status_code=400, detail="Image file is empty")
    return contents


def _validate_image(contents: bytes) -> None:
    try:
        with Image.open(io.BytesIO(contents)) as uploaded:
            if uploaded.width * uploaded.height > MAX_IMAGE_PIXELS:
                raise HTTPException(
                    status_code=413,
                    detail=f"Image exceeds the {MAX_IMAGE_PIXELS}-pixel limit",
                )
            uploaded.verify()
    except HTTPException:
        raise
    except Image.DecompressionBombError as exc:
        raise HTTPException(
            status_code=413,
            detail=f"Image exceeds the {MAX_IMAGE_PIXELS}-pixel limit",
        ) from exc
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="File is not a valid image") from exc


def _decode_image(contents: bytes) -> Image.Image:
    _validate_image(contents)
    try:
        with Image.open(io.BytesIO(contents)) as uploaded:
            return uploaded.convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="File is not a valid image") from exc


def _run_with_inference_slot(operation: Callable[[], T]) -> T:
    with _inference_slots:
        return operation()


async def _run_inference(operation: Callable[[], T]) -> T:
    return await asyncio.to_thread(_run_with_inference_slot, operation)


def _predict_image(image: Image.Image) -> dict:
    return get_predictor().predict(image)


def _remove_temp_dir(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)


@app.get("/health")
def health() -> dict:
    return {"status": "healthy", "model_loaded": predictor is not None}


@app.get("/classes")
def get_classes() -> dict:
    return {"classes": CLASS_LABELS}


@app.post("/predict")
async def predict(file: UploadFile = File(...)) -> dict:  # noqa: B008 - FastAPI dependency marker
    """Classify a retinal fundus image.

    Upload a retinal image and receive disease classification
    with confidence scores for all classes.
    """
    if not file.content_type or not file.content_type.startswith("image/"):
        await file.close()
        raise HTTPException(status_code=400, detail="File must be an image")

    contents = await _read_upload(file)
    image = await asyncio.to_thread(_decode_image, contents)

    try:
        result = await _run_inference(partial(_predict_image, image))
    finally:
        image.close()
    result["filename"] = file.filename

    return result


@app.post("/gradcam")
async def gradcam(file: UploadFile = File(...)) -> FileResponse:  # noqa: B008 - FastAPI dependency marker
    """Generate Grad-CAM heatmap for model interpretability.

    Upload a retinal image and receive a visualization showing
    which regions the model focuses on for its prediction.
    """
    if not file.content_type or not file.content_type.startswith("image/"):
        await file.close()
        raise HTTPException(status_code=400, detail="File must be an image")

    contents = await _read_upload(file)
    await asyncio.to_thread(_validate_image, contents)

    temp_dir = Path(tempfile.mkdtemp(prefix="retina-gradcam-"))
    input_path = temp_dir / "input.img"
    output_path = temp_dir / "gradcam.png"

    try:
        await asyncio.to_thread(input_path.write_bytes, contents)
        await _run_inference(partial(visualize_gradcam, input_path, CHECKPOINT_PATH, output_path))
        if not output_path.is_file():
            raise RuntimeError("Grad-CAM generation did not produce an output file")
        return FileResponse(
            output_path,
            media_type="image/png",
            filename="gradcam.png",
            background=BackgroundTask(_remove_temp_dir, temp_dir),
        )
    except Exception:
        await asyncio.to_thread(_remove_temp_dir, temp_dir)
        raise
