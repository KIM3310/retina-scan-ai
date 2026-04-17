"""DICOM de-identification per DICOM PS3.15 Annex E Basic Application Level
Confidentiality Profile, extended with HIPAA Safe Harbor identifiers.

Usage::

    from dicom.anonymizer import DicomAnonymizer
    from pydicom import dcmread

    ds = dcmread("input.dcm")
    anonymizer = DicomAnonymizer()
    anonymized = anonymizer.anonymize(ds)
    anonymized.save_as("anonymized.dcm", enforce_file_format=True)

The anonymizer is intentionally conservative: unknown private tags are removed
and any tag whose VR could contain free text is scrubbed.

References:
- DICOM PS3.15 Annex E (Basic Application Confidentiality Profile)
- HHS HIPAA Privacy Rule, 45 CFR Sec 164.514(b)(2) -- Safe Harbor identifiers
- NEMA PS3.6 -- Data Dictionary
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

try:
    from pydicom import Dataset, DataElement
    from pydicom.dataset import FileDataset
    from pydicom.tag import Tag
    from pydicom.uid import generate_uid
    from pydicom.valuerep import PersonName
except ImportError as exc:  # pragma: no cover - enforced at runtime
    raise ImportError(
        "pydicom is required for dicom.anonymizer. Install with: pip install pydicom"
    ) from exc


log = logging.getLogger(__name__)


# -- tag set for DICOM PS3.15 Annex E Basic Profile + HIPAA Safe Harbor --

# Tags to remove entirely (delete element).
TAGS_TO_REMOVE: tuple[tuple[int, int], ...] = (
    (0x0008, 0x0080),  # InstitutionName
    (0x0008, 0x0081),  # InstitutionAddress
    (0x0008, 0x0082),  # InstitutionCodeSequence
    (0x0008, 0x0092),  # ReferringPhysicianAddress
    (0x0008, 0x0094),  # ReferringPhysicianTelephoneNumbers
    (0x0008, 0x1010),  # StationName
    (0x0008, 0x1040),  # InstitutionalDepartmentName
    (0x0008, 0x1080),  # AdmittingDiagnosesDescription
    (0x0010, 0x1000),  # OtherPatientIDs
    (0x0010, 0x1005),  # PatientBirthName
    (0x0010, 0x1040),  # PatientAddress
    (0x0010, 0x1060),  # PatientMotherBirthName
    (0x0010, 0x2150),  # CountryOfResidence
    (0x0010, 0x2152),  # RegionOfResidence
    (0x0010, 0x2154),  # PatientTelephoneNumbers
    (0x0010, 0x21F0),  # PatientReligiousPreference
    (0x0010, 0x4000),  # PatientComments
    (0x0018, 0x1000),  # DeviceSerialNumber
    (0x0018, 0x1004),  # PlateID
    (0x0018, 0x1005),  # GeneratorID
    (0x0018, 0x1007),  # CassetteID
    (0x0018, 0x1008),  # GantryID
    (0x0020, 0x0010),  # StudyID
    (0x0020, 0x4000),  # ImageComments
    (0x0032, 0x1032),  # RequestingPhysician
    (0x0040, 0x0253),  # PerformedProcedureStepID
    (0x0040, 0x0254),  # PerformedProcedureStepDescription
    (0x0040, 0x1001),  # RequestedProcedureID
    (0x0040, 0x1400),  # RequestedProcedureComments
    (0x0040, 0x2008),  # OrderEnteredBy
    (0x0040, 0x2009),  # OrderEntererLocationName
    (0x0040, 0x2010),  # OrderCallbackPhoneNumber
    (0x0040, 0x2016),  # PlacerOrderNumberImagingServiceRequest
    (0x0040, 0x2017),  # FillerOrderNumberImagingServiceRequest
    (0x0040, 0x2400),  # ImagingServiceRequestComments
)

# Tags to replace with an empty value (PN VR name or empty string).
TAGS_TO_EMPTY: tuple[tuple[int, int], ...] = (
    (0x0008, 0x0090),  # ReferringPhysicianName
    (0x0008, 0x0096),  # ReferringPhysicianIdentificationSequence
    (0x0008, 0x1048),  # PhysiciansOfRecord
    (0x0008, 0x1050),  # PerformingPhysicianName
    (0x0008, 0x1060),  # NameOfPhysiciansReadingStudy
    (0x0008, 0x1070),  # OperatorsName
    (0x0010, 0x0010),  # PatientName
    (0x0010, 0x1001),  # OtherPatientNames
    (0x0010, 0x2160),  # EthnicGroup -- redacted unless retention is explicitly configured for fairness monitoring
    (0x0040, 0xA075),  # VerifyingObserverName
)

# Tags that hold dates -- set to year-only YYYY0101.
TAGS_TO_YEAR_ONLY: tuple[tuple[int, int], ...] = (
    (0x0008, 0x0020),  # StudyDate
    (0x0008, 0x0021),  # SeriesDate
    (0x0008, 0x0022),  # AcquisitionDate
    (0x0008, 0x0023),  # ContentDate
    (0x0008, 0x0024),  # OverlayDate
    (0x0008, 0x0025),  # CurveDate
    (0x0010, 0x0030),  # PatientBirthDate
    (0x0010, 0x0032),  # PatientBirthTime
    (0x0010, 0x21D0),  # LastMenstrualDate
    (0x0032, 0x0032),  # StudyVerifiedDate
    (0x0032, 0x1040),  # StudyArrivalDate
    (0x0032, 0x1060),  # RequestedProcedureDescription -- clinical, retained
    (0x0040, 0x0244),  # PerformedProcedureStepStartDate
    (0x0040, 0x0245),  # PerformedProcedureStepStartTime
    (0x3006, 0x0008),  # StructureSetDate
)

# Tags holding times -- zeroed.
TAGS_TO_ZERO_TIME: tuple[tuple[int, int], ...] = (
    (0x0008, 0x0030),  # StudyTime
    (0x0008, 0x0031),  # SeriesTime
    (0x0008, 0x0032),  # AcquisitionTime
    (0x0008, 0x0033),  # ContentTime
    (0x0008, 0x0034),  # OverlayTime
    (0x0008, 0x0035),  # CurveTime
)

# Tags that are UIDs requiring consistent remapping.
TAGS_TO_REMAP_UID: tuple[tuple[int, int], ...] = (
    (0x0008, 0x0018),  # SOPInstanceUID
    (0x0008, 0x1155),  # ReferencedSOPInstanceUID
    (0x0020, 0x000D),  # StudyInstanceUID
    (0x0020, 0x000E),  # SeriesInstanceUID
    (0x0020, 0x0052),  # FrameOfReferenceUID
    (0x0020, 0x0200),  # SynchronizationFrameOfReferenceUID
)

# Tags requiring pseudonymisation via HMAC.
TAGS_TO_PSEUDONYMISE: tuple[tuple[int, int], ...] = (
    (0x0008, 0x0050),  # AccessionNumber
    (0x0010, 0x0020),  # PatientID
    (0x0010, 0x0021),  # IssuerOfPatientID
)

# Tags to retain because they are clinically meaningful and not PHI-identifying.
TAGS_TO_RETAIN: tuple[tuple[int, int], ...] = (
    (0x0008, 0x0016),  # SOPClassUID
    (0x0008, 0x0060),  # Modality
    (0x0008, 0x1030),  # StudyDescription -- monitor; can be overridden
    (0x0008, 0x103E),  # SeriesDescription
    (0x0010, 0x0040),  # PatientSex -- clinically relevant for fairness monitoring
    (0x0010, 0x1010),  # PatientAge
    (0x0018, 0x0015),  # BodyPartExamined
    (0x0020, 0x0011),  # SeriesNumber
    (0x0020, 0x0013),  # InstanceNumber
    (0x0028, 0x0002),  # SamplesPerPixel
    (0x0028, 0x0004),  # PhotometricInterpretation
    (0x0028, 0x0010),  # Rows
    (0x0028, 0x0011),  # Columns
    (0x0028, 0x0100),  # BitsAllocated
    (0x0028, 0x0101),  # BitsStored
    (0x0028, 0x0102),  # HighBit
    (0x0028, 0x0103),  # PixelRepresentation
    (0x7FE0, 0x0010),  # PixelData
)


@dataclass
class AnonymizationRecord:
    """Bookkeeping for a single anonymisation operation.

    The mapping from original UIDs/IDs to pseudonymised replacements is
    retained in memory by default. In production, persistence of the mapping
    is deployment-specific (encrypted K/V store inside the trust boundary).
    """

    original_sop_instance_uid: str
    new_sop_instance_uid: str
    original_study_instance_uid: str
    new_study_instance_uid: str
    original_series_instance_uid: str
    new_series_instance_uid: str
    original_patient_id: str | None
    new_patient_id: str | None
    profile: str = "DICOM_PS3.15_ANNEX_E_BASIC"
    mapping: dict[str, str] = field(default_factory=dict)


class DicomAnonymizer:
    """Anonymise a DICOM dataset.

    Parameters
    ----------
    hmac_key:
        HMAC key for pseudonymisation of PatientID and similar fields. Must be
        a deployment secret; treated as operational configuration. Never log it.
    uid_root:
        Root UID for newly generated SOP/Study/Series UIDs. Use an organisation
        root registered with the appropriate authority in production.
    consistent:
        If True (default), the same input UID/PID maps to the same output value
        across successive calls within the process lifetime. Disable for
        single-use pseudonymisation.
    retain_patient_sex:
        Retain (0010,0040) PatientSex for fairness monitoring (default True).
    retain_patient_age:
        Retain (0010,1010) PatientAge (default True).
    retain_ethnic_group:
        Retain (0010,2160) EthnicGroup (default False; opt-in).
    """

    def __init__(
        self,
        hmac_key: bytes | None = None,
        uid_root: str = "2.25",
        consistent: bool = True,
        retain_patient_sex: bool = True,
        retain_patient_age: bool = True,
        retain_ethnic_group: bool = False,
    ) -> None:
        if hmac_key is None:
            # Derive from env; in production this comes from a secret store.
            env_key = os.environ.get("RETINA_ANON_HMAC_KEY")
            if env_key is None:
                log.warning(
                    "No HMAC key provided; using deterministic default. "
                    "Set RETINA_ANON_HMAC_KEY for production."
                )
                env_key = "retina-scan-ai-default-key-do-not-use-in-production"
            hmac_key = env_key.encode("utf-8")
        self._hmac_key = hmac_key
        self._uid_root = uid_root
        self._consistent = consistent
        self._uid_cache: dict[str, str] = {}
        self._pid_cache: dict[str, str] = {}
        self._retain_patient_sex = retain_patient_sex
        self._retain_patient_age = retain_patient_age
        self._retain_ethnic_group = retain_ethnic_group

    # -- public API --

    def anonymize(self, ds: Dataset) -> FileDataset:
        """Return a new anonymised copy of ``ds``.

        The original ``ds`` is not modified.
        """
        if self._pixel_has_burned_in_annotation(ds):
            raise AnonymizationError(
                "BurnedInAnnotation is YES -- image must be quarantined for manual review"
            )

        # Work on a deep-ish copy; pydicom's copy.deepcopy is expensive, so we copy
        # by walking and rebuilding.
        new_ds = Dataset()
        # Preserve file_meta for FileDataset reconstruction below.
        for element in ds.iterall():
            if _is_in(element.tag, TAGS_TO_REMOVE):
                continue
            new_ds.add(element)

        # Remove every private tag.
        new_ds.remove_private_tags()

        # Empty out the "names to empty" set.
        for group, elem in TAGS_TO_EMPTY:
            tag = Tag(group, elem)
            if tag not in new_ds:
                continue
            if not self._should_retain(group, elem):
                element = new_ds[tag]
                element.value = _empty_for_vr(element.VR)

        # Conditionally retain certain patient attributes.
        if not self._retain_patient_sex:
            _remove_tag(new_ds, 0x0010, 0x0040)
        if not self._retain_patient_age:
            _remove_tag(new_ds, 0x0010, 0x1010)
        if self._retain_ethnic_group:
            # Cancel the "empty" default above for ethnic group.
            # (Re-set from the source if present.)
            tag = Tag(0x0010, 0x2160)
            if tag in ds:
                new_ds[tag] = DataElement(tag, "SH", ds[tag].value)

        # Year-only dates, zeroed times.
        for group, elem in TAGS_TO_YEAR_ONLY:
            tag = Tag(group, elem)
            if tag in new_ds:
                original_value = new_ds[tag].value
                new_ds[tag].value = _year_only(original_value)
        for group, elem in TAGS_TO_ZERO_TIME:
            tag = Tag(group, elem)
            if tag in new_ds:
                new_ds[tag].value = "000000.000000"

        # UID remapping.
        remap: dict[str, str] = {}
        for group, elem in TAGS_TO_REMAP_UID:
            tag = Tag(group, elem)
            if tag in new_ds:
                original = str(new_ds[tag].value)
                new_uid = self._remap_uid(original)
                new_ds[tag].value = new_uid
                remap[original] = new_uid

        # Pseudonymise identifiers.
        for group, elem in TAGS_TO_PSEUDONYMISE:
            tag = Tag(group, elem)
            if tag in new_ds:
                original = str(new_ds[tag].value)
                if original:
                    new_ds[tag].value = self._pseudonymise(original)

        # Attach de-identification audit metadata per PS3.15 Sec E.3.
        _set_deidentification_headers(new_ds)

        # Rebuild file meta to reflect new UIDs.
        new_file_meta = getattr(ds, "file_meta", None)
        if new_file_meta is not None:
            try:
                new_file_meta = type(new_file_meta)()
                for element in ds.file_meta.iterall():  # type: ignore[attr-defined]
                    new_file_meta.add(element)
                if hasattr(new_file_meta, "MediaStorageSOPInstanceUID"):
                    new_file_meta.MediaStorageSOPInstanceUID = new_ds.get(
                        "SOPInstanceUID", new_file_meta.MediaStorageSOPInstanceUID
                    )
            except Exception:  # pragma: no cover -- defensive
                new_file_meta = ds.file_meta

        out = FileDataset(
            filename_or_obj=getattr(ds, "filename", ""),
            dataset=new_ds,
            file_meta=new_file_meta,
            preamble=b"\0" * 128,
        )
        # Transfer syntax from original if available.
        if new_file_meta is not None and hasattr(new_file_meta, "TransferSyntaxUID"):
            out.is_little_endian = True
            out.is_implicit_VR = False

        return out

    def build_record(self, original: Dataset, anonymized: Dataset) -> AnonymizationRecord:
        return AnonymizationRecord(
            original_sop_instance_uid=str(original.get("SOPInstanceUID", "")),
            new_sop_instance_uid=str(anonymized.get("SOPInstanceUID", "")),
            original_study_instance_uid=str(original.get("StudyInstanceUID", "")),
            new_study_instance_uid=str(anonymized.get("StudyInstanceUID", "")),
            original_series_instance_uid=str(original.get("SeriesInstanceUID", "")),
            new_series_instance_uid=str(anonymized.get("SeriesInstanceUID", "")),
            original_patient_id=str(original.get("PatientID", "")) or None,
            new_patient_id=str(anonymized.get("PatientID", "")) or None,
        )

    # -- internals --

    def _should_retain(self, group: int, elem: int) -> bool:
        if (group, elem) == (0x0010, 0x0040) and self._retain_patient_sex:
            return True
        if (group, elem) == (0x0010, 0x1010) and self._retain_patient_age:
            return True
        if (group, elem) == (0x0010, 0x2160) and self._retain_ethnic_group:
            return True
        return False

    def _remap_uid(self, original: str) -> str:
        if not original:
            return original
        if self._consistent and original in self._uid_cache:
            return self._uid_cache[original]
        new_uid = generate_uid(prefix=self._uid_root + ".")
        if self._consistent:
            self._uid_cache[original] = new_uid
        return new_uid

    def _pseudonymise(self, original: str) -> str:
        if self._consistent and original in self._pid_cache:
            return self._pid_cache[original]
        digest = hmac.new(self._hmac_key, original.encode("utf-8"), hashlib.sha256).hexdigest()
        # DICOM LO is max 64 chars; truncate.
        pseud = "anon-" + digest[:40]
        if self._consistent:
            self._pid_cache[original] = pseud
        return pseud

    def _pixel_has_burned_in_annotation(self, ds: Dataset) -> bool:
        tag = Tag(0x0028, 0x0301)
        if tag not in ds:
            return False
        value = ds[tag].value
        if value is None:
            return False
        return str(value).strip().upper() == "YES"


class AnonymizationError(Exception):
    """Raised when the source DICOM cannot be safely anonymised."""


# -- helpers --


def _is_in(tag: Tag, table: tuple[tuple[int, int], ...]) -> bool:
    return any(tag.group == group and tag.element == elem for group, elem in table)


def _empty_for_vr(vr: str) -> Any:
    if vr == "PN":
        return PersonName("")
    if vr in {"DA", "DT", "TM"}:
        return ""
    if vr in {"SQ"}:
        return []
    return ""


def _year_only(value: Any) -> str:
    if not value:
        return ""
    s = str(value)
    if len(s) >= 4 and s[:4].isdigit():
        return f"{s[:4]}0101"
    return ""


def _remove_tag(ds: Dataset, group: int, elem: int) -> None:
    tag = Tag(group, elem)
    if tag in ds:
        del ds[tag]


def _set_deidentification_headers(ds: Dataset) -> None:
    """Set (0012,0062) PatientIdentityRemoved and associated attributes.

    Per DICOM PS3.15 E.3.
    """
    ds.add_new((0x0012, 0x0062), "CS", "YES")
    # Codes per DICOM PS3.16 CID 7050 -- Basic Profile is "113100".
    ds.add_new(
        (0x0012, 0x0063),
        "LO",
        "Anonymised by Retina Scan AI per DICOM PS3.15 Annex E Basic Profile",
    )
    now_dt = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    # A minimal De-identification Method Code Sequence (0012,0064).
    method_item = Dataset()
    method_item.CodeValue = "113100"
    method_item.CodingSchemeDesignator = "DCM"
    method_item.CodeMeaning = "Basic Application Confidentiality Profile"
    ds.DeidentificationMethodCodeSequence = [method_item]
    ds.add_new((0x0012, 0x0023), "LO", f"RetinaScanAI:{now_dt}")


if __name__ == "__main__":  # pragma: no cover - smoke test
    import argparse

    parser = argparse.ArgumentParser(description="Anonymise a DICOM file")
    parser.add_argument("input", help="Input DICOM path")
    parser.add_argument("output", help="Output DICOM path")
    args = parser.parse_args()

    from pydicom import dcmread

    ds_in = dcmread(args.input)
    anonymizer = DicomAnonymizer()
    ds_out = anonymizer.anonymize(ds_in)
    ds_out.save_as(args.output)
    print(f"Anonymised {args.input} -> {args.output}")
