# Project root directory
import os
from pathlib import Path

PROJECT_DIR = str(Path(os.path.dirname(__file__)).parent)

# Application directory. Used for module importation, tests...
APP_DIR = str(os.path.join(PROJECT_DIR, "app"))

TEMPLATE_DIR = str(os.path.join(PROJECT_DIR, "templates"))
