import copy
import json
from datetime import datetime
from pathlib import Path

import pytest

from factory.common.config import load_config

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def base_config():
    config = load_config()
    # The sample data predates the platform list (Q18) and uses platform niches (Google Trends,
    # Trustpilot, ...) to exercise the Validator's rules, so tests keep them; test_scout_run covers the list.
    config["scout"]["exclude"]["platforms"] = []
    return config


@pytest.fixture
def config(base_config):
    """A deep copy, so a test can change thresholds without affecting others."""
    return copy.deepcopy(base_config)


@pytest.fixture(scope="session")
def fixtures_dir():
    return FIXTURES


@pytest.fixture(scope="session")
def as_of():
    manifest = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))
    return datetime.fromisoformat(manifest["as_of"])
