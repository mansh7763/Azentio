from pathlib import Path

import pytest
import yaml

from app.detect.config import load_rules
from app.detect.dataset import Dataset, prepare

GOLDEN = Path(__file__).resolve().parent / "golden"


@pytest.fixture(scope="session")
def cfg():
    return load_rules()


@pytest.fixture(scope="session")
def raw_golden():
    return Dataset.from_csv_dir(GOLDEN)


@pytest.fixture(scope="session")
def golden(raw_golden, cfg):
    return prepare(raw_golden, cfg)


@pytest.fixture(scope="session")
def expected():
    return yaml.safe_load((GOLDEN / "expected.yaml").read_text(encoding="utf-8"))
