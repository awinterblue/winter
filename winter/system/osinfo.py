"""Operating-system detection — used to pick platform-specific backends."""
import sys

IS_MACOS = sys.platform == "darwin"
IS_WINDOWS = sys.platform == "win32"
