from __future__ import annotations
import ipaddress
import os
import re
import socket
import urllib.parse
from pathlib import Path
from typing import Iterable, Optional

from app.models.schemas import DuplicatePolicy

WINDOWS_RESERVED_NAMES = frozenset({
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
})

WINDOWS_INVALID_CHARS_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

PRIVATE_HOST_SUFFIXES = (
    ".localhost",
    ".local",
    ".internal",
    ".intranet",
    ".lan",
    ".home.arpa",
)


class SecurityValidationError(ValueError):
    """Raised when a URL, path, or filename violates security constraints."""


def validate_download_url(url: str, resolve_dns: bool = False) -> str:
    """
    Validates that a URL uses strictly HTTP or HTTPS and does not target
    loopback, link-local, or private network addresses (SSRF protection).
    """
    if not url or not isinstance(url, str):
        raise SecurityValidationError("URL cannot be empty.")

    cleaned = url.strip()
    if len(cleaned) > 2048:
        raise SecurityValidationError("URL exceeds maximum allowed length (2048 characters).")

    try:
        parsed = urllib.parse.urlsplit(cleaned)
    except ValueError as exc:
        raise SecurityValidationError(f"Malformed URL: {exc}") from exc

    scheme = (parsed.scheme or "").lower()
    if scheme not in ("http", "https"):
        raise SecurityValidationError(
            f"Unsupported URL scheme '{scheme or 'none'}'. Only http:// and https:// URLs are allowed."
        )

    hostname = (parsed.hostname or "").strip().lower().rstrip(".")
    if not hostname:
        raise SecurityValidationError("URL must include a valid hostname.")

    if hostname == "localhost" or hostname.endswith(PRIVATE_HOST_SUFFIXES):
        raise SecurityValidationError(
            f"Local and private network hostnames ('{hostname}') are not allowed."
        )

    # Check if literal IP address
    ip_obj = None
    try:
        ip_obj = ipaddress.ip_address(hostname)
    except ValueError:
        ip_obj = None

    if ip_obj is not None:
        if (
            ip_obj.is_private
            or ip_obj.is_loopback
            or ip_obj.is_link_local
            or ip_obj.is_multicast
            or ip_obj.is_reserved
            or ip_obj.is_unspecified
        ):
            raise SecurityValidationError(
                f"Target IP address '{hostname}' is in a restricted local or private network range."
            )
    else:
        # Hostname is not a literal IP; require a valid domain structure
        if "." not in hostname:
            raise SecurityValidationError(
                f"Single-label internal hostname '{hostname}' is not allowed."
            )
        if resolve_dns:
            try:
                infos = socket.getaddrinfo(hostname, None)
                for info in infos:
                    resolved_ip = ipaddress.ip_address(info[4][0])
                    if (
                        resolved_ip.is_private
                        or resolved_ip.is_loopback
                        or resolved_ip.is_link_local
                        or resolved_ip.is_reserved
                        or resolved_ip.is_unspecified
                    ):
                        raise SecurityValidationError(
                            f"Hostname '{hostname}' resolves to restricted internal address '{resolved_ip}'."
                        )
            except socket.gaierror:
                pass

    return cleaned


def sanitize_filename(filename: str, default_stem: str = "media_output") -> str:
    """
    Sanitizes a filename for Windows and POSIX compatibility while preserving Unicode.
    Strips path components, reserved characters, trailing dots/spaces, and device names.
    """
    if not filename or not filename.strip():
        return default_stem

    # Strip any directory components
    raw_name = os.path.basename(filename.strip().replace("\\", "/"))
    cleaned = WINDOWS_INVALID_CHARS_RE.sub("_", raw_name)
    cleaned = cleaned.strip(" .")

    if not cleaned or cleaned in (".", ".."):
        cleaned = default_stem

    stem, ext = os.path.splitext(cleaned)
    if not stem:
        stem = default_stem

    if stem.upper() in WINDOWS_RESERVED_NAMES:
        stem = f"_{stem}"

    # Enforce safe length limit (200 chars for stem + ext)
    if len(stem) > 180:
        stem = stem[:180].rstrip(" .")

    return f"{stem}{ext}"


def validate_path_in_allowed_dirs(
    target_path: str | Path,
    allowed_dirs: Iterable[str | Path],
    must_exist: bool = False,
) -> Path:
    """
    Resolves `target_path` and verifies it resides strictly within at least one
    of the configured `allowed_dirs` to prevent path traversal (`../`).
    """
    if not target_path or str(target_path).strip() == "":
        raise SecurityValidationError("File path cannot be empty.")

    raw_str = str(target_path).strip()
    if "\x00" in raw_str:
        raise SecurityValidationError("Null bytes are not permitted in paths.")

    try:
        raw_path = Path(raw_str).expanduser()
        resolved_target = raw_path.resolve()
    except Exception as exc:
        raise SecurityValidationError(f"Invalid file path '{raw_str}': {exc}") from exc

    allowed_resolved = []
    for d in allowed_dirs:
        if d:
            try:
                allowed_resolved.append(Path(str(d)).expanduser().resolve())
            except Exception:
                continue

    if not allowed_resolved:
        raise SecurityValidationError("No permitted directories are configured.")

    def _is_under_allowed(candidate: Path) -> bool:
        for root in allowed_resolved:
            try:
                candidate.relative_to(root)
                return True
            except ValueError:
                continue
        return False

    is_permitted = _is_under_allowed(resolved_target)
    if not is_permitted and not raw_path.is_absolute():
        project_root = Path(__file__).resolve().parent.parent.parent
        alt_target = (project_root / raw_path).resolve()
        if _is_under_allowed(alt_target):
            resolved_target = alt_target
            is_permitted = True

    if not is_permitted:
        allowed_display = ", ".join(str(r) for r in allowed_resolved)
        raise SecurityValidationError(
            f"Access denied: path '{resolved_target}' is outside permitted directories ({allowed_display})."
        )

    if must_exist and not resolved_target.exists():
        raise SecurityValidationError(f"Requested file or directory does not exist: '{resolved_target.name}'.")

    return resolved_target


def resolve_output_filepath(
    directory: Path,
    desired_filename: str,
    policy: DuplicatePolicy = DuplicatePolicy.RENAME,
    forbid_same_as: Optional[Path] = None,
) -> Optional[Path]:
    """
    Determines the safe destination path according to `policy`:
    - OVERWRITE: returns path directly (unless identical to `forbid_same_as`, which then renames)
    - SKIP: returns None if file already exists
    - RENAME: appends ` (1)`, ` (2)`, etc. if file already exists
    """
    safe_name = sanitize_filename(desired_filename)
    candidate = (directory / safe_name).resolve()

    if forbid_same_as is not None and candidate == forbid_same_as.resolve():
        stem, ext = os.path.splitext(safe_name)
        safe_name = f"{stem}_converted{ext}"
        candidate = (directory / safe_name).resolve()

    if not candidate.exists():
        return candidate

    if policy == DuplicatePolicy.SKIP:
        return None

    if policy == DuplicatePolicy.OVERWRITE:
        return candidate

    # DuplicatePolicy.RENAME
    stem, ext = os.path.splitext(safe_name)
    counter = 1
    while True:
        renamed = (directory / f"{stem} ({counter}){ext}").resolve()
        if not renamed.exists() and (forbid_same_as is None or renamed != forbid_same_as.resolve()):
            return renamed
        counter += 1
