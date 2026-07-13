"""Runtime configuration loading and validation."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Optional


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load YAML configuration and optional ``.env`` values.

    A missing configuration file is valid; callers then receive an empty
    dictionary and ``GameTranslator`` applies its built-in defaults.
    """
    path = Path(config_path or "config.yaml")

    try:
        from dotenv import load_dotenv

        dotenv_path = path.parent / ".env"
        load_dotenv(dotenv_path=dotenv_path if dotenv_path.exists() else None)
    except ImportError:
        # dotenv is optional for library consumers.
        pass

    if not path.exists():
        return {}

    try:
        import yaml

        loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        raise ValueError(f"Unable to load configuration {path}: {exc}") from exc

    if not isinstance(loaded, dict):
        raise ValueError(f"Configuration {path} must contain a YAML mapping.")

    _validate_patterns(loaded)
    _validate_extraction(loaded)
    return loaded


def _validate_patterns(config: Dict[str, Any]) -> None:
    processing = config.get("processing", {})
    if not isinstance(processing, dict):
        raise ValueError("'processing' configuration must be a mapping.")

    for setting in ("skip_patterns", "preserve_patterns"):
        patterns = processing.get(setting, [])
        if not isinstance(patterns, list):
            raise ValueError(f"processing.{setting} must be a list.")
        for pattern in patterns:
            if not isinstance(pattern, str):
                raise ValueError(f"processing.{setting} contains a non-string pattern.")
            try:
                re.compile(pattern)
            except re.error as exc:
                raise ValueError(
                    f"Invalid regex in processing.{setting}: {pattern!r}: {exc}"
                ) from exc


def _validate_extraction(config: Dict[str, Any]) -> None:
    extraction = config.get('extraction', {})
    if not isinstance(extraction, dict):
        raise ValueError("'extraction' configuration must be a mapping.")

    rpgmv = extraction.get('rpgmv', {})
    if not isinstance(rpgmv, dict):
        raise ValueError("extraction.rpgmv must be a mapping.")

    command_codes = rpgmv.get('command_codes', [])
    if not isinstance(command_codes, list) or not all(isinstance(code, int) for code in command_codes):
        raise ValueError("extraction.rpgmv.command_codes must be a list of integers.")
    if not isinstance(rpgmv.get('include_notes', False), bool):
        raise ValueError("extraction.rpgmv.include_notes must be a boolean.")
