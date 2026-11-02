"""Validate sealed advisor logo bytes without changing branding contracts."""

from __future__ import annotations

import base64
import binascii
import hashlib
import re
from io import BytesIO
from typing import TYPE_CHECKING

from PIL import Image, ImageChops, UnidentifiedImageError

if TYPE_CHECKING:
    from src.api.schemas.stateless_report_schemas import ReportBranding


def validate_immutable_logo_asset(branding: ReportBranding) -> ReportBranding:
    sealed_fields = (
        branding.logo_data_uri,
        branding.logo_sha256,
        branding.logo_mime_type,
        branding.logo_width_px,
        branding.logo_height_px,
    )
    populated = [value is not None for value in sealed_fields]
    if any(populated) and not all(populated):
        raise ValueError("sealed advisor logo metadata must be complete")
    if branding.logo_url and branding.logo_data_uri:
        raise ValueError("advisor branding cannot mix a mutable URL with sealed logo bytes")
    if not branding.logo_data_uri:
        return branding

    match = re.fullmatch(
        r"data:(image/(?:png|jpeg|webp));base64,([A-Za-z0-9+/]+={0,2})",
        branding.logo_data_uri,
    )
    if match is None or match.group(1) != branding.logo_mime_type:
        raise ValueError("sealed advisor logo data URI has an invalid media type")
    try:
        image_bytes = base64.b64decode(match.group(2), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("sealed advisor logo is not canonical base64") from exc
    if not image_bytes or len(image_bytes) > 512 * 1024:
        raise ValueError("sealed advisor logo exceeds the 512 KiB limit")
    if hashlib.sha256(image_bytes).hexdigest() != branding.logo_sha256:
        raise ValueError("sealed advisor logo SHA-256 does not match its bytes")

    expected_format = {
        "image/png": "PNG",
        "image/jpeg": "JPEG",
        "image/webp": "WEBP",
    }[branding.logo_mime_type]
    try:
        with Image.open(BytesIO(image_bytes)) as image:
            width, height = image.size
            image_format = image.format
            image.load()
            rgba = image.convert("RGBA")
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValueError("sealed advisor logo is not a decodable image") from exc
    if image_format != expected_format:
        raise ValueError("sealed advisor logo media type does not match its bytes")
    if (width, height) != (branding.logo_width_px, branding.logo_height_px):
        raise ValueError("sealed advisor logo dimensions do not match its bytes")
    aspect_ratio = width / height
    if aspect_ratio < 0.1 or aspect_ratio > 12:
        raise ValueError("sealed advisor logo has an unsupported aspect ratio")

    alpha = rgba.getchannel("A")
    alpha_min, _alpha_max = alpha.getextrema()
    if alpha_min < 250:
        content_bbox = alpha.point(lambda value: 255 if value > 16 else 0).getbbox()
    else:
        corner = rgba.getpixel((0, 0))
        background = Image.new("RGBA", rgba.size, corner)
        difference = ImageChops.difference(rgba, background).convert("RGB")
        content_bbox = difference.point(lambda value: 255 if value > 20 else 0).getbbox()
        if content_bbox is None:
            content_bbox = (0, 0, width, height)
    if content_bbox is None:
        raise ValueError("sealed advisor logo has no visible content")
    content_width = content_bbox[2] - content_bbox[0]
    content_height = content_bbox[3] - content_bbox[1]
    if content_width / width < 0.25 or content_height / height < 0.15:
        raise ValueError(
            "sealed advisor logo contains excessive empty canvas; crop it before publication"
        )
    return branding
