"""Bounded, decoded logo images; immutable content addressed PostgreSQL assets."""
from __future__ import annotations

import hashlib
import warnings
from dataclasses import dataclass
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import Connection, text

MAX_LOGO_BYTES = 1024 * 1024
MAX_LOGO_DIMENSION = 2048


class LogoValidationError(ValueError):
    """The upload is not a supported, bounded image."""


@dataclass(frozen=True)
class LogoAsset:
    sha256: str
    png: bytes
    width: int
    height: int


def normalize_logo(data: bytes) -> LogoAsset:
    if not data or len(data) > MAX_LOGO_BYTES:
        raise LogoValidationError('Das Logo darf höchstens 1 MiB gross sein.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as source:
                if source.format not in {'PNG', 'JPEG', 'WEBP'} or getattr(source, 'n_frames', 1) != 1:
                    raise LogoValidationError('Bitte ein einzelnes PNG-, JPEG- oder WebP-Bild verwenden.')
                if not all(1 <= size <= MAX_LOGO_DIMENSION for size in source.size):
                    raise LogoValidationError('Das Logo darf höchstens 2048 × 2048 Pixel gross sein.')
                source.load()
                oriented = ImageOps.exif_transpose(source).convert('RGBA')
                # A fresh image strips EXIF, profiles, comments and embedded payloads.
                clean = Image.new('RGBA', oriented.size)
                clean.paste(oriented)
                output = BytesIO()
                clean.save(output, format='PNG', optimize=True)
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError,
            Image.DecompressionBombWarning) as error:
        if isinstance(error, LogoValidationError):
            raise
        raise LogoValidationError('Das Logo konnte nicht als sicheres Bild gelesen werden.') from error
    png = output.getvalue()
    if len(png) > MAX_LOGO_BYTES:
        raise LogoValidationError('Das normalisierte Logo überschreitet 1 MiB. Bitte das Bild verkleinern.')
    return LogoAsset(hashlib.sha256(png).hexdigest(), png, clean.width, clean.height)


def store_logo(connection: Connection, logo: LogoAsset, actor_id: int) -> None:
    """Use only inside the authorized branding-save transaction."""
    if normalize_logo(logo.png) != logo:
        raise LogoValidationError('Das Logo entspricht nicht dem normalisierten Bildvertrag.')
    connection.execute(text('''
        INSERT INTO cafeteria.branding_assets(sha256, png_data, width, height, created_by)
        VALUES (:sha256, :png, :width, :height, :actor)
        ON CONFLICT (sha256) DO NOTHING
    '''), {'sha256': logo.sha256, 'png': logo.png, 'width': logo.width,
          'height': logo.height, 'actor': actor_id})


def load_logo(connection: Connection, sha256: str) -> LogoAsset:
    row = connection.execute(text('''
        SELECT sha256, png_data, width, height FROM cafeteria.branding_assets WHERE sha256=:sha256
    '''), {'sha256': sha256}).one_or_none()
    if row is None:
        raise LookupError('Logo nicht gefunden.')
    return LogoAsset(row.sha256, bytes(row.png_data), row.width, row.height)
