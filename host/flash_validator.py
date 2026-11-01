"""Validate the structure and checksum of an ESP32 firmware image."""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path


class ImageValidationError(ValueError):
    """Raised when a firmware image is malformed or incomplete."""


def validate_image(image: bytes) -> dict[str, int | bool]:
    """Validate an ESP image header, segments, checksum, and optional hash."""
    if len(image) < 24:
        raise ImageValidationError("image is shorter than the 24-byte ESP image header")
    if image[0] != 0xE9:
        raise ImageValidationError(f"invalid image magic 0x{image[0]:02x}; expected 0xe9")

    segment_count = image[1]
    if not 1 <= segment_count <= 16:
        raise ImageValidationError(f"invalid segment count {segment_count}; expected 1-16")

    offset = 24
    checksum = 0xEF
    for index in range(segment_count):
        if offset + 8 > len(image):
            raise ImageValidationError(f"segment {index + 1} header is truncated")
        segment_length = int.from_bytes(image[offset + 4 : offset + 8], "little")
        offset += 8
        if segment_length == 0:
            raise ImageValidationError(f"segment {index + 1} has zero length")
        segment_end = offset + segment_length
        if segment_end > len(image):
            raise ImageValidationError(f"segment {index + 1} data is truncated")
        for byte in image[offset:segment_end]:
            checksum ^= byte
        offset = segment_end

    checksum_offset = ((offset // 16) + 1) * 16 - 1
    if checksum_offset >= len(image):
        raise ImageValidationError("image checksum byte is missing")
    if image[checksum_offset] != checksum:
        raise ImageValidationError(
            f"checksum mismatch at offset 0x{checksum_offset:x}: "
            f"found 0x{image[checksum_offset]:02x}, expected 0x{checksum:02x}"
        )

    has_sha256 = len(image) >= checksum_offset + 33
    if has_sha256:
        expected_hash = hashlib.sha256(image[: checksum_offset + 1]).digest()
        actual_hash = image[checksum_offset + 1 : checksum_offset + 33]
        if actual_hash != expected_hash:
            raise ImageValidationError("appended SHA-256 digest does not match the image")

    return {
        "size_bytes": len(image),
        "segments": segment_count,
        "checksum_offset": checksum_offset,
        "sha256_appended": has_sha256,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path, help="ESP32 firmware binary to validate")
    args = parser.parse_args()

    if not args.image.is_file():
        parser.error(f"image file does not exist: {args.image}")
    try:
        details = validate_image(args.image.read_bytes())
    except OSError as error:
        print(f"ERROR: cannot read image: {error}", file=sys.stderr)
        return 2
    except ImageValidationError as error:
        print(f"INVALID: {error}", file=sys.stderr)
        return 1

    print(
        "VALID: "
        f"{details['size_bytes']} bytes, {details['segments']} segments, "
        f"checksum at 0x{details['checksum_offset']:x}, "
        f"SHA-256 appended: {details['sha256_appended']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
