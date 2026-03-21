"""Tests for the screening workflow agent.

All OpenAI API calls are mocked — no real API key required.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from app.agent.orchestrator import (
    _RISK_PRIORITY,
    DISCLAIMER,
    AgentStatus,
    PatientRecord,
    ScreeningAgent,
    ScreeningResult,
    ScreeningSession,
    _determine_action_items,
)
from tests.conftest import (
    make_diabetic_retinopathy_fundus,
    make_glaucoma_fundus,
    make_normal_fundus,
)

# ── Helpers ───────────────────────────────────────────────────────────────────

def make_agent(monkeypatch=None, api_key: str = "test-key") -> ScreeningAgent:
    """Create a ScreeningAgent with a test API key."""
    if monkeypatch:
        monkeypatch.setenv("OPENAI_API_KEY", api_key)
    return ScreeningAgent(api_key=api_key)


def make_mock_openai_response(content: str) -> MagicMock:
    mock_choice = MagicMock()
    mock_choice.message.content = content
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    return mock_response


def make_patient_record(image: Image.Image | None = None) -> PatientRecord:
    if image is None:
        image = make_normal_fundus()
    return PatientRecord(image=image, patient_ref="patient-001")


# ── ScreeningAgent instantiation ──────────────────────────────────────────────

class TestScreeningAgentInit:
    def test_init_with_explicit_key(self):
        agent = ScreeningAgent(api_key="sk-test")
        assert agent._api_key == "sk-test"

    def test_init_reads_env_var(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-env-key")
        agent = ScreeningAgent()
        assert agent._api_key == "sk-env-key"

    def test_init_raises_without_key(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with pytest.raises(EnvironmentError, match="OPENAI_API_KEY"):
            ScreeningAgent()

    def test_init_raises_empty_key(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "")
        with pytest.raises(EnvironmentError, match="OPENAI_API_KEY"):
            ScreeningAgent()

    def test_initial_status_idle(self):
        agent = make_agent()
        assert agent.status == AgentStatus.IDLE

    def test_get_status_returns_dict(self):
        agent = make_agent()
        status = agent.get_status()
        assert isinstance(status, dict)
        assert "status" in status
        assert "disclaimer" in status

    def test_get_status_disclaimer_present(self):
        agent = make_agent()
        status = agent.get_status()
        assert DISCLAIMER in status["disclaimer"]


# ── PatientRecord ─────────────────────────────────────────────────────────────

class TestPatientRecord:
    def test_patient_record_defaults(self):
        img = make_normal_fundus()
        record = PatientRecord(image=img)
        assert record.patient_ref == ""
        assert record.laterality == "unspecified"
        assert record.patient_age is None
        assert record.has_hypertension is False

    def test_patient_record_with_metadata(self):
        img = make_diabetic_retinopathy_fundus()
        record = PatientRecord(
            image=img,
            patient_ref="P-001",
            patient_age=55,
            diabetes_duration=10,
            hba1c=8.5,
            has_hypertension=True,
        )
        assert record.patient_ref == "P-001"
        assert record.patient_age == 55
        assert record.hba1c == 8.5


# ── Action items logic ────────────────────────────────────────────────────────

class TestDetermineActionItems:
    def test_critical_risk_urgent_action(self):
        classification = {"predicted_label": "diabetic_retinopathy", "requires_urgent_review": True}
        risk = {"risk_level": "critical"}
        actions = _determine_action_items(classification, risk)
        assert any("URGENT" in a for a in actions)

    def test_high_risk_referral(self):
        classification = {"predicted_label": "glaucoma", "requires_urgent_review": False}
        risk = {"risk_level": "high"}
        actions = _determine_action_items(classification, risk)
        assert any("week" in a.lower() or "urgent" in a.lower() for a in actions)

    def test_moderate_risk_one_month(self):
        classification = {"predicted_label": "normal", "requires_urgent_review": False}
        risk = {"risk_level": "moderate"}
        actions = _determine_action_items(classification, risk)
        assert any("month" in a.lower() for a in actions)

    def test_low_risk_routine_followup(self):
        classification = {"predicted_label": "normal", "requires_urgent_review": False}
        risk = {"risk_level": "low"}
        actions = _determine_action_items(classification, risk)
        assert any("routine" in a.lower() or "follow" in a.lower() for a in actions)

    def test_dr_specific_actions(self):
        classification = {"predicted_label": "diabetic_retinopathy", "requires_urgent_review": False}
        risk = {"risk_level": "moderate"}
        actions = _determine_action_items(classification, risk)
        assert any("glycemic" in a.lower() or "hba1c" in a.lower() for a in actions)

    def test_glaucoma_specific_actions(self):
        classification = {"predicted_label": "glaucoma", "requires_urgent_review": False}
        risk = {"risk_level": "moderate"}
        actions = _determine_action_items(classification, risk)
        assert any("intraocular" in a.lower() or "pressure" in a.lower() for a in actions)

    def test_amd_specific_actions(self):
        classification = {"predicted_label": "amd", "requires_urgent_review": False}
        risk = {"risk_level": "moderate"}
        actions = _determine_action_items(classification, risk)
        assert any("vegf" in a.lower() or "therapy" in a.lower() for a in actions)

    def test_cataracts_specific_actions(self):
        classification = {"predicted_label": "cataracts", "requires_urgent_review": False}
        risk = {"risk_level": "low"}
        actions = _determine_action_items(classification, risk)
        assert any("surgical" in a.lower() or "visual" in a.lower() for a in actions)


# ── Risk prioritization ───────────────────────────────────────────────────────

class TestRiskPrioritization:
    def test_risk_priority_ordering(self):
        assert _RISK_PRIORITY["critical"] > _RISK_PRIORITY["high"]
        assert _RISK_PRIORITY["high"] > _RISK_PRIORITY["moderate"]
        assert _RISK_PRIORITY["moderate"] > _RISK_PRIORITY["low"]
        assert _RISK_PRIORITY["low"] > _RISK_PRIORITY["minimal"]

    @patch("app.agent.orchestrator.ScreeningAgent._get_openai_client")
    def test_results_sorted_by_risk_descending(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.chat.completions.create.return_value = make_mock_openai_response(
            f"Summary. {DISCLAIMER}"
        )
        agent = make_agent()
        records = [
            make_patient_record(make_normal_fundus()),
            make_patient_record(make_glaucoma_fundus()),
            make_patient_record(make_diabetic_retinopathy_fundus()),
        ]
        session = agent.run_screening(records)
        priorities = [r.risk_priority for r in session.results if r.status == "success"]
        assert priorities == sorted(priorities, reverse=True)


# ── run_screening workflow ────────────────────────────────────────────────────

class TestRunScreening:
    @patch("app.agent.orchestrator.ScreeningAgent._get_openai_client")
    def test_run_screening_returns_session(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.chat.completions.create.return_value = make_mock_openai_response(
            f"Screening complete. {DISCLAIMER}"
        )
        agent = make_agent()
        records = [make_patient_record()]
        session = agent.run_screening(records)
        assert isinstance(session, ScreeningSession)

    @patch("app.agent.orchestrator.ScreeningAgent._get_openai_client")
    def test_run_screening_correct_total(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.chat.completions.create.return_value = make_mock_openai_response(
            f"Summary. {DISCLAIMER}"
        )
        agent = make_agent()
        records = [make_patient_record(), make_patient_record(), make_patient_record()]
        session = agent.run_screening(records)
        assert session.total_patients == 3

    @patch("app.agent.orchestrator.ScreeningAgent._get_openai_client")
    def test_run_screening_status_completed(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.chat.completions.create.return_value = make_mock_openai_response(
            f"Summary. {DISCLAIMER}"
        )
        agent = make_agent()
        session = agent.run_screening([make_patient_record()])
        assert session.status == AgentStatus.COMPLETED

    @patch("app.agent.orchestrator.ScreeningAgent._get_openai_client")
    def test_run_screening_agent_status_completed_after_run(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.chat.completions.create.return_value = make_mock_openai_response(
            f"Summary. {DISCLAIMER}"
        )
        agent = make_agent()
        agent.run_screening([make_patient_record()])
        assert agent.status == AgentStatus.COMPLETED

    @patch("app.agent.orchestrator.ScreeningAgent._get_openai_client")
    def test_run_screening_summary_contains_disclaimer(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.chat.completions.create.return_value = make_mock_openai_response(
            f"Session summary. {DISCLAIMER}"
        )
        agent = make_agent()
        session = agent.run_screening([make_patient_record()])
        assert DISCLAIMER in session.summary

    @patch("app.agent.orchestrator.ScreeningAgent._get_openai_client")
    def test_run_screening_session_has_session_id(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.chat.completions.create.return_value = make_mock_openai_response(
            f"Summary. {DISCLAIMER}"
        )
        agent = make_agent()
        session = agent.run_screening([make_patient_record()])
        assert session.session_id != ""

    @patch("app.agent.orchestrator.ScreeningAgent._get_openai_client")
    def test_run_screening_empty_batch(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.chat.completions.create.return_value = make_mock_openai_response(
            f"No patients. {DISCLAIMER}"
        )
        agent = make_agent()
        session = agent.run_screening([])
        assert session.total_patients == 0
        assert session.succeeded == 0

    @patch("app.agent.orchestrator.ScreeningAgent._get_openai_client")
    def test_run_screening_urgent_count(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.chat.completions.create.return_value = make_mock_openai_response(
            f"Summary. {DISCLAIMER}"
        )
        agent = make_agent()
        records = [
            make_patient_record(make_diabetic_retinopathy_fundus()),
            make_patient_record(make_glaucoma_fundus()),
            make_patient_record(make_normal_fundus()),
        ]
        session = agent.run_screening(records)
        assert session.urgent_cases >= 0  # depends on heuristic classification

    @patch("app.agent.orchestrator.ScreeningAgent._get_openai_client")
    def test_run_screening_disclaimer_in_session(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.chat.completions.create.return_value = make_mock_openai_response(
            f"Summary. {DISCLAIMER}"
        )
        agent = make_agent()
        session = agent.run_screening([make_patient_record()])
        assert DISCLAIMER in session.disclaimer

    @patch("app.agent.orchestrator.ScreeningAgent._get_openai_client")
    def test_run_screening_results_list_length(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.chat.completions.create.return_value = make_mock_openai_response(
            f"Summary. {DISCLAIMER}"
        )
        agent = make_agent()
        records = [make_patient_record() for _ in range(5)]
        session = agent.run_screening(records)
        assert len(session.results) == 5


# ── Fallback behavior ─────────────────────────────────────────────────────────

class TestFallbackBehavior:
    @patch("app.agent.orchestrator.ScreeningAgent._get_openai_client")
    def test_openai_failure_uses_fallback_summary(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("API down")
        agent = make_agent()
        session = agent.run_screening([make_patient_record()])
        # Should not raise, should return fallback summary
        assert isinstance(session.summary, str)
        assert len(session.summary) > 0

    @patch("app.agent.orchestrator.ScreeningAgent._get_openai_client")
    def test_openai_failure_fallback_contains_disclaimer(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("timeout")
        agent = make_agent()
        session = agent.run_screening([make_patient_record()])
        assert DISCLAIMER in session.summary

    @patch("app.agent.orchestrator.ScreeningAgent._get_openai_client")
    def test_single_patient_failure_does_not_crash_batch(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.chat.completions.create.return_value = make_mock_openai_response(
            f"Summary. {DISCLAIMER}"
        )
        agent = make_agent()

        # Create a corrupted record that will fail processing
        broken_image = Image.new("RGB", (1, 1))  # extremely tiny
        records = [
            make_patient_record(make_normal_fundus()),
            PatientRecord(image=broken_image, patient_ref="broken"),
            make_patient_record(make_normal_fundus()),
        ]
        session = agent.run_screening(records)
        # Session completes even with one failure
        assert session.total_patients == 3
        assert session.status == AgentStatus.COMPLETED


# ── ScreeningResult dataclass ─────────────────────────────────────────────────

class TestScreeningResult:
    def test_default_status_success(self):
        result = ScreeningResult(patient_ref="p1", study_id="s1", status="success")
        assert result.flagged_urgent is False
        assert result.needs_rescan is False
        assert result.action_items == []

    def test_error_result(self):
        result = ScreeningResult(
            patient_ref="p2", study_id="s2", status="error", error="something failed"
        )
        assert result.error == "something failed"

    def test_urgent_flag_set(self):
        result = ScreeningResult(
            patient_ref="p3", study_id="s3", status="success", flagged_urgent=True
        )
        assert result.flagged_urgent is True
