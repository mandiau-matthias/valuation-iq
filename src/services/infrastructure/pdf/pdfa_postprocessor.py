"""Narrow, deterministic repairs required by PDF/A after native rendering."""

from __future__ import annotations

from io import BytesIO

import pikepdf


def normalize_pdfa_image_interpolation(pdf_bytes: bytes) -> tuple[bytes, int]:
    """Force image interpolation off as required by ISO 19005-2 clause 6.2.8.

    WeasyPrint can set ``/Interpolate true`` on raster images and soft masks.
    This function changes that one forbidden flag and leaves all report
    content, metadata and security properties untouched. Saving with a
    deterministic document ID keeps identical inputs byte-stable.
    """

    output = BytesIO()
    changed = 0
    with pikepdf.Pdf.open(BytesIO(pdf_bytes)) as document:
        for item in document.objects:
            try:
                if (
                    str(item.get("/Subtype")) == "/Image"
                    and item.get("/Interpolate", False) is True
                ):
                    item["/Interpolate"] = False
                    changed += 1
            except (AttributeError, TypeError, ValueError):
                # Non-dictionary indirect objects are expected in this walk.
                continue
        if changed == 0:
            return pdf_bytes, 0
        document.save(
            output,
            preserve_pdfa=True,
            fix_metadata_version=False,
            compress_streams=True,
            object_stream_mode=pikepdf.ObjectStreamMode.preserve,
            deterministic_id=True,
        )
    return output.getvalue(), changed
