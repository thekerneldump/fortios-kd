"""Common fixtures for FortiOS-KD tests."""

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable loading custom integrations in tests."""


@pytest.fixture
def hass_config_dir() -> str:
    """Use the FortiOS-KD repository root as Home Assistant's config directory."""
    return str(Path(__file__).resolve().parent.parent)
