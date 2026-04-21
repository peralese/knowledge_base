import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# Disable git auto-commits during the test suite so pipeline scripts don't
# write to the repo when running tests with temporary directories.
os.environ.setdefault("GIT_DISABLED", "1")
