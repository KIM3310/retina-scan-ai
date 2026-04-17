"""Tests for training components."""

import pytest

from src.train import EarlyStopping


class TestEarlyStopping:
    def test_no_stop_improving(self):
        es = EarlyStopping(patience=3)
        losses = [1.0, 0.9, 0.8, 0.7, 0.6]
        for loss in losses:
            assert not es(loss)

    def test_stop_after_patience(self):
        es = EarlyStopping(patience=3)
        es(1.0)  # best
        es(1.1)  # counter 1
        es(1.2)  # counter 2
        assert es(1.3)  # counter 3 -> stop

    def test_reset_on_improvement(self):
        es = EarlyStopping(patience=3)
        es(1.0)
        es(1.1)
        es(1.2)
        es(0.5)  # improvement, counter resets
        assert not es(0.6)  # counter 1
        assert not es(0.7)  # counter 2
        assert es(0.8)  # counter 3 -> stop

    def test_min_delta(self):
        es = EarlyStopping(patience=2, min_delta=0.1)
        es(1.0)  # best
        assert not es(0.95)  # improvement < min_delta, counter 1
        assert es(0.96)  # counter 2 -> stop
