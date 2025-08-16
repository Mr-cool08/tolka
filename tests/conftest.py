import sys
from pathlib import Path
import werkzeug

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Flask 2.3 expects werkzeug.__version__ which was removed in Werkzeug 3
if not hasattr(werkzeug, "__version__"):
    werkzeug.__version__ = "3"
