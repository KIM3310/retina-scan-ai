"""Structured audit logging for DICOM operations.

Emits JSON-formatted audit records to a local log file and/or standard output.
In production deployments, these records are shipped to a SIEM and archived
on WORM-backed storage per ``../audit/retention_policy.md``.

Every field relevant to HIPAA 45 CFR Sec 164.312(b) (Audit Controls) is captured:
- WHO  -- principal (AE title for DICOM operations; OIDC subject for user operations)
- WHAT -- event type and affected object(s)
- WHEN -- UTC timestamp, monotonic and high-precision
- WHERE -- source IP / AE title / calling host
- OUTCOME -- success / failure / partial, with reason codes
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import socket
import sys
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_LOG_PATH = Path(os.environ.get("RETINA_DICOM_AUDIT_LOG", "logs/dicom_audit.jsonl"))


@dataclass
class DicomAuditEvent:
    """A single audit record for a DICOM operation.

    Field names are chosen to align with HL7 FHIR AuditEvent and DICOM PS3.15
    Audit Message semantics while remaining simple JSON.
    """

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="microseconds"))
    event_type: str = ""
    outcome: str = "success"
    outcome_detail: str | None = None

    # Principal and peer
    principal: str = ""
    principal_type: str = "ae_title"  # or "oidc_sub"
    source_host: str | None = None
    source_ip: str | None = None
    calling_ae_title: str | None = None
    called_ae_title: str | None = None

    # Object references -- pseudonymised identifiers only
    study_instance_uid_hash: str | None = None
    series_instance_uid_hash: str | None = None
    sop_instance_uid_hash: str | None = None
    patient_id_hash: str | None = None

    # Service-specific
    sop_class_uid: str | None = None
    transfer_syntax_uid: str | None = None
    instance_count: int | None = None
    bytes_received: int | None = None

    # Integrity
    pixel_sha256: str | None = None

    # Additional key-value metadata
    extra: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), separators=(",", ":"))


class DicomAuditLogger:
    """Thread-safe DICOM audit logger.

    Writes JSON lines to a local log file. In production a sidecar ships the
    file to a SIEM over TLS (rsyslog/Fluent Bit/Vector).
    """

    def __init__(self, log_path: Path = DEFAULT_LOG_PATH, to_stdout: bool = True) -> None:
        self.log_path = Path(log_path)
        self.to_stdout = to_stdout
        self._lock = threading.Lock()

        self.log_path.parent.mkdir(parents=True, exist_ok=True)

        self._logger = logging.getLogger("retina.dicom.audit")
        if not self._logger.handlers:
            self._logger.setLevel(logging.INFO)
            file_handler = logging.FileHandler(self.log_path, encoding="utf-8")
            file_handler.setFormatter(logging.Formatter("%(message)s"))
            self._logger.addHandler(file_handler)
            if to_stdout:
                stream_handler = logging.StreamHandler(sys.stderr)
                stream_handler.setFormatter(logging.Formatter("%(message)s"))
                self._logger.addHandler(stream_handler)
            self._logger.propagate = False

    # -- emission --

    def emit(self, event: DicomAuditEvent) -> None:
        with self._lock:
            self._logger.info(event.to_json())

    # -- convenience event constructors --

    def association_open(
        self,
        calling_ae: str,
        called_ae: str,
        source_ip: str | None = None,
    ) -> DicomAuditEvent:
        event = DicomAuditEvent(
            event_type="DICOM_ASSOCIATION_OPEN",
            principal=calling_ae,
            calling_ae_title=calling_ae,
            called_ae_title=called_ae,
            source_ip=source_ip,
            source_host=_lookup_host(source_ip),
        )
        self.emit(event)
        return event

    def association_reject(
        self,
        calling_ae: str,
        called_ae: str,
        reason: str,
        source_ip: str | None = None,
    ) -> DicomAuditEvent:
        event = DicomAuditEvent(
            event_type="DICOM_ASSOCIATION_REJECT",
            outcome="failure",
            outcome_detail=reason,
            principal=calling_ae,
            calling_ae_title=calling_ae,
            called_ae_title=called_ae,
            source_ip=source_ip,
            source_host=_lookup_host(source_ip),
        )
        self.emit(event)
        return event

    def cstore_receive(
        self,
        *,
        calling_ae: str,
        called_ae: str,
        sop_class_uid: str,
        sop_instance_uid: str,
        study_instance_uid: str,
        series_instance_uid: str,
        patient_id: str | None,
        transfer_syntax_uid: str,
        bytes_received: int,
        pixel_sha256: str | None = None,
        outcome: str = "success",
        outcome_detail: str | None = None,
    ) -> DicomAuditEvent:
        event = DicomAuditEvent(
            event_type="DICOM_CSTORE_RECEIVE",
            outcome=outcome,
            outcome_detail=outcome_detail,
            principal=calling_ae,
            calling_ae_title=calling_ae,
            called_ae_title=called_ae,
            sop_class_uid=sop_class_uid,
            sop_instance_uid_hash=_hash_uid(sop_instance_uid),
            study_instance_uid_hash=_hash_uid(study_instance_uid),
            series_instance_uid_hash=_hash_uid(series_instance_uid),
            patient_id_hash=_hash_uid(patient_id) if patient_id else None,
            transfer_syntax_uid=transfer_syntax_uid,
            bytes_received=bytes_received,
            pixel_sha256=pixel_sha256,
        )
        self.emit(event)
        return event

    def anonymization(
        self,
        *,
        original_sop_instance_uid: str,
        new_sop_instance_uid: str,
        original_study_uid: str,
        new_study_uid: str,
        patient_id_original: str | None,
        patient_id_new: str | None,
        profile: str = "DICOM_PS3.15_ANNEX_E_BASIC",
    ) -> DicomAuditEvent:
        event = DicomAuditEvent(
            event_type="ANONYMIZATION",
            principal="retina-scan-ai",
            principal_type="service",
            study_instance_uid_hash=_hash_uid(original_study_uid),
            sop_instance_uid_hash=_hash_uid(original_sop_instance_uid),
            patient_id_hash=_hash_uid(patient_id_original) if patient_id_original else None,
            extra={
                "profile": profile,
                "new_sop_instance_uid_hash": _hash_uid(new_sop_instance_uid),
                "new_study_uid_hash": _hash_uid(new_study_uid),
                "new_patient_id_hash": _hash_uid(patient_id_new) if patient_id_new else None,
            },
        )
        self.emit(event)
        return event

    def inference(
        self,
        *,
        sop_instance_uid: str,
        model_version: str,
        predicted_class: str,
        predicted_confidence: float,
        latency_ms: float,
        outcome: str = "success",
    ) -> DicomAuditEvent:
        event = DicomAuditEvent(
            event_type="INFERENCE",
            outcome=outcome,
            principal="retina-scan-ai",
            principal_type="service",
            sop_instance_uid_hash=_hash_uid(sop_instance_uid),
            extra={
                "model_version": model_version,
                "predicted_class": predicted_class,
                "predicted_confidence": round(float(predicted_confidence), 4),
                "latency_ms": round(float(latency_ms), 2),
            },
        )
        self.emit(event)
        return event

    def gsps_create(
        self,
        *,
        referenced_sop_instance_uid: str,
        new_gsps_sop_instance_uid: str,
        model_version: str,
    ) -> DicomAuditEvent:
        event = DicomAuditEvent(
            event_type="GSPS_CREATE",
            principal="retina-scan-ai",
            principal_type="service",
            sop_instance_uid_hash=_hash_uid(referenced_sop_instance_uid),
            extra={
                "new_gsps_sop_instance_uid_hash": _hash_uid(new_gsps_sop_instance_uid),
                "model_version": model_version,
            },
        )
        self.emit(event)
        return event

    def cstore_send(
        self,
        *,
        sop_class_uid: str,
        sop_instance_uid: str,
        destination_ae: str,
        destination_host: str | None = None,
        outcome: str = "success",
        outcome_detail: str | None = None,
    ) -> DicomAuditEvent:
        event = DicomAuditEvent(
            event_type="DICOM_CSTORE_SEND",
            outcome=outcome,
            outcome_detail=outcome_detail,
            principal="retina-scan-ai",
            principal_type="service",
            sop_class_uid=sop_class_uid,
            sop_instance_uid_hash=_hash_uid(sop_instance_uid),
            called_ae_title=destination_ae,
            source_host=destination_host,
        )
        self.emit(event)
        return event

    def association_close(
        self,
        calling_ae: str,
        called_ae: str,
        instance_count: int | None = None,
    ) -> DicomAuditEvent:
        event = DicomAuditEvent(
            event_type="DICOM_ASSOCIATION_CLOSE",
            principal=calling_ae,
            calling_ae_title=calling_ae,
            called_ae_title=called_ae,
            instance_count=instance_count,
        )
        self.emit(event)
        return event


# -- helpers --

_HASH_SALT = os.environ.get("RETINA_AUDIT_SALT", "retina-scan-ai-default-salt")


def _hash_uid(value: str | None) -> str | None:
    """Return SHA-256 hash of a UID or identifier, salted for the deployment.

    The salt is deployment-specific so the same logical UID hashes to
    different values across deployments. This makes audit records joinable
    within a deployment but not across.
    """
    if value is None:
        return None
    digest = hashlib.sha256((_HASH_SALT + ":" + str(value)).encode("utf-8")).hexdigest()
    return digest


def _lookup_host(ip: str | None) -> str | None:
    if not ip:
        return None
    try:
        return socket.gethostbyaddr(ip)[0]
    except OSError:
        return None


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


if __name__ == "__main__":
    # Smoke test -- emit one of each event type.
    logger = DicomAuditLogger(log_path=Path("logs/dicom_audit_smoke.jsonl"), to_stdout=True)
    logger.association_open("SENDER_AE", "RETINASCAN", source_ip="10.0.0.5")
    logger.cstore_receive(
        calling_ae="SENDER_AE",
        called_ae="RETINASCAN",
        sop_class_uid="1.2.840.10008.5.1.4.1.1.77.1.5.1",
        sop_instance_uid="1.2.3.4.5.6.7.8.9",
        study_instance_uid="1.2.3.4.5",
        series_instance_uid="1.2.3.4.6",
        patient_id="PID-12345",
        transfer_syntax_uid="1.2.840.10008.1.2.1",
        bytes_received=2_000_000,
        pixel_sha256=sha256_bytes(b"fake-pixel-data"),
    )
    logger.anonymization(
        original_sop_instance_uid="1.2.3.4.5.6.7.8.9",
        new_sop_instance_uid="9.9.9.9.9.9",
        original_study_uid="1.2.3.4.5",
        new_study_uid="9.9.9.9",
        patient_id_original="PID-12345",
        patient_id_new="anon-abc",
    )
    logger.inference(
        sop_instance_uid="1.2.3.4.5.6.7.8.9",
        model_version="1.0.0",
        predicted_class="Diabetic Retinopathy",
        predicted_confidence=0.87,
        latency_ms=58.4,
    )
    logger.gsps_create(
        referenced_sop_instance_uid="1.2.3.4.5.6.7.8.9",
        new_gsps_sop_instance_uid="9.9.9.9.9.9.9",
        model_version="1.0.0",
    )
    logger.cstore_send(
        sop_class_uid="1.2.840.10008.5.1.4.1.1.11.1",
        sop_instance_uid="9.9.9.9.9.9.9",
        destination_ae="PACS_AE",
    )
    logger.association_close("SENDER_AE", "RETINASCAN", instance_count=1)
    print("emitted 6 events to", logger.log_path)
