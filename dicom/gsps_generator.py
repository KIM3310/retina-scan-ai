"""Generate a Grayscale Softcopy Presentation State (GSPS) with Grad-CAM overlay.

GSPS is a DICOM SOP Class (PS3.3 §A.33.4) used to convey annotations, windowing,
and overlays that display on top of a source image. This module produces a GSPS
object referencing a source fundus image, with the Grad-CAM heatmap encoded as
a Graphic Annotation.

The resulting GSPS can be stored back to the hospital PACS and rendered by any
compliant DICOM viewer, so the Grad-CAM overlay is visible in the radiologist's
normal reading workflow without custom software.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime

try:
    import numpy as np
    from pydicom import Dataset, Sequence, dcmread, dcmwrite  # type: ignore
    from pydicom.dataset import FileDataset, FileMetaDataset  # type: ignore
    from pydicom.uid import ExplicitVRLittleEndian, generate_uid  # type: ignore
    _DEPS_AVAILABLE = True
except ImportError:  # pragma: no cover
    _DEPS_AVAILABLE = False


log = logging.getLogger("retina_scan_ai.dicom.gsps")


GSPS_SOP_CLASS_UID = "1.2.840.10008.5.1.4.1.1.11.1"  # Grayscale Softcopy Presentation State


def heatmap_to_contours(
    heatmap: "np.ndarray", threshold: float = 0.5, max_contours: int = 20
) -> list[list[tuple[float, float]]]:
    """Convert a Grad-CAM heatmap into contour polygons above the threshold.

    Uses a simple 'marching squares' approximation suitable for GSPS graphic
    annotations. Contours are returned as lists of (x, y) vertex pairs.
    """
    try:
        from skimage import measure  # type: ignore
    except ImportError:
        log.warning("skimage not available; returning a bounding box contour")
        ys, xs = np.where(heatmap >= threshold)
        if len(xs) == 0:
            return []
        return [
            [
                (float(xs.min()), float(ys.min())),
                (float(xs.max()), float(ys.min())),
                (float(xs.max()), float(ys.max())),
                (float(xs.min()), float(ys.max())),
                (float(xs.min()), float(ys.min())),
            ]
        ]

    contours_raw = measure.find_contours(heatmap, threshold)
    # Sort by length, keep the longest N
    contours_raw.sort(key=lambda c: -len(c))
    kept = contours_raw[:max_contours]
    # skimage returns (row, col); GSPS expects (x, y) = (col, row)
    return [[(float(c[1]), float(c[0])) for c in contour] for contour in kept]


def build_gsps(
    source_ds: "Dataset",
    heatmap: "np.ndarray",
    threshold: float = 0.5,
    description: str = "Grad-CAM attention overlay",
    softcopy_type: str = "Analysis",
) -> "FileDataset":
    """Build a GSPS Dataset referencing the source image, with heatmap overlay.

    The returned object can be written to disk or sent via C-STORE.
    """
    if not _DEPS_AVAILABLE:
        raise RuntimeError("gsps_generator requires pydicom, numpy, scikit-image")

    contours = heatmap_to_contours(heatmap, threshold=threshold)

    # File meta
    file_meta = FileMetaDataset()
    file_meta.FileMetaInformationVersion = b"\x00\x01"
    file_meta.MediaStorageSOPClassUID = GSPS_SOP_CLASS_UID
    file_meta.MediaStorageSOPInstanceUID = generate_uid()
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    file_meta.ImplementationClassUID = generate_uid(prefix="1.2.826.0.1.3680043.9.7433.")
    file_meta.ImplementationVersionName = "RETINA_SCAN_AI"

    ds = FileDataset("", {}, file_meta=file_meta, preamble=b"\x00" * 128)
    now = datetime.now()

    # Patient / study / series identity (inherit from source so the PACS links them)
    for attr in ("PatientID", "PatientName", "PatientBirthDate", "PatientSex"):
        value = getattr(source_ds, attr, None)
        if value is not None:
            setattr(ds, attr, value)
    ds.StudyInstanceUID = source_ds.StudyInstanceUID
    ds.StudyDate = getattr(source_ds, "StudyDate", now.strftime("%Y%m%d"))
    ds.StudyTime = getattr(source_ds, "StudyTime", now.strftime("%H%M%S"))
    ds.AccessionNumber = getattr(source_ds, "AccessionNumber", "")

    # New series for the GSPS object
    ds.SeriesInstanceUID = generate_uid()
    ds.SeriesNumber = 9001
    ds.Modality = "PR"  # Presentation State
    ds.SeriesDescription = description

    # SOP instance
    ds.SOPClassUID = GSPS_SOP_CLASS_UID
    ds.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
    ds.InstanceNumber = 1

    # Presentation creation
    ds.ContentDate = now.strftime("%Y%m%d")
    ds.ContentTime = now.strftime("%H%M%S")
    ds.PresentationCreationDate = ds.ContentDate
    ds.PresentationCreationTime = ds.ContentTime
    ds.ContentCreatorName = "Retina^Scan^AI"
    ds.ContentLabel = "GRADCAM"
    ds.ContentDescription = description

    # Reference the source image
    ref_series_item = Dataset()
    ref_series_item.SeriesInstanceUID = source_ds.SeriesInstanceUID
    ref_image_item = Dataset()
    ref_image_item.ReferencedSOPClassUID = source_ds.SOPClassUID
    ref_image_item.ReferencedSOPInstanceUID = source_ds.SOPInstanceUID
    ref_series_item.ReferencedImageSequence = Sequence([ref_image_item])
    ds.ReferencedSeriesSequence = Sequence([ref_series_item])

    # Graphic Annotation Sequence
    graphic_annotations = Sequence()
    for contour in contours:
        annotation = Dataset()
        annotation.GraphicLayer = "GRADCAM"
        annotation.TextObjectSequence = Sequence([])

        graphic = Dataset()
        graphic.GraphicAnnotationUnits = "PIXEL"
        graphic.GraphicDimensions = 2
        graphic.NumberOfGraphicPoints = len(contour)
        flat = [coord for point in contour for coord in point]
        graphic.GraphicData = flat
        graphic.GraphicType = "POLYLINE"
        graphic.GraphicFilled = "N"
        annotation.GraphicObjectSequence = Sequence([graphic])

        referenced_image = Dataset()
        referenced_image.ReferencedSOPClassUID = source_ds.SOPClassUID
        referenced_image.ReferencedSOPInstanceUID = source_ds.SOPInstanceUID
        annotation.ReferencedImageSequence = Sequence([referenced_image])

        graphic_annotations.append(annotation)

    ds.GraphicAnnotationSequence = graphic_annotations

    # Graphic Layer Sequence
    graphic_layer = Dataset()
    graphic_layer.GraphicLayer = "GRADCAM"
    graphic_layer.GraphicLayerOrder = 1
    graphic_layer.GraphicLayerDescription = description
    graphic_layer.GraphicLayerRecommendedDisplayGrayscaleValue = 65535
    ds.GraphicLayerSequence = Sequence([graphic_layer])

    # Displayed Area
    disp = Dataset()
    disp.ReferencedImageSequence = Sequence([ref_image_item])
    rows = int(getattr(source_ds, "Rows", heatmap.shape[0]))
    cols = int(getattr(source_ds, "Columns", heatmap.shape[1]))
    disp.DisplayedAreaTopLeftHandCorner = [1, 1]
    disp.DisplayedAreaBottomRightHandCorner = [cols, rows]
    disp.PresentationSizeMode = "SCALE TO FIT"
    ds.DisplayedAreaSelectionSequence = Sequence([disp])

    # Softcopy type
    ds.SoftcopyVOILUTSequence = Sequence([])
    ds.PresentationLUTShape = "IDENTITY"
    ds.SpecificCharacterSet = "ISO_IR 100"

    log.info(
        "Built GSPS: study=%s source_sop=%s contours=%d",
        ds.StudyInstanceUID,
        source_ds.SOPInstanceUID,
        len(contours),
    )
    return ds


def build_and_save(
    source_dicom_path: str,
    heatmap: "np.ndarray",
    output_path: str,
    threshold: float = 0.5,
) -> None:
    if not _DEPS_AVAILABLE:
        raise RuntimeError("gsps_generator requires pydicom, numpy, scikit-image")

    source_ds = dcmread(source_dicom_path)
    gsps = build_gsps(source_ds, heatmap, threshold=threshold)
    dcmwrite(output_path, gsps)
    log.info("Wrote GSPS to %s", output_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a GSPS DICOM object with a Grad-CAM overlay")
    parser.add_argument("--source", required=True, help="Path to the source fundus DICOM")
    parser.add_argument(
        "--heatmap",
        required=True,
        help="Path to the heatmap .npy file (shape matches source image)",
    )
    parser.add_argument("--out", required=True, help="Path to write the GSPS DICOM")
    parser.add_argument("--threshold", type=float, default=0.5)
    args = parser.parse_args(argv)

    if not _DEPS_AVAILABLE:
        print(
            "ERROR: requires pydicom, numpy, scikit-image. Install via: pip install pydicom numpy scikit-image",
            file=sys.stderr,
        )
        return 2

    logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s %(message)s")

    heatmap = np.load(args.heatmap)
    build_and_save(args.source, heatmap, args.out, threshold=args.threshold)
    return 0


if __name__ == "__main__":
    sys.exit(main())
