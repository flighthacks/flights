"""Allow running as `python -m autofare`."""
from .main import main
import sys

sys.exit(main())
