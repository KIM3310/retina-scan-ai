"""Regression tests for DICOM SCP host binding defaults."""

from dicom import scp_listener
from dicom.scp_listener import SCPConfig


def test_scp_config_defaults_to_loopback_host():
    config = SCPConfig()

    assert config.host == "127.0.0.1"


def test_main_uses_loopback_host_by_default(monkeypatch):
    captured: dict[str, SCPConfig] = {}

    def fake_run(config: SCPConfig) -> int:
        captured["config"] = config
        return 0

    monkeypatch.delenv("DICOM_HOST", raising=False)
    monkeypatch.setattr(scp_listener, "run", fake_run)

    assert scp_listener.main([]) == 0
    assert captured["config"].host == "127.0.0.1"


def test_main_allows_explicit_all_interfaces_host(monkeypatch):
    captured: dict[str, SCPConfig] = {}

    def fake_run(config: SCPConfig) -> int:
        captured["config"] = config
        return 0

    monkeypatch.setattr(scp_listener, "run", fake_run)

    assert scp_listener.main(["--host", "0.0.0.0"]) == 0
    assert captured["config"].host == "0.0.0.0"


def test_main_reads_host_from_environment(monkeypatch):
    captured: dict[str, SCPConfig] = {}

    def fake_run(config: SCPConfig) -> int:
        captured["config"] = config
        return 0

    monkeypatch.setenv("DICOM_HOST", "192.0.2.10")
    monkeypatch.setattr(scp_listener, "run", fake_run)

    assert scp_listener.main([]) == 0
    assert captured["config"].host == "192.0.2.10"
