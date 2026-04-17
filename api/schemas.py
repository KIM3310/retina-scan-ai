"""Pydantic schemas for API request/response models."""

from pydantic import BaseModel


class PredictionResponse(BaseModel):
    predicted_class: int
    predicted_label: str
    confidence: float
    probabilities: dict[str, float]
    filename: str | None = None


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
