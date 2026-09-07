"""Immutable DTO values and bounded local image validation; never fetch URLs."""
from __future__ import annotations

import base64
import hashlib
import io
from types import MappingProxyType
from typing import Any

from PIL import Image, UnidentifiedImageError

from .recipe_types import RecipeValidationError


def frozen_json(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: frozen_json(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(frozen_json(item) for item in value)
    return value


def image_payload(data: bytes, content_type: str) -> dict[str, object]:
    if not isinstance(data, bytes) or not 0 < len(data) <= 1048576:
        raise RecipeValidationError('Bild muss zwischen 1 Byte und 1 MiB enthalten.')
    formats = {'image/png': 'PNG', 'image/jpeg': 'JPEG'}
    if content_type not in formats:
        raise RecipeValidationError('PNG oder JPEG erforderlich.')
    try:
        with Image.open(io.BytesIO(data)) as image:
            width, height = image.size
            if image.format != formats[content_type] or not 0 < width <= 10000 or not 0 < height <= 10000:
                raise RecipeValidationError('Ungültiges Bildformat oder Bildmaß.')
            image.verify()
        with Image.open(io.BytesIO(data)) as image:
            image.load()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise RecipeValidationError('Bilddaten sind beschädigt.') from None
    return {'sha256': hashlib.sha256(data).hexdigest(), 'data': base64.b64encode(data).decode('ascii'),
            'content_type': content_type, 'width': width, 'height': height}
