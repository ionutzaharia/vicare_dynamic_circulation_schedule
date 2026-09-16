"""Validate integration metadata and translations."""

import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
INTEGRATION = ROOT / "custom_components" / "vicare_circulation"


def test_manifest_is_hacs_compatible() -> None:
    """The custom integration exposes required metadata."""
    manifest = json.loads((INTEGRATION / "manifest.json").read_text())
    assert manifest["domain"] == "vicare_circulation"
    assert manifest["config_flow"] is True
    assert manifest["version"] == "1.0.2"
    assert "application_credentials" in manifest["dependencies"]
    assert (INTEGRATION / "brand" / "icon.png").is_file()


def test_strings_and_translations_have_matching_sections() -> None:
    """German and English translations cover all integration-owned keys."""
    strings = json.loads((INTEGRATION / "strings.json").read_text())
    for language in ("de", "en"):
        translation = json.loads(
            (INTEGRATION / "translations" / f"{language}.json").read_text()
        )
        assert translation.keys() == strings.keys()
        assert (
            translation["config"]["abort"].keys() == strings["config"]["abort"].keys()
        )
        assert translation["entity"].keys() == strings["entity"].keys()
        assert translation["exceptions"].keys() == strings["exceptions"].keys()


def test_diagnostic_output_source_does_not_include_secret_fields() -> None:
    """The diagnostic implementation does not emit entry OAuth or target data."""
    source = (INTEGRATION / "diagnostics.py").read_text()
    forbidden = (
        "access_token",
        "refresh_token",
        "installation_id",
        "gateway_serial",
        "device_id",
        "device_serial",
    )
    for field in forbidden:
        assert field not in source
