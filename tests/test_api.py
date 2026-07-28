"""Tests for FastAPI inference endpoints."""

import io
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

import api.main as api_main
from api.main import app

client = TestClient(app)


def image_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), color="red").save(buffer, format="PNG")
    return buffer.getvalue()


class TestHealthEndpoint:
    def test_health_check(self):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


class TestClassesEndpoint:
    def test_get_classes(self):
        response = client.get("/classes")
        assert response.status_code == 200
        data = response.json()
        assert "classes" in data
        assert len(data["classes"]) == 5


class TestPredictEndpoint:
    def test_predict_no_file(self):
        response = client.post("/predict")
        assert response.status_code == 422

    def test_predict_invalid_file_type(self):
        response = client.post(
            "/predict",
            files={"file": ("test.txt", b"not an image", "text/plain")},
        )
        assert response.status_code == 400

    def test_predict_rejects_invalid_image_payload(self):
        response = client.post(
            "/predict",
            files={"file": ("fake.png", b"not an image", "image/png")},
        )
        assert response.status_code == 400
        assert response.json()["detail"] == "File is not a valid image"

    def test_predict_rejects_upload_over_limit(self, monkeypatch):
        monkeypatch.setattr(api_main, "MAX_UPLOAD_BYTES", 4)

        response = client.post(
            "/predict",
            files={"file": ("large.png", b"12345", "image/png")},
        )

        assert response.status_code == 413

    def test_upload_body_is_rejected_before_multipart_parsing(self, monkeypatch):
        monkeypatch.setattr(api_main, "MAX_UPLOAD_BYTES", 4)
        monkeypatch.setattr(api_main, "MULTIPART_OVERHEAD_BYTES", 0)

        response = client.post(
            "/predict",
            files={"file": ("small.png", b"x", "image/png")},
        )

        assert response.status_code == 413
        assert response.json()["detail"] == "Request body exceeds the image upload limit"

    def test_streamed_upload_body_is_limited_without_content_length(self, monkeypatch):
        monkeypatch.setattr(api_main, "MAX_UPLOAD_BYTES", 4)
        monkeypatch.setattr(api_main, "MULTIPART_OVERHEAD_BYTES", 0)
        boundary = "retina-boundary"
        body = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="retina.png"\r\n'
            "Content-Type: image/png\r\n\r\n"
        ).encode()
        body += b"12345"
        body += f"\r\n--{boundary}--\r\n".encode()

        response = client.post(
            "/predict",
            content=iter([body]),
            headers={"content-type": f"multipart/form-data; boundary={boundary}"},
        )

        assert response.status_code == 413
        assert response.json()["detail"] == "Request body exceeds the image upload limit"

    def test_predict_rejects_excessive_decoded_dimensions(self, monkeypatch):
        monkeypatch.setattr(api_main, "MAX_IMAGE_PIXELS", 4)

        response = client.post(
            "/predict",
            files={"file": ("large-dimensions.png", image_bytes(), "image/png")},
        )

        assert response.status_code == 413

    def test_inference_concurrency_is_bounded(self, monkeypatch):
        class SlowPredictor:
            def __init__(self):
                self.active = 0
                self.max_active = 0
                self.lock = threading.Lock()

            def predict(self, _image):
                with self.lock:
                    self.active += 1
                    self.max_active = max(self.max_active, self.active)
                time.sleep(0.05)
                with self.lock:
                    self.active -= 1
                return {
                    "predicted_class": 0,
                    "predicted_label": "Normal",
                    "confidence": 1.0,
                    "probabilities": {"Normal": 1.0},
                }

        fake_predictor = SlowPredictor()
        monkeypatch.setattr(api_main, "get_predictor", lambda: fake_predictor)
        monkeypatch.setattr(api_main, "_inference_slots", threading.BoundedSemaphore(1))

        def request_prediction():
            with TestClient(app) as request_client:
                return request_client.post(
                    "/predict",
                    files={"file": ("retina.png", image_bytes(), "image/png")},
                )

        with ThreadPoolExecutor(max_workers=2) as executor:
            responses = list(executor.map(lambda _index: request_prediction(), range(2)))

        assert [response.status_code for response in responses] == [200, 200]
        assert fake_predictor.max_active == 1


class TestGradcamEndpoint:
    def test_gradcam_uses_unique_paths_and_cleans_them_after_response(self, monkeypatch):
        paths: list[tuple[Path, Path]] = []

        def fake_visualize(input_path, _checkpoint_path, output_path):
            input_path = Path(input_path)
            output_path = Path(output_path)
            assert input_path.exists()
            output_path.write_bytes(b"gradcam-result")
            paths.append((input_path, output_path))
            return {}

        monkeypatch.setattr(api_main, "visualize_gradcam", fake_visualize)

        responses = [
            client.post(
                "/gradcam",
                files={"file": ("retina.png", image_bytes(), "image/png")},
            )
            for _ in range(2)
        ]

        assert [response.status_code for response in responses] == [200, 200]
        assert [response.content for response in responses] == [b"gradcam-result"] * 2
        assert paths[0][0].parent != paths[1][0].parent
        assert all(not input_path.parent.exists() for input_path, _output_path in paths)

    def test_gradcam_cleans_request_directory_when_generation_fails(self, monkeypatch):
        request_dir: Path | None = None

        def failing_visualize(input_path, _checkpoint_path, _output_path):
            nonlocal request_dir
            request_dir = Path(input_path).parent
            raise RuntimeError("generation failed")

        monkeypatch.setattr(api_main, "visualize_gradcam", failing_visualize)

        with TestClient(app, raise_server_exceptions=False) as request_client:
            response = request_client.post(
                "/gradcam",
                files={"file": ("retina.png", image_bytes(), "image/png")},
            )

        assert response.status_code == 500
        assert request_dir is not None
        assert not request_dir.exists()
