"""Clinical AI chatbot for interpreting retinal scan results.

Provides a multi-turn conversational interface for clinicians to ask questions
about retinal scan classifications, severity grades, and risk scores.

DISCLAIMER: This is an AI-assisted tool. All findings must be confirmed by a
qualified ophthalmologist.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

DISCLAIMER = (
    "This is an AI-assisted tool. All findings must be confirmed by a qualified ophthalmologist."
)

SYSTEM_PROMPT_TEMPLATE = """You are a clinical AI assistant specializing in retinal disease interpretation.
You help ophthalmologists and clinicians understand retinal scan results.

Current scan context:
- Classification: {classification}
- Severity: {severity}
- Risk Score: {risk_score}
- Risk Level: {risk_level}

Your role:
- Answer questions about the scan findings in clear, clinical language
- Explain severity levels and what they mean for patient management
- Suggest appropriate follow-up intervals and referral thresholds
- Explain risk factors and DR progression patterns
- Provide evidence-based recommendations

Important constraints:
- You are an AI assistant, NOT a diagnostic tool
- Always remind clinicians that findings require confirmation by a qualified ophthalmologist
- Do not make definitive diagnoses
- When uncertain, recommend specialist consultation
- Keep responses concise and clinically relevant

Disclaimer: {disclaimer}
"""


@dataclass
class ChatMessage:
    """A single message in a chat conversation."""

    role: str  # "user" | "assistant" | "system"
    content: str


@dataclass
class ChatSession:
    """Tracks conversation history for a multi-turn dialogue."""

    scan_context: dict[str, Any]
    messages: list[ChatMessage] = field(default_factory=list)
    session_id: str = ""

    def add_message(self, role: str, content: str) -> None:
        self.messages.append(ChatMessage(role=role, content=content))

    def to_openai_messages(self, system_prompt: str) -> list[dict[str, str]]:
        """Convert session history to OpenAI message format."""
        result = [{"role": "system", "content": system_prompt}]
        for msg in self.messages:
            result.append({"role": msg.role, "content": msg.content})
        return result


class ClinicalAssistant:
    """Clinical AI assistant for retinal scan result interpretation.

    Uses OpenAI GPT-4o-mini to answer clinician questions about scan results.
    Maintains conversation history for multi-turn dialogue.

    Raises:
        EnvironmentError: If OPENAI_API_KEY is not set.
    """

    MODEL = "gpt-4o-mini"

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self._api_key:
            raise OSError(
                "OPENAI_API_KEY environment variable is not set. "
                "Please set it before using the ClinicalAssistant."
            )
        self._client: Any = None  # lazy-initialized

    def _get_client(self) -> Any:
        """Lazy-initialize OpenAI client."""
        if self._client is None:
            try:
                from openai import OpenAI  # noqa: PLC0415
                self._client = OpenAI(api_key=self._api_key)
            except ImportError as exc:
                raise ImportError(
                    "openai package is required. Install with: pip install openai"
                ) from exc
        return self._client

    def _build_system_prompt(self, scan_context: dict[str, Any]) -> str:
        """Build the system prompt with scan context injected."""
        return SYSTEM_PROMPT_TEMPLATE.format(
            classification=scan_context.get("classification", "Not available"),
            severity=scan_context.get("severity", "Not available"),
            risk_score=scan_context.get("risk_score", "Not available"),
            risk_level=scan_context.get("risk_level", "Not available"),
            disclaimer=DISCLAIMER,
        )

    def create_session(
        self,
        classification: str,
        severity: str,
        risk_score: float | str,
        risk_level: str,
        session_id: str = "",
    ) -> ChatSession:
        """Create a new chat session with scan context.

        Args:
            classification: Predicted disease label (e.g., "diabetic_retinopathy").
            severity: Severity grade (e.g., "moderate").
            risk_score: Numeric risk score (0.0 – 1.0) or string.
            risk_level: Risk level string (e.g., "high").
            session_id: Optional opaque session identifier.

        Returns:
            A new ChatSession ready for multi-turn conversation.
        """
        scan_context = {
            "classification": classification,
            "severity": severity,
            "risk_score": risk_score,
            "risk_level": risk_level,
        }
        return ChatSession(scan_context=scan_context, session_id=session_id)

    def chat(self, session: ChatSession, message: str) -> str:
        """Send a message and get a clinical AI response.

        Args:
            session: The active ChatSession with scan context.
            message: Clinician's natural language question.

        Returns:
            AI assistant response string, always includes disclaimer reminder.

        Raises:
            EnvironmentError: If API key is missing.
            RuntimeError: If the OpenAI API call fails.
        """
        session.add_message("user", message)

        system_prompt = self._build_system_prompt(session.scan_context)
        messages = session.to_openai_messages(system_prompt)

        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=self.MODEL,
                messages=messages,
                max_tokens=512,
                temperature=0.3,  # low temperature for clinical accuracy
            )
            reply = response.choices[0].message.content or ""
        except Exception as exc:
            logger.error("OpenAI API call failed: %s", exc)
            raise RuntimeError(f"AI assistant unavailable: {exc}") from exc

        # Ensure disclaimer is always appended if not already present
        if DISCLAIMER not in reply:
            reply = f"{reply}\n\n---\n{DISCLAIMER}"

        session.add_message("assistant", reply)
        return reply

    def get_disclaimer(self) -> str:
        """Return the standard clinical disclaimer."""
        return DISCLAIMER
