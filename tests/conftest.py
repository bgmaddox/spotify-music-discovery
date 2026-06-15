"""Make the project root importable so tests can `import lastfm`, `import tools`, etc.

The modules live at the repo root (flat layout), not in a package, so add the parent
dir to sys.path once for the whole test session.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
