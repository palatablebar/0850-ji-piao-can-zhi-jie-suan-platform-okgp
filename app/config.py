import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ROOT / "sample_data"
DB_PATH = os.getenv("WORKBENCH_DB", str(ROOT / "instance" / "workbench.sqlite3"))
MAX_FILE = 2 * 1024 * 1024
MAX_ROWS = 5000
