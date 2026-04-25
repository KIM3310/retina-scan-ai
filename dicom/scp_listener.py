"""DICOM C-STORE SCP listener.

Accepts DICOM Store requests from a hospital PACS, validates modality,
anonymizes, stages the image for inference, and emits audit events.

Before production:
- Penetration-test the listener (malformed DICOM, oversized images, DoS).
- Verify the allow-listed SOP Classes match your deployment's image types.
- Configure AE Title, port, and authentication per hospital network policy.
- Review DICOM Conformance Statement with the customer's imaging IT team.
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
from pathlib import Path
from typing import Any

try:
    from pynetdicom import AE, evt, debug_logger  # type: ignore
    from pydicom import dcmwrite  # type: ignore

    _PYNETDICOM_AVAILABLE = True
except ImportError:  # pragma: no cover
    _PYNETDICOM_AVAILABLE = False


log = logging.getLogger("retina_scan_ai.dicom.scp")


ALLOWED_SOP_CLASSES = {
    "1.2.840.10008.5.1.4.1.1.77.1.5.1": "OphthalmicPhotography8BitImageStorage",
    "1.2.840.10008.5.1.4.1.1.77.1.5.2": "OphthalmicPhotography16BitImageStorage",
    "1.2.840.10008.5.1.4.1.1.77.1.4": "VLPhotographicImageStorage",
}


class SCPConfig:
    """Configuration for the SCP listener."""

    def __init__(
        self,
        ae_title: str = "RETINA_SCP",
        port: int = 11112,
        staging_dir: str = "/var/spool/retina-scan-ai/inbound",
        anonymize: bool = True,
        max_pdu_size: int = 16384,
    ) -> None:
        self.ae_title = ae_title
        self.port = port
        self.staging_dir = Path(staging_dir)
        self.anonymize = anonymize
        self.max_pdu_size = max_pdu_size


def handle_store(event: Any, config: SCPConfig) -> int:
    """Handle an incoming C-STORE request.

    Returns a DICOM status code. 0x0000 = success.
    """
    try:
        ds = event.dataset
        ds.file_meta = event.file_meta

        sop_class_uid = getattr(ds, "SOPClassUID", None)
        sop_instance_uid = getattr(ds, "SOPInstanceUID", None)
        study_uid = getattr(ds, "StudyInstanceUID", "<unknown>")

        if sop_class_uid is None or str(sop_class_uid) not in ALLOWED_SOP_CLASSES:
            log.warning(
                "rejecting study=%s — SOP Class %s not in allow list",
                study_uid,
                sop_class_uid,
            )
            # 0xA700 — refused: out of resources (closest standard code for a policy refusal)
            return 0xA700

        if not sop_instance_uid:
            log.warning("rejecting study=%s — missing SOPInstanceUID", study_uid)
            return 0xA700

        # Anonymize before writing to staging, if enabled
        if config.anonymize:
            try:
                from dicom.anonymizer import anonymize_dataset  # type: ignore

                ds = anonymize_dataset(ds)
            except ImportError:
                log.error("anonymizer not available; refusing store to avoid PHI spill")
                return 0xA700
            except Exception as e:  # pragma: no cover
                log.exception("anonymization failed: %s", e)
                return 0xA700

        # Stage the file
        config.staging_dir.mkdir(parents=True, exist_ok=True)
        outpath = config.staging_dir / f"{sop_instance_uid}.dcm"
        dcmwrite(outpath, ds)
        log.info("accepted study=%s sop_instance=%s", study_uid, sop_instance_uid)

        # Emit audit event
        _emit_audit(
            event_type="access.study_receive",
            study_uid=str(study_uid),
            sop_instance_uid=str(sop_instance_uid),
            sop_class_uid=str(sop_class_uid),
            source_ae=str(event.assoc.remote["ae_title"]),
            source_ip=str(event.assoc.remote["address"]),
            outcome="SUCCESS",
        )
        return 0x0000

    except Exception as e:  # pragma: no cover
        log.exception("store handler failed: %s", e)
        # 0xC000 — error: cannot understand
        return 0xC000


def _emit_audit(**kwargs: Any) -> None:
    """Best-effort audit emit. Silently logs if audit module unavailable."""
    try:
        from audit.logger import Actor, Subject, Source, log_access  # type: ignore

        log_access(
            event_type=kwargs.get("event_type", "access.study_receive"),
            actor=Actor(user_id="dicom-scp", display_name="DICOM SCP listener", role="System"),
            subject=Subject(
                study_uid=kwargs.get("study_uid"),
            ),
            source=Source(
                ip=kwargs.get("source_ip"),
                user_agent=f"DICOM-AE/{kwargs.get('source_ae', 'unknown')}",
            ),
        )
    except ImportError:
        log.debug("audit module unavailable; skipping audit emit")


def build_application_entity(config: SCPConfig) -> Any:
    """Build a pynetdicom AE configured for this service's SOP classes."""
    if not _PYNETDICOM_AVAILABLE:
        raise RuntimeError(
            "scp_listener requires pynetdicom and pydicom. "
            "Install via: pip install pynetdicom pydicom"
        )

    ae = AE(ae_title=config.ae_title)
    ae.maximum_pdu_size = config.max_pdu_size

    # Presentation contexts for the SOP classes we accept
    for sop_uid in ALLOWED_SOP_CLASSES:
        ae.add_supported_context(sop_uid)

    # Verification SCP (C-ECHO) — standard best practice
    ae.add_supported_context("1.2.840.10008.1.1")  # Verification

    def _store_callback(event: Any) -> int:
        return handle_store(event, config)

    handlers = [(evt.EVT_C_STORE, _store_callback)]

    # Expose handlers to caller
    ae._retina_handlers = handlers  # type: ignore[attr-defined]
    return ae


def run(config: SCPConfig) -> int:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    log.info("Starting DICOM SCP on %s:%s as %s", "0.0.0.0", config.port, config.ae_title)
    log.info("Staging directory: %s (anonymize=%s)", config.staging_dir, config.anonymize)

    if os.getenv("DICOM_DEBUG", "0") == "1":
        debug_logger()

    ae = build_application_entity(config)
    handlers = ae._retina_handlers  # type: ignore[attr-defined]

    # Graceful shutdown on SIGINT/SIGTERM
    server = ae.start_server(("0.0.0.0", config.port), evt_handlers=handlers, block=False)

    def _shutdown(signum: int, _frame: Any) -> None:
        log.info("Received signal %s; shutting down SCP", signum)
        server.shutdown()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="DICOM C-STORE SCP listener")
    parser.add_argument("--ae-title", default=os.getenv("DICOM_AE_TITLE", "RETINA_SCP"))
    parser.add_argument("--port", type=int, default=int(os.getenv("DICOM_PORT", "11112")))
    parser.add_argument(
        "--staging-dir",
        default=os.getenv("DICOM_STAGING_DIR", "/var/spool/retina-scan-ai/inbound"),
    )
    parser.add_argument(
        "--no-anonymize",
        action="store_true",
        help="Disable anonymization (research use only; not for PHI)",
    )
    args = parser.parse_args(argv)

    config = SCPConfig(
        ae_title=args.ae_title,
        port=args.port,
        staging_dir=args.staging_dir,
        anonymize=not args.no_anonymize,
    )
    return run(config)


if __name__ == "__main__":
    sys.exit(main())
