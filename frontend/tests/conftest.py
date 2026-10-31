import os
import tempfile
from pathlib import Path

# Before any app import: C's tests use a throwaway database, never a developer's fraud.db.
os.environ["DATABASE_URL"] = f"sqlite:///{Path(tempfile.mkdtemp()).as_posix()}/test.db"
