import os
import tempfile
from pathlib import Path

# Before any app import: tests use a throwaway database, never a developer's fraud.db.
os.environ["GROQ_API_KEY"] = ""  # tests never call the LLM; the deterministic fallback is what they check
os.environ["DATABASE_URL"] = f"sqlite:///{Path(tempfile.mkdtemp()).as_posix()}/test.db"

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
