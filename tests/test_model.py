"""Tests for RetinalClassifier model architecture."""

import torch

from src.model import RetinalClassifier, build_model


class TestRetinalClassifier:
    def test_output_shape(self):
        model = RetinalClassifier(num_classes=5, pretrained=False)
        x = torch.randn(4, 3, 224, 224)
        out = model(x)
        assert out.shape == (4, 5)

    def test_pretrained_weights(self):
        model = RetinalClassifier(num_classes=5, pretrained=True)
        x = torch.randn(1, 3, 224, 224)
        out = model(x)
        assert out.shape == (1, 5)

    def test_freeze_backbone(self):
        model = RetinalClassifier(num_classes=5, pretrained=True, freeze_backbone=True)
        params = model.count_parameters()
        assert params["frozen"] > 0
        assert params["trainable"] < params["total"]

    def test_unfreeze_backbone(self):
        model = RetinalClassifier(num_classes=5, pretrained=True, freeze_backbone=True)
        model.unfreeze_backbone()
        params = model.count_parameters()
        assert params["frozen"] == 0

    def test_different_num_classes(self):
        for n in [2, 3, 5, 10]:
            model = RetinalClassifier(num_classes=n, pretrained=False)
            x = torch.randn(2, 3, 224, 224)
            out = model(x)
            assert out.shape == (2, n)

    def test_feature_extractor(self):
        model = RetinalClassifier(num_classes=5, pretrained=False)
        extractor = model.get_feature_extractor()
        x = torch.randn(1, 3, 224, 224)
        features = extractor(x)
        assert features.shape[0] == 1
        assert features.shape[1] == 512  # ResNet18 feature dim

    def test_build_model_factory(self):
        model = build_model(num_classes=3, pretrained=False)
        assert isinstance(model, RetinalClassifier)
        x = torch.randn(1, 3, 224, 224)
        assert model(x).shape == (1, 3)

    def test_gradient_flow(self):
        model = RetinalClassifier(num_classes=5, pretrained=False)
        x = torch.randn(2, 3, 224, 224)
        out = model(x)
        loss = out.sum()
        loss.backward()
        has_grad = any(p.grad is not None for p in model.parameters() if p.requires_grad)
        assert has_grad
