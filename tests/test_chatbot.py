"""Tests for the clinical AI chatbot assistant.

All OpenAI API calls are mocked — no real API key required.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.chatbot.assistant import (
    DISCLAIMER,
    ChatMessage,
    ChatSession,
    ClinicalAssistant,
)

# ── Helpers ───────────────────────────────────────────────────────────────────

def make_mock_openai_response(content: str) -> MagicMock:
    """Build a mock OpenAI ChatCompletion response."""
    mock_choice = MagicMock()
    mock_choice.message.content = content
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    return mock_response


def make_assistant(api_key: str = "test-key-123") -> ClinicalAssistant:
    return ClinicalAssistant(api_key=api_key)


# ── ClinicalAssistant instantiation ──────────────────────────────────────────

class TestClinicalAssistantInit:
    def test_init_with_explicit_key(self):
        assistant = ClinicalAssistant(api_key="sk-test")
        assert assistant._api_key == "sk-test"

    def test_init_reads_env_var(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-env-key")
        assistant = ClinicalAssistant()
        assert assistant._api_key == "sk-env-key"

    def test_init_raises_without_key(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with pytest.raises(EnvironmentError, match="OPENAI_API_KEY"):
            ClinicalAssistant()

    def test_init_raises_empty_env(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "")
        with pytest.raises(EnvironmentError, match="OPENAI_API_KEY"):
            ClinicalAssistant()

    def test_explicit_key_overrides_env(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-env")
        assistant = ClinicalAssistant(api_key="sk-explicit")
        assert assistant._api_key == "sk-explicit"


# ── ChatSession ───────────────────────────────────────────────────────────────

class TestChatSession:
    def test_create_session_stores_context(self):
        assistant = make_assistant()
        session = assistant.create_session(
            classification="diabetic_retinopathy",
            severity="moderate",
            risk_score=0.72,
            risk_level="high",
        )
        assert session.scan_context["classification"] == "diabetic_retinopathy"
        assert session.scan_context["severity"] == "moderate"
        assert session.scan_context["risk_score"] == 0.72
        assert session.scan_context["risk_level"] == "high"

    def test_create_session_empty_history(self):
        assistant = make_assistant()
        session = assistant.create_session("normal", "none", 0.05, "minimal")
        assert session.messages == []

    def test_create_session_with_session_id(self):
        assistant = make_assistant()
        session = assistant.create_session("glaucoma", "severe", 0.9, "critical", session_id="abc123")
        assert session.session_id == "abc123"

    def test_add_message_appends(self):
        session = ChatSession(scan_context={})
        session.add_message("user", "Hello")
        session.add_message("assistant", "Hi there")
        assert len(session.messages) == 2
        assert session.messages[0].role == "user"
        assert session.messages[1].role == "assistant"

    def test_to_openai_messages_includes_system(self):
        session = ChatSession(scan_context={})
        session.add_message("user", "What does this mean?")
        msgs = session.to_openai_messages("You are a doctor.")
        assert msgs[0]["role"] == "system"
        assert msgs[0]["content"] == "You are a doctor."
        assert msgs[1]["role"] == "user"

    def test_to_openai_messages_ordering(self):
        session = ChatSession(scan_context={})
        session.add_message("user", "Q1")
        session.add_message("assistant", "A1")
        session.add_message("user", "Q2")
        msgs = session.to_openai_messages("sys")
        assert len(msgs) == 4
        assert msgs[1]["content"] == "Q1"
        assert msgs[2]["content"] == "A1"
        assert msgs[3]["content"] == "Q2"

    def test_chat_message_dataclass(self):
        msg = ChatMessage(role="user", content="test")
        assert msg.role == "user"
        assert msg.content == "test"


# ── Chat method ───────────────────────────────────────────────────────────────

class TestChatMethod:
    def _make_session(self) -> ChatSession:
        assistant = make_assistant()
        return assistant.create_session(
            classification="diabetic_retinopathy",
            severity="moderate",
            risk_score=0.65,
            risk_level="high",
        )

    @patch("app.chatbot.assistant.ClinicalAssistant._get_client")
    def test_chat_returns_string(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.chat.completions.create.return_value = make_mock_openai_response(
            "The severity indicates moderate DR. " + DISCLAIMER
        )
        assistant = make_assistant()
        session = self._make_session()
        reply = assistant.chat(session, "What does moderate severity mean?")
        assert isinstance(reply, str)
        assert len(reply) > 0

    @patch("app.chatbot.assistant.ClinicalAssistant._get_client")
    def test_chat_always_contains_disclaimer(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.chat.completions.create.return_value = make_mock_openai_response(
            "This patient has moderate DR."
        )
        assistant = make_assistant()
        session = self._make_session()
        reply = assistant.chat(session, "Explain the findings")
        assert DISCLAIMER in reply

    @patch("app.chatbot.assistant.ClinicalAssistant._get_client")
    def test_chat_does_not_duplicate_disclaimer(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.chat.completions.create.return_value = make_mock_openai_response(
            f"Some response. {DISCLAIMER}"
        )
        assistant = make_assistant()
        session = self._make_session()
        reply = assistant.chat(session, "test")
        assert reply.count(DISCLAIMER) == 1

    @patch("app.chatbot.assistant.ClinicalAssistant._get_client")
    def test_chat_adds_user_message_to_history(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.chat.completions.create.return_value = make_mock_openai_response("ok " + DISCLAIMER)
        assistant = make_assistant()
        session = self._make_session()
        assistant.chat(session, "My question")
        assert session.messages[0].role == "user"
        assert session.messages[0].content == "My question"

    @patch("app.chatbot.assistant.ClinicalAssistant._get_client")
    def test_chat_adds_assistant_message_to_history(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.chat.completions.create.return_value = make_mock_openai_response("AI reply " + DISCLAIMER)
        assistant = make_assistant()
        session = self._make_session()
        reply = assistant.chat(session, "question")
        assert session.messages[1].role == "assistant"
        assert reply in session.messages[1].content or session.messages[1].content in reply

    @patch("app.chatbot.assistant.ClinicalAssistant._get_client")
    def test_chat_multi_turn_history_grows(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.chat.completions.create.return_value = make_mock_openai_response("answer " + DISCLAIMER)
        assistant = make_assistant()
        session = self._make_session()
        assistant.chat(session, "Q1")
        assistant.chat(session, "Q2")
        assert len(session.messages) == 4  # user, assistant, user, assistant

    @patch("app.chatbot.assistant.ClinicalAssistant._get_client")
    def test_chat_passes_context_in_system_prompt(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.chat.completions.create.return_value = make_mock_openai_response("ok " + DISCLAIMER)
        assistant = make_assistant()
        session = self._make_session()
        assistant.chat(session, "test")
        call_args = mock_client.chat.completions.create.call_args
        messages = call_args.kwargs.get("messages") or call_args.args[0] if call_args.args else call_args.kwargs["messages"]
        system_content = messages[0]["content"]
        assert "diabetic_retinopathy" in system_content
        assert "moderate" in system_content

    @patch("app.chatbot.assistant.ClinicalAssistant._get_client")
    def test_chat_api_failure_raises_runtime_error(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("connection error")
        assistant = make_assistant()
        session = self._make_session()
        with pytest.raises(RuntimeError, match="AI assistant unavailable"):
            assistant.chat(session, "test")

    @patch("app.chatbot.assistant.ClinicalAssistant._get_client")
    def test_chat_uses_gpt4o_mini_model(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.chat.completions.create.return_value = make_mock_openai_response("ok " + DISCLAIMER)
        assistant = make_assistant()
        session = self._make_session()
        assistant.chat(session, "test")
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs.get("model") == "gpt-4o-mini"


# ── System prompt ─────────────────────────────────────────────────────────────

class TestSystemPrompt:
    def test_system_prompt_includes_classification(self):
        assistant = make_assistant()
        ctx = {"classification": "glaucoma", "severity": "severe", "risk_score": 0.9, "risk_level": "critical"}
        prompt = assistant._build_system_prompt(ctx)
        assert "glaucoma" in prompt

    def test_system_prompt_includes_severity(self):
        assistant = make_assistant()
        ctx = {"classification": "amd", "severity": "advanced", "risk_score": 0.8, "risk_level": "high"}
        prompt = assistant._build_system_prompt(ctx)
        assert "advanced" in prompt

    def test_system_prompt_includes_disclaimer(self):
        assistant = make_assistant()
        ctx = {"classification": "normal", "severity": "none", "risk_score": 0.1, "risk_level": "low"}
        prompt = assistant._build_system_prompt(ctx)
        assert DISCLAIMER in prompt

    def test_get_disclaimer_returns_standard_text(self):
        assistant = make_assistant()
        d = assistant.get_disclaimer()
        assert "ophthalmologist" in d
        assert "AI-assisted" in d


# ── Context injection questions ───────────────────────────────────────────────

class TestClinicalQuestions:
    @patch("app.chatbot.assistant.ClinicalAssistant._get_client")
    def test_severity_question(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.chat.completions.create.return_value = make_mock_openai_response(
            "Moderate DR means microaneurysms are present. " + DISCLAIMER
        )
        assistant = make_assistant()
        session = assistant.create_session("diabetic_retinopathy", "moderate", 0.6, "high")
        reply = assistant.chat(session, "What does this severity level mean?")
        assert DISCLAIMER in reply

    @patch("app.chatbot.assistant.ClinicalAssistant._get_client")
    def test_followup_recommendation_question(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.chat.completions.create.return_value = make_mock_openai_response(
            "Follow-up in 3 months recommended. " + DISCLAIMER
        )
        assistant = make_assistant()
        session = assistant.create_session("diabetic_retinopathy", "mild", 0.4, "moderate")
        reply = assistant.chat(session, "What follow-up do you recommend?")
        assert DISCLAIMER in reply

    @patch("app.chatbot.assistant.ClinicalAssistant._get_client")
    def test_risk_factors_question(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.chat.completions.create.return_value = make_mock_openai_response(
            "Risk factors include poor glycemic control. " + DISCLAIMER
        )
        assistant = make_assistant()
        session = assistant.create_session("diabetic_retinopathy", "severe", 0.85, "critical")
        reply = assistant.chat(session, "Explain the risk factors for this patient")
        assert DISCLAIMER in reply

    @patch("app.chatbot.assistant.ClinicalAssistant._get_client")
    def test_dr_progression_question(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.chat.completions.create.return_value = make_mock_openai_response(
            "DR progresses from mild NPDR to PDR. " + DISCLAIMER
        )
        assistant = make_assistant()
        session = assistant.create_session("diabetic_retinopathy", "moderate", 0.65, "high")
        reply = assistant.chat(session, "Compare this to typical DR progression patterns")
        assert DISCLAIMER in reply
